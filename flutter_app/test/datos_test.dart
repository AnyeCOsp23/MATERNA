// Base local (SQLite real, en memoria) y seguridad del PIN.
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:materna/datos/base_local.dart';
import 'package:materna/datos/seguridad.dart';
import 'package:materna/motor/carga_masiva.dart';
import 'package:materna/motor/recursos.dart' show medirInferencia;
import 'package:materna/ui/pantallas/pantalla_acerca_de.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

import 'flujo_test.dart' show recursos;

const perfil = Perfil(atendidoPor: 'Auxiliar de enfermeria', ips: 'ESE Uribia', municipio: 'Uribia');

Future<BaseLocal> baseNueva() => BaseLocal.abrir(databaseFactoryFfiNoIsolate, inMemoryDatabasePath);

String hex(String base64) => base64Decode(base64).map((b) => b.toRadixString(16).padLeft(2, '0')).join();

void main() {
  group('PBKDF2-HMAC-SHA256', () {
    test('vectores de prueba conocidos (contraseña "password", sal "salt")', () {
      final sal = base64Encode(utf8.encode('salt'));
      expect(hex(derivarPin('password', sal, iteraciones: 1)), '120fb6cffcf8b32c43e7225256c4f837a86548c92ccc35480805987cb70be17b');
      expect(hex(derivarPin('password', sal, iteraciones: 2)), 'ae4d0c95af6b46d32d0adff928f06dd02a303f8ef3c251dfd6e2d85a95474c43');
    });

    test('el PIN no se guarda y cada cuenta tiene su sal', () {
      final a = generarSal(), b = generarSal();
      expect(a, isNot(b));
      expect(derivarPin('1234', a), isNot(derivarPin('1234', b)));
      expect(verificarPin('1234', a, derivarPin('1234', a)), isTrue);
      expect(verificarPin('1235', a, derivarPin('1234', a)), isFalse);
      expect(pinValido('12a4') || pinValido('123') || pinValido('12345'), isFalse);
    });
  });

  group('código de recuperación', () {
    test('8 caracteres sin letras confusas; se acepta con o sin guion', () {
      final c = generarCodigoRecuperacion();
      expect(c, matches(RegExp(r'^[A-HJ-NP-Z2-9]{4}-[A-HJ-NP-Z2-9]{4}$')));
      expect(normalizarCodigo(' ${c.toLowerCase().replaceAll('-', ' ')} '), c.replaceAll('-', ''));
      expect(generarCodigoRecuperacion(), isNot(c));
    });
  });

  group('cuentas de usuario', () {
    test('registrar, entrar y bloquear tras 5 intentos solo esa cuenta', () async {
      final base = await baseNueva();
      final codigo = await base.registrar(usuario: ' Auxiliar.Rural ', pin: '2580', perfil: perfil);
      expect(codigo, hasLength(9));
      await base.registrar(usuario: 'medico.uribia', pin: '1357', perfil: perfil);
      expect(() => base.registrar(usuario: 'auxiliar.rural', pin: '1111', perfil: perfil), throwsA(isA<UsuarioRepetido>()));
      expect(() => base.registrar(usuario: 'a b', pin: '1111', perfil: perfil), throwsArgumentError);

      final entro = await base.entrar('AUXILIAR.RURAL', '2580');
      expect(entro, isA<AccesoConcedido>());
      final perfilEntrado = (entro as AccesoConcedido).perfil;
      expect(perfilEntrado.usuario, 'auxiliar.rural');
      expect(perfilEntrado.ips, 'ESE Uribia');
      expect(perfilEntrado.id, isNotNull);
      expect(await base.entrar('nadie', '2580'), isA<AccesoDenegado>());

      final ahora = DateTime(2026, 11, 8, 10);
      for (var i = 0; i < intentosMaximos; i++) {
        expect(await base.entrar('auxiliar.rural', '0000', ahora: ahora), isA<AccesoDenegado>());
      }
      final bloqueado = await base.entrar('auxiliar.rural', '2580', ahora: ahora);
      expect((bloqueado as AccesoDenegado).segundosDeBloqueo, greaterThan(0), reason: 'bloqueado, aunque sea el PIN correcto');
      expect(await base.entrar('medico.uribia', '1357', ahora: ahora), isA<AccesoConcedido>(), reason: 'las demás cuentas no');
      expect(await base.entrar('auxiliar.rural', '2580', ahora: ahora.add(const Duration(seconds: segundosBloqueo + 1))),
          isA<AccesoConcedido>());
      await base.cerrar();
    });

    test('PIN olvidado, nivel 1: con el código de recuperación, sin perder nada', () async {
      final base = await baseNueva();
      final codigo = await base.registrar(usuario: 'auxiliar.rural', pin: '2580', perfil: perfil);
      final yo = (await base.perfilDe('auxiliar.rural'))!;
      await base.guardar(recursos.evaluar(_rutina), perfil: yo, versionModelo: 'v1', categoria: 'Bajo Riesgo');
      expect(await base.restablecerConCodigo('auxiliar.rural', 'AAAA-AAAA', '1111'), isNull);
      final nuevo = await base.restablecerConCodigo('auxiliar.rural', codigo.toLowerCase(), '1111');
      expect(nuevo, isNotNull);
      expect(nuevo, isNot(codigo));
      expect(await base.entrar('auxiliar.rural', '2580'), isA<AccesoDenegado>());
      expect(await base.entrar('auxiliar.rural', '1111'), isA<AccesoConcedido>());
      expect(await base.restablecerConCodigo('auxiliar.rural', codigo, '2222'), isNull, reason: 'el código viejo ya no sirve');
      expect(await base.listar(idUsuario: yo.id), hasLength(1));
      await base.cerrar();
    });

    test('PIN olvidado, nivel 2: el responsable con la clave de la IPS', () async {
      final base = await baseNueva();
      await base.registrar(usuario: 'auxiliar.rural', pin: '2580', perfil: perfil);
      expect(await base.restablecerConClaveIps('auxiliar.rural', _clave, '1111'), isNull, reason: 'sin clave configurada');
      await base.fijarClaveIps(_clave);
      expect(await base.restablecerConClaveIps('auxiliar.rural', '${_clave}x', '1111'), isNull);
      expect(await base.restablecerConClaveIps('auxiliar.rural', _clave, '1111'), isNotNull);
      expect(await base.entrar('auxiliar.rural', '1111'), isA<AccesoConcedido>());
      await base.cerrar();
    });

    test('nivel 3: eliminar solo esa cuenta con sus evaluaciones y cargas', () async {
      final base = await baseNueva();
      await base.registrar(usuario: 'auxiliar.rural', pin: '2580', perfil: perfil);
      await base.registrar(usuario: 'medico.uribia', pin: '1357', perfil: perfil);
      final a = (await base.perfilDe('auxiliar.rural'))!;
      final b = (await base.perfilDe('medico.uribia'))!;
      await base.guardar(recursos.evaluar(_rutina), perfil: a, versionModelo: 'v1', categoria: 'Bajo Riesgo');
      await base.guardar(recursos.evaluar(_rutina), perfil: b, versionModelo: 'v1', categoria: 'Bajo Riesgo');
      final carga = await _cargaEjemplo();
      await base.guardarCarga(carga, perfil: a, versionModelo: 'v1', clases: _clases, clave: _clave);
      await base.eliminarUsuario('auxiliar.rural');
      expect(await base.existeUsuario('auxiliar.rural'), isFalse);
      expect(await base.listar(idUsuario: a.id), isEmpty);
      expect(await base.cargaPrevia(carga.huellaArchivo, idUsuario: a.id), isNull);
      expect(await base.listar(idUsuario: b.id), hasLength(1));
      expect(await base.entrar('medico.uribia', '1357'), isA<AccesoConcedido>());
      await base.cerrar();
    });

    test('cada usuario ve solo sus evaluaciones, su sincronización y sus cargas', () async {
      final base = await baseNueva();
      await base.registrar(usuario: 'auxiliar.rural', pin: '2580', perfil: perfil);
      await base.registrar(usuario: 'medico.uribia', pin: '1357', perfil: perfil);
      final a = (await base.perfilDe('auxiliar.rural'))!;
      final b = (await base.perfilDe('medico.uribia'))!;
      await base.guardar(recursos.evaluar(_rutina), perfil: a, versionModelo: 'v1', categoria: 'Bajo Riesgo');
      final carga = await _cargaEjemplo();
      await base.guardarCarga(carga, perfil: b, versionModelo: 'v1', clases: _clases, clave: _clave);
      expect(await base.listar(idUsuario: a.id), hasLength(1));
      expect(await base.listar(idUsuario: b.id, limite: 1000), hasLength(300));
      expect(await base.cargaPrevia(carga.huellaArchivo, idUsuario: a.id), isNull);
      expect(await base.cargaPrevia(carga.huellaArchivo, idUsuario: b.id), isNotNull);
      expect(await base.pendientesDeSincronizar(idUsuario: a.id), 1);
      expect(await base.marcarSincronizadas(idUsuario: a.id), 1);
      expect(await base.pendientesDeSincronizar(idUsuario: b.id), 300);
      await base.cerrar();
    });
  });

  group('evaluaciones', () {
    test('se guardan sin identidad, con su resultado, y se filtran', () async {
      final base = await baseNueva();
      final rutina = recursos.evaluar(_rutina);
      final emergencia = recursos.evaluar({..._rutina, 'pas_mmhg': 170});
      await base.guardar(rutina, perfil: perfil, versionModelo: 'v1', categoria: 'Bajo Riesgo');
      await base.guardar(emergencia, perfil: perfil, versionModelo: 'v1', categoria: 'Alto Riesgo');
      final todas = await base.listar();
      expect(todas.length, 2);
      expect(todas.first.clase, 2, reason: 'la más reciente primero');
      expect(todas.first.origen, 'regla_clinica');
      expect(todas.first.registro['pas_mmhg'], 170);
      expect(todas.first.atendidoPor, 'Auxiliar de enfermeria');
      expect((await base.listar(clase: 0)).single.categoria, 'Bajo Riesgo');
      expect(await base.listar(desde: DateTime.now().add(const Duration(days: 1))), isEmpty);
      await base.cerrar();
    });

    test('sincronización simulada', () async {
      final base = await baseNueva();
      await base.guardar(recursos.evaluar(_rutina), perfil: perfil, versionModelo: 'v1', categoria: 'Bajo Riesgo');
      expect(await base.pendientesDeSincronizar(), 1);
      expect(await base.marcarSincronizadas(), 1);
      expect(await base.pendientesDeSincronizar(), 0);
      expect((await base.listar()).single.sincronizado, isTrue);
      await base.cerrar();
    });
  });

  group('carga masiva', () {
    test('la clave de la IPS se valida y se guarda en el dispositivo', () async {
      final base = await baseNueva();
      expect(await base.claveIps(), isNull);
      expect(() => base.fijarClaveIps('corta'), throwsArgumentError);
      await base.fijarClaveIps(_clave);
      expect(await base.claveIps(), _clave);
      await base.cerrar();
    });

    test('se guarda toda la carga en una transacción, con el seudónimo y sin documentos', () async {
      final base = await baseNueva();
      final carga = await _cargaEjemplo();
      expect(await base.cargaPrevia(carga.huellaArchivo), isNull);
      final id = await base.guardarCarga(carga, perfil: perfil, versionModelo: 'v1', clases: _clases, clave: _clave);
      final todas = await base.listar(limite: 1000);
      expect(todas, hasLength(carga.resultados.length));
      expect(todas.every((r) => r.idCarga == id), isTrue);
      expect(todas.where((r) => r.idSeudonimo != null), hasLength(carga.resultados.where((r) => r.idSeudonimo != null).length));
      expect(todas.map((r) => jsonEncode(r.registro)).join().contains('FICTICIO'), isFalse);
      final urgente = carga.resultados.first;
      final encontradas = await base.listar(seudonimo: urgente.idSeudonimo);
      expect(encontradas.first.clase, urgente.evaluacion.clase);
      final previa = (await base.cargaPrevia(carga.huellaArchivo))!;
      expect((previa.id, previa.archivo, previa.evaluadas, previa.sinEvaluar), (id, 'ips_ficticio_3280.csv', 300, 3));
      await base.cerrar();
    });

    test('una base de la versión 1 (commit B) pasa a la 3: se descarta el perfil viejo y sus datos de prueba', () async {
      final carpeta = Directory.systemTemp.createTempSync('materna_');
      addTearDown(() => carpeta.deleteSync(recursive: true));
      final ruta = '${carpeta.path}/materna.db';
      final v1 = await databaseFactoryFfiNoIsolate.openDatabase(ruta,
          options: OpenDatabaseOptions(version: 1, onCreate: (bd, _) async {
            await bd.execute('CREATE TABLE ajustes (clave TEXT PRIMARY KEY, valor TEXT NOT NULL)');
            await bd.execute('''CREATE TABLE evaluaciones (
              id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT NOT NULL, atendido_por TEXT NOT NULL, ips TEXT NOT NULL,
              categoria TEXT NOT NULL, clase INTEGER NOT NULL, origen TEXT NOT NULL,
              prob_bajo REAL NOT NULL, prob_medio REAL NOT NULL, prob_alto REAL NOT NULL,
              alertas TEXT NOT NULL, registro TEXT NOT NULL, version_modelo TEXT NOT NULL,
              id_seudonimo TEXT, id_carga INTEGER, sincronizado INTEGER NOT NULL DEFAULT 0)''');
            await bd.insert('ajustes', {'clave': 'atendido_por', 'valor': 'Medico'});
            await bd.insert('ajustes', {'clave': 'clave_ips', 'valor': _clave});
            await bd.insert('ajustes', {'clave': 'ips', 'valor': 'ESE Valledupar'});
            await bd.insert('evaluaciones', {
              'fecha': '2026-11-08T10:00:00', 'atendido_por': 'Medico', 'ips': 'ESE Valledupar', 'categoria': 'Bajo Riesgo',
              'clase': 0, 'origen': 'modelo_ml', 'prob_bajo': .9, 'prob_medio': .1, 'prob_alto': 0, 'alertas': '[]',
              'registro': jsonEncode(_rutina), 'version_modelo': 'v1',
            });
          }));
      await v1.close();
      final base = await BaseLocal.abrir(databaseFactoryFfiNoIsolate, ruta);
      expect(await base.listar(), isEmpty, reason: 'evaluaciones de prueba descartadas');
      expect(await base.claveIps(), _clave, reason: 'la clave de la IPS es del dispositivo y se conserva');
      await base.registrar(usuario: 'medico.valledupar', pin: '2580', perfil: perfil);
      final yo = (await base.perfilDe('medico.valledupar'))!;
      await base.guardarCarga(await _cargaEjemplo(), perfil: yo, versionModelo: 'v1', clases: _clases, clave: _clave);
      expect(await base.listar(idUsuario: yo.id, limite: 1000), hasLength(300));
      await base.cerrar();
    });
  });

  test('versión de la app igual a la de pubspec.yaml', () {
    expect(File('pubspec.yaml').readAsStringSync(), contains('version: $versionApp+'));
  });

  test('la inferencia completa tarda menos de 5 ms', () {
    expect(medirInferencia(recursos), lessThan(5));
  });
}

const _clave = 'clave-de-prueba-de-la-ips-2026';
const _clases = ['Bajo Riesgo', 'Riesgo Medio', 'Alto Riesgo'];

Future<CargaMasiva> _cargaEjemplo() => procesarCarga(
    nombre: 'ips_ficticio_3280.csv',
    bytes: File('../data/ejemplos/ips_ficticio_3280.csv').readAsBytesSync(),
    recursos: recursos,
    sal: _clave);

const _rutina = {
  'edad': 27, 'area_residencia': 'Cabecera', 'semanas_gestacion': 28, 'n_controles_prenatales': 5,
  'atendido_por': 'Medico', 'pas_mmhg': 110, 'pad_mmhg': 70, 'fcf_bpm': 142.0, 'glucosa_mgdl': 88.0,
  'proteinuria': 0, 'convulsiones': 0,
};
