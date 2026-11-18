/// Pantalla 2: resultado del triaje.
///
/// La pantalla es para personal de salud, no para técnicos: no usa términos de aprendizaje automático.
/// Orden deliberado: primero las alertas URGENTES de la ruta 3280 que no cambian el semáforo (p. ej. exposición
/// a violencias, que tiene su propia ruta), luego la tarjeta del nivel con el motivo en lenguaje claro (signo
/// crítico, signo de alarma o combinación de factores), el aviso de que es una herramienta de apoyo, los datos
/// clave, las demás alertas y la conducta sugerida. Los porcentajes y lo demás que sirve a quien audita van al
/// final, en «Ver detalle», plegado. Los signos de alarma obstétricos (sangrado, visión borrosa…) elevan el
/// semáforo a ROJO: un verde o un ámbar nunca acompañan a una urgencia obstétrica.
library;

import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../motor/catalogo_3280.dart';
import '../../motor/recursos.dart';
import '../tema/tema_materna.dart';
import '../widgets/encabezado.dart';

String _pct(double p) => '${(p * 100).round()}%';

/// Aviso visible en todo resultado.
const avisoApoyo = 'Herramienta de apoyo: no reemplaza el juicio clínico.';

class PantallaResultado extends StatelessWidget {
  const PantallaResultado({super.key, required this.recursos, required this.evaluacion, this.soloLectura = false, this.nota});

  final RecursosMaterna recursos;
  final Evaluacion evaluacion;

  /// Abierta desde el historial: sin los botones de evaluación nueva ni de corrección.
  final bool soloLectura;

  /// Contexto de una evaluación guardada (fecha, quién atendió).
  final String? nota;

  @override
  Widget build(BuildContext context) {
    final categoria = recursos.clasificador.clases[evaluacion.clase];
    final estilo = estiloPorCategoria[categoria]!;
    final urgentes = evaluacion.urgentesSinEscalar;
    return Scaffold(
      body: DecoratedBox(
        decoration: fondoCrema,
        child: SafeArea(
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 760),
              child: ListView(padding: const EdgeInsets.fromLTRB(16, 8, 16, 32), children: [
                EncabezadoMaterna(
                  etiqueta: soloLectura ? 'Evaluación guardada' : 'Evaluación',
                  alVolver: () => Navigator.of(context).maybePop(),
                ),
                const SizedBox(height: 10),
                if (nota != null) ...[
                  Text(nota!, key: const Key('nota-resultado'), style: TextStyle(color: ColoresMaterna.tintaSuave)),
                  const SizedBox(height: 12),
                ],
                if (urgentes.isNotEmpty) ...[
                  _AlertasUrgentes(urgentes, nivelNoEsAlto: categoria != 'Alto Riesgo'),
                  const SizedBox(height: 14),
                ],
                _TarjetaNivel(estilo: estilo, evaluacion: evaluacion, recursos: recursos),
                const SizedBox(height: 10),
                Row(key: Key('aviso-apoyo'), children: [
                  Icon(Icons.info_outline_rounded, size: 18, color: ColoresMaterna.tintaSuave),
                  SizedBox(width: 8),
                  Expanded(
                    child: Text(avisoApoyo,
                        style: TextStyle(color: ColoresMaterna.tintaSuave, fontWeight: FontWeight.w600, fontSize: 13)),
                  ),
                ]),
                if (evaluacion.imputadas.isNotEmpty) ...[
                  const SizedBox(height: 10),
                  _Aviso(
                    estilo: estiloPorCategoria['Riesgo Medio']!,
                    icono: Icons.info_outline_rounded,
                    texto: 'Sin dato de ${evaluacion.imputadas.map((v) => v == 'fcf_bpm' ? 'FCF' : 'glucosa').join(' y ')}: '
                        'la evaluación se hizo sin esa medición. Tome el dato cuando sea posible y repita la evaluación.',
                  ),
                ],
                const SizedBox(height: 14),
                _DatosClave(evaluacion.registro),
                if (evaluacion.noUrgentes.isNotEmpty) ...[
                  const SizedBox(height: 14),
                  _OtrasAlertas(evaluacion.noUrgentes),
                ],
                const SizedBox(height: 14),
                _Conducta(estilo: estilo, pasos: recursos.protocolo(categoria)),
                const SizedBox(height: 14),
                _Detalle(evaluacion: evaluacion, recursos: recursos),
                if (!soloLectura) ...[
                  const SizedBox(height: 24),
                  FilledButton.icon(
                    key: const Key('nueva-evaluacion'),
                    onPressed: () => Navigator.of(context).pop('nueva'),
                    icon: const Icon(Icons.add_rounded),
                    label: const Text('Nueva evaluación'),
                  ),
                  const SizedBox(height: 10),
                  OutlinedButton.icon(
                    key: const Key('editar-datos'),
                    onPressed: () => Navigator.of(context).pop('editar'),
                    icon: const Icon(Icons.edit_rounded),
                    label: const Text('Corregir los datos'),
                  ),
                ],
              ]),
            ),
          ),
        ),
      ),
    );
  }
}

