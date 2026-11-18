/// Pestaña 2: carga masiva de un archivo de la IPS con la plantilla de la Resolución 3280.
///
///   1 Clave de la IPS (una vez por dispositivo) · 2 Elegir el archivo (CSV, TXT con «|» o Excel) ·
///   3 Triaje de todas las gestantes, ordenado por urgencia · 4 Exportar el resultado a CSV
///
/// El documento de cada gestante se reemplaza por su seudónimo HMAC-SHA256 al leer el archivo: ni el documento ni
/// los nombres se guardan ni se muestran. Las evaluaciones se guardan en el historial con la carga; si el mismo
/// archivo ya se había cargado, no se guarda de nuevo salvo que el operador lo pida.
library;

import 'dart:convert';
import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';

import '../../datos/base_local.dart';
import '../../datos/lector_ips.dart';
import '../../datos/seudonimizacion.dart';
import '../../motor/carga_masiva.dart';
import '../../motor/recursos.dart';
import '../tema/tema_materna.dart';
import '../widgets/barra_flotante.dart';
import '../widgets/boton_info.dart';
import '../widgets/encabezado.dart';
import '../widgets/iconos_trazo.dart';
import 'pantalla_historial.dart' show fechaLegible;
import 'pantalla_resultado.dart';

typedef ElegirArchivo = Future<(String, Uint8List)?> Function();

/// Guarda el archivo exportado. Devuelve false si el operador canceló.
typedef GuardarArchivo = Future<bool> Function(String nombre, Uint8List bytes);

Future<(String, Uint8List)?> _elegirConSelector() async {
  final f = await FilePicker.pickFile(type: FileType.custom, allowedExtensions: extensionesIps);
  return f == null ? null : (f.name, await f.readAsBytes());
}

Future<bool> _guardarConSelector(String nombre, Uint8List bytes) async {
  final uri = await FilePicker.saveFile(fileName: nombre, bytes: bytes, mimeType: 'text/csv');
  return kIsWeb || uri != null; // en la web se descarga directamente y no devuelve ruta
}

class PantallaCarga extends StatefulWidget {
  const PantallaCarga({
    super.key,
    required this.recursos,
    required this.base,
    required this.perfil,
    this.alGuardar,
    this.elegirArchivo,
    this.guardarArchivo,
  });

  final RecursosMaterna recursos;
  final BaseLocal base;
  final Perfil perfil;

  /// Avisa que se guardaron evaluaciones nuevas (el historial se recarga).
  final VoidCallback? alGuardar;

  /// Permiten reemplazar el selector de archivos del sistema (las pruebas no lo pueden abrir).
  final ElegirArchivo? elegirArchivo;
  final GuardarArchivo? guardarArchivo;

  @override
  State<PantallaCarga> createState() => _EstadoCarga();
}

class _EstadoCarga extends State<PantallaCarga> {
  String? _clave;
  var _cargandoClave = true;
  var _editandoClave = false;
  var _verClave = false;
  final _campoClave = TextEditingController();
  final _campoRepetir = TextEditingController();
  final _focoClave = FocusNode();
  String? _errorClave;

  /// Se intentó guardar una clave de menos de [longitudMinimaSal] caracteres: el aviso del campo pasa a rojo.
  var _claveCorta = false;

  var _procesando = false;
  (int, int) _avance = (0, 0);
  String? _error;
  CargaMasiva? _carga;
  RegistroCarga? _previa;
  var _guardada = false;
  int? _filtro;

  @override
  void initState() {
    super.initState();
    // el aviso «Mínimo 16 caracteres» se recalcula al escribir y al entrar o salir del campo
    _campoClave.addListener(_alCambiarClave);
    _focoClave.addListener(_alCambiarClave);
    widget.base.claveIps().then((c) {
      if (mounted) {
        setState(() {
          _clave = c;
          _cargandoClave = false;
        });
      }
    });
  }

  @override
  void dispose() {
    _campoClave.dispose();
    _campoRepetir.dispose();
    _focoClave.dispose();
    super.dispose();
  }

  void _alCambiarClave() {
    if (!mounted) return;
    setState(() {
      if (salValida(_campoClave.text)) _claveCorta = false;
    });
  }

