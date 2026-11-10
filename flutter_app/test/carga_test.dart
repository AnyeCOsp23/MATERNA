// Paridad de la carga masiva con Python: el ejemplo ficticio de la IPS (data/ejemplos/, el mismo que usa la ingesta
// del Módulo 1) debe dar en Dart el mismo reporte, el mismo triaje ordenado y los mismos seudónimos que
// assets/casos_carga.json, generado por src/exportar_a_dart.py con src/carga_masiva.py y una sal SOLO de prueba.
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:archive/archive.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:materna/datos/lector_ips.dart';
import 'package:materna/datos/seudonimizacion.dart';
import 'package:materna/motor/carga_masiva.dart';

import 'flujo_test.dart' show recursos;

final casos = jsonDecode(File('assets/casos_carga.json').readAsStringSync()) as Map<String, dynamic>;
final sal = casos['sal_prueba'] as String;
final esperado = casos['reporte'] as Map<String, dynamic>;
final ejemplo = File('../${casos['archivo']}');

Uint8List bytes(String texto, {Encoding codificacion = utf8}) => Uint8List.fromList(codificacion.encode(texto));

Future<CargaMasiva> cargar(String nombre, Uint8List contenido) =>
    procesarCarga(nombre: nombre, bytes: contenido, recursos: recursos, sal: sal);

void compararConPython(CargaMasiva carga) {
  final r = carga.reporte;
  expect(r.filasLeidas, esperado['filas_leidas']);
  expect(r.columnasPorDecision, esperado['columnas_por_decision']);
  expect(r.columnasEliminadas, esperado['columnas_eliminadas']);
  expect(r.columnasDesconocidas, esperado['columnas_desconocidas']);
  expect(r.centinelas, esperado['centinelas']);
  expect(r.fueraDeRango, esperado['fuera_de_rango']);
  expect(r.filasDuplicadas, esperado['filas_duplicadas_eliminadas']);
  expect(r.gestantesUnicas, esperado['gestantes_unicas']);
  expect(r.gestantesConVariasAtenciones, esperado['gestantes_con_varias_atenciones']);
  expect(r.sinDocumento, esperado['sin_documento']);
  expect(r.aptas, esperado['aptas_modelo']);
  expect(r.faltantes, esperado['faltantes_que_impiden_modelo']);

  expect([for (final f in carga.rechazadas) {'fila': f.fila, 'faltan': f.faltan}], casos['rechazadas']);
  final resultados = casos['resultados'] as List;
  expect(carga.resultados, hasLength(resultados.length));
  final tolerancia = (casos['tolerancia'] as num).toDouble();
  for (final (i, c) in resultados.cast<Map<String, dynamic>>().indexed) {
    final r = carga.resultados[i];
    final e = r.evaluacion;
    final motivo = 'posición $i (fila ${c['fila']})';
    expect(r.fila, c['fila'], reason: motivo); // mismo orden por urgencia
    expect(r.idSeudonimo, c['id_seudonimo'], reason: motivo);
    expect(e.clase, c['clase'], reason: motivo);
    expect(e.origen, c['origen'], reason: motivo);
    expect(e.triaje.claseModelo, c['clase_modelo'], reason: motivo);
    expect(e.triaje.reglasActivadas, hasLength(c['n_signos_criticos'] as int), reason: motivo);
    expect(e.signosAlarma, c['signos_alarma'], reason: motivo);
    expect([for (final a in e.alertas) a.variable], c['alertas'], reason: motivo);
    for (final (k, p) in (c['probabilidades'] as List).indexed) {
      expect(e.triaje.probabilidades[k], closeTo((p as num).toDouble(), tolerancia), reason: motivo);
    }
  }
}

