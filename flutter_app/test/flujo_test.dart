// Flujo central del Módulo 2: recorrer el asistente de triaje, evaluar y leer el resultado, como una auxiliar.
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:materna/datos/base_local.dart';
import 'package:materna/motor/recursos.dart';
import 'package:materna/ui/pantallas/pantalla_carga.dart';
import 'package:materna/ui/pantallas/pantalla_principal.dart';
import 'package:materna/ui/tema/tema_materna.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

String leer(String nombre) => File('assets/$nombre').readAsStringSync();

final recursos = RecursosMaterna.desdeTextos(
  preproceso: leer('preproceso.json'),
  modelo: leer('modelo_rf.json'),
  reglas: leer('reglas.json'),
  catalogo: leer('variables_3280.json'),
);

const operador = Perfil(atendidoPor: 'Medico', ips: 'ESE Valledupar');
late BaseLocal base;

/// La pantalla principal con sesión iniciada y una base SQLite en memoria (el acceso se prueba en acceso_test).
/// [elegirArchivo] y [guardarArchivo] reemplazan el selector de archivos del sistema en la carga masiva.
Future<void> abrir(WidgetTester tester,
    {Size tamano = const Size(1000, 2400), ElegirArchivo? elegirArchivo, GuardarArchivo? guardarArchivo}) async {
  tester.view.physicalSize = tamano;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  base = (await tester.runAsync(() => BaseLocal.abrir(databaseFactoryFfiNoIsolate, inMemoryDatabasePath)))!;
  addTearDown(() => tester.runAsync(base.cerrar));
  await tester.pumpWidget(MaterialApp(
    theme: temaMaterna(),
    home: PantallaPrincipal(
      recursos: recursos,
      base: base,
      perfil: operador,
      alCerrarSesion: () {},
      elegirArchivo: elegirArchivo,
      guardarArchivo: guardarArchivo,
    ),
  ));
  await tester.pumpAndSettle();
}

Future<void> tocar(WidgetTester tester, Finder f) async {
  await tester.ensureVisible(f);
  await tester.pumpAndSettle();
  await tester.tap(f);
  await tester.pumpAndSettle();
}

Future<void> escribir(WidgetTester tester, String campo, String valor) async {
  final f = find.byKey(Key('campo-$campo'));
  await tester.ensureVisible(f);
  await tester.pumpAndSettle();
  await tester.enterText(f, valor);
}

Future<void> elegir(WidgetTester tester, String campo, String opcion) =>
    tocar(tester, find.descendant(of: find.byKey(Key('campo-$campo')), matching: find.text(opcion)));

Future<void> elegirEnLista(WidgetTester tester, String campo, String opcion) async {
  await tocar(tester, find.byKey(Key('campo-$campo')));
  await tester.tap(find.text(opcion).last);
  await tester.pumpAndSettle();
}

Future<void> siguiente(WidgetTester tester) => tocar(tester, find.byKey(const Key('siguiente')));

String pasoActual(WidgetTester tester) => tester.widget<Text>(find.byKey(const Key('paso-actual'))).data!;

/// Pasos 1 a 3 de un control de rutina en Valledupar (el caso 3 de la demo de la Fase 2: Bajo Riesgo).
Future<void> llenarRutina(WidgetTester tester) async {
  for (final (campo, valor) in [('edad', '27'), ('semanas_gestacion', '28'), ('n_controles_prenatales', '5')]) {
    await escribir(tester, campo, valor);
  }
  await siguiente(tester);
  for (final (campo, valor) in [('pas_mmhg', '110'), ('pad_mmhg', '70'), ('fcf_bpm', '142'), ('glucosa_mgdl', '88')]) {
    await escribir(tester, campo, valor);
  }
  await elegir(tester, 'proteinuria', 'Negativa');
  await elegir(tester, 'convulsiones', 'No');
  await siguiente(tester);
  await elegir(tester, 'area_residencia', 'Cabecera'); // quién atiende ya viene del perfil del operador
  await siguiente(tester); // ahora en el paso 4: signos de alarma
}

/// Desde los signos de alarma (paso 4) hasta el resultado, sin la valoración opcional.
Future<void> terminarYEvaluar(WidgetTester tester) async {
  await siguiente(tester); // paso 5: valoración de la ruta (opcional)
  await siguiente(tester); // paso 6: revisión
  await tocar(tester, find.byKey(const Key('evaluar')));
}

