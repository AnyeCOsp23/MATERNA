/// Presentación inicial (onboarding) de 4 pantallas: solo la primera vez que se abre la app en el dispositivo,
/// después de la animación del logo y antes del acceso. Sigue el diseño «MATERNA · Onboarding animado».
///
///   1. El logo flota y late; el título y el texto suben; corazoncitos rosados suben despacio.
///   2. Quién atiende: las 4 categorías del modelo (lo elegido llena «Quién atiende» al crear la cuenta), con
///      una ilustración animada (nube, casas, árbol que se mece, ubicación que salta y señal que se apaga: sin internet).
///   3. Avatar: un círculo grande con halo que late y tres puntos en órbita; el elegido se propone al crear la cuenta.
///   4. Ajustes reales de la app (letra grande, reducir animaciones, vibrar con Alto Riesgo), con un escudo animado.
///
/// Fondo pastel de 4 tonos que cambia de forma continua al deslizar; tarjetas de cristal; rebote elástico al
/// tocar tarjetas, avatares y casillas; puntos de página animados y «Omitir». Todo se guarda con shared_preferences.
/// Con «reducir movimiento» no hay animaciones que se repitan.
library;

import 'dart:math' as math;
import 'dart:ui' as ui;

import 'package:flutter/material.dart';

import '../../datos/preferencias.dart';
import '../tema/tema_materna.dart';
import '../widgets/avatar.dart';
import 'pantalla_triaje.dart' show atiende;

/// Un tono pastel por pantalla; el fondo pasa de uno a otro mientras se desliza.
const _tonos = [Color(0xFFF8DDE8), Color(0xFFF4DDF0), Color(0xFFECDEF7), Color(0xFFFBE3E8)];

/// Las 4 categorías del modelo, con su ícono y una línea que la describe.
const _roles = <(String, IconData, String)>[
  ('Medico', Icons.medical_services_outlined, 'Valoro y remito en la IPS'),
  ('Enfermero(a)', Icons.health_and_safety_outlined, 'Hago el control prenatal'),
  ('Auxiliar de enfermeria', Icons.home_work_outlined, 'Visito comunidades dispersas'),
  ('Partera tradicional', Icons.pregnant_woman_rounded, 'Acompaño a las gestantes de mi comunidad'),
];

const _textosBoton = ['Comenzar', 'Continuar', 'Continuar', 'Empezar a usar MATERNA'];

class PantallaPresentacion extends StatefulWidget {
  const PantallaPresentacion({super.key, required this.preferencias, required this.alTerminar});

  final Preferencias preferencias;
  final VoidCallback alTerminar;

  @override
  State<PantallaPresentacion> createState() => _EstadoPresentacion();
}

class _EstadoPresentacion extends State<PantallaPresentacion> with TickerProviderStateMixin {
  final _paginas = PageController();
  // un solo reloj para las animaciones que se repiten (latido, corazones, órbitas, ilustraciones)
  late final _ciclo = AnimationController(vsync: this, duration: const Duration(seconds: 36));
  var _pagina = 0;
  var _posicion = 0.0;
  String? _rol;
  var _omitioRol = false;
  late var _avatar = widget.preferencias.avatar;
  late var _letraGrande = widget.preferencias.letraGrande;
  late var _reducir = widget.preferencias.reducirAnimaciones;
  late var _vibrar = widget.preferencias.vibrarAlto;
  var _guardando = false;

  @override
  void initState() {
    super.initState();
    _rol = widget.preferencias.rol;
    _paginas.addListener(() => setState(() => _posicion = _paginas.page ?? 0));
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final quieto = MediaQuery.of(context).disableAnimations;
    if (quieto && _ciclo.isAnimating) _ciclo.stop();
    if (!quieto && !_ciclo.isAnimating) _ciclo.repeat();
  }

  @override
  void dispose() {
    _paginas.dispose();
    _ciclo.dispose();
    super.dispose();
  }

  bool get _puedeSeguir => _pagina != 1 || _rol != null;

  /// Sin rol elegido no se puede pasar de la pantalla 2 deslizando (salvo con «Omitir»).
  int get _cuantas => _rol != null || _omitioRol ? 4 : 2;

  void _ir(int pagina) {
    final quieto = MediaQuery.of(context).disableAnimations;
    quieto
        ? _paginas.jumpToPage(pagina)
        : _paginas.animateToPage(pagina, duration: const Duration(milliseconds: 520), curve: Curves.easeOutCubic);
  }

