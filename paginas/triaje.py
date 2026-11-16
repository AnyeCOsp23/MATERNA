"""MATERNA — Página de triaje de la consola (formulario de la gestante e inferencia híbrida).

Simula la app de campo offline-first: la inferencia corre localmente (sin internet) y cada
evaluación se guarda en una base SQLite local marcada como "pendiente de sincronización".
La configuración de la página, la bienvenida, los estilos y el inicio de sesión están en app_demo.py.
"""
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

import joblib
import pandas as pd
import streamlit as st

from src.clinical_rules import ETIQUETAS_PROTEINURIA, PROTOCOLO, evaluar_riesgo_hibrido
from src.config import DIR_METRICAS, DIR_MODELOS, RAIZ, RUTA_DATASET
from src.data_preprocessing import cargar_dataset
from src import recorrido, ui_laboratorio as lab, ui_theme as ui

# MATERNA_BD permite a las pruebas usar una base temporal sin tocar la del dispositivo
RUTA_BD_LOCAL = Path(os.environ.get("MATERNA_BD", RAIZ / "data" / "registros_locales.sqlite"))
ARCHIVOS_MODELO = {
    "Random Forest": "modelo_random_forest.joblib",
    "SVM (calibrado)": "modelo_svm_calibrado.joblib",
    "Regresión Logística": "modelo_regresion_logistica.joblib",
}
# nombre en reports/metrics -> nombre en la interfaz
NOMBRE_UI = {"Random Forest": "Random Forest", "SVM": "SVM (calibrado)", "Regresión Logística": "Regresión Logística"}

# Casos precargados para la demostración en vivo
CASOS_DEMO = recorrido.CASOS


def ver_recorrido():
    """Lleva a la fase 07 del laboratorio con la gestante recién evaluada lista para «Ver el recorrido»."""
    st.session_state["recorrido_registro"] = st.session_state.get("ultimo_registro_triaje")
    st.session_state["recorrido_caso"] = recorrido.ULTIMA
    st.session_state["recorrido_visible"] = True
    lab.ir_a("07")


@st.cache_resource
def cargar_modelo(archivo):
    return joblib.load(DIR_MODELOS / archivo)


@st.cache_data
def catalogos():
    df = cargar_dataset(RUTA_DATASET)
    return {
        "municipio_a_depto": df.groupby("municipio")["departamento"].first().to_dict(),
        "etnias": sorted(df["pertenencia_etnica"].unique()),
        "atendido_por": sorted(df["atendido_por"].unique()),
    }


def bd_local():
    con = sqlite3.connect(RUTA_BD_LOCAL)
    con.execute("""CREATE TABLE IF NOT EXISTS evaluaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, municipio TEXT, edad INTEGER,
        semanas INTEGER, pas INTEGER, pad INTEGER, categoria TEXT, origen TEXT, modelo TEXT,
        sincronizado INTEGER DEFAULT 0)""")
    return con


def guardar_local(registro, resultado, nombre_modelo):
    with bd_local() as con:
        con.execute(
            "INSERT INTO evaluaciones (fecha, municipio, edad, semanas, pas, pad, categoria, origen, modelo) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (datetime.now().isoformat(timespec="seconds"), registro["municipio"], registro["edad"],
             registro["semanas_gestacion"], registro["pas_mmhg"], registro["pad_mmhg"],
             resultado.categoria, resultado.origen, nombre_modelo))


def pendientes_sincronizar():
    with bd_local() as con:
        return con.execute("SELECT COUNT(*) FROM evaluaciones WHERE sincronizado = 0").fetchone()[0]