void main() {
  group('seudonimización HMAC-SHA256', () {
    test('mismos seudónimos que src/seudonimizacion.py', () {
      for (final c in (casos['seudonimos'] as List).cast<Map<String, dynamic>>()) {
        expect(seudonimizar(c['tipo'] as String, c['numero'] as String, sal), c['id_seudonimo'], reason: '${c['tipo']} ${c['numero']}');
      }
    });

    test('la clave importa, el documento nunca aparece y la huella no revela la clave', () {
      final a = seudonimizar('CC', '1065432', sal);
      expect(a, hasLength(64));
      expect(a, isNot(seudonimizar('CC', '1065432', '${sal}x')));
      expect(a.contains('1065432'), isFalse);
      expect(huellaSal(sal), matches(RegExp(r'^[0-9A-F]{4}-[0-9A-F]{4}$')));
      expect(huellaSal(sal), isNot(huellaSal('${sal}x')));
      expect(salValida('corta'), isFalse);
      expect(salValida(sal), isTrue);
      expect(() => seudonimizar('CC', ' .- ', sal), throwsArgumentError);
    });
  });

  group('carga del ejemplo ficticio de la IPS (paridad con Python)', () {
    test('CSV con «|» en Latin-1, como los planos de una IPS', () async {
      final carga = await cargar('ips_ficticio_3280.csv', ejemplo.readAsBytesSync());
      expect((carga.reporte.formato, carga.reporte.separador), (esperado['formato'], esperado['separador']));
      compararConPython(carga);
    });

    test('el mismo ejemplo en Excel da la misma carga', () async {
      final xlsx = File(ejemplo.path.replaceAll('.csv', '.xlsx'));
      final carga = await cargar('ips_ficticio_3280.xlsx', xlsx.readAsBytesSync());
      expect(carga.reporte.formato, 'xlsx');
      compararConPython(carga);
    });

    test('UTF-8 con coma y encabezados con tildes da lo mismo', () async {
      final latin = latin1.decode(ejemplo.readAsBytesSync());
      final tabla = leerArchivoIps('x.csv', bytes(latin));
      final conComa = [
        tabla.encabezado.map((e) => e == 'TAS' ? 'Presión Sistólica' : e).join(','),
        for (final f in tabla.filas) f.map((v) => v == null ? '' : (v.contains(',') ? '"$v"' : v)).join(','),
      ].join('\n');
      final carga = await cargar('ips.txt', bytes('\u{FEFF}$conComa'));
      expect((carga.reporte.formato, carga.reporte.separador), ('utf-8-sig', ','));
      compararConPython(carga);
    });
  });

  group('lector de archivos', () {
    test('comillas, líneas en blanco, espacios iniciales y vacíos de pandas', () {
      final t = leerArchivoIps('a.csv', bytes('Edad;Notas;TAS\n 27;"uno; ""dos""";120\n\n   \n30;NA;\r\n;;\n'));
      expect(t.separador, ';');
      expect(t.encabezado, ['Edad', 'Notas', 'TAS']);
      expect(t.filas, [
        ['27', 'uno; "dos"', '120'],
        ['30', null, null],
        [null, null, null],
      ]);
    });

    test('encabezados repetidos o vacíos como pandas', () {
      expect(leerArchivoIps('a.csv', bytes('TAS,TAS,\n1,2,3\n')).encabezado, ['TAS', 'TAS.1', 'Unnamed: 2']);
    });

    test('formatos no soportados y filas con columnas de más', () {
      expect(() => leerArchivoIps('a.xls', bytes('x')), throwsA(isA<ArchivoIpsInvalido>()));
      expect(() => leerArchivoIps('a.csv', bytes('a,b\n1,2,3\n')), throwsA(isA<ArchivoIpsInvalido>()));
      expect(() => leerArchivoIps('a.csv', bytes('')), throwsA(isA<ArchivoIpsInvalido>()));
    });

    test('Excel guardado por Microsoft Excel: cadenas compartidas, fechas, fórmulas y errores, como openpyxl', () {
      // Lo esperado es lo que devuelve _lotes_excel de Python (openpyxl) con este mismo archivo
      final t = leerArchivoIps('excel.xlsx', _xlsxEstiloExcel());
      expect(t.formato, 'xlsx');
      expect(t.encabezado, ['Edad', 'FUM', 'TAS', 'Fetocardia', 'Cefalea', 'Glicemia', 'Zona', 'Hora']);
      expect(t.filas, [
        ['27', '2025-12-09', '120', '157.6', 'True', '#N/A', 'Rural disperso', '12:00:00'],
        ['31', '2025-12-08', null, '140', null, null, null, null],
      ]);
    });

    test('normaliza los nombres como Python', () {
      expect(normalizarNombre('  Visión  Borrosa '), 'vision_borrosa');
      expect(normalizarNombre('Presión Sistólica'), 'presion_sistolica');
      expect(normalizarNombre('Tensión-Arterial/Sistólica'), 'tension_arterial_sistolica');
      expect(normalizarNombre('AÑO'), 'ano');
    });
  });

  group('resultado de la carga', () {
    test('un archivo sin una columna obligatoria no evalúa a nadie y lo dice', () async {
      final carga = await cargar('a.csv', bytes('Edad,Semanas\n27,28\n'));
      expect(carga.resultados, isEmpty);
      expect(carga.reporte.aptas, 0);
      expect(carga.reporte.faltantes.keys, contains('pas_mmhg'));
      expect(carga.reporte.faltantes['pas_mmhg'], isNull); // columna ausente
      expect(carga.rechazadas.single.faltan, contains('pas_mmhg'));
    });

    test('CSV exportado: ordenado, sin nombres ni documentos y con las filas sin evaluar', () async {
      final carga = await cargar('ips_ficticio_3280.csv', ejemplo.readAsBytesSync());
      final csv = exportarCsv(carga, recursos);
      expect(csv.startsWith('\u{FEFF}fila,id_seudonimo,semaforo'), isTrue);
      final lineas = csv.trim().split('\r\n');
      expect(lineas, hasLength(1 + carga.resultados.length + carga.rechazadas.length));
      expect(lineas[1], contains(',Rojo,Alto Riesgo,'));
      expect(lineas.last, contains('Sin evaluar'));
      final original = latin1.decode(ejemplo.readAsBytesSync());
      expect(csv.contains('FICTICIO'), isFalse);
      final documentos = original.split('\n').skip(1).take(40).map((l) => l.split('|')[1]).where((d) => d.length > 5);
      expect(documentos.where(csv.contains), isEmpty);
    });

    test('avisa el avance y cede el control durante la evaluación', () async {
      final avances = <int>[];
      await procesarCarga(
          nombre: 'ips_ficticio_3280.csv',
          bytes: ejemplo.readAsBytesSync(),
          recursos: recursos,
          sal: sal,
          cadaCuantas: 100,
          alAvanzar: (hechas, total) => avances.add(hechas));
      expect(avances, [0, 100, 200, 300, 303]);
    });
  });
}

