/// Pantalla principal del Módulo 2: las cuatro pestañas bajo la barra de navegación flotante.
///
///   1 Triaje individual · 2 Carga masiva IPS · 3 Historial local · 4 Acerca de
///
/// Cada pestaña conserva su estado al cambiar de una a otra (un triaje a medio llenar no se pierde).
/// Cada evaluación (individual o de una carga masiva) se guarda en la base local y aparece en el historial.
library;

import 'package:flutter/material.dart';

import '../../datos/base_local.dart';
import '../../datos/ubicaciones.dart';
import '../../motor/recursos.dart';
import '../tema/tema_materna.dart';
import '../widgets/avatar.dart';
import '../widgets/barra_flotante.dart';
import '../widgets/iconos_trazo.dart';
import 'pantalla_acerca_de.dart';
import 'pantalla_carga.dart';
import 'pantalla_historial.dart';
import 'pantalla_triaje.dart';

final destinos = [
  DestinoBarra(icono: (c) => IconoDeTrazo(IconoTrazo.estetoscopio, color: c), etiqueta: 'Triaje'),
  DestinoBarra(icono: (c) => IconoDeTrazo(IconoTrazo.subirArchivo, color: c), etiqueta: 'Carga IPS'),
  DestinoBarra(icono: (c) => IconoDeTrazo(IconoTrazo.baseDatos, color: c), etiqueta: 'Historial'),
  DestinoBarra(icono: (c) => IconoDeTrazo(IconoTrazo.informacion, color: c), etiqueta: 'Acerca de'),
];

class PantallaPrincipal extends StatefulWidget {
  const PantallaPrincipal({
    super.key,
    required this.recursos,
    required this.base,
    required this.perfil,
    required this.alCerrarSesion,
    this.elegirArchivo,
    this.guardarArchivo,
  });

  final RecursosMaterna recursos;
  final BaseLocal base;
  final Perfil perfil;
  final VoidCallback alCerrarSesion;

  /// Reemplazan el selector de archivos del sistema en la carga masiva (para las pruebas).
  final ElegirArchivo? elegirArchivo;
  final GuardarArchivo? guardarArchivo;

  @override
  State<PantallaPrincipal> createState() => _EstadoPrincipal();
}

class _EstadoPrincipal extends State<PantallaPrincipal> {
  var _pestana = 0;
  final _cambios = ValueNotifier(0); // avisa al historial que hay una evaluación nueva

  @override
  void dispose() {
    _cambios.dispose();
    super.dispose();
  }

  Future<void> _guardar(Evaluacion evaluacion, UbicacionCapturada? ubicacion) async {
    final id = await widget.base.guardar(
      evaluacion,
      perfil: widget.perfil,
      versionModelo: widget.recursos.clasificador.version,
      categoria: widget.recursos.clasificador.clases[evaluacion.clase],
    );
    if (ubicacion != null) await widget.base.guardarUbicacion(id, ubicacion, perfil: widget.perfil);
    _cambios.value++;
  }

  @override
  Widget build(BuildContext context) => AvatarSesion(
        indice: widget.perfil.avatar,
        child: Scaffold(
        extendBody: true, // el contenido pasa por detrás de la barra flotante
        body: DecoratedBox(
          decoration: fondoCrema,
          child: IndexedStack(index: _pestana, children: [
          PantallaTriaje(recursos: widget.recursos, atendidoPor: widget.perfil.atendidoPor, municipio: widget.perfil.municipio,
              alGuardar: _guardar),
          PantallaCarga(
            recursos: widget.recursos,
            base: widget.base,
            perfil: widget.perfil,
            alGuardar: () => _cambios.value++,
            elegirArchivo: widget.elegirArchivo,
            guardarArchivo: widget.guardarArchivo,
          ),
          PantallaHistorial(recursos: widget.recursos, base: widget.base, cambios: _cambios, idUsuario: widget.perfil.id),
          PantallaAcercaDe(recursos: widget.recursos, perfil: widget.perfil, alCerrarSesion: widget.alCerrarSesion),
          ]),
        ),
        bottomNavigationBar: BarraFlotante(
          destinos: destinos,
          indice: _pestana,
          alCambiar: (i) => setState(() => _pestana = i),
        ),
      ),
      );
}
