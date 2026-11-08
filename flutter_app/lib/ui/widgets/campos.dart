/// Campos del formulario de la gestante. Cada uno lleva la clave `campo-<variable>` (la usan las pruebas).
library;

import 'package:flutter/material.dart';

import '../tema/tema_materna.dart';

String _numero(double v) => v == v.roundToDouble() ? v.toInt().toString() : v.toString().replaceAll('.', ',');

class Etiqueta extends StatelessWidget {
  const Etiqueta(this.texto, {super.key, this.ayuda});

  final String texto;
  final String? ayuda;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 6),
        child: Text.rich(TextSpan(children: [
          TextSpan(text: texto, style: const TextStyle(fontWeight: FontWeight.w600, color: ColoresMaterna.tinta)),
          if (ayuda != null) TextSpan(text: '  $ayuda', style: const TextStyle(color: ColoresMaterna.tintaSuave, fontSize: 12.5)),
        ])),
      );
}

class TextoError extends StatelessWidget {
  const TextoError(this.error, {super.key});

  final String? error;

  @override
  Widget build(BuildContext context) => error == null
      ? const SizedBox.shrink()
      : Padding(
          padding: const EdgeInsets.only(top: 6, left: 4),
          child: Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error, fontSize: 12.5)),
        );
}

/// Número con su unidad y rango válido (del catálogo 3280). Con [sinDato] se puede marcar «Sin dato».
class CampoNumero extends StatelessWidget {
  const CampoNumero({
    super.key,
    required this.nombre,
    required this.etiqueta,
    required this.controlador,
    this.unidad,
    this.rango,
    this.error,
    this.decimal = false,
    this.sinDato,
    this.alCambiarSinDato,
  });

  final String nombre;
  final String etiqueta;
  final TextEditingController controlador;
  final String? unidad;
  final List<double>? rango;
  final String? error;
  final bool decimal;

  /// null: el campo no admite «Sin dato».
  final bool? sinDato;
  final ValueChanged<bool>? alCambiarSinDato;

  @override
  Widget build(BuildContext context) {
    final ayuda = rango == null ? null : '${_numero(rango![0])} a ${_numero(rango![1])}${unidad == null ? '' : ' $unidad'}';
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Etiqueta(etiqueta, ayuda: ayuda),
      Row(children: [
        Expanded(
          child: TextField(
            key: Key('campo-$nombre'),
            controller: controlador,
            enabled: sinDato != true,
            keyboardType: TextInputType.numberWithOptions(decimal: decimal),
            decoration: InputDecoration(
              suffixText: unidad,
              hintText: sinDato == true ? 'Sin dato' : null,
              errorText: error == null ? null : '',
              errorStyle: const TextStyle(height: 0, fontSize: 0),
            ),
          ),
        ),
        if (sinDato != null) ...[
          const SizedBox(width: 10),
          FilterChip(
            key: Key('sin-dato-$nombre'),
            label: const Text('Sin dato'),
            selected: sinDato!,
            onSelected: alCambiarSinDato,
            selectedColor: ColoresMaterna.ciruela100,
          ),
        ],
      ]),
      TextoError(error),
    ]);
  }
}

/// Opciones en botones segmentados (pocas opciones). [valor] null = ninguna elegida todavía.
class CampoOpciones<T extends Object> extends StatelessWidget {
  const CampoOpciones({
    super.key,
    required this.nombre,
    required this.etiqueta,
    required this.opciones,
    required this.valor,
    required this.alCambiar,
    this.error,
    this.ayuda,
  });

  final String nombre;
  final String etiqueta;
  final Map<T, String> opciones;
  final T? valor;
  final ValueChanged<T?> alCambiar;
  final String? error;
  final String? ayuda;

  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Etiqueta(etiqueta, ayuda: ayuda),
        SizedBox(
          width: double.infinity,
          child: SegmentedButton<T>(
            key: Key('campo-$nombre'),
            segments: [for (final e in opciones.entries) ButtonSegment(value: e.key, label: Text(e.value))],
            selected: valor == null ? <T>{} : {valor as T},
            emptySelectionAllowed: true,
            showSelectedIcon: false,
            onSelectionChanged: (s) => alCambiar(s.isEmpty ? null : s.first),
          ),
        ),
        TextoError(error),
      ]);
}

/// Respuesta Sí / No / Sin dato. «Sin dato» es el estado inicial y nunca dispara una alerta:
/// un interruptor apagado registraría un «No» que nadie afirmó.
class CampoTresEstados extends StatelessWidget {
  const CampoTresEstados({super.key, required this.nombre, required this.etiqueta, required this.valor, required this.alCambiar});

  final String nombre;
  final String etiqueta;
  final bool? valor;
  final ValueChanged<bool?> alCambiar;

  @override
  Widget build(BuildContext context) => CampoOpciones<String>(
        nombre: nombre,
        etiqueta: etiqueta,
        opciones: const {'si': 'Sí', 'no': 'No', 'sd': 'Sin dato'},
        valor: switch (valor) { true => 'si', false => 'no', null => 'sd' },
        alCambiar: (v) => alCambiar(switch (v) { 'si' => true, 'no' => false, _ => null }),
      );
}

/// Lista desplegable (muchas opciones).
class CampoLista extends StatelessWidget {
  const CampoLista({
    super.key,
    required this.nombre,
    required this.etiqueta,
    required this.opciones,
    required this.valor,
    required this.alCambiar,
    this.error,
  });

  final String nombre;
  final String etiqueta;
  final Map<String, String> opciones;
  final String? valor;
  final ValueChanged<String?> alCambiar;
  final String? error;

  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Etiqueta(etiqueta),
        DropdownButtonFormField<String>(
          key: Key('campo-$nombre'),
          initialValue: valor,
          isExpanded: true,
          hint: const Text('Elegir'),
          items: [for (final e in opciones.entries) DropdownMenuItem(value: e.key, child: Text(e.value))],
          onChanged: alCambiar,
          borderRadius: BorderRadius.circular(16),
        ),
        TextoError(error),
      ]);
}