/// .xlsx mínimo como lo guarda Microsoft Excel: rutas relativas, cadenas compartidas (una con formato), una fecha con
/// formato predefinido y otra con formato propio, una fórmula con su valor calculado, un error y una hora.
Uint8List _xlsxEstiloExcel() {
  const ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"';
  const rels = 'xmlns="http://schemas.openxmlformats.org/package/2006/relationships"';
  final partes = {
    'xl/workbook.xml': '<workbook $ns xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Datos" sheetId="1" r:id="rId1"/></sheets></workbook>',
    'xl/_rels/workbook.xml.rels': '<Relationships $rels><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>',
    'xl/sharedStrings.xml': '<sst $ns><si><t>Edad</t></si><si><r><t>F</t></r><r><rPr><b/></rPr><t>UM</t></r></si>'
        '<si><t>TAS</t></si><si><t>Fetocardia</t></si><si><t>Cefalea</t></si><si><t>Glicemia</t></si><si><t>Zona</t></si>'
        '<si><t>Rural disperso</t></si><si><t>Hora</t></si></sst>',
    'xl/styles.xml': '<styleSheet $ns><numFmts count="1"><numFmt numFmtId="164" formatCode="dd/mm/yyyy;@"/></numFmts>'
        '<cellXfs count="4"><xf numFmtId="0"/><xf numFmtId="14"/><xf numFmtId="164"/><xf numFmtId="20"/></cellXfs></styleSheet>',
    'xl/worksheets/sheet1.xml': '<worksheet $ns><sheetData>'
        '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c><c r="C1" t="s"><v>2</v></c>'
        '<c r="D1" t="s"><v>3</v></c><c r="E1" t="s"><v>4</v></c><c r="F1" t="s"><v>5</v></c><c r="G1" t="s"><v>6</v></c>'
        '<c r="H1" t="s"><v>8</v></c></row>'
        '<row r="2"><c r="A2"><v>27</v></c><c r="B2" s="1"><v>46000</v></c><c r="C2"><f>100+20</f><v>120</v></c>'
        '<c r="D2"><v>157.6</v></c><c r="E2" t="b"><v>1</v></c><c r="F2" t="e"><v>#N/A</v></c><c r="G2" t="s"><v>7</v></c>'
        '<c r="H2" s="3"><v>0.5</v></c></row>'
        '<row r="4"><c r="A4"><v>31</v></c><c r="B4" s="2"><v>45999.75</v></c><c r="D4" t="str"><v>140</v></c></row>'
        '<row r="5"><c r="C5"/></row>'
        '</sheetData></worksheet>',
  };
  final zip = Archive();
  for (final MapEntry(:key, :value) in partes.entries) {
    final contenido = utf8.encode(value);
    zip.addFile(ArchiveFile(key, contenido.length, contenido));
  }
  return Uint8List.fromList(ZipEncoder().encode(zip)!);
}
