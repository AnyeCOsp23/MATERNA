/// Pestaña 3: historial de las evaluaciones guardadas en el dispositivo (base local SQLite).
///
/// Filtros por nivel de riesgo y por fecha, búsqueda por seudónimo o por documento (se calcula su seudónimo con la
/// clave de la IPS; el documento no se guarda) y sincronización SIMULADA: no hay servidor, así que solo se marcan
/// como sincronizadas.
library;

import 'package:flutter/material.dart';

import '../../datos/base_local.dart';
import '../../datos/seudonimizacion.dart';
import '../../motor/recursos.dart';
import '../tema/tema_materna.dart';
import '../widgets/barra_flotante.dart';
import 'pantalla_resultado.dart';
import 'pantalla_triaje.dart' show atiende;

const origenLegible = {'regla_clinica': 'regla clínica', 'signo_alarma_3280': 'signo de alarma', 'modelo_ml': 'modelo'};

String fechaLegible(DateTime f) {
  String dos(int n) => n.toString().padLeft(2, '0');
  return '${dos(f.day)}/${dos(f.month)}/${f.year} ${dos(f.hour)}:${dos(f.minute)}';
}

class PantallaHistorial extends StatefulWidget {
  const PantallaHistorial({super.key, required this.recursos, required this.base, required this.cambios});

  final RecursosMaterna recursos;
  final BaseLocal base;

  /// Aumenta cada vez que se guarda una evaluación: el historial se recarga solo.
  final ValueNotifier<int> cambios;

  @override
  State<PantallaHistorial> createState() => _EstadoHistorial();
}

class _EstadoHistorial extends State<PantallaHistorial> {
  int? _clase;
  int? _dias;
  final _busqueda = TextEditingController();
  var _porDocumento = false;
  String? _avisoBusqueda;
  late Future<(List<RegistroEvaluacion>, int)> _datos = _cargar();

  @override
  void initState() {
    super.initState();
    widget.cambios.addListener(_recargar);
  }

  @override
  void dispose() {
    widget.cambios.removeListener(_recargar);
    _busqueda.dispose();
    super.dispose();
  }

  /// Seudónimo a buscar: el texto tal cual o, por documento, el HMAC del documento con la clave de la IPS.
  Future<String?> _seudonimoBuscado() async {
    _avisoBusqueda = null;
    final texto = _busqueda.text.trim();
    if (!_porDocumento || texto.isEmpty) return texto;
    final clave = await widget.base.claveIps();
    if (clave == null) {
      _avisoBusqueda = 'Configure primero la clave de la IPS en «Carga IPS».';
      return null;
    }
    final m = RegExp(r'^([A-Za-z]{1,3})[\s.:-]*(\S.*)$').firstMatch(texto);
    if (m == null || normalizarDocumento(m[1]!, m[2]!).$2.isEmpty) {
      _avisoBusqueda = 'Escriba el tipo y el número del documento, p. ej. CC 1065432.';
      return null;
    }
    return seudonimizar(m[1]!, m[2]!, clave);
  }

  Future<(List<RegistroEvaluacion>, int)> _cargar() async {
    final desde = _dias == null ? null : DateTime.now().subtract(Duration(days: _dias!));
    final seudonimo = await _seudonimoBuscado();
    final lista = seudonimo == null && _porDocumento
        ? <RegistroEvaluacion>[]
        : await widget.base.listar(clase: _clase, desde: desde, seudonimo: seudonimo);
    return (lista, await widget.base.pendientesDeSincronizar());
  }

  // llaves: con «=>» el setState devolvería el Future de la asignación, y Flutter lo rechaza
  void _recargar() => setState(() {
        _datos = _cargar();
      });

