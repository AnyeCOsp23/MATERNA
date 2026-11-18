/// Pestaña 3: historial de las evaluaciones guardadas en el dispositivo (base local SQLite).
///
/// Filtros por nivel de riesgo y por fecha, búsqueda por código o por documento (se calcula su seudónimo con la
/// clave de la IPS; el documento no se guarda) y sincronización SIMULADA: no hay servidor, así que solo se marcan
/// como sincronizadas.
library;

import 'package:flutter/material.dart';

import '../../datos/base_local.dart';
import '../../datos/seudonimizacion.dart';
import '../../motor/recursos.dart';
import '../tema/tema_materna.dart';
import '../widgets/barra_flotante.dart';
import '../widgets/encabezado.dart';
import '../widgets/iconos_trazo.dart';
import 'pantalla_resultado.dart';
import 'pantalla_triaje.dart' show atiende;

/// Por qué quedó en ese nivel, en pocas palabras. Un Bajo Riesgo no «tiene factores de riesgo»: no tuvo signos.
String origenLegible(String origen, int clase) => switch (origen) {
      'regla_clinica' => 'signo crítico',
      'signo_alarma_3280' => 'signo de alarma',
      _ => clase == 0 ? 'sin signos de alarma' : 'factores de riesgo',
    };

String fechaLegible(DateTime f) {
  String dos(int n) => n.toString().padLeft(2, '0');
  return '${dos(f.day)}/${dos(f.month)}/${f.year} ${dos(f.hour)}:${dos(f.minute)}';
}

class PantallaHistorial extends StatefulWidget {
  const PantallaHistorial({super.key, required this.recursos, required this.base, required this.cambios, this.idUsuario});

  final RecursosMaterna recursos;
  final BaseLocal base;

  /// Cuenta que inició sesión: solo se muestran sus evaluaciones.
  final int? idUsuario;

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

  /// Final del código escrito en «Por código» ('88' en '14A2-88'); se filtra después de consultar la base.
  String _finalCodigo = '';

  /// Inicio del seudónimo a buscar: por código, lo que se escribió ('14A2-88' -> '14a2'); por documento, el HMAC
  /// del documento con la clave de la IPS. null = la búsqueda no es válida (lista vacía con aviso).
  Future<String?> _seudonimoBuscado() async {
    _avisoBusqueda = null;
    _finalCodigo = '';
    final texto = _busqueda.text.trim();
    if (texto.isEmpty) return texto;
    if (!_porDocumento) {
      final codigo = leerCodigo(texto);
      if (codigo == null) {
        _avisoBusqueda = 'Escriba el código como aparece en la lista, p. ej. 14A2-88. Para buscar por cédula, use «Por documento».';
        return null;
      }
      _finalCodigo = codigo.$2;
      return codigo.$1;
    }
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
    final lista = seudonimo == null
        ? <RegistroEvaluacion>[]
        : [
            for (final r in await widget.base.listar(idUsuario: widget.idUsuario, clase: _clase, desde: desde, seudonimo: seudonimo))
              if (_finalCodigo.isEmpty || (r.idSeudonimo ?? '').endsWith(_finalCodigo)) r,
          ];
    return (lista, await widget.base.pendientesDeSincronizar(idUsuario: widget.idUsuario));
  }

  // llaves: con «=>» el setState devolvería el Future de la asignación, y Flutter lo rechaza
  void _recargar() => setState(() {
        _datos = _cargar();
      });

