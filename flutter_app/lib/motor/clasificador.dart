/// Motor de inferencia offline del Módulo 2: sistema híbrido Random Forest + reglas clínicas.
///
/// Traducción directa de `src/inferencia_json.py` (la referencia en Python puro). Lee solo los JSON
/// que entrega el Módulo 1 (`assets/preproceso.json`, `assets/modelo_rf.json`, `assets/reglas.json`)
/// y debe reproducir a scikit-learn: lo verifica `test/paridad_test.dart` con 200 casos.
///
/// Pasos, en el mismo orden que el pipeline entrenado:
///  1. Imputación de glucosa y FCF con la mediana del estrato área × trimestre (o la del área, o la
///     global), más los indicadores *_no_disponible.
///  2. RobustScaler en las 7 variables continuas: (x - centro) / escala.
///  3. One-Hot de área y quién atiende (una categoría desconocida queda en ceros).
///  4. Random Forest: cada árbol compara float32(x) <= umbral, como scikit-learn, y la probabilidad es
///     el promedio de las hojas de los 300 árboles.
///  5. Reglas clínicas: si hay un signo crítico, el resultado es Alto Riesgo aunque el modelo diga otra cosa.
library;

import 'dart:convert';
import 'dart:typed_data';

/// Redondea un double a float32 (scikit-learn convierte X a float32 antes de recorrer los árboles).
double aFloat32(double x) => (Float32List(1)..[0] = x)[0];

bool _esNulo(Object? v) => v == null || (v is double && v.isNaN);

double _aDouble(Object? v) => (v as num).toDouble();

class Arbol {
  Arbol(Map<String, dynamic> json)
      : variable = List<int>.from(json['variable'] as List),
        umbral = (json['umbral'] as List).map(_aDouble).toList(),
        izquierda = List<int>.from(json['izquierda'] as List),
        derecha = List<int>.from(json['derecha'] as List),
        hojas = (json['hojas'] as List).map((h) => (h as List).map(_aDouble).toList()).toList();

  final List<int> variable;
  final List<double> umbral;
  final List<int> izquierda;
  final List<int> derecha;

  /// En una hoja, `izquierda` guarda el índice de su vector de probabilidades.
  final List<List<double>> hojas;

  List<double> hoja(List<double> x32) {
    var nodo = 0;
    while (variable[nodo] >= 0) {
      nodo = x32[variable[nodo]] <= umbral[nodo] ? izquierda[nodo] : derecha[nodo];
    }
    return hojas[izquierda[nodo]];
  }
}

class ResultadoTriaje {
  const ResultadoTriaje({
    required this.probabilidades,
    required this.claseModelo,
    required this.clase,
    required this.categoria,
    required this.origen,
    required this.reglasActivadas,
  });

  /// Probabilidades del modelo por clase (Bajo, Medio, Alto), aunque decida una regla.
  final List<double> probabilidades;
  final int claseModelo;
  final int clase;
  final String categoria;

  /// 'regla_clinica' o 'modelo_ml'.
  final String origen;

  /// Identificadores de las reglas activadas (p. ej. 'pas_severa').
  final List<String> reglasActivadas;
}

class ClasificadorMaterna {
  ClasificadorMaterna(this.preproceso, Map<String, dynamic> modelo, this.reglas)
      : clases = List<String>.from(modelo['clases'] as List),
        version = modelo['version'] as String,
        sha256Joblib = modelo['sha256_joblib'] as String,
        arboles = (modelo['arboles'] as List).map((a) => Arbol(a as Map<String, dynamic>)).toList();

  /// Construye el clasificador a partir del texto de los tres JSON (en la app, desde rootBundle).
  factory ClasificadorMaterna.desdeTexto(String preproceso, String modelo, String reglas) => ClasificadorMaterna(
        jsonDecode(preproceso) as Map<String, dynamic>,
        jsonDecode(modelo) as Map<String, dynamic>,
        jsonDecode(reglas) as Map<String, dynamic>,
      );

  final Map<String, dynamic> preproceso;
  final Map<String, dynamic> reglas;
  final List<String> clases;
  final List<Arbol> arboles;
  final String version;
  final String sha256Joblib;

  Map<String, dynamic> get _imputacion => preproceso['imputacion'] as Map<String, dynamic>;

  List<String> get obligatorias => List<String>.from(preproceso['obligatorias'] as List);

  // ------------------------------------------------------------ preprocesamiento
  String? trimestre(num semanas) {
    for (final t in _imputacion['trimestres'] as List) {
      if ((t['desde_exclusivo'] as num) < semanas && semanas <= (t['hasta'] as num)) return t['nombre'] as String;
    }
    return null;
  }

