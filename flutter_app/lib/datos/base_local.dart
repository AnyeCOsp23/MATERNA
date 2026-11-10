/// Base de datos local del dispositivo (SQLite): perfil del operador, PIN y evaluaciones. 100 % offline.
///
/// La misma clase sirve en Android/iOS (sqflite), en la web (SQLite en WebAssembly) y en las pruebas (SQLite
/// por FFI): solo cambia la fábrica que recibe `abrir` (ver fabrica_bd.dart). Las pantallas solo conocen esta
/// clase, así que conectar un servidor de sincronización más adelante no las obliga a cambiar.
library;

import 'dart:convert';

import 'package:sqflite/sqflite.dart';

import '../motor/recursos.dart';
import 'seguridad.dart';

const _version = 1;

/// Quién usa el dispositivo. `atendidoPor` es una de las 4 categorías que conoce el modelo.
class Perfil {
  const Perfil({required this.atendidoPor, required this.ips, this.municipio});

  final String atendidoPor;
  final String ips;
  final String? municipio;
}

/// Una evaluación guardada (sin nombre ni documento).
class RegistroEvaluacion {
  RegistroEvaluacion.desdeFila(Map<String, Object?> f)
      : id = f['id'] as int,
        fecha = DateTime.parse(f['fecha'] as String),
        atendidoPor = f['atendido_por'] as String,
        ips = f['ips'] as String,
        categoria = f['categoria'] as String,
        clase = f['clase'] as int,
        origen = f['origen'] as String,
        probabilidadAlto = (f['prob_alto'] as num).toDouble(),
        alertas = List<String>.from(jsonDecode(f['alertas'] as String) as List),
        registro = jsonDecode(f['registro'] as String) as Map<String, dynamic>,
        versionModelo = f['version_modelo'] as String,
        idSeudonimo = f['id_seudonimo'] as String?,
        sincronizado = (f['sincronizado'] as int) == 1;

  final int id;
  final DateTime fecha;
  final String atendidoPor;
  final String ips;
  final String categoria;
  final int clase;
  final String origen;
  final double probabilidadAlto;
  final List<String> alertas;
  final Map<String, dynamic> registro;
  final String versionModelo;
  final String? idSeudonimo;
  final bool sincronizado;
}

class BaseLocal {
  BaseLocal._(this._bd);

  final Database _bd;

  static Future<BaseLocal> abrir(DatabaseFactory fabrica, String ruta) async {
    final bd = await fabrica.openDatabase(ruta,
        options: OpenDatabaseOptions(version: _version, onCreate: (bd, _) async {
          await bd.execute('CREATE TABLE ajustes (clave TEXT PRIMARY KEY, valor TEXT NOT NULL)');
          await bd.execute('''CREATE TABLE evaluaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT NOT NULL, atendido_por TEXT NOT NULL, ips TEXT NOT NULL,
            categoria TEXT NOT NULL, clase INTEGER NOT NULL, origen TEXT NOT NULL,
            prob_bajo REAL NOT NULL, prob_medio REAL NOT NULL, prob_alto REAL NOT NULL,
            alertas TEXT NOT NULL, registro TEXT NOT NULL, version_modelo TEXT NOT NULL,
            id_seudonimo TEXT, id_carga INTEGER, sincronizado INTEGER NOT NULL DEFAULT 0)''');
          // índices para que el historial siga rápido con miles de evaluaciones
          await bd.execute('CREATE INDEX evaluaciones_fecha ON evaluaciones (fecha)');
          await bd.execute('CREATE INDEX evaluaciones_clase ON evaluaciones (clase)');
          await bd.execute('CREATE INDEX evaluaciones_seudonimo ON evaluaciones (id_seudonimo)');
        }));
    return BaseLocal._(bd);
  }

  Future<void> cerrar() => _bd.close();

  // ------------------------------------------------------------------ ajustes, perfil y PIN
  Future<String?> _ajuste(String clave) async {
    final filas = await _bd.query('ajustes', where: 'clave = ?', whereArgs: [clave]);
    return filas.isEmpty ? null : filas.single['valor'] as String;
  }

  Future<void> _fijar(Map<String, String?> valores) => _bd.transaction((t) async {
        for (final e in valores.entries) {
          if (e.value == null) {
            await t.delete('ajustes', where: 'clave = ?', whereArgs: [e.key]);
          } else {
            await t.insert('ajustes', {'clave': e.key, 'valor': e.value}, conflictAlgorithm: ConflictAlgorithm.replace);
          }
        }
      });

  Future<bool> tienePin() async => await _ajuste('pin_derivado') != null;

