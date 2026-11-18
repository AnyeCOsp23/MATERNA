// Botón ⓘ con pulso: llama la atención, se detiene al tocarlo o tras unos pulsos, y respeta «reducir animaciones».
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:materna/ui/widgets/boton_info.dart';

Future<int> montar(WidgetTester tester, {bool quieto = false}) async {
  var toques = 0;
  await tester.pumpWidget(MaterialApp(
    home: MediaQuery(
      data: MediaQueryData(disableAnimations: quieto),
      child: Scaffold(body: Center(child: BotonInfoPulso(alTocar: () => toques++))),
    ),
  ));
  return toques;
}

Finder get pulso => find.descendant(of: find.byType(BotonInfoPulso), matching: find.byType(AnimatedBuilder));

void main() {
  testWidgets('pulsa, y deja de pulsar al tocarlo', (tester) async {
    var toques = 0;
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(body: Center(child: BotonInfoPulso(alTocar: () => toques++))),
    ));
    expect(pulso, findsOneWidget);
    await tester.pump(const Duration(milliseconds: 500));
    expect(tester.hasRunningAnimations, isTrue);
    await tester.tap(find.byKey(const Key('boton-info')));
    await tester.pump();
    expect(toques, 1);
    expect(pulso, findsNothing);
    // queda solo la onda del toque de Material, que termina sola (el pulso ya no vuelve)
    await tester.pump(const Duration(seconds: 1));
    expect(tester.hasRunningAnimations, isFalse);
  });

  testWidgets('se detiene solo tras unos pulsos (no distrae para siempre)', (tester) async {
    await montar(tester);
    await tester.pumpAndSettle(); // terminaría por tiempo de espera si el pulso fuera infinito
    expect(tester.hasRunningAnimations, isFalse);
  });

  testWidgets('con «reducir animaciones» queda quieto', (tester) async {
    await montar(tester, quieto: true);
    expect(pulso, findsNothing);
    expect(tester.hasRunningAnimations, isFalse);
  });
}
