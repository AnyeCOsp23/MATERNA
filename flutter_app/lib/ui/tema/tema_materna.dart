/// Identidad visual de MATERNA en la app (paleta de los mockups del Módulo 2).
///
/// Marca: vino #7B2D5B (botones, íconos y textos de marca), vino del logo #942255, rosa claro #F5D3E3 (pestaña
/// activa, íconos de título y botón secundario), fondo crema en degradado #F8F6EC -> #F0EEDD y blanco en tarjetas.
/// Semáforo: tarjeta en degradado, barra y aviso propios por nivel (rojo, ámbar y verde), siempre con texto: el
/// riesgo nunca se comunica solo con el color.
library;

import 'package:flutter/material.dart';

/// Paleta clara original, constante. La usan la presentación inicial (ilustración en pastel, siempre clara) y
/// [Paleta.claro].
abstract final class ColoresClaros {
  static const ciruela900 = Color(0xFF7B2D5B); // vino principal
  static const ciruela700 = Color(0xFFA54178);
  static const ciruela500 = Color(0xFFD8639B);
  static const ciruela100 = Color(0xFFF5D3E3); // rosa claro
  static const vinoLogo = Color(0xFF942255);
  static const ciruelaNoche = Color(0xFF5C1F45);
  static const crema = Color(0xFFF8F6EC);
  static const cremaFondo = Color(0xFFF0EEDD);
  static const tinta = Color(0xFF3A1230);
  static const tintaSuave = Color(0xFF6B4A5E);
  static const campo = Color(0xFFF6E8EF); // rosa de campos de texto
  static const borde = Color(0xFFEFE0E7);
  static const fondoProgreso = Color(0xFFE9D3DE);
  static const fondoBarras = Color(0xFFEFE0E7);
  static const sinConexionFondo = Color(0xFFE3F3E8);
  static const sinConexionTexto = Color(0xFF1B5E36);
  static const sinConexionPunto = Color(0xFF1B6B3A);
  static const alertaEdad = Color(0xFF8A4B00);
}

/// Colores de un modo (claro u oscuro).
class Paleta {
  const Paleta({
    required this.oscuro,
    required this.ciruela900,
    required this.ciruela700,
    required this.ciruela500,
    required this.ciruela100,
    required this.vinoLogo,
    required this.ciruelaNoche,
    required this.vino,
    required this.crema,
    required this.cremaFondo,
    required this.tarjeta,
    required this.tinta,
    required this.tintaSuave,
    required this.iconoInactivo,
    required this.campo,
    required this.borde,
    required this.fondoProgreso,
    required this.fondoBarras,
    required this.sinConexionFondo,
    required this.sinConexionTexto,
    required this.sinConexionPunto,
    required this.alertaEdad,
    required this.sombra,
  });

  final bool oscuro;

  /// Marca en textos, íconos y bordes (en oscuro, rosa claro para que se lea sobre el fondo).
  final Color ciruela900;
  final Color ciruela700;
  final Color ciruela500;

  /// Fondo rosado de pestañas activas, chips elegidos e íconos de título (en oscuro, ciruela profundo).
  final Color ciruela100;
  final Color vinoLogo;
  final Color ciruelaNoche;

  /// Fondo de botones y franjas de marca, siempre con texto blanco encima.
  final Color vino;
  final Color crema;
  final Color cremaFondo;

  /// Tarjetas, barra de navegación, ventanas y botones claros (blanco en el modo claro).
  final Color tarjeta;
  final Color tinta;
  final Color tintaSuave;
  final Color iconoInactivo;
  final Color campo;
  final Color borde;
  final Color fondoProgreso;
  final Color fondoBarras;
  final Color sinConexionFondo;
  final Color sinConexionTexto;
  final Color sinConexionPunto;
  final Color alertaEdad;
  final Color sombra;

