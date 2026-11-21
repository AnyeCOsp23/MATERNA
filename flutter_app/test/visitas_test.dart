// Mapa y visitas: orden por prioridad y por recorrido, puntos del mapa, carga masiva ubicada por municipio y la
// pestaña «Mapa y visitas» (marcar «Visitada» y «No la encontramos»).
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:materna/datos/base_local.dart';
import 'package:materna/datos/ubicaciones.dart';
import 'package:materna/motor/carga_masiva.dart';
import 'package:materna/motor/geografia.dart';
import 'package:materna/motor/visitas.dart';
import 'package:materna/ui/pantallas/pantalla_principal.dart';
import 'package:materna/ui/tema/tema_materna.dart';
import 'package:materna/ui/widgets/mapa_materna.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

import 'flujo_test.dart' show tocar;
import 'ubicacion_test.dart' show geo, recursosGeo;

const _uribia = '44847', _manaure = '44560', _valledupar = '20001';
const _base = {
  'edad': 27, 'semanas_gestacion': 28, 'n_controles_prenatales': 5, 'pas_mmhg': 110, 'pad_mmhg': 70, 'fcf_bpm': 142,
  'glucosa_mgdl': 88, 'proteinuria': 0, 'convulsiones': 0, 'area_residencia': 'Rural disperso', 'atendido_por': 'Medico',
};
const _alto = {'pas_mmhg': 170};
const _medio = {'pas_mmhg': 140, 'pad_mmhg': 90};
const _clases = ['Bajo Riesgo', 'Riesgo Medio', 'Alto Riesgo'];

