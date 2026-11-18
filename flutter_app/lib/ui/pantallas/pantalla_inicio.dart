/// Pantalla de inicio (splash) al abrir la app: el logo de MATERNA florece, se dibuja y escribe su nombre.
///
/// Reproduce la animación del video «MATERNA_logo_reveal» (sin música), en una sola línea de tiempo de 5 s:
///   - 0 a 0,5 s: aparece el fondo crema con ondas y puntos muy suaves, y un brillo rosado detrás del logo;
///   - 0,3 a 2,7 s: el loto florece pétalo por pétalo (central, interior izquierdo, interior derecho, exterior
///     izquierdo, exterior derecho), cada uno 0,25 s después del anterior y durante 1,4 s, así que siempre hay
///     varios abriéndose a la vez: sale de detrás del central y se abre girando desde la base, desacelerando
///     hasta detenerse, sin rebote. Mientras se abre proyecta una sombra suave sobre los de atrás, que se
///     desvanece al llegar (la silueta de la madre queda vacía);
///   - 2,2 a 3,2 s: la madre y el bebé aparecen de abajo hacia arriba;
///   - 3,0 a 4,3 s: la palabra MATERNA aparece letra por letra, cada una con un pequeño rebote;
///   - hasta 5 s: el logo queda quieto y la app continúa (acceso con PIN).
/// Las capas (los 5 pétalos, los trazos y la palabra) salen del propio video, así que el logo y la letra son los mismos.
/// Con «reducir movimiento» activado en el dispositivo se muestra el logo completo y quieto.
library;

import 'dart:math' as math;

import 'package:flutter/material.dart';

/// Color del logo (el mismo de las capas), para lo que se dibuja aparte.
const colorLogo = Color(0xFF942255);

const duracionInicio = Duration(milliseconds: 5000);
const _ms = 5000.0;

/// Tamaño de las capas en el archivo (cada pétalo y logo_trazos: 720 × 489; logo_palabra: 519 × 85).
const _anchoLogo = 230.0;
const _altoLogo = _anchoLogo * 489 / 720;
const _anchoPalabra = _anchoLogo * 519 / 720;
const _altoPalabra = _anchoPalabra * 85 / 519;
const _separacion = 48.6 * _anchoLogo / 720;

/// Los 5 pétalos, del fondo al frente: (archivo, giro inicial en grados hacia el centro, inicio y fin en ms).
/// Se abren uno por uno (central, interior izq., interior der., exterior izq., exterior der.), cada uno 0,25 s
/// después del anterior y durante 1,4 s; todos giran sobre la base del loto, plegados detrás del central.
const _petalos = [
  ('exterior_izq', 38.0, 1050.0, 2450.0),
  ('exterior_der', -38.0, 1300.0, 2700.0),
  ('interior_izq', 22.0, 550.0, 1950.0),
  ('interior_der', -22.0, 800.0, 2200.0),
  ('central', 0.0, 300.0, 1500.0),
];

/// Punto de giro: la base del loto (centro abajo de la capa).
const _base = Alignment(0, .94);

/// Curva de apertura de cada pétalo: arranca con soltura y desacelera largo hasta detenerse, sin pasarse,
/// como una flor que se abre (con rebote se veía brusco; con entrada lenta, el pétalo parecía aparecer de golpe).
const _abrir = Cubic(.22, .61, .36, 1);

/// Dónde termina cada letra de la palabra (fracción del ancho), medido en la capa.
const _cortesLetras = [0.0, 0.1696, 0.315, 0.4364, 0.5607, 0.6975, 0.8401, 1.0];