  static const claro = Paleta(
    oscuro: false,
    ciruela900: ColoresClaros.ciruela900,
    ciruela700: ColoresClaros.ciruela700,
    ciruela500: ColoresClaros.ciruela500,
    ciruela100: ColoresClaros.ciruela100,
    vinoLogo: ColoresClaros.vinoLogo,
    ciruelaNoche: ColoresClaros.ciruelaNoche,
    vino: ColoresClaros.ciruela900,
    crema: ColoresClaros.crema,
    cremaFondo: ColoresClaros.cremaFondo,
    tarjeta: Colors.white,
    tinta: ColoresClaros.tinta,
    tintaSuave: ColoresClaros.tintaSuave,
    iconoInactivo: Color(0xFF8A8487),
    campo: ColoresClaros.campo,
    borde: ColoresClaros.borde,
    fondoProgreso: ColoresClaros.fondoProgreso,
    fondoBarras: ColoresClaros.fondoBarras,
    sinConexionFondo: ColoresClaros.sinConexionFondo,
    sinConexionTexto: ColoresClaros.sinConexionTexto,
    sinConexionPunto: ColoresClaros.sinConexionPunto,
    alertaEdad: ColoresClaros.alertaEdad,
    sombra: Color(0x143A1230),
  );

  /// Ciruela muy oscuro (no negro puro), con la marca en rosa y el vino en los botones.
  static const oscura = Paleta(
    oscuro: true,
    ciruela900: Color(0xFFEFA3C8),
    ciruela700: Color(0xFFE08AB4),
    ciruela500: Color(0xFFD8639B),
    ciruela100: Color(0xFF4A2840),
    vinoLogo: Color(0xFFEFA3C8),
    ciruelaNoche: Color(0xFF5C1F45),
    vino: Color(0xFFA8437A),
    crema: Color(0xFF1C1419),
    cremaFondo: Color(0xFF150F13),
    tarjeta: Color(0xFF271D24),
    tinta: Color(0xFFF6EAF0),
    tintaSuave: Color(0xFFC9B2BF),
    iconoInactivo: Color(0xFFA2949C),
    campo: Color(0xFF34262F),
    borde: Color(0xFF3E2E38),
    fondoProgreso: Color(0xFF3E2E38),
    fondoBarras: Color(0xFF3E2E38),
    sinConexionFondo: Color(0xFF173325),
    sinConexionTexto: Color(0xFF9EDDB6),
    sinConexionPunto: Color(0xFF5CC085),
    alertaEdad: Color(0xFFF0B35C),
    sombra: Color(0x66000000),
  );
}

/// Colores de la app en el modo activo. El modo lo fija `MaternaApp` (ajuste «Modo oscuro») y, al cambiarlo, la app
/// se redibuja entera sin perder la sesión.
abstract final class ColoresMaterna {
  static Paleta _p = Paleta.claro;

  static Paleta get paleta => _p;
  static bool get oscuro => _p.oscuro;
  static void usar({required bool oscuro}) => _p = oscuro ? Paleta.oscura : Paleta.claro;

  /// Ejecuta [f] con la paleta [p] y deja la que estaba (p. ej. para armar el tema claro de la presentación).
  static T con<T>(Paleta p, T Function() f) {
    final antes = _p;
    _p = p;
    try {
      return f();
    } finally {
      _p = antes;
    }
  }

  static Color get ciruela900 => _p.ciruela900;
  static Color get ciruela700 => _p.ciruela700;
  static Color get ciruela500 => _p.ciruela500;
  static Color get ciruela100 => _p.ciruela100;
  static Color get vinoLogo => _p.vinoLogo;
  static Color get ciruelaNoche => _p.ciruelaNoche;
  static Color get vino => _p.vino;
  static Color get crema => _p.crema;
  static Color get cremaFondo => _p.cremaFondo;
  static Color get tarjeta => _p.tarjeta;
  static Color get tinta => _p.tinta;
  static Color get tintaSuave => _p.tintaSuave;
  static Color get iconoInactivo => _p.iconoInactivo;
  static Color get campo => _p.campo;
  static Color get borde => _p.borde;
  static Color get fondoProgreso => _p.fondoProgreso;
  static Color get fondoBarras => _p.fondoBarras;
  static Color get sinConexionFondo => _p.sinConexionFondo;
  static Color get sinConexionTexto => _p.sinConexionTexto;
  static Color get sinConexionPunto => _p.sinConexionPunto;
  static Color get alertaEdad => _p.alertaEdad;
  static Color get sombra => _p.sombra;
}

/// Fondo crema de las pantallas (de arriba hacia abajo); en oscuro, ciruela muy oscuro.
BoxDecoration get fondoCrema => BoxDecoration(
      gradient: LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [ColoresMaterna.crema, ColoresMaterna.cremaFondo],
      ),
    );

class EstiloRiesgo {
  const EstiloRiesgo({
    required this.semaforo,
    required this.nivel,
    required this.corto,
    required this.titulo,
    required this.subtitulo,
    required this.degradado,
    required this.barra,
    required this.fondo,
    required this.tinta,
    required this.icono,
  });

