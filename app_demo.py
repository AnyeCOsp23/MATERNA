"""MATERNA — Prototipo de interfaz para la sustentación de la Fase 2.

Simula la app de campo offline-first: la inferencia corre localmente (sin internet) y cada
evaluación se guarda en una base SQLite local marcada como "pendiente de sincronización".

Ejecutar:  streamlit run app_demo.py
Requiere los modelos entrenados:  python -m src.train_models
"""
import json
import sqlite3
from datetime import datetime

import joblib
import pandas as pd
import streamlit as st

from src.clinical_rules import ETIQUETAS_PROTEINURIA, PROTOCOLO, evaluar_riesgo_hibrido
from src.config import DIR_METRICAS, DIR_MODELOS, RAIZ, RUTA_DATASET
from src.data_preprocessing import cargar_dataset

RUTA_BD_LOCAL = RAIZ / "data" / "registros_locales.sqlite"
ARCHIVOS_MODELO = {
    "SVM (calibrado)": "modelo_svm_calibrado.joblib",
    "Regresión Logística": "modelo_regresion_logistica.joblib",
}
ESTILO_CATEGORIA = {
    "Alto Riesgo": ("#C62828", "🔴", "ALTO RIESGO — EMERGENCIA OBSTÉTRICA"),
    "Riesgo Medio": ("#F9A825", "🟡", "RIESGO MEDIO — VALORACIÓN PRIORITARIA"),
    "Bajo Riesgo": ("#2E7D32", "🟢", "BAJO RIESGO — CONTROL PRENATAL DE RUTINA"),
}

# Casos precargados para la demostración en vivo
CASOS_DEMO = {
    "Caso 1 · Emergencia (Uribia)": dict(
        edad=26, municipio="Uribia", area_residencia="Rural disperso", pertenencia_etnica="Wayuu",
        semanas_gestacion=31, n_controles_prenatales=1, atendido_por="Partera tradicional",
        pas_mmhg=165, pad_mmhg=108, fcf_bpm=None, glucosa_mgdl=110.5, proteinuria=2, convulsiones=1),
    "Caso 2 · Sin controles previos (Manaure)": dict(
        edad=17, municipio="Manaure", area_residencia="Rural disperso", pertenencia_etnica="Wayuu",
        semanas_gestacion=24, n_controles_prenatales=0, atendido_por="Auxiliar de enfermeria",
        pas_mmhg=128, pad_mmhg=82, fcf_bpm=150.0, glucosa_mgdl=None, proteinuria=0, convulsiones=0),
    "Caso 3 · Control de rutina (Valledupar)": dict(
        edad=27, municipio="Valledupar", area_residencia="Cabecera", pertenencia_etnica="Mestiza",
        semanas_gestacion=28, n_controles_prenatales=5, atendido_por="Medico",
        pas_mmhg=110, pad_mmhg=70, fcf_bpm=142.0, glucosa_mgdl=88.0, proteinuria=0, convulsiones=0),
}


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


def modelo_recomendado():
    try:
        with open(DIR_METRICAS / "resumen_evaluacion.json", encoding="utf-8") as f:
            return "SVM (calibrado)" if json.load(f)["modelo_principal_para_hibrido"] == "SVM" else "Regresión Logística"
    except FileNotFoundError:
        return "SVM (calibrado)"


st.set_page_config(page_title="MATERNA — Alerta temprana", page_icon="🤰", layout="wide")

faltantes = [a for a in ARCHIVOS_MODELO.values() if not (DIR_MODELOS / a).exists()]
if faltantes:
    st.error("No se encontraron los modelos entrenados. Ejecuta primero:  `python -m src.train_models`")
    st.stop()

cat = catalogos()

# ---------------------------------------------------------------- barra lateral
with st.sidebar:
    st.markdown("### ⚙️ Configuración")
    opciones = list(ARCHIVOS_MODELO)
    nombre_modelo = st.selectbox("Modelo estadístico", opciones, index=opciones.index(modelo_recomendado()),
                                 help="El SVM fue el modelo seleccionado en validación. La regla clínica aplica con cualquiera.")
    st.markdown("### 🧪 Casos de demostración")
    for nombre_caso, caso in CASOS_DEMO.items():
        if st.button(nombre_caso, width="stretch"):
            st.session_state["caso"] = caso
    st.divider()
    st.markdown(f"📴 **Modo offline-first**  \nInferencia local · **{pendientes_sincronizar()}** registro(s) pendiente(s) de sincronización")
    if st.button("🔄 Simular sincronización con la ESE/IPS", width="stretch"):
        with bd_local() as con:
            n = con.execute("UPDATE evaluaciones SET sincronizado = 1 WHERE sincronizado = 0").rowcount
        st.success(f"{n} registro(s) marcados como sincronizados (simulación: no se envían datos).")
    st.caption("Idioma: Español. La interfaz en Wayuunaiki queda para la Fase 3 y requiere una traducción validada con la comunidad.")

caso = st.session_state.get("caso", CASOS_DEMO["Caso 3 · Control de rutina (Valledupar)"])

st.markdown("## 🤰 MATERNA — Sistema de Alerta Temprana de Riesgo Materno-Perinatal")
st.caption("Universidad Popular del Cesar · Proyecto de aula IA · La Guajira y Cesar · "
           "Prototipo académico entrenado con datos sintéticos: NO usar para decisiones clínicas reales.")

