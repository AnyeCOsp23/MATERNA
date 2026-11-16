/// Pestaña 1: triaje obstétrico individual, como asistente por pasos (Resolución 3280 de 2018).
///
///   1 Datos maternos · 2 Constantes vitales y laboratorio · 3 Contexto y atención · 4 Signos de alarma ·
///   5 Valoración de la ruta (opcional) · 6 Revisión  ->  Resultado
///
/// Cada paso valida sus datos antes de avanzar. Los pasos 1 a 3 llevan las variables que necesita el modelo
/// (obligatorias, salvo glucosa y FCF, que admiten «Sin dato»); los pasos 4 y 5, las variables de la ruta
/// que solo generan alertas (Sí / No / Sin dato) y el territorio, que se registra para auditar sesgos.
library;

import 'package:flutter/material.dart';

import '../../motor/catalogo_3280.dart';
import '../../motor/recursos.dart';
import '../tema/tema_materna.dart';
import '../widgets/barra_flotante.dart';
import '../widgets/campos.dart';
import '../widgets/encabezado.dart';
import 'pantalla_resultado.dart';

const _proteinuria = {0: 'Negativa', 1: '+', 2: '++ o más'};
const _area = {'Rural disperso': 'Rural disperso', 'Cabecera': 'Cabecera'};
const atiende = {
  'Medico': 'Médico',
  'Enfermero(a)': 'Enfermero(a)',
  'Auxiliar de enfermeria': 'Auxiliar de enfermería',
  'Partera tradicional': 'Partera tradicional',
};
const _departamentos = {'La Guajira': 'La Guajira', 'Cesar': 'Cesar'};
const _seccionesOpcionales = ['Anamnesis', 'Examen físico', 'Paraclínicos', 'Escalas de riesgo', 'Plan de cuidado'];
const _conSinDato = {'glucosa_mgdl', 'fcf_bpm'};
// El rojo del nivel Alto (tema_materna.dart), para el triángulo de alerta del paso «Signos de alarma»
const _rojoAlerta = Color(0xFFC62828);

class _Paso {
  const _Paso(this.titulo, this.descripcion, this.icono, this.variables, {this.colorIcono = ColoresMaterna.ciruela900});

  final String titulo;
  final String descripcion;
  final IconData icono;

  /// Color del ícono del encabezado (rojo de alerta en «Signos de alarma»).
  final Color colorIcono;

  /// Variables que se validan al intentar avanzar.
  final List<String> variables;
}

class PantallaTriaje extends StatefulWidget {
  const PantallaTriaje({super.key, required this.recursos, this.atendidoPor, this.alGuardar});

  final RecursosMaterna recursos;

  /// Guarda la evaluación (base local) antes de mostrar el resultado.
  final Future<void> Function(Evaluacion evaluacion)? alGuardar;

  /// Quién atiende, tomado del perfil del operador (si ya inició sesión). Se puede cambiar en el paso 3.
  final String? atendidoPor;

  @override
  State<PantallaTriaje> createState() => _EstadoTriaje();
}

class _EstadoTriaje extends State<PantallaTriaje> {
  final _textos = <String, TextEditingController>{};
  final _opciones = <String, Object?>{};
  final _sinDato = <String>{};
  var _errores = <String, String>{};
  var _paso = 0;
  var _version = 0; // al empezar una evaluación nueva se reconstruye el asistente completo

  Catalogo3280 get _catalogo => widget.recursos.catalogo;

  late final List<_Paso> _pasos = [
    const _Paso('Datos maternos', 'Edad, semanas de gestación y controles previos.', Icons.pregnant_woman_rounded,
        ['edad', 'semanas_gestacion', 'n_controles_prenatales']),
    const _Paso('Constantes vitales y laboratorio', 'Presión arterial, frecuencia cardiaca fetal, glucosa y tira reactiva.',
        Icons.monitor_heart_rounded, ['pas_mmhg', 'pad_mmhg', 'fcf_bpm', 'glucosa_mgdl', 'proteinuria', 'convulsiones']),
    const _Paso('Contexto y atención', 'Dónde vive la gestante y quién la atiende.', Icons.location_on_rounded,
        ['area_residencia', 'atendido_por']),
    _Paso('Signos de alarma', 'Pregúntelos siempre: cualquiera exige valoración médica inmediata.', Icons.warning_rounded,
        [for (final v in _catalogo.porDecision('capturar_alertar')) if (v.seccion == 'Signos de alarma') v.nombre],
        colorIcono: _rojoAlerta),
    _Paso('Valoración de la ruta', 'Opcional: antecedentes, examen físico, paraclínicos, escalas y plan de cuidado.',
        Icons.fact_check_rounded, [
      for (final v in [..._catalogo.porDecision('capturar_alertar'), ..._catalogo.porDecision('auditoria')])
        if (v.seccion != 'Signos de alarma') v.nombre,
    ]),
    const _Paso('Revisión', 'Confirme los datos antes de evaluar.', Icons.checklist_rounded, []),
  ];

