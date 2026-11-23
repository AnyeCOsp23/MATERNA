/// Acceso local al Módulo 2, sin servidor ni señal celular. Varias personas pueden usar el mismo dispositivo.
///
///   Iniciar sesión: usuario y PIN de 4 dígitos (5 intentos fallidos bloquean esa cuenta 30 s).
///   Registrarse: usuario, quién atiende, IPS o puesto, municipio y PIN; al terminar se muestra una sola vez el
///     código de recuperación.
///   ¿Olvidó el PIN?: PIN nuevo con el código de recuperación; si también se perdió, el responsable de datos lo
///     pone con la clave de la IPS; como último recurso se elimina solo esa cuenta.
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../datos/base_local.dart';
import '../../datos/seguridad.dart';
import '../tema/tema_materna.dart';
import '../widgets/ambito_preferencias.dart';
import '../widgets/avatar.dart';
import '../widgets/campos.dart';
import 'pantalla_triaje.dart' show atiende;

enum _Vista { entrar, registrarse, recuperar, codigo }

class PantallaAcceso extends StatefulWidget {
  const PantallaAcceso({super.key, required this.base, required this.alEntrar});

  final BaseLocal base;
  final ValueChanged<Perfil> alEntrar;

  @override
  State<PantallaAcceso> createState() => _EstadoAcceso();
}

class _EstadoAcceso extends State<PantallaAcceso> {
  var _vista = _Vista.entrar;

  /// Código de recuperación recién creado y a dónde ir después de mostrarlo.
  String? _codigo;
  Perfil? _entrarTras;
  String? _avisoEntrar;
  String _usuario = '';

  void _ir(_Vista vista, {String? aviso}) => setState(() {
    _vista = vista;
    _avisoEntrar = aviso;
  });

  void _mostrarCodigo(String codigo, {Perfil? entrar, required String usuario}) => setState(() {
    _codigo = codigo;
    _entrarTras = entrar;
    _usuario = usuario;
    _vista = _Vista.codigo;
  });

  @override
  Widget build(BuildContext context) => Scaffold(
    backgroundColor: ColoresMaterna.tarjeta, // acceso en blanco (en oscuro, del color de las tarjetas)
    body: SafeArea(
      child: Column(
        children: [
          Expanded(
            child: Center(
              child: SingleChildScrollView(
                padding: const EdgeInsets.fromLTRB(24, 24, 24, 24),
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 420),
                  child: AnimatedSwitcher(
                    duration: const Duration(milliseconds: 250),
                    child: switch (_vista) {
                      _Vista.entrar => _Entrar(
                        key: const ValueKey('vista-entrar'),
                        base: widget.base,
                        usuarioInicial: _usuario,
                        aviso: _avisoEntrar,
                        alEntrar: widget.alEntrar,
                        alRegistrarse: () => _ir(_Vista.registrarse),
                        alOlvidar: (usuario) => setState(() {
                          _usuario = usuario;
                          _vista = _Vista.recuperar;
                        }),
                      ),
                      _Vista.registrarse => _Registrarse(
                        key: const ValueKey('vista-registrarse'),
                        base: widget.base,
                        alVolver: () => _ir(_Vista.entrar),
                        alCrear: (perfil, codigo) => _mostrarCodigo(codigo, entrar: perfil, usuario: perfil.usuario!),
                      ),
                      _Vista.recuperar => _Recuperar(
                        key: const ValueKey('vista-recuperar'),
                        base: widget.base,
                        usuarioInicial: _usuario,
                        alVolver: () => _ir(_Vista.entrar),
                        alRestablecer: (usuario, codigo) => _mostrarCodigo(codigo, usuario: usuario),
                        alEliminar: (usuario) {
                          _usuario = '';
                          _ir(_Vista.entrar, aviso: 'Se eliminó la cuenta «$usuario». Puede registrarse de nuevo.');
                        },
                      ),
                      _Vista.codigo => _Codigo(
                        key: const ValueKey('vista-codigo'),
                        codigo: _codigo!,
                        textoBoton: _entrarTras == null ? 'Ya lo anoté · iniciar sesión' : 'Ya lo anoté · entrar',
                        alContinuar: () => _entrarTras == null
                            ? _ir(_Vista.entrar, aviso: 'PIN cambiado. Inicie sesión con el PIN nuevo.')
                            : widget.alEntrar(_entrarTras!),
                      ),
                    },
                  ),
                ),
              ),
            ),
          ),
          // como en el mockup: el aviso va abajo, fijo, solo en «Iniciar sesión»
          if (_vista == _Vista.entrar)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 16),
              child: Center(
                child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 420), child: const _AvisoConexionPie()),
              ),
            ),
        ],
      ),
    ),
  );
}

