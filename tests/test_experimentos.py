"""Fase 3, etapa 3: partición parametrizable, parametrización de los modelos y registro versionado de experimentos."""
import hashlib

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.model_selection import train_test_split

from src import experimentos
from src.config import CLASE_ALTO, DIR_MODELOS
from src.data_preprocessing import (
    PARTICION_OFICIAL, cargar_dataset, marcar_fuera_de_rango, particionar, separar_xy, validar_proporciones,
)

RUTA_EN_USO = DIR_MODELOS / "modelo_random_forest.joblib"


@pytest.fixture(scope="module")
def xy():
    return separar_xy(marcar_fuera_de_rango(cargar_dataset()))


@pytest.fixture
def carpeta(tmp_path, monkeypatch):
    monkeypatch.setenv(experimentos.VARIABLE_DIRECTORIO, str(tmp_path / "experimentos"))
    return tmp_path / "experimentos"


def sha(ruta):
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


# ------------------------------------------------------------------ partición
@pytest.mark.parametrize("proporciones", [(70, 15, 15), (80, 10, 10), (60, 20, 20), (50, 25, 25)])
def test_particion_respeta_los_porcentajes(xy, proporciones):
    X, y = xy
    X_train, X_val, X_test, y_train, y_val, y_test = particionar(X, y, 42, proporciones)
    assert [len(X_train), len(X_val), len(X_test)] == [len(X) * p // 100 for p in proporciones]
    assert len(X_train) + len(X_val) + len(X_test) == len(X)
    indices = [set(p.index) for p in (X_train, X_val, X_test)]
    assert not (indices[0] & indices[1] or indices[0] & indices[2] or indices[1] & indices[2])
    # estratificada: la proporción de Alto Riesgo es casi la misma en los tres conjuntos
    global_alto = (y == CLASE_ALTO).mean()
    for yp in (y_train, y_val, y_test):
        assert abs((yp == CLASE_ALTO).mean() - global_alto) < 0.01


@pytest.mark.parametrize("proporciones", [(70, 15, 10), (70, 20, 20), (100, 0, 0), (70, 30), (69.5, 15.5, 15)])
def test_particion_rechaza_porcentajes_que_no_suman_100_o_no_validos(xy, proporciones):
    with pytest.raises(ValueError):
        validar_proporciones(proporciones)
    with pytest.raises(ValueError):
        particionar(*xy, 42, proporciones)


def test_la_particion_por_defecto_sigue_siendo_la_oficial(xy):
    X, y = xy
    assert PARTICION_OFICIAL == (70, 15, 15)
    X_train, X_tmp, _, y_tmp = train_test_split(X, y, test_size=0.30, stratify=y, random_state=42)
    X_val, X_test, _, _ = train_test_split(X_tmp, y_tmp, test_size=0.50, stratify=y_tmp, random_state=42)
    nuevas = particionar(X, y)
    for antes, ahora in zip((X_train, X_val, X_test), nuevas[:3]):
        assert list(antes.index) == list(ahora.index)


def test_la_semilla_cambia_la_particion_y_es_reproducible(xy):
    a, b, c = particionar(*xy, 7), particionar(*xy, 7), particionar(*xy, 8)
    assert list(a[0].index) == list(b[0].index) != list(c[0].index)


# ------------------------------------------------------------------ hiperparámetros
@pytest.mark.parametrize("algoritmo", experimentos.ALGORITMOS)
def test_los_hiperparametros_base_son_validos(algoritmo):
    experimentos.validar_hiperparametros(algoritmo, experimentos.hiperparametros_base(algoritmo))


@pytest.mark.parametrize("algoritmo, hiperparametros", [
    ("Random Forest", {"n_estimators": 0, "balanceo": "SMOTE"}),
    ("Random Forest", {"n_estimators": 100.5, "balanceo": "SMOTE"}),
    ("Random Forest", {"max_features": 1.5, "balanceo": "SMOTE"}),
    ("Random Forest", {"C": 1.0, "balanceo": "SMOTE"}),  # no es de este algoritmo
    ("Regresión Logística", {"C": -1, "balanceo": "class_weight"}),
    ("Regresión Logística", {"C": 1.0}),  # falta el balanceo
    ("Regresión Logística", {"C": 1.0, "balanceo": "los dos"}),
    ("SVM", {"kernel": "sigmoide", "C": 1, "balanceo": "SMOTE"}),
    ("Red neuronal", {"balanceo": "SMOTE"}),
])
def test_rechaza_configuraciones_no_validas(algoritmo, hiperparametros):
    with pytest.raises(ValueError):
        experimentos.validar_hiperparametros(algoritmo, hiperparametros)


def test_smote_y_pesos_nunca_juntos():
    con_smote = experimentos.construir("Regresión Logística", {"C": 1.0, "balanceo": "SMOTE"})
    con_pesos = experimentos.construir("Regresión Logística", {"C": 1.0, "balanceo": "class_weight"})
    assert con_smote.named_steps["balanceo"] != "passthrough" and con_smote.named_steps["modelo"].class_weight is None
    assert con_pesos.named_steps["balanceo"] == "passthrough" and con_pesos.named_steps["modelo"].class_weight == "balanced"


# ------------------------------------------------------------------ entrenamiento y versiones
def test_random_forest_base_reproduce_el_modelo_en_uso_sin_tocarlo(carpeta, resumen):
    huella = sha(RUTA_EN_USO)
    resultado = experimentos.entrenar("Random Forest", usuario="prueba")
    r = resultado["registro"]
    assert resultado["identico_al_modelo_en_uso"] and r["identico_al_modelo_en_uso"]
    assert (r["version"], r["particion"], r["semilla"], r["usuario"]) == ("exp-0001", "70/15/15", 42, "prueba")
    assert (r["n_entrenamiento"], r["n_validacion"], r["n_prueba"]) == (840, 180, 180)
    # las mismas cifras oficiales de la Fase 2 en prueba
    oficial = pd.read_csv(DIR_MODELOS.parent / "reports" / "metrics" / "metricas_test.csv").set_index("sistema")
    oficial = oficial.loc["Híbrido (Random Forest + reglas)"]
    assert r["prueba_f1_macro"] == pytest.approx(oficial["f1_macro"], abs=1e-4)
    assert r["prueba_recall_alto"] == pytest.approx(oficial["recall_alto"], abs=1e-4)
    # el modelo en uso no cambió y la versión quedó aparte, con su huella
    assert sha(RUTA_EN_USO) == huella
    ruta = carpeta / "modelos" / "exp-0001.joblib"
    assert r["sha256"] == sha(ruta)
    X_test = particionar(*separar_xy(marcar_fuera_de_rango(cargar_dataset())))[2]
    assert np.array_equal(experimentos.cargar_modelo("exp-0001").predict_proba(X_test), joblib.load(RUTA_EN_USO).predict_proba(X_test))


def test_cada_entrenamiento_crea_una_version_nueva_y_nunca_sobrescribe(carpeta):
    primera = experimentos.entrenar("Regresión Logística", usuario="ana")["registro"]
    huella = sha(carpeta / "modelos" / "exp-0001.joblib")
    segunda = experimentos.entrenar("Regresión Logística", {"C": 0.1, "balanceo": "SMOTE"}, (80, 10, 10), 7, "luis")["registro"]
    tercera = experimentos.entrenar("SVM", usuario="ana")["registro"]
    assert [primera["version"], segunda["version"], tercera["version"]] == ["exp-0001", "exp-0002", "exp-0003"]
    assert sha(carpeta / "modelos" / "exp-0001.joblib") == huella
    tabla = experimentos.tabla_registro()
    assert list(tabla["version"]) == ["exp-0001", "exp-0002", "exp-0003"]
    assert list(tabla["usuario"]) == ["ana", "luis", "ana"] and list(tabla["particion"]) == ["70/15/15", "80/10/10", "70/15/15"]
    assert tabla.loc[1, "semilla"] == 7 and tabla.loc[1, "balanceo"] == "SMOTE" and tabla.loc[1, "hiperparametros"] == "C=0.1"
    assert tabla.loc[1, "n_entrenamiento"] == 960
    for columna in ("fecha", "cv_f1_macro", "val_f1_macro", "val_recall_alto", "prueba_f1_macro", "tiempo_s", "sha256"):
        assert tabla[columna].notna().all(), columna
    # si el registro se perdiera, el número de versión sigue sin repetirse (los archivos mandan)
    (carpeta / "registro.jsonl").unlink()
    assert experimentos.entrenar("Regresión Logística")["registro"]["version"] == "exp-0004"


def test_la_misma_configuracion_y_semilla_dan_las_mismas_metricas(carpeta):
    a = experimentos.entrenar("Regresión Logística", {"C": 1.0, "balanceo": "SMOTE"}, (60, 20, 20), 3)["registro"]
    b = experimentos.entrenar("Regresión Logística", {"C": 1.0, "balanceo": "SMOTE"}, (60, 20, 20), 3)["registro"]
    for columna in ("cv_f1_macro", "val_f1_macro", "val_recall_alto", "prueba_f1_macro"):
        assert a[columna] == b[columna], columna


def test_una_configuracion_no_valida_no_deja_version(carpeta):
    with pytest.raises(ValueError):
        experimentos.entrenar("Regresión Logística", {"C": -5, "balanceo": "SMOTE"})
    with pytest.raises(ValueError):
        experimentos.entrenar("Regresión Logística", proporciones=(70, 20, 20))
    assert experimentos.tabla_registro().empty and not list(carpeta.glob("modelos/*.joblib"))


def test_criterio_de_seleccion():
    tabla = pd.DataFrame({
        "version": ["exp-0001", "exp-0002", "exp-0003", "exp-0004"],
        "val_f1_macro": [0.90, 0.94, 0.94, 0.94],
        "val_recall_alto": [0.99, 0.91, 0.95, 0.95],
    })
    # mayor F1-macro en validación; en empate, mayor recall de Alto; si persiste, la más antigua
    assert experimentos.mejor_version(tabla) == "exp-0003"
    assert experimentos.mejor_version(pd.DataFrame()) is None


def test_curva_de_aprendizaje_de_una_version(carpeta):
    experimentos.entrenar("Regresión Logística", proporciones=(80, 10, 10), semilla=5)
    curva = experimentos.curva_aprendizaje("exp-0001")
    assert len(curva) == 7 and curva["n_entrenamiento"].is_monotonic_increasing
    assert curva["n_entrenamiento"].iloc[-1] == 960 * 4 // 5  # 4 de las 5 particiones del entrenamiento
    assert curva[["f1_entrenamiento", "f1_cv"]].apply(lambda s: s.between(0, 1)).all().all()
    with pytest.raises(ValueError):
        experimentos.curva_aprendizaje("exp-9999")
