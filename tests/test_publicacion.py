"""Fase 3, etapa 7: «Publicar al Módulo 2» (solo Random Forest), prueba de paridad, versiones y vuelta al oficial."""
import hashlib
import json
import shutil

import joblib
import numpy as np
import pandas as pd
import pytest

from src import experimentos, exportar_a_dart, publicacion
from src.config import DIR_MODELOS
from src.data_preprocessing import cargar_dataset, marcar_fuera_de_rango, separar_xy
from src.inferencia_json import ClasificadorJSON

OFICIAL = DIR_MODELOS / "modelo_random_forest.joblib"
RF_CHICO = {"n_estimators": 25, "max_depth": 8, "min_samples_leaf": 1, "max_features": 0.5, "balanceo": "SMOTE"}
JSON_DEL_MODELO = ["modelo_rf.json", "preproceso.json", "reglas.json", "casos_paridad.json", "casos_carga.json"]


def sha(ruta):
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    """Copia de los JSON de la app y carpetas propias: publicar aquí no toca el repositorio."""
    assets = tmp_path / "assets"
    shutil.copytree(exportar_a_dart.DIR_ASSETS, assets, ignore=shutil.ignore_patterns("fonts", "*.webp"))
    monkeypatch.setenv(exportar_a_dart.VARIABLE_ASSETS, str(assets))
    monkeypatch.setenv(publicacion.VARIABLE_DIRECTORIO, str(tmp_path / "publicados"))
    monkeypatch.setenv(experimentos.VARIABLE_DIRECTORIO, str(tmp_path / "experimentos"))
    return tmp_path


def test_sin_publicar_la_app_usa_el_modelo_oficial(entorno):
    actual = publicacion.publicado()
    assert actual["oficial"] and actual["version"] == "v1" and actual["ruta"] == OFICIAL and actual["sha256"] == sha(OFICIAL)
    assert publicacion.assets_vigentes() and publicacion.tabla_historial().empty
    with pytest.raises(ValueError, match="ya usa el modelo oficial"):
        publicacion.restablecer_oficial("ana")


def test_solo_se_publica_el_random_forest(entorno):
    originales = {n: sha(entorno / "assets" / n) for n in JSON_DEL_MODELO}
    for algoritmo in ("Regresión Logística", "SVM"):
        version = experimentos.entrenar(algoritmo)["registro"]["version"]
        with pytest.raises(ValueError, match="Solo se publica el Random Forest"):
            publicacion.publicar(version, "ana")
    with pytest.raises(ValueError, match="No existe la versión"):
        publicacion.publicar("exp-9999", "ana")
    # un rechazo no cambia nada: ni los JSON ni el manifiesto
    assert {n: sha(entorno / "assets" / n) for n in JSON_DEL_MODELO} == originales
    assert publicacion.publicado()["oficial"] and not (entorno / "publicados").exists()


