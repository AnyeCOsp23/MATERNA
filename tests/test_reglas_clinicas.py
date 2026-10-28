"""Motor de reglas: umbrales exactos, valores faltantes y coherencia con el modelo."""
import numpy as np
import pandas as pd
import pytest

from conftest import REGISTRO_SANO, a_dataframe, registros_aleatorios
from src.clinical_rules import (
    PROTOCOLO, evaluar_reglas, evaluar_riesgo_hibrido, mascara_reglas, predecir_hibrido,
)
from src.config import CLASE_ALTO, NOMBRES_CLASES
from src.data_preprocessing import cargar_dataset


@pytest.mark.parametrize("variable, valor, dispara", [
    ("pas_mmhg", 159, False), ("pas_mmhg", 160, True), ("pas_mmhg", 250, True),
    ("pad_mmhg", 109, False), ("pad_mmhg", 110, True),
    ("proteinuria", 1, False), ("proteinuria", 2, True),
    ("convulsiones", 0, False), ("convulsiones", 1, True), ("convulsiones", True, True), ("convulsiones", False, False),
])
def test_umbral_exacto(variable, valor, dispara):
    assert bool(evaluar_reglas({**REGISTRO_SANO, variable: valor})) is dispara


def test_sin_alertas_en_gestante_sana():
    assert evaluar_reglas(REGISTRO_SANO) == []


def test_varias_alertas_se_listan_todas():
    alertas = evaluar_reglas({**REGISTRO_SANO, "pas_mmhg": 170, "pad_mmhg": 115, "proteinuria": 2, "convulsiones": 1})
    assert len(alertas) == 4


@pytest.mark.parametrize("variable", ["pas_mmhg", "pad_mmhg", "proteinuria"])
@pytest.mark.parametrize("vacio", [None, np.nan])
def test_valor_faltante_no_dispara_ni_falla(variable, vacio):
    assert evaluar_reglas({**REGISTRO_SANO, variable: vacio}) == []


def test_version_vectorizada_igual_a_la_individual():
    df = cargar_dataset()
    individual = np.array([bool(evaluar_reglas(fila)) for fila in df.to_dict("records")])
    assert (mascara_reglas(df) == individual).all()


def test_contrato_del_dataset_signos_criticos_son_alto_riesgo():
    """Supuesto documentado en el informe: el etiquetado sintético usa los mismos umbrales."""
    df = cargar_dataset()
    assert (df.loc[mascara_reglas(df), "riesgo_obstetrico"] == "Alto Riesgo").all()


def test_regla_sobrescribe_al_modelo(modelo_principal):
    r = evaluar_riesgo_hibrido({**REGISTRO_SANO, "pas_mmhg": 165}, modelo_principal)
    assert r.categoria == "Alto Riesgo" and r.origen == "regla_clinica" and r.alertas
    assert r.categoria_modelo in NOMBRES_CLASES


def test_sin_regla_decide_el_modelo(modelo_principal):
    r = evaluar_riesgo_hibrido(REGISTRO_SANO, modelo_principal)
    esperado = NOMBRES_CLASES[int(np.argmax(modelo_principal.predict_proba(a_dataframe([REGISTRO_SANO]))[0]))]
    assert r.origen == "modelo_ml" and r.categoria == esperado == r.categoria_modelo


def test_probabilidades_validas(modelo_principal):
    r = evaluar_riesgo_hibrido(REGISTRO_SANO, modelo_principal)
    assert set(r.probabilidades_modelo) == set(NOMBRES_CLASES)
    assert sum(r.probabilidades_modelo.values()) == pytest.approx(1.0, abs=1e-6)


def test_hibrido_vectorizado_igual_al_individual(modelo_principal, particiones):
    X_test = particiones[2]
    pred, proba, activa = predecir_hibrido(modelo_principal, X_test)
    for i, fila in enumerate(X_test.to_dict("records")):
        registro = {k: (None if pd.isna(v) else v) for k, v in fila.items()}
        assert NOMBRES_CLASES[pred[i]] == evaluar_riesgo_hibrido(registro, modelo_principal).categoria
    assert (proba[activa] == np.eye(3)[CLASE_ALTO]).all()


def test_propiedad_toda_regla_activa_termina_en_alto(modelo_principal):
    """2.000 entradas aleatorias: si hay signo crítico, el resultado es siempre Alto Riesgo."""
    X = a_dataframe(registros_aleatorios(2000, semilla=1))
    pred, _, activa = predecir_hibrido(modelo_principal, X)
    assert activa.sum() > 500
    assert (pred[activa] == CLASE_ALTO).all()


def test_hay_protocolo_para_cada_categoria():
    assert set(PROTOCOLO) == set(NOMBRES_CLASES) and all(len(p) >= 3 for p in PROTOCOLO.values())
