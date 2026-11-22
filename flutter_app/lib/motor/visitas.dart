/// Mapa y visitas: agrupa las ubicaciones por lugar para el mapa y ordena las visitas pendientes.
///
/// Orden por prioridad: primero el nivel de riesgo (Alto, Medio, Bajo) y, dentro de cada nivel, la gestante con el
/// último contacto más antiguo. Orden de recorrido: el mismo orden por riesgo, pero dentro de cada nivel se va
/// siempre al lugar más cercano al anterior (vecino más cercano, en línea recta). Las distancias son de apoyo:
/// no hay mapa de calles ni rutas reales, y la ubicación no entra al modelo.
library;

import '../datos/ubicaciones.dart';
import 'geografia.dart';

/// Un lugar del mapa con cuántas gestantes de cada nivel hay ahí.
class PuntoMapa {
  PuntoMapa({required this.posicion, required this.nombre, required this.municipio});

  final Coordenada posicion;
  final String nombre;
  final String municipio;
  final conteos = [0, 0, 0]; // Bajo, Medio, Alto

  int get total => conteos.fold(0, (a, b) => a + b);
}

/// Una gestante por visitar, con lo que se muestra en la lista.
class Visita {
  Visita({required this.ubicacion, required this.posicion, required this.lugar, required this.municipio,
      required this.cabecera, required this.kmCabecera});

  final RegistroUbicacion ubicacion;
  final Coordenada? posicion;
  final String lugar;
  final String municipio;

  /// Cabecera municipal más cercana y su distancia (referencia aproximada de la IPS).
  final String? cabecera;
  final double? kmCabecera;

  /// Distancia desde la visita anterior en el orden de recorrido.
  double? kmDesdeAnterior;
}

/// Una sola entrada por gestante: si tiene varias evaluaciones con el mismo código, cuenta la más reciente
/// (con el contacto más reciente de todas). Las evaluaciones sin código son gestantes distintas.
List<RegistroUbicacion> unaPorGestante(List<RegistroUbicacion> ubicaciones) {
  final porCodigo = <String, RegistroUbicacion>{};
  final sinCodigo = <RegistroUbicacion>[];
  for (final u in ubicaciones) {
    final codigo = u.idSeudonimo;
    if (codigo == null) {
      sinCodigo.add(u);
    } else if (!porCodigo.containsKey(codigo) || u.fechaEvaluacion.isAfter(porCodigo[codigo]!.fechaEvaluacion)) {
      porCodigo[codigo] = u;
    }
  }
  return [...porCodigo.values, ...sinCodigo];
}

/// Puntos del mapa: un punto por lugar (o por GPS exacto, si la cuenta puede verlo).
List<PuntoMapa> puntosDelMapa(List<RegistroUbicacion> ubicaciones, Geografia geo, {Set<int>? clases}) {
  final puntos = <String, PuntoMapa>{};
  for (final u in unaPorGestante(ubicaciones)) {
    if (clases != null && !clases.contains(u.clase)) continue;
    final posicion = u.posicion(geo);
    if (posicion == null) continue;
    final clave = u.gps != null ? 'gps-${u.id}' : (u.idLugar ?? idCabecera(u.codigoMunicipio));
    final municipio = geo.municipios[u.codigoMunicipio]?.nombre ?? u.codigoMunicipio;
    final punto = puntos.putIfAbsent(clave, () => PuntoMapa(posicion: posicion, municipio: municipio,
        nombre: u.gps != null ? 'Ubicación exacta' : geo.lugar(clave)?.nombre ?? 'Cabecera de $municipio'));
    punto.conteos[u.clase] += 1;
  }
  return puntos.values.toList();
}

/// Puntos del mapa a partir de (código del municipio, nivel): uno por municipio, en su cabecera. Lo usa el
/// resultado de la carga masiva, que ubica a cada gestante por la columna «Municipio» del archivo.
List<PuntoMapa> puntosPorMunicipio(Iterable<(String, int)> municipioYClase, Geografia geo) {
  final puntos = <String, PuntoMapa>{};
  for (final (codigo, clase) in municipioYClase) {
    final cabecera = geo.cabecera(codigo);
    if (cabecera == null) continue;
    final municipio = geo.municipios[codigo]!.nombre;
    final punto = puntos.putIfAbsent(codigo, () => PuntoMapa(posicion: cabecera.posicion, nombre: municipio, municipio: municipio));
    punto.conteos[clase] += 1;
  }
  return puntos.values.toList();
}

Visita _visita(RegistroUbicacion u, Geografia geo) {
  final posicion = u.posicion(geo);
  final cercana = posicion == null ? null : geo.cabeceraMasCercana(posicion);
  final municipio = geo.municipios[u.codigoMunicipio]?.nombre ?? u.codigoMunicipio;
  final lugar = u.gps != null
      ? 'Ubicación exacta'
      : geo.lugar(u.idLugar)?.nombre ?? 'Sin lugar: se muestra la cabecera';
  return Visita(ubicacion: u, posicion: posicion, lugar: lugar, municipio: municipio,
      cabecera: cercana?.$1.nombre, kmCabecera: cercana?.$2);
}

/// Visitas pendientes (no las ya visitadas), ordenadas por riesgo y luego por el último contacto más antiguo.
List<Visita> visitasPorPrioridad(List<RegistroUbicacion> ubicaciones, Geografia geo) {
  final pendientes = unaPorGestante(ubicaciones).where((u) => u.estado != EstadoVisita.visitada).toList()
    ..sort((a, b) {
      final porRiesgo = b.clase.compareTo(a.clase);
      return porRiesgo != 0 ? porRiesgo : a.ultimoContacto.compareTo(b.ultimoContacto);
    });
  return [for (final u in pendientes) _visita(u, geo)];
}

/// Las mismas visitas en orden de recorrido: Alto, luego Medio, luego Bajo; dentro de cada nivel, siempre la más
/// cercana a la anterior, empezando en [inicio] (por ejemplo, la cabecera del municipio de la cuenta).
List<Visita> visitasPorRecorrido(List<RegistroUbicacion> ubicaciones, Geografia geo, {Coordenada? inicio}) {
  final porPrioridad = visitasPorPrioridad(ubicaciones, geo);
  final orden = <Visita>[];
  var actual = inicio;
  for (final clase in [2, 1, 0]) {
    final quedan = porPrioridad.where((v) => v.ubicacion.clase == clase).toList();
    while (quedan.isNotEmpty) {
      quedan.sort((a, b) => _distancia(actual, a).compareTo(_distancia(actual, b)));
      final siguiente = quedan.removeAt(0);
      siguiente.kmDesdeAnterior =
          actual == null || siguiente.posicion == null ? null : distanciaKm(actual, siguiente.posicion!);
      orden.add(siguiente);
      actual = siguiente.posicion ?? actual;
    }
  }
  return orden;
}

/// Sin posición conocida, la visita queda al final de su nivel.
double _distancia(Coordenada? desde, Visita v) =>
    desde == null || v.posicion == null ? (v.posicion == null ? double.infinity : 0) : distanciaKm(desde, v.posicion!);