  @override
  void initState() {
    super.initState();
    _opciones['atendido_por'] = widget.atendidoPor;
  }

  TextEditingController _control(String nombre) => _textos.putIfAbsent(nombre, TextEditingController.new);

  @override
  void dispose() {
    for (final c in _textos.values) {
      c.dispose();
    }
    super.dispose();
  }

  void _nuevaEvaluacion() => setState(() {
        for (final c in _textos.values) {
          c.clear();
        }
        _opciones
          ..clear()
          ..['atendido_por'] = widget.atendidoPor;
        _sinDato.clear();
        _errores = {};
        _paso = 0;
        _version++;
      });

  // ------------------------------------------------------------------ validación y registro
  double? _leer(String nombre) => double.tryParse(_control(nombre).text.trim().replaceAll(',', '.'));

  /// Lee y valida un número del catálogo. Devuelve (valor, error).
  (double?, String?) _numero(VariableCatalogo v, {required bool obligatorio}) {
    if (_sinDato.contains(v.nombre)) return (null, null);
    final texto = _control(v.nombre).text.trim();
    if (texto.isEmpty) {
      if (!obligatorio) return (null, null);
      return (null, _conSinDato.contains(v.nombre) ? 'Escriba el valor o marque «Sin dato».' : 'Dato obligatorio.');
    }
    final valor = _leer(v.nombre);
    if (valor == null) return (null, 'Escriba un número.');
    final rango = v.rango;
    if (rango != null && (valor < rango[0] || valor > rango[1])) {
      return (null, 'Fuera del rango válido (${rango[0].toStringAsFixed(0)} a ${rango[1].toStringAsFixed(0)}).');
    }
    if (v.tipo == 'entero' && valor != valor.roundToDouble()) return (null, 'Debe ser un número entero.');
    return (valor, null);
  }

  /// Valida unas variables y las agrega al registro. Devuelve los errores encontrados.
  Map<String, String> _validar(Iterable<String> nombres, Map<String, dynamic> registro) {
    final errores = <String, String>{};
    for (final nombre in nombres) {
      final v = _catalogo.variable(nombre)!;
      final obligatoria = v.decision == 'modelo';
      if ((v.tipo == 'entero' || v.tipo == 'decimal') && nombre != 'proteinuria') {
        final (valor, error) = _numero(v, obligatorio: obligatoria);
        if (error != null) errores[nombre] = error;
        if (obligatoria || valor != null) registro[nombre] = valor;
      } else if (v.tipo == 'texto' && nombre != 'departamento') {
        final texto = _control(nombre).text.trim();
        if (texto.isNotEmpty) registro[nombre] = texto;
      } else {
        final valor = _opciones[nombre];
        if (valor == null) {
          if (obligatoria) errores[nombre] = 'Elija una opción.';
        } else {
          registro[nombre] = valor is bool && obligatoria ? (valor ? 1 : 0) : valor;
        }
      }
    }
    // Cada presión puede estar en su rango y aun así ser un error de digitación: la diastólica nunca es
    // mayor ni igual que la sistólica.
    final pas = registro['pas_mmhg'], pad = registro['pad_mmhg'];
    if (pas is num && pad is num && pad >= pas && !errores.containsKey('pas_mmhg') && !errores.containsKey('pad_mmhg')) {
      errores['pad_mmhg'] = 'Debe ser menor que la sistólica (PAS ${pas.round()}).';
    }
    return errores;
  }

  Map<String, dynamic>? _registroCompleto() {
    final registro = <String, dynamic>{};
    final errores = _validar(_pasos.expand((p) => p.variables), registro);
    setState(() => _errores = errores);
    return errores.isEmpty ? registro : null;
  }