  /// Valores de glucosa y FCF (imputados si faltan) y si faltaban.
  (Map<String, double>, Map<String, bool>) imputar(Map<String, dynamic> registro) {
    final area = '${registro['area_residencia']}';
    final tri = trimestre(registro['semanas_gestacion'] as num);
    final valores = <String, double>{};
    final faltantes = <String, bool>{};
    for (final col in List<String>.from(_imputacion['columnas'] as List)) {
      final v = registro[col];
      faltantes[col] = _esNulo(v);
      if (!faltantes[col]!) {
        valores[col] = _aDouble(v);
        continue;
      }
      final porEstrato = ((_imputacion['mediana_estrato'] as Map)[col] as Map)[area] as Map?;
      final porArea = (_imputacion['mediana_area'] as Map)[col] as Map;
      if (porEstrato != null && tri != null && porEstrato.containsKey(tri)) {
        valores[col] = _aDouble(porEstrato[tri]);
      } else if (porArea.containsKey(area)) {
        valores[col] = _aDouble(porArea[area]);
      } else {
        valores[col] = _aDouble((_imputacion['mediana_global'] as Map)[col]);
      }
    }
    return (valores, faltantes);
  }

  /// Las 17 variables de entrada del árbol, en el orden de preproceso.json.
  List<double> vector(Map<String, dynamic> registro) {
    for (final col in obligatorias) {
      if (_esNulo(registro[col])) throw ArgumentError('Falta la variable obligatoria: $col');
    }
    final (imputados, faltantes) = imputar(registro);
    final escalado = preproceso['escalado'] as Map<String, dynamic>;
    final columnas = List<String>.from(escalado['columnas'] as List);
    final centro = (escalado['centro'] as List).map(_aDouble).toList();
    final escala = (escalado['escala'] as List).map(_aDouble).toList();
    final x = <double>[];
    for (var i = 0; i < columnas.length; i++) {
      final v = imputados[columnas[i]] ?? _aDouble(registro[columnas[i]]);
      x.add((v - centro[i]) / escala[i]);
    }
    final indicadores = preproceso['indicadores'] as Map<String, dynamic>;
    for (final col in List<String>.from(preproceso['discretas'] as List)) {
      if (indicadores.containsKey(col)) {
        x.add(faltantes[indicadores[col]]! ? 1.0 : 0.0);
      } else {
        final v = registro[col];
        x.add((v is bool ? (v ? 1 : 0) : (v as num).toInt()).toDouble());
      }
    }
    for (final item in preproceso['one_hot'] as List) {
      final valor = registro[item['columna']];
      for (final cat in item['categorias'] as List) {
        x.add(valor == cat ? 1.0 : 0.0);
      }
    }
    return x;
  }

  // ------------------------------------------------------------ modelo
  List<double> probabilidades(List<double> x) {
    final x32 = x.map(aFloat32).toList();
    final total = List<double>.filled(clases.length, 0.0);
    for (final arbol in arboles) {
      final hoja = arbol.hoja(x32);
      for (var k = 0; k < total.length; k++) {
        total[k] += hoja[k];
      }
    }
    return total.map((t) => t / arboles.length).toList();
  }

  // ------------------------------------------------------------ reglas + resultado
  List<String> signosCriticos(Map<String, dynamic> registro) {
    final activadas = <String>[];
    for (final regla in reglas['reglas'] as List) {
      final v = registro[regla['variable']];
      if (_esNulo(v)) continue;
      if (regla['condicion'] == 'mayor_igual' && _aDouble(v) >= _aDouble(regla['umbral'])) {
        activadas.add(regla['id'] as String);
      } else if (regla['condicion'] == 'verdadero' && (v is bool ? v : (v as num) != 0)) {
        activadas.add(regla['id'] as String);
      }
    }
    return activadas;
  }

  /// Mismo resultado que clinical_rules.evaluar_riesgo_hibrido de Python.
  ResultadoTriaje evaluar(Map<String, dynamic> registro) {
    final proba = probabilidades(vector(registro));
    var claseModelo = 0;
    for (var k = 1; k < proba.length; k++) {
      if (proba[k] > proba[claseModelo]) claseModelo = k; // argmax: el primer máximo
    }
    final activadas = signosCriticos(registro);
    final clase = activadas.isEmpty ? claseModelo : reglas['clase_alto'] as int;
    return ResultadoTriaje(
      probabilidades: proba,
      claseModelo: claseModelo,
      clase: clase,
      categoria: clases[clase],
      origen: activadas.isEmpty ? 'modelo_ml' : 'regla_clinica',
      reglasActivadas: activadas,
    );
  }
}
