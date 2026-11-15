// Acceso desde el arranque de la app: iniciar sesión, registrarse, código de recuperación, bloqueo, cerrar sesión
// para que entre otra persona y los tres niveles para recuperar un PIN olvidado.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:materna/datos/base_local.dart';
import 'package:materna/datos/seguridad.dart';
import 'package:materna/main.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

import 'flujo_test.dart' show elegirEnLista, recursos, tocar;

Future<BaseLocal> arrancar(WidgetTester tester) async {
  tester.view.physicalSize = const Size(600, 1500);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final base = (await tester.runAsync(() => BaseLocal.abrir(databaseFactoryFfiNoIsolate, inMemoryDatabasePath)))!;
  addTearDown(() => tester.runAsync(base.cerrar));
  await tester.pumpWidget(MaternaApp(inicio: Future.value((recursos, base))));
  await tester.pumpAndSettle();
  return base;
}

/// PBKDF2 y SQLite corren de verdad: se les da tiempo real y luego se dibuja.
Future<void> esperar(WidgetTester tester) async {
  for (var i = 0; i < 3; i++) {
    await tester.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 60)));
    await tester.pumpAndSettle();
  }
}

Future<void> escribir(WidgetTester tester, String campo, String valor) =>
    tester.enterText(find.byKey(Key('campo-$campo')), valor);

/// Registra una cuenta desde el inicio de sesión y devuelve el código de recuperación que muestra la app.
Future<String> registrar(WidgetTester tester, {String usuario = 'auxiliar.rural', String pin = '2580'}) async {
  await tocar(tester, find.byKey(const Key('ir-registro')));
  await escribir(tester, 'usuario', usuario);
  await elegirEnLista(tester, 'atendido_por', 'Auxiliar de enfermería');
  await escribir(tester, 'ips', 'ESE Hospital de Uribia');
  await escribir(tester, 'pin', pin);
  await escribir(tester, 'pin2', pin);
  await tocar(tester, find.byKey(const Key('crear-acceso')));
  await esperar(tester);
  return tester.widget<SelectableText>(find.byKey(const Key('codigo-recuperacion'))).data!;
}

Future<void> entrar(WidgetTester tester, String usuario, String pin) async {
  await escribir(tester, 'usuario', usuario);
  await escribir(tester, 'pin', pin);
  await tocar(tester, find.byKey(const Key('entrar')));
  await esperar(tester);
}

Future<void> cerrarSesion(WidgetTester tester) async {
  await tocar(tester, find.byKey(const Key('pestana-3')));
  await tocar(tester, find.byKey(const Key('cerrar-sesion')));
  await tester.pumpAndSettle();
}

String texto(WidgetTester tester, Key clave) => tester.widget<TextField>(find.byKey(clave)).controller!.text;