  void _siguiente() {
    final errores = _validar(_pasos[_paso].variables, {});
    setState(() {
      _errores = errores;
      if (errores.isEmpty) _paso++;
    });
    if (errores.isNotEmpty) {
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(content: Text('Revise ${errores.length} dato(s) marcados en rojo.')));
    }
  }

  void _atras() => setState(() {
        _errores = {};
        _paso--;
      });

  Future<void> _evaluar() async {
    final registro = _registroCompleto();
    if (registro == null) return;
    final evaluacion = widget.recursos.evaluar(registro);
    await widget.alGuardar?.call(evaluacion);
    if (!mounted) return;
    final accion = await Navigator.of(context).push<String>(
      MaterialPageRoute(builder: (_) => PantallaResultado(recursos: widget.recursos, evaluacion: evaluacion)),
    );
    if (accion == 'nueva') _nuevaEvaluacion();
  }

  // ------------------------------------------------------------------ campos
  Widget _campo(String nombre) {
    final v = _catalogo.variable(nombre)!;
    switch (nombre) {
      case 'proteinuria':
        return _opcionesObligatorias<int>(nombre, 'Proteinuria en tira reactiva', _proteinuria);
      case 'convulsiones':
        return _opcionesObligatorias<bool>(nombre, 'Convulsiones', const {true: 'Sí', false: 'No'}, ayuda: 'sospecha de eclampsia');
      case 'area_residencia':
        return _opcionesObligatorias<String>(nombre, 'Área de residencia', _area);
      case 'atendido_por':
        return CampoLista(
          nombre: nombre,
          etiqueta: 'Quién atiende',
          opciones: atiende,
          valor: _opciones[nombre] as String?,
          error: _errores[nombre],
          alCambiar: (valor) => setState(() => _opciones[nombre] = valor),
        );
      case 'departamento':
        return CampoLista(
          nombre: nombre,
          etiqueta: v.etiqueta,
          opciones: _departamentos,
          valor: _opciones[nombre] as String?,
          alCambiar: (valor) => setState(() => _opciones[nombre] = valor),
        );
    }
    switch (v.tipo) {
      case 'entero' || 'decimal':
        final conSinDato = _conSinDato.contains(nombre);
        return CampoNumero(
          nombre: nombre,
          etiqueta: v.etiqueta,
          controlador: _control(nombre),
          unidad: v.unidad,
          rango: v.rango,
          decimal: v.tipo == 'decimal',
          error: _errores[nombre],
          sinDato: conSinDato ? _sinDato.contains(nombre) : null,
          alCambiarSinDato: conSinDato
              ? (marcado) => setState(() {
                    marcado ? _sinDato.add(nombre) : _sinDato.remove(nombre);
                    if (marcado) _control(nombre).clear();
                  })
              : null,
        );
      case 'binaria':
        return CampoTresEstados(
          nombre: nombre,
          etiqueta: v.etiqueta,
          valor: _opciones[nombre] as bool?,
          alCambiar: (valor) => setState(() => _opciones[nombre] = valor),
        );
      case 'categorica':
        return CampoLista(
          nombre: nombre,
          etiqueta: v.etiqueta,
          opciones: {for (final o in v.valores) o: o},
          valor: _opciones[nombre] as String?,
          alCambiar: (valor) => setState(() => _opciones[nombre] = valor),
        );
      case 'fecha':
        final fecha = _opciones[nombre] as String?;
        return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Etiqueta(v.etiqueta),
          OutlinedButton.icon(
            key: Key('campo-$nombre'),
            icon: const Icon(Icons.calendar_today_rounded, size: 18),
            label: Text(fecha ?? 'Elegir fecha'),
            onPressed: () async {
              final hoy = DateTime.now();
              final elegida = await showDatePicker(
                  context: context, firstDate: hoy.subtract(const Duration(days: 320)), lastDate: hoy, initialDate: hoy);
              if (elegida != null) setState(() => _opciones[nombre] = elegida.toIso8601String().substring(0, 10));
            },
          ),
        ]);
      default:
        return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Etiqueta(v.etiqueta),
          TextField(key: Key('campo-$nombre'), controller: _control(nombre)),
        ]);
    }
  }

  Widget _opcionesObligatorias<T extends Object>(String nombre, String etiqueta, Map<T, String> opciones, {String? ayuda}) =>
      CampoOpciones<T>(
        nombre: nombre,
        etiqueta: etiqueta,
        opciones: opciones,
        valor: _opciones[nombre] as T?,
        ayuda: ayuda,
        error: _errores[nombre],
        alCambiar: (valor) => setState(() => _opciones[nombre] = valor),
      );

  Widget _tarjeta(List<Widget> hijos) => Card(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 20, 20, 22),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            for (final (i, h) in hijos.indexed) ...[if (i > 0) const SizedBox(height: 18), h],
          ]),
        ),
      );

  Widget _seccionPlegable(String titulo, List<VariableCatalogo> variables, IconData icono, {String? nota}) {
    final respondidas =
        variables.where((v) => _opciones[v.nombre] != null || (_textos[v.nombre]?.text.isNotEmpty ?? false)).length;
    return Card(
      clipBehavior: Clip.antiAlias,
      child: ExpansionTile(
        // ValueKey y no PageStorageKey: esta guardaría el estado abierto (bool) donde los campos de texto de adentro
        // guardan su desplazamiento (double), y la app fallaba al abrir una sección con un campo numérico.
        key: ValueKey('seccion-$titulo-$_version'),
        initiallyExpanded: variables.any((v) => _errores.containsKey(v.nombre)),
        shape: const Border(),
        leading: Icon(icono, color: ColoresMaterna.ciruela700),
        title: Text(titulo, style: const TextStyle(fontWeight: FontWeight.w700)),
        subtitle: Text('${nota ?? 'Opcional'} · $respondidas de ${variables.length} registradas',
            style: const TextStyle(color: ColoresMaterna.tintaSuave, fontSize: 12.5)),
        childrenPadding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
        children: [for (final (i, v) in variables.indexed) ...[if (i > 0) const SizedBox(height: 16), _campo(v.nombre)]],
      ),
    );
  }

  static const _iconosSeccion = {
    'Anamnesis': Icons.history_edu_rounded,
    'Examen físico': Icons.straighten_rounded,
    'Paraclínicos': Icons.biotech_rounded,
    'Escalas de riesgo': Icons.analytics_rounded,
    'Plan de cuidado': Icons.vaccines_rounded,
  };

  Widget _contenidoPaso() {
    final paso = _pasos[_paso];
    switch (_paso) {
      case 4:
        final ruta = _catalogo.porDecision('capturar_alertar');
        return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          for (final s in _seccionesOpcionales) ...[
            _seccionPlegable(s, ruta.where((v) => v.seccion == s).toList(), _iconosSeccion[s]!),
            const SizedBox(height: 10),
          ],
          _seccionPlegable('Territorio', _catalogo.porDecision('auditoria'), Icons.map_rounded,
              nota: 'Solo para análisis por territorio; no cambia el resultado'),
        ]);
      case 5:
        return _Revision(
          catalogo: _catalogo,
          valores: _valoresLegibles(),
          alEditar: (indice) => setState(() => _paso = indice),
          pasos: [for (final p in _pasos.take(5)) (p.titulo, p.variables)],
        );
      default:
        return _tarjeta([for (final nombre in paso.variables) _campo(nombre)]);
    }
  }

  /// Valor legible de cada variable respondida (para la revisión).
  Map<String, String> _valoresLegibles() {
    final valores = <String, String>{};
    for (final p in _pasos.take(5)) {
      for (final nombre in p.variables) {
        final v = _catalogo.variable(nombre)!;
        if (_sinDato.contains(nombre)) {
          valores[nombre] = 'Sin dato';
        } else if (_textos[nombre]?.text.trim().isNotEmpty ?? false) {
          valores[nombre] = '${_textos[nombre]!.text.trim()}${v.unidad == null ? '' : ' ${v.unidad}'}';
        } else if (_opciones[nombre] != null) {
          final o = _opciones[nombre];
          valores[nombre] = switch (nombre) {
            'proteinuria' => _proteinuria[o]!,
            'atendido_por' => atiende[o] ?? '$o',
            _ => o is bool ? (o ? 'Sí' : 'No') : '$o',
          };
        }
      }
    }
    return valores;
  }

  @override
  Widget build(BuildContext context) {
    final paso = _pasos[_paso];
    final ultimo = _paso == _pasos.length - 1;
    return Scaffold(
      backgroundColor: Colors.transparent,
      body: SafeArea(
        bottom: false,
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 760),
            child: CustomScrollView(key: ValueKey('triaje-$_version-$_paso'), slivers: [
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
                sliver: SliverToBoxAdapter(child: _Cabecera(paso: paso, numero: _paso + 1, total: _pasos.length)),
              ),
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
                sliver: SliverToBoxAdapter(child: _contenidoPaso()),
              ),
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(16, 20, 16, BarraFlotante.espacioInferior),
                sliver: SliverToBoxAdapter(
                  child: Row(children: [
                    if (_paso > 0) ...[
                      Expanded(
                        child: OutlinedButton.icon(
                          key: const Key('atras'),
                          onPressed: _atras,
                          icon: const Icon(Icons.arrow_back_rounded),
                          label: const Text('Atrás'),
                        ),
                      ),
                      const SizedBox(width: 12),
                    ],
                    Expanded(
                      flex: 2,
                      child: ultimo
                          ? FilledButton.icon(
                              key: const Key('evaluar'),
                              onPressed: _evaluar,
                              icon: const Icon(Icons.health_and_safety_rounded),
                              label: const Text('Evaluar riesgo'),
                            )
                          : FilledButton.icon(
                              key: const Key('siguiente'),
                              onPressed: _siguiente,
                              icon: const Icon(Icons.arrow_forward_rounded),
                              label: Text(_paso == 4 ? 'Revisar' : 'Siguiente'),
                            ),
                    ),
                  ]),
                ),
              ),
            ]),
          ),
        ),
      ),
    );
  }
}

