"""Fase 3 — Sección «Interpretación de las métricas» del laboratorio (pestaña 10) y avisos fijos."""
import pandas as pd
import streamlit as st

from src import experimentos, interpretacion
from src.config import NOMBRES_CLASES


def aviso():
    """Aviso fijo que acompaña toda tabla de métricas."""
    st.warning(interpretacion.AVISO, icon=":material/info:")


@st.cache_data(show_spinner="Midiendo el sistema en cada conjunto (con 2.000 remuestreos bootstrap)…")
def _evaluacion(sistema, huella_trabajo):
    """La huella del conjunto de trabajo es parte de la clave: si cambia, se vuelve a medir."""
    return interpretacion.evaluar_sistema(sistema)


def seccion_interpretacion(trabajo):
    st.markdown("#### Interpretación de las métricas")
    aviso()
    with st.expander("Explicación para la sustentación: por qué las métricas son casi perfectas"):
        st.markdown(interpretacion.EXPLICACION)

    versiones = {r["version"]: r for r in experimentos.leer_registro()}
    sistema = st.selectbox(
        "Sistema que se interpreta", [interpretacion.MODELO_EN_USO, *sorted(versiones, reverse=True)], key="interp_sistema",
        format_func=lambda s: s if s not in versiones else f"{s} · {versiones[s]['algoritmo']} · partición {versiones[s]['particion']}")
    try:
        evaluacion = _evaluacion(sistema, trabajo["huella"] if trabajo else None)
    except ValueError as error:
        st.error(str(error))
        return
    conjuntos = evaluacion["conjuntos"]
    st.caption(f"Datos: {evaluacion['datos']}. Sistema híbrido: modelo + reglas clínicas.")

    st.markdown("**Patrones usados y no usados**")
    st.dataframe(pd.DataFrame(interpretacion.tabla_comparativa(conjuntos)).round(4), hide_index=True, width="stretch")
    st.markdown(interpretacion.frase_comparacion(conjuntos))
    if interpretacion.LOTE not in conjuntos:
        st.caption("Sin lote de demostración para este sistema: el conjunto de patrones no usados se aparta al establecer un "
                   "conjunto de trabajo (pestaña 04) y vale para las versiones entrenadas con él.")

    nombres = list(conjuntos)
    conjunto = st.radio("Conjunto que se explica", nombres, index=nombres.index("Prueba"), horizontal=True, key="interp_conjunto")
    elegido = conjuntos[conjunto]
    st.markdown(interpretacion.frase_criticos(elegido))
    for panel in interpretacion.paneles(elegido):
        with st.expander(f"{panel['nombre']} · {panel['valor']}"):
            st.markdown(f"**¿Qué es?** {panel['que_es']}\n\n**¿Por qué la usamos?** {panel['por_que']}\n\n"
                        f"**¿Cómo se lee?** {panel['como_se_lee']}")
            st.info(f"**En {conjunto.lower()}:** {panel['frase']}")
            if "matriz" in panel:
                st.dataframe(pd.DataFrame(panel["matriz"], index=[f"Real: {c}" for c in NOMBRES_CLASES],
                                          columns=[f"Asignada: {c}" for c in NOMBRES_CLASES]), width="content")
