/// Georreferenciación en la app: municipios y cabeceras REALES (DANE, MGN 2024) y puntos de concentración
/// SINTÉTICOS (ranchería, vereda o resguardo con nombre genérico). Vienen del Módulo 1 en assets/geo/
/// (src/georreferencia.py) y funcionan sin internet: los mapas dibujan solo límites y puntos.
///
/// La ubicación NUNCA entra al modelo: solo sirve para encontrar a la gestante y ordenar las visitas.
library;

import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/services.dart';

/// (longitud, latitud) en grados.
typedef Coordenada = ({double lon, double lat});

class Municipio {
  Municipio({required this.codigo, required this.nombre, required this.departamento, required this.poligonos});

  final String codigo;
  final String nombre;
  final String departamento;

  /// Cada polígono es una lista de anillos; el primero es el contorno y los demás, huecos.
  final List<List<List<Coordenada>>> poligonos;

  bool contiene(Coordenada p) => poligonos.any((anillos) =>
      _enAnillo(p, anillos.first) && !anillos.skip(1).any((hueco) => _enAnillo(p, hueco)));
}

/// Un lugar donde se agrupan gestantes. Las cabeceras municipales son reales; los demás puntos, sintéticos.
class Lugar {
  const Lugar({required this.id, required this.codigoMunicipio, required this.nombre, required this.tipo,
      required this.posicion, required this.sintetico});

  final String id;
  final String codigoMunicipio;
  final String nombre;
  final String tipo;
  final Coordenada posicion;
  final bool sintetico;

  bool get esCabecera => tipo == 'Cabecera municipal';
}

/// Identificador del lugar «cabecera» de un municipio (el mismo que usa el Módulo 1).
String idCabecera(String codigoMunicipio) => '$codigoMunicipio-CAB';

bool _enAnillo(Coordenada p, List<Coordenada> anillo) {
  var dentro = false;
  for (var i = 0, j = anillo.length - 1; i < anillo.length; j = i++) {
    final a = anillo[i], b = anillo[j];
    if ((a.lat > p.lat) != (b.lat > p.lat) && p.lon < (b.lon - a.lon) * (p.lat - a.lat) / (b.lat - a.lat) + a.lon) {
      dentro = !dentro;
    }
  }
  return dentro;
}

/// Distancia en línea recta (haversine), en km. Es solo información de apoyo.
double distanciaKm(Coordenada a, Coordenada b) {
  const r = 6371.0;
  double rad(double g) => g * math.pi / 180;
  final dLat = rad(b.lat - a.lat), dLon = rad(b.lon - a.lon);
  final h = math.pow(math.sin(dLat / 2), 2) + math.cos(rad(a.lat)) * math.cos(rad(b.lat)) * math.pow(math.sin(dLon / 2), 2);
  return 2 * r * math.asin(math.sqrt(h));
}

class Geografia {
  Geografia._(this.municipios, this._lugares, this.fuente);

  /// Los 40 municipios de La Guajira y el Cesar, por código DIVIPOLA.
  final Map<String, Municipio> municipios;
  final Map<String, Lugar> _lugares;
  final String fuente;

  static Future<Geografia> cargar() async => desdeTextos(
        municipios: await rootBundle.loadString('assets/geo/municipios_guajira_cesar.geojson'),
        cabeceras: await rootBundle.loadString('assets/geo/cabeceras_guajira_cesar.json'),
        puntos: await rootBundle.loadString('assets/geo/puntos_concentracion.json'),
      );

