"""Configuración central del proyecto MATERNA: rutas, semilla y definición de variables."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
RUTA_DATASET = RAIZ / "data" / "raw" / "dataset_riesgo_materno_guajira_cesar.csv"
DIR_PROCESADOS = RAIZ / "data" / "processed"
DIR_MODELOS = RAIZ / "models"
DIR_FIGURAS = RAIZ / "reports" / "figures"
DIR_METRICAS = RAIZ / "reports" / "metrics"

SEMILLA = 42

# Variable objetivo y su codificación ordinal
TARGET = "riesgo_obstetrico"
MAPA_TARGET = {"Bajo Riesgo": 0, "Riesgo Medio": 1, "Alto Riesgo": 2}
NOMBRES_CLASES = list(MAPA_TARGET.keys())
CLASE_ALTO = MAPA_TARGET["Alto Riesgo"]

# Variables continuas que se escalan con RobustScaler
VARS_CONTINUAS = [
    "edad",
    "semanas_gestacion",
    "n_controles_prenatales",
    "pas_mmhg",
    "pad_mmhg",
    "fcf_bpm",
    "glucosa_mgdl",
]
# Variables que ya son numéricas discretas y entran sin escalar
VARS_DISCRETAS = ["proteinuria", "convulsiones", "glucosa_no_disponible", "fcf_no_disponible"]
# Variables categóricas nominales de acceso a la atención (One-Hot)
VARS_CATEGORICAS = ["area_residencia", "atendido_por"]
# Variables de identidad territorial y étnica: NO entran al modelo por defecto.
# Se usan para auditar sesgos por subgrupo (ver evaluate.py) y en un experimento de ablación.
VARS_DEMOGRAFICAS = ["departamento", "municipio", "pertenencia_etnica"]

VARS_CON_NULOS = ["glucosa_mgdl", "fcf_bpm"]
