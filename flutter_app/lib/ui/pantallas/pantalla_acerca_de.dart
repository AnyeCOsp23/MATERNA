/// Pestaña 4: acerca de MATERNA, lo que permite hacer, el uso responsable y el deslinde médico.
///
/// Es para el personal de salud: no muestra datos técnicos del modelo (versión, árboles, huella, velocidad). Esa
/// ficha está en el Módulo 1 («Publicar al Módulo 2») y en la documentación del sistema.
library;

import 'package:flutter/material.dart';

import '../../datos/base_local.dart';
import '../../motor/recursos.dart';
import '../tema/tema_materna.dart';
import '../widgets/ambito_preferencias.dart';
import '../widgets/avatar.dart';
import '../widgets/barra_flotante.dart';
import '../widgets/encabezado.dart';
import '../widgets/iconos_trazo.dart';
import 'pantalla_triaje.dart' show atiende;

/// Debe coincidir con `version:` de pubspec.yaml (lo verifica una prueba).
const versionApp = '1.0.0';

const deslinde = 'Herramienta de apoyo al diagnóstico maternal; no reemplaza el criterio médico profesional.';

/// Lo que la app permite hacer al personal de salud (ícono, título, explicación).
const funciones = [
  (Icons.monitor_heart_outlined, 'Evaluar a la gestante',
      'Registre los datos del control (edad, semanas, tensión arterial, frecuencia cardiaca fetal, glucosa y otros) '
          'y obtenga en segundos el nivel de riesgo: Bajo, Medio o Alto.'),
  (Icons.troubleshoot_rounded, 'Identificar factores de riesgo y signos de alarma',
      'Señala los hallazgos que explican el nivel y los signos de alarma de la ruta materno-perinatal '
          '(Resolución 3280 de 2018), como cefalea intensa, sangrado o disminución de los movimientos fetales.'),
  (Icons.alt_route_rounded, 'Orientar la conducta',
      'Para cada nivel sugiere qué hacer, desde el control prenatal de rutina hasta la remisión inmediata.'),
  (Icons.upload_file_rounded, 'Priorizar los listados de la IPS',
      'Cargue el archivo de la IPS y vea a todas las gestantes ordenadas de mayor a menor prioridad, sin guardar '
          'sus documentos de identidad.'),
  (Icons.history_rounded, 'Hacer seguimiento',
      'Consulte las evaluaciones anteriores por fecha, nivel de riesgo o documento para acompañar la evolución de '
          'cada gestante.'),
  (Icons.wifi_off_rounded, 'Trabajar sin conexión',
      'Funciona sin internet, pensada para zonas rurales y dispersas de La Guajira y el Cesar.'),
];

class PantallaAcercaDe extends StatefulWidget {
  const PantallaAcercaDe({super.key, required this.recursos, required this.perfil, required this.alCerrarSesion});

  final RecursosMaterna recursos;
  final Perfil perfil;
  final VoidCallback alCerrarSesion;

  @override
  State<PantallaAcercaDe> createState() => _EstadoAcercaDe();
}

