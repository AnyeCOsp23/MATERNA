/// Mapa de concentración de gestantes, 100 % sin internet: solo los límites de los municipios (DANE) y marcadores
/// pequeños por lugar. No hay mapa de calles ni teselas.
///
/// Agrupación dinámica (como en los mapas de navegación): los lugares que en pantalla quedan a menos de
/// [_radioGrupo] píxeles se juntan en un grupo con halo que muestra cuántas gestantes suman; al acercar, los grupos
/// se separan en marcadores individuales (en el zoom máximo, todos van sueltos). El color de cada marcador es el
/// nivel más alto entre sus gestantes (semáforo) y el número, cuántas son. Al tocar un marcador aparece una
/// etiqueta flotante con el lugar, cuántas gestantes y su nivel (en un grupo, con «Acercar»); al tocar otro, la
/// anterior se cierra. El zoom es real (dos dedos, + y −, «Acercar»), con movimiento suave.
///
/// En «Mapa y visitas» puede dibujar además el recorrido sugerido: líneas punteadas desde el punto de partida, en
/// orden, con el número de cada parada (líneas rectas: no son carreteras).
library;

import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../../motor/geografia.dart';
import '../../motor/visitas.dart';
import '../tema/tema_materna.dart';

const _categorias = ['Bajo Riesgo', 'Riesgo Medio', 'Alto Riesgo'];
const _zoomMinimo = 5.0, _zoomMaximo = 14.0;

/// Distancia en pantalla (px) por debajo de la cual dos lugares se agrupan.
const _radioGrupo = 38.0;

LatLng _ll(Coordenada c) => LatLng(c.lat, c.lon);

/// Color del círculo de un nivel: el del semáforo, igual en modo claro y oscuro (el número va en blanco encima).
Color colorNivel(int clase) => estiloPorCategoria[_categorias[clase]]!.degradado.first;

/// Recorrido que se dibuja sobre el mapa: punto de partida y paradas en orden, cada una con su nivel.
class RutaMapa {
  const RutaMapa({required this.inicio, required this.paradas});

  final Coordenada? inicio;
  final List<({String clave, Coordenada posicion, int nivel})> paradas;
}

/// Nombre de un lugar de referencia (p. ej. una cabecera municipal) escrito sobre el mapa.
typedef RotuloMapa = ({Coordenada posicion, String texto});

/// Un marcador del mapa: un lugar suelto o varios lugares cercanos agrupados.
class GrupoMapa {
  GrupoMapa(this.lugares, this.centro);

  final List<PuntoMapa> lugares;
  final LatLng centro;

  String get id => (lugares.map((p) => p.clave).toList()..sort()).join('|');
  bool get esLugar => lugares.length == 1;
  int get total => lugares.fold(0, (s, p) => s + p.total);
  List<int> get conteos => [for (var c = 0; c < 3; c++) lugares.fold(0, (s, p) => s + p.conteos[c])];
  int get visitadas => lugares.fold(0, (s, p) => s + p.visitadas.fold(0, (a, b) => a + b));

  int? nivel({required bool sinVisitadas}) {
    final niveles = [for (final p in lugares) p.nivelMasAlto(sinVisitadas: sinVisitadas)].whereType<int>();
    return niveles.isEmpty ? null : niveles.reduce(math.max);
  }
}

/// Agrupa los lugares que, al [zoom] dado, quedan a menos de [radio] px entre sí. Empieza por los lugares con más
/// gestantes (son el centro de su grupo) y el centro se ajusta al promedio ponderado de sus integrantes. Depende solo
/// del zoom, no de hacia dónde se mueve el mapa: al arrastrar, los grupos no cambian.
List<GrupoMapa> agruparLugares(List<PuntoMapa> puntos, MapCamera camara, double zoom, {double radio = _radioGrupo}) {
  final orden = [...puntos]..sort((a, b) => b.total.compareTo(a.total));
  final grupos = <({List<PuntoMapa> lugares, Offset centro, double peso})>[];
  for (final p in orden) {
    final px = camara.projectAtZoom(_ll(p.posicion), zoom);
    var unido = false;
    if (radio > 0) {
      for (var i = 0; i < grupos.length; i++) {
        final g = grupos[i];
        if ((g.centro - px).distance < radio) {
          final peso = g.peso + p.total;
          grupos[i] = (lugares: [...g.lugares, p], centro: (g.centro * g.peso + px * p.total.toDouble()) / peso, peso: peso);
          unido = true;
          break;
        }
      }
    }
    if (!unido) grupos.add((lugares: [p], centro: px, peso: p.total.toDouble()));
  }
  return [
    for (final g in grupos)
      GrupoMapa(g.lugares, g.lugares.length == 1 ? _ll(g.lugares.single.posicion) : camara.unprojectAtZoom(g.centro, zoom)),
  ];
}

