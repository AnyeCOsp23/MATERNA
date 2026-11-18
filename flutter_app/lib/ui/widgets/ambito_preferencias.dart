/// Las preferencias del dispositivo al alcance de todas las pantallas, y los ajustes que valen para toda la app.
library;

import 'package:flutter/material.dart';

import '../../datos/preferencias.dart';

/// Hace disponibles las preferencias y redibuja a quien las use cuando cambian. Está siempre en el árbol, también
/// mientras se leen (con `preferencias` null): si apareciera recién al leerlas, Flutter reharía todo lo de abajo y
/// la animación del logo volvería a empezar.
class AmbitoPreferencias extends InheritedNotifier<Preferencias> {
  const AmbitoPreferencias({super.key, required Preferencias? preferencias, required super.child}) : super(notifier: preferencias);

  /// Las preferencias, o null si todavía no se cargaron (o en pruebas que no las usan).
  static Preferencias? de(BuildContext context) => context.dependOnInheritedWidgetOfExactType<AmbitoPreferencias>()?.notifier;
}

/// Aplica a toda la app la letra más grande y la reducción de animaciones elegidas.
class AjustesGlobales extends StatelessWidget {
  const AjustesGlobales({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    final preferencias = AmbitoPreferencias.de(context);
    if (preferencias == null) return child;
    final medios = MediaQuery.of(context);
    return MediaQuery(
      data: medios.copyWith(
        textScaler: preferencias.letraGrande ? TextScaler.linear(medios.textScaler.scale(1) * 1.15) : medios.textScaler,
        disableAnimations: medios.disableAnimations || preferencias.reducirAnimaciones,
      ),
      child: child,
    );
  }
}
