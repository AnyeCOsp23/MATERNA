/// Pantalla principal del Módulo 2: las cuatro pestañas bajo la barra de navegación flotante.
///
///   1 Triaje individual · 2 Carga masiva IPS · 3 Historial local · 4 Acerca de
///
/// Cada pestaña conserva su estado al cambiar de una a otra (un triaje a medio llenar no se pierde).
/// Cada evaluación se guarda en la base local al mostrar su resultado y aparece en el historial.
library;

import 'package:flutter/material.dart';

import '../../datos/base_local.dart';
import '../../motor/recursos.dart';
import '../tema/tema_materna.dart';
import '../widgets/barra_flotante.dart';
import '../widgets/iconos_trazo.dart';
import 'pantalla_acerca_de.dart';
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
  });

  final RecursosMaterna recursos;
  final BaseLocal base;
  final Perfil perfil;
  final VoidCallback alCerrarSesion;

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

  Future<void> _guardar(Evaluacion evaluacion) async {
    await widget.base.guardar(
      evaluacion,
      perfil: widget.perfil,
      versionModelo: widget.recursos.clasificador.version,
      categoria: widget.recursos.clasificador.clases[evaluacion.clase],
    );
    _cambios.value++;
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        extendBody: true, // el contenido pasa por detrás de la barra flotante
        body: IndexedStack(index: _pestana, children: [
          PantallaTriaje(recursos: widget.recursos, atendidoPor: widget.perfil.atendidoPor, alGuardar: _guardar),
          const _Pendiente(
            icono: Icons.note_add_rounded,
            titulo: 'Carga masiva IPS',
            texto: 'Aquí se cargarán los archivos de la IPS con la plantilla de la Resolución 3280 (CSV, TXT con «|» o '
                'Excel): seudonimización del documento, triaje de todas las gestantes ordenado por urgencia y '
                'exportación a CSV.',
          ),
          PantallaHistorial(recursos: widget.recursos, base: widget.base, cambios: _cambios),
          PantallaAcercaDe(recursos: widget.recursos, perfil: widget.perfil, alCerrarSesion: widget.alCerrarSesion),
        ]),
        bottomNavigationBar: BarraFlotante(
          destinos: destinos,
          indice: _pestana,
          alCambiar: (i) => setState(() => _pestana = i),
        ),
      );
}

/// Pestaña que se completa en la siguiente entrega del Módulo 2.
class _Pendiente extends StatelessWidget {
  const _Pendiente({required this.icono, required this.titulo, required this.texto});

  final IconData icono;
  final String titulo;
  final String texto;

  @override
  Widget build(BuildContext context) => SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 520),
            child: Padding(
              padding: const EdgeInsets.fromLTRB(28, 24, 28, BarraFlotante.espacioInferior),
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                Container(
                  width: 72,
                  height: 72,
                  decoration: BoxDecoration(color: ColoresMaterna.ciruela100, borderRadius: BorderRadius.circular(22)),
                  child: Icon(icono, size: 36, color: ColoresMaterna.ciruela900),
                ),
                const SizedBox(height: 18),
                Text(titulo, style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
                const SizedBox(height: 8),
                Text(texto, textAlign: TextAlign.center, style: const TextStyle(color: ColoresMaterna.tintaSuave, height: 1.5)),
                const SizedBox(height: 14),
                const Chip(label: Text('En la siguiente entrega del Módulo 2'), avatar: Icon(Icons.schedule_rounded, size: 18)),
              ]),
            ),
          ),
        ),
      );
}
