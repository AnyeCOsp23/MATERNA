// Georreferenciación en la app: geografía local (DANE + puntos sintéticos), reglas de la ubicación en la base
// local (consentimiento y rol para el GPS) y la sección «Ubicación para la visita» del triaje.
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:materna/datos/base_local.dart';
import 'package:materna/datos/ubicaciones.dart';
import 'package:materna/motor/geografia.dart';
import 'package:materna/motor/recursos.dart';
import 'package:materna/ui/pantallas/pantalla_principal.dart';
import 'package:materna/ui/tema/tema_materna.dart';
import 'package:materna/ui/widgets/seccion_ubicacion.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

import 'flujo_test.dart' show elegirEnLista, escribir, elegir, leer, siguiente, tocar;

final geo = Geografia.desdeTextos(
  municipios: leer('geo/municipios_guajira_cesar.geojson'),
  cabeceras: leer('geo/cabeceras_guajira_cesar.json'),
  puntos: leer('geo/puntos_concentracion.json'),
);
final recursosGeo = RecursosMaterna.desdeTextos(
  preproceso: leer('preproceso.json'),
  modelo: leer('modelo_rf.json'),
  reglas: leer('reglas.json'),
  catalogo: leer('variables_3280.json'),
  geografia: geo,
);
const _rutina = {
  'edad': 27, 'semanas_gestacion': 28, 'n_controles_prenatales': 5, 'pas_mmhg': 110, 'pad_mmhg': 70, 'fcf_bpm': 142,
  'glucosa_mgdl': 88, 'proteinuria': 0, 'convulsiones': 0, 'area_residencia': 'Rural disperso', 'atendido_por': 'Medico',
};
const _uribia = '44847', _valledupar = '20001';

Future<BaseLocal> baseNueva() => BaseLocal.abrir(databaseFactoryFfiNoIsolate, inMemoryDatabasePath);

