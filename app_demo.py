"""MATERNA — Módulo 1: Laboratorio de ML (Fase 3). Bienvenida, inicio de sesión y menú por rol.

Arquitectura de dos módulos independientes pero integrados:
  Módulo 1 (esta app, Streamlit)  fases 01 a 11 con la ingesta auditable; audiencia: docente y equipo.
  Módulo 2 (flutter_app/, web y móvil)  despliegue para el personal de salud: captura manual, carga masiva
                                   y semáforo. Consume los JSON que entrega el Módulo 1 (pestaña 12).

Páginas (carpeta paginas/):
  Laboratorio ML  fases 01 a 11, entrega al Módulo 2, ética y lista de chequeo (inicio)
  Variables 3280  tabla de decisiones del filtro de la Resolución 3280
  Triaje (Fase 2) demo anterior del triaje; provisional hasta que el Módulo 2 esté listo

Ejecutar:        streamlit run app_demo.py
Crear usuarios:  python -m src.autenticacion crear-usuario <usuario> --rol <rol> --nombre "<nombre>"
                 (quedan en .streamlit/secrets.toml, que no se sube al repositorio)
"""
import importlib
import threading
import time

import streamlit as st

from src import ui_theme as ui
from src.autenticacion import INTENTOS_MAXIMOS, ROLES, autenticar, cargar_usuarios, puede

SEGUNDOS_BLOQUEO = 60
# Módulos que importa el laboratorio. La primera vez tardan unos 4,5 s (scikit-learn, pandas, matplotlib,
# imbalanced-learn, Altair); se precargan mientras se ven la bienvenida y el login.
MODULOS_LABORATORIO = (
    "src.graficos", "src.clinical_rules", "src.consolidado_ips", "src.data_preprocessing", "src.experimentos", "src.conjunto_trabajo",
    "src.evaluate", "src.exportar_a_dart", "src.filtro_3280", "src.generar_ejemplo_ips", "src.inspeccionar_ips",
    "src.train_models",
)


def html(bloque):
    st.markdown(bloque, unsafe_allow_html=True)


@st.cache_resource(show_spinner=False)
def precargar_laboratorio():
    """Importa en segundo plano, una sola vez por servidor, lo que necesita el laboratorio: así, al iniciar
    sesión, no hay que esperar a que Python cargue las librerías. Importar es seguro entre hilos."""
    hilo = threading.Thread(target=lambda: [importlib.import_module(m) for m in MODULOS_LABORATORIO],
                            name="precarga-laboratorio", daemon=True)
    hilo.start()
    return hilo


st.set_page_config(page_title="MATERNA — Alerta temprana", page_icon="🪷", layout="wide")
precargar_laboratorio()

# Pantalla de bienvenida, solo al abrir la página (Streamlit vuelve a ejecutar el script en cada interacción).
# La primera ejecución envía ÚNICAMENTE la capa del logo y se detiene: nada de la app puede asomar antes.
# Cuando la capa ya cubre la pantalla, el componente avisa ("montada") y la app se dibuja debajo.
# El lugar de la bienvenida queda reservado en todas las ejecuciones (st.empty) para que los elementos
# siguientes conserven su posición: si se corrieran, Streamlit mostraría copias viejas del login.
lugar_bienvenida = st.empty()
if not st.session_state.get("bienvenida_mostrada"):
    with lugar_bienvenida:
        montada = ui.bienvenida_montada()
    if not montada:
        st.stop()
    st.session_state["bienvenida_mostrada"] = True
html(ui.estilos())


def formulario_login():
    """Dibuja el login. Devuelve los datos del usuario si acaba de iniciar sesión; si no, None."""
    usuarios = cargar_usuarios(st.secrets)
    # Pantalla completa: a la izquierda la marca, a la derecha el acceso (estilos .st-key-mt-login* en ui_theme)
    with st.container(key="mt-login"):
        marca, acceso = st.columns(2, gap="small")
        with marca:
            html(ui.login_marca())
        with acceso, st.container(key="mt-login-acceso"):
            html(ui.login_encabezado())
            if not usuarios:
                st.warning("No hay usuarios configurados. Cree uno desde la terminal y reinicie la consola:\n\n"
                           "`python -m src.autenticacion crear-usuario admin --rol administrador --nombre \"Administrador\"`")
                return None
            with st.form("login"):
                usuario = st.text_input("Usuario", autocomplete="username")
                contrasena = st.text_input("Contraseña", type="password", autocomplete="current-password")
                entrar = st.form_submit_button("Ingresar", type="primary", width="stretch")
            if entrar:
                espera = st.session_state.get("bloqueo_hasta", 0) - time.time()
                if espera > 0:
                    st.error(f"Demasiados intentos fallidos. Espere {int(espera) + 1} s.")
                    return None
                datos = autenticar(usuario, contrasena, usuarios)
                if datos:
                    st.session_state["usuario"] = datos
                    st.session_state.pop("intentos", None)
                    return datos
                st.session_state["intentos"] = st.session_state.get("intentos", 0) + 1
                if st.session_state["intentos"] >= INTENTOS_MAXIMOS:
                    st.session_state["bloqueo_hasta"] = time.time() + SEGUNDOS_BLOQUEO
                    st.session_state["intentos"] = 0
                st.error("Usuario o contraseña incorrectos.")
            st.caption("Para revisar el sistema: administrador y médico auditor. El personal de salud que "
                       "atiende a las gestantes usa el Módulo 2, la app MATERNA web y móvil. Las contraseñas se guardan solo como hash scrypt.")
    return None


# El login vive en un lugar propio. Al iniciar sesión se borra en esta MISMA ejecución y el laboratorio se
# dibuja a continuación: con st.rerun() el login quedaba en pantalla (atenuado y duplicado) mientras el
# laboratorio cargaba en frío la primera vez.
lugar_login = st.empty()
usuario = st.session_state.get("usuario")
if usuario is None:
    with lugar_login.container():
        usuario = formulario_login()
    if usuario is None:
        st.stop()
    # En el lugar del login (no en uno nuevo, para no correr la página) mientras el laboratorio se dibuja
    lugar_login.caption("Abriendo el laboratorio…")

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
lugar_login.empty()

# Después de la página, para no cambiar el orden de los botones propios de cada página en la barra lateral
with st.sidebar:
    st.divider()
    html(ui.tarjeta_usuario(usuario["nombre"], ROLES[usuario["rol"]]))
    if st.button("Cerrar sesión", icon=":material/logout:", width="stretch"):
        for clave in ("usuario", "entrenamiento", "experimento_hp", "curvas_exp", "archivo_ips", "ingesta_ips", "crudo",
                      "depurado", "lote_eval", "patron_evento", "reentrenamiento", "publicacion", "paridad_dart"):
            st.session_state.pop(clave, None)
        st.rerun()