class _Cabecera extends StatelessWidget {
  const _Cabecera({required this.paso, required this.numero, required this.total});

  final _Paso paso;
  final int numero;
  final int total;

  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        EncabezadoMaterna(etiqueta: 'Paso $numero de $total', claveEtiqueta: const Key('paso-actual')),
        const SizedBox(height: 10),
        ClipRRect(
          borderRadius: BorderRadius.circular(8),
          child: TweenAnimationBuilder<double>(
            tween: Tween(end: numero / total),
            duration: const Duration(milliseconds: 350),
            curve: const Cubic(.32, .72, 0, 1),
            builder: (context, valor, _) => LinearProgressIndicator(
              value: valor,
              minHeight: 6,
              backgroundColor: ColoresMaterna.fondoProgreso,
              color: ColoresMaterna.ciruela900,
            ),
          ),
        ),
        const SizedBox(height: 18),
        Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Container(
            width: 50,
            height: 50,
            decoration: BoxDecoration(color: ColoresMaterna.ciruela100, borderRadius: BorderRadius.circular(15)),
            child: Icon(paso.icono, key: const Key('icono-paso'), color: paso.colorIcono),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(paso.titulo, style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
              const SizedBox(height: 2),
              Text(paso.descripcion, style: const TextStyle(color: ColoresMaterna.tintaSuave)),
            ]),
          ),
        ]),
      ]);
}

