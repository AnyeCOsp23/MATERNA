/// Botón de información (ⓘ) con un pulso suave que invita a tocarlo, y la ventana con la explicación.
library;

import 'package:flutter/material.dart';

import '../tema/tema_materna.dart';

/// ⓘ con un círculo que crece y se desvanece cada [periodo]. Deja de pulsar al tocarlo o tras [pulsos] veces
/// (para no distraer indefinidamente); con «reducir animaciones» queda quieto.
class BotonInfoPulso extends StatefulWidget {
  const BotonInfoPulso({
    super.key,
    required this.alTocar,
    this.tooltip = 'Más información',
    this.pulsos = 8,
    this.periodo = const Duration(milliseconds: 2200),
  });

  final VoidCallback alTocar;
  final String tooltip;
  final int pulsos;
  final Duration periodo;

  @override
  State<BotonInfoPulso> createState() => _EstadoBotonInfo();
}

class _EstadoBotonInfo extends State<BotonInfoPulso> with SingleTickerProviderStateMixin {
  late final _control = AnimationController(vsync: this, duration: widget.periodo);
  var _hechos = 0;
  var _iniciado = false;
  var _visto = false;

  @override
  void initState() {
    super.initState();
    _control.addStatusListener((estado) {
      if (estado == AnimationStatus.completed && !_visto && ++_hechos < widget.pulsos) _control.forward(from: 0);
    });
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_iniciado && !MediaQuery.of(context).disableAnimations) {
      _iniciado = true;
      _control.forward();
    }
  }

  @override
  void dispose() {
    _control.dispose();
    super.dispose();
  }

  void _tocar() {
    setState(() => _visto = true);
    _control.stop();
    widget.alTocar();
  }

  @override
  Widget build(BuildContext context) {
    final pulsando = !_visto && !MediaQuery.of(context).disableAnimations;
    return SizedBox(
      width: 44,
      height: 44,
      child: Stack(alignment: Alignment.center, children: [
        if (pulsando)
          AnimatedBuilder(
            animation: _control,
            builder: (context, _) {
              // el pulso ocupa el primer 60 % del periodo; el resto es pausa
              final p = (_control.value / .6).clamp(0.0, 1.0);
              final crecer = Curves.easeOutCubic.transform(p);
              return Opacity(
                opacity: _control.value >= .6 ? 0 : (1 - p) * .45,
                child: Transform.scale(
                  scale: .7 + .65 * crecer,
                  child: Container(
                    width: 34,
                    height: 34,
                    decoration: BoxDecoration(color: ColoresMaterna.ciruela500, shape: BoxShape.circle),
                  ),
                ),
              );
            },
          ),
        IconButton(
          key: const Key('boton-info'),
          tooltip: widget.tooltip,
          onPressed: _tocar,
          icon: Icon(Icons.info_outline_rounded, color: ColoresMaterna.ciruela900),
        ),
      ]),
    );
  }
}

/// Una idea de la ventana de información: ícono, título y explicación (en rojo si es una advertencia).
typedef PuntoInfo = (IconData icono, String titulo, String texto, bool advertencia);

/// Ventana emergente con la información que antes ocupaba el formulario.
Future<void> mostrarInfo(BuildContext context, {required String titulo, required IconData icono, required List<PuntoInfo> puntos}) =>
    showDialog<void>(
      context: context,
      builder: (context) {
        final rojo = estiloPorCategoria['Alto Riesgo']!.tinta;
        return AlertDialog(
          key: const Key('ventana-info'),
          backgroundColor: ColoresMaterna.tarjeta,
          surfaceTintColor: Colors.transparent,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
          titlePadding: const EdgeInsets.fromLTRB(22, 22, 22, 4),
          contentPadding: const EdgeInsets.fromLTRB(22, 10, 22, 4),
          title: Row(children: [
            Icon(icono, color: ColoresMaterna.ciruela900),
            const SizedBox(width: 10),
            Expanded(child: Text(titulo, style: TextStyle(fontWeight: FontWeight.w800, color: ColoresMaterna.tinta, fontSize: 18))),
          ]),
          content: SingleChildScrollView(
            child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
              for (final (icono, titulo, texto, advertencia) in puntos)
                Padding(
                  padding: const EdgeInsets.only(top: 12),
                  child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Container(
                      padding: const EdgeInsets.all(7),
                      decoration: BoxDecoration(
                        color: advertencia ? estiloPorCategoria['Alto Riesgo']!.fondo : ColoresMaterna.ciruela100,
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Icon(icono, size: 18, color: advertencia ? rojo : ColoresMaterna.ciruela900),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text(titulo, style: TextStyle(fontWeight: FontWeight.w700, color: advertencia ? rojo : ColoresMaterna.tinta)),
                        const SizedBox(height: 2),
                        Text(texto, style: TextStyle(color: advertencia ? rojo : ColoresMaterna.tintaSuave, height: 1.4)),
                      ]),
                    ),
                  ]),
                ),
            ]),
          ),
          actions: [
            TextButton(key: const Key('cerrar-info'), onPressed: () => Navigator.of(context).pop(), child: const Text('Entendido')),
          ],
        );
      },
    );
