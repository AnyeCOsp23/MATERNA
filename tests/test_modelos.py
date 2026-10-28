"""Contrato de los modelos entrenados: salidas válidas, robustez, invariancias y reproducibilidad."""
import numpy as np
import pandas as pd
import pytest

from conftest import ETNIAS, MUNICIPIOS, RANGOS_UI, REGISTRO_SANO, a_dataframe, registros_aleatorios
from src.clinical_rules import predecir_hibrido
from src.config import DIR_METRICAS
from src.evaluate import calcular_metricas

NOMBRES = ["Regresión Logística", "SVM", "Random Forest"]


@pytest.mark.parametrize("nombre", NOMBRES)
def test_probabilidades_validas_en_prueba(modelos, particiones, nombre):
    P = modelos[nombre].predict_proba(particiones[2])
    assert P.shape == (180, 3)
    assert ((P >= 0) & (P <= 1)).all() and np.allclose(P.sum(axis=1), 1)


@pytest.mark.parametrize("nombre", NOMBRES)
def test_prediccion_determinista(modelos, particiones, nombre):
    X = particiones[2]
    assert np.array_equal(modelos[nombre].predict_proba(X), modelos[nombre].predict_proba(X))


@pytest.mark.parametrize("nombre", NOMBRES)
def test_fuzz_5000_entradas_de_la_interfaz(modelos, nombre):
    """Cualquier combinación que permita el formulario debe dar una predicción válida, sin errores."""
    X = a_dataframe(registros_aleatorios(5000, semilla=7))
    P = modelos[nombre].predict_proba(X)
    assert np.isfinite(P).all() and np.allclose(P.sum(axis=1), 1)


@pytest.mark.parametrize("nombre", NOMBRES)
@pytest.mark.parametrize("variable", list(RANGOS_UI))
def test_valores_en_los_bordes_de_la_interfaz(modelos, nombre, variable):
    lo, hi = RANGOS_UI[variable]
    P = modelos[nombre].predict_proba(a_dataframe([{**REGISTRO_SANO, variable: lo}, {**REGISTRO_SANO, variable: hi}]))
    assert np.isfinite(P).all() and np.allclose(P.sum(axis=1), 1)


@pytest.mark.parametrize("nombre", NOMBRES)
def test_sin_fcf_ni_glucosa(modelos, nombre):
    P = modelos[nombre].predict_proba(a_dataframe([{**REGISTRO_SANO, "fcf_bpm": None, "glucosa_mgdl": None}]))
    assert np.allclose(P.sum(), 1)


@pytest.mark.parametrize("nombre", NOMBRES)
def test_invariante_a_etnia_y_territorio(modelos, nombre):
    """Etnia, municipio y departamento no son entradas del modelo: cambiarlos no puede mover la predicción."""
    variantes = [{**REGISTRO_SANO, "pertenencia_etnica": e, "municipio": m, "departamento": d}
                 for e in ETNIAS for m, d in MUNICIPIOS.items()]
    P = modelos[nombre].predict_proba(a_dataframe(variantes))
    assert np.allclose(P, P[0])


def test_metricas_reportadas_son_reproducibles(modelo_principal, particiones, resumen):
    """Las cifras del informe deben salir de los modelos versionados, no de una corrida anterior."""
    _, _, X_test, _, _, y_test = particiones
    pred, proba, _ = predecir_hibrido(modelo_principal, X_test)
    m = calcular_metricas(y_test, pred, proba)
    reportado = pd.read_csv(DIR_METRICAS / "metricas_test.csv", index_col=0).loc[resumen["sistema_principal"]]
    for clave in ["accuracy", "f1_macro", "recall_alto", "roc_auc_ovr_macro"]:
        assert m[clave] == pytest.approx(float(reportado[clave]), abs=1e-4)