  Future<void> _siguiente() async {
    if (!_puedeSeguir) return;
    if (_pagina < 3) return _ir(_pagina + 1);
    if (_guardando) return;
    setState(() => _guardando = true);
    await widget.preferencias.terminarPresentacion(
        rol: _rol, avatar: _avatar, letraGrande: _letraGrande, reducirAnimaciones: _reducir, vibrarAlto: _vibrar);
    widget.alTerminar();
  }

  void _omitir() {
    setState(() => _omitioRol = true);
    WidgetsBinding.instance.addPostFrameCallback((_) => _ir(3));
  }

  @override
  Widget build(BuildContext context) {
    final i = _posicion.floor().clamp(0, 3), j = (i + 1).clamp(0, 3);
    final tono = Color.lerp(_tonos[i], _tonos[j], (_posicion - i).clamp(0.0, 1.0))!;
    final abajo = Color.lerp(tono, Colors.white, .55)!;
    return Scaffold(
      key: const Key('presentacion'),
      body: Container(
        decoration: BoxDecoration(
            gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [tono, abajo])),
        child: SafeArea(
          child: Stack(children: [
            PageView(
              key: const Key('presentacion-paginas'),
              controller: _paginas,
              onPageChanged: (p) => setState(() => _pagina = p),
              children: [
                _Bienvenida(ciclo: _ciclo),
                _Roles(ciclo: _ciclo, rol: _rol, alElegir: (r) => setState(() => _rol = r)),
                _Avatares(ciclo: _ciclo, avatar: _avatar, alElegir: (a) => setState(() => _avatar = a)),
                _Ajustes(
                  ciclo: _ciclo,
                  letraGrande: _letraGrande,
                  reducir: _reducir,
                  vibrar: _vibrar,
                  alCambiar: (letra, reducir, vibrar) => setState(() {
                    _letraGrande = letra;
                    _reducir = reducir;
                    _vibrar = vibrar;
                  }),
                ),
              ].take(_cuantas).toList(),
            ),
            // «Omitir»: lleva a los ajustes (sin rol elegido, «Quién atiende» se pregunta al crear la cuenta)
            Positioned(
              top: 6,
              right: 12,
              child: AnimatedOpacity(
                opacity: _pagina < 3 ? 1 : 0,
                duration: const Duration(milliseconds: 300),
                child: IgnorePointer(
                  ignoring: _pagina >= 3,
                  child: TextButton(
                    key: const Key('omitir'),
                    onPressed: _omitir,
                    child: const Text('Omitir', style: TextStyle(color: ColoresClaros.ciruela900, fontWeight: FontWeight.w500, fontSize: 15)),
                  ),
                ),
              ),
            ),
            Positioned(
              left: 24,
              right: 24,
              bottom: 26,
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                _Puntos(pagina: _pagina),
                const SizedBox(height: 18),
                Rebote(
                  key: const Key('presentacion-siguiente'),
                  etiqueta: _textosBoton[_pagina],
                  alTocar: _puedeSeguir ? _siguiente : null,
                  child: AnimatedOpacity(
                    opacity: _puedeSeguir ? 1 : .4,
                    duration: const Duration(milliseconds: 250),
                    child: Container(
                      height: 56,
                      alignment: Alignment.center,
                      decoration: BoxDecoration(
                        color: ColoresClaros.ciruela900,
                        borderRadius: BorderRadius.circular(18),
                        boxShadow: const [BoxShadow(color: Color(0x4D7B2D5B), blurRadius: 24, offset: Offset(0, 10))],
                      ),
                      child: AnimatedSwitcher(
                        duration: const Duration(milliseconds: 250),
                        child: Text(_textosBoton[_pagina],
                            key: ValueKey(_pagina),
                            style: const TextStyle(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w600)),
                      ),
                    ),
                  ),
                ),
                if (_pagina == 1 && _rol == null)
                  const Padding(
                    padding: EdgeInsets.only(top: 8),
                    child: Text('Elija quién atiende para continuar', style: TextStyle(color: ColoresClaros.tintaSuave, fontSize: 12.5)),
                  ),
              ]),
            ),
          ]),
        ),
      ),
    );
  }
}

/// Indicadores de página: el de la página actual se estira con un pequeño rebote.
class _Puntos extends StatelessWidget {
  const _Puntos({required this.pagina});

  final int pagina;