  static Geografia desdeTextos({required String municipios, required String cabeceras, required String puntos}) {
    final geo = jsonDecode(municipios) as Map<String, dynamic>;
    Coordenada c(List<dynamic> p) => (lon: (p[0] as num).toDouble(), lat: (p[1] as num).toDouble());
    List<List<Coordenada>> anillos(List<dynamic> poligono) => [for (final a in poligono) [for (final p in a as List) c(p as List)]];
    final lista = <String, Municipio>{};
    for (final f in geo['features'] as List) {
      final props = f['properties'] as Map<String, dynamic>;
      final g = f['geometry'] as Map<String, dynamic>;
      final coords = g['coordinates'] as List;
      lista[props['codigo'] as String] = Municipio(
        codigo: props['codigo'] as String,
        nombre: props['municipio'] as String,
        departamento: props['departamento'] as String,
        poligonos: g['type'] == 'Polygon' ? [anillos(coords)] : [for (final p in coords) anillos(p as List)],
      );
    }
    final lugares = <String, Lugar>{};
    for (final cab in (jsonDecode(cabeceras) as Map<String, dynamic>)['cabeceras'] as List) {
      final codigo = cab['codigo'] as String;
      lugares[idCabecera(codigo)] = Lugar(id: idCabecera(codigo), codigoMunicipio: codigo, nombre: 'Cabecera de ${cab['nombre']}',
          tipo: 'Cabecera municipal', posicion: (lon: (cab['lon'] as num).toDouble(), lat: (cab['lat'] as num).toDouble()),
          sintetico: false);
    }
    for (final p in (jsonDecode(puntos) as Map<String, dynamic>)['puntos'] as List) {
      lugares[p['id'] as String] = Lugar(id: p['id'] as String, codigoMunicipio: p['codigo_municipio'] as String,
          nombre: p['nombre'] as String, tipo: p['tipo'] as String,
          posicion: (lon: (p['lon'] as num).toDouble(), lat: (p['lat'] as num).toDouble()), sintetico: p['sintetico'] == true);
    }
    return Geografia._(lista, lugares, geo['fuente'] as String? ?? 'DANE');
  }

  /// Municipios ordenados por departamento y nombre (para elegirlos en una lista).
  List<Municipio> get ordenados =>
      municipios.values.toList()..sort((a, b) => '${a.departamento}${a.nombre}'.compareTo('${b.departamento}${b.nombre}'));

  /// Busca un municipio por su nombre, sin distinguir mayúsculas ni tildes («codazzi» encuentra «Agustín Codazzi»).
  Municipio? porNombre(String? nombre) {
    if (nombre == null || nombre.trim().isEmpty) return null;
    final buscado = _simple(nombre);
    for (final m in municipios.values) {
      if (_simple(m.nombre) == buscado) return m;
    }
    for (final m in municipios.values) {
      if (_simple(m.nombre).split(' ').contains(buscado)) return m;
    }
    return null;
  }

  Lugar? lugar(String? id) => id == null ? null : _lugares[id];

  /// La cabecera y luego los puntos de concentración del municipio.
  List<Lugar> lugaresDe(String codigoMunicipio) =>
      [for (final l in _lugares.values) if (l.codigoMunicipio == codigoMunicipio) l]..sort((a, b) {
          if (a.esCabecera != b.esCabecera) return a.esCabecera ? -1 : 1;
          return a.nombre.compareTo(b.nombre);
        });

  Lugar? cabecera(String codigoMunicipio) => _lugares[idCabecera(codigoMunicipio)];

  /// El municipio que contiene la coordenada (por ejemplo, la del GPS), o null si cae fuera de los dos departamentos.
  Municipio? municipioEn(Coordenada p) {
    for (final m in municipios.values) {
      if (m.contiene(p)) return m;
    }
    return null;
  }

  /// La cabecera municipal más cercana y su distancia en km (referencia de apoyo, no variable del modelo).
  (Lugar, double)? cabeceraMasCercana(Coordenada p) {
    (Lugar, double)? mejor;
    for (final l in _lugares.values) {
      if (!l.esCabecera) continue;
      final d = distanciaKm(p, l.posicion);
      if (mejor == null || d < mejor.$2) mejor = (l, d);
    }
    return mejor;
  }
}

String _simple(String texto) {
  const tildes = {'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ü': 'u', 'ñ': 'n'};
  return texto.trim().toLowerCase().split('').map((c) => tildes[c] ?? c).join();
}