// ------------------------------------------------------------------ piezas comunes
class _Marca extends StatelessWidget {
  const _Marca({required this.titulo, this.subtitulo, this.pie, this.grande = true, this.conNombre = true});

  final String titulo;
  final String? subtitulo;

  /// Algo que va bajo el título en lugar del subtítulo (p. ej. el aviso «Funciona sin conexión»).
  final Widget? pie;
  final bool grande;

  /// La palabra «MATERNA» bajo el logo (el inicio de sesión del mockup va solo con el isotipo).
  final bool conNombre;

  @override
  Widget build(BuildContext context) => Column(
    children: [
      Image.asset(
        'assets/logo_isotipo.webp',
        width: grande ? 104 : 64,
        height: grande ? 104 : 64,
        // en oscuro, el logo en rosa claro (la madre es transparente: se sigue viendo)
        color: ColoresMaterna.oscuro ? ColoresMaterna.vinoLogo : null,
        colorBlendMode: BlendMode.srcIn,
      ),
      if (conNombre)
        Text(
          'MATERNA',
          style: TextStyle(fontSize: 18, fontWeight: FontWeight.w400, color: ColoresMaterna.vinoLogo, letterSpacing: 4),
        ),
      SizedBox(height: conNombre ? (grande ? 26 : 16) : 12),
      Text(
        titulo,
        textAlign: TextAlign.center,
        style: TextStyle(fontSize: 26, fontWeight: FontWeight.w800, color: ColoresMaterna.tinta),
      ),
      if (subtitulo != null) ...[
        const SizedBox(height: 4),
        Text(
          subtitulo!,
          textAlign: TextAlign.center,
          style: TextStyle(color: ColoresMaterna.tintaSuave),
        ),
      ],
      if (pie != null) ...[const SizedBox(height: 10), pie!],
    ],
  );
}

/// Aviso al pie del inicio de sesión: «Funciona sin conexión» con un punto verde que titila unas veces al abrir la
/// pantalla y luego queda fijo (como el pulso del botón ⓘ: no distrae para siempre); con «reducir animaciones»,
/// quieto desde el principio.
class _AvisoConexionPie extends StatefulWidget {
  const _AvisoConexionPie();

  @override
  State<_AvisoConexionPie> createState() => _EstadoAvisoConexionPie();
}

class _EstadoAvisoConexionPie extends State<_AvisoConexionPie> with SingleTickerProviderStateMixin {
  static const _parpadeos = 6;
  var _cuenta = 0;
  late final AnimationController _brillo;

  @override
  void initState() {
    super.initState();
    _brillo = AnimationController(vsync: this, duration: const Duration(milliseconds: 650), value: 1)
      ..addStatusListener((estado) {
        if (estado == AnimationStatus.dismissed) {
          if (++_cuenta < _parpadeos) {
            _brillo.forward();
          } else {
            _brillo.value = 1; // termina encendido
          }
        } else if (estado == AnimationStatus.completed && _cuenta < _parpadeos) {
          _brillo.reverse();
        }
      });
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (MediaQuery.of(context).disableAnimations) {
      _brillo
        ..stop()
        ..value = 1;
    } else if (_cuenta == 0 && !_brillo.isAnimating) {
      _brillo.reverse();
    }
  }

