# MATERNA · Módulo 2 (app de usuario final)

Aplicación Flutter para el personal de salud en territorio, **web (PWA) y Android con un solo código**.
Consume, sin modificarlos, los artefactos que entrega el Módulo 1 (laboratorio de ML, `app_demo.py`):

| Archivo | Contenido | Lo genera |
|---|---|---|
| `assets/preproceso.json` | Imputación por área × trimestre, RobustScaler y One-Hot | `python -m src.exportar_a_dart` |
| `assets/modelo_rf.json` | Random Forest de 300 árboles, con versión y SHA-256 del `.joblib` | ídem |
| `assets/reglas.json` | Los 4 signos críticos (GPC Minsalud 2013) y los protocolos | ídem |
| `assets/casos_paridad.json` | 200 casos con la respuesta exacta de scikit-learn (solo para pruebas) | ídem |
| `assets/variables_3280.json` | Copia exacta de `config/variables_3280.json`: secciones, rangos y alertas de la ruta | ídem |
| `assets/casos_alertas.json` | 160 casos con las alertas que calcula Python (solo para pruebas) | ídem |
| `assets/casos_carga.json` | Carga masiva del ejemplo ficticio de la IPS según `src/carga_masiva.py`: reporte, triaje ordenado fila por fila y seudónimos, con una sal **solo de prueba** (solo para pruebas) | `python -m src.exportar_a_dart --solo-carga` |

## Estado

- **4a · Motor offline** (`lib/motor/clasificador.dart`): traducción de `src/inferencia_json.py`. Compara en float32
  como scikit-learn y reproduce los 200 casos de paridad (`test/paridad_test.dart`, tolerancia 1e-6).
- 4b · Paso 1, catálogo y alertas (`lib/motor/catalogo_3280.dart`): traducción de `evaluar_alertas_3280`. Los campos
  Sí/No tienen tres estados (Sí, No, Sin dato): «Sin dato» nunca alerta. Reproduce los 160 casos (`test/alertas_test.dart`).
- 4b · Commit A, navegación, triaje y resultado (`lib/ui/`):
  - Barra de navegación flotante, blanca y redondeada (`ui/widgets/barra_flotante.dart`), con la pestaña activa en una
    píldora rosa y 4 pestañas: Triaje, Carga IPS,
    Historial y Acerca de. Cada pestaña conserva su estado.
  - Triaje como asistente por pasos (`ui/pantallas/pantalla_triaje.dart`): 1 Datos maternos, 2 Constantes vitales y
    laboratorio, 3 Contexto y atención, 4 Signos de alarma, 5 Valoración de la ruta (opcional), 6 Revisión. Cada paso
    valida antes de avanzar; los rangos y unidades salen del catálogo 3280.
  - Resultado (`ui/pantallas/pantalla_resultado.dart`): primero las alertas URGENTES de la ruta (para que un verde no
    tranquilice en falso), luego el semáforo con icono y texto y el motivo (regla clínica o modelo), las
    probabilidades, las demás alertas y el protocolo.
  - Signos de alarma obstétricos de la ruta (cefalea, visión borrosa, tinnitus, dolor epigástrico, sangrado genital,
    fiebre y disminución de movimientos fetales; `escala_a_alto` en el catálogo) elevan el triaje final a ROJO, como
    las reglas críticas y con la misma lógica que `clinical_rules.evaluar_riesgo_hibrido` de Python. El modelo no
    cambia. Criterio del equipo por validar con un especialista.
  - Paleta de MATERNA, solo iconos vectoriales (Material y, en la barra, trazos propios de
    `ui/widgets/iconos_trazo.dart`; sin emojis) y tipografía Roboto incluida en `assets/fonts/`
    (licencia Apache 2.0): sin internet, la web no depende de fonts.gstatic.com para el texto.
  - Pruebas de pantallas en `test/flujo_test.dart`.