def resumen_evaluacion():
    try:
        with open(DIR_METRICAS / "resumen_evaluacion.json", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def modelo_recomendado():
    return NOMBRE_UI.get(resumen_evaluacion().get("modelo_principal_para_hibrido"), "Random Forest")


@st.cache_data
def kpis_prueba():
    """Métricas del sistema híbrido seleccionado en el conjunto de prueba (reports/metrics)."""
    try:
        sistema = resumen_evaluacion()["sistema_principal"]
        fila = pd.read_csv(DIR_METRICAS / "metricas_test.csv", index_col=0).loc[sistema]
    except (FileNotFoundError, KeyError):
        return []
    fmt = lambda v: f"{float(v):.3f}".replace(".", ",")  # 3 decimales: 0,998 no debe verse como 1,00
    return [("F1-macro", fmt(fila["f1_macro"])), ("Recall Alto", fmt(fila["recall_alto"])),
            ("ROC-AUC", fmt(fila["roc_auc_ovr_macro"]))]


def html(bloque):
    st.markdown(bloque, unsafe_allow_html=True)



faltantes = [a for a in ARCHIVOS_MODELO.values() if not (DIR_MODELOS / a).exists()]
if faltantes:
    st.error("No se encontraron los modelos entrenados. Ejecuta primero:  `python -m src.train_models`")
    st.stop()

cat = catalogos()
st.info("**Vista provisional del Módulo 2.** La app de usuario final definitiva es MATERNA en Flutter (web y móvil), con captura manual, carga masiva de archivos de la IPS y semáforo de riesgo. Esta página es la demo de la Fase 2.", icon=":material/info:")

# ---------------------------------------------------------------- barra lateral
with st.sidebar:
    st.markdown("#### Modelo")
    opciones = list(ARCHIVOS_MODELO)
    nombre_modelo = st.selectbox("Modelo estadístico", opciones, index=opciones.index(modelo_recomendado()),
                                 label_visibility="collapsed",
                                 help="Random Forest fue el modelo seleccionado en validación. La regla clínica aplica con cualquiera.")
    st.markdown("#### Casos de demostración")
    for nombre_caso, caso in CASOS_DEMO.items():
        if st.button(nombre_caso, width="stretch"):
            st.session_state["caso"] = caso
    st.markdown("#### Sincronización")
    if st.button("Simular sincronización con la ESE/IPS", width="stretch"):
        with bd_local() as con:
            n = con.execute("UPDATE evaluaciones SET sincronizado = 1 WHERE sincronizado = 0").rowcount
        st.toast(f"{n} registro(s) marcados como sincronizados (simulación: no se envían datos).",
                 icon=":material/cloud_done:", duration=3)
    st.caption("Idioma: Español. La interfaz en Wayuunaiki queda para la Fase 3 y requiere una traducción validada con la comunidad.")

caso = st.session_state.get("caso", CASOS_DEMO["Caso 3 · Control de rutina (Valledupar)"])
encabezado = st.empty()  # se dibuja al final para que el contador de pendientes incluya la evaluación actual

# ---------------------------------------------------------------- módulo 1
html(ui.titulo_seccion("01", "Registro de la gestante y signos vitales"))
municipios = sorted(cat["municipio_a_depto"])
with st.form("registro", border=False):
    c1, c2 = st.columns(2, gap="large")
    with c1:
        html(ui.grupo("Demografía y ubicación"))
        edad = st.number_input("Edad (años)", 10, 55, int(caso["edad"]))
        municipio = st.selectbox("Municipio", municipios, index=municipios.index(caso["municipio"]),
                                 format_func=lambda m: f"{m} ({cat['municipio_a_depto'][m]})")
        area = st.radio("Área de residencia", ["Rural disperso", "Cabecera"], horizontal=True,
                        index=["Rural disperso", "Cabecera"].index(caso["area_residencia"]))
        etnia = st.selectbox("Pertenencia étnica", cat["etnias"], index=cat["etnias"].index(caso["pertenencia_etnica"]),
                             help="Se registra para el seguimiento poblacional, pero NO es una entrada del modelo (decisión ética, ver README).")
        semanas = st.number_input("Semanas de gestación", 4, 42, int(caso["semanas_gestacion"]))
        controles = st.number_input("Controles prenatales previos", 0, 20, int(caso["n_controles_prenatales"]))
        atendido = st.selectbox("Atendido por", cat["atendido_por"], index=cat["atendido_por"].index(caso["atendido_por"]))
    with c2:
        html(ui.grupo("Constantes vitales y paraclínicos"))
        pas = st.number_input("Presión sistólica — PAS (mmHg)", 60, 250, int(caso["pas_mmhg"]))
        pad = st.number_input("Presión diastólica — PAD (mmHg)", 30, 150, int(caso["pad_mmhg"]))
        sin_fcf = st.checkbox("FCF no disponible (sin doppler fetal)", value=caso["fcf_bpm"] is None)
        fcf = st.number_input("Frecuencia cardiaca fetal (lpm)", 60.0, 220.0, float(caso["fcf_bpm"] or 140.0), disabled=sin_fcf)
        sin_glu = st.checkbox("Glucosa no disponible (sin glucómetro/reactivos)", value=caso["glucosa_mgdl"] is None)
        glucosa = st.number_input("Glucosa (mg/dL)", 30.0, 600.0, float(caso["glucosa_mgdl"] or 95.0), disabled=sin_glu)
        proteinuria = st.select_slider("Proteinuria en tira reactiva", options=[0, 1, 2], value=int(caso["proteinuria"]),
                                       format_func=lambda v: ETIQUETAS_PROTEINURIA[v])
        convulsiones = st.radio("Convulsiones / eclampsia", ["No", "Sí"], horizontal=True, index=int(caso["convulsiones"]))
    evaluar = st.form_submit_button("Evaluar riesgo materno", type="primary", width="stretch")

if evaluar:
    registro = {
        "edad": edad, "departamento": cat["municipio_a_depto"][municipio], "municipio": municipio,
        "pertenencia_etnica": etnia, "area_residencia": area, "semanas_gestacion": semanas,
        "n_controles_prenatales": controles, "atendido_por": atendido, "pas_mmhg": pas, "pad_mmhg": pad,
        "fcf_bpm": None if sin_fcf else fcf, "glucosa_mgdl": None if sin_glu else glucosa,
        "proteinuria": proteinuria, "convulsiones": int(convulsiones == "Sí"),
    }
    with st.spinner("Evaluando riesgo…"):
        resultado = evaluar_riesgo_hibrido(registro, cargar_modelo(ARCHIVOS_MODELO[nombre_modelo]))
        guardar_local(registro, resultado, nombre_modelo)
    st.session_state["ultimo_registro_triaje"] = registro

    # ------------------------------------------------------------ módulo 2
    html(ui.titulo_seccion("02", "Diagnóstico e inferencia híbrida"))
    html(ui.tarjeta_resultado(resultado.categoria, resultado.origen))
    if resultado.origen == "regla_clinica":
        html(ui.aviso_regla(resultado.alertas, resultado.categoria_modelo))
    else:
        html(ui.aviso("Ninguna regla crítica se activó. La categoría proviene del modelo estadístico.", "info"))
    if sin_fcf or sin_glu:
        faltan = " y ".join(n for n, f in [("FCF", sin_fcf), ("glucosa", sin_glu)] if f)
        html(ui.aviso(f"Sin dato de {faltan}: se imputó con la mediana de entrenamiento por área y trimestre. "
                      "Interpretar con cautela.", "warn", "Dato no disponible", orden=2))
    html(ui.panel_probabilidades(resultado.probabilidades_modelo, resultado.categoria_modelo,
                                 nombre_modelo, resultado.origen))
    # Opcional: el recorrido animado de esta gestante por el Random Forest en uso y las reglas (fase 07 del laboratorio)
    st.button("Ver cómo decidió el sistema", icon=":material/account_tree:", on_click=ver_recorrido,
              help="Abre la fase 07 del laboratorio con el recorrido de esta gestante por el Random Forest en uso y las reglas.")

    # ------------------------------------------------------------ módulo 3
    html(ui.titulo_seccion("03", "Acciones orientadoras"))
    html(ui.protocolo(resultado.categoria, PROTOCOLO[resultado.categoria]))
    st.toast("Evaluación guardada en el dispositivo · pendiente de sincronización",
             icon=":material/cloud_upload:", duration=3)

with encabezado:
    html(ui.encabezado(nombre_modelo, pendientes_sincronizar(), kpis_prueba()))

st.write("")
with st.expander("Registros guardados en este dispositivo"):
    with bd_local() as con:
        st.dataframe(pd.read_sql("SELECT * FROM evaluaciones ORDER BY id DESC LIMIT 50", con), width="stretch")
st.caption("Universidad Popular del Cesar · Proyecto de aula de Inteligencia Artificial · "
           "Prototipo académico entrenado con datos sintéticos: no usar para decisiones clínicas reales.")