  /// 'Rojo', 'Ámbar' o 'Verde'.
  final String semaforo;

  /// 'NIVEL ALTO', 'NIVEL MEDIO' o 'NIVEL BAJO'.
  final String nivel;

  /// 'Alto', 'Medio' o 'Bajo' (etiquetas de las listas).
  final String corto;
  final String titulo;
  final String subtitulo;

  /// Degradado de la tarjeta del resultado (texto blanco encima).
  final List<Color> degradado;

  /// Color de la barra de probabilidad y de los números del nivel.
  final Color barra;

  /// Fondo y texto de los avisos y etiquetas de este nivel.
  final Color fondo;
  final Color tinta;
  final IconData icono;
}

/// Por categoría del modelo, en el orden de las clases (Bajo, Medio, Alto), en el modo activo.
Map<String, EstiloRiesgo> get estiloPorCategoria => ColoresMaterna.oscuro ? _estilosOscuros : _estilosClaros;

const _estilosClaros = {
  'Alto Riesgo': EstiloRiesgo(
    semaforo: 'Rojo',
    nivel: 'NIVEL ALTO',
    corto: 'Alto',
    titulo: 'Alto riesgo',
    subtitulo: 'Emergencia obstétrica · remisión inmediata',
    degradado: [Color(0xFFD0342C), Color(0xFF8C1A1A)],
    barra: Color(0xFFC62828),
    fondo: Color(0xFFFDECEA),
    tinta: Color(0xFF7A1710),
    icono: Icons.error_rounded,
  ),
  'Riesgo Medio': EstiloRiesgo(
    semaforo: 'Ámbar',
    nivel: 'NIVEL MEDIO',
    corto: 'Medio',
    titulo: 'Riesgo medio',
    subtitulo: 'Valoración médica prioritaria',
    degradado: [Color(0xFFA85F00), Color(0xFF744500)],
    barra: Color(0xFFB26B00),
    fondo: Color(0xFFFFF1D6),
    tinta: Color(0xFF7A4A00),
    icono: Icons.warning_rounded,
  ),
  'Bajo Riesgo': EstiloRiesgo(
    semaforo: 'Verde',
    nivel: 'NIVEL BAJO',
    corto: 'Bajo',
    titulo: 'Bajo riesgo',
    subtitulo: 'Control prenatal de rutina',
    degradado: [Color(0xFF1F7A45), Color(0xFF13542F)],
    barra: Color(0xFF1B6B3A),
    fondo: Color(0xFFE3F3E8),
    tinta: Color(0xFF1B5E36),
    icono: Icons.check_circle_rounded,
  ),
};

/// Los mismos niveles en el modo oscuro: degradados iguales (texto blanco encima); avisos, etiquetas y barras con
/// tonos que conservan el contraste sobre el fondo oscuro.
const _estilosOscuros = {
  'Alto Riesgo': EstiloRiesgo(
    semaforo: 'Rojo',
    nivel: 'NIVEL ALTO',
    corto: 'Alto',
    titulo: 'Alto riesgo',
    subtitulo: 'Emergencia obstétrica · remisión inmediata',
    degradado: [Color(0xFFD0342C), Color(0xFF8C1A1A)],
    barra: Color(0xFFF07167),
    fondo: Color(0xFF3D1C1F),
    tinta: Color(0xFFFFA49B),
    icono: Icons.error_rounded,
  ),
  'Riesgo Medio': EstiloRiesgo(
    semaforo: 'Ámbar',
    nivel: 'NIVEL MEDIO',
    corto: 'Medio',
    titulo: 'Riesgo medio',
    subtitulo: 'Valoración médica prioritaria',
    degradado: [Color(0xFFA85F00), Color(0xFF744500)],
    barra: Color(0xFFE9A640),
    fondo: Color(0xFF3B2C12),
    tinta: Color(0xFFF4C672),
    icono: Icons.warning_rounded,
  ),
  'Bajo Riesgo': EstiloRiesgo(
    semaforo: 'Verde',
    nivel: 'NIVEL BAJO',
    corto: 'Bajo',
    titulo: 'Bajo riesgo',
    subtitulo: 'Control prenatal de rutina',
    degradado: [Color(0xFF1F7A45), Color(0xFF13542F)],
    barra: Color(0xFF5CC085),
    fondo: Color(0xFF173325),
    tinta: Color(0xFF9EDDB6),
    icono: Icons.check_circle_rounded,
  ),
};