void main() {
  testWidgets('primera vez: inicio de sesión, registro con código de recuperación y entrada directa', (tester) async {
    await arrancar(tester);
    expect(find.text('Iniciar sesión'), findsWidgets);
    expect(find.byKey(const Key('sin-conexion')), findsOneWidget);
    await tocar(tester, find.byKey(const Key('ir-registro')));
    await tocar(tester, find.byKey(const Key('crear-acceso')));
    await esperar(tester);
    expect(find.textContaining('letras minúsculas'), findsOneWidget);
    expect(find.text('Elija una opción.'), findsOneWidget);
    expect(find.text('El PIN debe tener 4 dígitos.'), findsOneWidget);
    await tocar(tester, find.byKey(const Key('ir-entrar')));

    final codigo = await registrar(tester);
    expect(codigo, matches(RegExp(r'^[A-Z2-9]{4}-[A-Z2-9]{4}$')));
    await tocar(tester, find.byKey(const Key('codigo-anotado')));
    expect(find.byKey(const Key('paso-actual')), findsOneWidget, reason: 'abrió el triaje');
    await tocar(tester, find.byKey(const Key('pestana-3')));
    expect(find.text('auxiliar.rural'), findsOneWidget);
    expect(find.text('ESE Hospital de Uribia'), findsOneWidget);
  });

  testWidgets('usuario repetido, PIN incorrecto y bloqueo tras 5 intentos', (tester) async {
    await arrancar(tester);
    await registrar(tester);
    await tocar(tester, find.byKey(const Key('codigo-anotado')));
    await cerrarSesion(tester);
    await tocar(tester, find.byKey(const Key('ir-registro')));
    await escribir(tester, 'usuario', 'Auxiliar.Rural');
    await elegirEnLista(tester, 'atendido_por', 'Médico');
    await escribir(tester, 'ips', 'Otra IPS');
    await escribir(tester, 'pin', '1111');
    await escribir(tester, 'pin2', '1111');
    await tocar(tester, find.byKey(const Key('crear-acceso')));
    await esperar(tester);
    expect(find.text('Ese usuario ya existe en este dispositivo.'), findsOneWidget);
    await tocar(tester, find.byKey(const Key('ir-entrar')));

    await entrar(tester, 'auxiliar.rural', '1111');
    expect(find.text('Usuario o PIN incorrecto.'), findsOneWidget);
    for (var i = 1; i < intentosMaximos; i++) {
      await entrar(tester, 'auxiliar.rural', '1111');
    }
    expect(find.textContaining('Demasiados intentos'), findsOneWidget);
    await entrar(tester, 'auxiliar.rural', '2580');
    expect(find.byKey(const Key('paso-actual')), findsNothing, reason: 'bloqueada aunque el PIN sea correcto');
  });

  testWidgets('«Cerrar sesión» deja el acceso en blanco y otra persona entra con su cuenta; cada una ve lo suyo', (tester) async {
    await arrancar(tester);
    await registrar(tester);
    await tocar(tester, find.byKey(const Key('codigo-anotado')));
    await cerrarSesion(tester);
    expect(find.byKey(const Key('entrar')), findsOneWidget);
    expect(texto(tester, const Key('campo-usuario')), isEmpty);
    expect(texto(tester, const Key('campo-pin')), isEmpty);

    await registrar(tester, usuario: 'medico.uribia', pin: '1357');
    await tocar(tester, find.byKey(const Key('codigo-anotado')));
    await tocar(tester, find.byKey(const Key('pestana-3')));
    expect(find.text('medico.uribia'), findsOneWidget);
    await cerrarSesion(tester);
    await entrar(tester, 'auxiliar.rural', '2580');
    expect(find.byKey(const Key('paso-actual')), findsOneWidget);
  });

  testWidgets('PIN olvidado con el código de recuperación: PIN nuevo sin borrar nada', (tester) async {
    final base = await arrancar(tester);
    final codigo = await registrar(tester);
    await tocar(tester, find.byKey(const Key('codigo-anotado')));
    await cerrarSesion(tester);
    await escribir(tester, 'usuario', 'auxiliar.rural');
    await tocar(tester, find.byKey(const Key('olvide-pin')));
    expect(texto(tester, const Key('campo-usuario')), 'auxiliar.rural', reason: 'trae el usuario escrito');
    await escribir(tester, 'codigo', 'AAAA-AAAA');
    await escribir(tester, 'pin-nuevo', '9999');
    await escribir(tester, 'pin-nuevo2', '9999');
    await tocar(tester, find.byKey(const Key('restablecer')));
    await esperar(tester);
    expect(find.textContaining('Usuario o código incorrectos'), findsOneWidget);
    await escribir(tester, 'codigo', codigo.toLowerCase());
    await tocar(tester, find.byKey(const Key('restablecer')));
    await esperar(tester);
    final nuevo = tester.widget<SelectableText>(find.byKey(const Key('codigo-recuperacion'))).data!;
    expect(nuevo, isNot(codigo));
    await tocar(tester, find.byKey(const Key('codigo-anotado')));
    expect(find.textContaining('PIN cambiado'), findsOneWidget);
    await entrar(tester, 'auxiliar.rural', '9999');
    expect(find.byKey(const Key('paso-actual')), findsOneWidget);
    expect(await tester.runAsync(() => base.existeUsuario('auxiliar.rural')), isTrue);
  });

  testWidgets('sin código: el responsable pone el PIN con la clave de la IPS; si no, se elimina solo esa cuenta', (tester) async {
    final base = await arrancar(tester);
    await registrar(tester);
    await tocar(tester, find.byKey(const Key('codigo-anotado')));
    await cerrarSesion(tester);
    await tester.runAsync(() => base.fijarClaveIps('clave-de-prueba-de-la-ips-2026'));
    await tocar(tester, find.byKey(const Key('olvide-pin')));
    await tocar(tester, find.text('Clave de la IPS'));
    await escribir(tester, 'usuario', 'auxiliar.rural');
    await escribir(tester, 'clave-ips', 'clave-de-prueba-de-la-ips-2026');
    await escribir(tester, 'pin-nuevo', '4444');
    await escribir(tester, 'pin-nuevo2', '4444');
    await tocar(tester, find.byKey(const Key('restablecer')));
    await esperar(tester);
    expect(find.byKey(const Key('codigo-recuperacion')), findsOneWidget);
    await tocar(tester, find.byKey(const Key('codigo-anotado')));

    await tocar(tester, find.byKey(const Key('olvide-pin')));
    await escribir(tester, 'usuario', 'auxiliar.rural');
    await tocar(tester, find.byKey(const Key('eliminar-cuenta')));
    await esperar(tester);
    await tocar(tester, find.byKey(const Key('confirmar-eliminar')));
    await esperar(tester);
    expect(find.textContaining('Se eliminó la cuenta «auxiliar.rural»'), findsOneWidget);
    expect(await tester.runAsync(() => base.existeUsuario('auxiliar.rural')), isFalse);
  });
}
