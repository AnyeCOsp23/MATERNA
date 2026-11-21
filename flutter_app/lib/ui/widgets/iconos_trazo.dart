/// Iconos vectoriales de trazo fino para la barra de navegación (estetoscopio, subir archivo, base de datos e
/// información): los dos primeros no existen en Material Icons y los cuatro deben tener el mismo trazo.
/// Se dibujan con CustomPainter en una cuadrícula de 24 x 24, con el mismo grosor que los iconos de contorno.
library;

import 'package:flutter/material.dart';

enum IconoTrazo { estetoscopio, subirArchivo, baseDatos, informacion, mapa }

class IconoDeTrazo extends StatelessWidget {
  const IconoDeTrazo(this.icono, {super.key, required this.color, this.tamano = 24});

  final IconoTrazo icono;
  final Color color;
  final double tamano;

  @override
  Widget build(BuildContext context) =>
      SizedBox.square(dimension: tamano, child: CustomPaint(painter: _Pintor(icono, color)));
}

class _Pintor extends CustomPainter {
  _Pintor(this.icono, this.color);

  final IconoTrazo icono;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    canvas.scale(size.width / 24, size.height / 24);
    final trazo = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.7
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;
    switch (icono) {
      case IconoTrazo.estetoscopio:
        // Auriculares en U, tubo que baja y sube hacia la campana
        canvas.drawPath(
          Path()
            ..moveTo(5, 3)
            ..lineTo(5, 8)
            ..arcToPoint(const Offset(13, 8), radius: const Radius.circular(4), clockwise: false)
            ..lineTo(13, 3),
          trazo,
        );
        canvas.drawPath(
          Path()
            ..moveTo(9, 12)
            ..lineTo(9, 15)
            ..arcToPoint(const Offset(19, 15), radius: const Radius.circular(5), clockwise: false)
            ..lineTo(19, 12.2),
          trazo,
        );
        canvas.drawCircle(const Offset(19, 10.2), 2, trazo);
        canvas.drawLine(const Offset(4, 3), const Offset(6, 3), trazo);
        canvas.drawLine(const Offset(12, 3), const Offset(14, 3), trazo);
      case IconoTrazo.subirArchivo:
        // Hoja con la esquina doblada y una flecha hacia arriba
        canvas.drawPath(
          Path()
            ..moveTo(14, 3)
            ..lineTo(7, 3)
            ..arcToPoint(const Offset(5, 5), radius: const Radius.circular(2), clockwise: false)
            ..lineTo(5, 19)
            ..arcToPoint(const Offset(7, 21), radius: const Radius.circular(2), clockwise: false)
            ..lineTo(17, 21)
            ..arcToPoint(const Offset(19, 19), radius: const Radius.circular(2), clockwise: false)
            ..lineTo(19, 8)
            ..close(),
          trazo,
        );
        canvas.drawPath(Path()..moveTo(14, 3)..lineTo(14, 8)..lineTo(19, 8), trazo);
        canvas.drawLine(const Offset(12, 17.5), const Offset(12, 11.5), trazo);
        canvas.drawPath(Path()..moveTo(9.5, 14)..lineTo(12, 11.5)..lineTo(14.5, 14), trazo);
      case IconoTrazo.mapa:
        // Marcador de ubicación (gota con un círculo) sobre una línea de suelo
        canvas.drawPath(
          Path()
            ..moveTo(12, 19)
            ..cubicTo(8.5, 15.2, 6, 12.4, 6, 9.4)
            ..arcToPoint(const Offset(18, 9.4), radius: const Radius.circular(6))
            ..cubicTo(18, 12.4, 15.5, 15.2, 12, 19)
            ..close(),
          trazo,
        );
        canvas.drawCircle(const Offset(12, 9.4), 2.2, trazo);
        canvas.drawLine(const Offset(7.5, 21.2), const Offset(16.5, 21.2), trazo);
      case IconoTrazo.informacion:
        canvas.drawCircle(const Offset(12, 12), 9, trazo);
        canvas.drawLine(const Offset(12, 11), const Offset(12, 16.5), trazo);
        canvas.drawCircle(const Offset(12, 7.9), 1.15, Paint()..color = color); // el punto de la i, sólido
      case IconoTrazo.baseDatos:
        // Cilindro con tres discos
        canvas.drawOval(Rect.fromCenter(center: const Offset(12, 5.5), width: 14, height: 5), trazo);
        canvas.drawLine(const Offset(5, 5.5), const Offset(5, 18.5), trazo);
        canvas.drawLine(const Offset(19, 5.5), const Offset(19, 18.5), trazo);
        for (final y in [12.0, 18.5]) {
          canvas.drawArc(Rect.fromCenter(center: Offset(12, y), width: 14, height: 5), 0, 3.14159, false, trazo);
        }
    }
  }

  @override
  bool shouldRepaint(_Pintor viejo) => viejo.icono != icono || viejo.color != color;
}
