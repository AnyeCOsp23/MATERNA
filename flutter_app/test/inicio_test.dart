// Pantalla de inicio (splash): los 5 pétalos se abren uno por uno, aparecen la madre y el bebé y MATERNA letra por letra,
// con la línea de tiempo del video MATERNA_logo_reveal.
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:materna/ui/pantallas/pantalla_inicio.dart';

double opacidad(WidgetTester tester, Key clave) => tester.widget<Opacity>(find.byKey(clave)).opacity;

/// Escala del loto en este instante.
double escala(WidgetTester tester) {
  final t = find.descendant(of: find.byKey(const Key('inicio-logo')), matching: find.byType(Transform)).first;
  return tester.widget<Transform>(t).transform.entry(0, 0);
}

/// Grados que le faltan girar a un pétalo para llegar a su posición final (positivo: hacia la derecha).
double giro(WidgetTester tester, String petalo) {
  // dentro del pétalo: desplazamiento, giro y escala, en ese orden
  final t = find.descendant(of: find.byKey(Key('petalo-$petalo')), matching: find.byType(Transform)).at(1);
  final m = tester.widget<Transform>(t).transform;
  return math.atan2(m.entry(1, 0), m.entry(0, 0)) * 180 / math.pi;
}

/// Opacidad de cada letra de MATERNA, en orden.
List<double> letras(WidgetTester tester) => tester
    .widgetList<Opacity>(find.descendant(of: find.byKey(const Key('inicio-texto')), matching: find.byType(Opacity)))
    .map((o) => o.opacity)
    .toList();

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

/// Lleva la animación hasta el instante `ms` (desde que empezó).
Future<void> hasta(WidgetTester tester, int ms, {required int ahora}) => tester.pump(Duration(milliseconds: ms - ahora));

void main() {
  testWidgets('los pétalos se abren uno por uno, despacio y sin rebote', (tester) async {
    await abrir(tester);
    expect(opacidad(tester, const Key('inicio-logo')), 0);
    expect(escala(tester), closeTo(.94, .001));
    // los laterales empiezan plegados hacia el centro (a la izquierda giran en un sentido; a la derecha, en el otro)
    expect(giro(tester, 'interior_izq'), closeTo(22, .01));
    expect(giro(tester, 'exterior_der'), closeTo(-38, .01));

    // uno por uno: central, interior izq., interior der., exterior izq., exterior der.
    const orden = ['central', 'interior_izq', 'interior_der', 'exterior_izq', 'exterior_der'];
    var ahora = 0;
    for (final (i, p) in orden.indexed) {
      final inicio = 300 + 250 * i;
      await hasta(tester, inicio + 100, ahora: ahora);
      ahora = inicio + 100;
      expect(opacidad(tester, Key('petalo-$p')), allOf(greaterThan(0), lessThan(1)), reason: '$p empieza');
      for (final siguiente in orden.skip(i + 1)) {
        expect(opacidad(tester, Key('petalo-$siguiente')), 0, reason: '$siguiente todavía no');
      }
    }

    // mientras se abre, el pétalo proyecta una sombra suave sobre los de atrás
    expect(opacidad(tester, const Key('sombra-exterior_der')), allOf(greaterThan(0), lessThan(.85)));

    // sin rebote: el giro de un pétalo nunca se pasa de su posición final
    for (var t = ahora + 100; t <= 2700; t += 100) {
      await hasta(tester, t, ahora: ahora);
      ahora = t;
      expect(giro(tester, 'exterior_izq'), greaterThanOrEqualTo(-.001));
      expect(giro(tester, 'exterior_der'), lessThanOrEqualTo(.001));
    }

    await hasta(tester, 2750, ahora: ahora);
    for (final p in orden) {
      expect(giro(tester, p), closeTo(0, .001), reason: p);
      expect(opacidad(tester, Key('petalo-$p')), 1, reason: p);
      expect(find.byKey(Key('sombra-$p')), findsNothing, reason: '$p: la sombra se desvanece al llegar');
    }
    expect(escala(tester), closeTo(1, .001));
  });

  testWidgets('la madre y el bebé aparecen de abajo hacia arriba mientras se abre el último pétalo', (tester) async {
    await abrir(tester);
    await hasta(tester, 2150, ahora: 0);
    expect(find.byKey(const Key('inicio-dibujar')), findsNothing); // aún no empiezan: la silueta está vacía
    expect(find.image(const AssetImage('assets/logo_trazos.webp')), findsNothing);

    await hasta(tester, 2700, ahora: 2150);
    expect(find.byKey(const Key('inicio-dibujar')), findsOneWidget); // apareciendo

    await hasta(tester, 3250, ahora: 2700);
    expect(find.byKey(const Key('inicio-dibujar')), findsNothing);
    expect(find.image(const AssetImage('assets/logo_trazos.webp')), findsOneWidget); // completos
  });

  testWidgets('MATERNA aparece letra por letra y la pantalla termina a los 5 s', (tester) async {
    var termino = false;
    await abrir(tester, alTerminar: () => termino = true);
    expect(letras(tester), hasLength(7));
    expect(letras(tester).every((o) => o == 0), isTrue);

    await hasta(tester, 3500, ahora: 0);
    final aMitad = letras(tester);
    expect(aMitad.first, 1); // la M ya está
    expect(aMitad.last, 0); // la última A todavía no
    expect(aMitad, orderedEquals([...aMitad]..sort((a, b) => b.compareTo(a)))); // de izquierda a derecha

    await hasta(tester, 4350, ahora: 3500); // la última termina a los 4,3 s
    expect(letras(tester).every((o) => o == 1), isTrue);
    expect(termino, isFalse);

    await hasta(tester, 5100, ahora: 4350); // 5 s más el cuadro en que arranca
    expect(termino, isTrue);
  });

  testWidgets('con «reducir movimiento» el logo y la palabra se ven completos y quietos', (tester) async {
    await abrir(tester, reducirMovimiento: true);
    expect(opacidad(tester, const Key('inicio-logo')), 1);
    expect(escala(tester), 1);
    expect(letras(tester).every((o) => o == 1), isTrue);
    expect(giro(tester, 'exterior_izq'), 0);
    expect(find.image(const AssetImage('assets/logo_trazos.webp')), findsOneWidget);
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