/// Permite a la pantalla pedirle al mapa que vaya a un lugar (p. ej. al abrir su cabecera en la lista).
class ControlMapaMaterna {
  _EstadoMapa? _estado;

  /// Mueve el mapa, con un vuelo suave, hasta el lugar con esa clave y abre su etiqueta.
  void enfocar(String clave) => _estado?._enfocar(clave);
}

class MapaMaterna extends StatefulWidget {
  const MapaMaterna({
    super.key,
    required this.geografia,
    required this.puntos,
    this.alto = 320,
    this.municipios,
    this.atenuarVisitadas = false,
    this.ruta,
    this.rotulos = const [],
    this.alElegirZona,
    this.control,
  });

  final Geografia geografia;
  final List<PuntoMapa> puntos;
  final double alto;

  /// Códigos de los municipios que se dibujan (null: los 40 de La Guajira y el Cesar).
  final Set<String>? municipios;

  /// En «Mapa y visitas»: el color sale de las gestantes que faltan por visitar; un lugar ya visitado del todo va
  /// en gris.
  final bool atenuarVisitadas;

  /// Recorrido sugerido (solo en «Mapa y visitas», orden «Recorrido»).
  final RutaMapa? ruta;
  final List<RotuloMapa> rotulos;

  /// Elegir una zona del mapa (nombre y lugares) para ver sus gestantes en la lista: al tocar un lugar suelto, o
  /// con «Ver gestantes» en la etiqueta de un grupo. Sin esta función, el mapa solo muestra las etiquetas.
  final void Function(String nombre, List<PuntoMapa> lugares)? alElegirZona;

  final ControlMapaMaterna? control;

  @override
  State<MapaMaterna> createState() => _EstadoMapa();
}

class _EstadoMapa extends State<MapaMaterna> with SingleTickerProviderStateMixin {
  final _control = MapController();
  late final AnimationController _vuelo;
  VoidCallback? _pasoVuelo;

  @override
  void initState() {
    super.initState();
    _vuelo = AnimationController(vsync: this, duration: const Duration(milliseconds: 420));
    widget.control?._estado = this;
  }

  @override
  void didUpdateWidget(MapaMaterna viejo) {
    super.didUpdateWidget(viejo);
    if (viejo.control != widget.control) {
      if (viejo.control?._estado == this) viejo.control!._estado = null;
      widget.control?._estado = this;
    }
  }

  void _enfocar(String clave) {
    final lugar = widget.puntos.where((p) => p.clave == clave).firstOrNull;
    if (lugar == null) return;
    setState(() => _abierto = clave);
    _volar(_ll(lugar.posicion), math.max(_control.camera.zoom, 10.5));
  }

  /// Lugar con la etiqueta abierta (su clave): la etiqueta sigue al grupo que lo contiene aunque cambie el zoom. Se
  /// cierra al tocar otro marcador o el mapa.
  String? _abierto;

  // la agrupación solo se recalcula cuando cambia el zoom (en pasos de un cuarto) o los puntos
  ({double zoom, List<PuntoMapa> puntos, List<GrupoMapa> grupos})? _memoria;

  @override
  void dispose() {
    if (widget.control?._estado == this) widget.control!._estado = null;
    _vuelo.dispose();
    super.dispose();
  }

  Iterable<Municipio> get _visibles =>
      widget.geografia.municipios.values.where((m) => widget.municipios == null || widget.municipios!.contains(m.codigo));

