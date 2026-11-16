"""Fase 3 — Secciones del laboratorio para los patrones nuevos: formulario (fase 02) y reentrenamiento (fase 08)."""
import pandas as pd
import streamlit as st

from src import experimentos, patrones, ui_laboratorio as lab, ui_theme as ui
from src.config import MAPA_TARGET, VARS_CON_NULOS
from src.ui_theme import miles

OPCION_PROXY = "Que la calcule el sistema (proxy por reglas)"
ATIENDE = {"Medico": "Médico", "Auxiliar de enfermeria": "Auxiliar de enfermería"}


def _campo(columna, v):
    """El control de una variable del catálogo. Sin límites en el control: la validación explica los rechazos."""
    nombre, etiqueta = v["nombre"], v["etiqueta"]
    if v["tipo"] == "categorica":
        return columna.selectbox(etiqueta, v["valores"], format_func=lambda x: ATIENDE.get(x, x), key=f"patron_{nombre}")
    if v["tipo"] == "binaria":
        return int(columna.selectbox(etiqueta, ["No", "Sí"], key=f"patron_{nombre}") == "Sí")
    lo, hi = v["rango"]
    opcional = " · opcional" if nombre in VARS_CON_NULOS else ""
    return columna.number_input(f"{etiqueta} ({v.get('unidad', '')})", value=None, step=1 if v["tipo"] == "entero" else 0.1,
                                placeholder=f"{lo} a {hi}{opcional}", key=f"patron_{nombre}")


def seccion_formulario(usuario, puede_agregar, puede_retirar, datos, nombre_datos):
    """Fase 02: agrega un patrón a mano, con contador, validación y bitácora."""
    vigentes = patrones.vigentes()
    total = len(datos) + len(vigentes)
    if len(vigentes):
        st.markdown(ui.cifra(miles(len(datos)), miles(total), "patrones"), unsafe_allow_html=True)
    else:
        st.markdown(ui.cifra(miles(total), etiqueta="patrones · aún sin patrones nuevos"), unsafe_allow_html=True)
    st.markdown(f"Registre una gestante con su clase. Se valida contra los rangos del catálogo de la Resolución 3280, no puede "
                f"repetir un registro existente y queda en la bitácora. Se suma a: **{nombre_datos}**.")

    with st.form("formulario_patron"):
        catalogo = patrones.catalogo_modelo()
        registro = {}
        for inicio in range(0, len(catalogo), 4):
            columnas = st.columns(4)
            for columna, v in zip(columnas, catalogo[inicio:inicio + 4]):
                registro[v["nombre"]] = _campo(columna, v)
        clase = st.radio("Clase", [*MAPA_TARGET, OPCION_PROXY], horizontal=True, key="patron_clase")
        enviado = st.form_submit_button("Agregar el patrón", type="primary", icon=":material/add:", disabled=not puede_agregar)
    st.caption("«Proxy por reglas»: la clase la pone el sistema en uso (modelo + reglas). Sirve para probar el flujo, pero no "
               "le enseña nada nuevo al modelo: repite lo que ya cree. Glucosa y FCF pueden quedar vacías.")
    if enviado:
        try:
            proxy = clase == OPCION_PROXY
            evento = st.session_state["patron_evento"] = patrones.agregar(
                registro, None if proxy else clase, usuario["usuario"], datos, patrones.PROXY if proxy else patrones.ASIGNADA)
        except ValueError as error:
            st.session_state.pop("patron_evento", None)
            st.error(f"**Patrón rechazado.** {error}")
            lab.anotar("Patrón rechazado por la validación")
        else:
            lab.anotar(f"Patrón {evento['id']} agregado · {miles(evento['contador_antes'])} → {miles(evento['contador_despues'])}")
    evento = st.session_state.get("patron_evento")
    if evento:
        st.success(f"Patrón **{evento['id']}** agregado como **{evento['clase']}** "
                   f"({patrones.ETIQUETAS_ORIGEN[evento[patrones.COLUMNA_ETIQUETA]].lower()}). Registros: "
                   f"**{miles(evento['contador_antes'])} → {miles(evento['contador_despues'])}**. Para que el modelo lo use, "
                   f"reentrene en {lab.nombre_fase('08')}.")
        lab.boton_ir("08", "Reentrenar y comparar en la fase 08")

    bitacora = patrones.tabla_eventos()
    if not bitacora.empty:
        st.markdown("**Bitácora de patrones**")
        st.dataframe(bitacora, hide_index=True, width="stretch")
        st.download_button("Descargar la bitácora (CSV)", bitacora.to_csv(index=False).encode("utf-8-sig"),
                           "materna_bitacora_patrones.csv", "text/csv", icon=":material/download:")
    vigentes = patrones.vigentes()
    if not vigentes.empty:
        r = st.columns([2, 1], vertical_alignment="bottom")
        elegido = r[0].selectbox("Retirar un patrón vigente (p. ej. uno mal digitado)", list(vigentes["id_gestante"]), key="patron_retirar")
        if r[1].button("Retirar", icon=":material/delete:", disabled=not puede_retirar):
            patrones.retirar(elegido, usuario["usuario"], len(datos))
            st.session_state.pop("patron_evento", None)
            lab.anotar(f"Patrón {elegido} retirado")
            st.rerun()