  Future<void> _sincronizar() async {
    final n = await widget.base.marcarSincronizadas(idUsuario: widget.idUsuario);
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
            '${r.versionModelo == widget.recursos.clasificador.version ? '' : ' · recalculada con la versión actual de MATERNA'}',
      ),
    ));
  }

  Widget _filtros() => Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        FiltroNivel(
          key: const Key('filtro-riesgo'),
          seleccion: _clase,
          alCambiar: (clase) {
            _clase = clase;
            _recargar();
          },
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
          for (final (documento, texto) in [(false, 'Por código'), (true, 'Por documento')])
            ChoiceChip(
              key: Key(documento ? 'buscar-por-documento' : 'buscar-por-codigo'),
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
            hintText: _porDocumento ? 'Tipo y número, p. ej. CC 1065432 (no se guarda)' : 'Código como aparece en la lista, p. ej. 14A2-88',
            suffixIcon: IconButton(icon: const Icon(Icons.arrow_forward_rounded), onPressed: _recargar, tooltip: 'Buscar'),
          ),
        ),
        if (_avisoBusqueda != null)
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Text(_avisoBusqueda!, key: const Key('aviso-busqueda'), style: TextStyle(color: estiloPorCategoria['Alto Riesgo']!.tinta)),
          ),
      ]);

  Widget _fila(RegistroEvaluacion r) {
    final estilo = estiloPorCategoria[widget.recursos.clasificador.clases[r.clase]]!;
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        key: Key('evaluacion-${r.id}'),
        onTap: () => _abrir(r),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Row(children: [
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(edadYSemanas(r.registro, largo: true),
                    style: TextStyle(fontWeight: FontWeight.w800, color: ColoresMaterna.tinta, fontSize: 15)),
                const SizedBox(height: 2),
                Text(
                  '${r.idCarga == null ? 'Triaje individual' : 'Carga IPS'} · ${fechaLegible(r.fecha)}\n'
                  '${atiende[r.atendidoPor] ?? r.atendidoPor} · ${origenLegible(r.origen, r.clase)}'
                  '${r.alertas.isEmpty ? '' : ' · ${r.alertas.length} alerta(s)'}',
                  style: TextStyle(color: ColoresMaterna.tintaSuave, fontSize: 12.5, height: 1.35),
                ),
                if (r.idSeudonimo != null) ...[
                  const SizedBox(height: 4),
                  Text(codigoGestante(r.idSeudonimo),
                      key: Key('codigo-${r.id}'),
                      style: TextStyle(color: ColoresMaterna.tintaSuave, fontSize: 11.5, letterSpacing: .6)),
                ],
              ]),
            ),
            const SizedBox(width: 8),
            EtiquetaNivel(estilo, key: Key('nivel-${r.clase}')),
            const SizedBox(width: 8),
            Icon(r.sincronizado ? Icons.cloud_done_outlined : Icons.cloud_upload_outlined,
                size: 20, color: ColoresMaterna.tintaSuave, semanticLabel: r.sincronizado ? 'Sincronizada' : 'Pendiente'),
          ]),
        ),
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
                return ListView(padding: const EdgeInsets.fromLTRB(16, 8, 16, BarraFlotante.espacioInferior), children: [
                  const EncabezadoMaterna(etiqueta: 'Registro local'),
                  const SizedBox(height: 14),
                  TituloConIcono(
                    icono: IconoDeTrazo(IconoTrazo.baseDatos, color: ColoresMaterna.ciruela900, tamano: 26),
                    titulo: 'Historial local',
                    subtitulo: 'Sus evaluaciones guardadas en este dispositivo',
                  ),
                  const SizedBox(height: 12),
                  // que es una simulación se avisa al tocar el botón y en «Acerca de» › «Uso responsable»
                  Row(mainAxisAlignment: MainAxisAlignment.end, children: [
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
                  const SizedBox(height: 14),
                  _filtros(),
                  const SizedBox(height: 14),
                  if (estado.connectionState != ConnectionState.done)
                    const Center(child: Padding(padding: EdgeInsets.all(24), child: CircularProgressIndicator()))
                  else if (lista.isEmpty)
                    Padding(
                      padding: EdgeInsets.all(28),
                      child: Text('No hay evaluaciones con estos filtros.',
                          key: Key('historial-vacio'), textAlign: TextAlign.center, style: TextStyle(color: ColoresMaterna.tintaSuave)),
                    )
                  else ...[
                    Text('${lista.length} evaluación(es)', key: const Key('historial-total'),
                        style: TextStyle(color: ColoresMaterna.tintaSuave)),
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
