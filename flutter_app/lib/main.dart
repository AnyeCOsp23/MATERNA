// MATERNA · Módulo 2: aplicación de usuario final (web y móvil) para el personal de salud en territorio.
//
// Carga una vez lo que entrega el Módulo 1 (modelo, preprocesamiento, reglas y catálogo 3280), abre la base
// local del dispositivo mientras muestra la pantalla de inicio animada, y pide usuario y PIN antes de la pantalla
// principal (varias personas pueden compartir el dispositivo, cada una con su cuenta). Todo corre sin internet.
// La sesión no se recuerda al cerrar la app: al volver a abrirla se pide el PIN de nuevo.
import 'package:flutter/material.dart';

import 'datos/base_local.dart';
import 'datos/fabrica_bd.dart';
import 'motor/recursos.dart';
import 'ui/pantallas/pantalla_acceso.dart';
import 'ui/pantallas/pantalla_inicio.dart';
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
      home: _Arranque(inicio: inicio ?? _iniciar()),
    );
  }
}

/// Pantalla de inicio animada mientras se cargan el modelo y la base; después, el acceso con PIN.
///
/// La pantalla de inicio sigue visible (con el logo ya en su lugar) hasta que la carga termine: en un teléfono
/// lento no aparece ninguna pantalla intermedia entre el logo y el PIN.
class _Arranque extends StatefulWidget {
  const _Arranque({required this.inicio});

  final Future<(RecursosMaterna, BaseLocal)> inicio;

  @override
  State<_Arranque> createState() => _EstadoArranque();
}

class _EstadoArranque extends State<_Arranque> {
  var _animacionTerminada = false;
  (RecursosMaterna, BaseLocal)? _listo;
  Object? _error;

  @override
  void initState() {
    super.initState();
    widget.inicio.then(
      (listo) => mounted ? setState(() => _listo = listo) : null,
      onError: (Object e) => mounted ? setState(() => _error = e) : null,
    );
  }

  @override
  Widget build(BuildContext context) {
    final listo = _listo;
    final Widget pantalla;
    if (!_animacionTerminada || (listo == null && _error == null)) {
      pantalla = PantallaInicio(key: const ValueKey('inicio'), alTerminar: () => setState(() => _animacionTerminada = true));
    } else if (listo == null) {
      pantalla = _Mensaje('No se pudo iniciar MATERNA: $_error');
    } else {
      pantalla = _Sesion(recursos: listo.$1, base: listo.$2);
    }
    return AnimatedSwitcher(duration: const Duration(milliseconds: 350), child: pantalla);
  }
}

/// Sin sesión iniciada muestra el acceso (usuario y PIN); con sesión, la pantalla principal. Cerrar sesión vuelve
/// al acceso en blanco, para que otra persona pueda entrar con su cuenta.
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