  @override
  Widget build(BuildContext context) => Semantics(
        label: 'Pantalla ${pagina + 1} de 4',
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          for (var k = 0; k < 4; k++)
            AnimatedContainer(
              key: Key('punto-$k'),
              duration: const Duration(milliseconds: 450),
              curve: const Cubic(.3, 1.6, .4, 1),
              margin: const EdgeInsets.symmetric(horizontal: 4),
              width: k == pagina ? 28 : 8,
              height: 8,
              decoration: BoxDecoration(
                color: k == pagina ? ColoresClaros.ciruela900 : const Color(0x407B2D5B),
                borderRadius: BorderRadius.circular(4),
              ),
            ),
        ]),
      );
}

// ------------------------------------------------------------------ piezas comunes
/// Valor de 0 a 1 que va y vuelve suave, `veces` por cada vuelta del reloj de 36 s.
double _vaivenDe(double t, double periodo, {double desfase = 0}) =>
    .5 - .5 * math.cos(2 * math.pi * (t * 36 / periodo + desfase));

/// Cristal: blanco translúcido con desenfoque del fondo.
class _Cristal extends StatelessWidget {
  const _Cristal({required this.child, this.radio = 22, this.opacidad = .7, this.borde});

  final Widget child;
  final double radio;
  final double opacidad;
  final Color? borde;

  @override
  Widget build(BuildContext context) => ClipRRect(
        borderRadius: BorderRadius.circular(radio),
        child: BackdropFilter(
          filter: ui.ImageFilter.blur(sigmaX: 18, sigmaY: 18),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 300),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: opacidad),
              borderRadius: BorderRadius.circular(radio),
              border: Border.all(color: borde ?? Colors.transparent, width: 2),
              boxShadow: const [BoxShadow(color: Color(0x177B2D5B), blurRadius: 24, offset: Offset(0, 8))],
            ),
            child: child,
          ),
        ),
      );
}

/// Encabezado de las pantallas 2 a 4: ícono en un cuadro de cristal, título y subtítulo.
class _Cabecera extends StatelessWidget {
  const _Cabecera({required this.icono, required this.titulo, required this.subtitulo});

  final IconData icono;
  final String titulo;
  final String subtitulo;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Row(children: [
          Container(
            width: 56,
            height: 56,
            decoration: BoxDecoration(color: Colors.white.withValues(alpha: .75), borderRadius: BorderRadius.circular(18)),
            child: Icon(icono, color: ColoresClaros.ciruela900, size: 28),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(titulo, style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w700, letterSpacing: -.5, color: ColoresClaros.tinta)),
              Text(subtitulo, style: const TextStyle(fontSize: 14, color: ColoresClaros.tintaSuave)),
            ]),
          ),
        ]),
      );
}

/// Contenido de una pantalla con desplazamiento (en teléfonos pequeños nada queda tapado por el botón).
class _Pagina extends StatelessWidget {
  const _Pagina({required this.children});

  final List<Widget> children;

  @override
  Widget build(BuildContext context) => ListView(
        padding: const EdgeInsets.fromLTRB(24, 56, 24, 170),
        children: children,
      );
}

/// Aparece subiendo 28 px la primera vez que se dibuja.
class _Sube extends StatelessWidget {
  const _Sube({required this.retraso, required this.child});

  final int retraso;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    if (MediaQuery.of(context).disableAnimations) return child;
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: 1),
      duration: Duration(milliseconds: 900 + retraso),
      curve: Interval(retraso / (900 + retraso), 1, curve: const Cubic(.2, .9, .25, 1)),
      builder: (context, v, hijo) => Opacity(opacity: v, child: Transform.translate(offset: Offset(0, 28 * (1 - v)), child: hijo)),
      child: child,
    );
  }
}

// ------------------------------------------------------------------ 1 · bienvenida
class _Bienvenida extends StatelessWidget {
  const _Bienvenida({required this.ciclo});

  final Animation<double> ciclo;