class _EstadoAcercaDe extends State<PantallaAcercaDe> {
  Widget _funcion(IconData icono, String titulo, String texto) => Padding(
        padding: const EdgeInsets.only(top: 10),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(color: ColoresMaterna.ciruela100, borderRadius: BorderRadius.circular(12)),
            child: Icon(icono, color: ColoresMaterna.ciruela900, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(titulo, style: TextStyle(fontWeight: FontWeight.w700, color: ColoresMaterna.tinta)),
              const SizedBox(height: 2),
              Text(texto, style: TextStyle(color: ColoresMaterna.tintaSuave, height: 1.4)),
            ]),
          ),
        ]),
      );

  Widget _seccion(String titulo, IconData icono, List<Widget> hijos) => Card(
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Icon(icono, color: ColoresMaterna.ciruela900, size: 20),
              const SizedBox(width: 8),
              Text(titulo, style: TextStyle(fontWeight: FontWeight.w800, color: ColoresMaterna.tinta)),
            ]),
            const SizedBox(height: 10),
            ...hijos,
          ]),
        ),
      );

  Widget _dato(String etiqueta, String valor, {Key? key}) => Padding(
        padding: const EdgeInsets.only(top: 6),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Expanded(child: Text(etiqueta, style: TextStyle(color: ColoresMaterna.tintaSuave))),
          const SizedBox(width: 12),
          Flexible(child: Text(valor, key: key, textAlign: TextAlign.right, style: const TextStyle(fontWeight: FontWeight.w600))),
        ]),
      );

  Widget _vineta(String texto, {String? clave}) => Padding(
        key: clave == null ? null : Key(clave),
        padding: const EdgeInsets.only(top: 6),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('•  '),
          Expanded(child: Text(texto, style: const TextStyle(height: 1.4))),
        ]),
      );

  @override
  Widget build(BuildContext context) {
    final perfil = widget.perfil;
    return SafeArea(
      bottom: false,
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 760),
          child: ListView(padding: const EdgeInsets.fromLTRB(16, 8, 16, BarraFlotante.espacioInferior), children: [
            const EncabezadoMaterna(etiqueta: 'Información'),
            const SizedBox(height: 14),
            TituloConIcono(
              icono: IconoDeTrazo(IconoTrazo.informacion, color: ColoresMaterna.ciruela900, tamano: 26),
              titulo: 'Acerca de',
              subtitulo: 'Versión $versionApp · Apoyo al triaje del riesgo materno',
            ),
            const SizedBox(height: 16),
            Container(
              key: const Key('deslinde'),
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                gradient: LinearGradient(colors: [ColoresMaterna.vino, ColoresMaterna.ciruelaNoche]),
                borderRadius: BorderRadius.circular(20),
              ),
              child: const Row(children: [
                Icon(Icons.gavel_rounded, color: Colors.white),
                SizedBox(width: 12),
                Expanded(child: Text(deslinde, style: TextStyle(color: Colors.white, fontWeight: FontWeight.w700, height: 1.35))),
              ]),
            ),
            const SizedBox(height: 14),
            _seccion('Qué le permite hacer MATERNA', Icons.volunteer_activism_outlined, [
              for (final (icono, titulo, texto) in funciones) _funcion(icono, titulo, texto),
            ]),
            const SizedBox(height: 14),
            _seccion('Operador', Icons.badge_outlined, [
              Row(children: [
                AvatarCirculo(perfil.avatar, tamano: 44),
                const SizedBox(width: 12),
                Expanded(child: Text('Avatar: ${avatares[perfil.avatar.clamp(0, avatares.length - 1)].nombre}', style: TextStyle(color: ColoresMaterna.tintaSuave))),
              ]),
              const SizedBox(height: 10),
              if (perfil.usuario != null) _dato('Usuario', perfil.usuario!, key: const Key('usuario-sesion')),
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
            if (AmbitoPreferencias.de(context) case final preferencias?) ...[
              const SizedBox(height: 14),
              _seccion('Ajustes de este dispositivo', Icons.tune_rounded, [
                SwitchListTile(
                  key: const Key('ajuste-letra-grande'),
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Letra más grande'),
                  value: preferencias.letraGrande,
                  onChanged: preferencias.fijarLetraGrande,
                ),
                SwitchListTile(
                  key: const Key('ajuste-reducir-animaciones'),
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Reducir animaciones'),
                  value: preferencias.reducirAnimaciones,
                  onChanged: preferencias.fijarReducirAnimaciones,
                ),
                SwitchListTile(
                  key: const Key('ajuste-vibrar'),
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Vibrar con Alto Riesgo'),
                  value: preferencias.vibrarAlto,
                  onChanged: preferencias.fijarVibrarAlto,
                ),
                SwitchListTile(
                  key: const Key('ajuste-modo-oscuro'),
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Modo oscuro'),
                  subtitle: Text('Colores oscuros, más cómodos de noche', style: TextStyle(color: ColoresMaterna.tintaSuave)),
                  secondary: Icon(ColoresMaterna.oscuro ? Icons.dark_mode_rounded : Icons.dark_mode_outlined, color: ColoresMaterna.ciruela900),
                  value: preferencias.modoOscuro,
                  onChanged: preferencias.fijarModoOscuro,
                ),
                const SizedBox(height: 6),
                OutlinedButton.icon(
                  key: const Key('ver-presentacion'),
                  onPressed: () async {
                    await preferencias.verPresentacionDeNuevo();
                    if (context.mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(content: Text('La presentación se mostrará la próxima vez que abra MATERNA.')));
                    }
                  },
                  icon: const Icon(Icons.slideshow_rounded),
                  label: const Text('Ver la presentación otra vez'),
                ),
              ]),
            ],
            const SizedBox(height: 14),
            _seccion('Uso responsable', Icons.warning_amber_rounded, [
              _vineta('MATERNA está en etapa de prueba: se construyó con datos simulados de la región y todavía no se ha '
                  'validado en la atención real de gestantes.'),
              _vineta('Los criterios de alerta y la conducta sugerida deben ser revisados por un especialista en '
                  'ginecobstetricia. La decisión final siempre es del profesional de salud.'),
              _vineta('La información se guarda solo en este dispositivo y sin cifrar. El PIN evita que otras personas que '
                  'usan el dispositivo vean sus evaluaciones: proteja también el teléfono con su bloqueo y cierre sesión '
                  'al terminar.'),
              _vineta('En «Mapa y visitas», los límites de los municipios y las cabeceras son del DANE; las rancherías, '
                  'veredas y resguardos del mapa son lugares de prueba con nombres genéricos. Las distancias son en línea '
                  'recta y el mapa funciona sin internet.', clave: 'acerca-mapa-prueba'),
              _vineta('La clave de la IPS también queda en el dispositivo; compártala solo con personal autorizado.'),
              _vineta('«Sincronizar» todavía no envía datos a ningún servidor: es una función de demostración.'),
              _vineta('Si olvida el PIN, puede crear uno nuevo con su código de recuperación o con la clave de la IPS; '
                  'eliminar la cuenta es el último recurso y borra sus evaluaciones.'),
            ]),
          ]),
        ),
      ),
    );
  }
}
