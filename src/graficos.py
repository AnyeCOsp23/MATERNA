"""Fase 3 — Gráficos de la consola web (ECharts), animados e interactivos, con la paleta de MATERNA.

Cada gráfico se construye al entrar a la fase (barras que crecen, líneas que se trazan, puntos que aparecen) y es
interactivo: detalle al pasar el mouse, series que se ocultan tocando la leyenda y zoom con la rueda en las
dispersiones. ECharts (Apache 2.0) se sirve desde static/echarts.min.js: funciona sin internet. Con «reducir
movimiento» del sistema operativo, los gráficos aparecen sin animación.

Colores validados para daltonismo con el validador de paletas (adyacentes y todos los pares):
- clases de riesgo: Bajo #2F9C8A, Medio #E0A33A, Alto #9B2D5C. El ámbar tiene poco contraste
  sobre fondo claro: por eso cada gráfico lleva leyenda, tooltip y una tabla al lado.
- dos series (entrenamiento / validación, sintético / IPS): vino #7B2D5B y rosa #D8639B.
"""
import json
import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v2 as componentes

from src.config import NOMBRES_CLASES

COLOR_CLASE = dict(zip(NOMBRES_CLASES, ["#2F9C8A", "#E0A33A", "#9B2D5C"]))
SERIE_1, SERIE_2 = "#7B2D5B", "#D8639B"
TINTA, TINTA_SUAVE, REJILLA = "#3A1230", "#6B4A5E", "#E9DDE3"
FUENTE = "-apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif"


@dataclass
class Grafico:
    """Opciones de ECharts y alto en píxeles. Las funciones de JavaScript van como «@@js:…@@»."""
    opciones: dict
    alto: int = 320
    titulo: str = ""
    datos: dict = field(default_factory=dict)  # resumen legible (para pruebas y accesibilidad)
    mapa: tuple = None  # (nombre, GeoJSON como texto) que el navegador registra en ECharts antes de dibujar


def js(codigo):
    return f"@@js:{codigo}@@"


# Componente v2 montado en la página (sin iframe), con una `key` estable: Streamlit conserva el elemento entre
# ejecuciones y le pasa los datos nuevos. Ciclo de vida de cada gráfico:
#   1. Espera a que el contenedor (de alto fijo) sea VISIBLE y tenga ANCHO > 0 (IntersectionObserver +
#      ResizeObserver) y a que terminen las animaciones de sus contenedores (fundido de la tarjeta).
#   2. Entonces chart.clear() + setOption(opciones): la animación de entrada arranca en ese momento, a la vista.
#   3. Si los datos cambian por una interacción: setOption sobre el mismo gráfico (series con id estable) =
#      transición. Si una ejecución trae los mismos datos, no hace nada.
# «prefers-reduced-motion» solo apaga la animación cuando el sistema lo tiene activo. Con ?debug=1 en la URL se
# muestra en cada gráfico el valor detectado y cuándo arrancó la animación.
JS_GRAFICO = r"""
function cargarEcharts() {
  if (window.echarts) return Promise.resolve();
  if (!window.__mtEcharts) {
    window.__mtEcharts = new Promise((listo, error) => {
      const s = document.createElement("script");
      s.src = "./app/static/echarts.min.js";  // servido por Streamlit: funciona sin internet
      s.onload = () => listo(); s.onerror = error;
      document.head.appendChild(s);
    });
  }
  return window.__mtEcharts;
}
function revivir(v) {  // "@@js:function…@@" → función de JavaScript
  if (typeof v === "string" && v.startsWith("@@js:") && v.endsWith("@@")) return new Function("return (" + v.slice(5, -2) + ")")();
  if (Array.isArray(v)) return v.map(revivir);
  if (v && typeof v === "object") { const o = {}; for (const k in v) o[k] = revivir(v[k]); return o; }
  return v;
}
const reducido = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
function opcionesFinales(json) {
  const o = revivir(JSON.parse(json));
  (o.series || []).forEach((s, i) => { if (s.id === undefined) s.id = "s" + i; });  // id estable: transición, no reemplazo
  if (reducido()) o.animation = false;  // solo si el sistema lo pide
  return o;
}
// espera a que las animaciones CSS de los contenedores (fundido de la tarjeta) terminen
function finAnimacionesDe(el) {
  const pendientes = [];
  for (let e = el; e && e !== document.body; e = e.parentElement)
    for (const a of e.getAnimations ? e.getAnimations() : []) if (a.playState === "running") pendientes.push(a.finished.catch(() => {}));
  return Promise.all(pendientes);
}
function cuandoSeaVisible(caja, alListo) {
  let visible = false, ancho = caja.clientWidth > 0, hecho = false;
  const intentar = () => {
    if (hecho || !visible || !ancho || !caja.isConnected) return;
    hecho = true; io.disconnect(); ro.disconnect();
    finAnimacionesDe(caja).then(alListo);
  };
  const io = new IntersectionObserver((es) => { visible = es.some((e) => e.isIntersecting && e.intersectionRatio > 0); intentar(); },
                                      { threshold: [0, 0.2] });
  const ro = new ResizeObserver(() => { ancho = caja.clientWidth > 0 && caja.clientHeight > 0; intentar(); });
  io.observe(caja); ro.observe(caja);
}
function avisoDebug(caja, texto) {
  let d = caja.parentElement.querySelector(".mt-debug");
  if (!d) {
    d = document.createElement("div");
    d.className = "mt-debug";
    d.style.cssText = "position:absolute;bottom:2px;right:6px;z-index:5;font:600 11px/1.3 system-ui;background:#FFF7D6;" +
                      "color:#5C4400;border:1px solid #E7CF77;border-radius:6px;padding:2px 6px;pointer-events:none";
    caja.parentElement.style.position = "relative";
    caja.parentElement.appendChild(d);
  }
  d.textContent = texto;
}
export default function ({ data, parentElement }) {
  if (!data) return;
  let caja = parentElement.querySelector(".mt-echart");
  if (!caja) {
    caja = document.createElement("div");
    caja.className = "mt-echart";
    caja.setAttribute("role", "img");
    caja.style.width = "100%";
    caja.__t0 = performance.now();
    parentElement.appendChild(caja);
  }
  caja.style.height = data.alto + "px";  // alto fijo desde el primer cuadro: sin saltos de layout
  caja.setAttribute("aria-label", data.titulo || "Gráfico");
  if (caja.__json === data.opciones) return;  // misma ejecución, mismos datos: no se toca nada
  caja.__json = data.opciones;
  const debug = (txt) => { if (data.debug) avisoDebug(caja, `reduce-motion: ${reducido()} · ${txt}`); };
  cargarEcharts().then(() => {
    // mapas (GeoJSON local): se registran una sola vez por nombre, antes de dibujar
    if (data.mapa && !echarts.getMap(data.mapa.nombre)) echarts.registerMap(data.mapa.nombre, JSON.parse(data.mapa.geojson));
    const opciones = opcionesFinales(caja.__json);
    if (caja.__grafico) {  // ya entró: transición a los datos nuevos sobre el mismo gráfico
      caja.__grafico.setOption(opciones, { replaceMerge: ["series"] });
      debug("transición " + new Date().toLocaleTimeString());
      return;
    }
    if (caja.__esperando) return;
    caja.__esperando = true;
    debug("esperando a ser visible…");
    cuandoSeaVisible(caja, () => {
      const g = echarts.getInstanceByDom(caja) || echarts.init(caja, null, { renderer: "svg" });
      caja.__grafico = g;
      g.clear();
      g.setOption(opcionesFinales(caja.__json));  // la entrada arranca ahora, a la vista
      // resize() corta la animación en curso: solo si el tamaño cambia DE VERDAD (el observador avisa una vez al
      // empezar a observar, y ese aviso no debe tocar el gráfico)
      let ancho = caja.clientWidth, alto = caja.clientHeight;
      new ResizeObserver(() => {
        if (caja.clientWidth === ancho && caja.clientHeight === alto) return;
        ancho = caja.clientWidth; alto = caja.clientHeight;
        g.resize();
      }).observe(caja);
      debug(`animación ${opciones.animation === false ? "desactivada" : "activa"} · entró a los ${Math.round(performance.now() - caja.__t0)} ms`);
    });
  });
}
"""
_COMPONENTE = componentes.component("materna_grafico", js=JS_GRAFICO, isolate_styles=False)
DEBUG = {"activo": False}


