"""Fase 3 — Sección «Interpretación de las métricas» del laboratorio (fase 10) y avisos fijos."""
import pandas as pd
import streamlit as st

from src import experimentos, interpretacion, patrones, ui_laboratorio as lab, ui_theme as ui
from src.config import NOMBRES_CLASES

AVISO_CORTO = "Datos sintéticos: mide cuánto reproduce el etiquetado, no el desempeño clínico."


def aviso():
    """Aviso fijo que acompaña toda tabla de métricas."""
    st.warning(interpretacion.AVISO, icon=":material/info:")


@st.cache_data(show_spinner="Midiendo el sistema en cada conjunto (con 2.000 remuestreos bootstrap)…")
def _evaluacion(sistema, huella_trabajo, patrones_vigentes):
    """La huella del conjunto de trabajo y los patrones vigentes son parte de la clave: si cambian, se vuelve a medir."""
    return interpretacion.evaluar_sistema(sistema)


def _explicacion(panel, conjunto):
    st.markdown(f"**¿Qué es?** {panel['que_es']}\n\n**¿Por qué la usamos?** {panel['por_que']}\n\n"
                f"**¿Cómo se lee?** {panel['como_se_lee']}")
    st.info(f"**En {conjunto.lower()}:** {panel['frase']}")


def seccion_interpretacion(trabajo):
    """Sistema y conjunto elegidos, cuatro indicadores, la matriz con cómo leerla, usados frente a no usados
    y el panel de cada métrica (qué es, por qué se usa y cómo se lee)."""
    versiones = {r["version"]: r for r in experimentos.leer_registro()}
    c = st.columns([2, 3], vertical_alignment="bottom")
    sistema = c[0].selectbox(
        "Sistema que se interpreta", [interpretacion.MODELO_EN_USO, *sorted(versiones, reverse=True)], key="interp_sistema",
        format_func=lambda s: s if s not in versiones else f"{s} · {versiones[s]['algoritmo']} · partición {versiones[s]['particion']}")
    try:
        vigentes = patrones.vigentes()
        evaluacion = _evaluacion(sistema, trabajo["huella"] if trabajo else None,
                                 tuple(vigentes["id_gestante"]) if not vigentes.empty else ())
    except ValueError as error:
        st.error(str(error))
        return
    conjuntos = evaluacion["conjuntos"]
    nombres = list(conjuntos)
    conjunto = c[1].radio("Conjunto que se explica", nombres, index=nombres.index("Prueba"), horizontal=True, key="interp_conjunto")
    elegido = conjuntos[conjunto]
    paneles = {p["nombre"]: p for p in interpretacion.paneles(elegido)}
    st.caption(f"Datos: {evaluacion['datos']}. Sistema híbrido: modelo + reglas clínicas. "
               f"{conjunto}: {interpretacion.USO[conjunto].lower()}.")

    # Indicadores: la cifra, una frase armada desde los números y la explicación al alcance de un clic
    columnas = st.columns(4, gap="small")
    for i, (columna, k) in enumerate(zip(columnas, interpretacion.indicadores(elegido))):
        with columna, lab.tarjeta(f"kpi-{i}", alto="stretch"):
            st.markdown(ui.indicador(k["nombre"], k["valor"], k["pie"]), unsafe_allow_html=True)
            with st.popover("¿por qué?"):
                _explicacion(paneles[k["panel"]], conjunto)

    izquierda, derecha = st.columns(2, gap="medium")
    with izquierda, lab.tarjeta("matriz", "Matriz de confusión", f"{conjunto} · {int(elegido['metricas']['n'])} gestantes",
                                alto="stretch"):
        st.markdown(ui.matriz(elegido["matriz"]), unsafe_allow_html=True)
    with derecha, lab.tarjeta("leer", "Cómo leerlo", alto="stretch"):
        st.markdown(ui.puntos(interpretacion.como_leer(elegido)), unsafe_allow_html=True)
        st.markdown(interpretacion.frase_criticos(elegido))
        st.markdown(ui.nota_sintetico(AVISO_CORTO), unsafe_allow_html=True)

    with lab.tarjeta("usados", "Patrones usados y no usados"):
        comparativa = pd.DataFrame(interpretacion.tabla_comparativa(conjuntos)).round(4)
        st.dataframe(comparativa, hide_index=True, width="stretch")
        st.markdown(interpretacion.frase_comparacion(conjuntos))
        if interpretacion.LOTE not in conjuntos:
            st.caption("Sin lote de demostración para este sistema: el conjunto de patrones no usados se aparta al establecer un "
                       f"conjunto de trabajo en {lab.nombre_fase('04')} y vale para las versiones entrenadas con él.")
        if interpretacion.NUEVOS in conjuntos:
            st.caption("Los registros nuevos son muy pocos: sus métricas muestran el procedimiento, no una medida estable.")
        st.download_button("Descargar el reporte de evaluación (CSV)", comparativa.to_csv(index=False).encode("utf-8-sig"),
                           "materna_reporte_evaluacion.csv", "text/csv", icon=":material/download:")

    with lab.tarjeta("paneles", "Cada métrica: qué es, por qué la usamos y cómo se lee", conjunto):
        for panel in paneles.values():
            with st.expander(f"{panel['nombre']} · {panel['valor']}"):
                _explicacion(panel, conjunto)
                if panel["nombre"] == "Costo clínico":
                    st.markdown(ui.matriz(panel["matriz"], tono=lambda i, j, v: "d" if v >= 5 else "e" if v else "",
                                          descripcion="Matriz de costo clínico"), unsafe_allow_html=True)
                elif "matriz" in panel:
                    st.dataframe(pd.DataFrame(panel["matriz"], index=[f"Real: {c}" for c in NOMBRES_CLASES],
                                              columns=[f"Asignada: {c}" for c in NOMBRES_CLASES]), width="content")
    aviso()
    with st.expander("Explicación para la sustentación: por qué las métricas son casi perfectas"):
        st.markdown(interpretacion.EXPLICACION)
