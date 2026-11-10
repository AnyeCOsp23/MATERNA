// Pestaña «Carga IPS» como la usaría el personal de salud: configurar la clave de la IPS, cargar el archivo de
// ejemplo, revisar el triaje ordenado, exportarlo y encontrar a una gestante en el historial por su documento.
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:materna/datos/seudonimizacion.dart';

import 'flujo_test.dart' show abrir, base, tocar;

final casos = jsonDecode(File('assets/casos_carga.json').readAsStringSync()) as Map<String, dynamic>;

/// La sal de prueba de Python: así los seudónimos de la app se comparan con los de casos_carga.json.
final clave = casos['sal_prueba'] as String;
final ejemplo = File('../data/ejemplos/ips_ficticio_3280.csv');

Future<(String, Uint8List)?> elegirEjemplo() async => ('ips_ficticio_3280.csv', ejemplo.readAsBytesSync());

/// Espera a que termine algo asíncrono de la pantalla (la evaluación cede el control cada 100 filas).
Future<void> esperar(WidgetTester tester, Finder f) async {
  for (var i = 0; i < 100 && f.evaluate().isEmpty; i++) {
    await tester.pump(const Duration(milliseconds: 50));
  }
  await tester.pumpAndSettle();
  expect(f, findsWidgets);
}

Future<void> configurarClave(WidgetTester tester, {String? repetida}) async {
  await tester.enterText(find.byKey(const Key('campo-clave')), clave);
  await tester.enterText(find.byKey(const Key('campo-clave-repetir')), repetida ?? clave);
  await tocar(tester, find.byKey(const Key('guardar-clave')));
}

/// Vuelve al inicio de la pestaña: la lista solo construye lo que está cerca de la pantalla.
Future<void> subir(WidgetTester tester) async {
  await tester.fling(find.byType(CustomScrollView), const Offset(0, 4000), 8000);
  await tester.pumpAndSettle();
}

/// Elige el archivo y espera a que termine la evaluación (el botón vuelve a decir «Cargar otro archivo»).
Future<void> cargarEjemplo(WidgetTester tester) async {
  await subir(tester);
  await tocar(tester, find.byKey(const Key('elegir-archivo')));
  await esperar(tester, find.text('Cargar otro archivo'));
  await tester.dragUntilVisible(find.byKey(const Key('resumen-carga')), find.byType(CustomScrollView), const Offset(0, -200));
  await tester.pumpAndSettle();
}

String conteo(WidgetTester tester, int clase) => tester
    .widget<Text>(find.descendant(of: find.byKey(Key('conteo-$clase')), matching: find.byType(Text)).at(0))
    .data!;