def modo_debug(activo):
    """Con ?debug=1 en la URL, cada gráfico muestra en pantalla prefers-reduced-motion y cuándo arrancó su animación."""
    DEBUG["activo"] = bool(activo)


def mostrar(g, key):
    """Dibuja el gráfico. `key` debe ser estable y única en la página: identifica al gráfico entre ejecuciones."""
    datos = {"opciones": _a_texto(g.opciones), "alto": g.alto, "titulo": g.titulo, "debug": DEBUG["activo"]}
    if g.mapa:
        datos["mapa"] = {"nombre": g.mapa[0], "geojson": g.mapa[1]}
    _COMPONENTE(key=f"g-{key}", data=datos, height=g.alto + 6)


def _a_texto(opciones):
    return json.dumps(opciones, ensure_ascii=False, sort_keys=True)


def html_grafico(g):
    """Resumen JSON de las opciones (para pruebas): las funciones quedan como «@@js:…@@» y se reviven en el navegador."""
    return json.dumps(g.opciones, ensure_ascii=False)


# ------------------------------------------------------------------ estilo común
def _eje(nombre=None, tipo="value", **extra):
    eje = {"type": tipo, "axisLine": {"lineStyle": {"color": REJILLA}}, "axisTick": {"show": False},
           "axisLabel": {"color": TINTA_SUAVE, "fontSize": 12}, "splitLine": {"lineStyle": {"color": REJILLA}},
           "nameTextStyle": {"color": TINTA, "fontSize": 12}}
    if nombre:
        eje.update(name=nombre, nameLocation="middle", nameGap=34)
    if tipo == "category":
        eje["splitLine"] = {"show": False}
    eje.update(extra)
    return eje


