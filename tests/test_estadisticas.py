"""Fase 3: estadísticas descriptivas del EDA (fase 03) que se actualizan con los patrones nuevos."""
import shutil

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from conftest import RAIZ
from src import estadisticas, experimentos, patrones
from src.data_preprocessing import cargar_dataset
from src.exportar_a_dart import DIR_ASSETS

PAGINA = str(RAIZ / "paginas" / "laboratorio.py")
REGISTRO = dict(edad=31, semanas_gestacion=30, n_controles_prenatales=2, pas_mmhg=150, pad_mmhg=96, fcf_bpm=None,
                glucosa_mgdl=130.5, proteinuria=1, convulsiones=0, area_residencia="Rural disperso",
                atendido_por="Partera tradicional")
ETIQUETAS = {"edad": "Edad (años)", "glucosa_mgdl": "Glucosa (mg/dL)", "proteinuria": "Proteinuria (cruces)"}


def test_calculos_sobre_datos_conocidos():
    datos = pd.DataFrame({"edad": [20, 20, 30, 40, None], "glucosa_mgdl": [90.4, 89.6, 120.2, 60.0, 60.0],
                          "proteinuria": [0, 0, 1, 2, 0]})
    t = estadisticas.descriptivas(datos, ETIQUETAS).set_index("Variable")
    edad = t.loc["Edad (años)"]
    assert (edad["N"], edad["Media"], edad["Mediana"], edad["Moda"], edad["Veces (moda)"]) == (4, 27.5, 25.0, 20.0, 2)
    assert edad["Desv. estándar"] == round(pd.Series([20, 20, 30, 40]).std(), 2) == 9.57  # muestral (n - 1)
    assert (edad["Mínimo"], edad["Máximo"], edad["% nulos"]) == (20, 40, 20.0)
    # glucosa con decimales: la moda se toma con enteros (90,4 y 89,6 -> 90 empatan con 60 dos veces; gana la menor)
    assert t.loc["Glucosa (mg/dL)", "Moda"] == 60.0 and t.loc["Glucosa (mg/dL)", "Veces (moda)"] == 2
    # el piso solo se avisa en mediciones continuas, no en la proteinuria (donde lo normal es 0)
    assert estadisticas.moda_en_el_minimo(t.reset_index(), ETIQUETAS) == ["Glucosa (mg/dL)"]


def test_moda_sin_datos_y_columna_ausente():
    assert estadisticas.moda(pd.Series([None, None], dtype=float)) == (None, 0)
    assert estadisticas.descriptivas(pd.DataFrame({"edad": [25]}), {"pas_mmhg": "PAS"}).empty


def test_dataset_base():
    t = estadisticas.descriptivas(cargar_dataset(), {"glucosa_mgdl": "Glucosa", "fcf_bpm": "FCF"}).set_index("Variable")
    assert t.loc["Glucosa", "N"] == 1041 and t.loc["FCF", "N"] == 1111      # los nulos no cuentan
    assert t.loc["Glucosa", "Moda"] == 60 and t.loc["Glucosa", "Veces (moda)"] == 43  # el piso del dataset sintético


def test_combinar_suma_los_patrones():
    base = cargar_dataset()
    nuevos = pd.DataFrame([{**REGISTRO, "riesgo_obstetrico": "Riesgo Medio", "origen": "patron_manual"}])
    juntos = estadisticas.combinar(base, nuevos)
    assert len(juntos) == len(base) + 1 and list(juntos.columns) == list(base.columns)
    assert estadisticas.combinar(base, pd.DataFrame()) is base


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    monkeypatch.setenv(experimentos.VARIABLE_DIRECTORIO, str(tmp_path / "experimentos"))
    monkeypatch.setenv("MATERNA_BD", str(tmp_path / "triaje.sqlite"))
    monkeypatch.setenv("MATERNA_BD_IPS", str(tmp_path / "laboratorio.sqlite"))
    shutil.copytree(DIR_ASSETS, tmp_path / "assets", ignore=shutil.ignore_patterns("fonts", "*.webp"))
    monkeypatch.setenv("MATERNA_ASSETS", str(tmp_path / "assets"))
    monkeypatch.setenv("MATERNA_PUBLICACION", str(tmp_path / "publicados"))
    return tmp_path


def fase_eda():
    at = AppTest.from_file(PAGINA, default_timeout=180)
    at.session_state["usuario"] = {"usuario": "admin", "nombre": "Admin", "rol": "administrador"}
    at.session_state["vista"] = "03"
    return at.run()


def tabla_descriptiva(at):
    return next(d.value for d in at.dataframe if "Desv. estándar" in d.value)


def test_la_tabla_se_actualiza_al_agregar_un_patron(entorno):
    at = fase_eda()
    assert not at.exception
    antes = tabla_descriptiva(at).set_index("Variable")
    assert antes.loc["Edad (años)", "N"] == 1200
    assert any("1.200 gestantes" in m.value for m in at.markdown)

    patrones.agregar(REGISTRO, "Riesgo Medio", "admin", cargar_dataset())
    at.run()
    despues = tabla_descriptiva(at).set_index("Variable")
    assert despues.loc["Edad (años)", "N"] == 1201 and despues.loc["PAS (mmHg)", "Máximo"] >= 150
    assert any("1.201 gestantes" in m.value for m in at.markdown)
    assert any("1 patrón(es) nuevo(s)" in c.value for c in at.caption)


def test_filtrar_por_clase(entorno):
    at = fase_eda()
    at.segmented_control(key="eda_grupo").set_value("Alto Riesgo").run()
    assert not at.exception and tabla_descriptiva(at).set_index("Variable").loc["Edad (años)", "N"] == 152
