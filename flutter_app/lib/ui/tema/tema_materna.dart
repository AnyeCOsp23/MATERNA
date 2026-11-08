/// Identidad visual de MATERNA en la app (la misma paleta de la consola web, src/ui_theme.py).
///
/// Sistema: ciruela #7D2F5F, #A54178, #D8639B y #EFC6D9 sobre crema #F3F3E7.
/// Semáforo: rojo #F099AB (Alto), amarillo #F2E88F (Medio) y verde #B6E39A (Bajo), siempre con una tinta
/// oscura legible encima, un icono y un texto: el riesgo nunca se comunica solo con el color.
library;

import 'package:flutter/material.dart';

abstract final class ColoresMaterna {
  static const ciruela900 = Color(0xFF7D2F5F);
  static const ciruela700 = Color(0xFFA54178);
  static const ciruela500 = Color(0xFFD8639B);
  static const ciruela100 = Color(0xFFEFC6D9);
  static const ciruelaNoche = Color(0xFF5C1F45); // fondo de la barra flotante (el mismo del login web)
  static const crema = Color(0xFFF3F3E7);
  static const tinta = Color(0xFF3A1F30);
  static const tintaSuave = Color(0xFF76606D);
  static const campo = Color(0xFFF6EAF0);
  static const borde = Color(0xFFE6D6DF);
}

class EstiloRiesgo {
  const EstiloRiesgo(this.semaforo, this.titulo, this.subtitulo, this.fondo, this.tinta, this.icono);

  final String semaforo;
  final String titulo;
  final String subtitulo;
  final Color fondo;
  final Color tinta;
  final IconData icono;
}

/// Por categoría del modelo, en el orden de las clases (Bajo, Medio, Alto).
const estiloPorCategoria = {
  'Alto Riesgo': EstiloRiesgo('Rojo', 'Alto riesgo', 'Emergencia obstétrica · remisión inmediata',
      Color(0xFFF099AB), Color(0xFF6B1832), Icons.error_rounded),
  'Riesgo Medio': EstiloRiesgo('Ámbar', 'Riesgo medio', 'Valoración médica prioritaria',
      Color(0xFFF2E88F), Color(0xFF5A4F0E), Icons.warning_rounded),
  'Bajo Riesgo': EstiloRiesgo('Verde', 'Bajo riesgo', 'Control prenatal de rutina',
      Color(0xFFB6E39A), Color(0xFF2C5219), Icons.check_circle_rounded),
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
      backgroundColor: ColoresMaterna.crema,
      foregroundColor: ColoresMaterna.tinta,
      elevation: 0,
      scrolledUnderElevation: 0,
      centerTitle: false,
    ),
    cardTheme: CardThemeData(
      color: Colors.white,
      elevation: 0,
      margin: EdgeInsets.zero,
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
        borderSide: const BorderSide(color: ColoresMaterna.ciruela700, width: 1.5),
      ),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: ColoresMaterna.ciruela900,
        minimumSize: const Size.fromHeight(52),
        shape: const StadiumBorder(),
        textStyle: const TextStyle(fontFamily: fuente, fontSize: 16, fontWeight: FontWeight.w600),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: ColoresMaterna.ciruela900,
        minimumSize: const Size.fromHeight(48),
        shape: const StadiumBorder(),
        side: const BorderSide(color: ColoresMaterna.ciruela100),
      ),
    ),
    segmentedButtonTheme: SegmentedButtonThemeData(
      style: SegmentedButton.styleFrom(
        selectedBackgroundColor: ColoresMaterna.ciruela100,
        selectedForegroundColor: ColoresMaterna.ciruela900,
        side: const BorderSide(color: ColoresMaterna.borde),
      ),
    ),
  );
}
