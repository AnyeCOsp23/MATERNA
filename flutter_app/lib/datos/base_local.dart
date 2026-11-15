/// Base de datos local del dispositivo (SQLite): cuentas de usuario, clave de la IPS, evaluaciones y cargas
/// masivas. 100 % offline.
///
/// Varias personas pueden usar el mismo dispositivo, cada una con su usuario y su PIN; cada una ve solo sus
/// evaluaciones y cargas. El PIN y el código de recuperación nunca se guardan: solo su derivación PBKDF2 con sal
/// (seguridad.dart). Si se olvida el PIN hay tres salidas, de menos a más drástica: el código de recuperación,
/// la clave de la IPS (el responsable de datos) o eliminar solo esa cuenta.
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

/// 1: perfil, PIN y evaluaciones (commit B) · 2: cargas masivas de la IPS · 3: varias cuentas de usuario.
const _version = 3;

/// Quién usa la app. `atendidoPor` es una de las 4 categorías que conoce el modelo. `id` y `usuario` son null
/// solo en las pruebas que no pasan por el acceso.
class Perfil {
  const Perfil({this.id, this.usuario, required this.atendidoPor, required this.ips, this.municipio});

  Perfil.desdeFila(Map<String, Object?> f)
      : id = f['id'] as int,
        usuario = f['usuario'] as String,
        atendidoPor = f['atendido_por'] as String,
        ips = f['ips'] as String,
        municipio = f['municipio'] as String?;

  final int? id;
  final String? usuario;
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

/// Resultado de un intento de entrar.
sealed class ResultadoAcceso {
  const ResultadoAcceso();
}

class AccesoConcedido extends ResultadoAcceso {
  const AccesoConcedido(this.perfil);

  final Perfil perfil;
}

class AccesoDenegado extends ResultadoAcceso {
  const AccesoDenegado({this.segundosDeBloqueo = 0});

  /// > 0 si la cuenta quedó (o estaba) bloqueada por intentos fallidos.
  final int segundosDeBloqueo;
}

/// El usuario ya existe al registrarse.
class UsuarioRepetido implements Exception {
  const UsuarioRepetido();
}

/// 'Auxiliar.Rural ' -> 'auxiliar.rural'.
String normalizarUsuario(String usuario) => usuario.trim().toLowerCase();

/// Letras minúsculas, números, punto, guion y guion bajo; de 3 a 30 caracteres.
bool usuarioValido(String usuario) => RegExp(r'^[a-z0-9._-]{3,30}$').hasMatch(normalizarUsuario(usuario));

class BaseLocal {
  BaseLocal._(this._bd);

  final Database _bd;