def _base(**extra):
    opciones = {
        "backgroundColor": "transparent", "textStyle": {"fontFamily": FUENTE, "color": TINTA},
        "animation": True, "animationDuration": 800, "animationEasing": "cubicOut", "animationDurationUpdate": 700,
        "animationEasingUpdate": "cubicInOut",
        "grid": {"left": 46, "right": 24, "top": 44, "bottom": 44, "containLabel": True},  # margen para los títulos de los ejes
        "tooltip": {"backgroundColor": "#FFFFFF", "borderColor": REJILLA, "textStyle": {"color": TINTA, "fontSize": 12},
                    "extraCssText": "box-shadow:0 6px 20px rgba(58,18,48,.12);border-radius:10px;"},
        "legend": {"show": False},
    }
    opciones.update(extra)
    return opciones


def _leyenda(**extra):
    return {"show": True, "top": 0, "icon": "circle", "itemWidth": 10, "itemHeight": 10,
            "textStyle": {"color": TINTA, "fontSize": 12}, **extra}


ESCALONADO = js("(i) => i * 70")  # barras: leve retardo escalonado


# ------------------------------------------------------------------ gráficos
def dispersion_presion(df):
    """PAS vs PAD por clase, con los umbrales de hipertensión (140/90) y de hipertensión severa (160/110)."""
    series = []
    for k, clase in enumerate(NOMBRES_CLASES):
        d = df[df["riesgo_obstetrico"] == clase]
        series.append({
            "name": clase, "type": "scatter", "symbolSize": 9,
            "data": [[float(a), float(b), float(c)] for a, b, c in zip(d["pas_mmhg"], d["pad_mmhg"], d["proteinuria"])],
            "itemStyle": {"color": COLOR_CLASE[clase], "opacity": 0.78, "borderColor": "#FFFFFF", "borderWidth": 1},
            "emphasis": {"focus": "series", "itemStyle": {"opacity": 1}},
            "animationDuration": 800, "animationDelay": js(f"(i) => {k * 70} + i * 0.1"),
        })
    linea = {"type": "dashed", "color": TINTA_SUAVE, "width": 1.2}
    series[0]["markLine"] = {
        "silent": False, "symbol": "none", "lineStyle": linea, "animationDuration": 800, "animationDelay": 300,
        "label": {"color": TINTA_SUAVE, "fontSize": 11},
        "data": [{"xAxis": 140, "name": "140/90 hipertensión", "label": {"formatter": "140"}},
                 {"xAxis": 160, "name": "160/110 severa (regla)", "label": {"formatter": "160"}},
                 {"yAxis": 90, "name": "140/90 hipertensión", "label": {"formatter": "90"}},
                 {"yAxis": 110, "name": "160/110 severa (regla)", "label": {"formatter": "110"}}]}
    opciones = _base(
        legend=_leyenda(), series=series,
        xAxis=_eje("Presión sistólica (mmHg)", scale=True), yAxis=_eje("Presión diastólica (mmHg)", scale=True, nameGap=40),
        dataZoom=[{"type": "inside", "xAxisIndex": 0}, {"type": "inside", "yAxisIndex": 0}],
        tooltip={**_base()["tooltip"], "trigger": "item", "formatter": js(
            "function (p) { if (p.componentType === 'markLine') return p.name; return '<b>' + p.seriesName + '</b><br/>PAS ' + "
            "p.value[0] + ' · PAD ' + p.value[1] + '<br/>Proteinuria ' + p.value[2]; }")})
    return Grafico(opciones, 380, "Presión sistólica frente a diastólica por clase",
                   {c: int((df["riesgo_obstetrico"] == c).sum()) for c in NOMBRES_CLASES})


def barras_nulos(pct):
    """% de valores faltantes por variable (una sola serie: sin leyenda)."""
    orden = sorted(pct.items(), key=lambda kv: kv[1])  # el mayor queda arriba
    opciones = _base(
        grid={"left": 18, "right": 56, "top": 10, "bottom": 44, "containLabel": True},
        xAxis=_eje("% de registros sin el dato"), yAxis=_eje(tipo="category", data=[k for k, _ in orden]),
        tooltip={**_base()["tooltip"], "trigger": "item", "formatter": "{b}<br/><b>{c} %</b> sin el dato"},
        series=[{"type": "bar", "barWidth": 26, "data": [round(float(v), 2) for _, v in orden],
                 "itemStyle": {"color": SERIE_1, "borderRadius": [0, 6, 6, 0]},
                 "label": {"show": True, "position": "right", "color": TINTA, "formatter": "{c}"},
                 "animationDelay": ESCALONADO}])
    return Grafico(opciones, 50 * len(pct) + 70, "Datos faltantes por variable", dict(orden))


def barras_clases(df, columna="riesgo_obstetrico"):
    conteo = df[columna].value_counts().reindex(NOMBRES_CLASES).fillna(0).astype(int)
    opciones = _base(
        xAxis=_eje(tipo="category", data=list(conteo.index)), yAxis=_eje("Gestantes", nameGap=44),
        tooltip={**_base()["tooltip"], "trigger": "item", "formatter": "{b}<br/><b>{c}</b> gestantes"},
        series=[{"type": "bar", "barWidth": 48, "animationDelay": ESCALONADO,
                 "data": [{"value": int(n), "itemStyle": {"color": COLOR_CLASE[c], "borderRadius": [6, 6, 0, 0]}}
                          for c, n in conteo.items()],
                 "label": {"show": True, "position": "top", "color": TINTA}}])
    return Grafico(opciones, 270, "Gestantes por clase de riesgo", conteo.to_dict())