  LatLngBounds _encuadre() {
    final puntosMapa = [
      for (final p in widget.puntos) _ll(p.posicion),
      if (widget.ruta?.inicio case final inicio?) _ll(inicio),
    ];
    if (puntosMapa.length >= 2) return LatLngBounds.fromPoints(puntosMapa);
    final contorno = [for (final m in _visibles) for (final p in m.poligonos) for (final c in p.first) _ll(c)];
    if (puntosMapa.length == 1) {
      // un solo lugar: su municipio completo alrededor
      final m = widget.geografia.municipioEn((lat: puntosMapa.single.latitude, lon: puntosMapa.single.longitude));
      if (m != null) return LatLngBounds.fromPoints([for (final p in m.poligonos) for (final c in p.first) _ll(c)]);
    }
    return LatLngBounds.fromPoints(contorno);
  }

  List<GrupoMapa> _grupos(MapCamera camara) {
    final zoom = (camara.zoom * 4).floorToDouble() / 4;
    final m = _memoria;
    if (m != null && m.zoom == zoom && identical(m.puntos, widget.puntos)) return m.grupos;
    final grupos = agruparLugares(widget.puntos, camara, zoom, radio: camara.zoom >= _zoomMaximo - .01 ? 0 : _radioGrupo);
    _memoria = (zoom: zoom, puntos: widget.puntos, grupos: grupos);
    return grupos;
  }

  /// Mueve la cámara de forma suave (o de inmediato con «reducir animaciones»).
  void _volar(LatLng destino, double zoom) {
    zoom = zoom.clamp(_zoomMinimo, _zoomMaximo);
    final inicio = _control.camera;
    if (MediaQuery.of(context).disableAnimations) {
      _control.move(destino, zoom);
      return;
    }
    final lat = Tween(begin: inicio.center.latitude, end: destino.latitude);
    final lon = Tween(begin: inicio.center.longitude, end: destino.longitude);
    final z = Tween(begin: inicio.zoom, end: zoom);
    final curva = CurvedAnimation(parent: _vuelo, curve: Curves.easeInOutCubic);
    if (_pasoVuelo != null) _vuelo.removeListener(_pasoVuelo!);
    _pasoVuelo = () => _control.move(LatLng(lat.evaluate(curva), lon.evaluate(curva)), z.evaluate(curva));
    _vuelo
      ..addListener(_pasoVuelo!)
      ..forward(from: 0);
  }

  void _zoom(double paso) => _volar(_control.camera.center, _control.camera.zoom + paso);

  void _acercar(GrupoMapa g) {
    final camara = _control.camera;
    final ajuste = CameraFit.bounds(
      bounds: LatLngBounds.fromPoints([for (final p in g.lugares) _ll(p.posicion)]),
      padding: const EdgeInsets.all(70),
      maxZoom: _zoomMaximo,
    ).fit(camara);
    setState(() => _abierto = null);
    _volar(ajuste.center, math.max(ajuste.zoom, camara.zoom + 1));
  }

  bool _contiene(GrupoMapa g, String? clave) => clave != null && g.lugares.any((p) => p.clave == clave);

  void _tocar(GrupoMapa g) {
    setState(() => _abierto = _contiene(g, _abierto) ? null : g.lugares.first.clave);
    if (g.esLugar) widget.alElegirZona?.call(nombreGrupo(g), g.lugares);
  }