  static Future<BaseLocal> abrir(DatabaseFactory fabrica, String ruta) async {
    final bd = await fabrica.openDatabase(ruta,
        options: OpenDatabaseOptions(version: _version, onUpgrade: (bd, anterior, _) async {
          if (anterior < 2) await _crearCargas(bd);
          if (anterior < 3) await _pasarACuentas(bd);
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
          await _pasarACuentas(bd);
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

  /// Versión 3: cuentas de usuario. El perfil único de las versiones anteriores (sin nombre de usuario) y sus
  /// evaluaciones de prueba se descartan; la clave de la IPS se conserva porque es del dispositivo.
  static Future<void> _pasarACuentas(Database bd) async {
    await bd.execute('''CREATE TABLE usuarios (
      id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT NOT NULL UNIQUE, atendido_por TEXT NOT NULL,
      ips TEXT NOT NULL, municipio TEXT, pin_sal TEXT NOT NULL, pin_derivado TEXT NOT NULL,
      codigo_sal TEXT NOT NULL, codigo_derivado TEXT NOT NULL, intentos INTEGER NOT NULL DEFAULT 0,
      bloqueado_hasta TEXT, creado TEXT NOT NULL)''');
    await bd.execute('ALTER TABLE evaluaciones ADD COLUMN id_usuario INTEGER');
    await bd.execute('ALTER TABLE cargas ADD COLUMN id_usuario INTEGER');
    await bd.execute('CREATE INDEX evaluaciones_usuario ON evaluaciones (id_usuario)');
    await bd.delete('evaluaciones');
    await bd.delete('cargas');
    await bd.delete('ajustes', where: 'clave <> ?', whereArgs: ['clave_ips']);
  }

  Future<void> cerrar() => _bd.close();

  // ------------------------------------------------------------------ ajustes del dispositivo
  Future<String?> _ajuste(String clave) async {
    final filas = await _bd.query('ajustes', where: 'clave = ?', whereArgs: [clave]);
    return filas.isEmpty ? null : filas.single['valor'] as String;
  }

  /// Clave secreta de la IPS para seudonimizar los documentos (la misma en todos sus dispositivos). También sirve
  /// al responsable de datos para poner un PIN nuevo a quien perdió su PIN y su código de recuperación.
  Future<String?> claveIps() => _ajuste('clave_ips');

  Future<void> fijarClaveIps(String clave) async {
    if (!salValida(clave)) throw ArgumentError('La clave debe tener al menos $longitudMinimaSal caracteres.');
    await _bd.insert('ajustes', {'clave': 'clave_ips', 'valor': clave}, conflictAlgorithm: ConflictAlgorithm.replace);
  }

  // ------------------------------------------------------------------ cuentas
  Future<Map<String, Object?>?> _usuario(String usuario) async {
    final filas = await _bd.query('usuarios', where: 'usuario = ?', whereArgs: [normalizarUsuario(usuario)]);
    return filas.isEmpty ? null : filas.single;
  }

  Future<bool> existeUsuario(String usuario) async => await _usuario(usuario) != null;

  /// Crea la cuenta y devuelve su código de recuperación (se muestra una sola vez).
  Future<String> registrar({required String usuario, required String pin, required Perfil perfil}) async {
    if (!usuarioValido(usuario)) throw ArgumentError('Usuario no válido.');
    if (!pinValido(pin)) throw ArgumentError('El PIN debe tener 4 dígitos.');
    if (await existeUsuario(usuario)) throw const UsuarioRepetido();
    final codigo = generarCodigoRecuperacion();
    final (pinSal, codigoSal) = (generarSal(), generarSal());
    await _bd.insert('usuarios', {
      'usuario': normalizarUsuario(usuario),
      'atendido_por': perfil.atendidoPor,
      'ips': perfil.ips,
      'municipio': perfil.municipio,
      'pin_sal': pinSal,
      'pin_derivado': derivarPin(pin, pinSal),
      'codigo_sal': codigoSal,
      'codigo_derivado': derivarPin(normalizarCodigo(codigo), codigoSal),
      'creado': DateTime.now().toIso8601String(),
    });
    return codigo;
  }

  Future<Perfil?> perfilDe(String usuario) async {
    final f = await _usuario(usuario);
    return f == null ? null : Perfil.desdeFila(f);
  }

  int _segundosDeBloqueo(Map<String, Object?> f, DateTime ahora) {
    final hasta = f['bloqueado_hasta'] as String?;
    if (hasta == null) return 0;
    final faltan = DateTime.parse(hasta).difference(ahora).inSeconds;
    return faltan > 0 ? faltan + 1 : 0;
  }

  /// Cuenta un intento fallido; tras [intentosMaximos] seguidos bloquea [segundosBloqueo] segundos.
  Future<int> _fallo(Map<String, Object?> f, DateTime ahora) async {
    final intentos = (f['intentos'] as int) + 1;
    final bloquear = intentos >= intentosMaximos;
    await _bd.update(
        'usuarios',
        bloquear
            ? {'intentos': 0, 'bloqueado_hasta': ahora.add(const Duration(seconds: segundosBloqueo)).toIso8601String()}
            : {'intentos': intentos},
        where: 'id = ?',
        whereArgs: [f['id']]);
    return bloquear ? segundosBloqueo : 0;
  }

  /// Entra con usuario y PIN. Un usuario inexistente se responde igual que un PIN incorrecto.
  Future<ResultadoAcceso> entrar(String usuario, String pin, {DateTime? ahora}) async {
    final momento = ahora ?? DateTime.now();
    final f = await _usuario(usuario);
    if (f == null) return const AccesoDenegado();
    final bloqueo = _segundosDeBloqueo(f, momento);
    if (bloqueo > 0) return AccesoDenegado(segundosDeBloqueo: bloqueo);
    if (!verificarPin(pin, f['pin_sal'] as String, f['pin_derivado'] as String)) {
      return AccesoDenegado(segundosDeBloqueo: await _fallo(f, momento));
    }
    await _bd.update('usuarios', {'intentos': 0, 'bloqueado_hasta': null}, where: 'id = ?', whereArgs: [f['id']]);
    return AccesoConcedido(Perfil.desdeFila(f));
  }

  /// Pone el PIN nuevo y un código de recuperación nuevo (el anterior deja de servir). Devuelve el código.
  Future<String> _nuevoPin(Map<String, Object?> f, String pin) async {
    final codigo = generarCodigoRecuperacion();
    final (pinSal, codigoSal) = (generarSal(), generarSal());
    await _bd.update(
        'usuarios',
        {
          'pin_sal': pinSal,
          'pin_derivado': derivarPin(pin, pinSal),
          'codigo_sal': codigoSal,
          'codigo_derivado': derivarPin(normalizarCodigo(codigo), codigoSal),
          'intentos': 0,
          'bloqueado_hasta': null,
        },
        where: 'id = ?',
        whereArgs: [f['id']]);
    return codigo;
  }

  /// Nivel 1: con el código de recuperación. Devuelve el código nuevo, o null si no coincide (cuenta como
  /// intento fallido, con el mismo bloqueo que el PIN).
  Future<String?> restablecerConCodigo(String usuario, String codigo, String pinNuevo, {DateTime? ahora}) async {
    if (!pinValido(pinNuevo)) throw ArgumentError('El PIN debe tener 4 dígitos.');
    final momento = ahora ?? DateTime.now();
    final f = await _usuario(usuario);
    if (f == null || _segundosDeBloqueo(f, momento) > 0) return null;
    if (!verificarPin(normalizarCodigo(codigo), f['codigo_sal'] as String, f['codigo_derivado'] as String)) {
      await _fallo(f, momento);
      return null;
    }
    return _nuevoPin(f, pinNuevo);
  }

  /// Nivel 2: el responsable de datos con la clave de la IPS configurada en este dispositivo.
  Future<String?> restablecerConClaveIps(String usuario, String claveIps, String pinNuevo) async {
    if (!pinValido(pinNuevo)) throw ArgumentError('El PIN debe tener 4 dígitos.');
    final guardada = await this.claveIps();
    final f = await _usuario(usuario);
    if (f == null || guardada == null || !iguales(guardada, claveIps)) return null;
    return _nuevoPin(f, pinNuevo);
  }

  /// Nivel 3: elimina la cuenta con sus evaluaciones y cargas; las demás cuentas no se tocan.
  Future<void> eliminarUsuario(String usuario) async {
    final f = await _usuario(usuario);
    if (f == null) return;
    await _bd.transaction((t) async {
      await t.delete('evaluaciones', where: 'id_usuario = ?', whereArgs: [f['id']]);
      await t.delete('cargas', where: 'id_usuario = ?', whereArgs: [f['id']]);
      await t.delete('usuarios', where: 'id = ?', whereArgs: [f['id']]);
    });
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
      'id_usuario': perfil.id,
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
        'id_usuario': perfil.id,
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

  /// Condición «solo las del usuario» (sin usuario, todas: lo usan las pruebas que no pasan por el acceso).
  (String?, List<Object?>) _deUsuario(int? idUsuario) =>
      idUsuario == null ? (null, const []) : ('id_usuario = ?', [idUsuario]);

  /// La carga anterior del mismo archivo hecha por este usuario (misma huella SHA-256), si la hay.
  Future<RegistroCarga?> cargaPrevia(String sha256, {int? idUsuario}) async {
    final (condicion, argumentos) = _deUsuario(idUsuario);
    final filas = await _bd.query('cargas',
        where: ['sha256 = ?', ?condicion].join(' AND '), whereArgs: [sha256, ...argumentos], orderBy: 'id DESC', limit: 1);
    return filas.isEmpty ? null : RegistroCarga.desdeFila(filas.single);
  }

  /// Evaluaciones de la más reciente a la más antigua, con filtros opcionales.
  Future<List<RegistroEvaluacion>> listar(
      {int? idUsuario, int? clase, DateTime? desde, String? seudonimo, int limite = 500}) async {
    final (deUsuario, argumentosUsuario) = _deUsuario(idUsuario);
    final condiciones = <String>[?deUsuario];
    final argumentos = <Object?>[...argumentosUsuario];
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

  Future<int> pendientesDeSincronizar({int? idUsuario}) async {
    final (deUsuario, argumentos) = _deUsuario(idUsuario);
    final filas = await _bd.rawQuery(
        'SELECT COUNT(*) AS n FROM evaluaciones WHERE sincronizado = 0${deUsuario == null ? '' : ' AND $deUsuario'}', argumentos);
    return filas.single['n'] as int;
  }

  /// Simulación: marca como sincronizadas las pendientes (no hay servidor; no se envía ningún dato).
  Future<int> marcarSincronizadas({int? idUsuario}) {
    final (deUsuario, argumentos) = _deUsuario(idUsuario);
    return _bd.update('evaluaciones', {'sincronizado': 1},
        where: ['sincronizado = 0', ?deUsuario].join(' AND '), whereArgs: argumentos);
  }
}
