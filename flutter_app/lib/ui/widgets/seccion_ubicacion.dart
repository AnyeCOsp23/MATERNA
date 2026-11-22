/// «Ubicación para la visita» (opcional), dentro del paso «Contexto y atención» del triaje.
///
/// Sirve para encontrar a la gestante después (rancherías, veredas y resguardos dispersos). No cambia el
/// resultado: la ubicación no es una variable del modelo. Niveles: municipio · lugar (por defecto) · GPS exacto,
/// este último solo con el consentimiento marcado y solo para médico o enfermería (ubicaciones.dart).
library;

import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';

import '../../datos/ubicaciones.dart';
import '../../motor/geografia.dart';
import '../tema/tema_materna.dart';
import 'campos.dart';

/// Devuelve la posición del teléfono o lanza una excepción con un mensaje para el usuario.
typedef ObtenerPosicion = Future<Coordenada> Function();

/// GPS del dispositivo (funciona sin internet en el teléfono; en la web el navegador pide permiso).
Future<Coordenada> posicionDelDispositivo() async {
  if (!await Geolocator.isLocationServiceEnabled()) {
    throw const _AvisoUbicacion('Active la ubicación del teléfono e intente de nuevo.');
  }
  var permiso = await Geolocator.checkPermission();
  if (permiso == LocationPermission.denied) permiso = await Geolocator.requestPermission();
  if (permiso == LocationPermission.denied || permiso == LocationPermission.deniedForever) {
    throw const _AvisoUbicacion('Sin permiso para usar la ubicación. Puede elegir el lugar en la lista.');
  }
  final p = await Geolocator.getCurrentPosition(
      locationSettings: const LocationSettings(accuracy: LocationAccuracy.high, timeLimit: Duration(seconds: 25)));
  return (lon: p.longitude, lat: p.latitude);
}

class _AvisoUbicacion implements Exception {
  const _AvisoUbicacion(this.mensaje);
  final String mensaje;
  @override
  String toString() => mensaje;
}

/// Lo que se va llenando en la sección. El triaje crea uno nuevo en cada evaluación.
class ControlUbicacion extends ChangeNotifier {
  ControlUbicacion({String? codigoMunicipio}) : _codigoMunicipio = codigoMunicipio;

  String? _codigoMunicipio;
  String? _idLugar;
  Coordenada? _gps;
  bool _consentimiento = false;
  String? _referenciaRol;
  final apodo = TextEditingController();

  String? get codigoMunicipio => _codigoMunicipio;
  String? get idLugar => _idLugar;
  Coordenada? get gps => _gps;
  bool get consentimiento => _consentimiento;
  String? get referenciaRol => _referenciaRol;

  set codigoMunicipio(String? v) {
    if (v == _codigoMunicipio) return;
    _codigoMunicipio = v;
    _idLugar = null; // el lugar pertenece al municipio anterior
    notifyListeners();
  }

  set idLugar(String? v) => _cambiar(() => _idLugar = v);
  set referenciaRol(String? v) => _cambiar(() => _referenciaRol = v);
  set consentimiento(bool v) => _cambiar(() {
        _consentimiento = v;
        if (!v) _gps = null; // sin consentimiento no se conserva el GPS
      });

  void fijarGps(Coordenada p, Municipio? municipio) => _cambiar(() {
        _gps = p;
        if (municipio != null && municipio.codigo != _codigoMunicipio) {
          _codigoMunicipio = municipio.codigo;
          _idLugar = null;
        }
      });

  void quitarGps() => _cambiar(() => _gps = null);

  void _cambiar(VoidCallback f) {
    f();
    notifyListeners();
  }

  /// La ubicación a guardar, o null si no se eligió al menos el municipio.
  UbicacionCapturada? capturada() => _codigoMunicipio == null
      ? null
      : UbicacionCapturada(
          codigoMunicipio: _codigoMunicipio!,
          idLugar: _idLugar,
          gps: _consentimiento ? _gps : null,
          consentimiento: _consentimiento,
          referenciaRol: _referenciaRol,
          referenciaApodo: apodo.text.trim().isEmpty ? null : apodo.text.trim(),
        );

  @override
  void dispose() {
    apodo.dispose();
    super.dispose();
  }
}

class SeccionUbicacion extends StatefulWidget {
  const SeccionUbicacion({super.key, required this.control, required this.geografia, required this.atendidoPor,
      this.obtenerPosicion = posicionDelDispositivo});

  final ControlUbicacion control;
  final Geografia geografia;

  /// Quién atiende: médico y enfermería pueden registrar el GPS exacto.
  final String? atendidoPor;
  final ObtenerPosicion obtenerPosicion;

  @override
  State<SeccionUbicacion> createState() => _EstadoSeccionUbicacion();
}

class _EstadoSeccionUbicacion extends State<SeccionUbicacion> {
  var _buscando = false;
  String? _aviso;

  ControlUbicacion get _c => widget.control;
  Geografia get _geo => widget.geografia;

  Future<void> _usarMiUbicacion() async {
    setState(() {
      _buscando = true;
      _aviso = null;
    });
    try {
      final p = await widget.obtenerPosicion();
      final municipio = _geo.municipioEn(p);
      _c.fijarGps(p, municipio);
      if (municipio == null) _aviso = 'La ubicación queda fuera de La Guajira y el Cesar: elija el municipio en la lista.';
    } catch (e) {
      _aviso = e is _AvisoUbicacion ? e.mensaje : 'No se pudo tomar la ubicación. Puede elegir el lugar en la lista.';
    } finally {
      if (mounted) setState(() => _buscando = false);
    }
  }