  @override
  Widget build(BuildContext context) => Stack(children: [
        Positioned.fill(child: _Corazones(ciclo: ciclo)),
        Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(24, 40, 24, 170),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              AnimatedBuilder(
                animation: ciclo,
                builder: (context, _) {
                  final v = _vaivenDe(ciclo.value, 2.6); // flota y late cada 2,6 s
                  return Column(children: [
                    Transform.translate(
                      offset: Offset(0, -14 * v),
                      child: Transform.scale(
                        scale: 1 + .05 * v,
                        child: Image.asset('assets/logo_isotipo.webp', width: 210, semanticLabel: 'Logo de MATERNA'),
                      ),
                    ),
                    const SizedBox(height: 6),
                    Opacity(
                      opacity: .9 - .4 * v,
                      child: Transform.scale(
                        scaleX: 1 - .3 * v,
                        child: Container(
                          width: 120,
                          height: 12,
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(60),
                            boxShadow: const [BoxShadow(color: Color(0x2E7B2D5B), blurRadius: 10)],
                          ),
                        ),
                      ),
                    ),
                  ]);
                },
              ),
              const SizedBox(height: 22),
              const _Sube(
                retraso: 200,
                child: Text('Cuidar a tiempo\nsalva vidas',
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 32, height: 1.1, fontWeight: FontWeight.w700, letterSpacing: -.8, color: ColoresClaros.tinta)),
              ),
              const SizedBox(height: 12),
              const _Sube(
                retraso: 450,
                child: SizedBox(
                  width: 290,
                  child: Text('Detecta a tiempo los riesgos del embarazo, incluso donde no hay internet.',
                      textAlign: TextAlign.center, style: TextStyle(fontSize: 16, height: 1.4, color: ColoresClaros.tintaSuave)),
                ),
              ),
            ]),
          ),
        ),
      ]);
}

/// Corazoncitos rosados que suben despacio, se mecen y se desvanecen.
class _Corazones extends StatelessWidget {
  const _Corazones({required this.ciclo});

  final Animation<double> ciclo;

  static const _colores = [Color(0xFFE9BFD3), Color(0xFFD898B6), Color(0xFFF3CFE0), Color(0xFFC47A9F)];
  static const _x = [.10, .26, .42, .58, .72, .84, .34];

  @override
  Widget build(BuildContext context) {
    if (MediaQuery.of(context).disableAnimations) return const SizedBox.shrink();
    return ExcludeSemantics(
      child: LayoutBuilder(
        builder: (context, caja) => AnimatedBuilder(
          animation: ciclo,
          builder: (context, _) => Stack(children: [
            for (var k = 0; k < 7; k++) () {
              final periodo = 9.0 + (k % 3) * 2; // segundos que tarda en subir
              final f = (ciclo.value * 36 / periodo + k * 1.3 / periodo) % 1;
              final opacidad = f < .2 ? f / .2 * .55 : .55 * (1 - (f - .2) / .8);
              final lado = (k.isOdd ? 1 : -1) * (14 + k * 5.0);
              return Positioned(
                left: caja.maxWidth * _x[k] + lado * f,
                top: caja.maxHeight + 30 - f * (caja.maxHeight + 60),
                child: Opacity(
                  opacity: opacidad.clamp(0.0, 1.0),
                  child: Transform.rotate(
                    angle: f * 50 * math.pi / 180,
                    child: Transform.scale(
                      scale: .6 + .5 * f,
                      child: Icon(Icons.favorite_rounded, size: 14 + (k % 3) * 5.0, color: _colores[k % 4]),
                    ),
                  ),
                ),
              );
            }(),
          ]),
        ),
      ),
    );
  }
}

// ------------------------------------------------------------------ 2 · quién atiende
class _Roles extends StatelessWidget {
  const _Roles({required this.ciclo, required this.rol, required this.alElegir});

  final Animation<double> ciclo;
  final String? rol;
  final ValueChanged<String> alElegir;

  @override
  Widget build(BuildContext context) => _Pagina(children: [
        const _Cabecera(icono: Icons.waving_hand_outlined, titulo: '¿Quién usará MATERNA?', subtitulo: 'Así llenamos «Quién atiende» en su cuenta'),
        const SizedBox(height: 6),
        _Cristal(
          radio: 28,
          opacidad: .45,
          child: SizedBox(
            height: 120,
            child: ExcludeSemantics(child: CustomPaint(painter: _Territorio(ciclo, quieto: MediaQuery.of(context).disableAnimations))),
          ),
        ),
        const SizedBox(height: 14),
        for (final (clave, icono, descripcion) in _roles) ...[
          Rebote(
            key: Key('rol-$clave'),
            etiqueta: atiende[clave],
            seleccionado: rol == clave,
            alTocar: () => alElegir(clave),
            child: _Cristal(
              opacidad: rol == clave ? 1 : .7,
              borde: rol == clave ? ColoresClaros.ciruela900 : null,
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Row(children: [
                  Container(
                    width: 48,
                    height: 48,
                    decoration: BoxDecoration(color: ColoresClaros.ciruela100, borderRadius: BorderRadius.circular(15)),
                    child: Icon(icono, color: ColoresClaros.ciruela900),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(atiende[clave]!, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: ColoresClaros.tinta)),
                      Text(descripcion, style: const TextStyle(fontSize: 13, color: ColoresClaros.tintaSuave)),
                    ]),
                  ),
                  Casilla(marcada: rol == clave),
                ]),
              ),
            ),
          ),
          const SizedBox(height: 12),
        ],
      ]);
}

