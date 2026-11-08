// Paridad de las alertas de la ruta 3280 con Python: los casos de assets/casos_alertas.json, generados por
// src/exportar_a_dart.py con evaluar_alertas_3280. Deben coincidir las alertas y su orden.
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:materna/motor/catalogo_3280.dart';

String leer(String nombre) => File('assets/$nombre').readAsStringSync();

void main() {
  final catalogo = Catalogo3280.desdeTexto(leer('variables_3280.json'));
  final casos = ((jsonDecode(leer('casos_alertas.json')) as Map)['casos'] as List).cast<Map<String, dynamic>>();

  test('el catálogo trae las decisiones de la 3280', () {
    expect(catalogo.variables.length, 71);
    expect(catalogo.porDecision('modelo').length, 11);
    expect(catalogo.porDecision('auditoria').map((v) => v.nombre), containsAll(['pertenencia_etnica', 'municipio']));
    expect(catalogo.variable('hemoglobina_gdl')!.alerta!.umbral, 11);
    expect(catalogo.variable('ptog_ayunas_mgdl')!.porValidar, isTrue);
  });

  group('paridad de alertas con Python', () {
    for (final caso in casos) {
      test('caso ${caso['id']}', () {
        final obtenidas = catalogo.evaluarAlertas(Map<String, dynamic>.from(caso['entrada'] as Map));
        final esperadas = (caso['alertas'] as List).cast<Map<String, dynamic>>();
        expect(obtenidas.map((a) => a.variable).toList(), esperadas.map((a) => a['variable']).toList());
        for (var i = 0; i < esperadas.length; i++) {
          expect(obtenidas[i].severidad, esperadas[i]['severidad']);
          expect(obtenidas[i].mensaje, esperadas[i]['mensaje']);
          expect(obtenidas[i].verificada, esperadas[i]['verificada']);
        }
      });
    }
  });

  group('tres estados: Sí, No y Sin dato', () {
    test('«Sin dato» nunca alerta, ni siquiera un pendiente', () {
      expect(catalogo.evaluarAlertas({'semanas_gestacion': 30, 'calcio': null, 'cefalea': null}), isEmpty);
    });
    test('solo un «No» explícito marca el calcio como pendiente', () {
      expect(catalogo.evaluarAlertas({'semanas_gestacion': 30, 'calcio': false}).single.variable, 'calcio');
      expect(catalogo.evaluarAlertas({'semanas_gestacion': 30, 'calcio': true}), isEmpty);
    });
    test('las urgentes van primero', () {
      final alertas = catalogo.evaluarAlertas({'hemoglobina_gdl': 9, 'sangrado_genital': true, 'semanas_gestacion': 20, 'calcio': false});
      expect(alertas.map((a) => a.severidad), ['urgente', 'atencion', 'seguimiento']);
    });
  });
}
