/// Mapa y visitas: agrupa las ubicaciones por lugar para el mapa y ordena las visitas.
///
/// Por prioridad: una entrada por gestante, primero el nivel de riesgo (Alto, Medio, Bajo) y, dentro de cada nivel,
/// la que lleva más tiempo sin contacto. Recorrido: paradas por LUGAR (al llegar se atiende a todas las gestantes
/// de ese lugar); primero los lugares con alguna gestante de Alto, que son urgentes, y después los demás solo por
/// cercanía, yendo siempre al lugar más cercano al anterior (vecino más cercano, en línea recta). Así no se cruza
/// el territorio de ida y vuelta por separar Medio y Bajo. Las distancias son de apoyo: no hay mapa de vías ni
/// rutas reales, y la ubicación no entra al modelo.
library;

import '../datos/ubicaciones.dart';
import 'geografia.dart';

/// Un lugar del mapa con cuántas gestantes de cada nivel hay ahí.
class PuntoMapa {
  PuntoMapa({required this.clave, required this.posicion, required this.nombre, required this.municipio});

  /// Identifica el lugar (el mismo valor que [Visita.clave] y [Parada.clave]).
  final String clave;
  final Coordenada posicion;
  final String nombre;
  final String municipio;
  final conteos = [0, 0, 0]; // Bajo, Medio, Alto

  /// Cuántas de [conteos] ya fueron visitadas, por nivel.
  final visitadas = [0, 0, 0];

  int get total => conteos.fold(0, (a, b) => a + b);

  /// Nivel más alto entre las gestantes del lugar (si [sinVisitadas], solo entre las que faltan por visitar);
  /// null si no queda ninguna.
  int? nivelMasAlto({bool sinVisitadas = false}) {
    for (final clase in [2, 1, 0]) {
      if (conteos[clase] - (sinVisitadas ? visitadas[clase] : 0) > 0) return clase;
    }
    return null;
  }
}

/// Clave del lugar donde se dibuja una ubicación: su GPS exacto, su lugar o la cabecera de su municipio.
String claveLugar(RegistroUbicacion u) => u.gps != null ? 'gps-${u.id}' : (u.idLugar ?? idCabecera(u.codigoMunicipio));

/// Una gestante por visitar, con lo que se muestra en la lista.
class Visita {
  Visita({required this.ubicacion, required this.posicion, required this.lugar, required this.municipio,
      required this.cabecera, required this.kmCabecera});

  final RegistroUbicacion ubicacion;

  String get clave => claveLugar(ubicacion);
  final Coordenada? posicion;
  final String lugar;
  final String municipio;

  /// Cabecera municipal más cercana y su distancia (referencia aproximada de la IPS).
  final String? cabecera;
  final double? kmCabecera;

}

/// Una parada del recorrido: un lugar con todas sus gestantes pendientes (en orden de prioridad).
class Parada {
  Parada({required this.clave, required this.posicion, required this.lugar, required this.municipio});

  final String clave;
  final Coordenada? posicion;
  final String lugar;
  final String municipio;
  final visitas = <Visita>[];

  /// Nivel de la parada: el más alto entre sus gestantes.
  int get nivel => visitas.map((v) => v.ubicacion.clase).reduce((a, b) => a > b ? a : b);

  /// Distancia en línea recta desde la parada anterior (o desde el punto de partida, en la primera).
  double? kmDesdeAnterior;
}

/// Recorrido sugerido: punto de partida, paradas en orden y kilómetros totales en línea recta.
class Recorrido {
  Recorrido({required this.inicio, required this.paradas});

  final Coordenada? inicio;
  final List<Parada> paradas;

  double get totalKm => paradas.fold(0, (s, p) => s + (p.kmDesdeAnterior ?? 0));

  /// Las gestantes en el orden en que se visitan.
  List<Visita> get visitas => [for (final p in paradas) ...p.visitas];
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
    final clave = claveLugar(u);
    final municipio = geo.municipios[u.codigoMunicipio]?.nombre ?? u.codigoMunicipio;
    final punto = puntos.putIfAbsent(clave, () => PuntoMapa(clave: clave, posicion: posicion, municipio: municipio,
        nombre: u.gps != null ? 'Ubicación exacta' : geo.lugar(clave)?.nombre ?? 'Cabecera de $municipio'));
    punto.conteos[u.clase] += 1;
    if (u.estado == EstadoVisita.visitada) punto.visitadas[u.clase] += 1;
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
    final punto = puntos.putIfAbsent(
        codigo, () => PuntoMapa(clave: idCabecera(codigo), posicion: cabecera.posicion, nombre: municipio, municipio: municipio));
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
      : geo.lugar(u.idLugar)?.nombre ?? 'Cabecera de $municipio';
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

/// Visitas ya hechas, de la más reciente a la más antigua (al marcarla, el último contacto es la fecha de la visita).
List<Visita> visitasHechas(List<RegistroUbicacion> ubicaciones, Geografia geo) {
  final hechas = unaPorGestante(ubicaciones).where((u) => u.estado == EstadoVisita.visitada).toList()
    ..sort((a, b) => b.ultimoContacto.compareTo(a.ultimoContacto));
  return [for (final u in hechas) _visita(u, geo)];
}

/// Recorrido por lugar desde [inicio] (por ejemplo, la cabecera del municipio de la cuenta): primero los lugares
/// con alguna gestante de Alto y luego los demás, siempre al lugar más cercano al anterior. Los lugares sin posición
/// conocida van al final de su grupo, sin distancia.
Recorrido recorridoPorLugar(List<RegistroUbicacion> ubicaciones, Geografia geo, {Coordenada? inicio}) {
  final porLugar = <String, Parada>{};
  for (final v in visitasPorPrioridad(ubicaciones, geo)) {
    porLugar
        .putIfAbsent(v.clave, () => Parada(clave: v.clave, posicion: v.posicion, lugar: v.lugar, municipio: v.municipio))
        .visitas
        .add(v);
  }
  final orden = <Parada>[];
  var actual = inicio;
  for (final urgentes in [true, false]) {
    final quedan = porLugar.values.where((p) => (p.nivel == 2) == urgentes).toList();
    while (quedan.isNotEmpty) {
      quedan.sort((a, b) => _distancia(actual, a.posicion).compareTo(_distancia(actual, b.posicion)));
      final siguiente = quedan.removeAt(0);
      siguiente.kmDesdeAnterior =
          actual == null || siguiente.posicion == null ? null : distanciaKm(actual, siguiente.posicion!);
      orden.add(siguiente);
      actual = siguiente.posicion ?? actual;
    }
  }
  return Recorrido(inicio: inicio, paradas: orden);
}

/// Sin posición conocida, el lugar queda al final de su grupo.
double _distancia(Coordenada? desde, Coordenada? hasta) =>
    hasta == null ? double.infinity : desde == null ? 0 : distanciaKm(desde, hasta);