def test_publicar_escribe_los_json_con_version_y_huella_y_comprueba_la_paridad(entorno):
    huella_oficial = sha(OFICIAL)
    originales = {n: (entorno / "assets" / n).read_bytes() for n in JSON_DEL_MODELO + ["variables_3280.json", "casos_alertas.json"]}
    registro = experimentos.entrenar("Random Forest", RF_CHICO, (80, 10, 10), 7, "ana")["registro"]
    resultado = publicacion.publicar(registro["version"], "ana")

    assert (resultado["version"], resultado["origen"], resultado["usuario"]) == ("v2", registro["version"], "ana")
    assert resultado["casos_paridad"] == 200 and resultado["dif_probabilidades"] <= exportar_a_dart.TOLERANCIA
    assert {a["Archivo"] for a in resultado["archivos"]} >= set(JSON_DEL_MODELO)
    # los JSON llevan la versión y la huella del modelo publicado, que quedó copiado aparte
    publicado = entorno / "publicados" / "v2_modelo_random_forest.joblib"
    modelo_json = json.loads((entorno / "assets" / "modelo_rf.json").read_text(encoding="utf-8"))
    assert modelo_json["version"] == "v2" and modelo_json["sha256_joblib"] == sha(publicado) == registro["sha256"]
    assert modelo_json["n_arboles"] == 25 and modelo_json["origen"] == publicado.name
    actual = publicacion.publicado()
    assert not actual["oficial"] and actual["version"] == "v2" and actual["ruta"] == publicado and publicacion.assets_vigentes()
    assert (actual["particion"], actual["semilla"], actual["val_f1_macro"]) == ("80/10/10", 7, registro["val_f1_macro"])

    # paridad: la inferencia desde los JSON publicados da lo mismo que scikit-learn en las 1.200 gestantes
    clf = ClasificadorJSON.desde_carpeta(entorno / "assets")
    X, _ = separar_xy(marcar_fuera_de_rango(cargar_dataset()))
    registros = [{k: (None if pd.isna(v) else v) for k, v in fila.items()} for fila in X.to_dict("records")]
    esperado = joblib.load(publicado).predict_proba(X)
    obtenido = np.array([clf.probabilidades(clf.vector(r)) for r in registros])
    assert np.abs(obtenido - esperado).max() <= exportar_a_dart.TOLERANCIA
    # las 4 reglas críticas y el catálogo 3280 van igual; lo oficial de la Fase 2 no se tocó
    assert (entorno / "assets" / "reglas.json").read_bytes() == originales["reglas.json"]
    assert (entorno / "assets" / "variables_3280.json").read_bytes() == originales["variables_3280.json"]
    assert (entorno / "assets" / "modelo_rf.json").read_bytes() != originales["modelo_rf.json"]
    assert sha(OFICIAL) == huella_oficial

    # volver al oficial deja TODOS los JSON idénticos, byte a byte, a como estaban
    publicacion.restablecer_oficial("luis")
    assert publicacion.publicado()["oficial"] and publicacion.assets_vigentes()
    for nombre, contenido in originales.items():
        assert (entorno / "assets" / nombre).read_bytes() == contenido, nombre
    # cada publicación tiene un número nuevo: no se reutiliza el v2 ni se pisa su archivo
    assert publicacion.publicar(registro["version"], "ana")["version"] == "v3"
    assert publicado.exists() and (entorno / "publicados" / "v3_modelo_random_forest.joblib").exists()
    historial = publicacion.tabla_historial()
    assert list(historial["Acción"]) == ["publicado", "restablecido", "publicado"]
    assert list(historial["Versión"]) == ["v3", "v1", "v2"] and list(historial["Usuario"]) == ["ana", "luis", "ana"]


def test_si_la_paridad_falla_no_se_publica(entorno, monkeypatch):
    registro = experimentos.entrenar("Random Forest", RF_CHICO)["registro"]
    original = (entorno / "assets" / "modelo_rf.json").read_bytes()

    def paridad_rota(*_):
        raise AssertionError("Diferencia mayor que 1e-06")

    monkeypatch.setattr(exportar_a_dart, "verificar", paridad_rota)
    with pytest.raises(ValueError, match="la prueba de paridad falló"):
        publicacion.publicar(registro["version"], "ana")
    assert (entorno / "assets" / "modelo_rf.json").read_bytes() == original
    assert publicacion.publicado()["oficial"] and not list((entorno / "publicados").glob("*.joblib"))


def test_la_exportacion_por_defecto_sigue_siendo_el_modelo_oficial(entorno):
    info = exportar_a_dart.exportar(exportado=publicacion._fecha_oficial())
    assert (info["version"], info["sha256"], info["n_arboles"], info["dif_probabilidades"]) == ("v1", sha(OFICIAL), 300, 0.0)
    for nombre in JSON_DEL_MODELO:
        assert (entorno / "assets" / nombre).read_bytes() == (exportar_a_dart.DIR_ASSETS / nombre).read_bytes(), nombre
