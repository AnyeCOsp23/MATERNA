/// Pestaña «Mapa y visitas»: dónde están las gestantes de esta cuenta y a quién visitar primero.
///
/// Mapa de concentración (sin internet, solo límites y lugares) y lista de visitas pendientes, por prioridad
/// (riesgo y último contacto) o por recorrido (lo más cercano primero dentro de cada nivel). Cada visita se marca
/// como «Visitada» o «No la encontramos». La distancia a la cabecera es solo una referencia de apoyo.
library;

import 'package:flutter/material.dart';

import '../../datos/base_local.dart';
import '../../datos/ubicaciones.dart';
import '../../motor/geografia.dart';
import '../../motor/recursos.dart';
import '../../motor/visitas.dart';
import '../tema/tema_materna.dart';
import '../widgets/barra_flotante.dart';
import '../widgets/encabezado.dart';
import '../widgets/iconos_trazo.dart';
import '../widgets/mapa_materna.dart';
import 'pantalla_historial.dart' show fechaLegible;

String kmLegible(double km) => km < 10 ? km.toStringAsFixed(1).replaceAll('.', ',') : km.round().toString();

String haceCuanto(DateTime fecha, {DateTime? ahora}) {
  final dias = (ahora ?? DateTime.now()).difference(fecha).inDays;
  return dias <= 0 ? 'hoy' : dias == 1 ? 'hace 1 día' : 'hace $dias días';
}

class PantallaVisitas extends StatefulWidget {
  const PantallaVisitas({super.key, required this.recursos, required this.base, required this.perfil, required this.cambios});

  final RecursosMaterna recursos;
  final BaseLocal base;
  final Perfil perfil;

  /// Aumenta cuando se guarda una evaluación o una visita: la pantalla se recarga sola.
  final ValueNotifier<int> cambios;

  @override
  State<PantallaVisitas> createState() => _EstadoVisitas();
}

class _EstadoVisitas extends State<PantallaVisitas> {
  int? _clase;
  var _recorrido = false;
  late Future<List<RegistroUbicacion>> _datos = _cargar();

  @override
  void initState() {
    super.initState();
    widget.cambios.addListener(_recargar);
  }

  @override
  void dispose() {
    widget.cambios.removeListener(_recargar);
    super.dispose();
  }

  Future<List<RegistroUbicacion>> _cargar() => widget.base.listarUbicaciones(perfil: widget.perfil);

  void _recargar() => setState(() {
        _datos = _cargar();
      });