- 4b · Commit B, acceso, base local, historial y «Acerca de»:
  - Base local SQLite (`lib/datos/base_local.dart`): sqflite en Android/iOS y SQLite en WebAssembly en la web
    (`sqflite_common_ffi_web`; sus archivos `web/sqlite3.wasm` y `web/sqflite_sw.js` se generan con
    `dart run sqflite_common_ffi_web:setup`). Cada evaluación se guarda al mostrar su resultado, sin nombre ni documento.
  - Acceso (`ui/pantallas/pantalla_acceso.dart`): la primera vez, perfil del operador (quién atiende, una de las 4
    categorías del modelo, e IPS o municipio) y PIN de 4 dígitos; después, teclado numérico. El PIN se guarda como
    PBKDF2-HMAC-SHA256 con sal (`lib/datos/seguridad.dart`); 5 intentos fallidos bloquean 30 s; si se olvida, la app se
    reinicia y se borran los datos locales. La sesión no se recuerda al cerrar la app.
  - Historial (`ui/pantallas/pantalla_historial.dart`): filtros por riesgo y fecha, búsqueda por seudónimo o por
    documento (desde el commit C), detalle de cada evaluación y sincronización simulada.
  - «Acerca de» (`ui/pantallas/pantalla_acerca_de.dart`): versión, modelo y su huella, paridad, velocidad medida en el
    dispositivo (menos de 5 ms), limitaciones y deslinde médico.
- 4b · Commit C, carga masiva de la IPS (pestaña «Carga IPS», `ui/pantallas/pantalla_carga.dart`):
  - Clave de la IPS, configurada una vez por dispositivo (mínimo 16 caracteres). Con ella el documento se reemplaza
    por su seudónimo HMAC-SHA256 (`lib/datos/seudonimizacion.dart`, traducción de `src/seudonimizacion.py`); la app
    muestra solo una huella corta de la clave para comprobar que todos los dispositivos de la IPS usan la misma.
  - Archivo con la plantilla 3280 (`data/plantillas/`): CSV o TXT con «|», «,», «;» o tabulador, en UTF-8 o Latin-1,
    y Excel .xlsx (`lib/datos/lector_ips.dart`, con un lector propio del .xlsx: el paquete `excel` falla con los
    archivos que genera openpyxl). Se elige con `file_picker`.
  - Motor (`lib/motor/carga_masiva.dart`, traducción de `src/carga_masiva.py`): centinelas, filtro 3280 por los
    sinónimos del catálogo, columnas personales y desconocidas descartadas, valores imposibles como vacíos, filas
    repetidas fuera; cada registro se evalúa con el mismo sistema híbrido del triaje y la lista queda ordenada por
    urgencia (rojo > ámbar > verde y, en cada color, por probabilidad de Alto Riesgo). Las filas sin una variable
    obligatoria no se evalúan y se informan.
  - Se guarda en el historial con la carga (base local versión 2, tabla `cargas`); el mismo archivo no se guarda dos
    veces salvo que se pida. Exportación a CSV con el seudónimo, sin nombres ni documentos.
  - Paridad con Python: el ejemplo ficticio de `data/ejemplos/` (CSV y XLSX) da el mismo reporte, el mismo orden, los
    mismos resultados y los mismos seudónimos que `casos_carga.json` (`test/carga_test.dart`).

**Limitaciones del prototipo:** datos locales sin cifrar (también la clave de la IPS); un PIN de 4 dígitos protege el
acceso casual, no los archivos de la app; sincronización simulada (no hay servidor); iOS no se compila desde Windows;
en Excel, una fórmula sin valor calculado guardado se lee vacía.

## Comandos

```
cd flutter_app
flutter test              # paridad del motor y de las alertas, y pruebas de la app
flutter run -d chrome     # versión web
flutter build web --no-web-resources-cdn   # PWA en build/web, sin depender de CDN
flutter build apk         # Android (requiere aceptar las licencias: flutter doctor --android-licenses)
```

Si el modelo se reentrena en el Módulo 1, hay que volver a exportar (`python -m src.exportar_a_dart`) antes de
compilar la app: una prueba de Python avisa si los JSON ya no corresponden al `.joblib` en uso.
