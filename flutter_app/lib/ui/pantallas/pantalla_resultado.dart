/// Pantalla 2: resultado del triaje.
///
/// Orden deliberado: primero las alertas URGENTES de la ruta 3280 que no cambian el semáforo (p. ej. exposición
/// a violencias, que tiene su propia ruta), luego el semáforo con el motivo de la decisión (regla clínica, signo
/// de alarma obstétrico o modelo), las probabilidades del modelo, las demás alertas y el protocolo.
/// Los signos de alarma obstétricos (sangrado, visión borrosa…) elevan el semáforo a ROJO: un verde o un ámbar
/// nunca acompañan a una urgencia obstétrica.
library;

import 'package:flutter/material.dart';

import '../../motor/catalogo_3280.dart';
import '../../motor/recursos.dart';
import '../tema/tema_materna.dart';

String _pct(double p) => '${(p * 100).toStringAsFixed(1).replaceAll('.', ',')} %';

class PantallaResultado extends StatelessWidget {
  const PantallaResultado({super.key, required this.recursos, required this.evaluacion});

  final RecursosMaterna recursos;
  final Evaluacion evaluacion;

  @override
  Widget build(BuildContext context) {
    final triaje = evaluacion.triaje;
    final categoria = recursos.clasificador.clases[evaluacion.clase];
    final estilo = estiloPorCategoria[categoria]!;
    final urgentes = evaluacion.urgentesSinEscalar;
    return Scaffold(
      appBar: AppBar(title: const Text('Resultado del triaje')),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 760),
            child: ListView(padding: const EdgeInsets.fromLTRB(16, 8, 16, 32), children: [
              if (urgentes.isNotEmpty) ...[
                _AlertasUrgentes(urgentes, contradiceAlModelo: categoria != 'Alto Riesgo'),
                const SizedBox(height: 14),
              ],
              _Semaforo(estilo: estilo, evaluacion: evaluacion, recursos: recursos),
              if (evaluacion.imputadas.isNotEmpty) ...[
                const SizedBox(height: 10),
                _Nota(
                  icono: Icons.info_outline_rounded,
                  texto: 'Sin dato de ${evaluacion.imputadas.map((v) => v == 'fcf_bpm' ? 'FCF' : 'glucosa').join(' y ')}: '
                      'el modelo lo completó con la mediana por área y trimestre. Interpretar con cautela.',
                ),
              ],
              const SizedBox(height: 14),
              _Probabilidades(triaje.probabilidades, recursos.clasificador.clases),
              if (evaluacion.noUrgentes.isNotEmpty) ...[
                const SizedBox(height: 14),
                _OtrasAlertas(evaluacion.noUrgentes),
              ],
              const SizedBox(height: 14),
              _Protocolo(recursos.protocolo(categoria), recursos.aviso),
              const SizedBox(height: 22),
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
            ]),
          ),
        ),
      ),
    );
  }
}

class _AlertasUrgentes extends StatelessWidget {
  const _AlertasUrgentes(this.alertas, {required this.contradiceAlModelo});

  final List<Alerta3280> alertas;

  /// El modelo no dio Alto Riesgo: hay que decir explícitamente que la alerta prevalece.
  final bool contradiceAlModelo;

  @override
  Widget build(BuildContext context) => Container(
        key: const Key('alertas-urgentes'),
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(color: ColoresMaterna.ciruela900, borderRadius: BorderRadius.circular(20)),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Row(children: [
            Icon(Icons.priority_high_rounded, color: Colors.white),
            SizedBox(width: 8),
            Expanded(
              child: Text('Signos de alarma: valoración médica inmediata',
                  style: TextStyle(color: Colors.white, fontWeight: FontWeight.w800, fontSize: 16)),
            ),
          ]),
          if (contradiceAlModelo)
            const Padding(
              padding: EdgeInsets.only(top: 6),
              child: Text('Aunque el modelo no clasifica Alto Riesgo, estas alertas de la ruta prevalecen.',
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

class _Semaforo extends StatelessWidget {
  const _Semaforo({required this.estilo, required this.evaluacion, required this.recursos});

  final EstiloRiesgo estilo;
  final Evaluacion evaluacion;
  final RecursosMaterna recursos;

  @override
  Widget build(BuildContext context) {
    final triaje = evaluacion.triaje;
    final motivos = switch (evaluacion.origen) {
      'regla_clinica' => [for (final id in triaje.reglasActivadas) recursos.mensajeRegla(id)],
      'signo_alarma_3280' => [for (final a in evaluacion.alertasQueEscalan) a.etiqueta],
      _ => <String>[],
    };
    final titulo = switch (evaluacion.origen) {
      'regla_clinica' => 'Decidido por regla clínica (GPC Minsalud 2013):',
      'signo_alarma_3280' => 'Decidido por signos de alarma de la ruta (Res. 3280):',
      _ => 'Decidido por el modelo (Random Forest).',
    };
    return Container(
      key: const Key('semaforo'),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(color: estilo.fondo, borderRadius: BorderRadius.circular(22)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(estilo.icono, color: estilo.tinta, size: 40),
          const SizedBox(width: 12),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('${estilo.semaforo.toUpperCase()} · ${estilo.titulo}',
                  style: TextStyle(color: estilo.tinta, fontWeight: FontWeight.w800, fontSize: 22)),
              Text(estilo.subtitulo, style: TextStyle(color: estilo.tinta)),
            ]),
          ),
        ]),
        const SizedBox(height: 14),
        Text(titulo, style: TextStyle(color: estilo.tinta, fontWeight: FontWeight.w700)),
        for (final m in motivos) Text('•  $m', style: TextStyle(color: estilo.tinta)),
        if (evaluacion.origen == 'regla_clinica' && evaluacion.signosAlarma.isNotEmpty)
          Text('•  Además, signos de alarma: ${evaluacion.alertasQueEscalan.map((a) => a.etiqueta.toLowerCase()).join(', ')}',
              style: TextStyle(color: estilo.tinta)),
        if (evaluacion.origen != 'modelo_ml' && triaje.claseModelo != evaluacion.clase)
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Text('El modelo por sí solo habría dicho ${recursos.clasificador.clases[triaje.claseModelo]}.',
                style: TextStyle(color: estilo.tinta, fontSize: 13)),
          ),
      ]),
    );
  }
}

