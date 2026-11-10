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
import 'pantalla_historial.dart' show fechaLegible, origenLegible;
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
  String? _errorClave;

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
    super.dispose();
  }

  void _aviso(String texto) => ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(content: Text(texto)));

  // ------------------------------------------------------------------ clave
  Future<void> _guardarClave() async {
    final clave = _campoClave.text;
    final error = !salValida(clave)
        ? 'La clave debe tener al menos $longitudMinimaSal caracteres.'
        : (clave != _campoRepetir.text ? 'Las dos claves no coinciden.' : null);
    if (error != null) {
      setState(() => _errorClave = error);
      return;
    }
    await widget.base.fijarClaveIps(clave);
    if (!mounted) return;
    setState(() {
      _clave = clave;
      _editandoClave = false;
      _errorClave = null;
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
      final previa = await widget.base.cargaPrevia(carga.huellaArchivo);
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
        nota: 'Fila ${r.fila} de ${_carga!.archivo}'
            '${r.idSeudonimo == null ? ' · sin documento' : ' · seudónimo ${r.idSeudonimo!.substring(0, 12)}…'}',
      ),
    ));
  }

  // ------------------------------------------------------------------ vista
  Widget _tarjeta({required IconData icono, required String titulo, required List<Widget> hijos, Key? key}) => Card(
        key: key,
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Row(children: [
              Icon(icono, color: ColoresMaterna.ciruela700, size: 20),
              const SizedBox(width: 8),
              Expanded(child: Text(titulo, style: const TextStyle(fontWeight: FontWeight.w700))),
            ]),
            const SizedBox(height: 10),
            ...hijos,
          ]),
        ),
      );

  static const _suave = TextStyle(color: ColoresMaterna.tintaSuave, height: 1.4);

  Widget _clavePanel() {
    if (_clave != null && !_editandoClave) {
      return _tarjeta(key: const Key('clave-configurada'), icono: Icons.key_rounded, titulo: 'Clave de la IPS configurada', hijos: [
        Text('Huella ${huellaSal(_clave!)}: debe ser la misma en todos los dispositivos de la IPS y en el laboratorio.',
            key: const Key('huella-clave'), style: _suave),
        Align(
          alignment: Alignment.centerLeft,
          child: TextButton.icon(
            key: const Key('cambiar-clave'),
            onPressed: _procesando ? null : () => setState(() => _editandoClave = true),
            icon: const Icon(Icons.edit_rounded, size: 18),
            label: const Text('Cambiar la clave'),
          ),
        ),
      ]);
    }
    return _tarjeta(key: const Key('configurar-clave'), icono: Icons.key_rounded, titulo: 'Clave de la IPS', hijos: [
      const Text(
        'Con ella se reemplaza el documento de cada gestante por un seudónimo (HMAC-SHA256): el documento nunca se '
        'guarda. Debe ser la misma en todos los dispositivos de la IPS; pídala al responsable de datos. '
        'Mínimo $longitudMinimaSal caracteres.',
        style: _suave,
      ),
      if (_clave != null) ...[
        const SizedBox(height: 8),
        const Text(
          'Si cambia la clave, las gestantes ya cargadas tendrán otro seudónimo y no se podrán relacionar con las nuevas.',
          style: TextStyle(color: Color(0xFF6B1832), height: 1.4),
        ),
      ],
      const SizedBox(height: 12),
      TextField(
        key: const Key('campo-clave'),
        controller: _campoClave,
        obscureText: !_verClave,
        autocorrect: false,
        enableSuggestions: false,
        decoration: InputDecoration(
          labelText: 'Clave de la IPS',
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
          child: Text(_errorClave!, key: const Key('error-clave'), style: const TextStyle(color: Color(0xFFB3261E))),
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

  Widget _archivoPanel() => _tarjeta(icono: Icons.description_outlined, titulo: 'Archivo con la plantilla 3280', hijos: [
        const Text(
          'CSV, TXT separado por «|» o Excel (.xlsx). Los encabezados se reconocen por sus nombres habituales (TAS, '
          'Fetocardia, Glicemia…). Nombres, teléfono y datos administrativos se descartan.',
          style: _suave,
        ),
        const SizedBox(height: 12),
        FilledButton.icon(
          key: const Key('elegir-archivo'),
          onPressed: _clave == null || _procesando ? null : _elegir,
          icon: const Icon(Icons.upload_file_rounded),
          label: Text(_carga == null ? 'Elegir archivo' : 'Cargar otro archivo'),
        ),
        if (_clave == null)
          const Padding(
            padding: EdgeInsets.only(top: 8),
            child: Text('Primero configure la clave de la IPS.', style: _suave),
          ),
      ]);

  Widget _progreso() {
    final (hechas, total) = _avance;
    return Card(
      key: const Key('procesando'),
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(total == 0 ? 'Leyendo el archivo…' : 'Evaluando $hechas de $total registros…'),
          const SizedBox(height: 10),
          LinearProgressIndicator(value: total == 0 ? null : hechas / total, color: ColoresMaterna.ciruela700),
        ]),
      ),
    );
  }

  Widget _conteo(int clase) {
    final estilo = estiloPorCategoria[widget.recursos.clasificador.clases[clase]]!;
    return Expanded(
      child: Container(
        key: Key('conteo-$clase'),
        padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 10),
        decoration: BoxDecoration(color: estilo.fondo, borderRadius: BorderRadius.circular(16)),
        child: Column(children: [
          Icon(estilo.icono, color: estilo.tinta),
          Text('${_carga!.cuantas(clase)}', style: TextStyle(color: estilo.tinta, fontSize: 22, fontWeight: FontWeight.w800)),
          Text(estilo.semaforo, style: TextStyle(color: estilo.tinta, fontWeight: FontWeight.w600)),
        ]),
      ),
    );
  }

  String _etiqueta(String variable) => widget.recursos.catalogo.variable(variable)?.etiqueta ?? variable;

  Widget _resumen() {
    final carga = _carga!;
    final r = carga.reporte;
    final registros = r.filasLeidas - r.filasDuplicadas;
    return _tarjeta(key: const Key('resumen-carga'), icono: Icons.fact_check_outlined, titulo: carga.archivo, hijos: [
      Row(children: [_conteo(2), const SizedBox(width: 8), _conteo(1), const SizedBox(width: 8), _conteo(0)]),
      const SizedBox(height: 12),
      Text(
        '$registros registros (${r.filasLeidas} filas leídas, ${r.filasDuplicadas} repetidas) · '
        '${carga.resultados.length} evaluadas · ${carga.rechazadas.length} sin evaluar',
        key: const Key('totales-carga'),
        style: _suave,
      ),
      const SizedBox(height: 10),
      if (_guardada)
        const Row(key: Key('carga-guardada'), children: [
          Icon(Icons.check_circle_rounded, color: Color(0xFF2C5219), size: 20),
          SizedBox(width: 8),
          Expanded(child: Text('Guardadas en el historial de este dispositivo.')),
        ])
      else if (_previa != null) ...[
        Text(
          'Este archivo ya se cargó el ${fechaLegible(_previa!.fecha)} (${_previa!.evaluadas} evaluadas): no se guardó de '
          'nuevo para no duplicar el historial.',
          key: const Key('carga-previa'),
          style: const TextStyle(color: Color(0xFF5A4F0E), height: 1.4),
        ),
        Align(
          alignment: Alignment.centerLeft,
          child: TextButton(key: const Key('guardar-otra-vez'), onPressed: _guardar, child: const Text('Guardar otra vez')),
        ),
      ],
      const SizedBox(height: 8),
      FilledButton.icon(
        key: const Key('exportar-csv'),
        onPressed: _exportar,
        icon: const Icon(Icons.download_rounded),
        label: const Text('Exportar CSV'),
      ),
      const SizedBox(height: 4),
      Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          key: const Key('detalle-lectura'),
          tilePadding: EdgeInsets.zero,
          title: const Text('Detalle de la lectura', style: TextStyle(fontWeight: FontWeight.w600)),
          expandedCrossAxisAlignment: CrossAxisAlignment.start,
          children: [
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
          ],
        ),
      ),
      if (carga.rechazadas.isNotEmpty)
        Theme(
          data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
          child: ExpansionTile(
            key: const Key('filas-sin-evaluar'),
            tilePadding: EdgeInsets.zero,
            title: Text('Filas sin evaluar (${carga.rechazadas.length})', style: const TextStyle(fontWeight: FontWeight.w600)),
            expandedCrossAxisAlignment: CrossAxisAlignment.start,
            children: [
              for (final f in carga.rechazadas.take(200))
                Padding(
                  padding: const EdgeInsets.only(bottom: 6),
                  child: Text('Fila ${f.fila}: falta ${f.faltan.map(_etiqueta).join(', ').toLowerCase()}', style: _suave),
                ),
              if (carga.rechazadas.length > 200) Text('… y ${carga.rechazadas.length - 200} más (ver el CSV exportado).', style: _suave),
            ],
          ),
        ),
    ]);
  }

  Widget _filtros() => SizedBox(
        width: double.infinity,
        child: SegmentedButton<int>(
          key: const Key('filtro-carga'),
          segments: [
            ButtonSegment(value: -1, label: Text('Todas (${_carga!.resultados.length})')),
            ButtonSegment(value: 2, label: Text('Rojo (${_carga!.cuantas(2)})')),
            ButtonSegment(value: 1, label: Text('Ámbar (${_carga!.cuantas(1)})')),
            ButtonSegment(value: 0, label: Text('Verde (${_carga!.cuantas(0)})')),
          ],
          selected: {_filtro ?? -1},
          showSelectedIcon: false,
          onSelectionChanged: (s) => setState(() => _filtro = s.first == -1 ? null : s.first),
        ),
      );

  Widget _fila(ResultadoFila r) {
    final e = r.evaluacion;
    final estilo = estiloPorCategoria[widget.recursos.clasificador.clases[e.clase]]!;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Card(
        child: ListTile(
          key: Key('fila-${r.fila}'),
          onTap: () => _abrir(r),
          contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
          leading: CircleAvatar(backgroundColor: estilo.fondo, child: Icon(estilo.icono, color: estilo.tinta)),
          title: Text('${estilo.semaforo.toUpperCase()} · ${estilo.titulo}', style: const TextStyle(fontWeight: FontWeight.w700)),
          subtitle: Text(
            'Fila ${r.fila} · ${origenLegible[e.origen] ?? e.origen}'
            '${e.origen == 'modelo_ml' ? '' : ': ${motivoDelSemaforo(e, widget.recursos)}'}'
            '${e.urgentesSinEscalar.isEmpty ? '' : ' · alerta urgente de la ruta'}'
            '\n${r.idSeudonimo == null ? 'Sin documento' : 'Seudónimo ${r.idSeudonimo!.substring(0, 12)}…'}',
          ),
          trailing: e.urgentesSinEscalar.isEmpty
              ? null
              : const Icon(Icons.priority_high_rounded, color: ColoresMaterna.ciruela900, semanticLabel: 'Alerta urgente'),
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
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
              sliver: SliverList.list(children: [
                Text('Carga masiva IPS', style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800)),
                const SizedBox(height: 4),
                const Text('Triaje de todas las gestantes de un archivo de la IPS, ordenado por urgencia. Sin internet.',
                    style: TextStyle(color: ColoresMaterna.tintaSuave)),
                const SizedBox(height: 14),
                if (_cargandoClave)
                  const Center(child: Padding(padding: EdgeInsets.all(24), child: CircularProgressIndicator()))
                else ...[
                  _clavePanel(),
                  const SizedBox(height: 14),
                  _archivoPanel(),
                ],
                if (_procesando) ...[const SizedBox(height: 14), _progreso()],
                if (_error != null) ...[
                  const SizedBox(height: 14),
                  Container(
                    key: const Key('error-carga'),
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(color: const Color(0xFFF099AB).withValues(alpha: .5), borderRadius: BorderRadius.circular(16)),
                    child: Row(children: [
                      const Icon(Icons.error_outline_rounded, color: Color(0xFF6B1832)),
                      const SizedBox(width: 10),
                      Expanded(child: Text(_error!, style: const TextStyle(color: Color(0xFF6B1832)))),
                    ]),
                  ),
                ],
                if (carga != null) ...[
                  const SizedBox(height: 14),
                  _resumen(),
                  if (carga.resultados.isNotEmpty) ...[
                    const SizedBox(height: 14),
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
