// MATERNA · Módulo 2: aplicación de usuario final (web y móvil) para el personal de salud en territorio.
//
// Carga una vez lo que entrega el Módulo 1 (modelo, preprocesamiento, reglas y catálogo 3280), abre la base
// local del dispositivo y pide el PIN del operador antes de la pantalla principal. Todo corre sin internet.
// La sesión no se recuerda al cerrar la app: al volver a abrirla se pide el PIN de nuevo.
import 'package:flutter/material.dart';

import 'datos/base_local.dart';
import 'datos/fabrica_bd.dart';
import 'motor/recursos.dart';
import 'ui/pantallas/pantalla_acceso.dart';
import 'ui/pantallas/pantalla_principal.dart';
import 'ui/tema/tema_materna.dart';

void main() {
  runApp(const MaternaApp());
}

Future<(RecursosMaterna, BaseLocal)> _iniciar() async =>
    (await RecursosMaterna.cargar(), await BaseLocal.abrir(fabricaBaseLocal(), rutaBaseLocal));

class MaternaApp extends StatelessWidget {
  const MaternaApp({super.key, this.inicio});

  /// Permite inyectar los recursos y la base (las pruebas usan los archivos y una base en memoria).
  final Future<(RecursosMaterna, BaseLocal)>? inicio;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'MATERNA',
      debugShowCheckedModeBanner: false,
      theme: temaMaterna(),
      home: FutureBuilder<(RecursosMaterna, BaseLocal)>(
        future: inicio ?? _iniciar(),
        builder: (context, estado) => switch (estado) {
          AsyncSnapshot(:final data?) => _Sesion(recursos: data.$1, base: data.$2),
          AsyncSnapshot(hasError: true) => _Mensaje('No se pudo iniciar MATERNA: ${estado.error}'),
          _ => const _Mensaje('Cargando el modelo…'),
        },
      ),
    );
  }
}

/// Sin perfil activo muestra el acceso por PIN; con perfil, la pantalla principal.
class _Sesion extends StatefulWidget {
  const _Sesion({required this.recursos, required this.base});

  final RecursosMaterna recursos;
  final BaseLocal base;

  @override
  State<_Sesion> createState() => _EstadoSesion();
}

class _EstadoSesion extends State<_Sesion> {
  Perfil? _perfil;

  @override
  Widget build(BuildContext context) => _perfil == null
      ? PantallaAcceso(base: widget.base, alEntrar: (p) => setState(() => _perfil = p))
      : PantallaPrincipal(
          recursos: widget.recursos,
          base: widget.base,
          perfil: _perfil!,
          alCerrarSesion: () => setState(() => _perfil = null),
        );
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