Interval _tramo(double desde, double hasta, [Curve curva = Curves.linear]) => Interval(desde / _ms, hasta / _ms, curve: curva);

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

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // las capas se decodifican antes de que aparezcan: así el loto no «parpadea» al empezar a florecer
    for (final capa in [
      for (final p in _petalos) ...['assets/logo_petalo_${p.$1}.webp', 'assets/logo_sombra_${p.$1}.webp'],
      'assets/logo_trazos.webp',
      'assets/logo_palabra.webp',
    ]) {
      precacheImage(AssetImage(capa), context);
    }
  }

  @override
  void dispose() {
    _control.dispose();
    super.dispose();
  }

  /// Valor de un tramo de la línea de tiempo (0 antes, 1 después).
  double _en(double desde, double hasta, [Curve curva = Curves.linear]) => _tramo(desde, hasta, curva).transform(_control.value);

  /// Escala del loto entero: crece despacio de 0,94 a 1 mientras florece (0,3 a 2,7 s), sin pasarse.
  double _escalaLoto() => .94 + .06 * _en(300, 2700, Curves.easeOutCubic);

  /// Un pétalo con su sombra: aparece, crece y gira desde su posición plegada hasta la final, sobre la base del loto.
  Widget _petalo((String, double, double, double) p, bool quieto) {
    final (nombre, giro, desde, hasta) = p;
    final avance = quieto ? 1.0 : _en(desde, hasta, _abrir);
    // aparece en el primer 40 % de su apertura: como sale de detrás del central, no se nota que «llega»
    final aparece = quieto ? 1.0 : _en(desde, desde + (hasta - desde) * .4, Curves.easeOut);
    // el central crece hacia arriba; los laterales, además, se abren girando (crecen poco: así no «saltan»)
    final escala = .85 + .15 * avance;
    // sombra: más marcada a mitad de la apertura (cuando el pétalo «se levanta») y nula al llegar
    final sombra = quieto ? 0.0 : aparece * math.sin(math.pi * avance) * .85;
    Widget capa(String archivo, {double y = 0}) => Transform.translate(
          offset: Offset(0, y),
          child: Transform.rotate(
            angle: giro * (1 - avance) * math.pi / 180,
            alignment: _base,
            child: Transform.scale(scale: escala, alignment: _base, child: Image.asset(archivo, fit: BoxFit.fill)),
          ),
        );
    return Stack(fit: StackFit.expand, children: [
      if (sombra > .01)
        Opacity(key: Key('sombra-$nombre'), opacity: sombra, child: capa('assets/logo_sombra_$nombre.webp', y: 4 * sombra)),
      Opacity(key: Key('petalo-$nombre'), opacity: aparece, child: capa('assets/logo_petalo_$nombre.webp')),
    ]);
  }

  @override
  Widget build(BuildContext context) {
    final quieto = MediaQuery.of(context).disableAnimations;
    return Scaffold(
      key: const Key('pantalla-inicio'),
      backgroundColor: Colors.white,
      body: AnimatedBuilder(
        animation: _control,
        builder: (context, _) {
          final fondo = quieto ? 1.0 : _en(0, 500, Curves.easeOut);
          final brillo = quieto ? 1.0 : _en(900, 2700, Curves.easeOut);
          final loto = quieto ? 1.0 : _en(300, 500, Curves.easeOut);
          final trazos = quieto ? 1.0 : _en(2200, 3200, Curves.easeInOut);
          return Stack(fit: StackFit.expand, children: [
            Opacity(opacity: fondo, child: CustomPaint(painter: _Fondo(fondo))),
            Center(
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                Stack(clipBehavior: Clip.none, alignment: Alignment.center, children: [
                  // brillo rosado detrás del logo
                  Opacity(
                    opacity: brillo * .9,
                    child: Container(
                      width: _anchoLogo * 1.5,
                      height: _anchoLogo * 1.5,
                      decoration: const BoxDecoration(
                        shape: BoxShape.circle,
                        gradient: RadialGradient(colors: [Color(0x66F5D3E3), Color(0x00F5D3E3)]),
                      ),
                    ),
                  ),
                  Opacity(
                    key: const Key('inicio-logo'),
                    opacity: loto,
                    child: Transform.scale(
                      scale: quieto ? 1 : _escalaLoto(),
                      alignment: const Alignment(0, .85),
                      child: Semantics(
                        label: 'Logo de MATERNA',
                        image: true,
                        child: SizedBox(
                          width: _anchoLogo,
                          height: _altoLogo,
                          child: Stack(fit: StackFit.expand, children: [
                            for (final p in _petalos) _petalo(p, quieto),
                            _Dibujar(avance: trazos, child: Image.asset('assets/logo_trazos.webp', fit: BoxFit.fill)),
                          ]),
                        ),
                      ),
                    ),
                  ),
                ]),
                const SizedBox(height: _separacion),
                Semantics(
                  key: const Key('inicio-texto'),
                  label: 'MATERNA',
                  child: SizedBox(
                    width: _anchoPalabra,
                    height: _altoPalabra,
                    child: Stack(fit: StackFit.expand, children: [
                      for (var i = 0; i < _cortesLetras.length - 1; i++)
                        _Letra(indice: i, avance: quieto ? 1 : _en(3000 + i * 170.0, 3000 + i * 170.0 + 280)),
                    ]),
                  ),
                ),
              ]),
            ),
          ]);
        },
      ),
    );
  }
}

