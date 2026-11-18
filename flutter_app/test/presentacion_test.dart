// Presentación inicial (onboarding): solo la primera vez, entre la animación del logo y el acceso. Lo elegido se
// guarda en las preferencias, queda propuesto al crear la cuenta y los ajustes se aplican a toda la app.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:materna/datos/base_local.dart';
import 'package:materna/datos/preferencias.dart';
import 'package:materna/main.dart';
import 'package:materna/ui/pantallas/pantalla_inicio.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

import 'acceso_test.dart' show escribir, esperar;
import 'flujo_test.dart' show recursos;

/// Abre la app con preferencias en memoria y deja pasar la animación del logo (la presentación tiene animaciones que
/// se repiten: aquí no se usa pumpAndSettle mientras está en pantalla).
Future<(BaseLocal, Preferencias)> arrancar(WidgetTester tester, {bool vista = false, bool reducirMovimiento = false}) async {
  tester.view.physicalSize = const Size(600, 1500);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final base = (await tester.runAsync(() => BaseLocal.abrir(databaseFactoryFfiNoIsolate, inMemoryDatabasePath)))!;
  addTearDown(() => tester.runAsync(base.cerrar));
  final preferencias = Preferencias.enMemoria(presentacionVista: vista);
  await tester.pumpWidget(MediaQuery(
    data: MediaQueryData(disableAnimations: reducirMovimiento, size: const Size(600, 1500)),
    child: MaternaApp(inicio: Future.value((recursos, base)), preferencias: Future.value(preferencias)),
  ));
  await tester.pump();
  await tester.pump(duracionInicio + const Duration(milliseconds: 100));
  await tester.pump(const Duration(milliseconds: 500)); // transición a la siguiente pantalla
  return (base, preferencias);
}

Future<void> tocar(WidgetTester tester, Finder f) async {
  await tester.ensureVisible(f);
  await tester.pump();
  await tester.tap(f);
  await avanzar(tester, 900); // rebote y cambio de página
}

/// Avanza el tiempo cuadro a cuadro (no de un salto): así terminan también las animaciones que empiezan en medio.
Future<void> avanzar(WidgetTester tester, int ms) async {
  for (var t = 0; t < ms; t += 50) {
    await tester.pump(const Duration(milliseconds: 50));
  }
}

Future<void> siguiente(WidgetTester tester) => tocar(tester, find.byKey(const Key('presentacion-siguiente')));

String textoBoton(WidgetTester tester) =>
    tester.widget<Text>(find.descendant(of: find.byKey(const Key('presentacion-siguiente')), matching: find.byType(Text))).data!;

/// Página visible según los puntos (el actual mide 28 de ancho).
int pagina(WidgetTester tester) =>
    [for (var k = 0; k < 4; k++) tester.getSize(find.byKey(Key('punto-$k'))).width].indexWhere((a) => a > 20);