  @override
  Widget build(BuildContext context) {
    final ruta = widget.ruta;
    final numeros = {for (final (i, p) in (ruta?.paradas ?? const []).indexed) p.clave: i + 1};
    return Semantics(
      label: 'Mapa de ${widget.puntos.length} lugares con gestantes'
          '${ruta == null || ruta.paradas.isEmpty ? '' : ', con el recorrido de ${ruta.paradas.length} paradas'}',
      child: ClipRRect(
        borderRadius: BorderRadius.circular(20),
        child: SizedBox(
          height: widget.alto,
          child: Stack(children: [
            FlutterMap(
              mapController: _control,
              options: MapOptions(
                backgroundColor: ColoresMaterna.crema,
                initialCameraFit: CameraFit.bounds(bounds: _encuadre(), padding: const EdgeInsets.fromLTRB(30, 36, 50, 30), maxZoom: 11),
                minZoom: _zoomMinimo,
                maxZoom: _zoomMaximo,
                interactionOptions: const InteractionOptions(flags: InteractiveFlag.all & ~InteractiveFlag.rotate),
                onTap: (_, _) {
                  if (_abierto != null) setState(() => _abierto = null);
                },
              ),
              children: [
                PolygonLayer(polygons: [
                  for (final m in _visibles)
                    for (final anillos in m.poligonos)
                      Polygon(
                        points: [for (final c in anillos.first) _ll(c)],
                        holePointsList: [for (final h in anillos.skip(1)) [for (final c in h) _ll(c)]],
                        color: ColoresMaterna.campo,
                        borderColor: ColoresMaterna.tarjeta,
                        borderStrokeWidth: 1,
                      ),
                ]),
                if (ruta != null && ruta.paradas.isNotEmpty)
                  PolylineLayer(polylines: [
                    // un tramo por parada, del color del nivel de la parada a la que llega
                    for (final (i, p) in ruta.paradas.indexed)
                      if (i > 0 || ruta.inicio != null)
                        Polyline(
                          points: [_ll(i == 0 ? ruta.inicio! : ruta.paradas[i - 1].posicion), _ll(p.posicion)],
                          color: colorNivel(p.nivel).withValues(alpha: .8),
                          strokeWidth: 3,
                          pattern: const StrokePattern.dotted(spacingFactor: 2.2),
                        ),
                  ]),
                MarkerLayer(markers: [
                  for (final r in widget.rotulos)
                    Marker(
                      point: _ll(r.posicion),
                      width: 130,
                      height: 34,
                      alignment: Alignment.topCenter,
                      child: IgnorePointer(
                        child: Column(mainAxisAlignment: MainAxisAlignment.end, children: [
                          Text(r.texto,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(fontSize: 11, fontWeight: FontWeight.w500, color: ColoresMaterna.tintaSuave)),
                          Container(
                              width: 4.5, height: 4.5, decoration: BoxDecoration(color: ColoresMaterna.tintaSuave, shape: BoxShape.circle)),
                        ]),
                      ),
                    ),
                  if (ruta?.inicio case final inicio?) _partida(inicio),
                ]),
                // marcadores agrupados y etiqueta: se reconstruyen con cada movimiento de la cámara
                Builder(builder: (context) {
                  final camara = MapCamera.of(context);
                  final grupos = _grupos(camara);
                  final abierto = grupos.where((g) => _contiene(g, _abierto)).firstOrNull;
                  final ancla = abierto == null ? null : camara.latLngToScreenOffset(abierto.centro);
                  // si el marcador salió de la vista al mover el mapa, su etiqueta no se queda pegada al borde
                  final visible = ancla != null && (Offset.zero & camara.nonRotatedSize).contains(ancla);
                  final orden = [...grupos]
                    ..sort((a, b) => (a.nivel(sinVisitadas: widget.atenuarVisitadas) ?? -1)
                        .compareTo(b.nivel(sinVisitadas: widget.atenuarVisitadas) ?? -1));
                  return Stack(children: [
                    MarkerLayer(markers: [
                      for (final g in orden)
                        _marcador(g, [for (final p in g.lugares) ?numeros[p.clave]].fold<int?>(null, (m, n) => m == null || n < m ? n : m)),
                    ]),
                    if (abierto != null && visible)
                      _Etiqueta(
                        key: const Key('mapa-etiqueta'),
                        ancla: ancla,
                        separacion: _diametro(abierto) / 2 + 8,
                        child: _TarjetaGrupo(
                          grupo: abierto,
                          atenuarVisitadas: widget.atenuarVisitadas,
                          parada: abierto.esLugar ? numeros[abierto.lugares.single.clave] : null,
                          alAcercar: abierto.esLugar ? null : () => _acercar(abierto),
                          alVer: abierto.esLugar || widget.alElegirZona == null
                              ? null
                              : () => widget.alElegirZona!(nombreGrupo(abierto), abierto.lugares),
                        ),
                      ),
                  ]);
                }),
              ],
            ),
            Positioned(
              right: 8,
              top: 8,
              child: Column(children: [
                _BotonZoom(clave: 'mapa-acercar', icono: Icons.add_rounded, etiqueta: 'Acercar', alTocar: () => _zoom(1)),
                const SizedBox(height: 6),
                _BotonZoom(clave: 'mapa-alejar', icono: Icons.remove_rounded, etiqueta: 'Alejar', alTocar: () => _zoom(-1)),
              ]),
            ),
          ]),
        ),
      ),
    );
  }