/// Ilustración del territorio: nube que se desplaza, colinas, casas, un árbol que se mece, la ubicación que
/// salta sobre su onda y una señal que se enciende y se apaga (sin internet, MATERNA sigue funcionando).
class _Territorio extends CustomPainter {
  _Territorio(this.ciclo, {required this.quieto}) : super(repaint: ciclo);

  final Animation<double> ciclo;
  final bool quieto;

  @override
  void paint(Canvas canvas, Size size) {
    final t = quieto ? 0.0 : ciclo.value;
    canvas.scale(size.width / 342, size.height / 120);
    final pincel = Paint()..isAntiAlias = true;
    // nube que va y viene (9 s)
    final dx = 46 * _vaivenDe(t, 18);
    pincel.color = Colors.white.withValues(alpha: .9);
    for (final (x, y, r) in [(52.0, 30.0, 9.0), (64.0, 26.0, 12.0), (78.0, 31.0, 8.0)]) {
      canvas.drawCircle(Offset(x + dx, y), r, pincel);
    }
    canvas.drawRRect(RRect.fromLTRBR(44 + dx, 30, 86 + dx, 40, const Radius.circular(5)), pincel);
    // colinas
    canvas.drawPath(
        Path()
          ..moveTo(0, 92)
          ..cubicTo(50, 66, 110, 70, 170, 84)
          ..cubicTo(230, 98, 280, 90, 342, 68)
          ..lineTo(342, 120)
          ..lineTo(0, 120)
          ..close(),
        pincel..color = Colors.white.withValues(alpha: .7));
    canvas.drawPath(
        Path()
          ..moveTo(0, 106)
          ..cubicTo(70, 88, 140, 92, 200, 100)
          ..cubicTo(260, 108, 290, 98, 342, 88)
          ..lineTo(342, 120)
          ..lineTo(0, 120)
          ..close(),
        pincel
          ..shader = const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFFF6D3E2), Color(0xFFEBB9D0)])
              .createShader(const Rect.fromLTWH(0, 88, 342, 32)));
    pincel.shader = null;
    // casas
    void casa(double x, double y, double ancho, double alto, Color techo) {
      canvas.drawRRect(RRect.fromLTRBR(x, y, x + ancho, y + alto, const Radius.circular(9)), pincel..color = Colors.white);
      canvas.drawPath(
          Path()
            ..moveTo(x + 4, y + 2)
            ..lineTo(x + ancho / 2, y - ancho * .36)
            ..lineTo(x + ancho - 4, y + 2)
            ..close(),
          Paint()
            ..color = techo
            ..strokeWidth = 8
            ..strokeJoin = StrokeJoin.round
            ..style = PaintingStyle.fill);
      canvas.drawRRect(RRect.fromLTRBR(x + ancho * .34, y + alto * .43, x + ancho * .66, y + alto, const Radius.circular(7)),
          pincel..color = const Color(0xFFEBB9D0));
    }

    casa(118, 76, 44, 28, const Color(0xFFA24477));
    casa(208, 82, 36, 22, ColoresClaros.ciruela900);
    // árbol que se mece (3 s)
    canvas.save();
    canvas.translate(287, 104);
    canvas.rotate((-4 + 8 * _vaivenDe(t, 6)) * math.pi / 180);
    canvas.drawRRect(RRect.fromLTRBR(-3, -24, 3, 0, const Radius.circular(3)), pincel..color = ColoresClaros.ciruela900);
    canvas.drawCircle(const Offset(0, -34), 16, pincel..color = const Color(0xFFC47A9F));
    canvas.drawCircle(const Offset(-9, -26), 10, pincel..color = const Color(0xFFD898B6));
    canvas.drawCircle(const Offset(9, -28), 9, pincel..color = const Color(0xFFA24477));
    canvas.restore();
    // onda bajo la ubicación (1,6 s)
    final onda = (t * 36 / 1.6) % 1;
    canvas.save();
    canvas.translate(178, 104);
    canvas.scale(.4 + 1.2 * onda);
    canvas.drawOval(
        Rect.fromCenter(center: Offset.zero, width: 28, height: 9),
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2.5 / (.4 + 1.2 * onda)
          ..color = ColoresClaros.ciruela900.withValues(alpha: .7 * (1 - onda)));
    canvas.restore();
    // ubicación que salta (1,6 s)
    final salto = -9 * _vaivenDe(t, 1.6);
    final pin = Path()
      ..moveTo(178, 98 + salto)
      ..cubicTo(170, 91 + salto, 165, 84 + salto, 165, 77 + salto)
      ..arcToPoint(Offset(191, 77 + salto), radius: const Radius.circular(13))
      ..cubicTo(191, 84 + salto, 186, 91 + salto, 178, 98 + salto)
      ..close();
    canvas.drawPath(pin, pincel..color = ColoresClaros.ciruela900);
    canvas.drawCircle(Offset(178, 77 + salto), 5, pincel..color = Colors.white);
    // señal que se enciende por arcos y se apaga (2,2 s)
    final senal = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 4
      ..strokeCap = StrokeCap.round;
    canvas.drawCircle(const Offset(56, 100), 6, pincel..color = ColoresClaros.ciruela900);
    for (var k = 0; k < 3; k++) {
      final f = ((t * 36 / 2.2) - k * .16) % 1;
      final a = f < .3 ? f / .3 * .9 : .9 * (1 - (f - .3) / .7);
      final r = 10.0 + k * 10;
      canvas.drawArc(Rect.fromCircle(center: const Offset(56, 100), radius: r), -math.pi * .78, math.pi * .56, false,
          senal..color = ColoresClaros.ciruela900.withValues(alpha: a.clamp(0.0, 1.0)));
    }
  }

  @override
  bool shouldRepaint(_Territorio viejo) => viejo.quieto != quieto;
}

