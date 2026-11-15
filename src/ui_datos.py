"""Fase 3 — Secciones del laboratorio para los datos de trabajo (pestañas 02, 03, 04 y 10).

Flujo:  pestaña 02  obtener datos crudos (generarlos o subir un archivo) y medir la escalabilidad
        pestaña 04  depurarlos paso a paso y dejarlos como conjunto de trabajo, apartando el lote de demostración
        pestaña 03  EDA del conjunto de trabajo frente al dataset base
        pestaña 10  cargar el lote de demostración y medir una versión sobre registros que no usó
"""
import hashlib
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from src import conjunto_trabajo, experimentos, graficos
from src.config import SEMILLA
from src.depuracion import depurar, leer_crudo, reporte
from src.generador_sintetico import SEPARADOR, a_texto, ensuciar, generar

AVISO_SINTETICO = ("Los registros generados sirven para **demostrar escalabilidad, no para validar clínicamente**. "
                   "Salen de las mismas 1.200 gestantes sintéticas: generar más no agrega evidencia clínica.")


def miles(n):
    return f"{int(n):,}".replace(",", ".")


def _guardar_crudo(nombre, datos, huella, info=None, inyectado=None):
    st.session_state["crudo"] = {"nombre": nombre, "datos": datos, "huella": huella, "info": info, "inyectado": inyectado}
    st.session_state.pop("depurado", None)


def _leer_subido(nombre, contenido):
    huella = hashlib.sha256(contenido).hexdigest()
    if st.session_state.get("crudo", {}).get("huella") == huella:
        return  # ya está leído: no se vuelve a leer en cada interacción
    barra = st.progress(0.0, text="Leyendo el archivo por lotes…")
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / Path(nombre).name
        ruta.write_bytes(contenido)
        try:
            datos, info = leer_crudo(ruta, lambda leidas, total: barra.progress(
                min(leidas / total, 1.0) if total else 0.5, text=f"{miles(leidas)} filas leídas…"))
        except Exception as error:  # archivo ilegible o con formato no soportado
            barra.empty()
            st.error(f"No se pudo leer el archivo: {error}")
            return
    barra.empty()
    _guardar_crudo(nombre, datos, huella, info)