  @override
  void dispose() {
    _brillo.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Container(
        key: const Key('aviso-sin-conexion-pie'),
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
        decoration: BoxDecoration(color: ColoresMaterna.sinConexionFondo, borderRadius: BorderRadius.circular(22)),
        child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
          FadeTransition(
            opacity: Tween<double>(begin: .3, end: 1).animate(CurvedAnimation(parent: _brillo, curve: Curves.easeInOut)),
            child: Container(
              key: const Key('aviso-sin-conexion-punto'),
              width: 11,
              height: 11,
              decoration: BoxDecoration(color: ColoresMaterna.sinConexionPunto, shape: BoxShape.circle),
            ),
          ),
          const SizedBox(width: 12),
          Flexible(
            child: Text('Funciona sin conexión',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(color: ColoresMaterna.sinConexionTexto, fontSize: 15.5, fontWeight: FontWeight.w600)),
          ),
        ]),
      );
}

/// Píldora verde: la cuenta y los datos viven en este dispositivo y no hace falta internet.
class _AvisoSinConexion extends StatelessWidget {
  const _AvisoSinConexion();

  @override
  Widget build(BuildContext context) => Container(
    key: const Key('aviso-sin-conexion'),
    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
    decoration: BoxDecoration(color: ColoresMaterna.sinConexionFondo, borderRadius: BorderRadius.circular(999)),
    // siempre en un renglón: si no cabe (pantalla angosta o letra grande), el texto se achica en vez de partirse
    child: FittedBox(
      fit: BoxFit.scaleDown,
      child: Text(
        'Funciona sin conexión · datos solo en este dispositivo',
        maxLines: 1,
        softWrap: false,
        style: TextStyle(color: ColoresMaterna.sinConexionTexto, fontSize: 12.5),
      ),
    ),
  );
}

/// Campo de texto con su etiqueta encima (como el mockup).
Widget _campo(
  String clave,
  String etiqueta,
  TextEditingController control, {
  String? pista,
  String? ayuda,
  String? error,
  bool pin = false,
  bool oculto = false,
  VoidCallback? alVerOcultar,
  ValueChanged<String>? alEnviar,
}) => Column(
  crossAxisAlignment: CrossAxisAlignment.start,
  children: [
    Etiqueta(etiqueta, ayuda: ayuda),
    TextField(
      key: Key('campo-$clave'),
      controller: control,
      obscureText: oculto,
      maxLength: pin ? 4 : null,
      keyboardType: pin ? TextInputType.number : TextInputType.text,
      inputFormatters: pin ? [FilteringTextInputFormatter.digitsOnly] : null,
      autocorrect: false,
      enableSuggestions: false,
      textInputAction: alEnviar == null ? TextInputAction.next : TextInputAction.done,
      onSubmitted: alEnviar,
      decoration: InputDecoration(
        // en los PIN, cuatro puntos de ejemplo (como «Ej. auxiliar.rural» en el usuario)
        hintText: pista ?? (pin ? '••••' : null),
        counterText: '',
        errorText: error,
        suffixIcon: alVerOcultar == null
            ? null
            : IconButton(
                tooltip: oculto ? 'Mostrar' : 'Ocultar',
                icon: Icon(oculto ? Icons.visibility_outlined : Icons.visibility_off_outlined, color: ColoresMaterna.tintaSuave),
                onPressed: alVerOcultar,
              ),
      ),
    ),
  ],
);

