/// Avatares de las cuentas, el rebote al tocar y el avatar de la sesión para el encabezado.
library;

import 'package:flutter/material.dart';

import '../tema/tema_materna.dart';

/// Los avatares que se pueden elegir (presentación inicial y registro). El índice se guarda en la cuenta.
const avatares = <({IconData icono, String nombre})>[
  (icono: Icons.person_outline_rounded, nombre: 'Persona'),
  (icono: Icons.sentiment_satisfied_alt_rounded, nombre: 'Sonrisa'),
  (icono: Icons.favorite_border_rounded, nombre: 'Corazón'),
  (icono: Icons.eco_outlined, nombre: 'Hoja'),
  (icono: Icons.diversity_1_outlined, nombre: 'Comunidad'),
  (icono: Icons.shield_outlined, nombre: 'Escudo'),
];

IconData iconoAvatar(int indice) => avatares[indice.clamp(0, avatares.length - 1)].icono;

/// Avatar en un círculo con degradado ciruela.
class AvatarCirculo extends StatelessWidget {
  const AvatarCirculo(this.indice, {super.key, this.tamano = 34});

  final int indice;
  final double tamano;

  @override
  Widget build(BuildContext context) => Container(
        width: tamano,
        height: tamano,
        decoration: const BoxDecoration(
          shape: BoxShape.circle,
          gradient: LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xFFA24477), Color(0xFF6A2650)]),
        ),
        alignment: Alignment.center,
        child: Icon(iconoAvatar(indice), color: Colors.white, size: tamano * .55,
            semanticLabel: 'Avatar ${avatares[indice.clamp(0, avatares.length - 1)].nombre}'),
      );
}

/// El avatar de la cuenta con sesión abierta, para que el encabezado de cada pantalla lo muestre.
class AvatarSesion extends InheritedWidget {
  const AvatarSesion({super.key, required this.indice, required super.child});

  final int indice;

  static int? de(BuildContext context) => context.dependOnInheritedWidgetOfExactType<AvatarSesion>()?.indice;

  @override
  bool updateShouldNotify(AvatarSesion vieja) => vieja.indice != indice;
}

/// Al tocarlo, el hijo se encoge un poco y vuelve con un rebote elástico (Curves.elasticOut).
class Rebote extends StatefulWidget {
  const Rebote({super.key, required this.child, this.alTocar, this.etiqueta, this.seleccionado});

  final Widget child;
  final VoidCallback? alTocar;

  /// Para lectores de pantalla.
  final String? etiqueta;
  final bool? seleccionado;

  @override
  State<Rebote> createState() => _EstadoRebote();
}

class _EstadoRebote extends State<Rebote> with SingleTickerProviderStateMixin {
  late final _control = AnimationController(vsync: this, duration: const Duration(milliseconds: 750), value: 1);
  late final _escala = TweenSequence<double>([
    TweenSequenceItem(tween: Tween<double>(begin: 1, end: .92).chain(CurveTween(curve: Curves.easeOut)), weight: 12),
    TweenSequenceItem(tween: Tween<double>(begin: .92, end: 1).chain(CurveTween(curve: Curves.elasticOut)), weight: 88),
  ]).animate(_control);

  @override
  void dispose() {
    _control.dispose();
    super.dispose();
  }

  void _tocar() {
    if (!MediaQuery.of(context).disableAnimations) _control.forward(from: 0);
    widget.alTocar?.call();
  }

  @override
  Widget build(BuildContext context) => Semantics(
        button: true,
        label: widget.etiqueta,
        selected: widget.seleccionado,
        child: GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTap: widget.alTocar == null ? null : _tocar,
          child: ScaleTransition(scale: _escala, child: widget.child),
        ),
      );
}

/// Casilla redonda o cuadrada que se llena de ciruela y muestra el visto con un pequeño rebote.
class Casilla extends StatelessWidget {
  const Casilla({super.key, required this.marcada, this.cuadrada = false});

  final bool marcada;
  final bool cuadrada;

  @override
  Widget build(BuildContext context) {
    final lado = cuadrada ? 30.0 : 26.0;
    return AnimatedContainer(
      duration: const Duration(milliseconds: 250),
      width: lado,
      height: lado,
      decoration: BoxDecoration(
        color: marcada ? ColoresMaterna.ciruela900 : Colors.transparent,
        borderRadius: BorderRadius.circular(cuadrada ? 9 : lado),
        border: Border.all(color: marcada ? ColoresMaterna.ciruela900 : const Color(0xFFE0C5D3), width: 2),
      ),
      child: AnimatedScale(
        scale: marcada ? 1 : 0,
        duration: const Duration(milliseconds: 550),
        curve: const Cubic(.3, 1.9, .4, 1),
        child: const Icon(Icons.check_rounded, color: Colors.white, size: 17),
      ),
    );
  }
}
