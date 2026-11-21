/// Ubicación de una gestante para encontrarla en territorio. Se guarda solo con la evaluación y su código
/// anónimo: nunca con su nombre ni su documento.
///
/// Tres niveles de detalle:
///   municipio · lugar (ranchería, vereda, resguardo o cabecera; el nivel de trabajo por defecto) ·
///   GPS exacto, solo con el consentimiento registrado y solo para médico o enfermería.
/// La base local (base_local.dart) hace cumplir estas reglas: la pantalla no puede saltárselas.
/// La ubicación NUNCA es una variable del modelo.
library;

import '../motor/geografia.dart';

enum NivelUbicacion { municipio, lugar, gps }

enum EstadoVisita { pendiente, visitada, sinLocalizar }

/// Quién atiende puede registrar y ver el GPS exacto (las demás cuentas trabajan por lugar).
const rolesConGps = {'Medico', 'Enfermero(a)'};

bool puedeUsarGps(String atendidoPor) => rolesConGps.contains(atendidoPor);

/// Quién acompaña o ayuda a ubicar a la gestante. Se guarda el rol y, si se quiere, un apodo: no el nombre completo.
const rolesReferencia = ['Autoridad tradicional', 'Partera', 'Promotor(a) de salud', 'Familiar', 'Otra persona'];
const largoMaximoApodo = 30;

/// Un apodo corto sin números largos (para que no se escriba ahí un documento o un teléfono).
String? apodoValido(String? apodo) {
  final texto = apodo?.trim() ?? '';
  if (texto.isEmpty) return null;
  if (texto.length > largoMaximoApodo) throw ArgumentError('El apodo admite hasta $largoMaximoApodo caracteres.');
  if (RegExp(r'\d{4,}').hasMatch(texto)) throw ArgumentError('No escriba documentos ni teléfonos en el apodo.');
  return texto;
}

/// Lo que se captura en el triaje (o se deduce del archivo de la IPS).
class UbicacionCapturada {
  const UbicacionCapturada({required this.codigoMunicipio, this.idLugar, this.gps, this.consentimiento = false,
      this.referenciaRol, this.referenciaApodo});

  final String codigoMunicipio;
  final String? idLugar;
  final Coordenada? gps;
  final bool consentimiento;
  final String? referenciaRol;
  final String? referenciaApodo;

  NivelUbicacion get nivel => gps != null ? NivelUbicacion.gps : idLugar != null ? NivelUbicacion.lugar : NivelUbicacion.municipio;
}

/// Una ubicación guardada, con lo necesario para el mapa y la lista de visitas.
class RegistroUbicacion {
  RegistroUbicacion.desdeFila(Map<String, Object?> f, {required bool conGps})
      : id = f['id'] as int,
        idEvaluacion = f['id_evaluacion'] as int,
        idSeudonimo = f['id_seudonimo'] as String?,
        fechaEvaluacion = DateTime.parse(f['fecha'] as String),
        clase = f['clase'] as int,
        categoria = f['categoria'] as String,
        codigoMunicipio = f['codigo_municipio'] as String,
        idLugar = f['id_lugar'] as String?,
        nivel = NivelUbicacion.values.byName(f['nivel'] as String),
        // el GPS exacto solo se entrega a quien puede verlo; a los demás les llega solo el lugar
        gps = conGps && f['lat'] != null ? (lon: (f['lon'] as num).toDouble(), lat: (f['lat'] as num).toDouble()) : null,
        consentimiento = (f['consentimiento'] as int) == 1,
        referenciaRol = f['referencia_rol'] as String?,
        referenciaApodo = f['referencia_apodo'] as String?,
        ultimoContacto = DateTime.parse(f['ultimo_contacto'] as String),
        estado = EstadoVisita.values.byName(f['estado'] as String),
        idCarga = f['id_carga'] as int?;

  final int id;
  final int idEvaluacion;
  final String? idSeudonimo;
  final DateTime fechaEvaluacion;
  final int clase;
  final String categoria;
  final String codigoMunicipio;
  final String? idLugar;
  final NivelUbicacion nivel;
  final Coordenada? gps;
  final bool consentimiento;
  final String? referenciaRol;
  final String? referenciaApodo;
  final DateTime ultimoContacto;
  final EstadoVisita estado;
  final int? idCarga;

  /// Dónde dibujarla: el GPS si se puede ver; si no, su lugar; si no, la cabecera de su municipio.
  Coordenada? posicion(Geografia geo) =>
      gps ?? geo.lugar(idLugar)?.posicion ?? geo.cabecera(codigoMunicipio)?.posicion;
}