  Future<void> _marcar(Visita v, EstadoVisita estado) async {
    await widget.base.marcarVisita(v.ubicacion.id, estado, perfil: widget.perfil);
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(
          content: Text(estado == EstadoVisita.visitada
              ? 'Visita registrada: sale de la lista de pendientes.'
              : 'Marcada como «no la encontramos»: sigue en la lista para intentarlo de nuevo.')));
    widget.cambios.value++;
  }

  Widget _visita(Visita v, int numero, Geografia geo) {
    final u = v.ubicacion;
    final estilo = estiloPorCategoria[widget.recursos.clasificador.clases[u.clase]]!;
    final detalles = [
      if (u.idSeudonimo != null) codigoGestante(u.idSeudonimo),
      'Último contacto ${haceCuanto(u.ultimoContacto)} (${fechaLegible(u.ultimoContacto).split(' ').first})',
      if (v.kmCabecera != null) 'A ${kmLegible(v.kmCabecera!)} km de la ${v.cabecera!.replaceFirst('Cabecera', 'cabecera')} (aprox.)',
      if (_recorrido && v.kmDesdeAnterior != null) '${kmLegible(v.kmDesdeAnterior!)} km desde la anterior',
      if (u.referenciaRol != null) 'Referencia: ${u.referenciaRol}${u.referenciaApodo == null ? '' : ' · ${u.referenciaApodo}'}',
    ];
    return Card(
      key: Key('visita-${u.id}'),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 12, 12, 8),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            CircleAvatar(radius: 13, backgroundColor: estilo.fondo,
                child: Text('$numero', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w800, color: estilo.tinta))),
            const SizedBox(width: 10),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(v.lugar, style: TextStyle(fontWeight: FontWeight.w800, color: ColoresMaterna.tinta, fontSize: 15)),
                Text(v.municipio, style: TextStyle(color: ColoresMaterna.tintaSuave, fontSize: 12.5)),
                const SizedBox(height: 4),
                Text(detalles.join('\n'), style: TextStyle(color: ColoresMaterna.tintaSuave, fontSize: 12.5, height: 1.4)),
              ]),
            ),
            const SizedBox(width: 8),
            Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
              EtiquetaNivel(estilo),
              if (u.estado == EstadoVisita.sinLocalizar) ...[
                const SizedBox(height: 6),
                Text('Sin localizar', key: Key('sin-localizar-${u.id}'),
                    style: TextStyle(color: estiloPorCategoria['Alto Riesgo']!.tinta, fontSize: 12, fontWeight: FontWeight.w700)),
              ],
            ]),
          ]),
          // Wrap y no Row: en un celular angosto o con letra grande, el segundo botón baja de línea
          Wrap(alignment: WrapAlignment.end, spacing: 4, children: [
            TextButton(
              key: Key('no-encontrada-${u.id}'),
              style: TextButton.styleFrom(minimumSize: const Size(0, 40)),
              onPressed: () => _marcar(v, EstadoVisita.sinLocalizar),
              child: const Text('No la encontramos'),
            ),
            TextButton.icon(
              key: Key('visitada-${u.id}'),
              style: TextButton.styleFrom(minimumSize: const Size(0, 40)),
              onPressed: () => _marcar(v, EstadoVisita.visitada),
              icon: const Icon(Icons.check_rounded, size: 18),
              label: const Text('Visitada'),
            ),
          ]),
        ]),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final geo = widget.recursos.geografia;
    return SafeArea(
      bottom: false,
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 760),
          child: FutureBuilder<List<RegistroUbicacion>>(
            future: _datos,
            builder: (context, estado) {
              final todas = estado.data ?? const <RegistroUbicacion>[];
              final elegidas = _clase == null ? todas : todas.where((u) => u.clase == _clase).toList();
              final inicio = geo?.cabecera(geo.porNombre(widget.perfil.municipio)?.codigo ?? '')?.posicion;
              final visitas = geo == null
                  ? const <Visita>[]
                  : _recorrido
                      ? visitasPorRecorrido(elegidas, geo, inicio: inicio)
                      : visitasPorPrioridad(elegidas, geo);
              return ListView(padding: const EdgeInsets.fromLTRB(16, 8, 16, BarraFlotante.espacioInferior), children: [
                const EncabezadoMaterna(etiqueta: 'En territorio'),
                const SizedBox(height: 14),
                TituloConIcono(
                  icono: IconoDeTrazo(IconoTrazo.mapa, color: ColoresMaterna.ciruela900, tamano: 26),
                  titulo: 'Mapa y visitas',
                  subtitulo: 'Dónde están sus gestantes y a quién visitar primero',
                ),
                const SizedBox(height: 14),
                if (geo == null)
                  const Text('El mapa no está disponible en este dispositivo.')
                else ...[
                  FiltroNivel(key: const Key('filtro-visitas'), seleccion: _clase, alCambiar: (c) => setState(() => _clase = c)),
                  const SizedBox(height: 12),
                  if (estado.connectionState != ConnectionState.done)
                    const Center(child: Padding(padding: EdgeInsets.all(24), child: CircularProgressIndicator()))
                  else if (todas.isEmpty)
                    Padding(
                      padding: const EdgeInsets.all(24),
                      child: Text(
                          'Aún no hay gestantes con ubicación. Regístrela en el paso «Contexto y atención» del triaje '
                          '(«Ubicación para la visita») o con la carga de la IPS.',
                          key: const Key('visitas-vacio'), textAlign: TextAlign.center, style: TextStyle(color: ColoresMaterna.tintaSuave)),
                    )
                  else ...[
                    MapaMaterna(key: ValueKey('mapa-visitas-$_clase-${todas.length}'), geografia: geo,
                        puntos: puntosDelMapa(elegidas, geo)),
                    const SizedBox(height: 8),
                    const LeyendaMapa(),
                    const SizedBox(height: 4),
                    Text('Solo límites de municipios y lugares; los puntos de ranchería, vereda o resguardo son de prueba. '
                        'Funciona sin internet.', style: TextStyle(color: ColoresMaterna.tintaSuave, fontSize: 12)),
                    const SizedBox(height: 16),
                    SegmentedButton<bool>(
                      key: const Key('orden-visitas'),
                      segments: const [
                        ButtonSegment(value: false, label: Text('Por prioridad'), icon: Icon(Icons.priority_high_rounded)),
                        ButtonSegment(value: true, label: Text('Recorrido'), icon: Icon(Icons.route_rounded)),
                      ],
                      selected: {_recorrido},
                      onSelectionChanged: (s) => setState(() => _recorrido = s.first),
                    ),
                    const SizedBox(height: 6),
                    Text(
                        _recorrido
                            ? 'Primero las de Alto Riesgo; dentro de cada nivel, la más cercana a la anterior (en línea recta).'
                            : 'Primero las de Alto Riesgo; dentro de cada nivel, la que lleva más tiempo sin contacto.',
                        style: TextStyle(color: ColoresMaterna.tintaSuave, fontSize: 12.5)),
                    const SizedBox(height: 10),
                    Text('${visitas.length} visita(s) pendiente(s)', key: const Key('visitas-total'),
                        style: TextStyle(color: ColoresMaterna.tintaSuave)),
                    const SizedBox(height: 8),
                    for (final (i, v) in visitas.indexed) ...[_visita(v, i + 1, geo), const SizedBox(height: 8)],
                    Text('La distancia a la cabecera es una referencia aproximada de la IPS más cercana: no cambia el resultado.',
                        style: TextStyle(color: ColoresMaterna.tintaSuave, fontSize: 12)),
                  ],
                ],
              ]);
            },
          ),
        ),
      ),
    );
  }
}
