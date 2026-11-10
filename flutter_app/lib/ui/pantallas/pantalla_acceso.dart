/// Acceso local al Módulo 2, sin servidor ni señal celular.
///
/// La primera vez se crea el perfil del operador (quién atiende, IPS y municipio) y un PIN de 4 dígitos.
/// Después, un teclado numérico táctil pide el PIN. Tras 5 intentos fallidos se bloquea 30 s. Si se olvida el
/// PIN no hay de dónde recuperarlo: se puede reiniciar el dispositivo, lo que borra el perfil y las evaluaciones.
library;

import 'package:flutter/material.dart';

import '../../datos/base_local.dart';
import '../../datos/seguridad.dart';
import '../tema/tema_materna.dart';
import '../widgets/campos.dart';
import 'pantalla_triaje.dart' show atiende;

class PantallaAcceso extends StatefulWidget {
  const PantallaAcceso({super.key, required this.base, required this.alEntrar});

  final BaseLocal base;
  final ValueChanged<Perfil> alEntrar;

  @override
  State<PantallaAcceso> createState() => _EstadoAcceso();
}

class _EstadoAcceso extends State<PantallaAcceso> {
  late Future<bool> _configurado = widget.base.tienePin();

  void _recargar() => setState(() {
        _configurado = widget.base.tienePin();
      });

  @override
  Widget build(BuildContext context) => FutureBuilder<bool>(
        future: _configurado,
        builder: (context, estado) => Scaffold(
          body: SafeArea(
            child: Center(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(24),
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 420),
                  child: switch (estado.data) {
                    null => const CircularProgressIndicator(),
                    false => _Configurar(base: widget.base, alTerminar: _recargar),
                    true => _Pin(base: widget.base, alEntrar: widget.alEntrar, alReiniciar: _recargar),
                  },
                ),
              ),
            ),
          ),
        ),
      );
}

class _Marca extends StatelessWidget {
  const _Marca(this.subtitulo);

  final String subtitulo;

  @override
  Widget build(BuildContext context) => Column(children: [
        Image.asset('assets/logo_isotipo.webp', width: 72, height: 72),
        const SizedBox(height: 10),
        const Text('MATERNA',
            style: TextStyle(fontSize: 28, fontWeight: FontWeight.w900, color: ColoresMaterna.ciruela900, letterSpacing: -.6)),
        const SizedBox(height: 4),
        Text(subtitulo, textAlign: TextAlign.center, style: const TextStyle(color: ColoresMaterna.tintaSuave)),
      ]);
}

// ------------------------------------------------------------------ primera vez: perfil y PIN
class _Configurar extends StatefulWidget {
  const _Configurar({required this.base, required this.alTerminar});

  final BaseLocal base;
  final VoidCallback alTerminar;

  @override
  State<_Configurar> createState() => _EstadoConfigurar();
}

class _EstadoConfigurar extends State<_Configurar> {
  final _ips = TextEditingController();
  final _municipio = TextEditingController();
  final _pin = TextEditingController();
  final _pin2 = TextEditingController();
  String? _atiende;
  var _errores = <String, String>{};

  @override
  void dispose() {
    for (final c in [_ips, _municipio, _pin, _pin2]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _crear() async {
    final errores = <String, String>{
      if (_atiende == null) 'atendido_por': 'Elija una opción.',
      if (_ips.text.trim().isEmpty) 'ips': 'Escriba la IPS o el puesto de salud.',
      if (!pinValido(_pin.text)) 'pin': 'El PIN debe tener 4 dígitos.',
      if (pinValido(_pin.text) && _pin.text != _pin2.text) 'pin2': 'Los PIN no coinciden.',
    };
    setState(() => _errores = errores);
    if (errores.isNotEmpty) return;
    await widget.base.configurar(
      pin: _pin.text,
      perfil: Perfil(
        atendidoPor: _atiende!,
        ips: _ips.text.trim(),
        municipio: _municipio.text.trim().isEmpty ? null : _municipio.text.trim(),
      ),
    );
    widget.alTerminar();
  }

  Widget _texto(String clave, String etiqueta, TextEditingController c, {bool pin = false, String? ayuda}) =>
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Etiqueta(etiqueta, ayuda: ayuda),
        TextField(
          key: Key('campo-$clave'),
          controller: c,
          obscureText: pin,
          maxLength: pin ? 4 : null,
          keyboardType: pin ? TextInputType.number : TextInputType.text,
          decoration: InputDecoration(counterText: '', errorText: _errores[clave]),
        ),
      ]);

  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        const _Marca('Configure este dispositivo. Los datos quedan solo aquí: no se necesita internet.'),
        const SizedBox(height: 24),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              CampoLista(
                nombre: 'atendido_por',
                etiqueta: 'Quién atiende',
                opciones: atiende,
                valor: _atiende,
                error: _errores['atendido_por'],
                alCambiar: (v) => setState(() => _atiende = v),
              ),
              const SizedBox(height: 16),
              _texto('ips', 'IPS o puesto de salud', _ips),
              const SizedBox(height: 16),
              _texto('municipio', 'Municipio', _municipio, ayuda: 'opcional'),
              const SizedBox(height: 16),
              _texto('pin', 'PIN de 4 dígitos', _pin, pin: true),
              const SizedBox(height: 16),
              _texto('pin2', 'Repita el PIN', _pin2, pin: true),
            ]),
          ),
        ),
        const SizedBox(height: 20),
        FilledButton.icon(
          key: const Key('crear-acceso'),
          onPressed: _crear,
          icon: const Icon(Icons.lock_outline_rounded),
          label: const Text('Crear acceso'),
        ),
        const SizedBox(height: 12),
        const Text('Si olvida el PIN, la app se puede reiniciar, pero se borran las evaluaciones guardadas en el dispositivo.',
            textAlign: TextAlign.center, style: TextStyle(color: ColoresMaterna.tintaSuave, fontSize: 12.5)),
      ]);
}

