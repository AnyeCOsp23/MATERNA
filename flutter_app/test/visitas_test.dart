// Mapa y visitas: orden por prioridad y recorrido por lugar, visitadas, puntos del mapa, carga masiva ubicada por municipio y la
// pestaña «Mapa y visitas» (filtros, marcar con ✓, «No la encontramos», deshacer y el recorrido dibujado).
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
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

  test('recorrido por lugar: primero las paradas con Alto; después, el resto solo por cercanía', () async {
    await gestante(_alto, _valledupar); // lejos de Uribia
    await gestante({}, _valledupar); // misma cabecera: va en la misma parada
    await gestante(_alto, _manaure); // cerca de Uribia
    await gestante(_alto, _uribia, lugar: 1);
    await gestante({}, _uribia, lugar: 1, dias: 20); // mismo lugar que la de Alto
    await gestante(_medio, _uribia); // Medio, en la cabecera del punto de partida (lejos de Valledupar)
    await gestante({}, _valledupar, lugar: 1); // Bajo, en un lugar de Valledupar (cerca de su cabecera)
    final inicio = geo.cabecera(_uribia)!.posicion;
    final ruta = recorridoPorLugar(await base.listarUbicaciones(perfil: yo), geo, inicio: inicio);

    expect(ruta.paradas, hasLength(5), reason: '7 gestantes en 5 lugares: una parada por lugar');
    expect(ruta.paradas.take(3).map((p) => p.nivel), [2, 2, 2], reason: 'primero los lugares con alguna de Alto');
    expect(ruta.paradas[2].municipio, 'Valledupar', reason: 'la más lejana de las de Alto, de última');
    // después de Valledupar no vuelve a Uribia por la de Medio: sigue a la más cercana, aunque sea de Bajo
    expect([for (final p in ruta.paradas.skip(3)) (p.nivel, p.municipio)], [(0, 'Valledupar'), (1, 'Uribia')]);
    final rancheria = ruta.paradas.firstWhere((p) => p.visitas.length == 2 && p.municipio == 'Uribia');
    expect(rancheria.visitas.map((v) => v.ubicacion.clase), [2, 0], reason: 'en la parada, por prioridad');
    expect(ruta.visitas, hasLength(7));

    // cada parada de Alto es la más cercana a la anterior entre las de Alto que quedan
    var actual = inicio;
    final altas = ruta.paradas.take(3).toList();
    for (final (i, p) in altas.indexed) {
      for (final otra in altas.skip(i + 1)) {
        expect(distanciaKm(actual, p.posicion!), lessThanOrEqualTo(distanciaKm(actual, otra.posicion!)));
      }
      expect(p.kmDesdeAnterior, closeTo(distanciaKm(actual, p.posicion!), 1e-9));
      actual = p.posicion!;
    }
    expect(ruta.totalKm, closeTo(ruta.paradas.fold<double>(0, (s, p) => s + p.kmDesdeAnterior!), 1e-9));
  });

  test('visitadas: de la más reciente a la más antigua; no entran al recorrido', () async {
    await gestante(_alto, _uribia);
    await gestante({}, _manaure);
    await gestante(_medio, _valledupar);
    final todas = await base.listarUbicaciones(perfil: yo);
    await base.marcarVisita(todas[0].id, EstadoVisita.visitada, perfil: yo, fecha: DateTime(2026, 11, 1));
    await base.marcarVisita(todas[1].id, EstadoVisita.visitada, perfil: yo, fecha: DateTime(2026, 11, 20));
    final ubicaciones = await base.listarUbicaciones(perfil: yo);
    expect([for (final v in visitasHechas(ubicaciones, geo)) v.ubicacion.id], [todas[1].id, todas[0].id]);
    expect(recorridoPorLugar(ubicaciones, geo).visitas.single.ubicacion.id, todas[2].id);
  });

  test('deshacer una marca deja el estado y el último contacto como estaban', () async {
    await gestante(_alto, _uribia, dias: 12);
    final antes = (await base.listarUbicaciones(perfil: yo)).single;
    await base.marcarVisita(antes.id, EstadoVisita.visitada, perfil: yo);
    expect((await base.listarUbicaciones(perfil: yo)).single.estado, EstadoVisita.visitada);
    await base.restaurarVisita(antes.id, antes.estado, antes.ultimoContacto, perfil: yo);
    final despues = (await base.listarUbicaciones(perfil: yo)).single;
    expect((despues.estado, despues.ultimoContacto), (antes.estado, antes.ultimoContacto));
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
    expect(rancheria.nivelMasAlto(), 2);
    final alto = (await base.listarUbicaciones(perfil: yo)).firstWhere((u) => u.clase == 2);
    await base.marcarVisita(alto.id, EstadoVisita.visitada, perfil: yo);
    final despues = puntosDelMapa(await base.listarUbicaciones(perfil: yo), geo).firstWhere((p) => p.clave == rancheria.clave);
    expect(despues.visitadas, [0, 0, 1]);
    expect((despues.nivelMasAlto(), despues.nivelMasAlto(sinVisitadas: true)), (2, 0),
        reason: 'ya visitada la de Alto, el lugar se pinta del nivel de la que falta');
    expect(puntosDelMapa(await base.listarUbicaciones(perfil: yo), geo, clases: {2}).single.total, 1);
  });

  // ------------------------------------------------------------------ mapa: agrupación dinámica y etiquetas
  const guajira = ['44001', '44560', '44847', '44430', '44035', '44090', '44279', '44650']; // 8 cabeceras de La Guajira
  final lejos = ['20001', '20011']; // Valledupar y Aguachica, en el Cesar
  List<PuntoMapa> puntosDe(List<String> codigos) =>
      puntosPorMunicipio([for (final (i, c) in codigos.indexed) for (var k = 0; k <= i % 3; k++) (c, (i + k) % 3)], geo);
  MapCamera camara(double zoom) => MapCamera(
      crs: const Epsg3857(), center: const LatLng(10.5, -73), zoom: zoom, rotation: 0, nonRotatedSize: const Size(400, 320));

  test('agrupación: al alejar se juntan los lugares cercanos y al acercar se separan; nunca se pierde una gestante', () {
    final puntos = puntosDe([...guajira, ...lejos]);
    final total = puntos.fold<int>(0, (s, p) => s + p.total);
    var antes = 0;
    for (final zoom in [5.0, 6.0, 7.0, 8.0, 9.0, 11.0, 13.0]) {
      final grupos = agruparLugares(puntos, camara(zoom), zoom);
      expect(grupos.fold<int>(0, (s, g) => s + g.total), total, reason: 'zoom $zoom');
      expect({for (final g in grupos) ...g.lugares.map((p) => p.clave)}, hasLength(puntos.length), reason: 'cada lugar en un solo grupo');
      expect(grupos.length, greaterThanOrEqualTo(antes), reason: 'al acercar, los grupos solo se separan');
      antes = grupos.length;
      // en pantalla, ningún par de marcadores queda más cerca que el radio de agrupación
      for (final (i, g) in grupos.indexed) {
        for (final h in grupos.skip(i + 1)) {
          final d = (camara(zoom).projectAtZoom(g.centro, zoom) - camara(zoom).projectAtZoom(h.centro, zoom)).distance;
          expect(d, greaterThan(20), reason: 'zoom $zoom: ${g.id} y ${h.id} se superponen');
        }
      }
    }
    expect(agruparLugares(puntos, camara(5), 5).length, lessThan(puntos.length), reason: 'de lejos hay grupos');
    expect(agruparLugares(puntos, camara(13), 13), hasLength(puntos.length), reason: 'de cerca, todos sueltos');
    final grupo = agruparLugares(puntos, camara(5), 5).firstWhere((g) => !g.esLugar);
    expect(grupo.nivel(sinVisitadas: false), grupo.lugares.map((p) => p.nivelMasAlto()!).reduce((a, b) => a > b ? a : b),
        reason: 'el grupo toma el color del nivel más alto de sus lugares');
  });

  testWidgets('mapa: etiqueta al tocar cualquier marcador, una sola a la vez, y «Acercar» separa el grupo', (tester) async {
    final puntos = puntosDe([...guajira, ...lejos]);
    PuntoMapa? tocado;
    List<PuntoMapa>? zona;
    await tester.pumpWidget(MaterialApp(
      theme: temaMaterna(),
      home: Scaffold(
        body: SizedBox(
          width: 400,
          child: MapaMaterna(
              geografia: geo,
              puntos: puntos,
              alto: 320,
              alElegirZona: (_, lugares) {
                zona = lugares;
                if (lugares.length == 1) tocado = lugares.single;
              }),
        ),
      ),
    ));
    await tester.pumpAndSettle();
    Finder marcadores() => find.byWidgetPredicate((w) => w.key is ValueKey<String> && (w.key! as ValueKey<String>).value.startsWith('anim-'));
    final alInicio = marcadores().evaluate().length;
    expect(alInicio, lessThan(puntos.length), reason: 'con todo el mapa a la vista, los cercanos van agrupados');
    expect(find.byKey(const Key('mapa-etiqueta')), findsNothing);

    // tocar un grupo: etiqueta con cuántos lugares y «Acercar»
    final grupo = find.byWidgetPredicate((w) => w is Semantics && (w.properties.label ?? '').startsWith('Grupo de'));
    expect(grupo, findsWidgets);
    final idGrupo = (tester.widget(find.descendant(of: grupo.first, matching: marcadores())).key! as ValueKey<String>).value.substring(5);
    await tester.tap(grupo.first, warnIfMissed: false);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('mapa-etiqueta')), findsOneWidget);
    expect(find.textContaining('gestantes ·'), findsOneWidget);
    expect(zona, isNull, reason: 'tocar un grupo solo abre su etiqueta');
    await tester.tap(find.byKey(const Key('mapa-etiqueta-ver')));
    await tester.pumpAndSettle();
    expect(zona!.map((p) => p.clave).toSet(), idGrupo.split('|').toSet(), reason: '«Ver gestantes» elige todo el grupo');
    await tester.tap(find.byKey(const Key('mapa-etiqueta-acercar')));
    await tester.pumpAndSettle();
    // el zoom es real: ese grupo ya no está y sus lugares aparecen en marcadores propios
    final ids = [for (final e in marcadores().evaluate()) (e.widget.key! as ValueKey<String>).value.substring(5)];
    expect(ids, isNot(contains(idGrupo)));
    expect(ids.where((id) => id.split('|').every(idGrupo.split('|').contains)).length, greaterThan(1));
    expect(find.byKey(const Key('mapa-etiqueta')), findsNothing, reason: 'al acercar, la etiqueta se cierra');

    // tocar un lugar suelto: su etiqueta con el nombre; tocar otro cierra la anterior
    final sueltos = find.byWidgetPredicate((w) => w is Semantics && (w.properties.label ?? '').contains('gestante(s)'));
    expect(sueltos, findsWidgets);
    await tester.tap(sueltos.first, warnIfMissed: false);
    await tester.pumpAndSettle();
    expect(tocado, isNotNull, reason: 'avisa a la pantalla (la lista baja a ese lugar)');
    expect(find.byKey(const Key('mapa-etiqueta')), findsOneWidget);
    expect(find.descendant(of: find.byKey(const Key('mapa-etiqueta')), matching: find.text(tocado!.nombre)), findsOneWidget);
    final primero = tocado;
    if (sueltos.evaluate().length > 1) {
      await tester.tap(sueltos.at(1), warnIfMissed: false);
      await tester.pumpAndSettle();
      expect(tocado, isNot(same(primero)));
      expect(find.byKey(const Key('mapa-etiqueta')), findsOneWidget, reason: 'solo una etiqueta abierta');
    }
    // los botones + y − cambian el zoom de verdad
    final antesMenos = marcadores().evaluate().length;
    for (var i = 0; i < 3; i++) {
      await tester.tap(find.byKey(const Key('mapa-alejar')));
      await tester.pumpAndSettle();
    }
    expect(marcadores().evaluate().length, lessThanOrEqualTo(antesMenos), reason: 'al alejar se vuelven a agrupar');
    for (var i = 0; i < 6; i++) {
      await tester.tap(find.byKey(const Key('mapa-acercar')));
      await tester.pumpAndSettle();
    }
    expect(tester.takeException(), isNull);
  });

  testWidgets('cabecera con muchas gestantes: primero 5 y «Ver las N gestantes»', (tester) async {
    tester.view.physicalSize = const Size(1000, 2600);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await tester.runAsync(() async {
      for (var i = 0; i < 7; i++) {
        await gestante(i.isEven ? _alto : {}, _uribia, lugar: 1, dias: i);
      }
    });
    await tester.pumpWidget(MaterialApp(
      theme: temaMaterna(),
      home: PantallaPrincipal(recursos: recursosGeo, base: base, perfil: yo, alCerrarSesion: () {}),
    ));
    await tester.pumpAndSettle();
    await tocar(tester, find.byKey(const Key('pestana-3')));
    await tester.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 200)));
    await tester.pumpAndSettle();
    await tocar(tester, find.byKey(const Key('orden-recorrido')));
    Finder botonesVisita() =>
        find.byWidgetPredicate((w) => w.key is ValueKey<String> && (w.key! as ValueKey<String>).value.startsWith('visitada-'));
    await tocar(tester, find.byKey(const Key('parada-abrir-1')));
    expect(botonesVisita(), findsNWidgets(5));
    expect(find.text('Ver las 7 gestantes'), findsOneWidget);
    await tocar(tester, find.byKey(const Key('parada-ver-todas-1')));
    expect(botonesVisita(), findsNWidgets(7));
    expect(find.text('Ver las 7 gestantes'), findsNothing);
  });

  Future<void> esperar(WidgetTester tester) async {
    await tester.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 200)));
    await tester.pumpAndSettle();
  }

  testWidgets('la pestaña «Mapa y visitas»: filtros, marcar y deshacer, y el recorrido dibujado', (tester) async {
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
    await esperar(tester);
    expect(find.text('Mapa y visitas'), findsOneWidget);
    expect(find.byType(MapaMaterna), findsOneWidget);
    expect(find.byKey(const Key('mapa-alto')), findsOneWidget, reason: 'el lugar con un caso Alto, en rojo');
    expect(find.text('2 gestantes pendientes'), findsOneWidget);
    expect(find.byKey(const Key('visita-siguiente')), findsOneWidget);
    expect(find.textContaining('Límites y cabeceras'), findsNothing, reason: 'el aviso pasó a «Acerca de»');

    // tocar un lugar en el mapa: la lista se filtra a esa zona y baja hasta su aviso; «Ver todas» lo quita
    final lugarMapa = find.byWidgetPredicate((w) => w is Semantics && (w.properties.label ?? '').startsWith('Cabecera de Manaure'));
    await tester.tap(lugarMapa, warnIfMissed: false);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('zona-elegida')), findsOneWidget);
    expect(find.text('1 gestante pendiente'), findsOneWidget);
    expect(find.byKey(const Key('mapa-etiqueta')), findsOneWidget, reason: 'y su etiqueta en el mapa');
    // los números de los filtros NO cambian con la zona (antes cambiaban y parecían otros)
    expect(find.descendant(of: find.byKey(const Key('estado-pendientes')), matching: find.text('2')), findsOneWidget);
    expect(find.descendant(of: find.byKey(const Key('estado-todas')), matching: find.text('2')), findsOneWidget);
    await tocar(tester, find.byKey(const Key('zona-quitar')));
    expect(find.byKey(const Key('zona-elegida')), findsNothing);
    expect(find.text('2 gestantes pendientes'), findsOneWidget);
    final alto = (await tester.runAsync(() => base.listarUbicaciones(perfil: yo)))!.firstWhere((u) => u.clase == 2);

    // el detalle está plegado; al tocar la tarjeta aparece «No la encontramos»
    expect(find.byKey(Key('no-encontrada-${alto.id}')), findsNothing);
    await tocar(tester, find.descendant(of: find.byKey(Key('visita-${alto.id}')), matching: find.byType(InkWell)).first);
    // la tarjeta elegida se acerca un poco (escala 1,03), sin borde
    expect(tester.widget<AnimatedScale>(find.byKey(const Key('tarjeta-seleccionada'))).scale, 1.03);
    expect(find.descendant(of: find.byKey(Key('visita-${alto.id}')), matching: find.byKey(const Key('tarjeta-seleccionada'))), findsOneWidget);
    await tocar(tester, find.byKey(Key('no-encontrada-${alto.id}')));
    await esperar(tester);
    expect(find.byKey(Key('sin-localizar-${alto.id}')), findsOneWidget, reason: 'sigue pendiente, marcada');

    // ✓: sale de pendientes; «Deshacer» la devuelve tal como estaba
    await tocar(tester, find.byKey(Key('visitada-${alto.id}')));
    await esperar(tester);
    expect(find.text('1 gestante pendiente'), findsOneWidget);
    expect(find.text('Visitadas: 1 de 2'), findsOneWidget);
    // el aviso con «Deshacer» se va solo a los 5 segundos
    final aviso = tester.widget<SnackBar>(find.byType(SnackBar));
    expect((aviso.duration, aviso.persist), (const Duration(seconds: 5), false));
    await tocar(tester, find.text('Deshacer'));
    await esperar(tester);
    expect(find.text('2 gestantes pendientes'), findsOneWidget);
    expect(find.byKey(Key('sin-localizar-${alto.id}')), findsOneWidget, reason: 'deshacer restaura el estado anterior');

    // filtro de estado: Visitadas muestra la visita hecha y permite devolverla
    await tocar(tester, find.byKey(Key('visitada-${alto.id}')));
    await esperar(tester);
    await tocar(tester, find.byKey(const Key('estado-visitadas')));
    expect(find.byKey(Key('devolver-${alto.id}')), findsOneWidget);
    expect(find.byKey(const Key('orden-visitas')), findsNothing, reason: 'las visitadas van por fecha, sin orden');
    expect(find.byKey(const Key('mapa-alto')), findsNothing, reason: 'en el mapa, solo la visitada (en gris)');
    await tocar(tester, find.byKey(const Key('estado-todas')));
    expect(find.text('PENDIENTES'), findsOneWidget);
    expect(find.text('VISITADAS'), findsOneWidget);
    await tocar(tester, find.byKey(const Key('estado-pendientes')));

    // recorrido: paradas numeradas en la lista y en el mapa, con el punto de partida
    await tocar(tester, find.byKey(const Key('orden-recorrido')));
    expect(find.byKey(const Key('resumen-recorrido')), findsOneWidget);
    expect(find.byKey(const Key('parada-1')), findsOneWidget);
    expect(find.byKey(const Key('parada-mapa-1')), findsOneWidget);
    expect(find.byKey(const Key('mapa-partida')), findsOneWidget);
    // las cabeceras empiezan plegadas; al abrir una se ven sus gestantes y el mapa abre la etiqueta de ese lugar
    Finder botonesVisita() =>
        find.byWidgetPredicate((w) => w.key is ValueKey<String> && (w.key! as ValueKey<String>).value.startsWith('visitada-'));
    expect(botonesVisita(), findsNothing);
    expect(find.byKey(const Key('mapa-etiqueta')), findsNothing);
    await tocar(tester, find.byKey(const Key('parada-abrir-1')));
    expect(botonesVisita(), findsOneWidget);
    expect(find.byKey(const Key('mapa-etiqueta')), findsOneWidget, reason: 'el mapa fue a ese lugar');
    await tocar(tester, find.byKey(const Key('parada-abrir-1')));
    expect(botonesVisita(), findsNothing);

    // el aviso de los lugares de prueba está en «Acerca de»
    await tocar(tester, find.byKey(const Key('pestana-4')));
    expect(find.byKey(const Key('acerca-mapa-prueba')), findsOneWidget);
  });
}
