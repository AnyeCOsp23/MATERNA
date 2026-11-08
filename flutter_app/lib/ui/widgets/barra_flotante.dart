/// Barra de navegación flotante y redondeada (estilo iOS): blanca, suspendida sobre el contenido, con márgenes
/// y una sombra suave. Iconos de contorno fino en gris; la pestaña activa se marca con una píldora rosa claro
/// y el icono en ciruela. El nombre de cada pestaña va como descripción accesible y en el tooltip.
library;

import 'package:flutter/material.dart';

import '../tema/tema_materna.dart';

/// Dibuja el icono de una pestaña con el color que corresponde a su estado.
typedef ConstructorIcono = Widget Function(Color color);

class DestinoBarra {
  const DestinoBarra({required this.icono, required this.etiqueta});

  final ConstructorIcono icono;
  final String etiqueta;
}

const _gris = Color(0xFF8A8487);
const _rosaActivo = Color(0xFFF7DCE7);

class BarraFlotante extends StatelessWidget {
  const BarraFlotante({super.key, required this.destinos, required this.indice, required this.alCambiar});

  final List<DestinoBarra> destinos;
  final int indice;
  final ValueChanged<int> alCambiar;

  /// Alto que ocupa la barra con su margen inferior: el contenido debe dejar este espacio libre al final.
  static const espacioInferior = 100.0;

  @override
  Widget build(BuildContext context) => SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 20),
          child: Center(
            heightFactor: 1,
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 440),
              child: DecoratedBox(
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(30),
                  boxShadow: const [
                    BoxShadow(color: Color(0x1F3A1F30), blurRadius: 26, offset: Offset(0, 10)),
                    BoxShadow(color: Color(0x0D000000), blurRadius: 4, offset: Offset(0, 1)),
                  ],
                ),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(30),
                  child: Material(
                    color: Colors.white,
                    child: Padding(
                      padding: const EdgeInsets.all(8),
                      child: Row(children: [
                        for (final (i, d) in destinos.indexed)
                          Expanded(child: _Item(destino: d, activo: i == indice, alTocar: () => alCambiar(i), indice: i)),
                      ]),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      );
}

class _Item extends StatelessWidget {
  const _Item({required this.destino, required this.activo, required this.alTocar, required this.indice});

  final DestinoBarra destino;
  final bool activo;
  final VoidCallback alTocar;
  final int indice;

  @override
  Widget build(BuildContext context) => Semantics(
        button: true,
        selected: activo,
        label: destino.etiqueta,
        excludeSemantics: true,
        child: Tooltip(
          message: destino.etiqueta,
          child: InkWell(
            key: Key('pestana-$indice'),
            borderRadius: BorderRadius.circular(24),
            onTap: alTocar,
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 280),
              curve: const Cubic(.32, .72, 0, 1), // la misma curva de la consola web
              height: 50,
              margin: const EdgeInsets.symmetric(horizontal: 2),
              decoration: BoxDecoration(
                color: activo ? _rosaActivo : Colors.transparent,
                borderRadius: BorderRadius.circular(25),
              ),
              alignment: Alignment.center,
              child: destino.icono(activo ? ColoresMaterna.ciruela900 : _gris),
            ),
          ),
        ),
      );
}