Widget _mensaje(String? texto, {Key key = const Key('mensaje-acceso'), bool bueno = false}) => texto == null
    ? const SizedBox.shrink()
    : Container(
        key: key,
        margin: const EdgeInsets.only(top: 12),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: bueno ? ColoresMaterna.sinConexionFondo : estiloPorCategoria['Alto Riesgo']!.fondo,
          borderRadius: BorderRadius.circular(14),
        ),
        child: Text(
          texto,
          style: TextStyle(color: bueno ? ColoresMaterna.sinConexionTexto : estiloPorCategoria['Alto Riesgo']!.tinta),
        ),
      );

/// Enlace en una línea: «¿No tiene cuenta? Registrarse».
Widget _enlace(String pregunta, String accion, Key clave, VoidCallback alTocar) => Wrap(
  alignment: WrapAlignment.center,
  crossAxisAlignment: WrapCrossAlignment.center,
  children: [
    Text(pregunta, style: TextStyle(color: ColoresMaterna.tintaSuave)),
    TextButton(
      key: clave,
      onPressed: alTocar,
      style: TextButton.styleFrom(padding: const EdgeInsets.symmetric(horizontal: 6)),
      child: Text(accion, style: const TextStyle(fontWeight: FontWeight.w800)),
    ),
  ],
);

String? _errorPin(String pin) => pinValido(pin) ? null : 'El PIN debe tener 4 dígitos.';

// ------------------------------------------------------------------ iniciar sesión
class _Entrar extends StatefulWidget {
  const _Entrar({
    super.key,
    required this.base,
    required this.usuarioInicial,
    required this.aviso,
    required this.alEntrar,
    required this.alRegistrarse,
    required this.alOlvidar,
  });

  final BaseLocal base;
  final String usuarioInicial;
  final String? aviso;
  final ValueChanged<Perfil> alEntrar;
  final VoidCallback alRegistrarse;
  final ValueChanged<String> alOlvidar;

  @override
  State<_Entrar> createState() => _EstadoEntrar();
}

class _EstadoEntrar extends State<_Entrar> {
  late final _usuario = TextEditingController(text: widget.usuarioInicial);
  final _pin = TextEditingController();
  var _oculto = true;
  var _entrando = false;
  var _recordar = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _cargarRecordado();
  }

  /// Si se pidió «Recordar usuario», el usuario aparece escrito (solo si esa cuenta sigue existiendo).
  Future<void> _cargarRecordado() async {
    final usuario = await widget.base.usuarioRecordado();
    if (usuario == null || !mounted) return;
    final existe = await widget.base.perfilDe(usuario) != null;
    if (!mounted) return;
    setState(() {
      _recordar = existe;
      if (existe && _usuario.text.trim().isEmpty) _usuario.text = usuario;
    });
  }

  @override
  void dispose() {
    _usuario.dispose();
    _pin.dispose();
    super.dispose();
  }

  Future<void> _entrar() async {
    if (_entrando) return;
    if (_usuario.text.trim().isEmpty || !pinValido(_pin.text)) {
      setState(() => _error = 'Escriba su usuario y su PIN de 4 dígitos.');
      return;
    }
    setState(() => _entrando = true);
    final resultado = await widget.base.entrar(_usuario.text, _pin.text);
    if (!mounted) return;
    switch (resultado) {
      case AccesoConcedido(:final perfil):
        await widget.base.recordarUsuario(_recordar ? perfil.usuario : null);
        widget.alEntrar(perfil);
      case AccesoDenegado(:final segundosDeBloqueo):
        setState(() {
          _entrando = false;
          _pin.clear();
          _error = segundosDeBloqueo > 0 ? 'Demasiados intentos. Espere $segundosDeBloqueo s.' : 'Usuario o PIN incorrecto.';
        });
    }
  }

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      const _Marca(titulo: 'Iniciar sesión', subtitulo: 'Acceso del personal de salud', conNombre: false),
      const SizedBox(height: 26),
      _campo('usuario', 'Usuario', _usuario, pista: 'Ej. auxiliar.rural'),
      const SizedBox(height: 16),
      _campo(
        'pin',
        'PIN de 4 dígitos',
        _pin,
        pin: true,
        oculto: _oculto,
        alVerOcultar: () => setState(() => _oculto = !_oculto),
        alEnviar: (_) => _entrar(),
      ),
      const SizedBox(height: 6),
      Row(
        children: [
          Expanded(
            child: InkWell(
              key: const Key('recordar-usuario'),
              borderRadius: BorderRadius.circular(8),
              onTap: () => setState(() => _recordar = !_recordar),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Checkbox(
                    value: _recordar,
                    onChanged: (v) => setState(() => _recordar = v ?? false),
                    visualDensity: VisualDensity.compact,
                    materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
                  Flexible(
                    child: Text('Recordar usuario', style: TextStyle(color: ColoresMaterna.tintaSuave, fontSize: 14)),
                  ),
                ],
              ),
            ),
          ),
          TextButton(
            key: const Key('olvide-pin'),
            onPressed: () => widget.alOlvidar(_usuario.text.trim()),
            style: TextButton.styleFrom(padding: const EdgeInsets.symmetric(horizontal: 4)),
            child: const Text('¿Olvidó su PIN?', style: TextStyle(fontWeight: FontWeight.w700)),
          ),
        ],
      ),
      _mensaje(_error ?? widget.aviso, bueno: _error == null),
      const SizedBox(height: 18),
      FilledButton(
        key: const Key('entrar'),
        onPressed: _entrando ? null : _entrar,
        child: _entrando
            ? const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2.4, color: Colors.white))
            : const Text('Entrar'),
      ),
      const SizedBox(height: 8),
      _enlace('¿No tiene cuenta?', 'Registrarse', const Key('ir-registro'), widget.alRegistrarse),
    ],
  );
}

