"""Fase 3 — Sección «Publicar al Módulo 2» del laboratorio (fase 12)."""
import pandas as pd
import streamlit as st

from src import experimentos, publicacion, ui_laboratorio as lab, ui_metricas

AVISO_RECOMPILAR = ("Los teléfonos reciben el modelo nuevo **al recompilar la app**: los JSON van dentro de ella "
                    "(`flutter build apk` o `flutter build web`). La paridad en **Dart** se comprueba con `flutter test`, "
                    "donde esté instalado Flutter.")


def tabla_dos_modulos():
    """Qué significa «agregar uno más» en cada módulo."""
    st.dataframe(pd.DataFrame([
        ("Qué se agrega", "Una gestante atendida", "Un patrón para enseñarle al modelo"),
        ("Lleva la clase puesta", "No: la app la calcula", "Sí: la pone quien lo registra (o el sistema)"),
        ("Dónde suma", "En el historial de la app", "En el conjunto de trabajo"),
        ("Cambia el modelo", "No, nunca", "Solo si se reentrena y se publica"),
    ], columns=["", "App del celular (Módulo 2)", "Laboratorio (Módulo 1)"]), hide_index=True, width="stretch")
    st.caption("En la app nada entrena: el celular solo usa el modelo que trae. El modelo cambia únicamente cuando el "
               "administrador lo publica desde aquí y la app se recompila.")


def seccion_publicar(usuario, permitido):
    actual = publicacion.publicado()
    st.info(f"La app usa hoy el modelo **{actual['version']}** ({actual['origen']}) · SHA-256 `{actual['sha256'][:16]}…`")
    st.caption("Solo se publica el **Random Forest**, con las 4 reglas críticas y el catálogo 3280: la app solo tiene motor de "
               "árboles. La Regresión Logística y la SVM se entrenan y se comparan en el laboratorio, pero no se publican.")

    registro = experimentos.tabla_registro()
    candidatas = registro[registro["algoritmo"] == publicacion.ALGORITMO_PUBLICABLE] if not registro.empty else registro
    if candidatas.empty:
        st.caption(f"No hay versiones de Random Forest para publicar. Entrene una en {lab.nombre_fase('08')}.")
    else:
        mejor = experimentos.mejor_version(candidatas)
        filas = candidatas.set_index("version")
        elegida = st.selectbox(
            "Versión de Random Forest que se publica", sorted(filas.index, reverse=True),
            index=sorted(filas.index, reverse=True).index(mejor), key="publicar_version",
            format_func=lambda v: f"{v} · partición {filas.loc[v, 'particion']} · F1-macro validación "
                                  f"{filas.loc[v, 'val_f1_macro']:.4f} · recall Alto {filas.loc[v, 'val_recall_alto']:.4f}"
                                  + (" · la mejor según el criterio" if v == mejor else ""))
        st.caption(f"Datos: {filas.loc[elegida, 'datos']}. Criterio de selección: mayor F1-macro en validación y, en empate, "
                   "mayor recall de Alto Riesgo.")
        ui_metricas.aviso()
        confirmado = st.checkbox("Entiendo que esto reemplaza el modelo que usa la app (los JSON de flutter_app/assets)",
                                 key="publicar_confirmar")
        if st.button("Publicar al Módulo 2", type="primary", icon=":material/publish:", disabled=not (permitido and confirmado)):
            with st.spinner("Exportando y comprobando la paridad en Python…"):
                try:
                    resultado = st.session_state["publicacion"] = publicacion.publicar(elegida, usuario["usuario"])
                    lab.anotar(f"Publicado al Módulo 2 como {resultado['version']} (sale de {elegida}) · paridad en Python comprobada")
                except ValueError as error:
                    st.session_state.pop("publicacion", None)
                    st.error(str(error))
                else:
                    st.rerun()
    if not permitido:
        st.caption("Solo el administrador publica.")

    resultado = st.session_state.get("publicacion")
    if resultado:
        st.success(f"Publicado como **{resultado['version']}** (sale de {resultado['origen']}). Paridad en Python: "
                   f"{resultado['casos_paridad']} casos, diferencia máxima en probabilidades "
                   f"{resultado['dif_probabilidades']:.1e}.")
        st.dataframe(pd.DataFrame(resultado["archivos"]), hide_index=True, width="content")
    st.warning(AVISO_RECOMPILAR, icon=":material/phone_android:")

    if publicacion.flutter():
        if st.button("Comprobar la paridad en Dart (flutter test)", icon=":material/rule:"):
            with st.spinner("Corriendo las pruebas de paridad en Dart…"):
                st.session_state["paridad_dart"] = publicacion.paridad_dart()
            lab.anotar("Paridad en Dart: " + ("pasa" if st.session_state["paridad_dart"][0] else "FALLA"))
        if "paridad_dart" in st.session_state:
            paso, salida = st.session_state["paridad_dart"]
            (st.success if paso else st.error)("Paridad en Dart: " + ("todas las pruebas pasaron." if paso else "hay pruebas que fallan."))
            st.code(salida)
    else:
        st.caption("Flutter no está en el PATH de este equipo: la paridad en Dart se comprueba en una terminal con "
                   "`cd flutter_app; flutter test`.")

    historial = publicacion.tabla_historial()
    if not historial.empty:
        st.markdown("**Historial de publicaciones**")
        st.dataframe(historial.round(4), hide_index=True, width="stretch")
    if not actual["oficial"]:
        if st.button("Volver al modelo oficial v1", icon=":material/restart_alt:", disabled=not permitido):
            with st.spinner("Exportando el modelo oficial de la Fase 2…"):
                publicacion.restablecer_oficial(usuario["usuario"])
            st.session_state.pop("publicacion", None)
            st.session_state.pop("paridad_dart", None)
            lab.anotar("Se volvió al modelo oficial v1")
            st.rerun()