// ------------------------------------------------------------------ PIN con teclado numérico
class _Pin extends StatefulWidget {
  const _Pin({required this.base, required this.alEntrar, required this.alReiniciar});

  final BaseLocal base;
  final ValueChanged<Perfil> alEntrar;
  final VoidCallback alReiniciar;

  @override
  State<_Pin> createState() => _EstadoPin();
}

class _EstadoPin extends State<_Pin> {
  var _pin = '';
  String? _mensaje;
  Perfil? _perfil;
  var _verificando = false;

  @override
  void initState() {
    super.initState();
    widget.base.perfil().then((p) => mounted ? setState(() => _perfil = p) : null);
  }

  Future<void> _tecla(String t) async {
    if (_verificando) return;
    setState(() {
      _mensaje = null;
      if (t == 'borrar') {
        if (_pin.isNotEmpty) _pin = _pin.substring(0, _pin.length - 1);
      } else if (_pin.length < 4) {
        _pin += t;
      }
    });
    if (_pin.length < 4) return;
    _verificando = true;
    final espera = await widget.base.segundosDeBloqueo();
    final correcto = espera == 0 && await widget.base.verificar(_pin);
    _verificando = false;
    if (!mounted) return;
    if (correcto) {
      widget.alEntrar((await widget.base.perfil())!);
      return;
    }
    final bloqueo = await widget.base.segundosDeBloqueo();
    setState(() {
      _pin = '';
      _mensaje = bloqueo > 0 ? 'Demasiados intentos. Espere $bloqueo s.' : 'PIN incorrecto.';
    });
  }

  Future<void> _olvide() async {
    final confirmar = await showDialog<bool>(
      context: context,
      builder: (contexto) => AlertDialog(
        title: const Text('¿Reiniciar el dispositivo?'),
        content: const Text('No hay servidor desde el cual recuperar el PIN. Para crear uno nuevo se borrarán el perfil '
            'y TODAS las evaluaciones guardadas en este dispositivo. No se puede deshacer.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(contexto, false), child: const Text('Cancelar')),
          FilledButton(
            key: const Key('confirmar-reinicio'),
            style: FilledButton.styleFrom(minimumSize: const Size(0, 44)),
            onPressed: () => Navigator.pop(contexto, true),
            child: const Text('Borrar y reiniciar'),
          ),
        ],
      ),
    );
    if (confirmar != true) return;
    await widget.base.borrarTodo();
    widget.alReiniciar();
  }

  @override
  Widget build(BuildContext context) {
    final operador = _perfil == null ? '' : '${atiende[_perfil!.atendidoPor] ?? _perfil!.atendidoPor} · ${_perfil!.ips}';
    return Column(children: [
      _Marca(operador.isEmpty ? 'Ingrese su PIN' : 'Ingrese su PIN\n$operador'),
      const SizedBox(height: 26),
      Row(mainAxisAlignment: MainAxisAlignment.center, children: [
        for (var i = 0; i < 4; i++)
          AnimatedContainer(
            duration: const Duration(milliseconds: 180),
            margin: const EdgeInsets.symmetric(horizontal: 9),
            width: 16,
            height: 16,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: i < _pin.length ? ColoresMaterna.ciruela900 : Colors.transparent,
              border: Border.all(color: ColoresMaterna.ciruela900, width: 1.6),
            ),
          ),
      ]),
      SizedBox(
        height: 36,
        child: Center(
          child: Text(_mensaje ?? '', key: const Key('mensaje-pin'),
              style: TextStyle(color: Theme.of(context).colorScheme.error, fontWeight: FontWeight.w600)),
        ),
      ),
      for (final fila in const [['1', '2', '3'], ['4', '5', '6'], ['7', '8', '9'], ['', '0', 'borrar']])
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 7),
          child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
            for (final t in fila)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 12),
                child: t.isEmpty
                    ? const SizedBox(width: 72, height: 72)
                    : SizedBox(
                        width: 72,
                        height: 72,
                        child: Material(
                          color: t == 'borrar' ? Colors.transparent : Colors.white,
                          shape: const CircleBorder(side: BorderSide(color: ColoresMaterna.borde)),
                          child: InkWell(
                            key: Key('tecla-$t'),
                            customBorder: const CircleBorder(),
                            onTap: () => _tecla(t),
                            child: Center(
                              child: t == 'borrar'
                                  ? const Icon(Icons.backspace_outlined, color: ColoresMaterna.tintaSuave, semanticLabel: 'Borrar')
                                  : Text(t, style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w500, color: ColoresMaterna.tinta)),
                            ),
                          ),
                        ),
                      ),
              ),
          ]),
        ),
      const SizedBox(height: 14),
      TextButton(key: const Key('olvide-pin'), onPressed: _olvide, child: const Text('¿Olvidó el PIN?')),
    ]);
  }
}
