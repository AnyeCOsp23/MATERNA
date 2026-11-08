"""Fase 3, bloque 2: exportación del sistema híbrido a JSON y paridad con scikit-learn."""
import json

import numpy as np
import pandas as pd
import pytest

from src.clinical_rules import (
    UMBRAL_PAD_SEVERA, UMBRAL_PAS_SEVERA, UMBRAL_PROTEINURIA, predecir_hibrido,
)
from src.data_preprocessing import cargar_dataset, marcar_fuera_de_rango, separar_xy
from src.exportar_a_dart import DIR_ASSETS, RUTA_MODELO, TOLERANCIA, _sha256
from src.filtro_3280 import RUTA_CATALOGO, evaluar_alertas_3280, signos_alarma_que_escalan
from src.inferencia_json import ClasificadorJSON, a_float32


@pytest.fixture(scope="module")
def clf():
    return ClasificadorJSON.desde_carpeta(DIR_ASSETS)


@pytest.fixture(scope="module")
def casos():
    return json.loads((DIR_ASSETS / "casos_paridad.json").read_text(encoding="utf-8"))


def _registros(X):
    return [{k: (None if pd.isna(v) else v) for k, v in fila.items()} for fila in X.to_dict("records")]


def test_assets_corresponden_al_modelo_actual(clf):
    """Si alguien reentrena el RF sin volver a exportar, esta prueba lo detecta."""
    assert clf.rf["sha256_joblib"] == _sha256(RUTA_MODELO)
    assert clf.rf["n_arboles"] == 300 and clf.rf["n_variables"] == 17 == len(clf.pre["variables_entrada"])


def test_paridad_en_las_1200_gestantes(clf, modelos):
    """La inferencia desde JSON da las mismas probabilidades que scikit-learn en todo el dataset."""
    X, _ = separar_xy(marcar_fuera_de_rango(cargar_dataset()))
    rf = modelos["Random Forest"]
    esperado = rf.predict_proba(X)
    obtenido = np.array([clf.probabilidades(clf.vector(r)) for r in _registros(X)])
    assert np.abs(obtenido - esperado).max() <= TOLERANCIA
    pred_hibrido, _, _ = predecir_hibrido(rf, X)
    assert [clf.evaluar(r)["clase"] for r in _registros(X)] == pred_hibrido.tolist()


def test_casos_de_paridad_vigentes(casos, modelos):
    """Lo guardado en casos_paridad.json es lo que hoy responde scikit-learn."""
    entradas = pd.DataFrame([{k: (np.nan if v is None else v) for k, v in c["entrada"].items()} for c in casos["casos"]])
    proba = modelos["Random Forest"].predict_proba(entradas)
    guardado = np.array([c["probabilidades"] for c in casos["casos"]])
    assert len(casos["casos"]) == 200 and np.abs(proba - guardado).max() <= casos["tolerancia"]


def test_inferencia_json_reproduce_los_casos(clf, casos):
    """Es la misma prueba que correrá la app en Dart (flutter test)."""
    for c in casos["casos"]:
        res = clf.evaluar(c["entrada"])
        assert np.allclose(clf.vector(c["entrada"]), c["variables_entrada"], atol=casos["tolerancia"], rtol=0)
        assert np.allclose(res["probabilidades"], c["probabilidades"], atol=casos["tolerancia"], rtol=0)
        assert (res["clase_modelo"], res["clase"], res["origen"], len(res["reglas_activadas"])) == \
               (c["clase_modelo"], c["clase"], c["origen"], c["n_signos_criticos"]), c["id"]


def test_casos_cubren_todas_las_ramas(casos):
    cs = casos["casos"]
    assert {c["clase"] for c in cs} == {0, 1, 2}
    assert any(c["origen"] == "regla_clinica" and c["clase_modelo"] != 2 for c in cs)  # la regla corrige al modelo
    assert sum(c["entrada"]["glucosa_mgdl"] is None for c in cs) >= 20
    assert any(c["entrada"]["atendido_por"] not in ("Medico", "Enfermero(a)", "Auxiliar de enfermeria", "Partera tradicional") for c in cs)


@pytest.mark.parametrize("area, semanas, esperado", [
    ("Rural disperso", 10, 101.3),   # mediana del estrato área × trimestre
    ("Cabecera", 10, 99.2),          # Cabecera-T1 tiene pocos datos: mediana del área
    ("Desconocida", 20, 98.9),       # área desconocida: mediana global
    ("Cabecera", 43, 96.3),          # T3 llega hasta la semana 45
    ("Cabecera", 46, 99.2),          # fuera de los trimestres: mediana del área
])
def test_imputacion_por_estrato(clf, area, semanas, esperado):
    valores, faltantes = clf.imputar({"area_residencia": area, "semanas_gestacion": semanas, "glucosa_mgdl": None, "fcf_bpm": 140})
    assert valores["glucosa_mgdl"] == pytest.approx(esperado) and faltantes == {"glucosa_mgdl": True, "fcf_bpm": False}


def test_variable_obligatoria_faltante(clf):
    registro = {"edad": None, "area_residencia": "Cabecera", "semanas_gestacion": 28}
    with pytest.raises(ValueError, match="edad"):
        clf.vector(registro)


def test_reglas_json_coinciden_con_el_motor(clf):
    umbrales = {r["id"]: r.get("umbral") for r in clf.reglas["reglas"]}
    assert umbrales == {"pas_severa": UMBRAL_PAS_SEVERA, "pad_severa": UMBRAL_PAD_SEVERA,
                        "convulsiones": None, "proteinuria": UMBRAL_PROTEINURIA}
    assert set(clf.reglas["protocolo"]) == set(clf.rf["clases"])


def test_float32_como_scikit_learn():
    assert a_float32(0.1) != 0.1 and a_float32(0.1) == float(np.float32(0.1))


def test_catalogo_de_la_app_es_copia_exacta():
    """La app Flutter usa el mismo catálogo 3280 que el Módulo 1 (si se edita uno, hay que volver a exportar)."""
    assert (DIR_ASSETS / "variables_3280.json").read_bytes() == RUTA_CATALOGO.read_bytes()


def test_casos_de_alertas_vigentes():
    """Lo guardado en casos_alertas.json es lo que hoy calcula Python (la prueba de Dart compara contra esto)."""
    casos = json.loads((DIR_ASSETS / "casos_alertas.json").read_text(encoding="utf-8"))["casos"]
    assert len(casos) >= 150 and sum(bool(c["alertas"]) for c in casos) > 50
    for c in casos:
        assert evaluar_alertas_3280(c["entrada"]) == c["alertas"], c["id"]
        assert signos_alarma_que_escalan(c["entrada"]) == c["escalan"], c["id"]
    assert sum(bool(c["escalan"]) for c in casos) > 20