// ------------------------------------------------------------------ 3 · avatar
class _Avatares extends StatelessWidget {
  const _Avatares({required this.ciclo, required this.avatar, required this.alElegir});

  final Animation<double> ciclo;
  final int avatar;
  final ValueChanged<int> alElegir;

  @override
  Widget build(BuildContext context) => _Pagina(children: [
        const _Cabecera(icono: Icons.face_retouching_natural_outlined, titulo: 'Elija su avatar', subtitulo: 'Así se verá su cuenta en la app'),
        Center(
          child: SizedBox(
            width: 170,
            height: 170,
            child: AnimatedBuilder(
              animation: ciclo,
              builder: (context, hijo) {
                final quieto = MediaQuery.of(context).disableAnimations;
                final pulso = quieto ? 1.0 : (ciclo.value * 36 / 2.4) % 1; // halo que se expande cada 2,4 s
                final giro = quieto ? 0.0 : ciclo.value * 36 / 9 * 2 * math.pi; // órbita de 9 s
                return Stack(alignment: Alignment.center, children: [
                  // anillo fijo con brillo
                  Container(
                    margin: const EdgeInsets.all(4),
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      border: Border.all(color: const Color(0x2E7B2D5B), width: 1.5),
                      gradient: const RadialGradient(colors: [Color(0x99FFFFFF), Color(0x00FFFFFF)]),
                    ),
                  ),
                  // halo que late
                  if (!quieto)
                    Transform.scale(
                      scale: 1 + .55 * pulso,
                      child: Container(
                        width: 120,
                        height: 120,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          border: Border.all(color: ColoresClaros.ciruela900.withValues(alpha: .45 * (1 - pulso)), width: 2),
                        ),
                      ),
                    ),
                  // tres puntos en órbita
                  Transform.rotate(
                    angle: giro,
                    child: SizedBox.expand(
                      child: Stack(children: [
                        const Positioned(top: -3, left: 79, child: _Punto(Color(0xA67B2D5B))),
                        const Positioned(bottom: 20, left: 12, child: _Punto(Color(0xFFC47A9F))),
                        const Positioned(bottom: 20, right: 12, child: _Punto(Color(0xFFE9BFD3))),
                      ]),
                    ),
                  ),
                  hijo!,
                ]);
              },
              // el avatar grande cambia con un rebote elástico
              child: AnimatedSwitcher(
                duration: const Duration(milliseconds: 600),
                transitionBuilder: (hijo, animacion) =>
                    ScaleTransition(scale: Tween<double>(begin: .6, end: 1).animate(CurvedAnimation(parent: animacion, curve: const Cubic(.3, 1.8, .4, 1))), child: hijo),
                child: DecoratedBox(
                  key: ValueKey(avatar),
                  decoration: const BoxDecoration(
                    shape: BoxShape.circle,
                    boxShadow: [BoxShadow(color: Color(0x597B2D5B), blurRadius: 30, offset: Offset(0, 12))],
                  ),
                  child: AvatarCirculo(avatar, tamano: 120),
                ),
              ),
            ),
          ),
        ),
        const SizedBox(height: 16),
        Wrap(alignment: WrapAlignment.center, spacing: 18, runSpacing: 18, children: [
          for (var k = 0; k < avatares.length; k++)
            Rebote(
              key: Key('avatar-$k'),
              etiqueta: 'Avatar ${avatares[k].nombre}',
              seleccionado: k == avatar,
              alTocar: () => alElegir(k),
              child: AnimatedScale(
                scale: k == avatar ? 1.12 : 1,
                duration: const Duration(milliseconds: 500),
                curve: const Cubic(.3, 1.8, .4, 1),
                child: _Cristal(
                  radio: 38,
                  opacidad: .8,
                  borde: k == avatar ? ColoresClaros.ciruela900 : null,
                  child: SizedBox(width: 72, height: 72, child: Icon(avatares[k].icono, color: ColoresClaros.ciruela900, size: 34)),
                ),
              ),
            ),
        ]),
      ]);
}