class _AlertasUrgentes extends StatelessWidget {
  const _AlertasUrgentes(this.alertas, {required this.nivelNoEsAlto});

  final List<Alerta3280> alertas;

  /// El semáforo no está en rojo: hay que decir explícitamente que la alerta se atiende igual.
  final bool nivelNoEsAlto;

  @override
  Widget build(BuildContext context) => Container(
        key: const Key('alertas-urgentes'),
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(
          gradient: LinearGradient(colors: [ColoresMaterna.vino, ColoresMaterna.ciruelaNoche]),
          borderRadius: BorderRadius.circular(22),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Row(children: [
            Icon(Icons.priority_high_rounded, color: Colors.white),
            SizedBox(width: 8),
            Expanded(
              child: Text('Signos de alarma: valoración médica inmediata',
                  style: TextStyle(color: Colors.white, fontWeight: FontWeight.w800, fontSize: 16)),
            ),
          ]),
          if (nivelNoEsAlto)
            Padding(
              padding: EdgeInsets.only(top: 6),
              child: Text('Aunque el nivel no es Alto Riesgo, estas alertas requieren atención inmediata.',
                  style: TextStyle(color: ColoresMaterna.ciruela100, fontSize: 13)),
            ),
          const SizedBox(height: 10),
          for (final a in alertas)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('•  ', style: TextStyle(color: Colors.white)),
                Expanded(child: Text(a.mensaje, style: const TextStyle(color: Colors.white, height: 1.35))),
              ]),
            ),
        ]),
      );
}

/// Tarjeta del nivel: degradado del color, ícono del nivel y el motivo en lenguaje claro.
class _TarjetaNivel extends StatelessWidget {
  const _TarjetaNivel({required this.estilo, required this.evaluacion, required this.recursos});

  final EstiloRiesgo estilo;
  final Evaluacion evaluacion;
  final RecursosMaterna recursos;

  @override
  Widget build(BuildContext context) {
    final motivo = switch (evaluacion.origen) {
      'regla_clinica' => 'Signo crítico: ${recursos.motivo(evaluacion)}',
      'signo_alarma_3280' => 'Signo de alarma: ${recursos.motivo(evaluacion)}',
      _ => recursos.motivo(evaluacion),
    };
    const blanco = Colors.white;
    final suave = Colors.white.withValues(alpha: .82);
    return Container(
      key: const Key('semaforo'),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: estilo.degradado),
        borderRadius: BorderRadius.circular(24),
        boxShadow: [BoxShadow(color: estilo.degradado.last.withValues(alpha: .18), blurRadius: 24, offset: const Offset(0, 6))],
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          _Anillo(Icon(estilo.icono, color: blanco, size: 30)),
          const SizedBox(width: 16),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                // punto dibujado: la tipografía incluida no trae «●» y sin internet saldría un cuadro vacío
                Container(width: 7, height: 7, decoration: BoxDecoration(color: suave, shape: BoxShape.circle)),
                const SizedBox(width: 6),
                Text(estilo.nivel, style: TextStyle(color: suave, fontWeight: FontWeight.w700, fontSize: 11.5, letterSpacing: 1.1)),
              ]),
              const SizedBox(height: 2),
              Text(estilo.titulo, style: const TextStyle(color: blanco, fontWeight: FontWeight.w800, fontSize: 26, height: 1.1)),
              const SizedBox(height: 6),
              Text(motivo, key: const Key('motivo'), style: TextStyle(color: suave, fontWeight: FontWeight.w600, fontSize: 13.5, height: 1.3)),
            ]),
          ),
        ]),
        if (evaluacion.origen == 'regla_clinica' && evaluacion.signosAlarma.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 10),
            child: Text('Además, signos de alarma: ${evaluacion.alertasQueEscalan.map((a) => a.etiqueta.toLowerCase()).join(', ')}',
                style: TextStyle(color: suave, fontSize: 13)),
          ),
        Padding(
          padding: const EdgeInsets.only(top: 10),
          child: Text(estilo.subtitulo, style: const TextStyle(color: blanco, fontWeight: FontWeight.w700, fontSize: 13.5)),
        ),
      ]),
    );
  }
}

