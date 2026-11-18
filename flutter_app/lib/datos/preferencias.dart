/// Preferencias del dispositivo, guardadas con shared_preferences: lo que se elige en la presentación inicial
/// (onboarding) y los ajustes que cambian cómo se ve y se siente la app.
///
/// El rol y el avatar elegidos en la presentación son SUGERENCIAS para la siguiente cuenta que se cree en el
/// dispositivo (cada cuenta guarda los suyos en la base local); los ajustes valen para todo el dispositivo.
library;

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Dónde se guardan los valores: shared_preferences en la app; un mapa en memoria en las pruebas.
abstract interface class Almacen {
  Object? leer(String clave);
  Future<void> escribir(String clave, Object valor);
}

class _AlmacenSistema implements Almacen {
  _AlmacenSistema(this._prefs);

  final SharedPreferences _prefs;

  @override
  Object? leer(String clave) => _prefs.get(clave);

  @override
  Future<void> escribir(String clave, Object valor) => switch (valor) {
        bool v => _prefs.setBool(clave, v),
        int v => _prefs.setInt(clave, v),
        String v => _prefs.setString(clave, v),
        _ => throw ArgumentError('Tipo no soportado: ${valor.runtimeType}'),
      };
}

class AlmacenEnMemoria implements Almacen {
  AlmacenEnMemoria([Map<String, Object>? inicial]) : valores = {...?inicial};

  final Map<String, Object> valores;

  @override
  Object? leer(String clave) => valores[clave];

  @override
  Future<void> escribir(String clave, Object valor) async => valores[clave] = valor;
}

/// Claves con que se guarda cada valor.
abstract final class ClavesPreferencias {
  static const presentacionVista = 'presentacion_vista';
  static const rol = 'rol_sugerido';
  static const avatar = 'avatar_sugerido';
  static const letraGrande = 'letra_grande';
  static const reducirAnimaciones = 'reducir_animaciones';
  static const vibrarAlto = 'vibrar_alto_riesgo';
  static const modoOscuro = 'modo_oscuro';
}

class Preferencias extends ChangeNotifier {
  Preferencias(this._almacen);

  /// Las de este dispositivo (shared_preferences).
  static Future<Preferencias> cargar() async => Preferencias(_AlmacenSistema(await SharedPreferences.getInstance()));

  /// En memoria, para las pruebas. Por omisión la presentación ya se vio (las pruebas que no la tratan van al acceso).
  factory Preferencias.enMemoria({bool presentacionVista = true, Map<String, Object>? valores}) => Preferencias(
      AlmacenEnMemoria({ClavesPreferencias.presentacionVista: presentacionVista, ...?valores}));

  final Almacen _almacen;

  T _valor<T>(String clave, T porOmision) {
    final v = _almacen.leer(clave);
    return v is T ? v : porOmision;
  }

  Future<void> _fijar(String clave, Object valor) async {
    await _almacen.escribir(clave, valor);
    notifyListeners();
  }

  /// Si la presentación inicial ya se mostró en este dispositivo (solo aparece la primera vez).
  bool get presentacionVista => _valor(ClavesPreferencias.presentacionVista, false);

  /// Quién atiende, elegido en la presentación (una de las 4 categorías del modelo), o null.
  String? get rol => _almacen.leer(ClavesPreferencias.rol) as String?;

  /// Avatar elegido en la presentación (índice en `avatares`).
  int get avatar => _valor(ClavesPreferencias.avatar, 0);

  /// Texto un 15 % más grande en toda la app (útil al sol o con la vista cansada).
  bool get letraGrande => _valor(ClavesPreferencias.letraGrande, false);

  /// Quita las animaciones de la app (además de lo que pida el sistema).
  bool get reducirAnimaciones => _valor(ClavesPreferencias.reducirAnimaciones, false);

  /// Vibra el teléfono cuando una evaluación sale Alto Riesgo.
  bool get vibrarAlto => _valor(ClavesPreferencias.vibrarAlto, true);

  /// Colores oscuros en toda la app (la animación del logo y la presentación inicial siguen en claro).
  bool get modoOscuro => _valor(ClavesPreferencias.modoOscuro, false);

  Future<void> fijarLetraGrande(bool v) => _fijar(ClavesPreferencias.letraGrande, v);
  Future<void> fijarReducirAnimaciones(bool v) => _fijar(ClavesPreferencias.reducirAnimaciones, v);
  Future<void> fijarVibrarAlto(bool v) => _fijar(ClavesPreferencias.vibrarAlto, v);
  Future<void> fijarModoOscuro(bool v) => _fijar(ClavesPreferencias.modoOscuro, v);

  /// Guarda todo lo elegido en la presentación y la marca como vista.
  Future<void> terminarPresentacion({String? rol, required int avatar, required bool letraGrande,
      required bool reducirAnimaciones, required bool vibrarAlto}) async {
    if (rol != null) await _almacen.escribir(ClavesPreferencias.rol, rol);
    await _almacen.escribir(ClavesPreferencias.avatar, avatar);
    await _almacen.escribir(ClavesPreferencias.letraGrande, letraGrande);
    await _almacen.escribir(ClavesPreferencias.reducirAnimaciones, reducirAnimaciones);
    await _almacen.escribir(ClavesPreferencias.vibrarAlto, vibrarAlto);
    await _fijar(ClavesPreferencias.presentacionVista, true);
  }

  /// Vuelve a mostrar la presentación la próxima vez (desde «Acerca de»).
  Future<void> verPresentacionDeNuevo() => _fijar(ClavesPreferencias.presentacionVista, false);
}
