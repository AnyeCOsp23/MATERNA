/// Seudonimización del documento de la gestante: HMAC-SHA256 con la clave (sal) de la IPS.
///
/// Traducción de `src/seudonimizacion.py`: con la misma clave, el mismo documento da el mismo seudónimo en el
/// Módulo 1 y en la app (lo verifica `test/carga_test.dart`). No se usa SHA-256 simple porque las cédulas son
/// predecibles: sin la clave, un hash se revierte probando todos los números.
///
/// La clave se configura una vez por dispositivo y debe ser la misma en todos los dispositivos de la IPS para que
/// los seudónimos coincidan. El documento nunca se guarda: solo su seudónimo.
library;

import 'dart:convert';

import 'package:crypto/crypto.dart';

const longitudMinimaSal = 16;

/// ('cc', '1.065.432-1 ') -> ('CC', '10654321'): el mismo documento escrito de distintas formas.
(String, String) normalizarDocumento(String tipo, String numero) =>
    (tipo.trim().toUpperCase(), numero.replaceAll(RegExp(r'[\s.\-]'), '').toUpperCase());

/// Seudónimo hexadecimal de 64 caracteres para un documento.
String seudonimizar(String tipo, String numero, String sal) {
  if (sal.isEmpty) throw ArgumentError('La sal no puede estar vacía.');
  final (t, n) = normalizarDocumento(tipo, numero);
  if (n.isEmpty) throw ArgumentError('El número de documento está vacío.');
  return Hmac(sha256, utf8.encode(sal)).convert(utf8.encode('$t|$n')).toString();
}

bool salValida(String sal) => sal.length >= longitudMinimaSal;

/// Huella corta de la clave para comprobar que dos dispositivos usan la misma sin mostrarla (p. ej. «3F9A-C21B»).
String huellaSal(String sal) {
  final h = sha256.convert(utf8.encode('materna-huella|$sal')).toString().toUpperCase();
  return '${h.substring(0, 4)}-${h.substring(4, 8)}';
}
