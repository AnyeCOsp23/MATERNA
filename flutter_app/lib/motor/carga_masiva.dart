/// Carga masiva de un archivo de la IPS con la plantilla de la Resolución 3280 (pestaña «Carga IPS»).
///
/// Traduce `src/carga_masiva.py`, que se apoya en `inspeccionar_ips.py` y `filtro_3280.py`, y debe dar lo mismo
/// fila por fila (lo verifica `test/carga_test.dart` con el ejemplo ficticio de la IPS):
///   1. Centinelas ('1845-01-01', '9999', '999') -> vacío en las columnas clínicas.
///   2. Filtro 3280: reconoce los encabezados por los sinónimos del catálogo, seudonimiza el documento con
///      HMAC-SHA256, descarta nombres, datos administrativos y columnas desconocidas, y convierte cada columna a
///      su tipo (lo imposible fisiológicamente queda vacío).
///   3. Quita las filas repetidas y evalúa cada registro con el sistema híbrido (reglas críticas, signos de
///      alarma de la ruta y modelo). Las filas sin una variable obligatoria no se evalúan y se informan.
///   4. Ordena por urgencia: rojo > ámbar > verde y, en cada color, de mayor a menor probabilidad de Alto Riesgo.
library;

import 'dart:convert';
import 'dart:typed_data';

import 'package:crypto/crypto.dart';

import '../datos/lector_ips.dart';
import '../datos/seudonimizacion.dart';
import 'catalogo_3280.dart';
import 'recursos.dart';

const centinelas = {'1845-01-01', '9999', '999'};
const _verdadero = {'1', 'si', 's', 'true', 'verdadero', 'x', 'positivo', 'reactivo'};
const _falso = {'0', 'no', 'n', 'false', 'falso', 'negativo', 'no reactivo'};
const _decisionesReportadas = ['modelo', 'capturar_alertar', 'auditoria'];
const _conNulos = ['glucosa_mgdl', 'fcf_bpm'];
const columnaSeudonimo = 'id_seudonimo';

const _sinTilde = {
  'á': 'a', 'à': 'a', 'â': 'a', 'ä': 'a', 'ã': 'a', 'å': 'a', 'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
  'í': 'i', 'ì': 'i', 'î': 'i', 'ï': 'i', 'ó': 'o', 'ò': 'o', 'ô': 'o', 'ö': 'o', 'õ': 'o', 'ú': 'u',
  'ù': 'u', 'û': 'u', 'ü': 'u', 'ñ': 'n', 'ç': 'c', 'ý': 'y', 'ÿ': 'y', 'º': 'o', 'ª': 'a',
};

/// 'Presión Sistólica ' -> 'presion_sistolica' (como normalizar_nombre de Python: quita tildes y lo que no es ASCII).
String normalizarNombre(String texto) {
  final ascii = StringBuffer();
  for (final c in texto.split('')) {
    final sin = _sinTilde[c] ?? _sinTilde[c.toLowerCase()]?.toUpperCase() ?? c;
    if (sin.codeUnitAt(0) < 128) ascii.write(sin);
  }
  return ascii
      .toString()
      .trim()
      .toLowerCase()
      .replaceAll('-', ' ')
      .replaceAll('/', ' ')
      .split(RegExp(r'\s+'))
      .where((p) => p.isNotEmpty)
      .join('_');
}

/// Lo mismo que ReporteInspeccion de Python (sin los porcentajes de nulos).
class ReporteCarga {
  ReporteCarga({required this.formato, required this.separador});

  final String formato;
  final String? separador;
  var filasLeidas = 0;
  var columnasPorDecision = <String, List<String>>{};
  var columnasEliminadas = <String>[];
  var columnasDesconocidas = <String>[];
  final centinelas = <String, int>{};
  final fueraDeRango = <String, int>{};
  var filasDuplicadas = 0;
  var gestantesUnicas = 0;
  var gestantesConVariasAtenciones = 0;
  var sinDocumento = 0;
  var aptas = 0;

