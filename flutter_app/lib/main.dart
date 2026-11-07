// MATERNA · Módulo 2: aplicación de usuario final (web y móvil) para el personal de salud en territorio.
//
// Parte 4a: solo el motor de inferencia offline (lib/motor/) y su prueba de paridad. Esta pantalla
// mínima carga el modelo que entrega el Módulo 1 y muestra su versión; las pantallas de captura,
// resultado y carga masiva llegan en las partes 4b y 4c.
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'motor/clasificador.dart';

Future<ClasificadorMaterna> cargarMotor() async => ClasificadorMaterna.desdeTexto(
      await rootBundle.loadString('assets/preproceso.json'),
      await rootBundle.loadString('assets/modelo_rf.json'),
      await rootBundle.loadString('assets/reglas.json'),
    );

void main() {
  runApp(const MaternaApp());
}

class MaternaApp extends StatelessWidget {
  const MaternaApp({super.key, this.motor});

  /// Permite inyectar el motor (las pruebas no cargan los 918 KB del modelo).
  final Future<ClasificadorMaterna>? motor;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'MATERNA',
      theme: ThemeData(colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF7D2F5F))),
      home: Scaffold(
        body: Center(
          child: FutureBuilder<ClasificadorMaterna>(
            future: motor ?? cargarMotor(),
            builder: (context, estado) {
              final texto = switch (estado) {
                AsyncSnapshot(hasError: true) => 'No se pudo cargar el modelo: ${estado.error}',
                AsyncSnapshot(:final data?) => 'Motor offline listo · modelo ${data.version} · ${data.arboles.length} árboles',
                _ => 'Cargando el modelo…',
              };
              return Column(mainAxisSize: MainAxisSize.min, children: [
                Text('MATERNA', style: Theme.of(context).textTheme.headlineMedium),
                const SizedBox(height: 8),
                Text(texto),
              ]);
            },
          ),
        ),
      ),
    );
  }
}
