"""MATERNA — Módulo 1: Laboratorio de ML (Fase 3). Bienvenida, inicio de sesión y menú por rol.

Arquitectura de dos módulos independientes pero integrados:
  Módulo 1 (esta app, Streamlit)  fases 01 a 11 con la ingesta auditable; audiencia: docente y evaluadores.
  Módulo 2 (flutter_app/, web y móvil)  despliegue para el personal de salud: captura manual, carga masiva
                                   y semáforo. Consume los JSON que entrega el Módulo 1 (pestaña 12).

Páginas (carpeta paginas/):
  Laboratorio ML  fases 01 a 11, entrega al Módulo 2 y ética (inicio)
  Variables 3280  tabla de decisiones del filtro de la Resolución 3280
  Triaje (Fase 2) demo anterior del triaje; provisional hasta que el Módulo 2 esté listo

Ejecutar:        streamlit run app_demo.py
Crear usuarios:  python -m src.autenticacion crear-usuario <usuario> --rol <rol> --nombre "<nombre>"
                 (quedan en .streamlit/secrets.toml, que no se sube al repositorio)
"""
import time

import streamlit as st

from src import ui_theme as ui
from src.autenticacion import INTENTOS_MAXIMOS, ROLES, autenticar, cargar_usuarios, puede

SEGUNDOS_BLOQUEO = 60


def html(bloque):
    st.markdown(bloque, unsafe_allow_html=True)


st.set_page_config(page_title="MATERNA — Alerta temprana", page_icon="🪷", layout="wide")

# Pantalla de bienvenida solo al abrir la página: Streamlit vuelve a ejecutar el script en cada
# interacción, y sin esta marca el logo reaparecería con cada clic. Es el primer elemento, para que
# la app no asome antes del logo.
if not st.session_state.get("bienvenida_mostrada"):
    # HTML propio (no de usuarios): seguro de incrustar. st.iframe exige altura positiva; el CSS lo oculta.
    st.iframe(ui.pantalla_bienvenida(), height=1, alt=ui.ETIQUETA_IFRAME_BIENVENIDA)
    st.session_state["bienvenida_mostrada"] = True
html(ui.estilos())


def formulario_login():
    usuarios = cargar_usuarios(st.secrets)
    _, centro, _ = st.columns([1, 1.4, 1])
    with centro:
        html(ui.cabecera("Módulo 1 · Laboratorio de ML", "MATERNA", "Alerta temprana materno-perinatal. Inicie sesión para continuar."))
        if not usuarios:
            st.warning("No hay usuarios configurados. Cree uno desde la terminal y reinicie la consola:\n\n"
                       "`python -m src.autenticacion crear-usuario admin --rol administrador --nombre \"Administrador\"`")
            return
        with st.form("login"):
            usuario = st.text_input("Usuario", autocomplete="username")
            contrasena = st.text_input("Contraseña", type="password", autocomplete="current-password")
            entrar = st.form_submit_button("Ingresar", type="primary", width="stretch")
        if entrar:
            espera = st.session_state.get("bloqueo_hasta", 0) - time.time()
            if espera > 0:
                st.error(f"Demasiados intentos fallidos. Espere {int(espera) + 1} s.")
                return
            datos = autenticar(usuario, contrasena, usuarios)
            if datos:
                st.session_state["usuario"] = datos
                st.session_state.pop("intentos", None)
                st.rerun()
            st.session_state["intentos"] = st.session_state.get("intentos", 0) + 1
            if st.session_state["intentos"] >= INTENTOS_MAXIMOS:
                st.session_state["bloqueo_hasta"] = time.time() + SEGUNDOS_BLOQUEO
                st.session_state["intentos"] = 0
            st.error("Usuario o contraseña incorrectos.")
        st.caption("Para revisar el sistema: administrador, médico auditor y evaluador académico. El personal de salud que "
                   "atiende a las gestantes usa el Módulo 2, la app MATERNA web y móvil. Las contraseñas se guardan solo como hash scrypt.")


usuario = st.session_state.get("usuario")
if usuario is None:
    formulario_login()
    st.stop()

SECCIONES = {
    "Módulo 1 · Laboratorio de ML": [
        ("laboratorio", st.Page("paginas/laboratorio.py", title="Laboratorio ML", icon=":material/science:", default=True)),
        ("variables_3280", st.Page("paginas/variables_3280.py", title="Variables 3280", icon=":material/fact_check:")),
    ],
    # Provisional: se retira cuando el Módulo 2 (app Flutter, web y móvil) esté listo
    "Módulo 2 · Vista provisional": [
        ("triaje", st.Page("paginas/triaje.py", title="Triaje (Fase 2)", icon=":material/stethoscope:")),
    ],
}
menu = {seccion: [p for permiso, p in paginas if puede(usuario, permiso)] for seccion, paginas in SECCIONES.items()}
pagina = st.navigation({seccion: paginas for seccion, paginas in menu.items() if paginas})
pagina.run()

# Después de la página, para no cambiar el orden de los botones propios de cada página en la barra lateral
with st.sidebar:
    st.divider()
    html(ui.tarjeta_usuario(usuario["nombre"], ROLES[usuario["rol"]]))
    if st.button("Cerrar sesión", icon=":material/logout:", width="stretch"):
        for clave in ("usuario", "entrenamiento", "archivo_ips"):
            st.session_state.pop(clave, None)
        st.rerun()