def histogramas_comparados(sintetico, ips, variable, titulo):
    """Distribución de una variable en el dataset sintético y en el archivo de la IPS (dos paneles, mismo eje)."""
    a, b = sintetico.dropna().astype(float), ips.dropna().astype(float)
    bordes = np.histogram_bin_edges(np.concatenate([a.to_numpy(), b.to_numpy()]), bins=25)
    etiquetas = [f"{x:.0f}–{y:.0f}" for x, y in zip(bordes[:-1], bordes[1:])]
    conteos = {"Sintético": np.histogram(a, bordes)[0], "IPS": np.histogram(b, bordes)[0]}
    grids = [{"left": 46, "right": 24, "top": 34, "height": 104, "containLabel": True},
             {"left": 46, "right": 24, "top": 182, "height": 104, "containLabel": True}]
    opciones = _base(
        legend=_leyenda(), grid=grids,
        xAxis=[_eje(tipo="category", data=etiquetas, gridIndex=0, axisLabel={"show": False}),
               _eje(titulo, tipo="category", data=etiquetas, gridIndex=1, nameGap=28)],
        yAxis=[_eje("Sintético", gridIndex=0, nameGap=40), _eje("IPS", gridIndex=1, nameGap=40)],
        tooltip={**_base()["tooltip"], "trigger": "item", "formatter": "{a} · {b}<br/><b>{c}</b> registros"},
        series=[{"name": nombre, "type": "bar", "xAxisIndex": i, "yAxisIndex": i, "barCategoryGap": "8%",
                 "data": [int(v) for v in conteos[nombre]], "itemStyle": {"color": color, "borderRadius": [3, 3, 0, 0]},
                 "animationDuration": 800, "animationDelay": js(f"(k) => {i * 70} + k * 8")}
                for i, (nombre, color) in enumerate([("Sintético", SERIE_1), ("IPS", SERIE_2)])])
    return Grafico(opciones, 340, f"Distribución de {titulo}: sintético frente a IPS",
                   {"Sintético": int(conteos["Sintético"].sum()), "IPS": int(conteos["IPS"].sum())})


def curva_aprendizaje(df, modelo, dominio_x=(50, 720)):
    """F1-macro en entrenamiento y en validación cruzada según el tamaño del entrenamiento.

    dominio_x=None ajusta el eje a los datos (para particiones distintas de la oficial).
    """
    d = df[df["modelo"] == modelo].sort_values("n_entrenamiento")
    if dominio_x is None:
        dominio_x = (d["n_entrenamiento"].min() * 0.85, d["n_entrenamiento"].max() * 1.05)
    n = d["n_entrenamiento"].astype(float).tolist()
    series, piso = [], 0.55
    for k, (nombre, media, desv, color) in enumerate([
            ("Entrenamiento", "f1_entrenamiento", "f1_entrenamiento_std", SERIE_1),
            ("Validación cruzada", "f1_cv", "f1_cv_std", SERIE_2)]):
        m, s = d[media].astype(float), d[desv].astype(float)
        piso = min(piso, float((m - s).min()) - 0.02)  # una configuración mala no debe salirse del gráfico
        # banda ± 1 desviación: un polígono (borde superior de izquierda a derecha y el inferior de vuelta)
        puntos = [[x, round(lo, 4), round(hi, 4)] for x, lo, hi in zip(n, m - s, m + s)]
        series.append({"name": f"banda-{k}", "type": "custom", "silent": True, "z": 1, "clip": True,
                       "data": puntos[:1], "tooltip": {"show": False}, "animationDuration": 800,
                       "renderItem": js(
                           "function (params, api) { const p = " + json.dumps(puntos) + "; "
                           "const arriba = p.map(q => api.coord([q[0], q[2]])); "
                           "const abajo = p.map(q => api.coord([q[0], q[1]])).reverse(); "
                           "return {type: 'polygon', shape: {points: arriba.concat(abajo)}, "
                           f"style: {{fill: '{color}', opacity: 0.14}}}}; }}")})
        series.append({"name": nombre, "type": "line", "symbolSize": 9, "lineStyle": {"width": 2.5, "color": color},
                       "itemStyle": {"color": color, "borderColor": "#FFFFFF", "borderWidth": 2},
                       "data": [[x, round(v, 4), round(e, 4)] for x, v, e in zip(n, m, s)],
                       "animationDuration": 800, "animationDelay": k * 100})
    opciones = _base(
        legend=_leyenda(data=["Entrenamiento", "Validación cruzada"]), series=series,
        xAxis=_eje("Gestantes de entrenamiento", min=round(dominio_x[0]), max=round(dominio_x[1])),
        yAxis=_eje("F1-macro", min=round(piso, 2), max=1.02, nameGap=42, axisLabel={"color": TINTA_SUAVE, "formatter": js(
            "function (v) { return v.toFixed(2); }")}),
        tooltip={**_base()["tooltip"], "trigger": "item", "formatter": js(
            "function (p) { return '<b>' + p.seriesName + '</b><br/>n = ' + p.value[0] + '<br/>F1-macro ' + "
            "p.value[1].toFixed(3) + ' ± ' + p.value[2].toFixed(3); }")})
    return Grafico(opciones, 310, f"Curva de aprendizaje de {modelo}", {"puntos": len(d)})


