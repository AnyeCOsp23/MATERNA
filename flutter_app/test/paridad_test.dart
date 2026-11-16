// Paridad del motor Dart con scikit-learn: los 200 casos de assets/casos_paridad.json, generados por
// src/exportar_a_dart.py con la respuesta exacta del pipeline de Python. Tolerancia 1e-6.
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:materna/motor/clasificador.dart';

String leer(String nombre) => File('assets/$nombre').readAsStringSync();

void main() {
  final clf = ClasificadorMaterna.desdeTexto(leer('preproceso.json'), leer('modelo_rf.json'), leer('reglas.json'));
  final paridad = jsonDecode(leer('casos_paridad.json')) as Map<String, dynamic>;
  final tolerancia = (paridad['tolerancia'] as num).toDouble();
  final casos = (paridad['casos'] as List).cast<Map<String, dynamic>>();

  // Lo que declara el modelo publicado (v1 oficial u otra versión): las pruebas no dependen de cuál sea
  final modeloJson = jsonDecode(leer('modelo_rf.json')) as Map<String, dynamic>;
  final imputacion = (jsonDecode(leer('preproceso.json')) as Map<String, dynamic>)['imputacion'] as Map<String, dynamic>;

  test('los JSON corresponden al modelo exportado', () {
    expect(clf.arboles.length, modeloJson['n_arboles']);
    expect(clf.arboles, isNotEmpty);
    expect(clf.version, modeloJson['version']);
    expect(clf.clases, ['Bajo Riesgo', 'Riesgo Medio', 'Alto Riesgo']);
    expect(clf.sha256Joblib.length, 64);
    expect(casos.length, 200);
  });

  test('float32 como scikit-learn', () {
    expect(aFloat32(0.1), isNot(0.1));
    expect(aFloat32(0.5), 0.5);
  });

  group('paridad con scikit-learn', () {
    for (final caso in casos) {
      test('caso ${caso['id']}', () {
        final entrada = Map<String, dynamic>.from(caso['entrada'] as Map);
        final x = clf.vector(entrada);
        final esperadoX = (caso['variables_entrada'] as List).map((v) => (v as num).toDouble()).toList();
        expect(x.length, esperadoX.length);
        for (var i = 0; i < x.length; i++) {
          expect((x[i] - esperadoX[i]).abs(), lessThanOrEqualTo(tolerancia), reason: 'variable $i');
        }
        final r = clf.evaluar(entrada);
        final esperadoP = (caso['probabilidades'] as List).map((v) => (v as num).toDouble()).toList();
        for (var k = 0; k < 3; k++) {
          expect((r.probabilidades[k] - esperadoP[k]).abs(), lessThanOrEqualTo(tolerancia), reason: 'clase $k');
        }
        expect(r.claseModelo, caso['clase_modelo']);
        expect(r.clase, caso['clase']);
        expect(r.origen, caso['origen']);
        expect(r.reglasActivadas.length, caso['n_signos_criticos']);
      });
    }
  });

  group('reglas e imputación', () {
    Map<String, dynamic> sana() => {
          'edad': 27, 'area_residencia': 'Cabecera', 'semanas_gestacion': 28, 'n_controles_prenatales': 5,
          'atendido_por': 'Medico', 'pas_mmhg': 110, 'pad_mmhg': 70, 'fcf_bpm': 142.0, 'glucosa_mgdl': 88.0,
          'proteinuria': 0, 'convulsiones': 0,
        };

    test('un signo crítico da Alto Riesgo por regla', () {
      for (final cambio in [
        {'pas_mmhg': 160}, {'pad_mmhg': 110}, {'proteinuria': 2}, {'convulsiones': 1}, {'convulsiones': true},
      ]) {
        final r = clf.evaluar({...sana(), ...cambio});
        expect(r.categoria, 'Alto Riesgo', reason: '$cambio');
        expect(r.origen, 'regla_clinica');
      }
      expect(clf.evaluar({...sana(), 'pas_mmhg': 159}).origen, 'modelo_ml');
    });

    test('glucosa faltante se imputa con la mediana del estrato', () {
      final (valores, faltantes) = clf.imputar({...sana(), 'area_residencia': 'Rural disperso', 'semanas_gestacion': 10, 'glucosa_mgdl': null});
      // la mediana que aprendió el modelo publicado: estrato área × trimestre o, si tenía pocos datos, área o global
      final esperada = ((imputacion['mediana_estrato'] as Map)['glucosa_mgdl'] as Map)['Rural disperso']?['T1'] ??
          ((imputacion['mediana_area'] as Map)['glucosa_mgdl'] as Map)['Rural disperso'] ??
          (imputacion['mediana_global'] as Map)['glucosa_mgdl'];
      expect(valores['glucosa_mgdl'], closeTo((esperada as num).toDouble(), 1e-9));
      expect(faltantes['glucosa_mgdl'], isTrue);
    });

    test('falta una variable obligatoria', () {
      expect(() => clf.vector({...sana(), 'edad': null}), throwsArgumentError);
    });
  });
}