  /// Diámetro del círculo: pequeño y casi constante para un lugar; un poco mayor para un grupo.
  double _diametro(GrupoMapa g) =>
      g.esLugar ? (16 + 3 * math.sqrt(g.total)).clamp(18.0, 28.0) : (22 + 3.2 * math.sqrt(g.total)).clamp(24.0, 36.0);

  Marker _marcador(GrupoMapa g, int? parada) {
    final nivel = g.nivel(sinVisitadas: widget.atenuarVisitadas);
    final d = _diametro(g);
    final halo = g.esLugar ? 0.0 : 7.0;
    final color = nivel == null ? ColoresMaterna.iconoInactivo : colorNivel(nivel);
    final lado = d + 2 * halo + 14;
    final quieto = MediaQuery.of(context).disableAnimations;
    return Marker(
      key: ValueKey(g.id),
      point: g.centro,
      width: lado,
      height: lado,
      child: Semantics(
        button: true,
        label: g.esLugar
            ? '${g.lugares.single.nombre}, ${g.total} gestante(s)${parada == null ? '' : ', parada $parada'}'
            : 'Grupo de ${g.lugares.length} lugares, ${g.total} gestantes',
        excludeSemantics: true,
        child: GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTap: () => _tocar(g),
          // al separarse o juntarse, el marcador nuevo aparece creciendo suavemente
          child: TweenAnimationBuilder<double>(
            key: ValueKey('anim-${g.id}'),
            tween: Tween(begin: quieto ? 1 : .55, end: 1),
            duration: quieto ? Duration.zero : const Duration(milliseconds: 260),
            curve: Curves.easeOutBack,
            builder: (context, escala, hijo) => Transform.scale(scale: escala, child: hijo),
            child: Stack(alignment: Alignment.center, children: [
              if (!g.esLugar)
                Container(
                  width: d + 2 * halo,
                  height: d + 2 * halo,
                  decoration: BoxDecoration(shape: BoxShape.circle, color: color.withValues(alpha: .18),
                      border: Border.all(color: color.withValues(alpha: .35), width: 1.5)),
                ),
              AnimatedContainer(
                key: nivel == 2 ? const Key('mapa-alto') : null,
                duration: quieto ? Duration.zero : const Duration(milliseconds: 200),
                width: d,
                height: d,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: color,
                  border: Border.all(color: Colors.white, width: 2),
                  boxShadow: [BoxShadow(color: color.withValues(alpha: .35), blurRadius: 6, offset: const Offset(0, 2))],
                ),
                child: FittedBox(
                  child: Padding(
                    padding: const EdgeInsets.all(2),
                    child: Text('${g.total}',
                        style: TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: g.esLugar ? 11 : 12.5, height: 1)),
                  ),
                ),
              ),
              if (parada != null)
                Positioned(
                  right: halo + 1,
                  top: halo + 1,
                  child: Container(
                    key: Key('parada-mapa-$parada'),
                    constraints: const BoxConstraints(minWidth: 15),
                    height: 15,
                    padding: const EdgeInsets.symmetric(horizontal: 3),
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: ColoresMaterna.tinta,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: ColoresMaterna.tarjeta, width: 1.5),
                    ),
                    child: Text('$parada', style: TextStyle(color: ColoresMaterna.crema, fontSize: 8.5, fontWeight: FontWeight.w700, height: 1)),
                  ),
                ),
            ]),
          ),
        ),
      ),
    );
  }

  Marker _partida(Coordenada inicio) => Marker(
        point: _ll(inicio),
        width: 110,
        height: 56,
        // el punto queda justo en la cabecera y el nombre debajo, sin empujarlo (con letra grande no se desborda)
        child: IgnorePointer(
          child: Stack(alignment: Alignment.center, clipBehavior: Clip.none, children: [
            Container(
              key: const Key('mapa-partida'),
              width: 14,
              height: 14,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: ColoresMaterna.vino,
                border: Border.all(color: ColoresMaterna.tarjeta, width: 2.5),
                boxShadow: [BoxShadow(color: ColoresMaterna.vino.withValues(alpha: .35), blurRadius: 10, spreadRadius: 3)],
              ),
            ),
            Positioned(
              top: 37,
              left: 0,
              right: 0,
              child: Text('Punto de partida',
                  textAlign: TextAlign.center,
                  maxLines: 1,
                  softWrap: false,
                  overflow: TextOverflow.visible,
                  style: TextStyle(fontSize: 10.5, fontWeight: FontWeight.w700, color: ColoresMaterna.ciruela900)),
            ),
          ]),
        ),
      );
}

