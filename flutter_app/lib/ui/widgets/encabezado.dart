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
          Image.asset('assets/logo_isotipo.webp', width: 30, height: 30,
              color: ColoresMaterna.oscuro ? ColoresMaterna.vinoLogo : null, colorBlendMode: BlendMode.srcIn),
          const SizedBox(width: 8),
          Text('MATERNA',
              style: TextStyle(fontWeight: FontWeight.w800, color: ColoresMaterna.ciruela900, fontSize: 17, letterSpacing: .2)),
          const SizedBox(width: 12),
          Expanded(
            child: Text(etiqueta,
                key: claveEtiqueta,
                textAlign: TextAlign.right,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(color: ColoresMaterna.tintaSuave, fontSize: 13, fontWeight: FontWeight.w500)),
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
            Text(titulo, style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: ColoresMaterna.tinta, height: 1.15)),
            if (subtitulo != null) ...[
              const SizedBox(height: 2),
              Text(subtitulo!, style: TextStyle(color: ColoresMaterna.tintaSuave, fontSize: 13.5)),
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
          color: ColoresMaterna.tarjeta,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: ColoresMaterna.borde),
        ),
        child: Text(texto, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w500, color: ColoresMaterna.tinta)),
      );
}

/// Código corto de la gestante para la pantalla: 'Código 14A2-88' (los 4 primeros y los 2 últimos caracteres de su
/// seudónimo). El documento nunca se guarda; para buscar a una gestante concreta se usa «Por documento».
String codigoGestante(String? seudonimo) => seudonimo == null
    ? 'Sin documento'
    : 'Código ${seudonimo.substring(0, 4).toUpperCase()}-${seudonimo.substring(seudonimo.length - 2).toUpperCase()}';

/// Lo que se escribe en «Por código» ('14A2', '14a2-88', 'Código 14A2-88') -> (inicio, final) del seudónimo en
/// minúsculas, o null si no parece un código (p. ej. un documento: eso va en «Por documento»).
(String, String)? leerCodigo(String texto) {
  if (RegExp(r'^[A-Za-z]{1,3}\s+\d').hasMatch(texto.trim())) return null; // 'CC 1065432' es un documento
  final limpio = texto.toLowerCase().replaceAll(RegExp(r'c[oó]digo|\s'), '');
  final m = RegExp(r'^([0-9a-f]+)(?:[-–…]+([0-9a-f]*))?$').firstMatch(limpio);
  return m == null ? null : (m[1]!, m[2] ?? '');
}

/// Edad y semanas de un registro: '17 años · 28 sem' (o '28 semanas' con [largo]).
String edadYSemanas(Map<String, dynamic> registro, {bool largo = false}) {
  String n(Object? v) => v is num ? v.round().toString() : '–';
  return '${n(registro['edad'])} años · ${n(registro['semanas_gestacion'])} ${largo ? 'semanas' : 'sem'}';
}

/// Tarjeta blanca con borde punteado (el archivo cargado en el mockup).
class TarjetaPunteada extends StatelessWidget {
  const TarjetaPunteada({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) => CustomPaint(
        painter: _BordePunteado(),
        child: Container(
          decoration: BoxDecoration(color: ColoresMaterna.tarjeta, borderRadius: BorderRadius.circular(18)),
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

/// Filtro por nivel de riesgo (Carga IPS e Historial): -1 = todas; 2 = Alto, 1 = Medio, 0 = Bajo (índice de la
/// clase del modelo). Solo cambia lo que se muestra, no la clasificación.
class FiltroNivel extends StatelessWidget {
  const FiltroNivel({super.key, required this.seleccion, required this.alCambiar});

  /// null = todas.
  final int? seleccion;
  final ValueChanged<int?> alCambiar;

  @override
  Widget build(BuildContext context) => SizedBox(
        width: double.infinity,
        child: SegmentedButton<int>(
          segments: const [
            ButtonSegment(value: -1, label: Text('Todas')),
            ButtonSegment(value: 2, label: Text('Alto')),
            ButtonSegment(value: 1, label: Text('Medio')),
            ButtonSegment(value: 0, label: Text('Bajo')),
          ],
          selected: {seleccion ?? -1},
          showSelectedIcon: false,
          onSelectionChanged: (s) => alCambiar(s.first == -1 ? null : s.first),
        ),
      );
}