  Future<Perfil?> perfil() async {
    final atiende = await _ajuste('atendido_por');
    if (atiende == null) return null;
    return Perfil(atendidoPor: atiende, ips: (await _ajuste('ips'))!, municipio: await _ajuste('municipio'));
  }

  Future<void> configurar({required String pin, required Perfil perfil}) async {
    if (!pinValido(pin)) throw ArgumentError('El PIN debe tener 4 dígitos.');
    final sal = generarSal();
    await _fijar({
      'pin_sal': sal,
      'pin_derivado': derivarPin(pin, sal),
      'atendido_por': perfil.atendidoPor,
      'ips': perfil.ips,
      'municipio': perfil.municipio,
      'intentos': '0',
      'bloqueado_hasta': null,
    });
  }

  /// Segundos de bloqueo que faltan (0 si se puede intentar).
  Future<int> segundosDeBloqueo({DateTime? ahora}) async {
    final hasta = await _ajuste('bloqueado_hasta');
    if (hasta == null) return 0;
    final faltan = DateTime.parse(hasta).difference(ahora ?? DateTime.now()).inSeconds;
    return faltan > 0 ? faltan + 1 : 0;
  }

  /// Verifica el PIN. Tras [intentosMaximos] fallos seguidos bloquea [segundosBloqueo] segundos.
  Future<bool> verificar(String pin, {DateTime? ahora}) async {
    if (await segundosDeBloqueo(ahora: ahora) > 0) return false;
    final sal = await _ajuste('pin_sal');
    final derivado = await _ajuste('pin_derivado');
    if (sal == null || derivado == null) return false;
    if (verificarPin(pin, sal, derivado)) {
      await _fijar({'intentos': '0', 'bloqueado_hasta': null});
      return true;
    }
    final intentos = int.parse(await _ajuste('intentos') ?? '0') + 1;
    await _fijar(intentos >= intentosMaximos
        ? {'intentos': '0', 'bloqueado_hasta': (ahora ?? DateTime.now()).add(const Duration(seconds: segundosBloqueo)).toIso8601String()}
        : {'intentos': '$intentos'});
    return false;
  }

  /// PIN olvidado: no hay servidor desde el cual recuperarlo, así que se borra todo lo del dispositivo.
  Future<void> borrarTodo() => _bd.transaction((t) async {
        await t.delete('ajustes');
        await t.delete('evaluaciones');
      });

  // ------------------------------------------------------------------ evaluaciones
  Future<int> guardar(Evaluacion e, {required Perfil perfil, required String versionModelo, required String categoria, String? idSeudonimo}) {
    final p = e.triaje.probabilidades;
    return _bd.insert('evaluaciones', {
      'fecha': DateTime.now().toIso8601String(),
      'atendido_por': perfil.atendidoPor,
      'ips': perfil.ips,
      'categoria': categoria,
      'clase': e.clase,
      'origen': e.origen,
      'prob_bajo': p[0],
      'prob_medio': p[1],
      'prob_alto': p[2],
      'alertas': jsonEncode([for (final a in e.alertas) a.variable]),
      'registro': jsonEncode(e.registro),
      'version_modelo': versionModelo,
      'id_seudonimo': idSeudonimo,
    });
  }

  /// Evaluaciones de la más reciente a la más antigua, con filtros opcionales.
  Future<List<RegistroEvaluacion>> listar({int? clase, DateTime? desde, String? seudonimo, int limite = 500}) async {
    final condiciones = <String>[];
    final argumentos = <Object?>[];
    if (clase != null) {
      condiciones.add('clase = ?');
      argumentos.add(clase);
    }
    if (desde != null) {
      condiciones.add('fecha >= ?');
      argumentos.add(desde.toIso8601String());
    }
    if (seudonimo != null && seudonimo.trim().isNotEmpty) {
      condiciones.add('id_seudonimo LIKE ?');
      argumentos.add('${seudonimo.trim()}%');
    }
    final filas = await _bd.query('evaluaciones',
        where: condiciones.isEmpty ? null : condiciones.join(' AND '),
        whereArgs: argumentos,
        orderBy: 'fecha DESC, id DESC',
        limit: limite);
    return filas.map(RegistroEvaluacion.desdeFila).toList();
  }

  Future<int> pendientesDeSincronizar() async =>
      (await _bd.rawQuery('SELECT COUNT(*) AS n FROM evaluaciones WHERE sincronizado = 0')).single['n'] as int;

  /// Simulación: marca como sincronizadas las pendientes (no hay servidor; no se envía ningún dato).
  Future<int> marcarSincronizadas() => _bd.update('evaluaciones', {'sincronizado': 1}, where: 'sincronizado = 0');
}