// ------------------------------------------------------------------ registrarse
class _Registrarse extends StatefulWidget {
  const _Registrarse({super.key, required this.base, required this.alVolver, required this.alCrear});

  final BaseLocal base;
  final VoidCallback alVolver;
  final void Function(Perfil perfil, String codigo) alCrear;

  @override
  State<_Registrarse> createState() => _EstadoRegistrarse();
}

class _EstadoRegistrarse extends State<_Registrarse> {
  final _usuario = TextEditingController();
  final _ips = TextEditingController();
  final _municipio = TextEditingController();
  final _pin = TextEditingController();
  final _pin2 = TextEditingController();
  String? _atiende;
  var _avatar = 0;
  var _errores = <String, String>{};
  var _creando = false;
  var _sugeridos = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // lo elegido en la presentación queda propuesto (se puede cambiar)
    final preferencias = AmbitoPreferencias.de(context);
    if (!_sugeridos && preferencias != null) {
      _sugeridos = true;
      _atiende = atiende.containsKey(preferencias.rol) ? preferencias.rol : null;
      _avatar = preferencias.avatar;
    }
  }

  @override
  void dispose() {
    for (final c in [_usuario, _ips, _municipio, _pin, _pin2]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _crear() async {
    if (_creando) return;
    final errores = <String, String>{
      if (!usuarioValido(_usuario.text)) 'usuario': 'Use de 3 a 30 letras minúsculas, números, punto o guion.',
      if (_atiende == null) 'atendido_por': 'Elija una opción.',
      if (_ips.text.trim().isEmpty) 'ips': 'Escriba la IPS o el puesto de salud.',
      if (_errorPin(_pin.text) != null) 'pin': _errorPin(_pin.text)!,
      if (pinValido(_pin.text) && _pin.text != _pin2.text) 'pin2': 'Los PIN no coinciden.',
    };
    if (errores.isEmpty && await widget.base.existeUsuario(_usuario.text)) {
      errores['usuario'] = 'Ese usuario ya existe en este dispositivo.';
    }
    if (!mounted) return;
    setState(() => _errores = errores);
    if (errores.isNotEmpty) return;
    setState(() => _creando = true);
    final perfil = Perfil(
      atendidoPor: _atiende!,
      ips: _ips.text.trim(),
      municipio: _municipio.text.trim().isEmpty ? null : _municipio.text.trim(),
      avatar: _avatar,
    );
    final codigo = await widget.base.registrar(usuario: _usuario.text, pin: _pin.text, perfil: perfil);
    final creado = await widget.base.perfilDe(_usuario.text);
    if (mounted) widget.alCrear(creado!, codigo);
  }

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      const _Marca(titulo: 'Crear cuenta', pie: _AvisoSinConexion(), grande: false),
      const SizedBox(height: 22),
      Card(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _campo('usuario', 'Usuario', _usuario, pista: 'Ej. auxiliar.rural', error: _errores['usuario']),
              const SizedBox(height: 16),
              CampoLista(
                nombre: 'atendido_por',
                etiqueta: 'Quién atiende',
                opciones: atiende,
                valor: _atiende,
                error: _errores['atendido_por'],
                alCambiar: (v) => setState(() => _atiende = v),
              ),
              const SizedBox(height: 16),
              const Etiqueta('Avatar'),
              Wrap(
                spacing: 10,
                runSpacing: 10,
                children: [
                  for (var k = 0; k < avatares.length; k++)
                    Rebote(
                      key: Key('registro-avatar-$k'),
                      etiqueta: 'Avatar ${avatares[k].nombre}',
                      seleccionado: k == _avatar,
                      alTocar: () => setState(() => _avatar = k),
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 250),
                        padding: const EdgeInsets.all(3),
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          border: Border.all(color: k == _avatar ? ColoresMaterna.ciruela900 : Colors.transparent, width: 2),
                        ),
                        child: Opacity(opacity: k == _avatar ? 1 : .55, child: AvatarCirculo(k, tamano: 40)),
                      ),
                    ),
                ],
              ),
              const SizedBox(height: 16),
              _campo('ips', 'IPS o puesto de salud', _ips, error: _errores['ips']),
              const SizedBox(height: 16),
              _campo('municipio', 'Municipio', _municipio, ayuda: 'opcional'),
              const SizedBox(height: 16),
              _campo('pin', 'PIN de 4 dígitos', _pin, pin: true, oculto: true, error: _errores['pin']),
              const SizedBox(height: 16),
              _campo('pin2', 'Repita el PIN', _pin2, pin: true, oculto: true, error: _errores['pin2'], alEnviar: (_) => _crear()),
            ],
          ),
        ),
      ),
      const SizedBox(height: 20),
      FilledButton.icon(
        key: const Key('crear-acceso'),
        onPressed: _creando ? null : _crear,
        icon: const Icon(Icons.lock_outline_rounded),
        label: const Text('Crear cuenta'),
      ),
      const SizedBox(height: 8),
      _enlace('¿Ya tiene cuenta?', 'Iniciar sesión', const Key('ir-entrar'), widget.alVolver),
      const SizedBox(height: 4),
      Text(
        'Al crear la cuenta verá un código de recuperación: anótelo, sirve para poner un PIN nuevo si lo olvida.',
        textAlign: TextAlign.center,
        style: TextStyle(color: ColoresMaterna.tintaSuave, fontSize: 12.5),
      ),
    ],
  );
}