def seccion_conjunto(usuario, permitido, trabajo):
    """Pestaña 02: estado del conjunto de trabajo, generador, carga de archivos crudos y escalabilidad."""
    st.markdown("#### Conjunto de trabajo: datos para entrenar")
    if trabajo:
        st.info(f"**Activo:** {trabajo['nombre']} · {miles(trabajo['n_trabajo'])} registros para entrenamiento, validación y "
                f"prueba · lote de demostración de {miles(trabajo['n_lote'])} · establecido por {trabajo['usuario']} "
                f"el {trabajo['fecha'][:10]}.")
        if st.button("Volver al dataset base", icon=":material/restart_alt:", disabled=not permitido):
            conjunto_trabajo.restablecer()
            st.rerun()
    else:
        st.caption("Activo: el dataset base de 1.200 gestantes. Genere o suba datos crudos aquí y depúrelos en la pestaña 04 "
                   "para entrenar con más registros.")
    st.warning(AVISO_SINTETICO, icon=":material/info:")

    generador, archivo = st.columns(2, gap="large")
    with generador:
        st.markdown("**Generador sintético**")
        st.caption("A partir de las 1.200: interpola entre gestantes parecidas de la misma clase y área. Cada registro "
                   "conserva la clase de su registro base y lleva `origen = sintetico_generado`.")
        c = st.columns(2)
        n = c[0].number_input("Registros", 1000, 200000, 10000, step=5000, key="gen_n",
                              help="Por ejemplo 5.000, 10.000, 20.000 o 30.000")
        semilla = c[1].number_input("Semilla", 0, 2**31 - 1, SEMILLA, key="gen_semilla")
        sucio = st.toggle("Con errores de captura simulados (para demostrar la depuración)", True, key="gen_sucio")
        if st.button("Generar", type="primary", icon=":material/auto_awesome:", disabled=not permitido):
            datos, inyectado = generar(n, semilla), None
            if sucio:
                datos, inyectado = ensuciar(datos, semilla)
            _guardar_crudo(f"Sintético generado (N={miles(n)}, semilla {semilla})", datos, f"gen-{n}-{semilla}-{sucio}",
                           inyectado=inyectado)
    with archivo:
        st.markdown("**Archivo crudo con etiqueta**")
        st.caption("CSV, TXT separado por «|» o Excel, con las columnas del dataset y la clase `riesgo_obstetrico`. "
                   "Se lee por lotes de 5.000 filas. Solo datos ficticios o generados.")
        subido = st.file_uploader("Archivo crudo", type=["csv", "txt", "xlsx"], key="crudo_subido", disabled=not permitido)
        if subido is not None:
            _leer_subido(subido.name, subido.getvalue())
    if not permitido:
        st.caption("Solo el administrador genera o sube datos de trabajo.")

    crudo = st.session_state.get("crudo")
    if crudo:
        lectura = f" · {crudo['info']['lotes']} lote(s), separador {crudo['info']['separador']!r}" if crudo["info"] else ""
        st.success(f"**Datos crudos listos:** {crudo['nombre']} · {miles(len(crudo['datos']))} filas{lectura}. "
                   "Continúe en la pestaña **04 Limpieza** para depurarlos.")
        with st.expander("Ver las primeras filas crudas"):
            st.dataframe(crudo["datos"].head(100), width="stretch")
        st.download_button("Descargar el archivo crudo (.txt con «|»)", a_texto(crudo["datos"]).encode("utf-8"),
                           "materna_crudo.txt", "text/plain", icon=":material/download:")

    st.markdown("#### Escalabilidad")
    st.markdown("Para 5.000, 10.000, 20.000 y 30.000 registros: genera el archivo crudo, lo **carga**, lo **depura** y "
                "**entrena** una vez (70 % de los registros limpios, mejores hiperparámetros de la Fase 2).")
    algoritmo = st.selectbox("Algoritmo", experimentos.ALGORITMOS, key="escala_algoritmo")
    if st.button("Medir la escalabilidad", icon=":material/speed:", disabled=not permitido):
        tamanos = conjunto_trabajo.TAMANOS_ESCALABILIDAD
        barra = st.progress(0.0, text="Empezando…")
        etapas = ["generando", "cargando", "limpiando", "entrenando"]
        conjunto_trabajo.medir_escalabilidad(tamanos, algoritmo, al_avanzar=lambda n, etapa: barra.progress(
            (tamanos.index(n) * 4 + etapas.index(etapa)) / (len(tamanos) * 4), text=f"{miles(n)} registros: {etapa}…"))
        barra.empty()
    tabla = conjunto_trabajo.escalabilidad_guardada()
    if tabla is not None:
        grafico, datos = st.columns([3, 2], gap="large")
        grafico.altair_chart(graficos.escalabilidad(tabla), width="stretch")
        datos.dataframe(tabla[["registros", "filas_limpias", "carga_s", "limpieza_s", "entrenamiento_s", "memoria_mb"]].rename(columns={
            "registros": "Registros", "filas_limpias": "Filas limpias", "carga_s": "Carga (s)", "limpieza_s": "Limpieza (s)",
            "entrenamiento_s": "Entrenamiento (s)", "memoria_mb": "Memoria (MB)"}), hide_index=True, width="stretch")
        st.caption(f"Medido en este equipo con {tabla['algoritmo'].iloc[0]}. La memoria es la del conjunto limpio cargado. "
                   f"La **SVM** cuesta aproximadamente el cuadrado del número de registros: con más de "
                   f"{miles(experimentos.MAX_SVM)} de entrenamiento se ajusta con una muestra estratificada de ese tamaño.")


def seccion_eda(base, datos_trabajo, trabajo, etiquetas):
    """Pestaña 03: el conjunto de trabajo frente al dataset base."""
    if datos_trabajo is None:
        return
    st.markdown(f"**EDA del conjunto de trabajo** · {trabajo['nombre']} ({miles(len(datos_trabajo))} registros)")
    c1, c2 = st.columns([2, 3], gap="large")
    c1.altair_chart(graficos.barras_clases(datos_trabajo), width="stretch")
    c2.dataframe(pd.DataFrame([{
        "Variable": etiquetas[v], "Media base": base[v].mean(), "Media trabajo": datos_trabajo[v].mean(),
        "Mediana base": base[v].median(), "Mediana trabajo": datos_trabajo[v].median(),
        "% nulos base": base[v].isna().mean() * 100, "% nulos trabajo": datos_trabajo[v].isna().mean() * 100,
    } for v in etiquetas]).round(2), hide_index=True, width="stretch")
    st.caption("Las distribuciones casi coinciden con las del dataset base porque los registros se generaron a partir de él.")


