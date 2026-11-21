/// Todo lo que la app recibe del Módulo 1, cargado una vez: modelo, preprocesamiento, reglas y catálogo 3280.
library;

import 'dart:convert';

import 'package:flutter/foundation.dart' show compute;
import 'package:flutter/services.dart';

import 'catalogo_3280.dart';
import 'clasificador.dart';
import 'geografia.dart';

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
  RecursosMaterna({required this.clasificador, required this.catalogo, required this.reglas, this.geografia});

  factory RecursosMaterna.desdeTextos({
    required String preproceso,
    required String modelo,
    required String reglas,
    required String catalogo,
    Geografia? geografia,
  }) =>
      RecursosMaterna(
        clasificador: ClasificadorMaterna.desdeTexto(preproceso, modelo, reglas),
        catalogo: Catalogo3280.desdeTexto(catalogo),
        reglas: jsonDecode(reglas) as Map<String, dynamic>,
        geografia: geografia,
      );

  /// Lee los JSON y arma el modelo en otro hilo (compute): son 918 KB y 300 árboles, y en un teléfono lento o en
  /// modo debug congelarían la pantalla de inicio unos segundos. En la web compute corre en el mismo hilo.
  static Future<RecursosMaterna> cargar() async => compute(_desdeLista, [
        await rootBundle.loadString('assets/preproceso.json'),
        await rootBundle.loadString('assets/modelo_rf.json'),
        await rootBundle.loadString('assets/reglas.json'),
        await rootBundle.loadString('assets/variables_3280.json'),
        await rootBundle.loadString('assets/geo/municipios_guajira_cesar.geojson'),
        await rootBundle.loadString('assets/geo/cabeceras_guajira_cesar.json'),
        await rootBundle.loadString('assets/geo/puntos_concentracion.json'),
      ]);

  static RecursosMaterna _desdeLista(List<String> t) => RecursosMaterna.desdeTextos(
      preproceso: t[0], modelo: t[1], reglas: t[2], catalogo: t[3],
      geografia: Geografia.desdeTextos(municipios: t[4], cabeceras: t[5], puntos: t[6]));

  final ClasificadorMaterna clasificador;
  final Catalogo3280 catalogo;
  final Map<String, dynamic> reglas;

  /// Municipios, cabeceras y puntos de concentración para ubicar a las gestantes (null en pruebas que no la usan).
  final Geografia? geografia;

  /// Mensaje legible de cada signo crítico (p. ej. 'pas_severa' -> 'Hipertensión severa: PAS ≥ 160 mmHg').
  String mensajeRegla(String id) =>
      ((reglas['reglas'] as List).firstWhere((r) => r['id'] == id) as Map)['mensaje'] as String;

  List<String> protocolo(String categoria) => List<String>.from((reglas['protocolo'] as Map)[categoria] as List);

  String get aviso => reglas['aviso'] as String;

  /// Motivo del nivel en lenguaje claro, sin términos técnicos: los signos críticos o de alarma que lo
  /// decidieron o, si no hubo ninguno, que el nivel sale de la combinación de los datos de la gestante.
  String motivo(Evaluacion e) => switch (e.origen) {
        'regla_clinica' => [for (final id in e.triaje.reglasActivadas) mensajeRegla(id)].join('; '),
        'signo_alarma_3280' => [for (final a in e.alertasQueEscalan) a.etiqueta].join('; '),
        _ when e.clase > 0 => 'Combinación de factores de riesgo',
        _ => e.alertas.isEmpty ? 'Sin signos críticos ni de alarma' : 'Sin signos críticos',
      };

  Evaluacion evaluar(Map<String, dynamic> registro) => Evaluacion(
        registro: registro,
        triaje: clasificador.evaluar(registro),
        alertas: catalogo.evaluarAlertas(registro),
        signosAlarma: catalogo.signosQueEscalan(registro),
        imputadas: [for (final v in ['glucosa_mgdl', 'fcf_bpm']) if (registro[v] == null) v],
      );
}

/// Gestante de control de rutina para medir la velocidad de la inferencia (no se muestra en la app: la ficha
/// técnica del modelo está en el Módulo 1; lo verifica `test/datos_test.dart`).
const _registroPrueba = {
  'edad': 27, 'area_residencia': 'Cabecera', 'semanas_gestacion': 28, 'n_controles_prenatales': 5,
  'atendido_por': 'Medico', 'pas_mmhg': 110, 'pad_mmhg': 70, 'fcf_bpm': 142.0, 'glucosa_mgdl': 88.0,
  'proteinuria': 0, 'convulsiones': 0,
};

/// Milisegundos promedio de una evaluación completa (modelo, reglas y alertas).
double medirInferencia(RecursosMaterna recursos, {int repeticiones = 50}) {
  recursos.evaluar(_registroPrueba); // calentamiento
  final reloj = Stopwatch()..start();
  for (var i = 0; i < repeticiones; i++) {
    recursos.evaluar(_registroPrueba);
  }
  return reloj.elapsedMicroseconds / repeticiones / 1000;
}