  Future<void> _sincronizar() async {
    final n = await widget.base.marcarSincronizadas();
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text('$n evaluación(es) marcadas como sincronizadas. Simulación: no se envía ningún dato.')));
    _recargar();
  }

  void _abrir(RegistroEvaluacion r) {
    Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => PantallaResultado(
        recursos: widget.recursos,
        evaluacion: widget.recursos.evaluar(r.registro),
        soloLectura: true,
        nota: 'Evaluación del ${fechaLegible(r.fecha)} · ${atiende[r.atendidoPor] ?? r.atendidoPor} · ${r.ips}'
            '${r.versionModelo == widget.recursos.clasificador.version ? '' : ' · guardada con el modelo ${r.versionModelo}, recalculada con el ${widget.recursos.clasificador.version}'}',
      ),
    ));
  }

  Widget _filtros() => Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        SizedBox(
          width: double.infinity,
          child: SegmentedButton<int>(
            key: const Key('filtro-riesgo'),
            segments: const [
              ButtonSegment(value: -1, label: Text('Todas')),
              ButtonSegment(value: 2, label: Text('Rojo')),
              ButtonSegment(value: 1, label: Text('Ámbar')),
              ButtonSegment(value: 0, label: Text('Verde')),
            ],
            selected: {_clase ?? -1},
            showSelectedIcon: false,
            onSelectionChanged: (s) {
              _clase = s.first == -1 ? null : s.first;
              _recargar();
            },
          ),
        ),
        const SizedBox(height: 10),
        Wrap(spacing: 8, runSpacing: 8, children: [
          for (final (dias, texto) in [(null, 'Todo'), (1, 'Hoy'), (7, '7 días'), (30, '30 días')])
            ChoiceChip(
              key: Key('filtro-dias-${dias ?? 'todo'}'),
              label: Text(texto),
              selected: _dias == dias,
              onSelected: (_) {
                _dias = dias;
                _recargar();
              },
            ),
        ]),
        const SizedBox(height: 10),
        Wrap(spacing: 8, children: [
          for (final (documento, texto) in [(false, 'Por seudónimo'), (true, 'Por documento')])
            ChoiceChip(
              key: Key(documento ? 'buscar-por-documento' : 'buscar-por-seudonimo'),
              label: Text(texto),
              selected: _porDocumento == documento,
              onSelected: (_) {
                _porDocumento = documento;
                if (_busqueda.text.trim().isNotEmpty) _recargar();
                setState(() {});
              },
            ),
        ]),
        const SizedBox(height: 8),
        TextField(
          key: const Key('buscar-seudonimo'),
          controller: _busqueda,
          onSubmitted: (_) => _recargar(),
          decoration: InputDecoration(
            prefixIcon: const Icon(Icons.search_rounded),
            hintText: _porDocumento ? 'Tipo y número, p. ej. CC 1065432 (no se guarda)' : 'Primeros caracteres del seudónimo',
            suffixIcon: IconButton(icon: const Icon(Icons.arrow_forward_rounded), onPressed: _recargar, tooltip: 'Buscar'),
          ),
        ),
        if (_avisoBusqueda != null)
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Text(_avisoBusqueda!, key: const Key('aviso-busqueda'), style: const TextStyle(color: Color(0xFF6B1832))),
          ),
      ]);

  Widget _fila(RegistroEvaluacion r) {
    final estilo = estiloPorCategoria[widget.recursos.clasificador.clases[r.clase]]!;
    return Card(
      child: ListTile(
        key: Key('evaluacion-${r.id}'),
        onTap: () => _abrir(r),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
        leading: CircleAvatar(backgroundColor: estilo.fondo, child: Icon(estilo.icono, color: estilo.tinta)),
        title: Text('${estilo.semaforo.toUpperCase()} · ${estilo.titulo}', style: const TextStyle(fontWeight: FontWeight.w700)),
        subtitle: Text(
          '${fechaLegible(r.fecha)} · ${atiende[r.atendidoPor] ?? r.atendidoPor} · ${origenLegible[r.origen] ?? r.origen}'
          '${r.alertas.isEmpty ? '' : ' · ${r.alertas.length} alerta(s)'}'
          '${r.idCarga == null ? '' : ' · carga IPS'}'
          '${r.idSeudonimo == null ? '' : '\nSeudónimo ${r.idSeudonimo!.substring(0, 12)}…'}',
        ),
        trailing: Icon(r.sincronizado ? Icons.cloud_done_outlined : Icons.cloud_upload_outlined,
            color: ColoresMaterna.tintaSuave, semanticLabel: r.sincronizado ? 'Sincronizada' : 'Pendiente'),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => SafeArea(
        bottom: false,
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 760),
            child: FutureBuilder<(List<RegistroEvaluacion>, int)>(
              future: _datos,
              builder: (context, estado) {
                final (lista, pendientes) = estado.data ?? (<RegistroEvaluacion>[], 0);
                return ListView(padding: const EdgeInsets.fromLTRB(16, 16, 16, BarraFlotante.espacioInferior), children: [
                  Row(children: [
                    Expanded(
                      child: Text('Historial local',
                          style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800)),
                    ),
                    FilledButton.tonalIcon(
                      key: const Key('sincronizar'),
                      // el tema da a los botones todo el ancho; dentro de una fila ese ancho sería infinito
                      style: FilledButton.styleFrom(
                        minimumSize: const Size(0, 44),
                        backgroundColor: ColoresMaterna.ciruela100,
                        foregroundColor: ColoresMaterna.ciruela900,
                      ),
                      onPressed: pendientes == 0 ? null : _sincronizar,
                      icon: const Icon(Icons.sync_rounded),
                      label: Text('Sincronizar ($pendientes)'),
                    ),
                  ]),
                  const SizedBox(height: 4),
                  const Text('Evaluaciones guardadas en este dispositivo. La sincronización es una simulación.',
                      style: TextStyle(color: ColoresMaterna.tintaSuave)),
                  const SizedBox(height: 14),
                  _filtros(),
                  const SizedBox(height: 14),
                  if (estado.connectionState != ConnectionState.done)
                    const Center(child: Padding(padding: EdgeInsets.all(24), child: CircularProgressIndicator()))
                  else if (lista.isEmpty)
                    const Padding(
                      padding: EdgeInsets.all(28),
                      child: Text('No hay evaluaciones con estos filtros.',
                          key: Key('historial-vacio'), textAlign: TextAlign.center, style: TextStyle(color: ColoresMaterna.tintaSuave)),
                    )
                  else ...[
                    Text('${lista.length} evaluación(es)', key: const Key('historial-total'),
                        style: const TextStyle(color: ColoresMaterna.tintaSuave)),
                    const SizedBox(height: 8),
                    for (final r in lista) ...[_fila(r), const SizedBox(height: 8)],
                  ],
                ]);
              },
            ),
          ),
        ),
      );
}
