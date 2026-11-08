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
- 4b · Commit B (base local SQLite, historial, PIN con perfil y «Acerca de») y commit C (carga masiva con la
  plantilla 3280, seudonimización HMAC y exportación CSV): pendientes.
- 4c · Carga masiva de archivos de la IPS: pendiente.

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
