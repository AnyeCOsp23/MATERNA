/// PIN de cada usuario: nunca se guarda; solo su derivación PBKDF2-HMAC-SHA256 con una sal aleatoria por cuenta.
/// El código de recuperación de cada cuenta se guarda igual.
///
/// Un PIN de 4 dígitos tiene solo 10.000 combinaciones: protege el acceso casual al dispositivo (junto con el
/// bloqueo tras 5 intentos fallidos), no un ataque a los archivos de la app. Es una limitación declarada del
/// prototipo; los datos locales no van cifrados.
library;

import 'dart:convert';
import 'dart:math';
import 'dart:typed_data';

import 'package:crypto/crypto.dart';

const iteracionesPin = 20000;
const intentosMaximos = 5;
const segundosBloqueo = 30;

String generarSal() {
  final azar = Random.secure();
  return base64Encode(List<int>.generate(16, (_) => azar.nextInt(256)));
}

/// PBKDF2-HMAC-SHA256 (RFC 8018) con un solo bloque de 32 bytes.
String derivarPin(String pin, String sal, {int iteraciones = iteracionesPin}) {
  final hmac = Hmac(sha256, utf8.encode(pin));
  var u = hmac.convert([...base64Decode(sal), 0, 0, 0, 1]).bytes;
  final resultado = Uint8List.fromList(u);
  for (var i = 1; i < iteraciones; i++) {
    u = hmac.convert(u).bytes;
    for (var j = 0; j < resultado.length; j++) {
      resultado[j] ^= u[j];
    }
  }
  return base64Encode(resultado);
}

bool pinValido(String pin) => RegExp(r'^\d{4}$').hasMatch(pin);

/// Comparación en tiempo constante (no revela cuántos caracteres coinciden).
bool iguales(String a, String b) {
  if (a.length != b.length) return false;
  var diferencia = 0;
  for (var i = 0; i < a.length; i++) {
    diferencia |= a.codeUnitAt(i) ^ b.codeUnitAt(i);
  }
  return diferencia == 0;
}

bool verificarPin(String pin, String sal, String derivado) => iguales(derivarPin(pin, sal), derivado);

/// Sin letras ni números que se confundan al anotarlos (0/O, 1/I/L).
const _alfabetoCodigo = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789';

/// Código de recuperación de la cuenta, p. ej. 'K7M2-Q9XP' (8 caracteres, unos 39 bits de azar). Se muestra una
/// sola vez y se guarda derivado, igual que el PIN.
String generarCodigoRecuperacion() {
  final azar = Random.secure();
  final c = List.generate(8, (_) => _alfabetoCodigo[azar.nextInt(_alfabetoCodigo.length)]).join();
  return '${c.substring(0, 4)}-${c.substring(4)}';
}

/// ' k7m2 q9xp' -> 'K7M2Q9XP': se acepta escrito con o sin guion, en mayúsculas o minúsculas.
String normalizarCodigo(String codigo) => codigo.toUpperCase().replaceAll(RegExp(r'[^A-Z0-9]'), '');