/// Anillo decorativo con el ícono del nivel. El porcentaje ya no va aquí: está en «Ver detalle».
class _Anillo extends StatelessWidget {
  const _Anillo(this.centro);

  final Widget centro;

  @override
  Widget build(BuildContext context) => SizedBox(
        width: 78,
        height: 78,
        child: CustomPaint(painter: _PintorAnillo(), child: Center(child: centro)),
      );
}

class _PintorAnillo extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    const grosor = 7.0;
    final pincel = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = grosor
      ..color = Colors.white;
    canvas.drawArc((Offset.zero & size).deflate(grosor / 2), 0, 2 * math.pi, false, pincel);
  }

  @override
  bool shouldRepaint(_PintorAnillo anterior) => false;
}

/// «Ver detalle», plegado: lo que sirve a quien audita y no hace falta para atender a la gestante.
class _Detalle extends StatelessWidget {
  const _Detalle({required this.evaluacion, required this.recursos});

  final Evaluacion evaluacion;
  final RecursosMaterna recursos;

  @override
  Widget build(BuildContext context) {
    final probabilidades = evaluacion.triaje.probabilidades;
    final clases = recursos.clasificador.clases;
    final estimado = evaluacion.triaje.claseModelo;
    final nota = TextStyle(color: ColoresMaterna.tintaSuave, fontSize: 12.5, height: 1.35);
    return Card(
      key: const Key('detalle'),
      clipBehavior: Clip.antiAlias,
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          title: Text('Ver detalle', style: TextStyle(fontWeight: FontWeight.w800, color: ColoresMaterna.tinta)),
          tilePadding: const EdgeInsets.symmetric(horizontal: 18),
          childrenPadding: const EdgeInsets.fromLTRB(18, 0, 18, 14),
          expandedCrossAxisAlignment: CrossAxisAlignment.start,
          expandedAlignment: Alignment.centerLeft,
          children: [
            Text('Estimación del sistema para cada nivel', style: nota),
            const SizedBox(height: 12),
            for (var k = 0; k < clases.length; k++) ...[
              Row(children: [
                SizedBox(width: 62, child: Text(estiloPorCategoria[clases[k]]!.corto, style: TextStyle(color: ColoresMaterna.tinta))),
                Expanded(
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(8),
                    child: LinearProgressIndicator(
                      value: probabilidades[k],
                      minHeight: 9,
                      backgroundColor: ColoresMaterna.fondoBarras,
                      color: estiloPorCategoria[clases[k]]!.barra,
                    ),
                  ),
                ),
                SizedBox(
                  width: 52,
                  child: Text(_pct(probabilidades[k]),
                      textAlign: TextAlign.right, style: TextStyle(fontWeight: FontWeight.w700, color: ColoresMaterna.tinta)),
                ),
              ]),
              const SizedBox(height: 10),
            ],
            if (evaluacion.origen != 'modelo_ml' && estimado != evaluacion.clase)
              Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Text(
                    'El nivel lo decidió un signo crítico o de alarma. Sin ese signo, la estimación sería ${clases[estimado]}.',
                    key: const Key('detalle-estimacion'),
                    style: nota),
              ),
          ],
        ),
      ),
    );
  }
}