class _Revision extends StatelessWidget {
  const _Revision({required this.catalogo, required this.valores, required this.alEditar, required this.pasos});

  final Catalogo3280 catalogo;
  final Map<String, String> valores;
  final ValueChanged<int> alEditar;
  final List<(String, List<String>)> pasos;

  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        for (final (i, (titulo, variables)) in pasos.indexed) ...[
          Card(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(18, 10, 8, 14),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  Expanded(child: Text(titulo, style: const TextStyle(fontWeight: FontWeight.w700))),
                  TextButton.icon(
                    key: Key('editar-paso-$i'),
                    onPressed: () => alEditar(i),
                    icon: const Icon(Icons.edit_rounded, size: 18),
                    label: const Text('Editar'),
                  ),
                ]),
                if (!variables.any(valores.containsKey))
                  const Text('Sin registrar', style: TextStyle(color: ColoresMaterna.tintaSuave))
                else
                  for (final nombre in variables.where(valores.containsKey))
                    Padding(
                      padding: const EdgeInsets.only(top: 6, right: 10),
                      child: Row(children: [
                        Expanded(child: Text(catalogo.variable(nombre)!.etiqueta, style: const TextStyle(color: ColoresMaterna.tintaSuave))),
                        Text(valores[nombre]!, style: const TextStyle(fontWeight: FontWeight.w600)),
                      ]),
                    ),
              ]),
            ),
          ),
          const SizedBox(height: 10),
        ],
      ]);
}