  /// Variable obligatoria -> filas a las que les falta; null si la columna no está en el archivo.
  var faltantes = <String, int?>{};
}

/// Una fila del archivo ya filtrada: sin nombres ni documento.
class RegistroIps {
  const RegistroIps({required this.fila, required this.idSeudonimo, required this.datos});

  /// Fila como la numera Excel (el encabezado es la fila 1; las filas vacías no se cuentan).
  final int fila;
  final String? idSeudonimo;

  /// Columna del catálogo -> valor convertido (double, String o null).
  final Map<String, Object?> datos;

  /// El registro para el sistema híbrido: sin fechas, con glucosa y FCF aunque falten.
  Map<String, dynamic> registro(Catalogo3280 catalogo) => {
        for (final e in datos.entries)
          if (catalogo.variable(e.key)?.tipo != 'fecha') e.key: e.key == 'convulsiones' && e.value != null ? (e.value as double).toInt() : e.value,
        for (final c in _conNulos)
          if (!datos.containsKey(c)) c: null,
      };
}

class ResultadoFila {
  const ResultadoFila({required this.fila, required this.idSeudonimo, required this.evaluacion});

  final int fila;
  final String? idSeudonimo;
  final Evaluacion evaluacion;
}

class FilaRechazada {
  const FilaRechazada({required this.fila, required this.faltan});

  final int fila;
  final List<String> faltan;
}

class CargaMasiva {
  const CargaMasiva({
    required this.archivo,
    required this.huellaArchivo,
    required this.reporte,
    required this.resultados,
    required this.rechazadas,
  });

  final String archivo;

  /// SHA-256 del archivo, para avisar si ya se cargó antes.
  final String huellaArchivo;
  final ReporteCarga reporte;

  /// Ordenados por urgencia.
  final List<ResultadoFila> resultados;
  final List<FilaRechazada> rechazadas;

  int cuantas(int clase) => resultados.where((r) => r.evaluacion.clase == clase).length;
}

// ------------------------------------------------------------------ filtro 3280 e inspección
class _Columna {
  _Columna(this.indice, this.variable);

  final int indice;
  final VariableCatalogo variable;
}

Map<String, VariableCatalogo> _mapaSinonimos(Catalogo3280 catalogo) => {
      for (final v in catalogo.variables)
        for (final alias in [v.nombre, ...v.sinonimos]) normalizarNombre(alias): v,
    };

Object? _convertir(VariableCatalogo v, String? texto, ReporteCarga reporte) {
  if (texto == null) return null;
  switch (v.tipo) {
    case 'entero' || 'decimal':
      final numero = double.tryParse(texto.trim().replaceAll(',', '.'));
      if (numero == null || !numero.isFinite) return null;
      final rango = v.rango;
      if (rango != null && (numero < rango[0] || numero > rango[1])) {
        reporte.fueraDeRango[v.nombre] = (reporte.fueraDeRango[v.nombre] ?? 0) + 1;
        return null;
      }
      return numero;
    case 'binaria':
      final t = normalizarNombre(texto.trim().toLowerCase()).replaceAll('_', ' ');
      return _verdadero.contains(t) ? 1.0 : (_falso.contains(t) ? 0.0 : null);
    case 'categorica' when v.valores.isNotEmpty:
      final clave = normalizarNombre(texto);
      for (final valor in v.valores) {
        if (normalizarNombre(valor) == clave) return valor;
      }
      return null;
    case 'fecha':
      final m = RegExp(r'^(\d{4})-(\d{1,2})-(\d{1,2})$').firstMatch(texto);
      if (m == null) return null;
      final (a, mes, d) = (int.parse(m[1]!), int.parse(m[2]!), int.parse(m[3]!));
      final fecha = DateTime(a, mes, d);
      if (fecha.month != mes || fecha.day != d) return null; // p. ej. 2026-02-30
      return '$a-${mes.toString().padLeft(2, '0')}-${d.toString().padLeft(2, '0')}';
    default:
      return texto;
  }
}