void main() {
  group('geografía local', () {
    test('40 municipios reales del DANE y cada lugar dentro de su municipio', () {
      expect(geo.municipios, hasLength(40));
      expect(geo.municipios.values.where((m) => m.departamento == 'La Guajira'), hasLength(15));
      expect(geo.fuente, contains('DANE'));
      for (final m in geo.municipios.values) {
        for (final l in geo.lugaresDe(m.codigo)) {
          expect(m.contiene(l.posicion), isTrue, reason: l.nombre);
        }
      }
    });

    test('la cabecera va primero, los puntos van rotulados como sintéticos y los nombres se encuentran sin tildes', () {
      final lugares = geo.lugaresDe(_uribia);
      expect(lugares.first.esCabecera, isTrue);
      expect(lugares.first.sintetico, isFalse);
      expect(lugares.skip(1).every((l) => l.sintetico && l.nombre.contains('(sintético)')), isTrue);
      expect(geo.porNombre('codazzi')?.codigo, '20013');
      expect(geo.porNombre('URIBIA')?.codigo, _uribia);
      expect(geo.porNombre('Bogotá'), isNull);
    });

    test('el GPS se ubica en su municipio y la distancia es la misma que en Python', () {
      final cabeceraUribia = geo.cabecera(_uribia)!.posicion;
      expect(geo.municipioEn(cabeceraUribia)?.codigo, _uribia);
      expect(geo.municipioEn((lon: -74.07, lat: 4.71)), isNull); // Bogotá: fuera de los dos departamentos
      final (cercana, km) = geo.cabeceraMasCercana((lon: cabeceraUribia.lon + 0.01, lat: cabeceraUribia.lat))!;
      expect(cercana.codigoMunicipio, _uribia);
      expect(km, closeTo(1.09, 0.01));
      // tests/test_georreferencia.py::test_distancia_en_km usa las mismas cabeceras
      expect(distanciaKm((lon: -72.9118, lat: 11.5286), (lon: -73.2594, lat: 10.4605)), inInclusiveRange(120, 130));
    });
  });

  group('ubicaciones en la base local', () {
    late BaseLocal base;
    late Perfil medico, partera;
    setUp(() async {
      base = await baseNueva();
      for (final (u, rol) in [('medico.uri', 'Medico'), ('partera.uri', 'Partera tradicional')]) {
        await base.registrar(usuario: u, pin: '2580', perfil: Perfil(atendidoPor: rol, ips: 'ESE Uribia'));
      }
      medico = (await base.perfilDe('medico.uri'))!;
      partera = (await base.perfilDe('partera.uri'))!;
    });
    tearDown(() => base.cerrar());

    Future<int> evaluacion(Perfil p, {Map<String, Object> cambios = const {}}) =>
        base.guardar(recursosGeo.evaluar({..._rutina, ...cambios}), perfil: p, versionModelo: 'v1', categoria: 'x');

    test('el GPS exacto exige consentimiento y una cuenta de médico o enfermería', () async {
      final gps = geo.cabecera(_uribia)!.posicion;
      final id = await evaluacion(medico);
      expect(() => base.guardarUbicacion(id, UbicacionCapturada(codigoMunicipio: _uribia, gps: gps), perfil: medico),
          throwsArgumentError, reason: 'sin consentimiento');
      final idPartera = await evaluacion(partera);
      expect(
          () => base.guardarUbicacion(idPartera,
              UbicacionCapturada(codigoMunicipio: _uribia, gps: gps, consentimiento: true), perfil: partera),
          throwsArgumentError, reason: 'la partera trabaja por lugar');
      await base.guardarUbicacion(id, UbicacionCapturada(codigoMunicipio: _uribia, gps: gps, consentimiento: true),
          perfil: medico);
      final u = (await base.listarUbicaciones(perfil: medico)).single;
      expect(u.nivel, NivelUbicacion.gps);
      expect(u.gps, isNotNull);
      expect(u.consentimiento, isTrue);
    });

    test('la referencia comunitaria es un rol y un apodo corto, sin documentos', () async {
      final id = await evaluacion(partera);
      final lugar = geo.lugaresDe(_uribia)[1].id;
      expect(
          () => base.guardarUbicacion(id, UbicacionCapturada(codigoMunicipio: _uribia, idLugar: lugar, referenciaApodo: 'CC 1065123456'),
              perfil: partera),
          throwsArgumentError);
      expect(() => base.guardarUbicacion(id, UbicacionCapturada(codigoMunicipio: _uribia, referenciaRol: 'Juan Pérez'), perfil: partera),
          throwsArgumentError);
      await base.guardarUbicacion(
          id, UbicacionCapturada(codigoMunicipio: _uribia, idLugar: lugar, referenciaRol: 'Partera', referenciaApodo: 'La de Jepira'),
          perfil: partera);
      final u = (await base.listarUbicaciones(perfil: partera)).single;
      expect((u.nivel, u.idLugar, u.referenciaRol, u.referenciaApodo), (NivelUbicacion.lugar, lugar, 'Partera', 'La de Jepira'));
      expect(u.posicion(geo), geo.lugar(lugar)!.posicion);
    });

    test('cada cuenta ve solo sus ubicaciones; las de Alto van primero', () async {
      await base.guardarUbicacion(await evaluacion(partera), const UbicacionCapturada(codigoMunicipio: _uribia), perfil: partera);
      await base.guardarUbicacion(await evaluacion(partera, cambios: {'pas_mmhg': 170}),
          const UbicacionCapturada(codigoMunicipio: _valledupar), perfil: partera);
      await base.guardarUbicacion(await evaluacion(medico), const UbicacionCapturada(codigoMunicipio: _uribia), perfil: medico);
      final suyas = await base.listarUbicaciones(perfil: partera);
      expect(suyas, hasLength(2));
      expect(suyas.first.clase, 2, reason: 'PAS 170: Alto por regla');
      expect(suyas.first.posicion(geo), geo.cabecera(_valledupar)!.posicion, reason: 'sin lugar: la cabecera');
      expect(await base.listarUbicaciones(perfil: medico), hasLength(1));
    });

    test('marcar la visita: «visitada» actualiza el último contacto y «sin localizar» no', () async {
      await base.guardarUbicacion(await evaluacion(partera), const UbicacionCapturada(codigoMunicipio: _uribia),
          perfil: partera, fecha: DateTime(2026, 11, 1));
      final u = (await base.listarUbicaciones(perfil: partera)).single;
      await base.marcarVisita(u.id, EstadoVisita.sinLocalizar, perfil: partera, fecha: DateTime(2026, 11, 5));
      var ahora = (await base.listarUbicaciones(perfil: partera)).single;
      expect((ahora.estado, ahora.ultimoContacto), (EstadoVisita.sinLocalizar, DateTime(2026, 11, 1)));
      await base.marcarVisita(u.id, EstadoVisita.visitada, perfil: partera, fecha: DateTime(2026, 11, 9));
      ahora = (await base.listarUbicaciones(perfil: partera)).single;
      expect((ahora.estado, ahora.ultimoContacto), (EstadoVisita.visitada, DateTime(2026, 11, 9)));
      // otra cuenta no puede marcar las visitas ajenas
      await base.marcarVisita(u.id, EstadoVisita.pendiente, perfil: medico);
      expect((await base.listarUbicaciones(perfil: partera)).single.estado, EstadoVisita.visitada);
    });

    test('al eliminar una cuenta se borran también sus ubicaciones', () async {
      await base.guardarUbicacion(await evaluacion(partera), const UbicacionCapturada(codigoMunicipio: _uribia), perfil: partera);
      await base.eliminarUsuario('partera.uri');
      await base.registrar(usuario: 'partera.uri', pin: '2580', perfil: const Perfil(atendidoPor: 'Partera tradicional', ips: 'x'));
      expect(await base.listarUbicaciones(perfil: (await base.perfilDe('partera.uri'))!), isEmpty);
    });
  });

  group('sección «Ubicación para la visita»', () {
    Future<ControlUbicacion> pintar(WidgetTester tester, String atiende, {ObtenerPosicion? gps}) async {
      final control = ControlUbicacion(codigoMunicipio: _valledupar);
      addTearDown(control.dispose);
      await tester.pumpWidget(MaterialApp(
        theme: temaMaterna(),
        home: Scaffold(
          body: SingleChildScrollView(
            child: SeccionUbicacion(control: control, geografia: geo, atendidoPor: atiende,
                obtenerPosicion: gps ?? () async => geo.cabecera(_uribia)!.posicion),
          ),
        ),
      ));
      await tester.tap(find.text('Ubicación para la visita'));
      await tester.pumpAndSettle();
      return control;
    }

    testWidgets('médico: con el permiso de la gestante usa el GPS, que corrige el municipio y muestra la distancia',
        (tester) async {
      final control = await pintar(tester, 'Medico');
      expect(find.text('Valledupar (Cesar)'), findsOneWidget, reason: 'empieza en el municipio de la cuenta');
      final boton = find.byKey(const Key('usar_mi_ubicacion'));
      expect(tester.widget<OutlinedButton>(boton).onPressed, isNull, reason: 'sin consentimiento no se activa');
      await tester.tap(find.byKey(const Key('ubicacion_consentimiento')));
      await tester.pumpAndSettle();
      await tester.tap(boton);
      await tester.pumpAndSettle();
      expect(find.text('Ubicación exacta tomada'), findsOneWidget);
      expect(control.codigoMunicipio, _uribia, reason: 'el GPS cae en Uribia');
      expect(find.textContaining('cabecera de Uribia'), findsOneWidget);
      expect(control.capturada()!.nivel, NivelUbicacion.gps);
      // si se quita el permiso, el GPS no se conserva
      await tester.tap(find.byKey(const Key('ubicacion_consentimiento')));
      await tester.pumpAndSettle();
      expect(control.capturada()!.gps, isNull);
    });

    testWidgets('partera: no ve el GPS; registra el lugar y la referencia comunitaria', (tester) async {
      final control = await pintar(tester, 'Partera tradicional');
      expect(find.byKey(const Key('usar_mi_ubicacion')), findsNothing);
      expect(find.byKey(const Key('ubicacion_sin_gps')), findsOneWidget);
      final lugar = geo.lugaresDe(_valledupar)[1];
      await elegirEnLista(tester, 'ubicacion_lugar', lugar.nombre);
      await elegirEnLista(tester, 'ubicacion_referencia', 'Autoridad tradicional');
      expect(find.byKey(const Key('ubicacion_distancia')), findsOneWidget);
      final u = control.capturada()!;
      expect((u.nivel, u.idLugar, u.referenciaRol, u.gps), (NivelUbicacion.lugar, lugar.id, 'Autoridad tradicional', null));
    });

    testWidgets('un GPS fuera de La Guajira y el Cesar se avisa y no cambia el municipio', (tester) async {
      final control = await pintar(tester, 'Enfermero(a)', gps: () async => (lon: -74.07, lat: 4.71));
      await tester.tap(find.byKey(const Key('ubicacion_consentimiento')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('usar_mi_ubicacion')));
      await tester.pumpAndSettle();
      expect(find.textContaining('fuera de La Guajira y el Cesar'), findsOneWidget);
      expect(control.codigoMunicipio, _valledupar);
    });
  });

  testWidgets('el triaje guarda la evaluación con su ubicación para la visita', (tester) async {
    tester.view.physicalSize = const Size(1000, 2400);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    final base = (await tester.runAsync(baseNueva))!;
    addTearDown(() => tester.runAsync(base.cerrar));
    const yo = Perfil(atendidoPor: 'Auxiliar de enfermeria', ips: 'ESE Uribia', municipio: 'Uribia');
    await tester.pumpWidget(MaterialApp(
      theme: temaMaterna(),
      home: PantallaPrincipal(recursos: recursosGeo, base: base, perfil: yo, alCerrarSesion: () {}),
    ));
    await tester.pumpAndSettle();
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
    await elegir(tester, 'area_residencia', 'Rural disperso');
    await tocar(tester, find.text('Ubicación para la visita'));
    expect(find.text('Uribia (La Guajira)'), findsOneWidget, reason: 'el municipio de la cuenta');
    final lugar = geo.lugaresDe(_uribia)[2];
    await elegirEnLista(tester, 'ubicacion_lugar', lugar.nombre);
    await siguiente(tester);
    await siguiente(tester);
    await siguiente(tester);
    await tocar(tester, find.byKey(const Key('evaluar')));
    final guardadas = (await tester.runAsync(() => base.listarUbicaciones(perfil: yo)))!;
    expect(guardadas, hasLength(1));
    expect((guardadas.single.codigoMunicipio, guardadas.single.idLugar, guardadas.single.nivel),
        (_uribia, lugar.id, NivelUbicacion.lugar));
  });

  test('la ubicación no es una variable del modelo', () {
    final entrada = File('assets/preproceso.json').readAsStringSync();
    for (final palabra in ['"lat', '"lon', 'municipio', 'id_lugar', 'distancia']) {
      expect(entrada.contains(palabra), isFalse, reason: palabra);
    }
  });
}
