"""Fase 3 — Lista de chequeo del ciclo de vida de ML (12 fases), auditada contra el repositorio.

Cada fila es una actividad con su estado real:
  Hecho    se puede ver o ejecutar hoy en el aplicativo;
  Parcial  existe una parte (se dice cuál) y falta otra;
  Falta    todavía no existe; la columna "Etapa" dice en qué etapa del plan de ajustes se construye.

El requisito del docente es que cada fase se pueda EJECUTAR en el Módulo 1, no solo mostrarse: por eso
una actividad que hoy solo muestra resultados guardados figura aparte de su versión ejecutable.

Esta tabla se actualiza al cerrar cada etapa. Una prueba (tests/test_lista_chequeo.py) vigila que los
archivos citados existan, para que la evidencia no apunte a algo que ya no está.
"""
import pandas as pd

from src.config import RAIZ

ESTADOS = ("Hecho", "Parcial", "Falta")
FASES = {
    "01": "Definir el problema", "02": "Recolección de datos", "03": "Análisis exploratorio (EDA)", "04": "Limpieza",
    "05": "Ingeniería de características", "06": "División de los datos", "07": "Selección del algoritmo",
    "08": "Entrenamiento", "09": "Ajuste de hiperparámetros", "10": "Evaluación", "11": "Generalización",
    "12": "Despliegue",
}
# Etapas del plan de ajustes de la Fase 3 (donde se construye lo que falta)
ETAPAS = {
    2: "Lenguaje del Módulo 2", 3: "Partición, parámetros y experimentos", 4: "Generador, depuración y carga masiva",
    5: "Interpretación de métricas", 6: "Nuevo patrón y reentrenamiento", 7: "Publicación al Módulo 2",
}

