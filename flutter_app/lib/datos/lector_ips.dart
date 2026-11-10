/// Lectura de un archivo de la IPS: CSV o TXT (separador «|», «,», «;» o tabulador; UTF-8 o Latin-1) y Excel .xlsx.
///
/// Traduce la lectura de `src/inspeccionar_ips.py` (que usa pandas y openpyxl) para que la app vea las mismas
/// celdas que el Módulo 1: la misma detección de codificación y de separador, los mismos textos que pandas toma
/// como vacíos y, en Excel, los números enteros sin «.0» y las fechas como AAAA-MM-DD. Todo es texto: el filtro
/// de la Resolución 3280 (motor/carga_masiva.dart) convierte después cada columna a su tipo.
library;

import 'dart:convert';
import 'dart:typed_data';

import 'package:archive/archive.dart';
import 'package:xml/xml.dart';

/// Lo que pandas toma como vacío al leer un CSV (STR_NA_VALUES de pandas), además de la celda vacía.
const _vaciosPandas = {
  '#N/A', '#N/A N/A', '#NA', '-1.#IND', '-1.#QNAN', '-NaN', '-nan', '1.#IND', '1.#QNAN', '<NA>', 'N/A', 'NA', 'NULL',
  'NaN', 'None', 'n/a', 'nan', 'null',
};

/// Separadores que se prueban, en el orden de preferencia de csv.Sniffer de Python ante un empate.
const _separadores = [',', '\t', ';', '|'];

const extensionesIps = ['csv', 'txt', 'xlsx'];

class TablaIps {
  const TablaIps({required this.formato, required this.separador, required this.encabezado, required this.filas});

  /// 'utf-8-sig', 'latin-1' o 'xlsx' (los mismos nombres del reporte de Python).
  final String formato;
  final String? separador;
  final List<String> encabezado;

  /// Una lista por fila de datos, del largo del encabezado; null es una celda vacía.
  final List<List<String?>> filas;
}

/// Error de formato con un mensaje para mostrar en pantalla.
class ArchivoIpsInvalido implements Exception {
  const ArchivoIpsInvalido(this.mensaje);

  final String mensaje;

  @override
  String toString() => mensaje;
}

TablaIps leerArchivoIps(String nombre, Uint8List bytes) {
  final extension = nombre.contains('.') ? nombre.substring(nombre.lastIndexOf('.') + 1).toLowerCase() : '';
  if (extension == 'xlsx') return _leerExcel(bytes);
  if (const {'xls', 'xlsb', 'xlsm'}.contains(extension)) {
    throw ArchivoIpsInvalido('Formato .$extension no soportado: guarde el archivo como .xlsx o .csv.');
  }
  return _leerTexto(bytes);
}

// ------------------------------------------------------------------ CSV / TXT
TablaIps _leerTexto(Uint8List bytes) {
  String texto;
  String formato;
  try {
    texto = utf8.decode(bytes);
    formato = 'utf-8-sig';
  } on FormatException {
    texto = latin1.decode(bytes);
    formato = 'latin-1';
  }
  if (texto.startsWith('\u{FEFF}')) texto = texto.substring(1); // BOM de UTF-8, como 'utf-8-sig'
  final separador = detectarSeparador(texto);
  final filas = _filasCsv(texto, separador);
  if (filas.isEmpty) throw const ArchivoIpsInvalido('El archivo está vacío.');
  final encabezado = _nombresUnicos([
    for (final (i, c) in filas.first.indexed) (c == null || c.isEmpty) ? 'Unnamed: $i' : c,
  ]);
  final datos = <List<String?>>[];
  for (final (i, fila) in filas.skip(1).indexed) {
    if (fila.length > encabezado.length) {
      throw ArchivoIpsInvalido('La fila ${i + 2} tiene ${fila.length} columnas y el encabezado ${encabezado.length}.');
    }
    datos.add([
      for (var j = 0; j < encabezado.length; j++)
        j < fila.length && fila[j] != null && !_vaciosPandas.contains(fila[j]) ? fila[j] : null,
    ]);
  }
  return TablaIps(formato: formato, separador: separador, encabezado: encabezado, filas: datos);
}

/// El separador que aparece el mismo número de veces en más de las primeras 20 líneas (como csv.Sniffer).
String detectarSeparador(String texto) {
  final lineas = const LineSplitter().convert(texto).take(20).where((l) => l.trim().isNotEmpty).toList();
  var mejor = ',';
  var mejorPuntaje = 0;
  for (final s in _separadores) {
    final frecuencia = <int, int>{};
    for (final l in lineas) {
      final n = _contarFueraDeComillas(l, s);
      if (n > 0) frecuencia[n] = (frecuencia[n] ?? 0) + 1;
    }
    final puntaje = frecuencia.values.fold(0, (a, b) => a > b ? a : b);
    if (puntaje > mejorPuntaje) {
      mejor = s;
      mejorPuntaje = puntaje;
    }
  }
  return mejor;
}