/// Incluida en la app (assets/fonts, Roboto del SDK de Flutter): sin ella, la web la descarga de internet.
const fuente = 'MaternaRoboto';

/// Tema de Material con la paleta del modo activo (llamar a [ColoresMaterna.usar] antes).
ThemeData temaMaterna() {
  final oscuro = ColoresMaterna.oscuro;
  final esquema = ColorScheme.fromSeed(
    seedColor: ColoresClaros.ciruela900,
    brightness: oscuro ? Brightness.dark : Brightness.light,
    primary: ColoresMaterna.ciruela900,
    onPrimary: oscuro ? ColoresClaros.tinta : Colors.white,
    secondary: ColoresMaterna.ciruela700,
    surface: ColoresMaterna.crema,
    onSurface: ColoresMaterna.tinta,
    surfaceContainerHighest: ColoresMaterna.campo,
  );
  final redondeo = BorderRadius.circular(16);
  return ThemeData(
    useMaterial3: true,
    brightness: oscuro ? Brightness.dark : Brightness.light,
    fontFamily: fuente,
    colorScheme: esquema,
    scaffoldBackgroundColor: ColoresMaterna.crema,
    appBarTheme: AppBarTheme(
      backgroundColor: Colors.transparent,
      foregroundColor: ColoresMaterna.tinta,
      elevation: 0,
      scrolledUnderElevation: 0,
      centerTitle: false,
    ),
    cardTheme: CardThemeData(
      color: ColoresMaterna.tarjeta,
      elevation: 0,
      margin: EdgeInsets.zero,
      shadowColor: ColoresMaterna.sombra,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(20),
        side: BorderSide(color: ColoresMaterna.borde),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: ColoresMaterna.campo,
      border: OutlineInputBorder(borderRadius: redondeo, borderSide: BorderSide.none),
      focusedBorder: OutlineInputBorder(
        borderRadius: redondeo,
        borderSide: BorderSide(color: ColoresMaterna.ciruela900, width: 1.5),
      ),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: ColoresMaterna.vino,
        foregroundColor: Colors.white,
        minimumSize: const Size.fromHeight(54),
        shape: const StadiumBorder(),
        textStyle: const TextStyle(fontFamily: fuente, fontSize: 16, fontWeight: FontWeight.w700),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: ColoresMaterna.ciruela900,
        backgroundColor: ColoresMaterna.tarjeta,
        minimumSize: const Size.fromHeight(48),
        shape: const StadiumBorder(),
        side: BorderSide(color: ColoresMaterna.ciruela100),
      ),
    ),
    textButtonTheme: TextButtonThemeData(style: TextButton.styleFrom(foregroundColor: ColoresMaterna.ciruela900)),
    segmentedButtonTheme: SegmentedButtonThemeData(
      style: SegmentedButton.styleFrom(
        backgroundColor: ColoresMaterna.tarjeta,
        foregroundColor: ColoresMaterna.ciruela900,
        selectedBackgroundColor: ColoresMaterna.ciruela100,
        selectedForegroundColor: ColoresMaterna.ciruela900,
        side: BorderSide(color: ColoresMaterna.borde),
      ),
    ),
    chipTheme: ChipThemeData(
      backgroundColor: ColoresMaterna.tarjeta,
      selectedColor: ColoresMaterna.ciruela100,
      side: BorderSide(color: ColoresMaterna.borde),
      shape: const StadiumBorder(),
      labelStyle: TextStyle(fontFamily: fuente, color: ColoresMaterna.tinta),
    ),
    dialogTheme: DialogThemeData(backgroundColor: ColoresMaterna.tarjeta, surfaceTintColor: Colors.transparent),
    bottomSheetTheme: BottomSheetThemeData(backgroundColor: ColoresMaterna.tarjeta, surfaceTintColor: Colors.transparent),
    switchTheme: SwitchThemeData(
      thumbColor: WidgetStateProperty.resolveWith((e) => e.contains(WidgetState.selected) ? Colors.white : null),
      trackColor: WidgetStateProperty.resolveWith((e) => e.contains(WidgetState.selected) ? ColoresMaterna.vino : null),
    ),
    progressIndicatorTheme: ProgressIndicatorThemeData(
      color: ColoresMaterna.ciruela900,
      linearTrackColor: ColoresMaterna.fondoProgreso,
    ),
  );
}