/// Filtra la tabla como inspeccionar(..., con_fila=True) de Python. Devuelve los registros sin duplicados y el reporte.
(List<RegistroIps>, ReporteCarga) inspeccionarTabla(TablaIps tabla, Catalogo3280 catalogo, String sal) {
  final reporte = ReporteCarga(formato: tabla.formato, separador: tabla.separador)..filasLeidas = tabla.filas.length;
  final sinonimos = _mapaSinonimos(catalogo);

  // columnas reconocidas: la primera de cada variable del catálogo, en el orden del archivo
  final columnas = <String, _Columna>{};
  final todasLasReconocidas = <_Columna>[];
  for (final (i, nombre) in tabla.encabezado.indexed) {
    final v = sinonimos[normalizarNombre(nombre)];
    if (v == null) {
      reporte.columnasDesconocidas.add(nombre);
      continue;
    }
    todasLasReconocidas.add(_Columna(i, v));
    columnas.putIfAbsent(v.nombre, () => _Columna(i, v));
  }
  reporte.columnasEliminadas = [for (final c in columnas.values) if (c.variable.decision == 'eliminar') c.variable.nombre];
  final clinicas = [for (final c in columnas.values) if (!const {'seudonimizar', 'eliminar'}.contains(c.variable.decision)) c];
  reporte.columnasPorDecision = {
    for (final d in _decisionesReportadas) d: [for (final c in clinicas) if (c.variable.decision == d) c.variable.nombre],
  };
  final tipo = columnas['tipo_documento'];
  final numero = columnas['numero_documento'];

  final registros = <RegistroIps>[];
  final vistos = <String>{};
  for (final (k, crudo) in tabla.filas.indexed) {
    final fila = List<String?>.of(crudo);
    for (final c in todasLasReconocidas) {
      if (const {'seudonimizar', 'eliminar'}.contains(c.variable.decision)) continue;
      if (fila[c.indice] != null && centinelas.contains(fila[c.indice]!.trim())) {
        reporte.centinelas[c.variable.nombre] = (reporte.centinelas[c.variable.nombre] ?? 0) + 1;
        fila[c.indice] = null;
      }
    }
    String? seudonimo;
    if (numero != null) {
      final n = fila[numero.indice];
      if (n != null && n.trim().isNotEmpty) seudonimo = seudonimizar(tipo == null ? '' : fila[tipo.indice] ?? '', n, sal);
    }
    final datos = {for (final c in clinicas) c.variable.nombre: _convertir(c.variable, fila[c.indice], reporte)};
    final clave = jsonEncode([seudonimo, ...datos.values]);
    if (!vistos.add(clave)) {
      reporte.filasDuplicadas++;
      continue;
    }
    registros.add(RegistroIps(fila: k + 2, idSeudonimo: seudonimo, datos: datos));
  }

  if (numero != null) {
    final conteo = <String, int>{};
    for (final r in registros) {
      if (r.idSeudonimo == null) {
        reporte.sinDocumento++;
      } else {
        conteo[r.idSeudonimo!] = (conteo[r.idSeudonimo!] ?? 0) + 1;
      }
    }
    reporte.gestantesUnicas = conteo.length;
    reporte.gestantesConVariasAtenciones = conteo.values.where((n) => n > 1).length;
  }

  final obligatorias = obligatoriasDelModelo(catalogo);
  final ausentes = [for (final c in obligatorias) if (!columnas.containsKey(c)) c];
  if (ausentes.isNotEmpty || registros.isEmpty) {
    reporte.faltantes = {for (final c in ausentes) c: null};
  } else {
    for (final c in obligatorias) {
      final n = registros.where((r) => r.datos[c] == null).length;
      if (n > 0) reporte.faltantes[c] = n;
    }
    reporte.aptas = registros.where((r) => obligatorias.every((c) => r.datos[c] != null)).length;
  }
  return (registros, reporte);
}

