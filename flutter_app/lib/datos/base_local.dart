/// Base de datos local del dispositivo (SQLite): perfil del operador, PIN, clave de la IPS, evaluaciones y cargas
/// masivas. 100 % offline.
///
/// La misma clase sirve en Android/iOS (sqflite), en la web (SQLite en WebAssembly) y en las pruebas (SQLite
/// por FFI): solo cambia la fábrica que recibe `abrir` (ver fabrica_bd.dart). Las pantallas solo conocen esta
/// clase, así que conectar un servidor de sincronización más adelante no las obliga a cambiar.
library;

import 'dart:convert';

import 'package:sqflite/sqflite.dart';

import '../motor/carga_masiva.dart';
import '../motor/recursos.dart';
import 'seguridad.dart';
import 'seudonimizacion.dart';

/// 1: perfil, PIN y evaluaciones (commit B) · 2: cargas masivas de la IPS.
const _version = 2;

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
        idCarga = f['id_carga'] as int?,
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

  /// La carga masiva de la que viene (null si es un triaje individual).
  final int? idCarga;
  final bool sincronizado;
}

/// Una carga masiva guardada: de qué archivo y cuántas filas (sin datos de las gestantes).
class RegistroCarga {
  RegistroCarga.desdeFila(Map<String, Object?> f)
      : id = f['id'] as int,
        fecha = DateTime.parse(f['fecha'] as String),
        archivo = f['archivo'] as String,
        evaluadas = f['evaluadas'] as int,
        sinEvaluar = f['sin_evaluar'] as int;

  final int id;
  final DateTime fecha;
  final String archivo;
  final int evaluadas;
  final int sinEvaluar;
}

class BaseLocal {
  BaseLocal._(this._bd);

  final Database _bd;

  static Future<BaseLocal> abrir(DatabaseFactory fabrica, String ruta) async {
    final bd = await fabrica.openDatabase(ruta,
        options: OpenDatabaseOptions(version: _version, onUpgrade: (bd, anterior, _) async {
          if (anterior < 2) await _crearCargas(bd);
        }, onCreate: (bd, _) async {
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
          await _crearCargas(bd);
        }));
    return BaseLocal._(bd);
  }

  /// Cada carga guarda el archivo, su huella SHA-256 (para avisar si se carga dos veces) y la huella de la clave
  /// de la IPS con que se seudonimizó; nunca el contenido del archivo.
  static Future<void> _crearCargas(Database bd) async {
    await bd.execute('''CREATE TABLE cargas (
      id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT NOT NULL, archivo TEXT NOT NULL, sha256 TEXT NOT NULL,
      formato TEXT NOT NULL, filas_leidas INTEGER NOT NULL, evaluadas INTEGER NOT NULL, sin_evaluar INTEGER NOT NULL,
      duplicadas INTEGER NOT NULL, huella_clave TEXT NOT NULL, atendido_por TEXT NOT NULL, ips TEXT NOT NULL)''');
    await bd.execute('CREATE INDEX cargas_sha256 ON cargas (sha256)');
    await bd.execute('CREATE INDEX evaluaciones_carga ON evaluaciones (id_carga)');
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
        await t.delete('cargas');
      });

  // ------------------------------------------------------------------ clave de la IPS
  /// Clave secreta de la IPS para seudonimizar los documentos (la misma en todos sus dispositivos).
  Future<String?> claveIps() => _ajuste('clave_ips');

  Future<void> fijarClaveIps(String clave) async {
    if (!salValida(clave)) throw ArgumentError('La clave debe tener al menos $longitudMinimaSal caracteres.');
    await _fijar({'clave_ips': clave});
  }

  // ------------------------------------------------------------------ evaluaciones
  Map<String, Object?> _fila(Evaluacion e, Perfil perfil, String versionModelo, String categoria,
      {String? idSeudonimo, int? idCarga, DateTime? fecha}) {
    final p = e.triaje.probabilidades;
    return {
      'fecha': (fecha ?? DateTime.now()).toIso8601String(),
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
      'id_carga': idCarga,
    };
  }

  Future<int> guardar(Evaluacion e, {required Perfil perfil, required String versionModelo, required String categoria, String? idSeudonimo}) =>
      _bd.insert('evaluaciones', _fila(e, perfil, versionModelo, categoria, idSeudonimo: idSeudonimo));

  /// Guarda una carga masiva y todas sus evaluaciones en una sola transacción (todo o nada). Devuelve su id.
  Future<int> guardarCarga(CargaMasiva carga,
      {required Perfil perfil, required String versionModelo, required List<String> clases, required String clave}) {
    final fecha = DateTime.now();
    return _bd.transaction((t) async {
      final id = await t.insert('cargas', {
        'fecha': fecha.toIso8601String(),
        'archivo': carga.archivo,
        'sha256': carga.huellaArchivo,
        'formato': carga.reporte.formato,
        'filas_leidas': carga.reporte.filasLeidas,
        'evaluadas': carga.resultados.length,
        'sin_evaluar': carga.rechazadas.length,
        'duplicadas': carga.reporte.filasDuplicadas,
        'huella_clave': huellaSal(clave),
        'atendido_por': perfil.atendidoPor,
        'ips': perfil.ips,
      });
      final lote = t.batch();
      for (final r in carga.resultados) {
        lote.insert('evaluaciones', _fila(r.evaluacion, perfil, versionModelo, clases[r.evaluacion.clase],
            idSeudonimo: r.idSeudonimo, idCarga: id, fecha: fecha));
      }
      await lote.commit(noResult: true);
      return id;
    });
  }

  /// La carga anterior del mismo archivo (misma huella SHA-256), si la hay.
  Future<RegistroCarga?> cargaPrevia(String sha256) async {
    final filas = await _bd.query('cargas', where: 'sha256 = ?', whereArgs: [sha256], orderBy: 'id DESC', limit: 1);
    return filas.isEmpty ? null : RegistroCarga.desdeFila(filas.single);
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