int _contarFueraDeComillas(String linea, String separador) {
  var n = 0;
  var comillas = false;
  for (final c in linea.split('')) {
    if (c == '"') comillas = !comillas;
    if (c == separador && !comillas) n++;
  }
  return n;
}

/// Filas de un CSV con comillas dobles (RFC 4180). Quita los espacios al inicio de cada campo y salta las
/// líneas en blanco, como pandas con skipinitialspace. Un campo vacío es null.
List<List<String?>> _filasCsv(String texto, String separador) {
  final filas = <List<String?>>[];
  var fila = <String?>[];
  final campo = StringBuffer();
  var entreComillas = false;
  var citado = false; // el campo actual empezó con comillas
  var lineaConContenido = false;

  void cerrarCampo() {
    fila.add(campo.isEmpty ? null : campo.toString());
    campo.clear();
    citado = false;
  }

  void cerrarFila() {
    cerrarCampo();
    if (lineaConContenido) filas.add(fila);
    fila = <String?>[];
    lineaConContenido = false;
  }

  for (var i = 0; i < texto.length; i++) {
    final c = texto[i];
    if (entreComillas) {
      if (c == '"') {
        if (i + 1 < texto.length && texto[i + 1] == '"') {
          campo.write('"');
          i++;
        } else {
          entreComillas = false;
        }
      } else {
        campo.write(c);
      }
    } else if (c == '"' && campo.isEmpty && !citado) {
      entreComillas = citado = lineaConContenido = true;
    } else if (c == separador) {
      cerrarCampo();
      lineaConContenido = true;
    } else if (c == '\n' || c == '\r') {
      if (c == '\r' && i + 1 < texto.length && texto[i + 1] == '\n') i++;
      cerrarFila();
    } else if ((c == ' ' || c == '\t') && campo.isEmpty && !citado) {
      continue; // skipinitialspace
    } else {
      campo.write(c);
      lineaConContenido = true;
    }
  }
  if (lineaConContenido || campo.isNotEmpty) cerrarFila();
  return filas;
}

/// Encabezados repetidos como los deja pandas: 'TAS', 'TAS.1', 'TAS.2'…
List<String> _nombresUnicos(List<String> nombres) {
  final vistos = <String>{};
  return [
    for (final n in nombres)
      () {
        var candidato = n;
        for (var k = 1; vistos.contains(candidato); k++) {
          candidato = '$n.$k';
        }
        vistos.add(candidato);
        return candidato;
      }(),
  ];
}

// ------------------------------------------------------------------ Excel
// Lector propio del .xlsx (un .zip con XML): lee la primera hoja con los valores ya calculados, como openpyxl con
// data_only=True. No se usa el paquete excel porque falla con los archivos que genera openpyxl (rutas absolutas y
// texto en línea), que son justamente la plantilla y el ejemplo del Módulo 1.

/// Formatos de número predefinidos de Excel que son fecha u hora (ECMA-376, 18.8.30).
const _formatosFechaPredefinidos = {14, 15, 16, 17, 22};
const _formatosHoraPredefinidos = {18, 19, 20, 21, 45, 46, 47};

TablaIps _leerExcel(Uint8List bytes) {
  final Archive zip;
  try {
    zip = ZipDecoder().decodeBytes(bytes);
  } catch (_) {
    throw const ArchivoIpsInvalido('No se pudo leer el Excel: ¿está dañado o protegido con contraseña?');
  }
  XmlDocument? xml(String ruta) {
    final f = zip.findFile(ruta);
    return f == null ? null : XmlDocument.parse(utf8.decode(f.content as List<int>));
  }

  final libro = xml('xl/workbook.xml');
  final primera = libro?.findAllElements('sheet').firstOrNull; // la primera hoja, como en Python
  if (libro == null || primera == null) throw const ArchivoIpsInvalido('El Excel no tiene hojas.');
  final id = primera.attributes.where((a) => a.name.local == 'id').firstOrNull?.value;
  final destino = xml('xl/_rels/workbook.xml.rels')
      ?.findAllElements('Relationship')
      .where((r) => r.getAttribute('Id') == id)
      .firstOrNull
      ?.getAttribute('Target');
  // openpyxl escribe la ruta absoluta ('/xl/worksheets/sheet1.xml'); Excel, relativa ('worksheets/sheet1.xml')
  final hoja = destino == null ? null : xml(destino.startsWith('/') ? destino.substring(1) : 'xl/$destino');
  if (hoja == null) throw const ArchivoIpsInvalido('No se encontró la primera hoja del Excel.');

  final compartidos = [
    for (final si in xml('xl/sharedStrings.xml')?.findAllElements('si') ?? const <XmlElement>[]) _textoDe(si),
  ];
  final estilos = xml('xl/styles.xml');
  final formatos = {
    for (final f in estilos?.findAllElements('numFmt') ?? const <XmlElement>[])
      int.parse(f.getAttribute('numFmtId')!): f.getAttribute('formatCode') ?? '',
  };
  final tipoPorEstilo = [
    for (final xf in estilos?.findAllElements('cellXfs').firstOrNull?.findElements('xf') ?? const <XmlElement>[])
      _tipoDeFormato(int.tryParse(xf.getAttribute('numFmtId') ?? '0') ?? 0, formatos),
  ];
  final opcion1904 = libro.findAllElements('workbookPr').firstOrNull?.getAttribute('date1904');
  final fecha1904 = opcion1904 == '1' || opcion1904 == 'true';

  final filas = <int, Map<int, String?>>{};
  var ancho = 0;
  for (final (k, fila) in hoja.findAllElements('row').indexed) {
    final r = int.tryParse(fila.getAttribute('r') ?? '') ?? k + 1;
    final celdas = <int, String?>{};
    var siguiente = 0;
    for (final c in fila.findElements('c')) {
      final col = _columna(c.getAttribute('r')) ?? siguiente;
      siguiente = col + 1;
      final estilo = int.tryParse(c.getAttribute('s') ?? '');
      final tipo = estilo != null && estilo < tipoPorEstilo.length ? tipoPorEstilo[estilo] : null;
      celdas[col] = _valorCelda(c, compartidos, tipo, fecha1904);
      if (col + 1 > ancho) ancho = col + 1;
    }
    filas[r] = celdas;
  }
  final orden = filas.keys.toList()..sort();
  if (orden.isEmpty) throw const ArchivoIpsInvalido('La primera hoja del Excel está vacía.');
  final encabezado = [for (var j = 0; j < ancho; j++) filas[orden.first]![j]?.trim() ?? 'columna_$j'];
  final datos = <List<String?>>[];
  for (final r in orden.skip(1)) {
    final valores = [for (var j = 0; j < ancho; j++) filas[r]![j]];
    if (valores.every((v) => v == null)) continue;
    datos.add(valores);
  }
  return TablaIps(formato: 'xlsx', separador: null, encabezado: encabezado, filas: datos);
}