/// Coloca la etiqueta encima del marcador (o debajo si no cabe arriba) y siempre dentro del mapa.
class _Etiqueta extends StatelessWidget {
  const _Etiqueta({super.key, required this.ancla, required this.separacion, required this.child});

  final Offset ancla;
  final double separacion;
  final Widget child;

  @override
  Widget build(BuildContext context) => Positioned.fill(
        child: CustomSingleChildLayout(delegate: _Colocar(ancla, separacion), child: child),
      );
}

class _Colocar extends SingleChildLayoutDelegate {
  _Colocar(this.ancla, this.separacion);

  final Offset ancla;
  final double separacion;
  static const _margen = 8.0;

  @override
  BoxConstraints getConstraintsForChild(BoxConstraints c) =>
      BoxConstraints(maxWidth: math.min(260, c.maxWidth - 2 * _margen), maxHeight: c.maxHeight - 2 * _margen);

  @override
  Offset getPositionForChild(Size mapa, Size tarjeta) {
    final x = (ancla.dx - tarjeta.width / 2).clamp(_margen, math.max(_margen, mapa.width - tarjeta.width - _margen)).toDouble();
    var y = ancla.dy - separacion - tarjeta.height;
    if (y < _margen) y = ancla.dy + separacion; // no cabe arriba: va debajo
    y = y.clamp(_margen, math.max(_margen, mapa.height - tarjeta.height - _margen));
    return Offset(x, y);
  }

  @override
  bool shouldRelayout(_Colocar viejo) => viejo.ancla != ancla || viejo.separacion != separacion;
}

/// Nombre de un marcador: el del lugar o, en un grupo, su municipio y cuántos lugares (o «N lugares cercanos»).
String nombreGrupo(GrupoMapa g) {
  if (g.esLugar) return g.lugares.single.nombre;
  final municipios = {for (final p in g.lugares) p.municipio};
  return municipios.length == 1 ? '${municipios.single} · ${g.lugares.length} lugares' : '${g.lugares.length} lugares cercanos';
}

/// Contenido de la etiqueta: lugar (o zona), cuántas gestantes y su nivel; en un grupo, cuántos lugares,
/// «Ver gestantes» y «Acercar».
class _TarjetaGrupo extends StatelessWidget {
  const _TarjetaGrupo({required this.grupo, required this.atenuarVisitadas, this.parada, this.alAcercar, this.alVer});

  final GrupoMapa grupo;
  final bool atenuarVisitadas;
  final int? parada;
  final VoidCallback? alAcercar;
  final VoidCallback? alVer;

