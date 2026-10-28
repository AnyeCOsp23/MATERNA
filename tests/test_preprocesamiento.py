"""Carga, partición e imputación: integridad de datos y ausencia de fuga de información."""
import numpy as np
import pandas as pd
import pytest

from conftest import REGISTRO_SANO, a_dataframe
from src.data_preprocessing import (
    MedianaEstratificadaImputer, cargar_dataset, construir_preprocesador, marcar_fuera_de_rango,
    preparar_datos, reporte_calidad, trimestre,
)


def test_carga_limpia_el_csv():
    df = cargar_dataset()
    assert df.shape == (1200, 16)
    assert not df.columns.str.startswith("Unnamed").any()
    assert set(df["convulsiones"].unique()) <= {0, 1}


def test_reporte_de_calidad_coincide_con_el_eda():
    r = reporte_calidad(cargar_dataset())
    assert r["nulos"] == {"fcf_bpm": 89, "glucosa_mgdl": 159}
    assert r["ids_duplicados"] == 0 and r["filas_duplicadas_sin_id"] == 0
    assert r["fuera_de_rango_fisiologico"] == {}


def test_valores_imposibles_se_vuelven_nulos():
    df = cargar_dataset().head(3).copy()
    df.loc[df.index[0], "pas_mmhg"] = 999
    df.loc[df.index[1], "fcf_bpm"] = 5
    marcado = marcar_fuera_de_rango(df)
    assert marcado["pas_mmhg"].isna().sum() == 1 and marcado["fcf_bpm"].isna().sum() >= 1


def test_particion_70_15_15_estratificada_y_disjunta(particiones):
    X_train, X_val, X_test, y_train, y_val, y_test = particiones
    assert (len(X_train), len(X_val), len(X_test)) == (840, 180, 180)
    assert not (set(X_train.index) & set(X_val.index) or set(X_train.index) & set(X_test.index) or set(X_val.index) & set(X_test.index))
    for y in (y_train, y_val, y_test):
        assert abs((y == 2).mean() - 152 / 1200) < 0.01


def test_particion_reproducible():
    a, b = preparar_datos(guardar=False), preparar_datos(guardar=False)
    assert list(a[2].index) == list(b[2].index)


def test_imputador_aprende_solo_de_entrenamiento(particiones):
    X_train, X_val = particiones[0], particiones[1]
    imp = MedianaEstratificadaImputer().fit(X_train)
    assert imp.mediana_global_["glucosa_mgdl"] == pytest.approx(X_train["glucosa_mgdl"].median())
    antes = dict(imp.mediana_global_)
    imp.transform(X_val)
    assert imp.mediana_global_ == antes


def test_imputador_usa_mediana_del_estrato(particiones):
    X_train = particiones[0]
    imp = MedianaEstratificadaImputer().fit(X_train)
    fila = a_dataframe([{**REGISTRO_SANO, "area_residencia": "Rural disperso", "semanas_gestacion": 30, "glucosa_mgdl": None}])
    mask = (X_train["area_residencia"] == "Rural disperso") & (trimestre(X_train["semanas_gestacion"]) == "T3")
    assert imp.transform(fila)["glucosa_mgdl"].iloc[0] == pytest.approx(X_train.loc[mask, "glucosa_mgdl"].median())


def test_imputador_recurre_a_mediana_global_si_el_estrato_es_pequeno():
    X = a_dataframe([{**REGISTRO_SANO, "glucosa_mgdl": float(v)} for v in range(80, 100)])
    imp = MedianaEstratificadaImputer(min_tamano=50).fit(X)
    fila = a_dataframe([{**REGISTRO_SANO, "glucosa_mgdl": None}])
    assert imp.transform(fila)["glucosa_mgdl"].iloc[0] == pytest.approx(89.5)


def test_imputador_crea_indicadores_de_no_disponible():
    imp = MedianaEstratificadaImputer().fit(a_dataframe([REGISTRO_SANO] * 20))
    out = imp.transform(a_dataframe([{**REGISTRO_SANO, "fcf_bpm": None}, REGISTRO_SANO]))
    assert list(out["fcf_no_disponible"]) == [1, 0] and list(out["glucosa_no_disponible"]) == [0, 0]
    assert not out[["fcf_bpm", "glucosa_mgdl"]].isna().any().any()


def test_regresion_columna_entera_sin_nulos():
    """Bug encontrado en pruebas: glucosa=100 (entero) sin nulos hacía fallar la imputación en pandas 3."""
    imp = MedianaEstratificadaImputer().fit(a_dataframe([REGISTRO_SANO] * 20))
    X = pd.DataFrame([{**REGISTRO_SANO, "glucosa_mgdl": 100, "fcf_bpm": 140}])
    assert X["glucosa_mgdl"].dtype.kind == "i"
    assert imp.transform(X)["glucosa_mgdl"].iloc[0] == 100


def test_preprocesador_produce_17_variables_finitas(particiones):
    X_train, X_test = particiones[0], particiones[2]
    pre = construir_preprocesador().fit(X_train)
    Xt = pre.transform(X_test)
    assert Xt.shape == (180, 17) and np.isfinite(Xt).all()


def test_categoria_desconocida_no_rompe_el_pipeline(particiones):
    pre = construir_preprocesador().fit(particiones[0])
    Xt = pre.transform(a_dataframe([{**REGISTRO_SANO, "atendido_por": "Promotora de salud", "area_residencia": "Otra"}]))
    assert np.isfinite(Xt).all()
