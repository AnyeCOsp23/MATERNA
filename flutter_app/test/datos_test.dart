// Base local (SQLite real, en memoria) y seguridad del PIN.
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:materna/datos/base_local.dart';
import 'package:materna/datos/seguridad.dart';
import 'package:materna/motor/carga_masiva.dart';
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

    test('el PIN no se guarda y cada dispositivo tiene su sal', () {
      final a = generarSal(), b = generarSal();
      expect(a, isNot(b));
      expect(derivarPin('1234', a), isNot(derivarPin('1234', b)));
      expect(verificarPin('1234', a, derivarPin('1234', a)), isTrue);
      expect(verificarPin('1235', a, derivarPin('1234', a)), isFalse);
      expect(pinValido('12a4') || pinValido('123') || pinValido('12345'), isFalse);
    });
  });

  group('perfil y PIN', () {
    test('configurar, verificar y bloquear tras 5 intentos', () async {
      final base = await baseNueva();
      expect(await base.tienePin(), isFalse);
      await base.configurar(pin: '2580', perfil: perfil);
      expect(await base.tienePin(), isTrue);
      expect((await base.perfil())!.ips, 'ESE Uribia');
      expect(await base.verificar('2580'), isTrue);
      final ahora = DateTime(2026, 11, 8, 10);
      for (var i = 0; i < intentosMaximos; i++) {
        expect(await base.verificar('0000', ahora: ahora), isFalse);
      }
      expect(await base.segundosDeBloqueo(ahora: ahora), greaterThan(0));
      expect(await base.verificar('2580', ahora: ahora), isFalse, reason: 'bloqueado, aunque sea el PIN correcto');
      expect(await base.verificar('2580', ahora: ahora.add(const Duration(seconds: segundosBloqueo + 1))), isTrue);
      await base.cerrar();
    });

    test('olvidé el PIN: se borra todo', () async {
      final base = await baseNueva();
      await base.configurar(pin: '2580', perfil: perfil);
      await base.guardar(recursos.evaluar(_rutina), perfil: perfil, versionModelo: 'v1', categoria: 'Bajo Riesgo');
      await base.fijarClaveIps(_clave);
      await base.guardarCarga(await _cargaEjemplo(), perfil: perfil, versionModelo: 'v1', clases: _clases, clave: _clave);
      await base.borrarTodo();
      expect(await base.tienePin(), isFalse);
      expect(await base.claveIps(), isNull);
      expect(await base.listar(), isEmpty);
      expect(await base.cargaPrevia((await _cargaEjemplo()).huellaArchivo), isNull);
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

    test('una base de la versión 1 (commit B) pasa a la 2 sin perder nada', () async {
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
            await bd.insert('ajustes', {'clave': 'ips', 'valor': 'ESE Valledupar'});
            await bd.insert('evaluaciones', {
              'fecha': '2026-11-08T10:00:00', 'atendido_por': 'Medico', 'ips': 'ESE Valledupar', 'categoria': 'Bajo Riesgo',
              'clase': 0, 'origen': 'modelo_ml', 'prob_bajo': .9, 'prob_medio': .1, 'prob_alto': 0, 'alertas': '[]',
              'registro': jsonEncode(_rutina), 'version_modelo': 'v1',
            });
          }));
      await v1.close();
      final base = await BaseLocal.abrir(databaseFactoryFfiNoIsolate, ruta);
      expect((await base.perfil())!.ips, 'ESE Valledupar');
      expect(await base.listar(), hasLength(1));
      await base.guardarCarga(await _cargaEjemplo(), perfil: perfil, versionModelo: 'v1', clases: _clases, clave: _clave);
      expect(await base.listar(limite: 1000), hasLength(301));
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
