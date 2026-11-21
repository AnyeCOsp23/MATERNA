// Modo oscuro: se activa en «Acerca de», cambia toda la app sin cerrar la sesión, se guarda, y conserva la
// identidad (vino y rosa) con contraste suficiente. La animación del logo y la presentación siguen en claro.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:materna/datos/base_local.dart';
import 'package:materna/datos/preferencias.dart';
import 'package:materna/main.dart';
import 'package:materna/ui/pantallas/pantalla_inicio.dart';
import 'package:materna/ui/tema/tema_materna.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

import 'acceso_test.dart' show esperar, registrar;
import 'flujo_test.dart' show recursos, tocar;

Future<(BaseLocal, Preferencias)> arrancar(WidgetTester tester, Preferencias preferencias) async {
  tester.view.physicalSize = const Size(600, 1500);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  addTearDown(() => ColoresMaterna.usar(oscuro: false)); // la paleta es global: no contagiar a otras pruebas
  final base = (await tester.runAsync(() => BaseLocal.abrir(databaseFactoryFfiNoIsolate, inMemoryDatabasePath)))!;
  addTearDown(() => tester.runAsync(base.cerrar));
  await tester.pumpWidget(MaternaApp(inicio: Future.value((recursos, base)), preferencias: Future.value(preferencias)));
  return (base, preferencias);
}

Brightness brillo(WidgetTester tester, Finder f) => Theme.of(tester.element(f)).brightness;
Color? colorTexto(WidgetTester tester, String texto) => tester.widget<Text>(find.text(texto).first).style?.color;

double contraste(Color a, Color b) {
  final (la, lb) = (a.computeLuminance(), b.computeLuminance());
  return (la > lb ? la + .05 : lb + .05) / (la > lb ? lb + .05 : la + .05);
}

void main() {
  testWidgets('el interruptor cambia toda la app a oscuro sin cerrar la sesión, y se guarda', (tester) async {
    final (_, preferencias) = await arrancar(tester, Preferencias.enMemoria());
    await tester.pumpAndSettle();
    await registrar(tester);
    await tester.tap(find.byKey(const Key('codigo-anotado')));
    await esperar(tester);
    await tocar(tester, find.byKey(const Key('pestana-4')));
    expect(brillo(tester, find.byKey(const Key('deslinde'))), Brightness.light);
    expect(colorTexto(tester, 'Qué le permite hacer MATERNA'), Paleta.claro.tinta);

    await tocar(tester, find.byKey(const Key('ajuste-modo-oscuro')));
    expect(preferencias.modoOscuro, isTrue);
    expect(ColoresMaterna.oscuro, isTrue);
    // la misma pantalla, con la sesión abierta, ya redibujada con la paleta oscura
    expect(find.byKey(const Key('ajuste-modo-oscuro')), findsOneWidget);
    expect(brillo(tester, find.byKey(const Key('ajuste-modo-oscuro'))), Brightness.dark);
    expect(colorTexto(tester, 'Colores oscuros, más cómodos de noche'), Paleta.oscura.tintaSuave);
    expect(tester.takeException(), isNull);

    // las demás pestañas también se dibujan en oscuro, sin errores
    for (final pestana in [0, 1, 2]) {
      await tocar(tester, find.byKey(Key('pestana-$pestana')));
      expect(tester.takeException(), isNull);
    }
    expect(colorTexto(tester, 'Historial local'), Paleta.oscura.tinta);

    // y se vuelve al claro
    await tocar(tester, find.byKey(const Key('pestana-4')));
    await tocar(tester, find.byKey(const Key('ajuste-modo-oscuro')));
    expect(preferencias.modoOscuro, isFalse);
    expect(colorTexto(tester, 'Colores oscuros, más cómodos de noche'), Paleta.claro.tintaSuave);
    await tocar(tester, find.byKey(const Key('cerrar-sesion'))); // la sesión seguía abierta
    expect(find.byKey(const Key('entrar')), findsOneWidget);
  });

  testWidgets('guardado en oscuro: la app arranca oscura, pero el logo y la presentación siguen claros', (tester) async {
    await arrancar(tester, Preferencias.enMemoria(presentacionVista: false, valores: {ClavesPreferencias.modoOscuro: true}));
    await tester.pump();
    expect(brillo(tester, find.byType(PantallaInicio)), Brightness.light);
    await tester.pump(duracionInicio + const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 500));
    expect(ColoresMaterna.oscuro, isTrue);
    expect(brillo(tester, find.byKey(const Key('presentacion'))), Brightness.light);

    await tester.tap(find.byKey(const Key('omitir')));
    for (var t = 0; t < 1500; t += 50) {
      await tester.pump(const Duration(milliseconds: 50));
    }
    await tester.tap(find.byKey(const Key('presentacion-siguiente')));
    await tester.pumpAndSettle();
    expect(brillo(tester, find.byKey(const Key('entrar'))), Brightness.dark);
    expect(tester.takeException(), isNull);
  });

  test('en los dos modos, textos y fondos con contraste de lectura (WCAG AA, 4,5:1)', () {
    for (final p in [Paleta.claro, Paleta.oscura]) {
      final pares = {
        'texto en tarjeta': (p.tinta, p.tarjeta),
        'texto suave en tarjeta': (p.tintaSuave, p.tarjeta),
        'texto suave en el fondo': (p.tintaSuave, p.crema),
        'marca en tarjeta': (p.ciruela900, p.tarjeta),
        'marca en el fondo': (p.ciruela900, p.crema),
        'marca en la pestaña activa': (p.ciruela900, p.ciruela100),
        'botón (texto blanco en vino)': (Colors.white, p.vino),
      };
      ColoresMaterna.con(p, () {
        for (final e in estiloPorCategoria.values) {
          pares['aviso ${e.corto}'] = (e.tinta, e.fondo);
        }
      });
      for (final MapEntry(key: nombre, value: (a, b)) in pares.entries) {
        expect(contraste(a, b), greaterThanOrEqualTo(4.5), reason: '${p.oscuro ? 'oscuro' : 'claro'}: $nombre');
      }
    }
  });
}