// ------------------------------------------------------------------ código de recuperación
class _Codigo extends StatelessWidget {
  const _Codigo({super.key, required this.codigo, required this.textoBoton, required this.alContinuar});

  final String codigo;
  final String textoBoton;
  final VoidCallback alContinuar;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      const _Marca(
        titulo: 'Su código de recuperación',
        subtitulo: 'Con él puede poner un PIN nuevo si lo olvida. Anótelo en un lugar seguro: no se vuelve a mostrar.',
        grande: false,
      ),
      const SizedBox(height: 24),
      Container(
        padding: const EdgeInsets.symmetric(vertical: 22),
        decoration: BoxDecoration(
          color: ColoresMaterna.campo,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: ColoresMaterna.ciruela100),
        ),
        child: SelectableText(
          codigo,
          key: const Key('codigo-recuperacion'),
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 30, fontWeight: FontWeight.w800, letterSpacing: 4, color: ColoresMaterna.ciruela900),
        ),
      ),
      const SizedBox(height: 12),
      Text(
        'Si pierde el PIN y este código, el responsable de datos de la IPS puede ponerle uno nuevo con la clave de la IPS.',
        textAlign: TextAlign.center,
        style: TextStyle(color: ColoresMaterna.tintaSuave, fontSize: 12.5),
      ),
      const SizedBox(height: 24),
      FilledButton(key: const Key('codigo-anotado'), onPressed: alContinuar, child: Text(textoBoton)),
    ],
  );
}

