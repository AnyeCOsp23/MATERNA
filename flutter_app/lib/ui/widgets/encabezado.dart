/// Piezas visuales comunes de las pantallas (según los mockups): encabezado con el logo, título con ícono,
/// etiqueta del nivel de riesgo, chips de datos y el borde punteado del archivo cargado.
library;

import 'package:flutter/material.dart';

import '../tema/tema_materna.dart';
import 'avatar.dart';

/// Logo y «MATERNA» a la izquierda; a la derecha, en qué parte de la app se está (o un botón para volver).
class EncabezadoMaterna extends StatelessWidget {
  const EncabezadoMaterna({super.key, required this.etiqueta, this.claveEtiqueta, this.alVolver});

  final String etiqueta;
  final Key? claveEtiqueta;

  /// Si se da, muestra a la izquierda el botón de volver.
  final VoidCallback? alVolver;

  @override
  Widget build(BuildContext context) => SizedBox(
        height: 44,
        child: Row(children: [
          if (alVolver != null) ...[
            BackButton(onPressed: alVolver, color: ColoresMaterna.ciruela900),
            const SizedBox(width: 2),
          ],
          Image.asset('assets/logo_isotipo.webp', width: 30, height: 30),
          const SizedBox(width: 8),
          const Text('MATERNA',
              style: TextStyle(fontWeight: FontWeight.w800, color: ColoresMaterna.ciruela900, fontSize: 17, letterSpacing: .2)),
          const SizedBox(width: 12),
          Expanded(
            child: Text(etiqueta,
                key: claveEtiqueta,
                textAlign: TextAlign.right,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(color: ColoresMaterna.tintaSuave, fontSize: 13, fontWeight: FontWeight.w500)),
          ),
          if (AvatarSesion.de(context) case final avatar?) ...[
            const SizedBox(width: 10),
            AvatarCirculo(avatar, key: const Key('avatar-sesion'), tamano: 30),
          ],
        ]),
      );
}

/// Ícono en un cuadro rosa claro, con el título y el subtítulo de la pantalla.
class TituloConIcono extends StatelessWidget {
  const TituloConIcono({super.key, required this.icono, required this.titulo, this.subtitulo, this.accion});

  final Widget icono;
  final String titulo;
  final String? subtitulo;
  final Widget? accion;

  @override
  Widget build(BuildContext context) => Row(children: [
        Container(
          width: 50,
          height: 50,
          decoration: BoxDecoration(color: ColoresMaterna.ciruela100, borderRadius: BorderRadius.circular(15)),
          alignment: Alignment.center,
          child: icono,
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(titulo, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: ColoresMaterna.tinta, height: 1.15)),
            if (subtitulo != null) ...[
              const SizedBox(height: 2),
              Text(subtitulo!, style: const TextStyle(color: ColoresMaterna.tintaSuave, fontSize: 13.5)),
            ],
          ]),
        ),
        ?accion,
      ]);
}

/// Etiqueta del nivel (Alto, Medio o Bajo) con el fondo y el texto de su color.
class EtiquetaNivel extends StatelessWidget {
  const EtiquetaNivel(this.estilo, {super.key});

  final EstiloRiesgo estilo;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(color: estilo.fondo, borderRadius: BorderRadius.circular(20)),
        child: Text(estilo.corto, style: TextStyle(color: estilo.tinta, fontWeight: FontWeight.w700, fontSize: 12.5)),
      );
}

/// Dato corto en una píldora blanca (p. ej. «Edad 17», «PAS 165»).
class ChipDato extends StatelessWidget {
  const ChipDato(this.texto, {super.key});

  final String texto;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: ColoresMaterna.borde),
        ),
        child: Text(texto, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500, color: ColoresMaterna.tinta)),
      );
}

/// Seudónimo abreviado: 'a3f9…c1'.
String seudonimoCorto(String? seudonimo) =>
    seudonimo == null ? 'Sin documento' : '${seudonimo.substring(0, 4)}…${seudonimo.substring(seudonimo.length - 2)}';

/// Edad y semanas de un registro: '17 años · 28 sem'.
String edadYSemanas(Map<String, dynamic> registro) {
  String n(Object? v) => v is num ? v.round().toString() : '–';
  return '${n(registro['edad'])} años · ${n(registro['semanas_gestacion'])} sem';
}

/// Tarjeta blanca con borde punteado (el archivo cargado en el mockup).
class TarjetaPunteada extends StatelessWidget {
  const TarjetaPunteada({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) => CustomPaint(
        painter: _BordePunteado(),
        child: Container(
          decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(18)),
          padding: const EdgeInsets.fromLTRB(16, 14, 12, 14),
          child: child,
        ),
      );
}

class _BordePunteado extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final pincel = Paint()
      ..color = ColoresMaterna.ciruela700.withValues(alpha: .55)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.3;
    final ruta = Path()..addRRect(RRect.fromRectAndRadius(Offset.zero & size, const Radius.circular(18)));
    for (final m in ruta.computeMetrics()) {
      for (var d = 0.0; d < m.length; d += 9) {
        canvas.drawPath(m.extractPath(d, d + 5), pincel);
      }
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
