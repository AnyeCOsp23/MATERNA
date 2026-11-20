"""Gráficos y diagramas animados de la consola: datos reales, sin internet, entrada de 600-900 ms solo al abrir la
fase, transición (no redibujo) cuando cambian los datos y respeto por «reducir movimiento»."""
import json
import re

import pandas as pd
import pytest

from src import graficos, ui_theme as ui
from src.config import NOMBRES_CLASES
from src.data_preprocessing import cargar_dataset
from tests.conftest import RAIZ


@pytest.fixture(scope="module")
def df():
    return cargar_dataset()


def todos(df):
    curvas = pd.read_csv(RAIZ / "reports/metrics/curvas_aprendizaje.csv")
    exp = pd.read_csv(RAIZ / "reports/metrics/experimentos_cv_completo.csv")
    escala = pd.DataFrame({"registros": [5000, 10000], "carga_s": [0.04, 0.06], "limpieza_s": [0.15, 0.16],
                           "entrenamiento_s": [1.61, 2.47]})
    return [graficos.barras_clases(df), graficos.barras_nulos({"Glucosa (mg/dL)": 13.25, "FCF (lpm)": 7.42}),
            graficos.dispersion_presion(df), graficos.histogramas_comparados(df["edad"], df["edad"].head(300), "edad", "Edad"),
            graficos.curva_aprendizaje(curvas, curvas["modelo"].iloc[0]), graficos.escalabilidad(escala),
            graficos.f1_por_particion([0.93, 0.95, 0.91, 0.94, 0.92]), graficos.f1_por_particion([0.9, 0.8], solo_ultima=True),
            graficos.dispersion_hiperparametros(exp), graficos.mapa_calor([[85, 2, 0], [0, 68, 2], [0, 1, 22]], "Matriz"),
            graficos.curvas_roc({"Alto": ([0.0, 0.1, 1.0], [0.0, 0.9, 1.0], 0.95)}),
            graficos.barras_simples(["5.000", "10.000"], [1.8, 2.7], "Total", "Segundos")]


def funciones(texto):
    return re.findall(r"@@js:(.*?)@@", texto)


def test_cada_grafico_se_serializa_y_sus_funciones_estan_completas(df):
    for g in todos(df):
        texto = graficos.html_grafico(g)
        json.loads(texto)  # viaja como JSON al componente
        for f in funciones(texto):
            assert (f.startswith("function") or "=>" in f) and f.count("(") == f.count(")") and f.count("{") == f.count("}"), f
        assert g.alto > 0


def test_la_entrada_esta_activa_y_dura_800_ms(df):
    for g in todos(df):
        o = g.opciones
        base = o["animationDuration"]
        assert o["animation"] is True and base == 800 and o["animationEasing"] == "cubicOut"
        assert 600 <= o["animationDurationUpdate"] <= 900  # la transición por cambio de datos también
        for s in o["series"]:
            assert s.get("animationDuration", base) <= 900


def test_las_barras_crecen_escalonadas_70_ms(df):
    for g in (graficos.barras_clases(df), graficos.f1_por_particion([0.9, 0.8, 0.95])):
        assert g.opciones["series"][0]["animationDelay"] == "@@js:(i) => i * 70@@"


def test_el_componente_espera_a_ser_visible_y_transforma_sin_redibujar():
    js = graficos.JS_GRAFICO
    assert "./app/static/echarts.min.js" in js and "cdn" not in js.lower()  # ECharts local: sin internet
    assert "IntersectionObserver" in js and "ResizeObserver" in js and "clientWidth > 0" in js  # visible y con ancho
    assert "getAnimations" in js  # espera a que termine el fundido de la tarjeta
    assert "g.clear();" in js and "g.setOption(opcionesFinales(caja.__json));" in js  # la entrada arranca a la vista
    assert 'setOption(opciones, { replaceMerge: ["series"] })' in js and 's.id = "s" + i' in js  # transición por id estable
    assert "if (caja.__json === data.opciones) return;" in js  # misma ejecución, mismos datos: nada
    assert 'matchMedia("(prefers-reduced-motion: reduce)").matches' in js and "if (reducido()) o.animation = false" in js
    assert "reduce-motion:" in js  # modo debug en pantalla


def test_las_opciones_se_cachean():
    for nombre in ("barras_clases", "dispersion_presion", "mapa_calor", "curvas_roc", "curva_aprendizaje"):
        assert hasattr(getattr(graficos, nombre), "clear"), nombre  # envuelta con st.cache_data