  String _km(double km) => km < 10 ? km.toStringAsFixed(1).replaceAll('.', ',') : km.round().toString();

  /// «A 12 km de la cabecera de Uribia (aproximado)»: referencia de apoyo, no entra al modelo.
  String? _distancia() {
    final codigo = _c.codigoMunicipio;
    if (codigo == null) return null;
    final punto = _c.gps ?? _geo.lugar(_c.idLugar)?.posicion;
    if (punto == null) return null;
    final (cabecera, km) = _geo.cabeceraMasCercana(punto)!;
    return 'A ${_km(km)} km en línea recta de la ${cabecera.nombre.replaceFirst('Cabecera', 'cabecera')} '
        '(referencia aproximada de la IPS más cercana).';
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
        listenable: _c,
        builder: (context, _) {
          final conGps = puedeUsarGps(widget.atendidoPor ?? '');
          final codigo = _c.codigoMunicipio;
          final distancia = _distancia();
          return Card(
            clipBehavior: Clip.antiAlias,
            child: ExpansionTile(
              key: const ValueKey('seccion-ubicacion'),
              shape: const Border(),
              leading: Icon(Icons.place_rounded, color: ColoresMaterna.ciruela700),
              title: const Text('Ubicación para la visita', style: TextStyle(fontWeight: FontWeight.w700)),
              subtitle: Text(
                  codigo == null ? 'Opcional · ayuda a encontrarla después' : 'Opcional · ${_geo.municipios[codigo]!.nombre}',
                  style: TextStyle(color: ColoresMaterna.tintaSuave, fontSize: 12.5)),
              childrenPadding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
              expandedCrossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text('No cambia el resultado: solo sirve para encontrarla y organizar las visitas.',
                    style: TextStyle(color: ColoresMaterna.tintaSuave, fontSize: 13)),
                const SizedBox(height: 14),
                KeyedSubtree(
                  key: ValueKey('municipio-$codigo'),
                  child: CampoLista(
                    nombre: 'ubicacion_municipio',
                    etiqueta: 'Municipio',
                    opciones: {for (final m in _geo.ordenados) m.codigo: '${m.nombre} (${m.departamento})'},
                    valor: codigo,
                    alCambiar: (v) => _c.codigoMunicipio = v,
                  ),
                ),
                if (codigo != null) ...[
                  const SizedBox(height: 14),
                  KeyedSubtree(
                    key: ValueKey('lugar-$codigo-${_c.idLugar}'),
                    child: CampoLista(
                      nombre: 'ubicacion_lugar',
                      etiqueta: 'Ranchería, vereda o resguardo',
                      opciones: {for (final l in _geo.lugaresDe(codigo)) l.id: l.nombre},
                      valor: _c.idLugar,
                      alCambiar: (v) => _c.idLugar = v,
                    ),
                  ),
                ],
                const SizedBox(height: 14),
                if (conGps) ...[
                  CheckboxListTile(
                    key: const Key('ubicacion_consentimiento'),
                    contentPadding: EdgeInsets.zero,
                    controlAffinity: ListTileControlAffinity.leading,
                    value: _c.consentimiento,
                    onChanged: (v) => _c.consentimiento = v ?? false,
                    title: const Text('La gestante autoriza registrar su ubicación exacta'),
                    subtitle: const Text('Sin este permiso solo se guarda el municipio y el lugar.'),
                  ),
                  if (_c.gps == null)
                    OutlinedButton.icon(
                      key: const Key('usar_mi_ubicacion'),
                      onPressed: _c.consentimiento && !_buscando ? _usarMiUbicacion : null,
                      icon: _buscando
                          ? const SizedBox.square(dimension: 18, child: CircularProgressIndicator(strokeWidth: 2))
                          : const Icon(Icons.my_location_rounded),
                      label: Text(_buscando ? 'Buscando la ubicación…' : 'Usar mi ubicación'),
                    )
                  else
                    Row(children: [
                      Icon(Icons.check_circle_rounded, color: ColoresMaterna.ciruela700, size: 20),
                      const SizedBox(width: 8),
                      const Expanded(child: Text('Ubicación exacta tomada')),
                      TextButton(onPressed: _c.quitarGps, child: const Text('Quitar')),
                    ]),
                ] else
                  Text('Su cuenta registra la ubicación por ranchería, vereda o resguardo. La ubicación exacta la '
                      'registran médico o enfermería, con el permiso de la gestante.',
                      key: const Key('ubicacion_sin_gps'), style: TextStyle(color: ColoresMaterna.tintaSuave, fontSize: 13)),
                if (_aviso != null) ...[const SizedBox(height: 8), TextoError(_aviso)],
                if (distancia != null) ...[
                  const SizedBox(height: 10),
                  Text(distancia, key: const Key('ubicacion_distancia'), style: TextStyle(color: ColoresMaterna.tintaSuave, fontSize: 13)),
                ],
                const SizedBox(height: 18),
                CampoLista(
                  nombre: 'ubicacion_referencia',
                  etiqueta: 'Referencia comunitaria',
                  opciones: {for (final r in rolesReferencia) r: r},
                  valor: _c.referenciaRol,
                  alCambiar: (v) => _c.referenciaRol = v,
                ),
                const SizedBox(height: 10),
                TextField(
                  key: const Key('ubicacion_apodo'),
                  controller: _c.apodo,
                  maxLength: largoMaximoApodo,
                  decoration: const InputDecoration(
                      labelText: 'Cómo la reconocen (opcional)', helperText: 'Un apodo; sin apellidos, documentos ni teléfonos'),
                ),
              ],
            ),
          );
        },
      );
}