void main() {
  late BaseLocal base;
  late Perfil yo;
  setUp(() async {
    base = await BaseLocal.abrir(databaseFactoryFfiNoIsolate, inMemoryDatabasePath);
    await base.registrar(usuario: 'aux.uribia', pin: '2580',
        perfil: const Perfil(atendidoPor: 'Auxiliar de enfermeria', ips: 'ESE Uribia', municipio: 'Uribia'));
    yo = (await base.perfilDe('aux.uribia'))!;
  });
  tearDown(() => base.cerrar());

  /// Guarda una evaluación con su ubicación; [dias] = hace cuántos días fue el último contacto.
  Future<void> gestante(Map<String, Object> cambios, String municipio, {int? lugar, int dias = 0}) async {
    final evaluacion = recursosGeo.evaluar({..._base, ...cambios});
    final id = await base.guardar(evaluacion, perfil: yo, versionModelo: 'v1', categoria: _clases[evaluacion.clase]);
    await base.guardarUbicacion(id,
        UbicacionCapturada(codigoMunicipio: municipio, idLugar: lugar == null ? null : geo.lugaresDe(municipio)[lugar].id),
        perfil: yo, fecha: DateTime.now().subtract(Duration(days: dias)));
  }

  test('por prioridad: Alto primero y, dentro de cada nivel, el contacto más antiguo; las visitadas salen', () async {
    await gestante({}, _uribia, dias: 30);
    await gestante(_alto, _uribia, lugar: 1, dias: 2);
    await gestante(_alto, _manaure, dias: 9);
    await gestante(_medio, _valledupar, dias: 1);
    final visitas = visitasPorPrioridad(await base.listarUbicaciones(perfil: yo), geo);
    expect([for (final v in visitas) (v.ubicacion.clase, v.municipio)],
        [(2, 'Manaure'), (2, 'Uribia'), (1, 'Valledupar'), (0, 'Uribia')]);
    expect(visitas.first.kmCabecera, closeTo(0, 0.01), reason: 'sin lugar: se ubica en su cabecera');
    expect(visitas[1].lugar, contains('(sintético)'));
    await base.marcarVisita(visitas.first.ubicacion.id, EstadoVisita.visitada, perfil: yo);
    expect(visitasPorPrioridad(await base.listarUbicaciones(perfil: yo), geo), hasLength(3));
  });

  test('recorrido: dentro de cada nivel va al lugar más cercano al anterior', () async {
    await gestante(_alto, _valledupar); // lejos de Uribia
    await gestante(_alto, _manaure); // cerca de Uribia
    await gestante(_alto, _uribia, lugar: 1);
    await gestante({}, _uribia);
    final inicio = geo.cabecera(_uribia)!.posicion;
    final orden = visitasPorRecorrido(await base.listarUbicaciones(perfil: yo), geo, inicio: inicio);
    expect(orden.map((v) => v.ubicacion.clase), [2, 2, 2, 0], reason: 'las de Alto, primero');
    expect(orden.last.municipio, 'Uribia');
    expect(orden[2].municipio, 'Valledupar', reason: 'Valledupar queda de último entre las de Alto: es la más lejana');
    // cada paso del recorrido es el más corto posible desde donde se está
    var actual = inicio;
    final altos = orden.take(3).toList();
    for (final (i, v) in altos.indexed) {
      for (final otra in altos.skip(i + 1)) {
        expect(distanciaKm(actual, v.posicion!), lessThanOrEqualTo(distanciaKm(actual, otra.posicion!)));
      }
      expect(v.kmDesdeAnterior, closeTo(distanciaKm(actual, v.posicion!), 1e-9));
      actual = v.posicion!;
    }
  });

  test('una entrada por gestante: con el mismo código cuenta la evaluación más reciente', () async {
    final carga = await procesarCarga(
        nombre: 'ips_ficticio_3280.csv',
        bytes: File('../data/ejemplos/ips_ficticio_3280.csv').readAsBytesSync(),
        recursos: recursosGeo,
        sal: 'clave-de-prueba-de-la-ips-2026');
    final codigos = [for (final r in carga.resultados) r.idSeudonimo];
    await base.guardarCarga(carga, perfil: yo, versionModelo: 'v1', clases: _clases, clave: 'clave-de-prueba-de-la-ips-2026',
        ubicaciones: [
          for (final r in carga.resultados)
            switch (geo.porNombre(r.evaluacion.registro['municipio'] as String?)) {
              final m? => UbicacionCapturada(codigoMunicipio: m.codigo),
              null => null,
            },
        ]);
    final ubicaciones = await base.listarUbicaciones(perfil: yo);
    expect(ubicaciones, hasLength(300), reason: 'las 300 evaluadas traen un municipio de La Guajira o el Cesar');
    expect(ubicaciones.every((u) => u.nivel == NivelUbicacion.municipio && u.gps == null), isTrue);
    // con código, una por gestante; sin documento (sin código) cada fila cuenta aparte
    expect(unaPorGestante(ubicaciones), hasLength(codigos.whereType<String>().toSet().length + codigos.where((c) => c == null).length));
    // el mapa por municipio suma lo mismo que la carga, nivel por nivel
    final puntos = puntosPorMunicipio([for (final u in ubicaciones) (u.codigoMunicipio, u.clase)], geo);
    for (final clase in [0, 1, 2]) {
      expect(puntos.fold<int>(0, (n, p) => n + p.conteos[clase]), carga.cuantas(clase));
    }
  });

  test('el mapa agrupa por lugar y solo muestra el GPS a quien puede verlo', () async {
    await gestante(_alto, _uribia, lugar: 1);
    await gestante({}, _uribia, lugar: 1);
    await gestante(_medio, _uribia);
    final puntos = puntosDelMapa(await base.listarUbicaciones(perfil: yo), geo);
    expect(puntos, hasLength(2));
    final rancheria = puntos.firstWhere((p) => p.nombre.contains('(sintético)'));
    expect(rancheria.conteos, [1, 0, 1]);
    expect(puntosDelMapa(await base.listarUbicaciones(perfil: yo), geo, clases: {2}).single.total, 1);
  });

  testWidgets('la pestaña «Mapa y visitas» muestra el mapa y permite marcar las visitas', (tester) async {
    tester.view.physicalSize = const Size(1000, 2600);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await tester.runAsync(() async {
      await gestante(_alto, _uribia, lugar: 1, dias: 3);
      await gestante({}, _manaure, dias: 10);
    });
    await tester.pumpWidget(MaterialApp(
      theme: temaMaterna(),
      home: PantallaPrincipal(recursos: recursosGeo, base: base, perfil: yo, alCerrarSesion: () {}),
    ));
    await tester.pumpAndSettle();
    await tocar(tester, find.byKey(const Key('pestana-3')));
    await tester.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 200)));
    await tester.pumpAndSettle();
    expect(find.text('Mapa y visitas'), findsOneWidget);
    expect(find.byType(MapaMaterna), findsOneWidget);
    expect(find.byKey(const Key('mapa-alto')), findsOneWidget, reason: 'el caso Alto resaltado');
    expect(find.text('2 visita(s) pendiente(s)'), findsOneWidget);
    final alto = (await tester.runAsync(() => base.listarUbicaciones(perfil: yo)))!.first;
    await tocar(tester, find.byKey(Key('no-encontrada-${alto.id}')));
    await tester.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 200)));
    await tester.pumpAndSettle();
    expect(find.byKey(Key('sin-localizar-${alto.id}')), findsOneWidget, reason: 'sigue pendiente, marcada');
    await tocar(tester, find.byKey(Key('visitada-${alto.id}')));
    await tester.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 200)));
    await tester.pumpAndSettle();
    expect(find.text('1 visita(s) pendiente(s)'), findsOneWidget);
    await tocar(tester, find.text('Recorrido'));
    expect(find.textContaining('la más cercana a la anterior'), findsOneWidget);
  });
}