class _Punto extends StatelessWidget {
  const _Punto(this.color);

  final Color color;

  @override
  Widget build(BuildContext context) =>
      Container(width: 11, height: 11, decoration: BoxDecoration(color: color, shape: BoxShape.circle));
}

// ------------------------------------------------------------------ 4 · ajustes
class _Ajustes extends StatelessWidget {
  const _Ajustes({required this.ciclo, required this.letraGrande, required this.reducir, required this.vibrar, required this.alCambiar});

  final Animation<double> ciclo;
  final bool letraGrande;
  final bool reducir;
  final bool vibrar;
  final void Function(bool letraGrande, bool reducir, bool vibrar) alCambiar;

  @override
  Widget build(BuildContext context) {
    final opciones = [
      ('letra', Icons.text_increase_rounded, 'Letra más grande', 'Para leer mejor al sol o en un teléfono pequeño', letraGrande,
          () => alCambiar(!letraGrande, reducir, vibrar)),
      ('animaciones', Icons.motion_photos_off_outlined, 'Reducir animaciones', 'La app responde igual, sin movimientos', reducir,
          () => alCambiar(letraGrande, !reducir, vibrar)),
      ('vibrar', Icons.vibration_rounded, 'Vibrar con Alto Riesgo', 'Un aviso más cuando una evaluación sale Alto Riesgo', vibrar,
          () => alCambiar(letraGrande, reducir, !vibrar)),
    ];
    return _Pagina(children: [
      const _Cabecera(icono: Icons.shield_outlined, titulo: 'Casi listo', subtitulo: 'Ajuste cómo se ve y se siente la app'),
      const SizedBox(height: 6),
      _Cristal(
        radio: 28,
        opacidad: .45,
        child: SizedBox(
          height: 130,
          child: ExcludeSemantics(child: CustomPaint(painter: _Escudo(ciclo, quieto: MediaQuery.of(context).disableAnimations))),
        ),
      ),
      const SizedBox(height: 14),
      for (final (clave, icono, titulo, descripcion, marcada, alTocar) in opciones) ...[
        Rebote(
          key: Key('ajuste-$clave'),
          etiqueta: titulo,
          seleccionado: marcada,
          alTocar: alTocar,
          child: _Cristal(
            opacidad: .85,
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Row(children: [
                Icon(icono, color: ColoresClaros.ciruela900),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(titulo, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: ColoresClaros.tinta)),
                    Text(descripcion, style: const TextStyle(fontSize: 13, color: ColoresClaros.tintaSuave)),
                  ]),
                ),
                Casilla(marcada: marcada, cuadrada: true),
              ]),
            ),
          ),
        ),
        const SizedBox(height: 12),
      ],
      const Text('La pertenencia étnica y el municipio de la gestante nunca se usan para calcular su riesgo.',
          textAlign: TextAlign.center, style: TextStyle(fontSize: 12.5, height: 1.4, color: ColoresClaros.tintaSuave)),
    ]);
  }
}

/// Escudo con un visto que se dibuja y se borra, una onda alrededor, destellos y tres íconos en órbita.
class _Escudo extends CustomPainter {
  _Escudo(this.ciclo, {required this.quieto}) : super(repaint: ciclo);