void main() {
  testWidgets('sin la clave de la IPS no se puede cargar; la clave se valida y queda su huella', (tester) async {
    await abrir(tester, elegirArchivo: elegirEjemplo);
    await tocar(tester, find.byKey(const Key('pestana-1')));
    expect(find.text('Carga masiva IPS'), findsOneWidget);
    expect(tester.widget<FilledButton>(find.byKey(const Key('elegir-archivo'))).onPressed, isNull);
    await tester.enterText(find.byKey(const Key('campo-clave')), 'corta');
    await tester.enterText(find.byKey(const Key('campo-clave-repetir')), 'corta');
    await tocar(tester, find.byKey(const Key('guardar-clave')));
    expect(find.textContaining('al menos 16 caracteres'), findsOneWidget);
    await configurarClave(tester, repetida: '${clave}x');
    expect(find.text('Las dos claves no coinciden.'), findsOneWidget);
    await configurarClave(tester);
    expect(find.byKey(const Key('clave-configurada')), findsOneWidget);
    expect(find.textContaining(huellaSal(clave)), findsWidgets);
    expect(await tester.runAsync(base.claveIps), clave);
    expect(tester.widget<FilledButton>(find.byKey(const Key('elegir-archivo'))).onPressed, isNotNull);
  });

  testWidgets('carga el ejemplo: triaje ordenado, detalle, CSV sin documentos y búsqueda por documento', (tester) async {
    String? exportado;
    await abrir(tester, elegirArchivo: elegirEjemplo, guardarArchivo: (nombre, bytes) async {
      exportado = utf8.decode(bytes);
      return true;
    });
    await tocar(tester, find.byKey(const Key('pestana-1')));
    await configurarClave(tester);
    await cargarEjemplo(tester);

    final resultados = (casos['resultados'] as List).cast<Map<String, dynamic>>();
    for (final clase in [0, 1, 2]) {
      expect(conteo(tester, clase), '${resultados.where((r) => r['clase'] == clase).length}');
    }
    expect(find.text('303 registros (307 filas leídas, 4 repetidas) · 300 evaluadas · 3 sin evaluar'), findsOneWidget);
    expect(find.byKey(const Key('carga-guardada')), findsOneWidget);

    // la primera fila de la lista es la más urgente (la misma que en Python)
    final primera = find.byKey(Key('fila-${resultados.first['fila']}'));
    expect(primera, findsOneWidget);
    expect(find.descendant(of: primera, matching: find.textContaining('ROJO')), findsOneWidget);

    await tocar(tester, find.byKey(const Key('filas-sin-evaluar')));
    expect(find.textContaining('Fila 122: falta edad'), findsOneWidget);

    await tocar(tester, find.descendant(of: find.byKey(const Key('filtro-carga')), matching: find.textContaining('Verde')));
    expect(find.descendant(of: find.byType(ListTile), matching: find.textContaining('ROJO')), findsNothing);
    await tocar(tester, find.descendant(of: find.byKey(const Key('filtro-carga')), matching: find.textContaining('Todas')));

    await tocar(tester, primera);
    expect(find.text('Evaluación guardada'), findsOneWidget);
    expect(find.textContaining('Fila ${resultados.first['fila']} de ips_ficticio_3280.csv'), findsOneWidget);
    await tester.pageBack();
    await tester.pumpAndSettle();
    await subir(tester);

    await tocar(tester, find.byKey(const Key('exportar-csv')));
    expect(exportado, isNotNull);
    expect(exportado!.split('\r\n')[1], startsWith('${resultados.first['fila']},'));
    expect(exportado!.contains('FICTICIO'), isFalse);
    expect(find.textContaining('Triaje exportado'), findsOneWidget);

    // historial: las 300 evaluaciones, y la gestante de la primera fila se encuentra por su documento
    final lineas = latin1.decode(ejemplo.readAsBytesSync()).split(RegExp(r'\r?\n'));
    final campos = lineas[(resultados.first['fila'] as int) - 1].split('|');
    expect(exportado!.contains(campos[1]), isFalse); // el documento no sale en el CSV
    await tocar(tester, find.byKey(const Key('pestana-2')));
    expect(find.text('300 evaluación(es)'), findsOneWidget);
    await tocar(tester, find.byKey(const Key('buscar-por-documento')));
    await tester.enterText(find.byKey(const Key('buscar-seudonimo')), '${campos[0].toLowerCase()} ${campos[1]}');
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pumpAndSettle();
    final buscado = seudonimizar(campos[0], campos[1], clave);
    expect(buscado, resultados.first['id_seudonimo']); // el mismo seudónimo que calcula Python
    final mismas = resultados.where((r) => r['id_seudonimo'] == buscado).length;
    expect(mismas, greaterThan(0));
    expect(find.text('$mismas evaluación(es)'), findsOneWidget);
    expect(find.textContaining('carga IPS'), findsWidgets);
  });

  testWidgets('el mismo archivo otra vez no duplica el historial, salvo que se pida', (tester) async {
    await abrir(tester, elegirArchivo: elegirEjemplo);
    await tocar(tester, find.byKey(const Key('pestana-1')));
    await configurarClave(tester);
    await cargarEjemplo(tester);
    await cargarEjemplo(tester);
    expect(find.byKey(const Key('carga-previa')), findsOneWidget);
    expect((await tester.runAsync(base.listar))!, hasLength(300));
    await tocar(tester, find.byKey(const Key('guardar-otra-vez')));
    expect(find.byKey(const Key('carga-guardada')), findsOneWidget);
    expect((await tester.runAsync(() => base.listar(limite: 1000)))!, hasLength(600));
  });

  testWidgets('un archivo que no es de la plantilla muestra el motivo sin romper la app', (tester) async {
    await abrir(tester, elegirArchivo: () async => ('viejo.xls', Uint8List.fromList([1, 2, 3])));
    await tocar(tester, find.byKey(const Key('pestana-1')));
    await configurarClave(tester);
    await tocar(tester, find.byKey(const Key('elegir-archivo')));
    await esperar(tester, find.byKey(const Key('error-carga')));
    expect(find.textContaining('guarde el archivo como .xlsx o .csv'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('en el celular la carga cabe en pantalla', (tester) async {
    await abrir(tester, tamano: const Size(390, 844), elegirArchivo: elegirEjemplo);
    await tocar(tester, find.byKey(const Key('pestana-1')));
    await configurarClave(tester);
    await cargarEjemplo(tester);
    expect(tester.takeException(), isNull);
  });
}
