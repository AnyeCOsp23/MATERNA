"""Datos y modelos compartidos por las pruebas."""
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src.config import DIR_METRICAS, DIR_MODELOS  # noqa: E402

# Gestante sana de referencia: ningún factor de riesgo
REGISTRO_SANO = dict(
    edad=27, departamento="Cesar", municipio="Valledupar", pertenencia_etnica="Mestiza",
    area_residencia="Cabecera", semanas_gestacion=28, n_controles_prenatales=5, atendido_por="Medico",
    pas_mmhg=110, pad_mmhg=70, fcf_bpm=142.0, glucosa_mgdl=88.0, proteinuria=0, convulsiones=0,
)

# Rangos que admite el formulario de app_demo.py
RANGOS_UI = dict(edad=(10, 55), semanas_gestacion=(4, 42), n_controles_prenatales=(0, 20),
                 pas_mmhg=(60, 250), pad_mmhg=(30, 150), fcf_bpm=(60.0, 220.0), glucosa_mgdl=(30.0, 600.0))
MUNICIPIOS = {"Uribia": "La Guajira", "Riohacha": "La Guajira", "Manaure": "La Guajira", "Maicao": "La Guajira",
              "Valledupar": "Cesar", "Codazzi": "Cesar", "La Paz": "Cesar", "Becerril": "Cesar"}
ETNIAS = ["Wayuu", "Mestiza", "Afro", "Yukpa", "Arhuaco", "Wiwa", "Kogui"]
ATENCION = ["Medico", "Enfermero(a)", "Auxiliar de enfermeria", "Partera tradicional"]


def registros_aleatorios(n, semilla=0):
    """Entradas aleatorias dentro de los rangos de la interfaz, con ~20 % de FCF/glucosa faltantes."""
    rng = np.random.default_rng(semilla)
    filas = []
    for _ in range(n):
        municipio = rng.choice(list(MUNICIPIOS))
        fila = {
            "edad": int(rng.integers(*RANGOS_UI["edad"], endpoint=True)),
            "departamento": MUNICIPIOS[municipio], "municipio": municipio,
            "pertenencia_etnica": rng.choice(ETNIAS),
            "area_residencia": rng.choice(["Cabecera", "Rural disperso"]),
            "semanas_gestacion": int(rng.integers(*RANGOS_UI["semanas_gestacion"], endpoint=True)),
            "n_controles_prenatales": int(rng.integers(*RANGOS_UI["n_controles_prenatales"], endpoint=True)),
            "atendido_por": rng.choice(ATENCION),
            "pas_mmhg": int(rng.integers(*RANGOS_UI["pas_mmhg"], endpoint=True)),
            "pad_mmhg": int(rng.integers(*RANGOS_UI["pad_mmhg"], endpoint=True)),
            "fcf_bpm": None if rng.random() < 0.2 else float(rng.uniform(*RANGOS_UI["fcf_bpm"])),
            "glucosa_mgdl": None if rng.random() < 0.2 else float(rng.uniform(*RANGOS_UI["glucosa_mgdl"])),
            "proteinuria": int(rng.integers(0, 3)),
            "convulsiones": int(rng.random() < 0.05),
        }
        filas.append(fila)
    return filas


def a_dataframe(registros):
    return pd.DataFrame([{k: (np.nan if v is None else v) for k, v in r.items()} for r in registros])


@pytest.fixture(scope="session")
def modelos():
    return {
        "Regresión Logística": joblib.load(DIR_MODELOS / "modelo_regresion_logistica.joblib"),
        "SVM": joblib.load(DIR_MODELOS / "modelo_svm_calibrado.joblib"),
        "Random Forest": joblib.load(DIR_MODELOS / "modelo_random_forest.joblib"),
    }


@pytest.fixture(scope="session")
def resumen():
    with open(DIR_METRICAS / "resumen_evaluacion.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def modelo_principal(modelos, resumen):
    return modelos[resumen["modelo_principal_para_hibrido"]]


@pytest.fixture(scope="session")
def particiones():
    from src.data_preprocessing import preparar_datos
    return preparar_datos(guardar=False)
