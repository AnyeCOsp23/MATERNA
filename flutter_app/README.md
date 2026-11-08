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
- 4b · Pantallas (PIN, formulario por secciones de la Resolución 3280, semáforo, alertas, SQLite): en curso.
- 4c · Carga masiva de archivos de la IPS: pendiente.

## Comandos

```
cd flutter_app
flutter test              # paridad del motor y de las alertas, y pruebas de la app
flutter run -d chrome     # versión web
flutter build web         # PWA en build/web
flutter build apk         # Android (requiere aceptar las licencias: flutter doctor --android-licenses)
```

Si el modelo se reentrena en el Módulo 1, hay que volver a exportar (`python -m src.exportar_a_dart`) antes de
compilar la app: una prueba de Python avisa si los JSON ya no corresponden al `.joblib` en uso.