  Widget _accion(String clave, IconData icono, String texto, VoidCallback alTocar) => InkWell(
        key: Key(clave),
        onTap: alTocar,
        borderRadius: BorderRadius.circular(8),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 4, horizontal: 2),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Icon(icono, size: 18, color: ColoresMaterna.ciruela900),
            const SizedBox(width: 4),
            Text(texto, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: ColoresMaterna.ciruela900)),
          ]),
        ),
      );

  @override
  Widget build(BuildContext context) {
    final g = grupo;
    final nivel = g.nivel(sinVisitadas: atenuarVisitadas);
    final titulo = nombreGrupo(g);
    final subtitulo = g.esLugar && !g.lugares.single.nombre.contains(g.lugares.single.municipio) ? g.lugares.single.municipio : null;
    final conteos = g.conteos;
    final desglose = [for (final c in [2, 1, 0]) if (conteos[c] > 0) '${estiloPorCategoria[_categorias[c]]!.corto} ${conteos[c]}'];
    final suave = TextStyle(fontSize: 12.5, color: ColoresMaterna.tintaSuave, height: 1.3);
    return Material(
      color: ColoresMaterna.tarjeta,
      elevation: 6,
      shadowColor: ColoresMaterna.sombra,
      borderRadius: BorderRadius.circular(14),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 9, 12, 9),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(titulo,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(fontSize: 14.5, fontWeight: FontWeight.w700, color: ColoresMaterna.tinta, height: 1.2)),
          if (subtitulo != null) Text(subtitulo, style: suave),
          const SizedBox(height: 2),
          Text.rich(
            TextSpan(children: [
              TextSpan(text: '${g.total} ${g.total == 1 ? 'gestante' : 'gestantes'}'),
              if (nivel != null) ...[
                const TextSpan(text: ' · '),
                TextSpan(
                    text: estiloPorCategoria[_categorias[nivel]]!.corto,
                    style: TextStyle(fontWeight: FontWeight.w700, color: estiloPorCategoria[_categorias[nivel]]!.tinta)),
              ] else
                const TextSpan(text: ' · ya visitadas'),
              if (parada != null) TextSpan(text: ' · parada $parada'),
            ]),
            style: suave.copyWith(fontSize: 13),
          ),
          if (desglose.length > 1 || (atenuarVisitadas && g.visitadas > 0))
            Text([if (desglose.length > 1) desglose.join(' · '), if (atenuarVisitadas && g.visitadas > 0) '${g.visitadas} visitada(s)'].join(' · '),
                style: suave.copyWith(fontSize: 11.5)),
          if (alAcercar != null || alVer != null)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Wrap(spacing: 14, children: [
                if (alVer != null) _accion('mapa-etiqueta-ver', Icons.format_list_bulleted_rounded, 'Ver gestantes', alVer!),
                if (alAcercar != null) _accion('mapa-etiqueta-acercar', Icons.zoom_in_rounded, 'Acercar', alAcercar!),
              ]),
            ),
        ]),
      ),
    );
  }
}

class _BotonZoom extends StatelessWidget {
  const _BotonZoom({required this.clave, required this.icono, required this.etiqueta, required this.alTocar});

  final String clave;
  final IconData icono;
  final String etiqueta;
  final VoidCallback alTocar;

  @override
  Widget build(BuildContext context) => Material(
        color: ColoresMaterna.tarjeta,
        borderRadius: BorderRadius.circular(10),
        elevation: 1.5,
        shadowColor: ColoresMaterna.sombra,
        child: InkWell(
          key: Key(clave),
          borderRadius: BorderRadius.circular(10),
          onTap: alTocar,
          child: Tooltip(
            message: etiqueta,
            child: SizedBox(width: 36, height: 36, child: Icon(icono, size: 20, color: ColoresMaterna.tinta)),
          ),
        ),
      );
}

/// Leyenda del mapa: colores por nivel, qué significa el número y, si aplica, las visitadas y el recorrido.
class LeyendaMapa extends StatelessWidget {
  const LeyendaMapa({super.key, this.conVisitadas = false, this.conRecorrido = false});

  final bool conVisitadas;
  final bool conRecorrido;

  Widget _punto(Color color, String texto) => Row(mainAxisSize: MainAxisSize.min, children: [
        Container(width: 12, height: 12, decoration: BoxDecoration(shape: BoxShape.circle, color: color)),
        const SizedBox(width: 6),
        Text(texto, style: const TextStyle(fontSize: 12.5)),
      ]);

  @override
  Widget build(BuildContext context) => Wrap(spacing: 14, runSpacing: 6, crossAxisAlignment: WrapCrossAlignment.center, children: [
        for (final c in [2, 1, 0]) _punto(colorNivel(c), estiloPorCategoria[_categorias[c]]!.corto),
        if (conVisitadas) _punto(ColoresMaterna.iconoInactivo, 'Visitada'),
        if (conRecorrido)
          Row(mainAxisSize: MainAxisSize.min, children: [
            Text('• • •', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w900, color: ColoresMaterna.ciruela900, letterSpacing: -1)),
            const SizedBox(width: 6),
            const Text('Orden de visita', style: TextStyle(fontSize: 12.5)),
          ])
        else
          Text('Número: cuántas gestantes · con halo: varios lugares', style: TextStyle(fontSize: 12.5, color: ColoresMaterna.tintaSuave)),
      ]);
}
