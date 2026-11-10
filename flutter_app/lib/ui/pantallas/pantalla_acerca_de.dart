/// Pestaña 4: acerca de MATERNA, el modelo que usa, sus límites y el deslinde médico.
library;

import 'package:flutter/material.dart';

import '../../datos/base_local.dart';
import '../../motor/recursos.dart';
import '../tema/tema_materna.dart';
import '../widgets/barra_flotante.dart';
import 'pantalla_triaje.dart' show atiende;

/// Debe coincidir con `version:` de pubspec.yaml (lo verifica una prueba).
const versionApp = '1.0.0';

const deslinde = 'Herramienta de apoyo al diagnóstico maternal; no reemplaza el criterio médico profesional.';

/// Gestante de control de rutina para medir la velocidad de la inferencia en este dispositivo.
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

class PantallaAcercaDe extends StatefulWidget {
  const PantallaAcercaDe({super.key, required this.recursos, required this.perfil, required this.alCerrarSesion});

  final RecursosMaterna recursos;
  final Perfil perfil;
  final VoidCallback alCerrarSesion;

  @override
  State<PantallaAcercaDe> createState() => _EstadoAcercaDe();
}

class _EstadoAcercaDe extends State<PantallaAcercaDe> {
  late final double _milisegundos = medirInferencia(widget.recursos);

  Widget _seccion(String titulo, IconData icono, List<Widget> hijos) => Card(
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Icon(icono, color: ColoresMaterna.ciruela700, size: 20),
              const SizedBox(width: 8),
              Text(titulo, style: const TextStyle(fontWeight: FontWeight.w700)),
            ]),
            const SizedBox(height: 10),
            ...hijos,
          ]),
        ),
      );

  Widget _dato(String etiqueta, String valor, {Key? key}) => Padding(
        padding: const EdgeInsets.only(top: 6),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Expanded(child: Text(etiqueta, style: const TextStyle(color: ColoresMaterna.tintaSuave))),
          const SizedBox(width: 12),
          Flexible(child: Text(valor, key: key, textAlign: TextAlign.right, style: const TextStyle(fontWeight: FontWeight.w600))),
        ]),
      );

  Widget _vineta(String texto) => Padding(
        padding: const EdgeInsets.only(top: 6),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('•  '),
          Expanded(child: Text(texto, style: const TextStyle(height: 1.4))),
        ]),
      );

  @override
  Widget build(BuildContext context) {
    final clasificador = widget.recursos.clasificador;
    final perfil = widget.perfil;
    return SafeArea(
      bottom: false,
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 760),
          child: ListView(padding: const EdgeInsets.fromLTRB(16, 16, 16, BarraFlotante.espacioInferior), children: [
            Row(children: [
              Image.asset('assets/logo_isotipo.webp', width: 52, height: 52),
              const SizedBox(width: 12),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  const Text('MATERNA',
                      style: TextStyle(fontSize: 26, fontWeight: FontWeight.w900, color: ColoresMaterna.ciruela900, letterSpacing: -.5)),
                  Text('Versión $versionApp · Módulo 2, aplicación de usuario final',
                      key: const Key('version-app'), style: const TextStyle(color: ColoresMaterna.tintaSuave)),
                ]),
              ),
            ]),
            const SizedBox(height: 16),
            Container(
              key: const Key('deslinde'),
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(color: ColoresMaterna.ciruela900, borderRadius: BorderRadius.circular(18)),
              child: const Row(children: [
                Icon(Icons.gavel_rounded, color: Colors.white),
                SizedBox(width: 12),
                Expanded(child: Text(deslinde, style: TextStyle(color: Colors.white, fontWeight: FontWeight.w700, height: 1.35))),
              ]),
            ),
            const SizedBox(height: 14),
            _seccion('Operador', Icons.badge_outlined, [
              _dato('Quién atiende', atiende[perfil.atendidoPor] ?? perfil.atendidoPor),
              _dato('IPS o puesto de salud', perfil.ips),
              if (perfil.municipio != null) _dato('Municipio', perfil.municipio!),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                key: const Key('cerrar-sesion'),
                onPressed: widget.alCerrarSesion,
                icon: const Icon(Icons.lock_outline_rounded),
                label: const Text('Cerrar sesión'),
              ),
            ]),
            const SizedBox(height: 14),
            _seccion('Modelo', Icons.hub_outlined, [
              _dato('Sistema', 'Random Forest + reglas clínicas'),
              _dato('Versión del modelo', clasificador.version, key: const Key('version-modelo')),
              _dato('Árboles', '${clasificador.arboles.length}'),
              _dato('Huella SHA-256 del modelo', '${clasificador.sha256Joblib.substring(0, 16)}…'),
              _dato('Inferencia en este dispositivo', '${_milisegundos.toStringAsFixed(2).replaceAll('.', ',')} ms',
                  key: const Key('velocidad')),
              const SizedBox(height: 10),
              const Text(
                'Entregado por el Módulo 1 (laboratorio de ML). La app reproduce a scikit-learn: 200 casos del modelo, '
                '160 de las alertas de la Resolución 3280 y la carga masiva del archivo de ejemplo de la IPS (fila por '
                'fila, con los mismos seudónimos) dan lo mismo en Python y en Dart (tolerancia 1e-6).',
                style: TextStyle(color: ColoresMaterna.tintaSuave, height: 1.4),
              ),
            ]),
            const SizedBox(height: 14),
            _seccion('Limitaciones', Icons.warning_amber_rounded, [
              _vineta('Entrenado con datos SINTÉTICOS calibrados con cifras del DANE y el INS: las métricas no son evidencia clínica.'),
              _vineta('Las reglas clínicas, los signos de alarma que elevan el triaje y los textos de protocolo deben validarse '
                  'con un especialista en ginecobstetricia.'),
              _vineta('Los datos se guardan en el dispositivo sin cifrar. El PIN de 4 dígitos protege el acceso casual, no los '
                  'archivos de la app.'),
              _vineta('La clave de la IPS para seudonimizar los documentos también se guarda sin cifrar en el dispositivo.'),
              _vineta('La sincronización es una simulación: no hay servidor y no se envía ningún dato.'),
              _vineta('Si se olvida el PIN, la app se reinicia y se pierden las evaluaciones guardadas.'),
            ]),
          ]),
        ),
      ),
    );
  }
}