# (fase, actividad, estado, evidencia en el aplicativo, archivos, etapa en que se completa o None)
ACTIVIDADES = [
    ("01", "Tipo de problema, clases y métricas objetivo con su justificación", "Hecho",
     "Pestaña 01", ["paginas/laboratorio.py", "reports/metrics/metricas_test.csv"], None),
    ("01", "Matriz de costo clínico de los errores", "Hecho",
     "Pestaña 01", ["src/evaluate.py"], None),

    ("02", "Dataset base: 1.200 gestantes sintéticas, fuentes de calibración y aviso de que no son pacientes reales", "Hecho",
     "Pestaña 02", ["data/raw/dataset_riesgo_materno_guajira_cesar.csv", "src/data_preprocessing.py"], None),
    ("02", "Ingesta de un archivo CSV, TXT o Excel con filtro 3280, seudonimización y reporte de calidad", "Hecho",
     "Pestaña 02 · «Ingesta auditable»", ["src/inspeccionar_ips.py", "src/filtro_3280.py", "src/seudonimizacion.py"], None),
    ("02", "Guardar la carga en la base del laboratorio, con quién y cuándo", "Hecho",
     "Pestaña 02 · «Guardar en la base del laboratorio»", ["src/consolidado_ips.py"], None),
    ("02", "Carga masiva de 5.000 a 30.000+ registros con barra de progreso y caché", "Parcial",
     "Pestaña 02: ya lee por lotes de 5.000 filas; falta la barra de progreso, la caché y medirlo con esos tamaños",
     ["src/inspeccionar_ips.py"], 4),
    ("02", "Generador sintético a pedido (N registros a partir de las 1.200, con semilla y columna «origen»)", "Falta",
     "—", [], 4),
    ("02", "Lote de demostración reservado, que nunca entra al entrenamiento", "Falta", "—", [], 4),
    ("02", "Agregar un patrón nuevo a mano (10.000 → 10.001) con registro del evento", "Falta", "—", [], 6),

    ("03", "Datos faltantes, presión por clase y distribución de clases del dataset base", "Hecho",
     "Pestañas 02 y 03", ["src/graficos.py", "notebooks/EDA_Riesgo_Materno_Guajira_Cesar.ipynb"], None),
    ("03", "Comparación del dataset sintético con un archivo de la IPS (ejemplo ficticio o base del laboratorio)", "Hecho",
     "Pestaña 03 · «Comparación»", ["paginas/laboratorio.py", "src/graficos.py"], None),
    ("03", "EDA del conjunto de trabajo (datos generados o cargados para entrenar)", "Falta",
     "Hoy el EDA está fijo sobre las 1.200", [], 4),

    ("04", "Reglas de limpieza, rangos fisiológicos y medianas del imputador del modelo en uso", "Hecho",
     "Pestaña 04", ["src/data_preprocessing.py", "src/inspeccionar_ips.py"], None),
    ("04", "Depurar datos crudos dentro del aplicativo: pasos visibles, conteo antes y después y reporte descargable", "Parcial",
     "Pestaña 02: la ingesta ya limpia centinelas, rangos y duplicados y los cuenta; faltan los pasos uno a uno, "
     "el reporte descargable y limpiar un conjunto con etiqueta para entrenar", ["src/inspeccionar_ips.py"], 4),

    ("05", "Filtro de la Resolución 3280: decisión por cada una de las 71 variables", "Hecho",
     "Página «Variables 3280» y pestaña 04", ["config/variables_3280.json", "src/filtro_3280.py"], None),
    ("05", "Variables de entrada, escalado robusto, One-Hot e indicadores de dato faltante", "Hecho",
     "Pestaña 05", ["src/data_preprocessing.py", "flutter_app/assets/preproceso.json"], None),
    ("05", "Ablación: etnia y territorio no mejoran el modelo y quedan fuera", "Hecho",
     "Pestaña 05", ["reports/metrics/ablacion_variables_demograficas.csv"], None),

    ("06", "Partición 70/15/15 estratificada, conjuntos disjuntos y sin fuga de datos", "Hecho",
     "Pestaña 06", ["src/data_preprocessing.py", "tests/test_preprocesamiento.py"], None),
    ("06", "Partición parametrizable: porcentajes, semilla, conteos por clase y aviso si hay pocos casos de Alto", "Falta",
     "Hoy la partición es fija (solo la semilla es un parámetro de la función)", ["src/data_preprocessing.py"], 3),

    ("07", "Comparación de Regresión Logística, SVM y Random Forest en validación cruzada y en validación", "Hecho",
     "Pestaña 07", ["reports/metrics/comparacion_cv_por_estrategia.csv", "reports/metrics/metricas_validacion.csv"], None),
    ("07", "Justificación del Random Forest con las pruebas de coherencia clínica", "Hecho",
     "Pestaña 07", ["tests/test_coherencia_clinica.py"], None),
    ("07", "Tabla comparativa de los experimentos propios y criterio explícito de selección", "Falta", "—", [], 3),

    ("08", "Entrenar en vivo el Random Forest, con avance por partición, tiempo y comparación con el modelo en uso", "Hecho",
     "Pestaña 08 · «Entrenar en vivo»", ["src/entrenamiento_vivo.py"], None),
    ("08", "Entrenar en vivo la Regresión Logística y la SVM", "Falta", "—", [], 3),
    ("08", "Cada entrenamiento crea una versión nueva, sin tocar el modelo en uso", "Falta",
     "Hoy el entrenamiento en vivo no guarda nada", ["src/entrenamiento_vivo.py"], 3),
    ("08", "Reentrenar con un patrón nuevo y comparar antes y después", "Falta", "—", [], 6),

    ("09", "Búsqueda en grilla ya ejecutada: 166 configuraciones × 5 particiones, con SMOTE y pesos comparados", "Hecho",
     "Pestaña 09", ["src/train_models.py", "reports/metrics/experimentos_cv_completo.csv"], None),
    ("09", "Elegir los hiperparámetros de cada modelo desde el aplicativo", "Falta",
     "Hoy son fijos (los mejores de la búsqueda)", ["src/entrenamiento_vivo.py"], 3),
    ("09", "Registro de experimentos (fecha, parámetros, partición, semilla, métricas, tiempo, usuario) descargable", "Falta",
     "—", [], 3),

    ("10", "Métricas en prueba con intervalos bootstrap, matrices de confusión, curvas ROC y costo clínico", "Hecho",
     "Pestaña 10", ["src/evaluate.py", "reports/metrics/metricas_test.csv", "reports/figures/matrices_confusion_test.png",
                    "reports/figures/curvas_roc_test.png"], None),
    ("10", "Evaluación sin signos críticos: lo que el modelo resuelve sin las reglas", "Hecho",
     "Pestaña 10", ["reports/metrics/metricas_test_sin_signos_criticos.csv"], None),
    ("10", "Aviso fijo: las métricas miden el etiquetado sintético, no el desempeño clínico", "Parcial",
     "Está en las pestañas 02, 12 y 13; falta junto a cada tabla de métricas", ["paginas/laboratorio.py"], 5),
    ("10", "Panel por métrica: qué es, por qué se usa y cómo se lee, con una frase armada desde los números", "Falta",
     "—", [], 5),
    ("10", "Métricas sobre patrones no usados (lote de demostración y registros nuevos), comparadas", "Falta", "—", [], 5),

    ("11", "Curvas de aprendizaje y brecha entre entrenamiento y validación de los tres modelos", "Hecho",
     "Pestaña 11", ["src/curvas_aprendizaje.py", "reports/metrics/curvas_aprendizaje.csv",
                    "reports/metrics/brecha_sobreajuste.csv"], None),
    ("11", "Recalcular las curvas con la partición y los parámetros elegidos", "Falta",
     "Hoy se calculan desde la terminal y la pestaña muestra el resultado guardado", ["src/curvas_aprendizaje.py"], 3),
    ("11", "Auditoría de sesgos por área, etnia, quién atiende y departamento", "Hecho",
     "Pestaña 13", ["reports/metrics/auditoria_subgrupos.csv"], None),

    ("12", "Exportación del Random Forest, el preprocesamiento y las reglas a JSON, con versión y SHA-256", "Hecho",
     "Pestaña 12 (estado de la entrega y artefactos); se ejecuta desde la terminal",
     ["src/exportar_a_dart.py", "flutter_app/assets/modelo_rf.json"], None),
    ("12", "Paridad exacta entre scikit-learn, el JSON y la app", "Hecho",
     "Pestaña 12", ["src/inferencia_json.py", "tests/test_exportacion_json.py", "flutter_app/test/paridad_test.dart"], None),
    ("12", "Motor de reglas clínicas, con prueba interactiva", "Hecho",
     "Pestaña 12 · «Pruebe el motor de reglas»", ["src/clinical_rules.py", "flutter_app/assets/reglas.json"], None),
    ("12", "Botón «Publicar al Módulo 2» (solo administrador, solo Random Forest) con paridad y versión nueva", "Falta",
     "Hoy la exportación es un comando: python -m src.exportar_a_dart", ["src/exportar_a_dart.py"], 7),
    ("12", "Módulo 2: app web y móvil con triaje, carga masiva, historial y cuentas, sin internet", "Hecho",
     "App MATERNA (Flutter)", ["flutter_app/lib/main.dart", "flutter_app/lib/motor/clasificador.dart"], None),
    ("12", "Resultado de la app en lenguaje claro, sin términos de aprendizaje automático", "Falta",
     "Hoy el resultado dice «Modelo de IA» y «Probabilidad por clase»",
     ["flutter_app/lib/ui/pantallas/pantalla_resultado.dart"], 2),
]


def tabla():
    """La lista de chequeo como tabla, lista para mostrar o descargar."""
    return pd.DataFrame([{
        "Fase": f"{fase} {FASES[fase]}", "Actividad": actividad, "Estado": estado, "Evidencia en el aplicativo": evidencia,
        "Archivo": ", ".join(archivos) or "—", "Se completa en": f"Etapa {etapa} · {ETAPAS[etapa]}" if etapa else "—",
    } for fase, actividad, estado, evidencia, archivos, etapa in ACTIVIDADES])


def resumen():
    """Conteo de actividades por fase y estado (una fila por cada una de las 12 fases)."""
    t = tabla()
    conteo = t.groupby(["Fase", "Estado"]).size().unstack(fill_value=0).reindex(columns=list(ESTADOS), fill_value=0)
    return conteo.reset_index()


def archivos_faltantes():
    """Archivos citados como evidencia que no existen en el repositorio (debe estar vacío)."""
    citados = {a for *_, archivos, _ in ACTIVIDADES for a in archivos}
    return sorted(a for a in citados if not (RAIZ / a).exists())