  final Animation<double> ciclo;
  final bool quieto;

  static const _iconos = [Icons.text_increase_rounded, Icons.motion_photos_off_outlined, Icons.vibration_rounded];

  @override
  void paint(Canvas canvas, Size size) {
    final t = quieto ? 0.0 : ciclo.value;
    canvas.scale(size.width / 342, size.height / 130);
    const centro = Offset(171, 65);
    final pincel = Paint()..isAntiAlias = true;
    // destellos que titilan (2 s, desfasados)
    for (final (i, (x, y, r)) in [(38.0, 28.0, 4.0), (305.0, 36.0, 5.0), (66.0, 108.0, 3.0), (284.0, 100.0, 4.0), (132.0, 16.0, 3.0), (226.0, 14.0, 4.0)].indexed) {
      final v = quieto ? 1.0 : _vaivenDe(t, 2, desfase: i * .175);
      canvas.drawCircle(Offset(x, y), r * (.4 + .6 * v), pincel..color = const Color(0xFFC47A9F).withValues(alpha: .3 + .7 * v));
    }
    // onda alrededor del escudo (1,6 s)
    if (!quieto) {
      final f = (t * 36 / 1.6) % 1;
      canvas.drawCircle(
          centro,
          40 * (.4 + 1.2 * f),
          Paint()
            ..style = PaintingStyle.stroke
            ..strokeWidth = 2.5
            ..color = ColoresClaros.ciruela900.withValues(alpha: .7 * (1 - f)));
    }
    // escudo
    final escudo = Path()
      ..moveTo(171, 34)
      ..cubicTo(184, 42, 195, 44, 201, 44)
      ..lineTo(201, 64)
      ..cubicTo(201, 81, 189, 92, 171, 99)
      ..cubicTo(153, 92, 141, 81, 141, 64)
      ..lineTo(141, 44)
      ..cubicTo(147, 44, 158, 42, 171, 34)
      ..close();
    canvas.drawPath(
        escudo,
        Paint()
          ..shader = const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFFA24477), Color(0xFF6A2650)])
              .createShader(const Rect.fromLTWH(141, 34, 60, 65))
          ..strokeWidth = 8
          ..strokeJoin = StrokeJoin.round
          ..style = PaintingStyle.fill);
    // visto que se dibuja, se queda y se borra (3 s)
    final f = quieto ? .5 : (t * 36 / 3) % 1;
    final trazo = f < .1 ? 0.0 : f < .35 ? (f - .1) / .25 : f < .85 ? 1.0 : 1 - (f - .85) / .15;
    final visto = Path()
      ..moveTo(158, 66)
      ..lineTo(167, 75)
      ..lineTo(184, 56);
    for (final m in visto.computeMetrics()) {
      canvas.drawPath(
          m.extractPath(0, m.length * Curves.easeInOut.transform(trazo.clamp(0.0, 1.0))),
          Paint()
            ..style = PaintingStyle.stroke
            ..strokeWidth = 6
            ..strokeCap = StrokeCap.round
            ..strokeJoin = StrokeJoin.round
            ..color = Colors.white);
    }
    // tres íconos en órbita alrededor del escudo (14 s), siempre derechos
    final giro = t * 36 / 14 * 2 * math.pi;
    for (final (i, (x, y)) in [(171.0, 15.0), (251.0, 89.0), (91.0, 89.0)].indexed) {
      final a = math.atan2(y - centro.dy, x - centro.dx) + giro;
      final r = (Offset(x, y) - centro).distance;
      final p = centro + Offset(math.cos(a), math.sin(a)) * r;
      final caja = RRect.fromRectAndRadius(Rect.fromCenter(center: p, width: 32, height: 32), const Radius.circular(11));
      canvas.drawRRect(caja.shift(const Offset(0, 4)), Paint()
        ..color = const Color(0x387B2D5B)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 4));
      canvas.drawRRect(caja, pincel..color = Colors.white);
      final icono = TextPainter(
        text: TextSpan(
          text: String.fromCharCode(_iconos[i].codePoint),
          style: TextStyle(fontSize: 19, fontFamily: _iconos[i].fontFamily, package: _iconos[i].fontPackage, color: ColoresClaros.ciruela900),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      icono.paint(canvas, p - Offset(icono.width / 2, icono.height / 2));
    }
  }

  @override
  bool shouldRepaint(_Escudo viejo) => viejo.quieto != quieto;
}
