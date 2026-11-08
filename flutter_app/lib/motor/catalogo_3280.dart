/// Catálogo de variables de la Resolución 3280 de 2018 y alertas de la ruta materno-perinatal.
///
/// Lee `assets/variables_3280.json`, copia exacta de `config/variables_3280.json` (la misma fuente que
/// usan el Módulo 1 y `src/filtro_3280.py`). La evaluación de alertas traduce `evaluar_alertas_3280` de
/// Python y debe dar las mismas alertas, en el mismo orden: lo verifica `test/alertas_test.dart`.
///
/// Las alertas de la ruta no entran al modelo. Los signos de alarma obstétricos («escala_a_alto» en el catálogo)
/// elevan el triaje FINAL a Alto Riesgo, como las reglas críticas: ver Evaluacion en recursos.dart.
library;

import 'dart:convert';

double? _aDoble(Object? v) {
  if (v == null) return null;
  if (v is bool) return v ? 1.0 : 0.0;
  final d = (v as num).toDouble();
  return d.isNaN ? null : d;
}

class ReglaAlerta {
  ReglaAlerta(Map<String, dynamic> json)
      : condicion = json['condicion'] as String,
        umbral = _aDoble(json['umbral']),
        severidad = json['severidad'] as String,
        mensaje = json['mensaje'] as String,
        escalaAAlto = json['escala_a_alto'] == true;

  /// 'verdadero', 'menor_que', 'mayor_igual' o 'pendiente_desde_semana'.
  final String condicion;
  final double? umbral;

  /// 'urgente', 'atencion' o 'seguimiento'.
  final String severidad;
  final String mensaje;

  /// Signo de alarma obstétrico: si se activa, el triaje final pasa a Alto Riesgo.
  final bool escalaAAlto;

  bool seCumple(double? valor, double? semanas) {
    if (condicion == 'pendiente_desde_semana') {
      // Se alerta si el suplemento o la vacuna NO se ha dado y ya pasó la semana indicada
      return semanas != null && semanas >= umbral! && valor == 0;
    }
    if (valor == null) return false;
    return switch (condicion) {
      'verdadero' => valor != 0,
      'menor_que' => valor < umbral!,
      'mayor_igual' => valor >= umbral!,
      _ => throw ArgumentError('Condición de alerta desconocida: $condicion'),
    };
  }
}

class VariableCatalogo {
  VariableCatalogo(Map<String, dynamic> json)
      : nombre = json['nombre'] as String,
        etiqueta = json['etiqueta'] as String,
        seccion = json['seccion'] as String,
        decision = json['decision'] as String,
        tipo = json['tipo'] as String,
        unidad = json['unidad'] as String?,
        rango = json['rango'] == null ? null : (json['rango'] as List).map((v) => (v as num).toDouble()).toList(),
        valores = json['valores'] == null ? const [] : List<String>.from(json['valores'] as List),
        justificacion = json['justificacion'] as String,
        verificacion = json['verificacion'] as String,
        alerta = json['alerta'] == null ? null : ReglaAlerta(json['alerta'] as Map<String, dynamic>);

  final String nombre;
  final String etiqueta;

  /// Sección del control prenatal en la ruta (Anamnesis, Examen físico, Paraclínicos…).
  final String seccion;

  /// 'modelo', 'capturar_alertar', 'auditoria', 'seudonimizar' o 'eliminar'.
  final String decision;

  /// 'entero', 'decimal', 'binaria', 'categorica', 'fecha' o 'texto'.
  final String tipo;
  final String? unidad;
  final List<double>? rango;
  final List<String> valores;
  final String justificacion;
  final String verificacion;
  final ReglaAlerta? alerta;

  /// El corte de la alerta es un criterio clínico que debe validar un asesor.
  bool get porValidar => verificacion == 'criterio_clinico_por_validar';
}

class Alerta3280 {
  const Alerta3280({
    required this.variable,
    required this.etiqueta,
    required this.severidad,
    required this.mensaje,
    required this.verificada,
  });

  final String variable;
  final String etiqueta;
  final String severidad;
  final String mensaje;

  /// false cuando el corte es un criterio clínico por validar.
  final bool verificada;
}

class Catalogo3280 {
  Catalogo3280(Map<String, dynamic> json)
      : variables = (json['variables'] as List).map((v) => VariableCatalogo(v as Map<String, dynamic>)).toList();

  factory Catalogo3280.desdeTexto(String texto) => Catalogo3280(jsonDecode(texto) as Map<String, dynamic>);

  final List<VariableCatalogo> variables;

  static const ordenSeveridad = ['urgente', 'atencion', 'seguimiento'];

  List<VariableCatalogo> porDecision(String decision) => variables.where((v) => v.decision == decision).toList();

  VariableCatalogo? variable(String nombre) {
    for (final v in variables) {
      if (v.nombre == nombre) return v;
    }
    return null;
  }

  /// Variables cuyo signo de alarma obstétrico se activa y eleva el triaje a Alto (igual que
  /// `signos_alarma_que_escalan` de Python).
  List<String> signosQueEscalan(Map<String, dynamic> registro) => [
        for (final a in evaluarAlertas(registro))
          if (variable(a.variable)?.alerta?.escalaAAlto ?? false) a.variable,
      ];

  /// Alertas de la ruta para un registro, de la más a la menos urgente (mismo orden que Python: por
  /// severidad y, dentro de cada severidad, en el orden del catálogo).
  List<Alerta3280> evaluarAlertas(Map<String, dynamic> registro) {
    final semanas = _aDoble(registro['semanas_gestacion']);
    final porSeveridad = {for (final s in ordenSeveridad) s: <Alerta3280>[]};
    for (final v in porDecision('capturar_alertar')) {
      final alerta = v.alerta;
      if (alerta == null || !registro.containsKey(v.nombre)) continue;
      if (alerta.seCumple(_aDoble(registro[v.nombre]), semanas)) {
        porSeveridad[alerta.severidad]!.add(Alerta3280(
          variable: v.nombre,
          etiqueta: v.etiqueta,
          severidad: alerta.severidad,
          mensaje: alerta.mensaje,
          verificada: !v.porValidar,
        ));
      }
    }
    return [for (final s in ordenSeveridad) ...porSeveridad[s]!];
  }
}