def seccion_reentrenar(permitido, huella_datos, entrenar):
    """Fase 08: reentrena una versión con los patrones nuevos y compara antes y después.

    `entrenar(algoritmo, hiperparametros, proporciones, semilla, patrones)` es la función del laboratorio
    que entrena mostrando el avance.
    """
    vigentes = patrones.vigentes()
    if vigentes.empty:
        st.caption(f"Aún no hay patrones nuevos. Agregue uno en {lab.nombre_fase('02')}.")
        return
    referencias = {r["version"]: r for r in experimentos.leer_registro() if r.get("datos_huella") == huella_datos}
    if not referencias:
        st.caption(f"Hay {len(vigentes)} patrón(es) nuevo(s). Entrene primero una versión con los datos actuales (arriba): "
                   "será el «antes» de la comparación.")
        return
    elegida = st.selectbox(
        "Versión de referencia (el «antes»)", sorted(referencias, reverse=True), key="reentrenar_referencia",
        format_func=lambda v: f"{v} · {referencias[v]['algoritmo']} · partición {referencias[v]['particion']} · "
                              f"{len(referencias[v].get('patrones') or [])} patrón(es)")
    antes = referencias[elegida]
    st.caption(f"Se entrena otra vez {antes['algoritmo']} con los mismos hiperparámetros, partición y semilla que {elegida}, "
               f"sumando los {len(vigentes)} patrón(es) vigentes **solo al entrenamiento**. La validación y la prueba no "
               "cambian: por eso el antes y el después se pueden comparar.")
    if st.button("Reentrenar con el nuevo patrón", type="primary", icon=":material/model_training:", disabled=not permitido):
        proporciones = tuple(int(p) for p in antes["particion"].split("/"))
        resultado = entrenar(antes["algoritmo"], antes["hiperparametros"], proporciones, antes["semilla"], vigentes)
        if resultado:
            st.session_state["reentrenamiento"] = {"antes": antes, "despues": resultado["registro"]}
    if not permitido:
        st.caption("Solo el administrador puede reentrenar.")
    comparacion = st.session_state.get("reentrenamiento")
    if comparacion:
        a, d = comparacion["antes"], comparacion["despues"]
        st.success(f"Versión **{d['version']}** creada con {len(d['patrones'])} patrón(es) nuevo(s) en el entrenamiento.")
        st.markdown(ui.cifra(miles(a["n_entrenamiento"]), miles(d["n_entrenamiento"]), "registros de entrenamiento"),
                    unsafe_allow_html=True)
        st.dataframe(pd.DataFrame([
            {"": etiqueta, "Versión": r["version"], "Patrones nuevos": len(r.get("patrones") or []),
             "n entrenamiento": r["n_entrenamiento"], "F1-macro validación": r["val_f1_macro"],
             "Recall Alto validación": r["val_recall_alto"], "F1-macro prueba": r["prueba_f1_macro"],
             "Recall Alto prueba": r["prueba_recall_alto"], "Costo prueba": int(r["prueba_costo_clinico_total"])}
            for etiqueta, r in [("Antes", a), ("Después", d)]]).round(4), hide_index=True, width="stretch")
        cambio = d["val_f1_macro"] - a["val_f1_macro"]
        sentido = "no cambió" if abs(cambio) < 5e-5 else f"{'subió' if cambio > 0 else 'bajó'} {abs(cambio):.4f}".replace(".", ",")
        st.markdown(f"El entrenamiento pasó de {miles(a['n_entrenamiento'])} a {miles(d['n_entrenamiento'])} registros y el "
                    f"F1-macro en validación **{sentido}**. Unos pocos patrones entre cientos o miles casi no mueven las "
                    "métricas: lo que se demuestra es el procedimiento y su trazabilidad.")