def escalabilidad(df):
    """Segundos de carga, limpieza y entrenamiento según el número de registros."""
    etapas = [("carga_s", "Carga", "#E0A33A"), ("limpieza_s", "Limpieza", SERIE_2), ("entrenamiento_s", "Entrenamiento", SERIE_1)]
    registros = [f"{int(r):,}".replace(",", ".") for r in df["registros"]]
    opciones = _base(
        legend=_leyenda(), xAxis=_eje("Registros", tipo="category", data=registros, boundaryGap=False),
        yAxis=_eje("Segundos", nameGap=40),
        tooltip={**_base()["tooltip"], "trigger": "axis", "valueFormatter": js("function (v) { return v.toFixed(2) + ' s'; }")},
        series=[{"name": nombre, "type": "line", "symbolSize": 9, "data": [round(float(v), 2) for v in df[col]],
                 "lineStyle": {"width": 2.5, "color": color}, "itemStyle": {"color": color, "borderColor": "#FFFFFF", "borderWidth": 2},
                 "animationDuration": 800, "animationDelay": k * 40} for k, (col, nombre, color) in enumerate(etapas)])
    return Grafico(opciones, 310, "Tiempos de carga, limpieza y entrenamiento según los registros", {"tamaños": len(df)})


def f1_por_particion(valores, solo_ultima=False):
    """F1-macro de cada partición. Con `solo_ultima` (entrenamiento en vivo) solo crece la barra recién terminada."""
    datos = [round(float(v), 4) for v in valores]
    estilo = {"type": "bar", "barWidth": 34, "itemStyle": {"color": SERIE_1, "borderRadius": [6, 6, 0, 0]},
              "label": {"show": True, "position": "top", "color": TINTA, "formatter": js("function (p) { return p.value.toFixed(3); }")}}
    if solo_ultima and len(datos) > 1:
        series = [{**estilo, "data": datos[:-1] + [None], "animation": False},
                  {**estilo, "data": [None] * (len(datos) - 1) + datos[-1:], "barGap": "-100%", "animationDuration": 800}]
    else:
        series = [{**estilo, "data": datos, "animationDelay": ESCALONADO, "animationDuration": 800}]
    opciones = _base(
        xAxis=_eje("Partición", tipo="category", data=[f"P{i}" for i in range(1, len(valores) + 1)], nameGap=28),
        yAxis=_eje("F1-macro", min=0, max=1, nameGap=40),
        tooltip={**_base()["tooltip"], "trigger": "item", "formatter": js(
            "function (p) { return p.name + '<br/>F1-macro <b>' + p.value.toFixed(4) + '</b>'; }")},
        series=series)
    return Grafico(opciones, 250, "F1-macro por partición de la validación cruzada", {"particiones": len(valores)})


def dispersion_hiperparametros(df):
    """F1-macro de cada configuración probada, por modelo y estrategia de balanceo."""
    colores = {"Regresión Logística": "#E0A33A", "SVM": SERIE_2, "Random Forest": SERIE_1}
    simbolos = ["circle", "triangle", "diamond", "rect"]
    balanceos = sorted(df["balanceo"].astype(str).unique())
    series = []
    for k, ((modelo, balanceo), d) in enumerate(df.groupby(["modelo", df["balanceo"].astype(str)], sort=False)):
        series.append({
            "name": f"{modelo} · {balanceo}", "type": "scatter", "symbolSize": 12,
            "symbol": simbolos[balanceos.index(balanceo) % len(simbolos)],
            "itemStyle": {"color": colores.get(modelo, TINTA_SUAVE), "opacity": 0.82, "borderColor": "#FFFFFF", "borderWidth": 1},
            "emphasis": {"focus": "series"},
            "data": [[round(float(x), 4), round(float(y), 4), str(h)] for x, y, h in
                     zip(d["cv_recall_alto_media"], d["cv_f1_macro_media"], d["hiperparametros"])],
            "animationDuration": 800, "animationDelay": js(f"(i) => {k * 70} + i * 2")})
    opciones = _base(
        legend=_leyenda(type="scroll"), series=series,
        grid={"left": 50, "right": 24, "top": 56, "bottom": 44, "containLabel": True},
        xAxis=_eje("Recall de Alto Riesgo (CV)", scale=True), yAxis=_eje("F1-macro (CV)", scale=True, nameGap=44),
        dataZoom=[{"type": "inside", "xAxisIndex": 0}, {"type": "inside", "yAxisIndex": 0}],
        tooltip={**_base()["tooltip"], "trigger": "item", "formatter": js(
            "function (p) { return '<b>' + p.seriesName + '</b><br/>' + p.value[2] + '<br/>F1-macro ' + p.value[1].toFixed(4) + "
            "' · Recall Alto ' + p.value[0].toFixed(4); }")})
    return Grafico(opciones, 400, "F1-macro de cada configuración probada", {"configuraciones": len(df)})