  /// Aviso bajo el campo de la clave:
  ///   · vacío y sin el foco: nada;
  ///   · con el foco, o con algo escrito pero incompleto (también al salir del campo): «Mínimo 16 caracteres»;
  ///   · si se intentó guardar incompleta: en rojo y con los caracteres que lleva;
  ///   · con 16 o más: desaparece.
  ({String? ayuda, String? error}) get _avisoLongitud {
    final n = _campoClave.text.length;
    if (n >= longitudMinimaSal || (n == 0 && !_focoClave.hasFocus && !_claveCorta)) return (ayuda: null, error: null);
    if (_claveCorta) return (ayuda: null, error: 'Mínimo $longitudMinimaSal caracteres (lleva $n)');
    return (ayuda: 'Mínimo $longitudMinimaSal caracteres', error: null);
  }

  /// Lo que antes ocupaba el formulario, ahora en la ventana del botón ⓘ.
  void _infoClave() => mostrarInfo(context, titulo: 'Clave de la IPS', icono: Icons.key_rounded, puntos: const [
        (Icons.shield_outlined, 'Protege la identidad de las gestantes',
            'Con esta clave, el documento de cada gestante se reemplaza por un código anónimo. El documento nunca se '
                'guarda en el dispositivo.', false),
        (Icons.devices_outlined, 'La misma en todos los dispositivos',
            'Debe ser la misma en todos los dispositivos de la IPS, para que cada gestante tenga siempre el mismo código y '
                'se pueda hacer su seguimiento.', false),
        (Icons.support_agent_outlined, 'Pídala al responsable de datos',
            'No invente una clave nueva: solicítela al responsable de datos de su IPS.', false),
        (Icons.warning_amber_rounded, 'Si cambia la clave',
            'Las gestantes que ya se cargaron quedarán con otro código y no se podrán relacionar con las que se carguen '
                'después.', true),
      ]);