/// Variables del modelo sin las que no se puede evaluar (glucosa y FCF se imputan si faltan).
List<String> obligatoriasDelModelo(Catalogo3280 catalogo) =>
    [for (final v in catalogo.porDecision('modelo')) if (!_conNulos.contains(v.nombre)) v.nombre];

// ------------------------------------------------------------------ evaluación
/// Evalúa todas las filas de un archivo. Cede el control cada [cadaCuantas] filas para que la pantalla muestre
/// el avance y no se congele con archivos grandes.
Future<CargaMasiva> procesarCarga({
  required String nombre,
  required Uint8List bytes,
  required RecursosMaterna recursos,
  required String sal,
  void Function(int hechas, int total)? alAvanzar,
  int cadaCuantas = 100,
}) async {
  final tabla = leerArchivoIps(nombre, bytes);
  final (registros, reporte) = inspeccionarTabla(tabla, recursos.catalogo, sal);
  final obligatorias = obligatoriasDelModelo(recursos.catalogo);
  final resultados = <ResultadoFila>[];
  final rechazadas = <FilaRechazada>[];
  for (final (i, r) in registros.indexed) {
    if (i % cadaCuantas == 0) {
      alAvanzar?.call(i, registros.length);
      await Future<void>.delayed(Duration.zero);
    }
    final registro = r.registro(recursos.catalogo);
    final faltan = [for (final c in obligatorias) if (registro[c] == null) c];
    if (faltan.isNotEmpty) {
      rechazadas.add(FilaRechazada(fila: r.fila, faltan: faltan));
    } else {
      resultados.add(ResultadoFila(fila: r.fila, idSeudonimo: r.idSeudonimo, evaluacion: recursos.evaluar(registro)));
    }
  }
  alAvanzar?.call(registros.length, registros.length);
  resultados.sort((a, b) {
    final porClase = b.evaluacion.clase.compareTo(a.evaluacion.clase);
    if (porClase != 0) return porClase;
    final porAlto = b.evaluacion.triaje.probabilidades[2].compareTo(a.evaluacion.triaje.probabilidades[2]);
    return porAlto != 0 ? porAlto : a.fila.compareTo(b.fila);
  });
  return CargaMasiva(
    archivo: nombre,
    huellaArchivo: sha256.convert(bytes).toString(),
    reporte: reporte,
    resultados: resultados,
    rechazadas: rechazadas,
  );
}

// ------------------------------------------------------------------ exportación
const _semaforo = ['Verde', 'Ámbar', 'Rojo'];

String _celdaCsv(Object? v) {
  final t = v == null ? '' : '$v';
  return RegExp(r'[",\n\r]').hasMatch(t) ? '"${t.replaceAll('"', '""')}"' : t;
}

/// CSV con el triaje ordenado y las filas sin evaluar. Sin nombres ni documentos: solo el seudónimo.
/// Lleva BOM para que Excel muestre bien las tildes.
String exportarCsv(CargaMasiva carga, RecursosMaterna recursos) {
  final clases = recursos.clasificador.clases;
  final version = recursos.clasificador.version;
  final lineas = [
    'fila,id_seudonimo,semaforo,categoria,origen,motivo,prob_bajo,prob_medio,prob_alto,alertas_ruta,version_modelo',
    for (final r in carga.resultados)
      [
        r.fila,
        r.idSeudonimo,
        _semaforo[r.evaluacion.clase],
        clases[r.evaluacion.clase],
        r.evaluacion.origen,
        recursos.motivo(r.evaluacion),
        for (final p in r.evaluacion.triaje.probabilidades) p.toStringAsFixed(4),
        [for (final a in r.evaluacion.alertas) a.variable].join(';'),
        version,
      ].map(_celdaCsv).join(','),
    for (final r in carga.rechazadas)
      [r.fila, null, 'Sin evaluar', null, null, 'Falta: ${r.faltan.join(', ')}', null, null, null, null, version]
          .map(_celdaCsv)
          .join(','),
  ];
  return '\u{FEFF}${lineas.join('\r\n')}\r\n';
}
