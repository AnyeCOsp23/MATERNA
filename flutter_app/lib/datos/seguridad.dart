/// PIN del operador: nunca se guarda; solo su derivación PBKDF2-HMAC-SHA256 con una sal aleatoria por dispositivo.
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

/// Comparación en tiempo constante.
bool verificarPin(String pin, String sal, String derivado) {
  final a = derivarPin(pin, sal);
  if (a.length != derivado.length) return false;
  var diferencia = 0;
  for (var i = 0; i < a.length; i++) {
    diferencia |= a.codeUnitAt(i) ^ derivado.codeUnitAt(i);
  }
  return diferencia == 0;
}