def test_los_datos_son_los_del_dataset(df):
    clases = graficos.barras_clases(df)
    assert clases.datos == {"Bajo Riesgo": 578, "Riesgo Medio": 470, "Alto Riesgo": 152}
    assert [d["value"] for d in clases.opciones["series"][0]["data"]] == [578, 470, 152]
    presion = graficos.dispersion_presion(df)
    assert [s["name"] for s in presion.opciones["series"]] == NOMBRES_CLASES
    assert sum(len(s["data"]) for s in presion.opciones["series"]) == 1200
    umbrales = {d.get("xAxis") or d.get("yAxis") for d in presion.opciones["series"][0]["markLine"]["data"]}
    assert umbrales == {140, 160, 90, 110}
    assert any(z["type"] == "inside" for z in presion.opciones["dataZoom"])  # zoom con la rueda


def test_entrenamiento_en_vivo_solo_anima_la_barra_nueva():
    previas, nueva = graficos.f1_por_particion([0.91, 0.93, 0.95], solo_ultima=True).opciones["series"]
    assert previas["animation"] is False and previas["data"] == [0.91, 0.93, None]
    assert nueva["data"] == [None, None, 0.95]


def test_diagramas_html_listos_para_el_motor():
    ui.contexto_animacion("prueba")
    cifra = ui.cifra("1.200", etiqueta="gestantes")
    assert 'data-mt="prueba-cifra-1"' in cifra and 'data-mt-num="1200.0"' in cifra and 'data-mt-miles="1"' in cifra
    matriz = ui.matriz([[85, 2, 0], [0, 68, 2], [0, 1, 22]])
    assert matriz.count("--i:") == 9 and 'data-mt-num="85.0"' in matriz  # se rellena celda por celda y cuenta
    particion = ui.barra_particion([("Entrenamiento", 70, 840), ("Validación", 15, 180), ("Prueba", 15, 180)])
    assert particion.count('data-mt-dim="flex-grow"') == 3 and particion.count('data-mt-dim="width"') == 3
    barras = ui.barras([(1.6, "5.000"), (7.3, "30.000")])
    assert 'data-mt-dim="height"' in barras and "--i:1" in barras  # crecen escalonadas
    # los ids son estables entre ejecuciones y distintos entre fases
    ui.contexto_animacion("prueba")
    assert 'data-mt="prueba-cifra-1"' in ui.cifra("1.200")
    ui.contexto_animacion("otra")
    assert 'data-mt="otra-cifra-1"' in ui.cifra("1.200")
    # «v1» o códigos no se toman como cifras
    assert "data-mt-num" not in ui._numeros("modelo v1")


def test_el_motor_transforma_respeta_movimiento_y_las_entradas_duran_poco():
    js = ui.JS_MOTOR
    assert "MutationObserver" in js and "prefers-reduced-motion" in js and "const DUR = 750" in js
    assert 'attributeFilter: ["data-mt-num"], attributeOldValue: true' in js  # cuenta desde el valor anterior
    css = ui.estilos()
    assert "--mt-entrada-larga: .75s" in css and "@keyframes mt-celda" in css
    # al cambiar los datos, el mismo elemento se transforma con transición (no se repite la entrada)
    for regla in (".mt-barras i { transition: height .75s", ".mt-part i { transition: flex-grow .75s",
                  ".mt-tr i, .mt-fill { transition: width .75s", ".mt-ring .arc { transition: stroke-dashoffset .75s"):
        assert regla in css, regla


def test_echarts_esta_en_static_y_se_sirve():
    archivo = RAIZ / "static/echarts.min.js"
    assert archivo.exists() and archivo.stat().st_size > 500_000
    assert "Apache" in archivo.read_text(encoding="utf-8", errors="ignore")[:600]
    assert "enableStaticServing = true" in (RAIZ / ".streamlit/config.toml").read_text(encoding="utf-8")


def test_auc_casi_perfecto_no_se_muestra_como_1():
    """Un AUC de 0,9999 no es 1: la leyenda dice «> 0,999» para no aparentar una separación perfecta."""
    assert graficos.texto_auc(0.9999) == "> 0,999"
    assert graficos.texto_auc(1.0) == "1,000"
    assert graficos.texto_auc(0.9959) == "0,996"
    nombres = [s["name"] for s in graficos.curvas_roc({"Bajo": ([0, 0, 1], [0, 1, 1], 0.9999)}).opciones["series"]]
    assert nombres[0] == "Bajo (AUC > 0,999)"