// ------------------------------------------------------------------ recuperar el acceso
class _Recuperar extends StatefulWidget {
  const _Recuperar({
    super.key,
    required this.base,
    required this.usuarioInicial,
    required this.alVolver,
    required this.alRestablecer,
    required this.alEliminar,
  });

  final BaseLocal base;
  final String usuarioInicial;
  final VoidCallback alVolver;
  final void Function(String usuario, String codigoNuevo) alRestablecer;
  final ValueChanged<String> alEliminar;

  @override
  State<_Recuperar> createState() => _EstadoRecuperar();
}

class _EstadoRecuperar extends State<_Recuperar> {
  late final _usuario = TextEditingController(text: widget.usuarioInicial);
  final _secreto = TextEditingController();
  final _pin = TextEditingController();
  final _pin2 = TextEditingController();
  var _conClaveIps = false;
  var _errores = <String, String>{};
  String? _error;
  var _trabajando = false;

  @override
  void dispose() {
    for (final c in [_usuario, _secreto, _pin, _pin2]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _restablecer() async {
    if (_trabajando) return;
    final errores = <String, String>{
      if (_usuario.text.trim().isEmpty) 'usuario': 'Escriba el usuario.',
      if (_secreto.text.trim().isEmpty)
        'secreto': _conClaveIps ? 'Escriba la clave de la IPS.' : 'Escriba el código de recuperación.',
      if (_errorPin(_pin.text) != null) 'pin-nuevo': _errorPin(_pin.text)!,
      if (pinValido(_pin.text) && _pin.text != _pin2.text) 'pin-nuevo2': 'Los PIN no coinciden.',
    };
    setState(() {
      _errores = errores;
      _error = null;
    });
    if (errores.isNotEmpty) return;
    setState(() => _trabajando = true);
    final codigo = _conClaveIps
        ? await widget.base.restablecerConClaveIps(_usuario.text, _secreto.text, _pin.text)
        : await widget.base.restablecerConCodigo(_usuario.text, _secreto.text, _pin.text);
    if (!mounted) return;
    if (codigo != null) {
      widget.alRestablecer(normalizarUsuario(_usuario.text), codigo);
      return;
    }
    setState(() {
      _trabajando = false;
      _error = _conClaveIps
          ? 'Usuario o clave de la IPS incorrectos (o la clave no está configurada en este dispositivo).'
          : 'Usuario o código incorrectos. Tras 5 intentos la cuenta se bloquea 30 s.';
    });
  }

  Future<void> _eliminar() async {
    final usuario = normalizarUsuario(_usuario.text);
    if (usuario.isEmpty || !await widget.base.existeUsuario(usuario)) {
      setState(() => _errores = {'usuario': 'Escriba un usuario que exista en este dispositivo.'});
      return;
    }
    if (!mounted) return;
    final confirmar = await showDialog<bool>(
      context: context,
      builder: (contexto) => AlertDialog(
        title: Text('¿Eliminar la cuenta «$usuario»?'),
        content: const Text(
          'Use esta opción solo si no tiene el código de recuperación ni la clave de la IPS. Se borrarán '
          'la cuenta y TODAS sus evaluaciones y cargas de este dispositivo; las demás cuentas no se tocan. No se puede deshacer.',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(contexto, false), child: const Text('Cancelar')),
          FilledButton(
            key: const Key('confirmar-eliminar'),
            style: FilledButton.styleFrom(
              minimumSize: const Size(0, 44),
              backgroundColor: estiloPorCategoria['Alto Riesgo']!.tinta,
            ),
            onPressed: () => Navigator.pop(contexto, true),
            child: const Text('Eliminar la cuenta'),
          ),
        ],
      ),
    );
    if (confirmar != true) return;
    await widget.base.eliminarUsuario(usuario);
    widget.alEliminar(usuario);
  }

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      const _Marca(titulo: 'Recuperar el acceso', subtitulo: 'Ponga un PIN nuevo sin perder sus evaluaciones.', grande: false),
      const SizedBox(height: 20),
      SegmentedButton<bool>(
        key: const Key('modo-recuperar'),
        segments: const [
          ButtonSegment(value: false, label: Text('Código de recuperación')),
          ButtonSegment(value: true, label: Text('Clave de la IPS')),
        ],
        selected: {_conClaveIps},
        showSelectedIcon: false,
        onSelectionChanged: (s) => setState(() {
          _conClaveIps = s.first;
          _secreto.clear();
          _errores = {};
          _error = null;
        }),
      ),
      const SizedBox(height: 8),
      Text(
        _conClaveIps
            ? 'Para el responsable de datos de la IPS: la clave que se configuró en «Carga IPS».'
            : 'El código que le mostró la app al crear la cuenta (p. ej. K7M2-Q9XP).',
        textAlign: TextAlign.center,
        style: TextStyle(color: ColoresMaterna.tintaSuave, fontSize: 12.5),
      ),
      const SizedBox(height: 16),
      Card(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _campo('usuario', 'Usuario', _usuario, pista: 'Ej. auxiliar.rural', error: _errores['usuario']),
              const SizedBox(height: 16),
              _campo(
                _conClaveIps ? 'clave-ips' : 'codigo',
                _conClaveIps ? 'Clave de la IPS' : 'Código de recuperación',
                _secreto,
                oculto: _conClaveIps,
                error: _errores['secreto'],
              ),
              const SizedBox(height: 16),
              _campo('pin-nuevo', 'PIN nuevo de 4 dígitos', _pin, pin: true, oculto: true, error: _errores['pin-nuevo']),
              const SizedBox(height: 16),
              _campo(
                'pin-nuevo2',
                'Repita el PIN nuevo',
                _pin2,
                pin: true,
                oculto: true,
                error: _errores['pin-nuevo2'],
                alEnviar: (_) => _restablecer(),
              ),
            ],
          ),
        ),
      ),
      _mensaje(_error),
      const SizedBox(height: 20),
      FilledButton(
        key: const Key('restablecer'),
        onPressed: _trabajando ? null : _restablecer,
        child: const Text('Poner PIN nuevo'),
      ),
      const SizedBox(height: 8),
      _enlace('¿Lo recordó?', 'Iniciar sesión', const Key('ir-entrar'), widget.alVolver),
      const Divider(height: 28),
      Text(
        '¿Sin código ni clave de la IPS?',
        textAlign: TextAlign.center,
        style: TextStyle(color: ColoresMaterna.tintaSuave, fontSize: 12.5),
      ),
      TextButton(
        key: const Key('eliminar-cuenta'),
        onPressed: _eliminar,
        style: TextButton.styleFrom(foregroundColor: estiloPorCategoria['Alto Riesgo']!.tinta),
        child: const Text('Eliminar solo esta cuenta'),
      ),
    ],
  );
}
