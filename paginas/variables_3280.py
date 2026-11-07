"""MATERNA — Tabla de decisiones de variables frente a la Resolución 3280 de 2018 (filtro 3280)."""
import pandas as pd
import streamlit as st

from src import ui_theme as ui
from src.filtro_3280 import DECISIONES, cargar_catalogo, tabla_decisiones

st.markdown(ui.cabecera("Ruta Materno Perinatal · Resolución 3280 de 2018", "Variables 3280",
                        "Qué hace MATERNA con cada dato de la gestante y por qué.",
                        ["config/variables_3280.json", "src/filtro_3280.py"]), unsafe_allow_html=True)

catalogo = cargar_catalogo()
tabla = tabla_decisiones()

conteo = tabla["Decisión"].value_counts()
columnas = st.columns(len(DECISIONES))
for col, decision in zip(columnas, DECISIONES):
    col.metric(decision.replace("_", " ").capitalize(), int(conteo.get(decision, 0)),
               help=catalogo["_decisiones"][decision])

st.markdown(
    "Las **11 variables del modelo** son las de la Fase 2. Las de **capturar y alertar** vienen de la ruta: "
    "se registran y pueden generar una alerta, pero **no entran al modelo** hasta tener datos reales de gestantes "
    "(entrenar con ellas exigiría inventar datos). Etnia y territorio quedan **solo para auditar sesgos**."
)

f1, f2 = st.columns(2)
decisiones = f1.multiselect("Decisión", list(DECISIONES), default=list(DECISIONES))
secciones = f2.multiselect("Sección de la ruta", sorted(tabla["Sección 3280"].unique()), placeholder="Todas las secciones")
vista = tabla[tabla["Decisión"].isin(decisiones)]
if secciones:
    vista = vista[vista["Sección 3280"].isin(secciones)]
st.dataframe(vista, hide_index=True, width="stretch", height=520,
             column_config={"Justificación": st.column_config.TextColumn(width="large"),
                            "Verificación": st.column_config.TextColumn(width="medium")})

with st.expander("Alertas de la ruta y qué tan verificado está cada corte"):
    alertas = pd.DataFrame([
        {"Variable": v["etiqueta"], "Condición": v["alerta"]["condicion"], "Umbral": v["alerta"].get("umbral", ""),
         "Severidad": v["alerta"]["severidad"], "Mensaje": v["alerta"]["mensaje"],
         "Verificación": catalogo["_verificacion"][v["verificacion"]]}
        for v in catalogo["variables"] if "alerta" in v])
    st.dataframe(alertas, hide_index=True, width="stretch")
    st.caption("Los cortes marcados como criterio clínico por validar deben revisarse con un asesor en ginecobstetricia "
               "antes de cualquier uso en campo. Las alertas nunca cambian la clasificación del modelo.")