class _Probabilidades extends StatelessWidget {
  const _Probabilidades(this.probabilidades, this.clases);

  final List<double> probabilidades;
  final List<String> clases;

  @override
  Widget build(BuildContext context) => Card(
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('Probabilidad del modelo', style: TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(height: 12),
            for (var k = clases.length - 1; k >= 0; k--) ...[
              Row(children: [
                SizedBox(width: 110, child: Text(clases[k])),
                Expanded(
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(8),
                    child: LinearProgressIndicator(
                      value: probabilidades[k],
                      minHeight: 12,
                      backgroundColor: ColoresMaterna.campo,
                      color: estiloPorCategoria[clases[k]]!.tinta,
                    ),
                  ),
                ),
                SizedBox(width: 70, child: Text(_pct(probabilidades[k]), textAlign: TextAlign.right)),
              ]),
              const SizedBox(height: 8),
            ],
          ]),
        ),
      );
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
            const Text('Alertas de la ruta 3280', style: TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(height: 4),
            const Text('No cambian la clasificación del modelo.', style: TextStyle(color: ColoresMaterna.tintaSuave, fontSize: 13)),
            for (final a in alertas)
              Padding(
                padding: const EdgeInsets.only(top: 10),
                child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Icon(a.severidad == 'atencion' ? Icons.report_rounded : Icons.event_note_rounded,
                      size: 20, color: ColoresMaterna.ciruela700),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text.rich(TextSpan(children: [
                      TextSpan(text: a.mensaje),
                      if (!a.verificada)
                        const TextSpan(text: '  (corte por validar)', style: TextStyle(color: ColoresMaterna.tintaSuave, fontSize: 12)),
                    ])),
                  ),
                ]),
              ),
          ]),
        ),
      );
}

class _Protocolo extends StatelessWidget {
  const _Protocolo(this.pasos, this.aviso);

  final List<String> pasos;
  final String aviso;

  @override
  Widget build(BuildContext context) => Card(
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('Qué hacer', style: TextStyle(fontWeight: FontWeight.w700)),
            for (final (i, paso) in pasos.indexed)
              Padding(
                padding: const EdgeInsets.only(top: 10),
                child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  CircleAvatar(
                    radius: 12,
                    backgroundColor: ColoresMaterna.ciruela100,
                    child: Text('${i + 1}', style: const TextStyle(fontSize: 12, color: ColoresMaterna.ciruela900)),
                  ),
                  const SizedBox(width: 10),
                  Expanded(child: Text(paso, style: const TextStyle(height: 1.4))),
                ]),
              ),
            const SizedBox(height: 12),
            Text(aviso, style: const TextStyle(color: ColoresMaterna.tintaSuave, fontSize: 12)),
          ]),
        ),
      );
}

class _Nota extends StatelessWidget {
  const _Nota({required this.icono, required this.texto});

  final IconData icono;
  final String texto;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(color: const Color(0xFFF2E88F).withValues(alpha: .45), borderRadius: BorderRadius.circular(16)),
        child: Row(children: [
          Icon(icono, color: const Color(0xFF5A4F0E)),
          const SizedBox(width: 10),
          Expanded(child: Text(texto, style: const TextStyle(color: Color(0xFF5A4F0E)))),
        ]),
      );
}