void main() {
  testWidgets('la barra flotante muestra las 4 pestañas y conserva el triaje a medio llenar', (tester) async {
    await abrir(tester);
    for (final nombre in ['Triaje', 'Carga IPS', 'Historial', 'Acerca de']) {
      expect(find.bySemanticsLabel(nombre), findsOneWidget);
    }
    await escribir(tester, 'edad', '31');
    await tocar(tester, find.byKey(const Key('pestana-2')));
    expect(find.text('Historial local'), findsOneWidget);
    expect(find.byKey(const Key('historial-vacio')), findsOneWidget);
    await tocar(tester, find.byKey(const Key('pestana-0')));
    expect(tester.widget<TextField>(find.byKey(const Key('campo-edad'))).controller!.text, '31');
  });

  testWidgets('cada paso valida antes de avanzar', (tester) async {
    await abrir(tester);
    expect(pasoActual(tester), 'Paso 1 de 6');
    await siguiente(tester);
    expect(pasoActual(tester), 'Paso 1 de 6');
    expect(find.text('Dato obligatorio.'), findsNWidgets(3));
    await escribir(tester, 'edad', '27');
    await escribir(tester, 'semanas_gestacion', '50');
    await escribir(tester, 'n_controles_prenatales', '5');
    await siguiente(tester);
    expect(find.textContaining('Fuera del rango válido (4 a 42)'), findsOneWidget);
    await escribir(tester, 'semanas_gestacion', '28');
    await siguiente(tester);
    expect(pasoActual(tester), 'Paso 2 de 6');
    await siguiente(tester);
    expect(find.text('Escriba el valor o marque «Sin dato».'), findsNWidgets(2));
    await tocar(tester, find.byKey(const Key('atras')));
    expect(pasoActual(tester), 'Paso 1 de 6');
  });

  testWidgets('emergencia: Alto Riesgo por regla clínica, con el motivo', (tester) async {
    await abrir(tester);
    for (final (campo, valor) in [('edad', '26'), ('semanas_gestacion', '31'), ('n_controles_prenatales', '1')]) {
      await escribir(tester, campo, valor);
    }
    await siguiente(tester);
    for (final (campo, valor) in [('pas_mmhg', '165'), ('pad_mmhg', '108'), ('glucosa_mgdl', '110,5')]) {
      await escribir(tester, campo, valor);
    }
    await tocar(tester, find.byKey(const Key('sin-dato-fcf_bpm')));
    await elegir(tester, 'proteinuria', '++ o más');
    await elegir(tester, 'convulsiones', 'Sí');
    await siguiente(tester);
    await elegir(tester, 'area_residencia', 'Rural disperso');
    await elegirEnLista(tester, 'atendido_por', 'Partera tradicional');
    await siguiente(tester);
    await terminarYEvaluar(tester);
    expect(find.text('Alto riesgo'), findsOneWidget);
    expect(find.text('NIVEL ALTO'), findsOneWidget);
    expect(find.textContaining('Signo crítico: '), findsOneWidget);
    expect(find.byKey(const Key('aviso-apoyo')), findsOneWidget);
    expect(find.text('Criterio pendiente de validación clínica'), findsOneWidget);
    expect(find.textContaining('PAS ≥ 160 mmHg'), findsOneWidget);
    expect(find.textContaining('Sin dato de FCF'), findsOneWidget);
  });

  testWidgets('rutina sin alertas: Bajo Riesgo por el modelo', (tester) async {
    await abrir(tester);
    await llenarRutina(tester);
    await terminarYEvaluar(tester);
    expect(find.text('Bajo riesgo'), findsOneWidget);
    expect(find.text('NIVEL BAJO'), findsOneWidget);
    expect(find.text('Sin signos críticos ni de alarma'), findsOneWidget);
    expect(find.text('Herramienta de apoyo: no reemplaza el juicio clínico.'), findsOneWidget);
    // lenguaje para personal de salud: ni «modelo», ni «IA», ni «probabilidad»; los porcentajes, solo al abrir el detalle
    for (final jerga in ['odelo', 'IA ', 'robabilidad', 'mediana']) {
      expect(find.textContaining(jerga), findsNothing, reason: jerga);
    }
    expect(find.textContaining('%'), findsNothing);
    await tocar(tester, find.text('Ver detalle'));
    expect(find.text('Estimación del sistema para cada nivel'), findsOneWidget);
    expect(find.textContaining('%'), findsNWidgets(3));
    expect(find.byKey(const Key('detalle-estimacion')), findsNothing); // aquí no intervino ningún signo
    expect(find.byKey(const Key('alertas-urgentes')), findsNothing);
  });

  testWidgets('sangrado genital: el modelo dice verde, pero el signo de alarma eleva el semáforo a ROJO', (tester) async {
    await abrir(tester);
    await llenarRutina(tester);
    await elegir(tester, 'sangrado_genital', 'Sí');
    await elegir(tester, 'vision_borrosa', 'Sí');
    await terminarYEvaluar(tester);
    expect(find.text('Alto riesgo'), findsOneWidget);
    expect(find.textContaining('Signo de alarma: '), findsOneWidget);
    expect(find.textContaining('Sangrado genital'), findsOneWidget);
    expect(find.textContaining('la estimación sería'), findsNothing); // plegado
    await tocar(tester, find.text('Ver detalle'));
    expect(find.textContaining('Sin ese signo, la estimación sería Bajo Riesgo.'), findsOneWidget);
    expect(find.textContaining('Remisión INMEDIATA'), findsOneWidget); // protocolo de Alto, no «próximos días»
  });

  testWidgets('violencias: urgente pero no obstétrica; no cambia el semáforo y va encima de él', (tester) async {
    await abrir(tester);
    await llenarRutina(tester);
    await siguiente(tester);
    await tocar(tester, find.text('Escalas de riesgo'));
    await elegir(tester, 'tamizaje_violencia_positivo', 'Sí');
    await siguiente(tester);
    await tocar(tester, find.byKey(const Key('evaluar')));
    final alerta = find.byKey(const Key('alertas-urgentes'));
    expect(find.text('Bajo riesgo'), findsOneWidget);
    expect(tester.getTopLeft(alerta).dy, lessThan(tester.getTopLeft(find.byKey(const Key('semaforo'))).dy));
    expect(find.textContaining('ruta de atención a víctimas'), findsOneWidget);
  });

  testWidgets('la revisión muestra lo ingresado y permite volver a editar un paso', (tester) async {
    await abrir(tester);
    await llenarRutina(tester);
    await elegir(tester, 'cefalea', 'No');
    await siguiente(tester);
    await siguiente(tester);
    expect(pasoActual(tester), 'Paso 6 de 6');
    expect(find.text('27 años'), findsOneWidget);
    expect(find.text('110 mmHg'), findsOneWidget);
    expect(find.text('Médico'), findsOneWidget);
    await tocar(tester, find.byKey(const Key('editar-paso-1')));
    expect(pasoActual(tester), 'Paso 2 de 6');
  });

  testWidgets('«Sin dato» no alerta; un «No» explícito del calcio sí', (tester) async {
    await abrir(tester);
    await llenarRutina(tester); // semana 28: el calcio ya debería darse
    await siguiente(tester);
    await tocar(tester, find.text('Plan de cuidado'));
    await elegir(tester, 'calcio', 'No');
    await siguiente(tester);
    await tocar(tester, find.byKey(const Key('evaluar')));
    expect(find.textContaining('Calcio pendiente'), findsOneWidget);
  });

  testWidgets('«Nueva evaluación» vuelve al paso 1 con el formulario en blanco', (tester) async {
    await abrir(tester);
    await llenarRutina(tester);
    await terminarYEvaluar(tester);
    await tocar(tester, find.byKey(const Key('nueva-evaluacion')));
    expect(pasoActual(tester), 'Paso 1 de 6');
    expect(tester.widget<TextField>(find.byKey(const Key('campo-edad'))).controller!.text, isEmpty);
  });

  testWidgets('en el celular el asistente cabe y la barra no tapa los botones', (tester) async {
    await abrir(tester, tamano: const Size(390, 844));
    final boton = find.byKey(const Key('siguiente'));
    await tester.ensureVisible(boton);
    await tester.pumpAndSettle();
    final barra = tester.getTopLeft(find.byKey(const Key('pestana-0'))).dy;
    expect(tester.getBottomLeft(boton).dy, lessThan(barra));
    expect(tester.takeException(), isNull);
  });

  testWidgets('cada evaluación queda guardada y aparece en el historial', (tester) async {
    await abrir(tester);
    await llenarRutina(tester);
    await terminarYEvaluar(tester);
    await tocar(tester, find.byKey(const Key('nueva-evaluacion')));
    await tocar(tester, find.byKey(const Key('pestana-2')));
    expect(find.text('1 evaluación(es)'), findsOneWidget);
    expect(find.text('Triaje individual'), findsOneWidget);
    expect(find.byKey(const Key('nivel-0')), findsOneWidget);
    await tocar(tester, find.descendant(of: find.byKey(const Key('filtro-riesgo')), matching: find.text('Rojo')));
    expect(find.byKey(const Key('historial-vacio')), findsOneWidget);
    await tocar(tester, find.descendant(of: find.byKey(const Key('filtro-riesgo')), matching: find.text('Todas')));
    await tocar(tester, find.byKey(const Key('sincronizar')));
    expect(find.textContaining('Simulación: no se envía ningún dato'), findsOneWidget);
    await tocar(tester, find.text('Triaje individual'));
    expect(find.text('Evaluación guardada'), findsOneWidget);
    expect(find.textContaining('Médico · ESE Valledupar'), findsOneWidget);
    expect(find.byKey(const Key('nueva-evaluacion')), findsNothing);
  });

  testWidgets('«Acerca de» muestra versión, modelo, velocidad y el deslinde', (tester) async {
    await abrir(tester);
    await tocar(tester, find.byKey(const Key('pestana-3')));
    expect(find.text('Herramienta de apoyo al diagnóstico maternal; no reemplaza el criterio médico profesional.'), findsOneWidget);
    expect(find.textContaining('Versión 1.0.0'), findsOneWidget);
    expect(find.text('v1'), findsOneWidget);
    expect(find.textContaining(' ms'), findsWidgets);
    expect(find.text('ESE Valledupar'), findsOneWidget);
  });
}