def mapa_calor(valores, titulo, filas=("Bajo", "Medio", "Alto"), columnas=("Bajo", "Medio", "Alto"), prefijo="Real ",
               decimales=0, alto=290):
    """Matriz (confusión o costo) como mapa de calor que se rellena celda por celda en orden de lectura."""
    n_c = len(columnas)
    plano = [float(v) for fila in valores for v in fila]
    datos = [[j, i, round(float(v), decimales) if decimales else int(v)] for i, fila in enumerate(valores) for j, v in enumerate(fila)]
    opciones = _base(
        grid={"left": 10, "right": 16, "top": 34, "bottom": 10, "containLabel": True},
        xAxis={**_eje(tipo="category", data=list(columnas), position="top"), "axisLine": {"show": False},
               "splitArea": {"show": False}},
        yAxis={**_eje(tipo="category", data=[prefijo + f for f in filas], inverse=True), "axisLine": {"show": False}},
        visualMap={"show": False, "min": min(plano), "max": max(plano) or 1, "inRange": {"color": ["#F6EEF2", "#E9C8D8", "#C98AAB"]}},
        tooltip={**_base()["tooltip"], "trigger": "item", "formatter": js(
            "(p) => p.marker + ' ' + p.name + ' → asignada ' + p.value[0] + '<br/><b>' + p.value[2] + '</b>'")},
        series=[{"type": "heatmap", "data": datos, "animationDelay": js("(i) => i * 70"),  # celda por celda
                 "label": {"show": True, "fontSize": 16, "fontWeight": 600, "color": TINTA},
                 "itemStyle": {"borderColor": "#FFFFFF", "borderWidth": 4, "borderRadius": 10},
                 "emphasis": {"itemStyle": {"borderColor": SERIE_1, "borderWidth": 2}}}])
    # el tooltip muestra los nombres de fila y columna
    opciones["tooltip"]["formatter"] = js(
        "(p) => " + json.dumps([prefijo + f for f in filas]) + "[p.value[1]] + ' · asignada ' + "
        + json.dumps(list(columnas)) + "[p.value[0]] + '<br/><b>' + p.value[2] + '</b>'")
    return Grafico(opciones, alto, titulo, {"celdas": len(datos), "n_columnas": n_c})


def texto_auc(auc):
    """AUC con 3 decimales y coma. Un AUC menor que 1 que se redondearía a 1,000 se muestra «> 0,999»:
    «1,000» haría creer que la separación es perfecta."""
    if auc < 1 and round(auc, 3) >= 1:
        return "> 0,999"
    return f"{auc:.3f}".replace(".", ",")


def curvas_roc(curvas, titulo="Curvas ROC"):
    """Curvas ROC uno contra el resto: {clase: (fpr, tpr, auc)}. Las líneas se trazan de izquierda a derecha.
    Los puntos llegan tal cual de sklearn.metrics.roc_curve (un punto por umbral, de (0, 0) a (1, 1))."""
    color = {"Bajo": COLOR_CLASE["Bajo Riesgo"], "Medio": COLOR_CLASE["Riesgo Medio"], "Alto": COLOR_CLASE["Alto Riesgo"]}
    coma = {"color": TINTA_SUAVE, "fontSize": 12, "formatter": js("(v) => String(v).replace('.', ',')")}
    series = [{"name": f"{clase} (AUC {texto_auc(auc)})", "type": "line", "showSymbol": False, "smooth": False,
               "data": [[round(float(x), 4), round(float(y), 4)] for x, y in zip(fpr, tpr)],
               "lineStyle": {"width": 2.5, "color": color.get(clase, COLOR_CLASE.get(clase, SERIE_1))},
               "itemStyle": {"color": color.get(clase, COLOR_CLASE.get(clase, SERIE_1))},
               "animationDelay": k * 70} for k, (clase, (fpr, tpr, auc)) in enumerate(curvas.items())]
    series.append({"id": "azar", "name": "Azar", "type": "line", "showSymbol": False, "silent": True, "data": [[0, 0], [1, 1]],
                   "lineStyle": {"type": "dashed", "color": TINTA_SUAVE, "width": 1}, "tooltip": {"show": False}})
    opciones = _base(
        legend=_leyenda(data=[s["name"] for s in series[:-1]]), series=series,
        xAxis=_eje("Tasa de falsos positivos (FPR)", min=0, max=1, axisLabel=coma),
        yAxis=_eje("Sensibilidad (TPR)", min=0, max=1, nameGap=40, axisLabel=coma),
        tooltip={**_base()["tooltip"], "trigger": "item", "formatter": js(
            "(p) => p.seriesName + '<br/>FPR ' + p.value[0].toFixed(3) + ' · sensibilidad ' + p.value[1].toFixed(3)")})
    return Grafico(opciones, 320, titulo, {"curvas": len(curvas)})


def barras_simples(etiquetas, valores, titulo, nombre_y, decimales=2, alto=250):
    """Barras de una sola serie que crecen escalonadas (p. ej. tiempo total por tamaño)."""
    opciones = _base(
        xAxis=_eje(tipo="category", data=list(etiquetas)), yAxis=_eje(nombre_y, nameGap=40),
        tooltip={**_base()["tooltip"], "trigger": "item", "formatter": "{b}<br/><b>{c}</b>"},
        series=[{"type": "bar", "barWidth": 42, "data": [round(float(v), decimales) for v in valores], "animationDelay": ESCALONADO,
                 "itemStyle": {"color": SERIE_2, "borderRadius": [6, 6, 0, 0]},
                 "label": {"show": True, "position": "top", "color": TINTA}}])
    return Grafico(opciones, alto, titulo, {"barras": len(valores)})


