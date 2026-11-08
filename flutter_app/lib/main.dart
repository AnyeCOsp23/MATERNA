// MATERNA · Módulo 2: aplicación de usuario final (web y móvil) para el personal de salud en territorio.
//
// Carga una vez lo que entrega el Módulo 1 (modelo, preprocesamiento, reglas y catálogo 3280) y abre la
// pantalla principal con la barra de navegación flotante. Todo corre en el dispositivo, sin internet.
import 'package:flutter/material.dart';

import 'motor/recursos.dart';
import 'ui/pantallas/pantalla_principal.dart';
import 'ui/tema/tema_materna.dart';

void main() {
  runApp(const MaternaApp());
}

class MaternaApp extends StatelessWidget {
  const MaternaApp({super.key, this.recursos});

  /// Permite inyectar los recursos (las pruebas los leen de los archivos en lugar del bundle).
  final Future<RecursosMaterna>? recursos;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'MATERNA',
      debugShowCheckedModeBanner: false,
      theme: temaMaterna(),
      home: FutureBuilder<RecursosMaterna>(
        future: recursos ?? RecursosMaterna.cargar(),
        builder: (context, estado) => switch (estado) {
          AsyncSnapshot(:final data?) => PantallaPrincipal(recursos: data),
          AsyncSnapshot(hasError: true) => _Mensaje('No se pudo cargar el modelo: ${estado.error}'),
          _ => const _Mensaje('Cargando el modelo…'),
        },
      ),
    );
  }
}

class _Mensaje extends StatelessWidget {
  const _Mensaje(this.texto);

  final String texto;

  @override
  Widget build(BuildContext context) => Scaffold(
        body: Center(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Text('MATERNA',
                style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                    fontWeight: FontWeight.w800, color: ColoresMaterna.ciruela900)),
            const SizedBox(height: 8),
            Text(texto),
          ]),
        ),
      );
}
