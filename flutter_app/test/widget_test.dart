import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:materna/datos/base_local.dart';
import 'package:materna/main.dart';
import 'package:materna/motor/recursos.dart';
import 'package:materna/ui/pantallas/pantalla_inicio.dart';

void main() {
  testWidgets('si el modelo tarda, la pantalla de inicio sigue en pantalla sin pantallas intermedias', (tester) async {
    await tester.pumpWidget(MaternaApp(inicio: Completer<(RecursosMaterna, BaseLocal)>().future));
    expect(find.byKey(const Key('pantalla-inicio')), findsOneWidget);
    expect(find.byKey(const Key('inicio-texto')), findsOneWidget); // la palabra MATERNA, que se escribe letra por letra
    await tester.pump(duracionInicio * 3);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('pantalla-inicio')), findsOneWidget);
    expect(tester.widget<Opacity>(find.byKey(const Key('inicio-logo'))).opacity, 1);
    expect(find.textContaining('Cargando'), findsNothing);
  });

  testWidgets('si la carga falla, lo dice después de la pantalla de inicio', (tester) async {
    final carga = Completer<(RecursosMaterna, BaseLocal)>();
    await tester.pumpWidget(MaternaApp(inicio: carga.future));
    carga.completeError(StateError('sin modelo'));
    await tester.pump(duracionInicio);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('pantalla-inicio')), findsNothing);
    expect(find.textContaining('No se pudo iniciar MATERNA'), findsOneWidget);
  });
}
