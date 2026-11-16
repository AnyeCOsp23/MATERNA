"""Página de triaje de la consola (app_demo.py -> paginas/triaje.py) con el simulador de Streamlit."""
import sqlite3

import pytest
from streamlit.testing.v1 import AppTest

from conftest import RAIZ

APP = str(RAIZ / "app_demo.py")
USUARIO_PRUEBA = {"usuario": "prueba", "nombre": "Usuario de prueba", "rol": "administrador"}


@pytest.fixture
def app(tmp_path, monkeypatch):
    bd = tmp_path / "registros.sqlite"
    monkeypatch.setenv("MATERNA_BD", str(bd))
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["bienvenida_mostrada"] = True  # el simulador no ejecuta JavaScript: ver test_bienvenida_*
    at.session_state["usuario"] = USUARIO_PRUEBA  # sesión iniciada: el login se prueba en test_consola.py
    at.switch_page("paginas/triaje.py")  # la página de inicio es el laboratorio (Módulo 1)
    at.run()
    assert not at.exception
    at.bd = bd
    return at


def widget(lista, inicio):
    return next(w for w in lista if w.label.startswith(inicio))


def evaluar(at):
    next(b for b in at.button if b.label == "Evaluar riesgo materno").click().run()
    assert not at.exception
    return at


def resultado(at):
    """Devuelve (categoría, origen) leyendo la tarjeta de resultado renderizada."""
    html = next(m.value for m in at.markdown if "mt-result" in m.value and "<style>" not in m.value)
    categoria = next(c for c in ("alto", "medio", "bajo") if f"mt-result {c}" in html)
    origen = "regla" if "Regla clínica GPC" in html else "modelo"
    return categoria, origen


def cargar_caso(at, numero):
    next(b for b in at.sidebar.button if b.label.startswith(f"Caso {numero}")).click().run()  # por nombre: antes va el menú de fases
    return at


def bienvenidas(at):
    return [e for e in at.main if getattr(e, "type", None) == "bidi_component"]


def test_bienvenida_es_lo_unico_de_la_primera_ejecucion(tmp_path, monkeypatch):
    """Al abrir la página solo se envía la capa del logo: ni login ni contenido pueden asomar antes."""
    monkeypatch.setenv("MATERNA_BD", str(tmp_path / "registros.sqlite"))
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception
    assert len(bienvenidas(at)) == 1
    assert not at.text_input and not at.button and not at.markdown and not at.sidebar.children


def test_bienvenida_no_reaparece(app):
    assert bienvenidas(app) == []  # ya se mostró en esta sesión
    cargar_caso(app, 3)  # cualquier interacción vuelve a ejecutar el script
    assert bienvenidas(app) == []


def test_carga_inicial_con_encabezado_y_metricas(app):
    textos = " ".join(m.value for m in app.markdown)
    assert "MATERNA" in textos and "F1-macro" in textos and "Recall Alto" in textos


@pytest.mark.parametrize("numero, esperado", [(1, ("alto", "regla")), (2, ("medio", "modelo")), (3, ("bajo", "modelo"))])
def test_casos_de_demostracion(app, numero, esperado):
    assert resultado(evaluar(cargar_caso(app, numero))) == esperado


@pytest.mark.parametrize("etiqueta, valor, esperado", [
    ("Presión sistólica", 159, "modelo"), ("Presión sistólica", 160, "regla"),
    ("Presión diastólica", 109, "modelo"), ("Presión diastólica", 110, "regla"),
])
def test_umbral_de_presion_desde_el_formulario(app, etiqueta, valor, esperado):
    cargar_caso(app, 3)
    widget(app.number_input, etiqueta).set_value(valor)
    categoria, origen = resultado(evaluar(app))
    assert origen == esperado
    if esperado == "regla":
        assert categoria == "alto"


def test_convulsiones_desde_el_formulario(app):
    cargar_caso(app, 3)
    widget(app.radio, "Convulsiones").set_value("Sí")
    assert resultado(evaluar(app)) == ("alto", "regla")


@pytest.mark.parametrize("nivel, origen", [(0, "modelo"), (1, "modelo"), (2, "regla")])
def test_proteinuria_desde_el_formulario(app, nivel, origen):
    cargar_caso(app, 3)
    widget(app.select_slider, "Proteinuria").set_value(nivel)
    assert resultado(evaluar(app))[1] == origen


def test_datos_no_disponibles_muestran_aviso(app):
    cargar_caso(app, 3)
    widget(app.checkbox, "FCF no disponible").check()
    widget(app.checkbox, "Glucosa no disponible").check()
    evaluar(app)
    assert any("Sin dato de FCF y glucosa" in m.value for m in app.markdown)


def test_cambio_de_modelo_a_regresion_logistica(app):
    widget(app.sidebar.selectbox, "Modelo").set_value("Regresión Logística").run()
    evaluar(cargar_caso(app, 3))
    assert any("Inferencia del modelo · Regresión Logística" in m.value for m in app.markdown)


@pytest.mark.parametrize("etiqueta, valor", [
    ("Edad", 10), ("Edad", 55), ("Semanas", 4), ("Semanas", 42), ("Controles", 0), ("Controles", 20),
    ("Presión sistólica", 60), ("Presión sistólica", 250), ("Presión diastólica", 30), ("Presión diastólica", 150),
    ("Frecuencia cardiaca fetal", 60.0), ("Frecuencia cardiaca fetal", 220.0), ("Glucosa (mg/dL)", 30.0), ("Glucosa (mg/dL)", 600.0),
])
def test_valores_extremos_del_formulario_no_rompen_la_app(app, etiqueta, valor):
    cargar_caso(app, 3)
    widget(app.number_input, etiqueta).set_value(valor)
    assert resultado(evaluar(app))[0] in {"alto", "medio", "bajo"}


def test_cada_evaluacion_se_guarda_y_se_sincroniza(app):
    for numero in (1, 2, 3):
        evaluar(cargar_caso(app, numero))
    with sqlite3.connect(app.bd) as con:
        filas = con.execute("SELECT categoria, origen, sincronizado FROM evaluaciones ORDER BY id").fetchall()
    assert [f[:2] for f in filas] == [("Alto Riesgo", "regla_clinica"), ("Riesgo Medio", "modelo_ml"), ("Bajo Riesgo", "modelo_ml")]
    assert all(f[2] == 0 for f in filas)
    next(b for b in app.sidebar.button if b.label.startswith("Simular sincronización")).click().run()
    with sqlite3.connect(app.bd) as con:
        assert con.execute("SELECT COUNT(*) FROM evaluaciones WHERE sincronizado = 0").fetchone()[0] == 0


def test_ver_como_decidio_el_sistema_lleva_al_recorrido(app):
    """Tras evaluar, el botón deja lista la gestante para «Ver el recorrido» de la fase 07 del laboratorio."""
    evaluar(cargar_caso(app, 2))
    assert app.session_state["ultimo_registro_triaje"]["municipio"] == "Manaure"
    next(b for b in app.button if b.label == "Ver cómo decidió el sistema").click().run()
    assert not app.exception
    assert app.session_state["vista"] == "07" and app.session_state["recorrido_visible"]
    assert app.session_state["recorrido_registro"]["municipio"] == "Manaure"
    assert app.session_state["recorrido_caso"] == "Última evaluación del triaje"
