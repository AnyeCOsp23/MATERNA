import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:materna/datos/base_local.dart';
import 'package:materna/main.dart';
import 'package:materna/motor/recursos.dart';

void main() {
  testWidgets('la app abre y espera el modelo', (tester) async {
    await tester.pumpWidget(MaternaApp(inicio: Completer<(RecursosMaterna, BaseLocal)>().future));
    expect(find.text('MATERNA'), findsOneWidget);
    expect(find.text('Cargando el modelo…'), findsOneWidget);
  });
}