/// Texto de una cadena de Excel, también con formato enriquecido (sin la guía fonética).
String _textoDe(XmlElement nodo) => [
      for (final t in nodo.findAllElements('t'))
        if (t.parentElement?.name.local != 'rPh') t.innerText,
    ].join();

/// 'AB12' -> 27 (columna desde 0).
int? _columna(String? referencia) {
  final letras = RegExp(r'^[A-Z]+').firstMatch(referencia ?? '')?[0];
  if (letras == null) return null;
  return letras.codeUnits.fold<int>(0, (n, c) => n * 26 + c - 64) - 1;
}

/// 'fecha', 'hora' o null según el formato de número (como is_date_format e is_datetime de openpyxl).
String? _tipoDeFormato(int id, Map<int, String> formatos) {
  if (_formatosFechaPredefinidos.contains(id)) return 'fecha';
  if (_formatosHoraPredefinidos.contains(id)) return 'hora';
  final codigo = formatos[id];
  if (codigo == null) return null;
  final limpio = codigo.split(';').first.replaceAll(RegExp(r'".*?"|\[(?!hh?\]|mm?\]|ss?\])[^\]]*\]'), '');
  if (!RegExp(r'(?<![_\\])[dmhysDMHYS]').hasMatch(limpio)) return null;
  return RegExp('[dy]').hasMatch(limpio) ? 'fecha' : 'hora';
}

String _dos(int n) => n.toString().padLeft(2, '0');

/// Igual que _celda_a_texto de Python: 1065432.0 -> '1065432' (documentos guardados como número), fechas AAAA-MM-DD.
String? _valorCelda(XmlElement c, List<String> compartidos, String? tipoFormato, bool fecha1904) {
  final v = c.findElements('v').firstOrNull?.innerText;
  final enLinea = c.findElements('is').firstOrNull;
  final texto = switch (c.getAttribute('t')) {
    's' => v == null ? null : compartidos[int.parse(v)],
    'inlineStr' => enLinea == null ? null : _textoDe(enLinea),
    'str' || 'e' => v, // resultado de una fórmula de texto, o un error como #N/A
    'b' => v == null ? null : (v == '1' ? 'True' : 'False'),
    'd' => v == null || v.length < 10 ? v : v.substring(0, 10),
    _ => _numeroDeCelda(v, tipoFormato, fecha1904),
  };
  return texto == null || texto.isEmpty ? null : texto;
}

String? _numeroDeCelda(String? v, String? tipoFormato, bool fecha1904) {
  final numero = v == null ? null : double.tryParse(v);
  if (numero == null) return v;
  if (tipoFormato != null) {
    final base = fecha1904 ? DateTime.utc(1904) : DateTime.utc(1899, 12, 30);
    final f = base.add(Duration(milliseconds: (numero * 86400000).round()));
    return tipoFormato == 'fecha'
        ? '${f.year}-${_dos(f.month)}-${_dos(f.day)}'
        : '${_dos(f.hour)}:${_dos(f.minute)}:${_dos(f.second)}';
  }
  return numero == numero.truncateToDouble() && numero.abs() < 1e15 ? '${numero.toInt()}' : '$numero';
}