def seccion_depuracion(usuario, permitido):
    """Pestaña 04: depura los datos crudos de la sesión, paso a paso, y los deja como conjunto de trabajo."""
    st.markdown("#### Depuración de los datos crudos")
    crudo = st.session_state.get("crudo")
    if not crudo:
        st.caption("Aún no hay datos crudos. Genérelos o suba un archivo en la pestaña 02 y vuelva aquí para depurarlos.")
        return
    depurado = st.session_state.get("depurado")
    if not depurado or depurado["huella"] != crudo["huella"]:
        try:
            limpio, pasos = depurar(crudo["datos"])
        except ValueError as error:
            st.error(str(error))
            return
        depurado = st.session_state["depurado"] = {"huella": crudo["huella"], "limpio": limpio, "pasos": pasos}
    limpio, pasos = depurado["limpio"], reporte(depurado["pasos"])
    st.markdown(f"**{crudo['nombre']}**")
    m = st.columns(4)
    m[0].metric("Filas crudas", miles(len(crudo["datos"])))
    m[1].metric("Filas limpias", miles(len(limpio)))
    m[2].metric("Filas retiradas", miles(len(crudo["datos"]) - len(limpio)))
    m[3].metric("Celdas cambiadas", miles(pasos["Celdas cambiadas"].sum()))
    st.dataframe(pasos, hide_index=True, width="stretch")
    if crudo["inyectado"]:
        with st.expander("Errores de captura simulados que traía este archivo"):
            st.dataframe(pd.DataFrame(crudo["inyectado"].items(), columns=["Error simulado", "Cantidad"]), hide_index=True)
            st.caption("Algunas celdas reciben dos errores a la vez y el generador produce algunas filas idénticas por sí "
                       "solo: por eso los conteos de la depuración no coinciden uno a uno con esta tabla.")
    d = st.columns(2)
    d[0].download_button("Descargar el reporte de depuración (CSV)", pasos.to_csv(index=False).encode("utf-8-sig"),
                         "materna_reporte_depuracion.csv", "text/csv", icon=":material/download:")
    d[1].download_button("Descargar los datos limpios (CSV)", limpio.to_csv(index=False).encode("utf-8-sig"),
                         "materna_datos_limpios.csv", "text/csv", icon=":material/download:")

    st.markdown("**Usar como conjunto de trabajo**")
    n_lote = st.number_input(
        "Lote de demostración (registros que se apartan y nunca entran al entrenamiento)", 0, len(limpio) // 2,
        min(len(limpio) // 2, round(len(limpio) / 10)), step=100, key="lote_n",
        help="Se aparta de forma estratificada antes de partir en entrenamiento, validación y prueba")
    if st.button("Usar como conjunto de trabajo", type="primary", icon=":material/dataset:", disabled=not permitido):
        try:
            conjunto_trabajo.establecer(limpio, crudo["nombre"], usuario["usuario"], n_lote)
        except ValueError as error:
            st.error(str(error))
        else:
            st.rerun()
    if not permitido:
        st.caption("Solo el administrador cambia el conjunto de trabajo.")


def seccion_lote(trabajo):
    """Pestaña 10: carga el lote de demostración y mide una versión sobre registros que no usó."""
    st.markdown("#### Lote de demostración: registros que el modelo no usó")
    if not trabajo or not trabajo["n_lote"]:
        st.caption("No hay lote de demostración. Se aparta al establecer un conjunto de trabajo en la pestaña 04.")
        return
    versiones = {r["version"]: r for r in experimentos.leer_registro() if r.get("datos_huella") == trabajo["huella"]}
    if not versiones:
        st.caption(f"Hay un lote de {miles(trabajo['n_lote'])} registros apartado. Entrene una versión con el conjunto de "
                   "trabajo activo (pestaña 08) para medirla sobre él.")
        return
    elegida = st.selectbox("Versión", sorted(versiones, reverse=True), key="lote_version",
                           format_func=lambda v: f"{v} · {versiones[v]['algoritmo']} · partición {versiones[v]['particion']}")
    if st.button(f"Cargar el lote de demostración ({miles(trabajo['n_lote'])} registros) y evaluar", icon=":material/upload:"):
        st.session_state.setdefault("lote_eval", {})[elegida] = conjunto_trabajo.evaluar_lote(experimentos.cargar_modelo(elegida))
    metricas = st.session_state.get("lote_eval", {}).get(elegida)
    if metricas:
        r = versiones[elegida]
        st.dataframe(pd.DataFrame([
            {"Conjunto": "Prueba (usado para medir al entrenar)", "Registros": r["n_prueba"], "F1-macro": r["prueba_f1_macro"],
             "Recall Alto": r["prueba_recall_alto"], "Accuracy": r["prueba_accuracy"], "Costo clínico": r["prueba_costo_clinico_total"]},
            {"Conjunto": "Lote de demostración (no usado)", "Registros": metricas["n"], "F1-macro": metricas["f1_macro"],
             "Recall Alto": metricas["recall_alto"], "Accuracy": metricas["accuracy"], "Costo clínico": metricas["costo_clinico_total"]},
        ]).round(4), hide_index=True, width="stretch")
        st.caption("El lote se apartó antes de partir los datos: el modelo no lo vio al entrenar ni al medirse. "
                   "Aviso: si los datos son generados, el lote sale de las mismas 1.200 gestantes; demuestra el "
                   "procedimiento, no el desempeño clínico.")
