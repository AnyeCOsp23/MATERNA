/// Identidad visual de MATERNA en la app (paleta de los mockups del Módulo 2).
///
/// Marca: vino #7B2D5B (botones, íconos y textos de marca), vino del logo #942255, rosa claro #F5D3E3 (pestaña
/// activa, íconos de título y botón secundario), fondo crema en degradado #F8F6EC -> #F0EEDD y blanco en tarjetas.
/// Semáforo: tarjeta en degradado, barra y aviso propios por nivel (rojo, ámbar y verde), siempre con texto: el
/// riesgo nunca se comunica solo con el color.
library;

import 'package:flutter/material.dart';

abstract final class ColoresMaterna {
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

/// Fondo crema de las pantallas (de arriba hacia abajo).
const fondoCrema = BoxDecoration(
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

/// Por categoría del modelo, en el orden de las clases (Bajo, Medio, Alto).
const estiloPorCategoria = {
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

/// Incluida en la app (assets/fonts, Roboto del SDK de Flutter): sin ella, la web la descarga de internet.
const fuente = 'MaternaRoboto';

ThemeData temaMaterna() {
  final esquema = ColorScheme.fromSeed(
    seedColor: ColoresMaterna.ciruela900,
    primary: ColoresMaterna.ciruela900,
    secondary: ColoresMaterna.ciruela700,
    surface: ColoresMaterna.crema,
    onSurface: ColoresMaterna.tinta,
  );
  final redondeo = BorderRadius.circular(16);
  return ThemeData(
    useMaterial3: true,
    fontFamily: fuente,
    colorScheme: esquema,
    scaffoldBackgroundColor: ColoresMaterna.crema,
    appBarTheme: const AppBarTheme(
      backgroundColor: Colors.transparent,
      foregroundColor: ColoresMaterna.tinta,
      elevation: 0,
      scrolledUnderElevation: 0,
      centerTitle: false,
    ),
    cardTheme: CardThemeData(
      color: Colors.white,
      elevation: 0,
      margin: EdgeInsets.zero,
      shadowColor: const Color(0x143A1230),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(20),
        side: const BorderSide(color: ColoresMaterna.borde),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: ColoresMaterna.campo,
      border: OutlineInputBorder(borderRadius: redondeo, borderSide: BorderSide.none),
      focusedBorder: OutlineInputBorder(
        borderRadius: redondeo,
        borderSide: const BorderSide(color: ColoresMaterna.ciruela900, width: 1.5),
      ),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: ColoresMaterna.ciruela900,
        foregroundColor: Colors.white,
        minimumSize: const Size.fromHeight(54),
        shape: const StadiumBorder(),
        textStyle: const TextStyle(fontFamily: fuente, fontSize: 16, fontWeight: FontWeight.w700),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: ColoresMaterna.ciruela900,
        backgroundColor: Colors.white,
        minimumSize: const Size.fromHeight(48),
        shape: const StadiumBorder(),
        side: const BorderSide(color: ColoresMaterna.ciruela100),
      ),
    ),
    textButtonTheme: TextButtonThemeData(style: TextButton.styleFrom(foregroundColor: ColoresMaterna.ciruela900)),
    segmentedButtonTheme: SegmentedButtonThemeData(
      style: SegmentedButton.styleFrom(
        backgroundColor: Colors.white,
        selectedBackgroundColor: ColoresMaterna.ciruela100,
        selectedForegroundColor: ColoresMaterna.ciruela900,
        side: const BorderSide(color: ColoresMaterna.borde),
      ),
    ),
    chipTheme: ChipThemeData(
      backgroundColor: Colors.white,
      selectedColor: ColoresMaterna.ciruela100,
      side: const BorderSide(color: ColoresMaterna.borde),
      shape: const StadiumBorder(),
      labelStyle: const TextStyle(fontFamily: fuente, color: ColoresMaterna.tinta),
    ),
    progressIndicatorTheme: const ProgressIndicatorThemeData(
      color: ColoresMaterna.ciruela900,
      linearTrackColor: ColoresMaterna.fondoProgreso,
    ),
  );
}