# ------------------------------------------------------------------ mapas (GeoJSON local del DANE, sin mapa de fondo)
SIN_DATOS = "#F2EEF0"          # municipios sin gestantes en los datos
ESCALA_ALTO = ["#F6E7EE", "#D9A3BD", "#9B2D5C"]  # de poco a mucho Alto Riesgo (tonos de la clase Alto)
ESCALA_CONTEO = ["#EEF3F2", "#8CC5BA", "#2F6F64"]
# una escala por nivel (el color de la clase al final) y otra vino cuando se eligen varios niveles
ESCALA_NIVEL = {"Bajo Riesgo": ["#E7F3F0", "#93CBBF", "#2F9C8A"], "Riesgo Medio": ["#FBF1DE", "#EDC278", "#C2861F"],
                "Alto Riesgo": ESCALA_ALTO}
ESCALA_VARIOS = ["#F3E6EE", "#C58AAA", "#7B2D5B"]


def geojson_texto(departamento=None):
    """GeoJSON de los municipios (de un departamento o de los dos) como texto, y su nombre para ECharts."""
    from src import georreferencia
    geo = georreferencia.municipios()
    if departamento:
        geo = {**geo, "features": [f for f in geo["features"] if f["properties"]["departamento"] == departamento]}
    nombre = "materna-" + (departamento or "ambos").lower().replace(" ", "-")
    return nombre, json.dumps(geo, ensure_ascii=False, separators=(",", ":"))


def _geo_base(nombre_mapa, **extra):
    """Mapa solo de límites: sin calles ni teselas. Se puede acercar con la rueda y arrastrar."""
    return {"map": nombre_mapa, "nameProperty": "municipio", "roam": True, "aspectScale": 0.98,
            "layoutCenter": ["50%", "47%"], "layoutSize": "92%",  # el mapa ocupa todo el alto del gráfico
            "scaleLimit": {"min": 0.8, "max": 12}, "label": {"show": False},
            "itemStyle": {"areaColor": SIN_DATOS, "borderColor": "#FFFFFF", "borderWidth": 0.8},
            "emphasis": {"label": {"show": True, "color": TINTA, "fontSize": 11, "fontWeight": 600},
                         "itemStyle": {"areaColor": "#E9DDE3"}}, **extra}


def mapa_coropletico(tabla, departamento=None, niveles=tuple(NOMBRES_CLASES), modo="porcentaje", titulo="Municipios"):
    """Municipios coloreados según los niveles elegidos, con el detalle en el tooltip.

    Porcentaje (por defecto): con todos los niveles, el % de Alto Riesgo; con algunos, el % de gestantes del municipio
    que son de esos niveles. Así se comparan municipios de distinto tamaño. Cantidad: cuántas gestantes de esos niveles
    (sigue casi igual al tamaño del municipio). La escala va del menor al mayor valor real, para que se noten las
    diferencias, y el color es el del nivel elegido (vino si son varios)."""
    nombre, texto = geojson_texto(departamento)
    niveles = [n for n in NOMBRES_CLASES if n in niveles] or list(NOMBRES_CLASES)
    todos = len(niveles) == len(NOMBRES_CLASES)
    porcentaje = modo == "porcentaje"
    datos = []
    for f in tabla.to_dict("records"):
        sel = sum(int(f[n]) for n in niveles)
        if porcentaje:
            valor = f["pct_alto"] if todos else round(100 * sel / f["gestantes"], 1) if f["gestantes"] else 0.0
        else:
            valor = int(f["gestantes"]) if todos else sel
        datos.append({"name": f["municipio"], "value": valor, "gestantes": int(f["gestantes"]), "alto": int(f["Alto Riesgo"]),
                      "medio": int(f["Riesgo Medio"]), "bajo": int(f["Bajo Riesgo"]), "pct": f["pct_alto"]})
    valores = [d["value"] for d in datos] or [0]
    if porcentaje:
        minimo, maximo = math.floor(min(valores)), math.ceil(max(valores))
        if maximo <= minimo:
            maximo = minimo + 1
        textos = [f"{maximo} %", f"{minimo} %"]
    else:
        minimo, maximo = 0, max(max(valores), 1)
        textos = [f"{int(maximo)} gestantes", "0"]
    if todos:
        escala = ESCALA_ALTO if porcentaje else ESCALA_CONTEO
    else:
        escala = ESCALA_NIVEL[niveles[0]] if len(niveles) == 1 else ESCALA_VARIOS
    opciones = _base(
        tooltip={**_base()["tooltip"], "trigger": "item", "formatter": js(
            "(p) => p.data ? '<b>' + p.name + '</b><br/>' + p.data.gestantes + ' gestantes · Alto ' + p.data.alto + "
            "' (' + String(p.data.pct).replace('.', ',') + ' %)<br/>Medio ' + p.data.medio + ' · Bajo ' + p.data.bajo "
            ": '<b>' + p.name + '</b><br/>Sin gestantes en los datos'")},
        visualMap={"min": minimo, "max": maximo, "calculable": False, "orient": "horizontal", "left": "center", "bottom": 4,
                   "itemWidth": 12, "itemHeight": 140, "text": textos,
                   "textStyle": {"color": TINTA_SUAVE, "fontSize": 11},
                   "inRange": {"color": escala}, "seriesIndex": 0},
        series=[{"id": "municipios", "type": "map", **_geo_base(nombre), "data": datos, "selectedMode": False,
                 "showLegendSymbol": False,  # sin el punto que ECharts pone en cada municipio
                 "animationDurationUpdate": 600}])
    return Grafico(opciones, 500, titulo, {"municipios": len(datos), "niveles": niveles, "modo": modo}, mapa=(nombre, texto))


