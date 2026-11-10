/// Fábrica de la base local según la plataforma: SQLite nativo (sqflite) en Android/iOS y SQLite compilado
/// a WebAssembly en la web (sqflite_common_ffi_web; sus archivos sqlite3.wasm y sqflite_sw.js están en web/).
library;

export 'fabrica_bd_movil.dart' if (dart.library.js_interop) 'fabrica_bd_web.dart';