/// La madre y el bebé aparecen de abajo hacia arriba, con el borde difuso.
class _Dibujar extends StatelessWidget {
  const _Dibujar({required this.avance, required this.child});

  final double avance;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    if (avance <= 0) return const SizedBox.shrink();
    if (avance >= 1) return child;
    // los trazos ocupan más o menos del 25 % al 70 % del alto de la capa
    final hasta = 1 - (.25 + .5 * avance);
    return ShaderMask(
      key: const Key('inicio-dibujar'),
      blendMode: BlendMode.dstIn,
      shaderCallback: (rect) => LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: const [Colors.transparent, Colors.white],
        stops: [math.max(0, hasta - .06), hasta],
      ).createShader(rect),
      child: child,
    );
  }
}

/// Una letra de MATERNA: un recorte de la capa de la palabra que aparece con un rebote y un brillo suave.
class _Letra extends StatelessWidget {
  const _Letra({required this.indice, required this.avance});

  final int indice;
  final double avance;

  @override
  Widget build(BuildContext context) {
    final rebote = Curves.easeOutBack.transform(avance);
    final brillo = math.sin(avance * math.pi); // 0 → 1 → 0 mientras aparece
    return Opacity(
      opacity: Curves.easeOut.transform(avance),
      child: Transform.scale(
        scale: .6 + .4 * rebote,
        alignment: Alignment((_cortesLetras[indice] + _cortesLetras[indice + 1]) - 1, .4),
        child: DecoratedBox(
          decoration: BoxDecoration(boxShadow: [
            if (brillo > 0) BoxShadow(color: const Color(0xFFF5D3E3).withValues(alpha: .8 * brillo), blurRadius: 14, spreadRadius: -4),
          ]),
          child: ClipRect(
            clipper: _Franja(_cortesLetras[indice], _cortesLetras[indice + 1]),
            child: Image.asset('assets/logo_palabra.webp', fit: BoxFit.fill),
          ),
        ),
      ),
    );
  }
}

class _Franja extends CustomClipper<Rect> {
  const _Franja(this.desde, this.hasta);

  final double desde, hasta;

  @override
  Rect getClip(Size size) => Rect.fromLTRB(size.width * desde, 0, size.width * hasta, size.height);

  @override
  bool shouldReclip(_Franja vieja) => vieja.desde != desde || vieja.hasta != hasta;
}

/// Fondo del video: crema con un leve tono rosado, ondas finas y puntos, todo casi transparente.
class _Fondo extends CustomPainter {
  const _Fondo(this.visible);

  final double visible;

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Offset.zero & size;
    canvas.drawRect(rect, Paint()..shader = const LinearGradient(
      begin: Alignment.topCenter,
      end: Alignment.bottomCenter,
      colors: [Color(0xFFF8F3F3), Color(0xFFF7EEEE), Color(0xFFF8F3F2)],
    ).createShader(rect));
    // círculos grandes y tenues, como pétalos fuera de foco
    final tenue = Paint()..color = colorLogo.withValues(alpha: .035);
    canvas.drawCircle(Offset(size.width * .1, size.height * .12), size.width * .45, tenue);
    canvas.drawCircle(Offset(size.width * .95, size.height * .9), size.width * .5, tenue);
    // ondas finas arriba y abajo
    final onda = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.2
      ..color = colorLogo.withValues(alpha: .10);
    for (final (y, amplitud, fase) in [(.16, 14.0, 0.0), (.19, 10.0, 1.6), (.82, 16.0, .8), (.86, 11.0, 2.4)]) {
      final camino = Path()..moveTo(0, size.height * y);
      for (var x = 0.0; x <= size.width; x += 6) {
        camino.lineTo(x, size.height * y + amplitud * math.sin(x / size.width * 2 * math.pi * 1.3 + fase));
      }
      canvas.drawPath(camino, onda);
    }
    // puntos que se encienden con el fondo
    final punto = Paint()..color = colorLogo.withValues(alpha: .12 * visible);
    final azar = math.Random(7); // siempre los mismos
    for (var i = 0; i < 22; i++) {
      final y = azar.nextBool() ? azar.nextDouble() * .3 : .7 + azar.nextDouble() * .3;
      canvas.drawCircle(Offset(azar.nextDouble() * size.width, y * size.height), 1.2 + azar.nextDouble() * 1.8, punto);
    }
  }

  @override
  bool shouldRepaint(_Fondo viejo) => viejo.visible != visible;
}
