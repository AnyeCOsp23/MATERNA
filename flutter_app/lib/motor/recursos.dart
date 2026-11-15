/// Todo lo que la app recibe del Módulo 1, cargado una vez: modelo, preprocesamiento, reglas y catálogo 3280.
library;

import 'dart:convert';

import 'package:flutter/foundation.dart' show compute;
import 'package:flutter/services.dart';

import 'catalogo_3280.dart';
import 'clasificador.dart';

/// Resultado completo de una evaluación (igual que clinical_rules.evaluar_riesgo_hibrido de Python):
///   1. signo crítico (PAS, PAD, convulsiones, proteinuria)  -> Alto Riesgo, origen 'regla_clinica';
///   2. signo de alarma obstétrico de la ruta 3280            -> Alto Riesgo, origen 'signo_alarma_3280';
///   3. si no, decide el modelo                               -> origen 'modelo_ml'.
class Evaluacion {
  const Evaluacion({
    required this.registro,
    required this.triaje,
    required this.alertas,
    required this.signosAlarma,
    required this.imputadas,
  });

  final Map<String, dynamic> registro;

  /// Sistema híbrido de la Fase 2 (modelo + 4 reglas críticas).
  final ResultadoTriaje triaje;
  final List<Alerta3280> alertas;

  /// Variables cuyo signo de alarma obstétrico eleva el triaje a Alto.
  final List<String> signosAlarma;

  /// Variables que faltaban y el modelo completó con la mediana (glucosa, FCF).
  final List<String> imputadas;

  int get clase => triaje.origen == 'modelo_ml' && signosAlarma.isNotEmpty ? 2 : triaje.clase;
  String get origen => triaje.origen == 'modelo_ml' && signosAlarma.isNotEmpty ? 'signo_alarma_3280' : triaje.origen;

  /// Alertas de los signos que elevaron el triaje (se muestran como motivo del semáforo).
  List<Alerta3280> get alertasQueEscalan => alertas.where((a) => signosAlarma.contains(a.variable)).toList();

  List<Alerta3280> get urgentes => alertas.where((a) => a.severidad == 'urgente').toList();

  /// Urgentes que NO elevaron el triaje (p. ej. exposición a violencias, que tiene su propia ruta).
  List<Alerta3280> get urgentesSinEscalar => urgentes.where((a) => !signosAlarma.contains(a.variable)).toList();
  List<Alerta3280> get noUrgentes => alertas.where((a) => a.severidad != 'urgente').toList();
}

class RecursosMaterna {
  RecursosMaterna({required this.clasificador, required this.catalogo, required this.reglas});

  factory RecursosMaterna.desdeTextos({
    required String preproceso,
    required String modelo,
    required String reglas,
    required String catalogo,
  }) =>
      RecursosMaterna(
        clasificador: ClasificadorMaterna.desdeTexto(preproceso, modelo, reglas),
        catalogo: Catalogo3280.desdeTexto(catalogo),
        reglas: jsonDecode(reglas) as Map<String, dynamic>,
      );

  /// Lee los JSON y arma el modelo en otro hilo (compute): son 918 KB y 300 árboles, y en un teléfono lento o en
  /// modo debug congelarían la pantalla de inicio unos segundos. En la web compute corre en el mismo hilo.
  static Future<RecursosMaterna> cargar() async => compute(_desdeLista, [
        await rootBundle.loadString('assets/preproceso.json'),
        await rootBundle.loadString('assets/modelo_rf.json'),
        await rootBundle.loadString('assets/reglas.json'),
        await rootBundle.loadString('assets/variables_3280.json'),
      ]);

  static RecursosMaterna _desdeLista(List<String> t) =>
      RecursosMaterna.desdeTextos(preproceso: t[0], modelo: t[1], reglas: t[2], catalogo: t[3]);

  final ClasificadorMaterna clasificador;
  final Catalogo3280 catalogo;
  final Map<String, dynamic> reglas;

  /// Mensaje legible de cada signo crítico (p. ej. 'pas_severa' -> 'Hipertensión severa: PAS ≥ 160 mmHg').
  String mensajeRegla(String id) =>
      ((reglas['reglas'] as List).firstWhere((r) => r['id'] == id) as Map)['mensaje'] as String;

  List<String> protocolo(String categoria) => List<String>.from((reglas['protocolo'] as Map)[categoria] as List);

  String get aviso => reglas['aviso'] as String;

  Evaluacion evaluar(Map<String, dynamic> registro) => Evaluacion(
        registro: registro,
        triaje: clasificador.evaluar(registro),
        alertas: catalogo.evaluarAlertas(registro),
        signosAlarma: catalogo.signosQueEscalan(registro),
        imputadas: [for (final v in ['glucosa_mgdl', 'fcf_bpm']) if (registro[v] == null) v],
      );
}