# ---------------------------------------------------------------- módulo 1
st.markdown("### Módulo 1 · Registro de la gestante y signos vitales")
municipios = sorted(cat["municipio_a_depto"])
with st.form("registro"):
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Demografía y ubicación**")
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
        st.markdown("**Constantes vitales y paraclínicos**")
        pas = st.number_input("Presión sistólica — PAS (mmHg)", 60, 250, int(caso["pas_mmhg"]))
        pad = st.number_input("Presión diastólica — PAD (mmHg)", 30, 150, int(caso["pad_mmhg"]))
        sin_fcf = st.checkbox("FCF no disponible (sin doppler fetal)", value=caso["fcf_bpm"] is None)
        fcf = st.number_input("Frecuencia cardiaca fetal (lpm)", 60.0, 220.0, float(caso["fcf_bpm"] or 140.0), disabled=sin_fcf)
        sin_glu = st.checkbox("Glucosa no disponible (sin glucómetro/reactivos)", value=caso["glucosa_mgdl"] is None)
        glucosa = st.number_input("Glucosa (mg/dL)", 30.0, 600.0, float(caso["glucosa_mgdl"] or 95.0), disabled=sin_glu)
        proteinuria = st.select_slider("Proteinuria en tira reactiva", options=[0, 1, 2], value=int(caso["proteinuria"]),
                                       format_func=lambda v: ETIQUETAS_PROTEINURIA[v])
        convulsiones = st.radio("Convulsiones / eclampsia", ["No", "Sí"], horizontal=True, index=int(caso["convulsiones"]))
    evaluar = st.form_submit_button("🩺 EVALUAR RIESGO MATERNO", type="primary", width="stretch")

if evaluar:
    registro = {
        "edad": edad, "departamento": cat["municipio_a_depto"][municipio], "municipio": municipio,
        "pertenencia_etnica": etnia, "area_residencia": area, "semanas_gestacion": semanas,
        "n_controles_prenatales": controles, "atendido_por": atendido, "pas_mmhg": pas, "pad_mmhg": pad,
        "fcf_bpm": None if sin_fcf else fcf, "glucosa_mgdl": None if sin_glu else glucosa,
        "proteinuria": proteinuria, "convulsiones": int(convulsiones == "Sí"),
    }
    resultado = evaluar_riesgo_hibrido(registro, cargar_modelo(ARCHIVOS_MODELO[nombre_modelo]))
    guardar_local(registro, resultado, nombre_modelo)
    color, icono, titulo = ESTILO_CATEGORIA[resultado.categoria]

    # ------------------------------------------------------------ módulo 2
    st.markdown("### Módulo 2 · Panel de diagnóstico e inferencia híbrida")
    st.markdown(
        f"<div style='background:{color};color:white;padding:18px 22px;border-radius:12px;"
        f"font-size:1.45rem;font-weight:700'>{icono} CATEGORÍA FINAL: {titulo}</div>",
        unsafe_allow_html=True)
    st.write("")
    if resultado.origen == "regla_clinica":
        st.error("⚠️ **Alerta de seguridad clínica: regla de sobreescritura activada.**  \n"
                 + "  \n".join(f"• {a}" for a in resultado.alertas)
                 + f"  \nEl modelo estadístico por sí solo habría clasificado: **{resultado.categoria_modelo}**. "
                 "La regla prevalece sobre el modelo.")
    else:
        st.info("Ninguna regla crítica se activó. La categoría proviene del modelo estadístico.")

    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown(f"**📊 Probabilidades del modelo ({nombre_modelo})**")
        for clase, p in resultado.probabilidades_modelo.items():
            st.progress(p, text=f"{clase}: {p:.1%}")
    with c2:
        st.markdown("**🔎 Trazabilidad de la decisión**")
        st.markdown(
            f"- Origen: **{'Regla clínica (GPC Minsalud)' if resultado.origen == 'regla_clinica' else 'Modelo de aprendizaje automático'}**\n"
            f"- Predicción del modelo: **{resultado.categoria_modelo}**\n"
            f"- Sobreescritura por regla: **{'SÍ' if resultado.origen == 'regla_clinica' else 'NO'}**")
        if sin_fcf or sin_glu:
            faltan = ", ".join(n for n, f in [("FCF", sin_fcf), ("glucosa", sin_glu)] if f)
            st.warning(f"Dato(s) no disponible(s): {faltan}. Se imputaron con la mediana de entrenamiento "
                       "por área y trimestre. Interpretar con cautela.")

    # ------------------------------------------------------------ módulo 3
    st.markdown("### Módulo 3 · Acciones orientadoras")
    for i, paso in enumerate(PROTOCOLO[resultado.categoria], 1):
        st.markdown(f"{i}. {paso}")
    st.caption("Texto orientativo para la demostración académica: debe validarse con un asesor clínico y con la red de "
               "referencia de cada ESE/IPS antes de cualquier uso en campo.")
    st.success("💾 Evaluación guardada localmente (SQLite), pendiente de sincronización.")

with st.expander("📁 Registros guardados en este dispositivo"):
    with bd_local() as con:
        st.dataframe(pd.read_sql("SELECT * FROM evaluaciones ORDER BY id DESC LIMIT 50", con), width="stretch")