def _encuadre_puntos(geojson, filas):
    """Abre el mapa acercado a donde hay lugares (centro y zoom de su recuadro), no a los dos departamentos completos:
    así los anillos no quedan amontonados en una esquina. Se puede alejar con la rueda."""
    if not filas:
        return {}
    coords = [c for f in json.loads(geojson)["features"] for c in _coordenadas(f["geometry"])]
    lat_mapa = max(c[1] for c in coords) - min(c[1] for c in coords)
    lons, lats = [f["lon"] for f in filas], [f["lat"] for f in filas]
    alto = max(max(lats) - min(lats), 0.3)
    zoom = round(min(2.6, max(1.0, 0.8 * lat_mapa / alto)), 2)
    return {"center": [round((min(lons) + max(lons)) / 2, 4), round((min(lats) + max(lats)) / 2, 4)], "zoom": zoom}


def _coordenadas(geometria):
    poligonos = geometria["coordinates"] if geometria["type"] == "MultiPolygon" else [geometria["coordinates"]]
    return [c for poligono in poligonos for anillo in poligono for c in anillo]


def mapa_concentracion(tabla_puntos, clases=tuple(NOMBRES_CLASES), departamento=None, titulo="Puntos de concentración"):
    """Un anillo por lugar: su tamaño es cuántas gestantes (de los niveles elegidos) hay ahí y sus colores, cómo se
    reparten entre Bajo, Medio y Alto. Con el número en el centro cuando cabe. Antes eran hasta tres círculos
    superpuestos por lugar, difíciles de leer."""
    nombre, texto = geojson_texto(departamento)
    clases = [c for c in NOMBRES_CLASES if c in clases] or list(NOMBRES_CLASES)
    filas = [f for f in tabla_puntos.to_dict("records") if sum(int(f[c]) for c in clases) > 0]
    maximo = max([sum(int(f[c]) for c in clases) for f in filas] or [1])
    # los grandes primero: los pequeños quedan encima y se pueden tocar
    filas.sort(key=lambda f: -sum(int(f[c]) for c in clases))
    series, conteos = [], []
    for k, f in enumerate(filas):
        total = sum(int(f[c]) for c in clases)
        radio = round(6 + 14 * math.sqrt(total / maximo), 1)
        detalle = " · ".join(f"{c.split()[0] if c != 'Riesgo Medio' else 'Medio'} {int(f[c])}" for c in reversed(clases))
        datos = [{"name": c, "value": int(f[c]), "lugar": f["nombre"], "tipo": f["tipo"], "municipio": f["municipio"],
                  "total": total, "detalle": detalle, "itemStyle": {"color": COLOR_CLASE[c]}} for c in clases if f[c] > 0]
        series.append({"type": "pie", "name": f["nombre"], "coordinateSystem": "geo", "geoIndex": 0, "center": [f["lon"], f["lat"]],
                       "radius": [round(radio * 0.52, 1), radio], "data": datos, "z": 2 + k / 1000,
                       "label": {"show": False}, "labelLine": {"show": False}, "startAngle": 90,
                       "itemStyle": {"borderColor": "#FFFFFF", "borderWidth": 1.2},
                       "emphasis": {"scale": True, "scaleSize": 4},
                       "animationDelay": k * 12})
        if radio >= 13:  # el número en el centro solo cuando cabe
            conteos.append({"name": f["nombre"], "value": [f["lon"], f["lat"], total]})
    series.append({"id": "conteos", "type": "scatter", "coordinateSystem": "geo", "geoIndex": 0, "data": conteos, "symbolSize": 0,
                   "silent": True, "z": 5, "label": {"show": True, "formatter": js("(p) => p.value[2]"), "color": TINTA,
                                                      "fontSize": 10, "fontWeight": 700}})
    opciones = _base(
        geo=_geo_base(nombre, **_encuadre_puntos(texto, filas)),
        series=series,
        legend=_leyenda(data=list(clases), top="bottom"),
        tooltip={**_base()["tooltip"], "trigger": "item", "formatter": js(
            "(p) => p.data && p.data.lugar ? '<b>' + p.data.lugar + '</b><br/>' + p.data.tipo + ' · ' + p.data.municipio + "
            "'<br/><b>' + p.data.total + '</b> gestantes: ' + p.data.detalle : ''")})
    return Grafico(opciones, 540, titulo, {"puntos": len(filas), "clases": list(clases)}, mapa=(nombre, texto))


# Las opciones se cachean (st.cache_data): con los mismos datos no se recalculan en cada ejecución.
for _nombre in ("dispersion_presion", "barras_nulos", "barras_clases", "histogramas_comparados", "curva_aprendizaje",
                "escalabilidad", "f1_por_particion", "dispersion_hiperparametros", "mapa_calor", "curvas_roc", "barras_simples",
                "mapa_coropletico", "mapa_concentracion"):
    globals()[_nombre] = st.cache_data(show_spinner=False, max_entries=128)(globals()[_nombre])
