// Acceso por PIN desde el arranque de la app: primera configuración, PIN, bloqueo, olvido y cierre de sesión.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:materna/datos/base_local.dart';
import 'package:materna/datos/seguridad.dart';
import 'package:materna/main.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

import 'flujo_test.dart' show elegirEnLista, recursos, tocar;

Future<BaseLocal> arrancar(WidgetTester tester) async {
  tester.view.physicalSize = const Size(600, 1300);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final base = (await tester.runAsync(() => BaseLocal.abrir(databaseFactoryFfiNoIsolate, inMemoryDatabasePath)))!;
  addTearDown(() => tester.runAsync(base.cerrar));
  await tester.pumpWidget(MaternaApp(inicio: Future.value((recursos, base))));
  await tester.pumpAndSettle();
  return base;
}

Future<void> escribirPin(WidgetTester tester, String pin) async {
  for (final d in pin.split('')) {
    await tester.tap(find.byKey(Key('tecla-$d')));
    await tester.pump();
  }
  await tester.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 50))); // PBKDF2 y SQLite
  await tester.pumpAndSettle();
}

Future<void> configurar(WidgetTester tester) async {
  await elegirEnLista(tester, 'atendido_por', 'Auxiliar de enfermería');
  await tester.enterText(find.byKey(const Key('campo-ips')), 'ESE Hospital de Uribia');
  await tester.enterText(find.byKey(const Key('campo-pin')), '2580');
  await tester.enterText(find.byKey(const Key('campo-pin2')), '2580');
  await tocar(tester, find.byKey(const Key('crear-acceso')));
  // PBKDF2 y SQLite corren de verdad: se les da tiempo real y luego se dibuja (dos rondas: guardar y leer el perfil)
  for (var i = 0; i < 2; i++) {
    await tester.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 80)));
    await tester.pumpAndSettle();
  }
}

void main() {
  testWidgets('primera vez: perfil y PIN; luego se entra con el PIN', (tester) async {
    await arrancar(tester);
    expect(find.byKey(const Key('crear-acceso')), findsOneWidget);
    await tocar(tester, find.byKey(const Key('crear-acceso')));
    expect(find.text('Elija una opción.'), findsOneWidget);
    expect(find.text('El PIN debe tener 4 dígitos.'), findsOneWidget);
    await configurar(tester);
    expect(find.textContaining('Auxiliar de enfermería · ESE Hospital de Uribia'), findsOneWidget);
    await escribirPin(tester, '2580');
    expect(find.byKey(const Key('paso-actual')), findsOneWidget, reason: 'abrió el triaje');
  });

  testWidgets('PIN incorrecto y bloqueo tras 5 intentos', (tester) async {
    await arrancar(tester);
    await configurar(tester);
    await escribirPin(tester, '1111');
    expect(find.text('PIN incorrecto.'), findsOneWidget);
    for (var i = 1; i < intentosMaximos; i++) {
      await escribirPin(tester, '1111');
    }
    expect(find.textContaining('Demasiados intentos'), findsOneWidget);
    await escribirPin(tester, '2580');
    expect(find.byKey(const Key('paso-actual')), findsNothing, reason: 'bloqueado aunque el PIN sea correcto');
  });

  testWidgets('«¿Olvidó el PIN?» borra el dispositivo y vuelve a la configuración', (tester) async {
    final base = await arrancar(tester);
    await configurar(tester);
    await tocar(tester, find.byKey(const Key('olvide-pin')));
    await tocar(tester, find.byKey(const Key('confirmar-reinicio')));
    await tester.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 50)));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('crear-acceso')), findsOneWidget);
    expect(await tester.runAsync(base.tienePin), isFalse);
  });

  testWidgets('quién atiende viene del perfil y «Cerrar sesión» vuelve a pedir el PIN', (tester) async {
    await arrancar(tester);
    await configurar(tester);
    await escribirPin(tester, '2580');
    await tocar(tester, find.byKey(const Key('pestana-3')));
    expect(find.text('ESE Hospital de Uribia'), findsOneWidget);
    await tocar(tester, find.byKey(const Key('cerrar-sesion')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('tecla-1')), findsOneWidget);
  });
}