void main() {
  testWidgets('la primera vez: 4 pantallas, sin rol no se avanza, y lo elegido queda guardado', (tester) async {
    final (_, preferencias) = await arrancar(tester);
    expect(find.byKey(const Key('presentacion')), findsOneWidget);
    expect(find.text('Cuidar a tiempo\nsalva vidas'), findsOneWidget);
    expect(textoBoton(tester), 'Comenzar');

    await siguiente(tester);
    expect(pagina(tester), 1);
    expect(find.text('¿Quién usará MATERNA?'), findsOneWidget);
    // las 4 categorías del modelo, no otras
    for (final rol in ['Medico', 'Enfermero(a)', 'Auxiliar de enfermeria', 'Partera tradicional']) {
      expect(find.byKey(Key('rol-$rol')), findsOneWidget);
    }
    // sin elegir quién atiende, el botón no avanza
    await siguiente(tester);
    expect(pagina(tester), 1);
    expect(find.text('Elija quién atiende para continuar'), findsOneWidget);

    await tocar(tester, find.byKey(const Key('rol-Partera tradicional')));
    expect(find.text('Elija quién atiende para continuar'), findsNothing);
    await siguiente(tester);
    expect(pagina(tester), 2);
    expect(textoBoton(tester), 'Continuar');

    await tocar(tester, find.byKey(const Key('avatar-4')));
    await siguiente(tester);
    expect(pagina(tester), 3);
    expect(textoBoton(tester), 'Empezar a usar MATERNA');
    expect(find.byKey(const Key('omitir')).hitTestable(), findsNothing); // en la última no se puede omitir

    await tocar(tester, find.byKey(const Key('ajuste-letra')));
    await tocar(tester, find.byKey(const Key('ajuste-vibrar'))); // venía marcado: queda desmarcado
    await siguiente(tester);
    await tester.pumpAndSettle();

    expect(preferencias.presentacionVista, isTrue);
    expect((preferencias.rol, preferencias.avatar, preferencias.letraGrande, preferencias.reducirAnimaciones, preferencias.vibrarAlto),
        ('Partera tradicional', 4, true, false, false));
    // pasa al acceso, con la letra un 15 % más grande en toda la app
    expect(find.byKey(const Key('presentacion')), findsNothing);
    expect(find.byKey(const Key('entrar')), findsOneWidget);
    expect(MediaQuery.of(tester.element(find.byKey(const Key('entrar')))).textScaler.scale(10), closeTo(11.5, .001));
  });

  testWidgets('lo elegido queda propuesto al crear la cuenta, y el avatar se ve en el encabezado', (tester) async {
    final (base, preferencias) = await arrancar(tester);
    await siguiente(tester);
    await tocar(tester, find.byKey(const Key('rol-Enfermero(a)')));
    await siguiente(tester);
    await tocar(tester, find.byKey(const Key('avatar-3')));
    await siguiente(tester);
    await siguiente(tester);
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('ir-registro')));
    await tester.pumpAndSettle();
    await escribir(tester, 'usuario', 'enfermera.manaure');
    await escribir(tester, 'ips', 'ESE Manaure');
    await escribir(tester, 'pin', '1357');
    await escribir(tester, 'pin2', '1357');
    await tester.ensureVisible(find.byKey(const Key('crear-acceso')));
    await tester.tap(find.byKey(const Key('crear-acceso')));
    await esperar(tester);

    final perfil = (await tester.runAsync(() => base.perfilDe('enfermera.manaure')))!;
    expect((perfil.atendidoPor, perfil.avatar), ('Enfermero(a)', 3)); // sin tocar «Quién atiende» ni el avatar
    expect(preferencias.presentacionVista, isTrue);

    await tester.tap(find.byKey(const Key('codigo-anotado')));
    await esperar(tester);
    expect(find.byKey(const Key('avatar-sesion')), findsWidgets); // en el encabezado de la pantalla principal
  });

  testWidgets('«Omitir» lleva a los ajustes sin elegir rol; se puede terminar igual', (tester) async {
    final (_, preferencias) = await arrancar(tester);
    await tocar(tester, find.byKey(const Key('omitir')));
    await avanzar(tester, 600);
    expect(pagina(tester), 3);
    await siguiente(tester);
    await tester.pumpAndSettle();
    expect(preferencias.presentacionVista, isTrue);
    expect(preferencias.rol, isNull); // «Quién atiende» se elige al crear la cuenta
    expect(find.byKey(const Key('entrar')), findsOneWidget);
  });

  testWidgets('si ya se vio, la app va directo al acceso', (tester) async {
    await arrancar(tester, vista: true);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('presentacion')), findsNothing);
    expect(find.byKey(const Key('entrar')), findsOneWidget);
  });

  testWidgets('con «reducir movimiento» no hay animaciones que se repitan', (tester) async {
    await arrancar(tester, reducirMovimiento: true);
    expect(find.byKey(const Key('presentacion')), findsOneWidget);
    expect(find.byIcon(Icons.favorite_rounded), findsNothing); // sin corazoncitos
    await tester.pumpAndSettle(); // nada se queda animando
    await siguiente(tester);
    await tester.pumpAndSettle();
    expect(pagina(tester), 1);
  });

  testWidgets('cabe en un celular pequeño sin desbordarse', (tester) async {
    final (_, _) = await arrancar(tester);
    tester.view.physicalSize = const Size(320, 568);
    await tester.pump(const Duration(milliseconds: 300));
    for (var k = 0; k < 3; k++) {
      if (k == 1) await tocar(tester, find.byKey(const Key('rol-Medico')));
      await siguiente(tester);
      expect(tester.takeException(), isNull);
    }
  });
}