/// Los datos que más pesan, como píldoras: edad, semanas, presión y área.
class _DatosClave extends StatelessWidget {
  const _DatosClave(this.registro);

  final Map<String, dynamic> registro;

  @override
  Widget build(BuildContext context) {
    String? n(String clave, String formato) {
      final v = registro[clave];
      return v is num ? formato.replaceFirst('#', v.round().toString()) : null;
    }

    final datos = [
      n('edad', 'Edad #'),
      n('semanas_gestacion', '# sem'),
      n('pas_mmhg', 'PAS #'),
      n('pad_mmhg', 'PAD #'),
      if (registro['area_residencia'] is String) registro['area_residencia'] == 'Cabecera' ? 'Cabecera municipal' : registro['area_residencia'] as String,
    ].whereType<String>();
    return Wrap(key: const Key('datos-clave'), spacing: 8, runSpacing: 8, children: [for (final d in datos) ChipDato(d)]);
  }
}

class _OtrasAlertas extends StatelessWidget {
  const _OtrasAlertas(this.alertas);

  final List<Alerta3280> alertas;

  @override
  Widget build(BuildContext context) => Card(
        key: const Key('otras-alertas'),
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('Alertas de la ruta 3280', style: TextStyle(fontWeight: FontWeight.w800, color: ColoresMaterna.tinta)),
            const SizedBox(height: 4),
            Text('No cambian el nivel de riesgo.', style: TextStyle(color: ColoresMaterna.tintaSuave, fontSize: 13)),
            for (final a in alertas)
              Padding(
                padding: const EdgeInsets.only(top: 10),
                child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Icon(a.severidad == 'atencion' ? Icons.report_rounded : Icons.event_note_rounded,
                      size: 20, color: ColoresMaterna.ciruela900),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text.rich(TextSpan(children: [
                      TextSpan(text: a.mensaje),
                      if (!a.verificada)
                        TextSpan(text: '  (corte por validar)', style: TextStyle(color: ColoresMaterna.tintaSuave, fontSize: 12)),
                    ])),
                  ),
                ]),
              ),
          ]),
        ),
      );
}

/// Conducta sugerida en el aviso del color del nivel.
class _Conducta extends StatelessWidget {
  const _Conducta({required this.estilo, required this.pasos});

  final EstiloRiesgo estilo;
  final List<String> pasos;

  @override
  Widget build(BuildContext context) => Container(
        key: const Key('conducta'),
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(color: estilo.fondo, borderRadius: BorderRadius.circular(18)),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Conducta sugerida', style: TextStyle(fontWeight: FontWeight.w800, color: estilo.tinta)),
          const SizedBox(height: 2),
          Text('Criterio pendiente de validación clínica',
              key: const Key('conducta-por-validar'), style: TextStyle(color: estilo.tinta.withValues(alpha: .8), fontSize: 12)),
          for (final (i, paso) in pasos.indexed)
            Padding(
              padding: const EdgeInsets.only(top: 10),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                CircleAvatar(
                  radius: 11,
                  backgroundColor: ColoresMaterna.tarjeta.withValues(alpha: .75),
                  child: Text('${i + 1}', style: TextStyle(fontSize: 12, color: estilo.tinta, fontWeight: FontWeight.w700)),
                ),
                const SizedBox(width: 10),
                Expanded(child: Text(paso, style: TextStyle(height: 1.4, color: estilo.tinta))),
              ]),
            ),
        ]),
      );
}

/// Aviso con el fondo y el texto de un nivel (p. ej. ámbar para un dato faltante).
class _Aviso extends StatelessWidget {
  const _Aviso({required this.estilo, required this.icono, required this.texto});

  final EstiloRiesgo estilo;
  final IconData icono;
  final String texto;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(color: estilo.fondo, borderRadius: BorderRadius.circular(16)),
        child: Row(children: [
          Icon(icono, color: estilo.tinta),
          const SizedBox(width: 10),
          Expanded(child: Text(texto, style: TextStyle(color: estilo.tinta))),
        ]),
      );
}
