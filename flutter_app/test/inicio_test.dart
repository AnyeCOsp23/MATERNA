// Pantalla de inicio (splash): el logo sube con fundido y rebote; la palabra MATERNA aparece desde los 0,9 s.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:materna/ui/pantallas/pantalla_inicio.dart';

double opacidad(WidgetTester tester, String clave) => tester.widget<Opacity>(find.byKey(Key(clave))).opacity;

/// Desplazamiento vertical y escala del logo en este instante.
(double, double) logo(WidgetTester tester) {
  final transformaciones = find.descendant(of: find.byKey(const Key('inicio-logo')), matching: find.byType(Transform));
  final mover = tester.widget<Transform>(transformaciones.at(0)).transform;
  final escalar = tester.widget<Transform>(transformaciones.at(1)).transform;
  return (mover.getTranslation().y, escalar.entry(0, 0));
}

/// Abre la pantalla y dibuja el primer cuadro de la animación (empieza después del primer cuadro de la pantalla).
Future<void> abrir(WidgetTester tester, {bool reducirMovimiento = false, VoidCallback? alTerminar}) async {
  await tester.pumpWidget(MaterialApp(
    home: MediaQuery(
      data: MediaQueryData(disableAnimations: reducirMovimiento),
      child: PantallaInicio(alTerminar: alTerminar),
    ),
  ));
  await tester.pump();
}

void main() {
  testWidgets('el logo sube 40 px, aparece y crece de 0,82 a 1 con un rebote suave', (tester) async {
    var termino = false;
    await abrir(tester, alTerminar: () => termino = true);
    expect(opacidad(tester, 'inicio-logo'), 0);
    final (y0, escala0) = logo(tester);
    expect(y0, closeTo(40, .01));
    expect(escala0, closeTo(.82, .001));

    await tester.pump(const Duration(milliseconds: 700)); // easeOutBack: pasa un poco del final y vuelve
    final (yRebote, escalaRebote) = logo(tester);
    expect(yRebote, lessThan(0));
    expect(escalaRebote, greaterThan(1));
    expect(opacidad(tester, 'inicio-logo'), 1);

    await tester.pump(const Duration(milliseconds: 400)); // 1,1 s
    final (y1, escala1) = logo(tester);
    expect(y1, closeTo(0, .01));
    expect(escala1, closeTo(1, .001));
    expect(termino, isFalse);
  });

  testWidgets('la palabra MATERNA aparece desde los 0,9 s y sube un poco', (tester) async {
    var termino = false;
    await abrir(tester, alTerminar: () => termino = true);
    expect(find.text('MATERNA'), findsOneWidget);
    await tester.pump(const Duration(milliseconds: 890));
    expect(opacidad(tester, 'inicio-texto'), 0);
    await tester.pump(const Duration(milliseconds: 210)); // 1,1 s
    expect(opacidad(tester, 'inicio-texto'), allOf(greaterThan(0), lessThan(1)));
    await tester.pump(const Duration(milliseconds: 400)); // 1,5 s
    expect(opacidad(tester, 'inicio-texto'), 1);
    await tester.pump(const Duration(milliseconds: 450)); // 1,9 s (más un cuadro): termina
    expect(termino, isTrue);
  });

  testWidgets('con «reducir movimiento» el logo y la palabra se ven quietos desde el comienzo', (tester) async {
    await abrir(tester, reducirMovimiento: true);
    expect(opacidad(tester, 'inicio-logo'), 1);
    expect(opacidad(tester, 'inicio-texto'), 1);
    final (y, escala) = logo(tester);
    expect((y, escala), (0, 1));
    await tester.pumpAndSettle();
  });

  testWidgets('cabe en un celular pequeño sin desbordarse', (tester) async {
    tester.view.physicalSize = const Size(320, 568);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await abrir(tester);
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });
}
