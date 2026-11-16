"""Fase 3: el recorrido de una gestante por el sistema híbrido (src/recorrido.py) reproduce al modelo en uso."""
import json

import joblib
import numpy as np
import pandas as pd
import pytest

from src import recorrido as R
from src.clinical_rules import evaluar_riesgo_hibrido
from src.data_preprocessing import cargar_dataset, separar_xy
from src.exportar_a_dart import RUTA_MODELO


@pytest.fixture(scope="module")
def modelo():
    return joblib.load(RUTA_MODELO)


def fila(registro):
    return pd.DataFrame([{k: (np.nan if v is None else v) for k, v in registro.items()}])


@pytest.mark.parametrize("caso, categoria, origen", [
    ("Caso 1 · Emergencia (Uribia)", "Alto Riesgo", "regla_clinica"),
    ("Caso 2 · Sin controles previos (Manaure)", "Riesgo Medio", "modelo_ml"),
    ("Caso 3 · Control de rutina (Valledupar)", "Bajo Riesgo", "modelo_ml"),
])
def test_los_casos_de_demostracion(modelo, caso, categoria, origen):
    r = R.recorrido(R.CASOS[caso], modelo)
    assert (r["categoria"], r["origen"]) == (categoria, origen)
    assert len(r["datos"]) == 11 and len(r["variables"]) == 17 and len(r["arboles"]) == R.ARBOLES_VISIBLES
    assert r["n_arboles"] == 300 == len(r["inclinacion"]) == sum(r["arboles_por_clase"])
    # las probabilidades son las del modelo en uso (el promedio de las 300 hojas)
    assert np.allclose(r["probabilidades"], modelo.predict_proba(fila(R.CASOS[caso]))[0], atol=1e-4)
    json.dumps(r)  # solo tipos simples: se puede enviar al navegador


def test_reproduce_al_modelo_en_300_gestantes_del_dataset(modelo):
    X, _ = separar_xy(cargar_dataset())
    for _, gestante in X.sample(300, random_state=7).iterrows():
        registro = {k: (None if pd.isna(v) else v) for k, v in gestante.items()}
        r, esperado = R.recorrido(registro, modelo, n_arboles=2), evaluar_riesgo_hibrido(registro, modelo)
        assert np.allclose(r["probabilidades"], list(esperado.probabilidades_modelo.values()), atol=1e-4)
        assert (r["clase"], r["origen"], r["reglas"]) == (esperado.clase, esperado.origen, esperado.alertas)


def test_las_preguntas_son_coherentes_con_los_datos(modelo):
    caso = R.CASOS["Caso 2 · Sin controles previos (Manaure)"]
    r = R.recorrido(caso, modelo)
    # la glucosa no se midió: se marca como imputada y se enciende su indicador
    glucosa = next(d for d in r["datos"] if d["nombre"] == "glucosa_mgdl")
    assert glucosa["imputado"] and not next(d for d in r["datos"] if d["nombre"] == "fcf_bpm")["imputado"]
    assert next(v for v in r["variables"] if v["nombre"] == "glucosa_no_disponible")["valor"] == 1
    for arbol in r["arboles"]:
        assert arbol["pasos"] and abs(sum(arbol["hoja"]) - 1) < 1e-3 and arbol["clase"] == int(np.argmax(arbol["hoja"]))
        for paso in arbol["pasos"]:
            assert paso["pregunta"].startswith("¿") and paso["pregunta"].endswith("?")
            assert paso["respuesta"].startswith(("sí", "no")) and 0 <= paso["variable"] < 17
    # umbrales en unidades originales: una pregunta sobre la presión compara con mmHg reales, no con el valor escalado
    presion = [p for a in r["arboles"] for p in a["pasos"] if p["pregunta"].startswith("¿PAS")]
    assert presion and all(60 <= float(p["pregunta"].split("≤ ")[1].split(" ")[0].replace(",", ".")) <= 250 for p in presion)
    assert all(("sí" in p["respuesta"]) == (caso["pas_mmhg"] <= float(p["pregunta"].split("≤ ")[1].split(" ")[0].replace(",", ".")))
               for p in presion)


def test_el_recorrido_en_texto(modelo):
    frases = R.en_texto(R.recorrido(R.CASOS["Caso 1 · Emergencia (Uribia)"], modelo))
    assert len(frases) == 5 and "La regla prevalece sobre el modelo" in frases[3] and "Alto Riesgo" in frases[4]
    frases = R.en_texto(R.recorrido(R.CASOS["Caso 2 · Sin controles previos (Manaure)"], modelo))
    assert "Glucosa no se midió" in frases[0] and "decide el modelo" in frases[3] and "91,3 %" in frases[2]
