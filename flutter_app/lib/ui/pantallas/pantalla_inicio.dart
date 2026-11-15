/// Pantalla de inicio (splash) al abrir la app: el logo de MATERNA sobre fondo blanco.
///
/// Animación al estilo de iPhone, en una sola línea de tiempo de 1,9 s:
///   - el logo sube 40 px desde abajo, aparece y crece de 0,82 a 1 con un rebote suave (Curves.easeOutBack, 1,1 s);
///   - la palabra MATERNA aparece desde los 0,9 s con un leve desplazamiento hacia arriba;
///   - una pausa corta y la app continúa (acceso con PIN).
/// Con «reducir movimiento» activado en el dispositivo se muestra el logo quieto el mismo tiempo.
library;

import 'package:flutter/material.dart';

/// Color del isotipo (assets/logo_isotipo.webp), para que la palabra quede del mismo tono.
const colorLogo = Color(0xFF942255);

const duracionInicio = Duration(milliseconds: 1900);
const _ms = 1900.0;

class PantallaInicio extends StatefulWidget {
  const PantallaInicio({super.key, this.alTerminar});

  /// Se llama al terminar la animación.
  final VoidCallback? alTerminar;

  @override
  State<PantallaInicio> createState() => _EstadoInicio();
}

class _EstadoInicio extends State<PantallaInicio> with SingleTickerProviderStateMixin {
  late final _control = AnimationController(vsync: this, duration: duracionInicio)
    ..addStatusListener((estado) {
      if (estado == AnimationStatus.completed) widget.alTerminar?.call();
    });

  @override
  void initState() {
    super.initState();
    // empieza cuando ya se dibujó el primer cuadro: en un arranque en frío lento no se pierde parte de la animación
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _control.forward();
    });
  }

  // logo: 0 a 1,1 s; la opacidad no usa easeOutBack para no pasar de 1
  late final _logoMovimiento = CurvedAnimation(parent: _control, curve: const Interval(0, 1100 / _ms, curve: Curves.easeOutBack));
  late final _logoOpacidad = CurvedAnimation(parent: _control, curve: const Interval(0, 600 / _ms, curve: Curves.easeOut));
  // texto: desde 0,9 s, durante 0,6 s
  late final _texto = CurvedAnimation(parent: _control, curve: const Interval(900 / _ms, 1500 / _ms, curve: Curves.easeOutCubic));

  @override
  void dispose() {
    _control.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final quieto = MediaQuery.of(context).disableAnimations;
    return Scaffold(
      key: const Key('pantalla-inicio'),
      backgroundColor: Colors.white,
      body: Center(
        child: AnimatedBuilder(
          animation: _control,
          builder: (context, _) {
            final m = quieto ? 1.0 : _logoMovimiento.value;
            final t = quieto ? 1.0 : _texto.value;
            return Column(mainAxisSize: MainAxisSize.min, children: [
              Opacity(
                key: const Key('inicio-logo'),
                opacity: quieto ? 1 : _logoOpacidad.value.clamp(0.0, 1.0),
                child: Transform.translate(
                  offset: Offset(0, 40 * (1 - m)),
                  child: Transform.scale(
                    scale: 0.82 + 0.18 * m,
                    child: Image.asset('assets/logo_isotipo.webp', width: 168, height: 168, semanticLabel: 'Logo de MATERNA'),
                  ),
                ),
              ),
              const SizedBox(height: 6),
              Opacity(
                key: const Key('inicio-texto'),
                opacity: t.clamp(0.0, 1.0),
                child: Transform.translate(
                  offset: Offset(0, 12 * (1 - t)),
                  child: const Text(
                    'MATERNA',
                    style: TextStyle(color: colorLogo, fontSize: 26, fontWeight: FontWeight.w400, letterSpacing: 4.5),
                  ),
                ),
              ),
            ]);
          },
        ),
      ),
    );
  }
}
