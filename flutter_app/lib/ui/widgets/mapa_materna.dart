/// Mapa de concentración de gestantes, 100 % sin internet: solo los límites de los municipios (DANE) y un círculo
/// por nivel de riesgo en cada lugar (tamaño = cuántas gestantes; Alto encima y con borde resaltado). No hay mapa
/// de calles ni teselas. Se puede acercar con dos dedos y mover; al tocar un lugar se ve su detalle.
library;

import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../../motor/geografia.dart';
import '../../motor/visitas.dart';
import '../tema/tema_materna.dart';

const _categorias = ['Bajo Riesgo', 'Riesgo Medio', 'Alto Riesgo'];

LatLng _ll(Coordenada c) => LatLng(c.lat, c.lon);

class MapaMaterna extends StatelessWidget {
  const MapaMaterna({super.key, required this.geografia, required this.puntos, this.alto = 320, this.municipios});

  final Geografia geografia;
  final List<PuntoMapa> puntos;
  final double alto;

  /// Códigos de los municipios que se dibujan (null: los 40 de La Guajira y el Cesar).
  final Set<String>? municipios;

  Iterable<Municipio> get _visibles =>
      geografia.municipios.values.where((m) => municipios == null || municipios!.contains(m.codigo));

  LatLngBounds _encuadre() {
    final puntosMapa = [for (final p in puntos) _ll(p.posicion)];
    if (puntosMapa.length >= 2) return LatLngBounds.fromPoints(puntosMapa);
    final contorno = [for (final m in _visibles) for (final p in m.poligonos) for (final c in p.first) _ll(c)];
    if (puntosMapa.length == 1) {
      // un solo lugar: su municipio completo alrededor
      final m = geografia.municipioEn(puntos.single.posicion);
      if (m != null) return LatLngBounds.fromPoints([for (final p in m.poligonos) for (final c in p.first) _ll(c)]);
    }
    return LatLngBounds.fromPoints(contorno);
  }

  void _detalle(BuildContext context, PuntoMapa p) {
    final partes = [for (final (i, n) in p.conteos.indexed.toList().reversed) if (n > 0) '${estiloPorCategoria[_categorias[i]]!.corto} $n'];
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(
          content: Text('${p.nombre} · ${p.municipio}\n${p.total} gestante(s): ${partes.join(' · ')}')));
  }

  @override
  Widget build(BuildContext context) {
    final maximo = puntos.fold<int>(1, (m, p) => math.max(m, p.conteos.reduce(math.max)));
    final marcadores = <Marker>[];
    for (final clase in [0, 1, 2]) {
      // Bajo primero y Alto al final: el círculo de Alto queda encima
      final estilo = estiloPorCategoria[_categorias[clase]]!;
      for (final p in puntos) {
        final n = p.conteos[clase];
        if (n == 0) continue;
        final d = 14 + 30 * math.sqrt(n / maximo);
        marcadores.add(Marker(
          point: _ll(p.posicion),
          width: d,
          height: d,
          child: GestureDetector(
            onTap: () => _detalle(context, p),
            child: DecoratedBox(
              key: clase == 2 ? const Key('mapa-alto') : null,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: estilo.barra.withValues(alpha: clase == 2 ? .9 : .72),
                border: Border.all(color: clase == 2 ? ColoresMaterna.tarjeta : Colors.white70, width: clase == 2 ? 2.5 : 1),
              ),
            ),
          ),
        ));
      }
    }
    return Semantics(
      label: 'Mapa de ${puntos.length} lugares con gestantes',
      child: ClipRRect(
        borderRadius: BorderRadius.circular(20),
        child: SizedBox(
          height: alto,
          child: FlutterMap(
            options: MapOptions(
              backgroundColor: ColoresMaterna.crema,
              initialCameraFit: CameraFit.bounds(bounds: _encuadre(), padding: const EdgeInsets.all(28), maxZoom: 11),
              minZoom: 5,
              maxZoom: 14,
              interactionOptions: const InteractionOptions(flags: InteractiveFlag.all & ~InteractiveFlag.rotate),
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
              MarkerLayer(markers: marcadores),
            ],
          ),
        ),
      ),
    );
  }
}

/// Leyenda del mapa: colores por nivel y qué significa el tamaño.
class LeyendaMapa extends StatelessWidget {
  const LeyendaMapa({super.key});

  @override
  Widget build(BuildContext context) => Wrap(spacing: 14, runSpacing: 6, crossAxisAlignment: WrapCrossAlignment.center, children: [
        for (final c in _categorias.reversed)
          Row(mainAxisSize: MainAxisSize.min, children: [
            Container(width: 12, height: 12, decoration: BoxDecoration(shape: BoxShape.circle, color: estiloPorCategoria[c]!.barra)),
            const SizedBox(width: 6),
            Text(estiloPorCategoria[c]!.corto, style: const TextStyle(fontSize: 12.5)),
          ]),
        Text('Tamaño: cuántas gestantes', style: TextStyle(fontSize: 12.5, color: ColoresMaterna.tintaSuave)),
      ]);
}
