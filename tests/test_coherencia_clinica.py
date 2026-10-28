"""Pruebas de aceptación clínica del modelo principal (sin reglas de sobreescritura).

Referencia: en el dataset, Bajo Riesgo exige CERO factores de riesgo; un solo factor implica al
menos Riesgo Medio (verificado: 0 de 578 gestantes de Bajo Riesgo tienen alguno de estos factores).
Cada prueba cambia UNA variable de una gestante sana y comprueba que el modelo deja de decir Bajo.
"""
import numpy as np
import pytest

from conftest import REGISTRO_SANO, a_dataframe
from src.data_preprocessing import cargar_dataset

pytestmark = pytest.mark.coherencia

FACTOR_UNICO = [
    ("HTA sistólica 140", {"pas_mmhg": 140}),
    ("HTA sistólica 145", {"pas_mmhg": 145}),
    ("HTA diastólica 90", {"pad_mmhg": 90}),
    ("HTA diastólica 95", {"pad_mmhg": 95}),
    ("Glucosa 140", {"glucosa_mgdl": 140.0}),
    ("Glucosa 145", {"glucosa_mgdl": 145.0}),
    ("FCF 105 (bradicardia)", {"fcf_bpm": 105.0}),
    ("FCF 165 (taquicardia)", {"fcf_bpm": 165.0}),
    ("Sin controles prenatales", {"n_controles_prenatales": 0}),
    ("Proteinuria +", {"proteinuria": 1}),
    ("Edad 15", {"edad": 15}),
    ("Edad 36", {"edad": 36}),
    ("Edad 40", {"edad": 40}),
]


def clase(modelo, cambios):
    return int(np.argmax(modelo.predict_proba(a_dataframe([{**REGISTRO_SANO, **cambios}]))[0]))


def test_referencia_del_dataset():
    df = cargar_dataset()
    bajo = df[df["riesgo_obstetrico"] == "Bajo Riesgo"]
    factores = ((bajo.pas_mmhg >= 140) | (bajo.pad_mmhg >= 90) | (bajo.glucosa_mgdl >= 140) | (bajo.fcf_bpm < 110)
                | (bajo.fcf_bpm > 160) | (bajo.n_controles_prenatales == 0) | (bajo.proteinuria >= 1)
                | (bajo.edad < 16) | (bajo.edad > 35))
    assert factores.sum() == 0


def test_gestante_sana_es_bajo_riesgo(modelo_principal):
    assert clase(modelo_principal, {}) == 0


@pytest.mark.parametrize("nombre, cambios", FACTOR_UNICO, ids=[f[0] for f in FACTOR_UNICO])
def test_un_factor_de_riesgo_no_es_bajo_riesgo(modelo_principal, nombre, cambios):
    assert clase(modelo_principal, cambios) >= 1, f"{nombre}: el modelo dice Bajo Riesgo"


@pytest.mark.parametrize("cambios", [{"n_controles_prenatales": 20}, {"n_controles_prenatales": 12}],
                         ids=["20 controles", "12 controles"])
def test_mas_controles_fuera_de_rango_no_inventa_alto_riesgo(modelo_principal, cambios):
    """El dataset solo llega a 6 controles: extrapolar no debe producir Alto Riesgo en una gestante sana."""
    assert clase(modelo_principal, cambios) != 2