  void _aviso(String texto) => ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(content: Text(texto)));

  // ------------------------------------------------------------------ clave
  Future<void> _guardarClave() async {
    final clave = _campoClave.text;
    if (!salValida(clave)) {
      // el aviso del propio campo lo explica (en rojo y con los caracteres que lleva)
      setState(() {
        _claveCorta = true;
        _errorClave = null;
      });
      return;
    }
    if (clave != _campoRepetir.text) {
      setState(() => _errorClave = 'Las dos claves no coinciden.');
      return;
    }
    await widget.base.fijarClaveIps(clave);
    if (!mounted) return;
    setState(() {
      _clave = clave;
      _editandoClave = false;
      _errorClave = null;
      _claveCorta = false;
      _campoClave.clear();
      _campoRepetir.clear();
    });
    // sin aviso flotante: en el celular tapaba el botón «Elegir archivo»; la tarjeta ya muestra la huella
  }

  // ------------------------------------------------------------------ carga
  Future<void> _elegir() async {
    final elegido = await (widget.elegirArchivo ?? _elegirConSelector)();
    if (elegido == null || !mounted) return;
    final (nombre, bytes) = elegido;
    setState(() {
      _procesando = true;
      _avance = (0, 0);
      _error = null;
      _carga = null;
      _previa = null;
      _guardada = false;
      _filtro = null;
    });
    try {
      final carga = await procesarCarga(
        nombre: nombre,
        bytes: bytes,
        recursos: widget.recursos,
        sal: _clave!,
        alAvanzar: (hechas, total) {
          if (mounted) setState(() => _avance = (hechas, total));
        },
      );
      final previa = await widget.base.cargaPrevia(carga.huellaArchivo, idUsuario: widget.perfil.id);
      if (!mounted) return;
      setState(() {
        _carga = carga;
        _previa = previa;
      });
      if (previa == null) await _guardar();
    } on ArchivoIpsInvalido catch (e) {
      if (mounted) setState(() => _error = e.mensaje);
    } catch (e) {
      if (mounted) setState(() => _error = 'No se pudo procesar el archivo: $e');
    } finally {
      if (mounted) setState(() => _procesando = false);
    }
  }

  Future<void> _guardar() async {
    final carga = _carga!;
    if (carga.resultados.isEmpty) return;
    final clasificador = widget.recursos.clasificador;
    await widget.base.guardarCarga(carga,
        perfil: widget.perfil, versionModelo: clasificador.version, clases: clasificador.clases, clave: _clave!);
    widget.alGuardar?.call();
    if (mounted) setState(() => _guardada = true);
  }

  Future<void> _exportar() async {
    final carga = _carga!;
    final ahora = DateTime.now();
    String dos(int n) => n.toString().padLeft(2, '0');
    final base = carga.archivo.contains('.') ? carga.archivo.substring(0, carga.archivo.lastIndexOf('.')) : carga.archivo;
    final nombre = 'materna_triaje_${base}_${ahora.year}${dos(ahora.month)}${dos(ahora.day)}_${dos(ahora.hour)}${dos(ahora.minute)}.csv';
    final bytes = Uint8List.fromList(utf8.encode(exportarCsv(carga, widget.recursos)));
    final guardado = await (widget.guardarArchivo ?? _guardarConSelector)(nombre, bytes);
    if (guardado && mounted) _aviso('Triaje exportado: $nombre (sin nombres ni documentos).');
  }

  void _abrir(ResultadoFila r) {
    Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => PantallaResultado(
        recursos: widget.recursos,
        evaluacion: r.evaluacion,
        soloLectura: true,
        nota: 'Fila ${r.fila} del archivo',
      ),
    ));
  }

  // ------------------------------------------------------------------ vista
  static TextStyle get _suave => TextStyle(color: ColoresMaterna.tintaSuave, height: 1.4);

  Widget _tarjeta({required List<Widget> hijos, Key? key}) => Card(
        key: key,
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: hijos),
        ),
      );

  static ButtonStyle get _botonRosa => FilledButton.styleFrom(
    backgroundColor: ColoresMaterna.ciruela100,
    foregroundColor: ColoresMaterna.ciruela900,
    minimumSize: const Size(0, 42),
    padding: const EdgeInsets.symmetric(horizontal: 18),
    textStyle: const TextStyle(fontFamily: fuente, fontWeight: FontWeight.w700),
  );

  Widget _clavePanel() {
    if (_clave != null && !_editandoClave) {
      return Card(
        key: const Key('clave-configurada'),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 8, 12),
          child: Row(children: [
            Icon(Icons.key_rounded, color: ColoresMaterna.ciruela900),
            const SizedBox(width: 12),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('Clave de la IPS configurada', style: TextStyle(fontWeight: FontWeight.w700, color: ColoresMaterna.tinta)),
                Text('Código de verificación ${huellaSal(_clave!)} · debe ser el mismo en todos los dispositivos de la IPS',
                    key: const Key('huella-clave'), style: TextStyle(color: ColoresMaterna.tintaSuave, fontSize: 12.5)),
              ]),
            ),
            TextButton(
              key: const Key('cambiar-clave'),
              onPressed: _procesando ? null : () => setState(() => _editandoClave = true),
              child: const Text('Cambiar'),
            ),
          ]),
        ),
      );
    }
    return _tarjeta(key: const Key('configurar-clave'), hijos: [
      Row(children: [
        Icon(Icons.key_rounded, color: ColoresMaterna.ciruela900),
        const SizedBox(width: 10),
        Expanded(child: Text('Clave de la IPS', style: TextStyle(fontWeight: FontWeight.w800, color: ColoresMaterna.tinta))),
        // la explicación (para qué sirve, la misma en toda la IPS, a quién pedirla, qué pasa si cambia) va aquí
        BotonInfoPulso(key: const Key('info-clave'), tooltip: 'Qué es la clave de la IPS', alTocar: _infoClave),
      ]),
      const SizedBox(height: 10),
      TextField(
        key: const Key('campo-clave'),
        controller: _campoClave,
        focusNode: _focoClave,
        obscureText: !_verClave,
        autocorrect: false,
        enableSuggestions: false,
        decoration: InputDecoration(
          labelText: 'Clave de la IPS',
          helperText: _avisoLongitud.ayuda,
          errorText: _avisoLongitud.error,
          suffixIcon: IconButton(
            tooltip: _verClave ? 'Ocultar' : 'Mostrar',
            icon: Icon(_verClave ? Icons.visibility_off_rounded : Icons.visibility_rounded),
            onPressed: () => setState(() => _verClave = !_verClave),
          ),
        ),
      ),
      const SizedBox(height: 10),
      TextField(
        key: const Key('campo-clave-repetir'),
        controller: _campoRepetir,
        obscureText: !_verClave,
        autocorrect: false,
        enableSuggestions: false,
        decoration: const InputDecoration(labelText: 'Repita la clave'),
        onSubmitted: (_) => _guardarClave(),
      ),
      if (_errorClave != null)
        Padding(
          padding: const EdgeInsets.only(top: 8),
          child: Text(_errorClave!, key: const Key('error-clave'), style: TextStyle(color: estiloPorCategoria['Alto Riesgo']!.tinta)),
        ),
      const SizedBox(height: 12),
      FilledButton.icon(
        key: const Key('guardar-clave'),
        onPressed: _guardarClave,
        icon: const Icon(Icons.check_rounded),
        label: const Text('Guardar la clave'),
      ),
      if (_clave != null)
        TextButton(
          onPressed: () => setState(() {
            _editandoClave = false;
            _errorClave = null;
          }),
          child: const Text('Cancelar'),
        ),
    ]);
  }

  /// Sin archivo: qué se puede cargar y el botón para elegirlo. Con archivo: su nombre y «Cambiar».
  Widget _archivoPanel() {
    final carga = _carga;
    final puedeElegir = _clave != null && !_procesando;
    if (carga == null) {
      return TarjetaPunteada(
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text('Archivo con la plantilla 3280', style: TextStyle(fontWeight: FontWeight.w800, color: ColoresMaterna.tinta)),
          const SizedBox(height: 4),
          Text(
            'CSV, TXT separado por «|» o Excel (.xlsx). Los encabezados se reconocen por sus nombres habituales (TAS, '
            'Fetocardia, Glicemia…). Nombres, teléfono y datos administrativos se descartan.',
            style: _suave,
          ),
          const SizedBox(height: 12),
          FilledButton.icon(
            key: const Key('elegir-archivo'),
            onPressed: puedeElegir ? _elegir : null,
            icon: const Icon(Icons.upload_file_rounded),
            label: const Text('Elegir archivo'),
          ),
          if (_clave == null)
            Padding(
              padding: EdgeInsets.only(top: 8),
              child: Text('Primero configure la clave de la IPS.', textAlign: TextAlign.center, style: _suave),
            ),
        ]),
      );
    }
    final r = carga.reporte;
    final formato = r.separador == null
        ? 'Excel (.xlsx)'
        : 'separador ${r.separador == '\t' ? 'tabulador' : r.separador} · ${r.formato}';
    return TarjetaPunteada(
      key: const Key('archivo-cargado'),
      child: Row(children: [
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(carga.archivo,
                overflow: TextOverflow.ellipsis, style: TextStyle(fontWeight: FontWeight.w800, color: ColoresMaterna.tinta)),
            const SizedBox(height: 2),
            Text('${r.filasLeidas - r.filasDuplicadas} registros · $formato',
                style: TextStyle(color: ColoresMaterna.tintaSuave, fontSize: 12.5)),
          ]),
        ),
        const SizedBox(width: 8),
        FilledButton(
          key: const Key('elegir-archivo'),
          style: _botonRosa,
          onPressed: puedeElegir ? _elegir : null,
          child: const Text('Cambiar'),
        ),
      ]),
    );
  }

  Widget _progreso() {
    final (hechas, total) = _avance;
    return _tarjeta(key: const Key('procesando'), hijos: [
      Text(total == 0 ? 'Leyendo el archivo…' : 'Evaluando $hechas de $total registros…',
          style: TextStyle(color: ColoresMaterna.tinta)),
      const SizedBox(height: 10),
      ClipRRect(
        borderRadius: BorderRadius.circular(6),
        child: LinearProgressIndicator(value: total == 0 ? null : hechas / total, minHeight: 6),
      ),
    ]);
  }

  Widget _conteo(int clase) {
    final estilo = estiloPorCategoria[widget.recursos.clasificador.clases[clase]]!;
    return Expanded(
      child: Container(
        key: Key('conteo-$clase'),
        padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 8),
        decoration: BoxDecoration(color: estilo.fondo, borderRadius: BorderRadius.circular(18)),
        child: Column(children: [
          Text('${_carga!.cuantas(clase)}', style: TextStyle(color: estilo.barra, fontSize: 26, fontWeight: FontWeight.w800, height: 1.1)),
          const SizedBox(height: 2),
          Text(estilo.corto, style: TextStyle(color: estilo.tinta, fontWeight: FontWeight.w600)),
        ]),
      ),
    );
  }

  String _etiqueta(String variable) => widget.recursos.catalogo.variable(variable)?.etiqueta ?? variable;

  Widget _desplegable({required Key key, required String titulo, required List<Widget> hijos}) => Card(
        child: Theme(
          data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
          child: ExpansionTile(
            key: key,
            shape: const Border(),
            title: Text(titulo, style: TextStyle(fontWeight: FontWeight.w700, color: ColoresMaterna.tinta)),
            childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
            expandedCrossAxisAlignment: CrossAxisAlignment.start,
            children: hijos,
          ),
        ),
      );

  Widget _resumen() {
    final carga = _carga!;
    final r = carga.reporte;
    final registros = r.filasLeidas - r.filasDuplicadas;
    return Column(key: const Key('resumen-carga'), crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Row(children: [_conteo(2), const SizedBox(width: 10), _conteo(1), const SizedBox(width: 10), _conteo(0)]),
      const SizedBox(height: 10),
      Text(
        '$registros registros (${r.filasLeidas} filas leídas, ${r.filasDuplicadas} repetidas) · '
        '${carga.resultados.length} evaluadas · ${carga.rechazadas.length} sin evaluar',
        key: const Key('totales-carga'),
        textAlign: TextAlign.center,
        style: TextStyle(color: ColoresMaterna.tintaSuave, fontSize: 12.5),
      ),
      const SizedBox(height: 10),
      if (_guardada)
        Container(
          key: const Key('carga-guardada'),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          decoration: BoxDecoration(color: ColoresMaterna.sinConexionFondo, borderRadius: BorderRadius.circular(14)),
          child: Row(children: [
            Icon(Icons.check_circle_rounded, color: ColoresMaterna.sinConexionPunto, size: 20),
            SizedBox(width: 8),
            Expanded(child: Text('Guardadas en el historial de este dispositivo.', style: TextStyle(color: ColoresMaterna.sinConexionTexto))),
          ]),
        )
      else if (_previa != null) ...[
        Container(
          key: const Key('carga-previa'),
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(color: estiloPorCategoria['Riesgo Medio']!.fondo, borderRadius: BorderRadius.circular(14)),
          child: Text(
            'Este archivo ya se cargó el ${fechaLegible(_previa!.fecha)} (${_previa!.evaluadas} evaluadas): no se guardó de '
            'nuevo para no duplicar el historial.',
            style: TextStyle(color: estiloPorCategoria['Riesgo Medio']!.tinta, height: 1.4),
          ),
        ),
        Align(
          alignment: Alignment.centerLeft,
          child: TextButton(key: const Key('guardar-otra-vez'), onPressed: _guardar, child: const Text('Guardar otra vez')),
        ),
      ],
      const SizedBox(height: 10),
      FilledButton.icon(
        key: const Key('exportar-csv'),
        onPressed: _exportar,
        icon: const Icon(Icons.download_rounded),
        label: const Text('Exportar lista priorizada (CSV)'),
      ),
      const SizedBox(height: 12),
      _desplegable(key: const Key('detalle-lectura'), titulo: 'Detalle de la lectura', hijos: [
        for (final linea in [
          'Formato: ${r.formato}${r.separador == null ? '' : ', separador «${r.separador == '\t' ? 'tabulador' : r.separador}»'}',
          'Gestantes distintas: ${r.gestantesUnicas}; con varias atenciones: ${r.gestantesConVariasAtenciones}; '
              'filas sin documento: ${r.sinDocumento}',
          if (r.centinelas.isNotEmpty)
            'Valores «sin dato» (centinelas): ${r.centinelas.entries.map((e) => '${_etiqueta(e.key)} ${e.value}').join(', ')}',
          if (r.fueraDeRango.isNotEmpty)
            'Fuera de rango fisiológico, tomados como vacíos: '
                '${r.fueraDeRango.entries.map((e) => '${_etiqueta(e.key)} ${e.value}').join(', ')}',
          if (r.columnasEliminadas.isNotEmpty) 'Datos personales descartados: ${r.columnasEliminadas.join(', ')}',
          if (r.columnasDesconocidas.isNotEmpty) 'Columnas no reconocidas (descartadas): ${r.columnasDesconocidas.join(', ')}',
        ])
          Padding(padding: const EdgeInsets.only(bottom: 6), child: Text(linea, style: _suave)),
      ]),
      if (carga.rechazadas.isNotEmpty) ...[
        const SizedBox(height: 10),
        _desplegable(key: const Key('filas-sin-evaluar'), titulo: 'Filas sin evaluar (${carga.rechazadas.length})', hijos: [
          for (final f in carga.rechazadas.take(200))
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Text('Fila ${f.fila}: falta ${f.faltan.map(_etiqueta).join(', ').toLowerCase()}', style: _suave),
            ),
          if (carga.rechazadas.length > 200) Text('… y ${carga.rechazadas.length - 200} más (ver el CSV exportado).', style: _suave),
        ]),
      ],
    ]);
  }

  Widget _filtros() => FiltroNivel(
        key: const Key('filtro-carga'),
        seleccion: _filtro,
        alCambiar: (clase) => setState(() => _filtro = clase),
      );

  /// Lo que más pesó en el nivel, para la lista: la regla o el signo de alarma, o la presión arterial.
  String _hallazgo(Evaluacion e) {
    String n(String c) => e.registro[c] is num ? (e.registro[c] as num).round().toString() : '–';
    final primera = e.triaje.reglasActivadas.firstOrNull;
    return switch (e.origen) {
      'signo_alarma_3280' => e.alertasQueEscalan.first.etiqueta,
      'regla_clinica' when primera == 'convulsiones' => 'Convulsiones',
      'regla_clinica' when primera == 'proteinuria' => 'Proteinuria ++',
      _ => 'PAS ${n('pas_mmhg')}/${n('pad_mmhg')}',
    };
  }

  Widget _fila(ResultadoFila r) {
    final e = r.evaluacion;
    final estilo = estiloPorCategoria[widget.recursos.clasificador.clases[e.clase]]!;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Card(
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          key: Key('fila-${r.fila}'),
          onTap: () => _abrir(r),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            child: Row(children: [
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('Fila ${r.fila} del archivo',
                      style: TextStyle(fontWeight: FontWeight.w800, color: ColoresMaterna.tinta, fontSize: 15)),
                  const SizedBox(height: 2),
                  Text(edadYSemanas(e.registro),
                      style: TextStyle(color: ColoresMaterna.tintaSuave, fontSize: 12.5)),
                ]),
              ),
              if (e.urgentesSinEscalar.isNotEmpty)
                Padding(
                  padding: EdgeInsets.only(right: 6),
                  child: Icon(Icons.priority_high_rounded, color: ColoresMaterna.ciruela900, size: 18, semanticLabel: 'Alerta urgente'),
                ),
              ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 130),
                child: Text(_hallazgo(e),
                    textAlign: TextAlign.right,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(color: ColoresMaterna.tinta, fontSize: 12.5)),
              ),
              const SizedBox(width: 8),
              EtiquetaNivel(estilo, key: Key('nivel-${e.clase}')),
            ]),
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final carga = _carga;
    final visibles = carga == null
        ? const <ResultadoFila>[]
        : [for (final r in carga.resultados) if (_filtro == null || r.evaluacion.clase == _filtro) r];
    return SafeArea(
      bottom: false,
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 760),
          child: CustomScrollView(slivers: [
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
              sliver: SliverList.list(children: [
                const EncabezadoMaterna(etiqueta: 'Archivo IPS'),
                const SizedBox(height: 14),
                TituloConIcono(
                  icono: IconoDeTrazo(IconoTrazo.subirArchivo, color: ColoresMaterna.ciruela900, tamano: 26),
                  titulo: 'Carga masiva IPS',
                  subtitulo: 'Triaje ordenado por urgencia · sin internet',
                ),
                const SizedBox(height: 16),
                if (_cargandoClave)
                  const Center(child: Padding(padding: EdgeInsets.all(24), child: CircularProgressIndicator()))
                else ...[
                  _clavePanel(),
                  const SizedBox(height: 12),
                  _archivoPanel(),
                ],
                if (_procesando) ...[const SizedBox(height: 14), _progreso()],
                if (_error != null) ...[
                  const SizedBox(height: 14),
                  Container(
                    key: const Key('error-carga'),
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(color: estiloPorCategoria['Alto Riesgo']!.fondo, borderRadius: BorderRadius.circular(16)),
                    child: Row(children: [
                      Icon(Icons.error_outline_rounded, color: estiloPorCategoria['Alto Riesgo']!.tinta),
                      const SizedBox(width: 10),
                      Expanded(child: Text(_error!, style: TextStyle(color: estiloPorCategoria['Alto Riesgo']!.tinta))),
                    ]),
                  ),
                ],
                if (carga != null) ...[
                  const SizedBox(height: 14),
                  _resumen(),
                  if (carga.resultados.isNotEmpty) ...[
                    const SizedBox(height: 16),
                    _filtros(),
                    const SizedBox(height: 10),
                  ],
                ],
              ]),
            ),
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, BarraFlotante.espacioInferior),
              sliver: SliverList.builder(itemCount: visibles.length, itemBuilder: (_, i) => _fila(visibles[i])),
            ),
          ]),
        ),
      ),
    );
  }
}
