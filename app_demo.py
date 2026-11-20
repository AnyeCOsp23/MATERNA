"""MATERNA — Módulo 1: Laboratorio de ML (Fase 3). Bienvenida, inicio de sesión y menú por rol.

Arquitectura de dos módulos independientes pero integrados:
  Módulo 1 (esta app, Streamlit)  fases 01 a 11 con la ingesta auditable; audiencia: docente y equipo.
  Módulo 2 (flutter_app/, web y móvil)  despliegue para el personal de salud: captura manual, carga masiva
                                   y semáforo. Consume los JSON que entrega el Módulo 1 (fase 12).

Páginas (carpeta paginas/):
  Laboratorio ML  las 12 fases y ética; muestra una fase a la vez, elegida en el menú lateral
  Variables 3280  tabla de decisiones del filtro de la Resolución 3280
  Triaje (Módulo 2) vista provisional del triaje (demo de la Fase 2); la app definitiva del Módulo 2 es Flutter

Ejecutar:        streamlit run app_demo.py
Crear usuarios:  python -m src.autenticacion crear-usuario <usuario> --rol <rol> --nombre "<nombre>"
                 (quedan en .streamlit/secrets.toml, que no se sube al repositorio)
"""
import importlib
import threading
import time
from pathlib import Path

import streamlit as st

from src import graficos, recuperacion, ui_laboratorio as lab, ui_theme as ui
from src.autenticacion import INTENTOS_MAXIMOS, LONGITUD_MINIMA, ROLES, autenticar, cargar_usuarios, puede

SEGUNDOS_BLOQUEO = 60
FAVICON = Path(__file__).resolve().parent / "static" / "favicon.png"
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


# Favicon: el isotipo de MATERNA (static/favicon.png, cuadrado de 128 px con fondo transparente)
st.set_page_config(page_title="MATERNA — Alerta temprana", page_icon=str(FAVICON), layout="wide")
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
# ?debug=1 en la URL: muestra prefers-reduced-motion y el arranque de cada animación
DEBUG_ANIMACION = st.query_params.get("debug") == "1"
graficos.modo_debug(DEBUG_ANIMACION)
ui.motor_animaciones(DEBUG_ANIMACION)  # entrada y transiciones de los diagramas HTML (una vez por página)


def ir_a_recuperar(paso):
    """on_click de los botones de la recuperación: None vuelve al inicio de sesión."""
    st.session_state["recuperar"] = paso
    if paso is None:
        st.session_state.pop("recuperar_id", None)


def formulario_recuperacion(usuarios):
    """«¿Olvidó su contraseña?»: pedir el código por correo y, con él, elegir una contraseña nueva (src/recuperacion.py)."""
    config = recuperacion.config_correo()
    if st.session_state.get("recuperar") == "pedir":
        if config is None:
            st.info("La recuperación por correo aún no está configurada en este equipo. Pida al administrador que "
                    "restablezca su contraseña.", icon=":material/mail:")
        else:
            with st.form("recuperar_pedir"):
                identificador = st.text_input("Usuario o correo registrado", autocomplete="username")
                pedir = st.form_submit_button("Enviar el código", type="primary", width="stretch")
            if pedir and identificador.strip():
                with st.spinner("Enviando el código…"):
                    enviado = recuperacion.solicitar(identificador, usuarios, config)
                if enviado:
                    st.session_state["recuperar_id"] = identificador.strip()
                    st.session_state["recuperar"] = "codigo"
                    st.rerun()
                st.error("No se pudo enviar el correo en este momento. Intente más tarde o avise al administrador.")
            elif pedir:
                st.error("Escriba su usuario o su correo.")
    else:
        st.info(recuperacion.AVISO_ENVIO, icon=":material/mark_email_read:")
        with st.form("recuperar_codigo"):
            codigo = st.text_input(f"Código de {recuperacion.DIGITOS} dígitos", max_chars=recuperacion.DIGITOS,
                                   autocomplete="one-time-code")
            nueva = st.text_input("Contraseña nueva", type="password", autocomplete="new-password",
                                  help=f"Al menos {LONGITUD_MINIMA} caracteres.")
            repetida = st.text_input("Repita la contraseña nueva", type="password", autocomplete="new-password")
            cambiar = st.form_submit_button("Cambiar la contraseña", type="primary", width="stretch")
        if cambiar:
            ok, mensaje = recuperacion.restablecer(st.session_state.get("recuperar_id", ""), codigo, nueva, repetida,
                                                   usuarios, config)
            if ok:
                ir_a_recuperar(None)
                st.session_state["login_aviso"] = mensaje
                st.rerun()
            st.error(mensaje)
    # los enlaces van en una fila para que el paso del código quepa en una pantalla de portátil (1366 × 768)
    volver, otro = st.columns(2, gap="small")
    volver.button("Volver al inicio de sesión", key="mt-recuperar-volver", type="tertiary", icon=":material/arrow_back:",
                  on_click=ir_a_recuperar, args=(None,))
    if st.session_state.get("recuperar") == "codigo":
        otro.button("Pedir otro código", key="mt-recuperar-otra-vez", type="tertiary", on_click=ir_a_recuperar, args=("pedir",))


def formulario_login():
    """Dibuja el login. Devuelve los datos del usuario si acaba de iniciar sesión; si no, None."""
    usuarios = cargar_usuarios(st.secrets)
    recuperando = st.session_state.get("recuperar") is not None
    # Pantalla completa: a la izquierda la marca, a la derecha el acceso (estilos .st-key-mt-login* en ui_theme)
    with st.container(key="mt-login"):
        marca, acceso = st.columns(2, gap="small")
        with marca:
            html(ui.login_marca())
        with acceso, st.container(key="mt-login-acceso"):
            html(ui.login_encabezado(recuperando))
            if not usuarios:
                st.warning("No hay usuarios configurados. Cree uno desde la terminal y reinicie la consola:\n\n"
                           "`python -m src.autenticacion crear-usuario admin --rol administrador --nombre \"Administrador\"`")
                return None
            if recuperando:
                formulario_recuperacion(usuarios)
                return None
            if aviso := st.session_state.pop("login_aviso", None):
                st.success(aviso, icon=":material/check_circle:")
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
            st.button("¿Olvidó su contraseña?", key="mt-olvido", type="tertiary", on_click=ir_a_recuperar, args=("pedir",))
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

if "sesion_anotada" not in st.session_state:
    st.session_state["sesion_anotada"] = True
    lab.anotar(f"Sesión iniciada · {ROLES[usuario['rol']]}")

# El menú nativo de Streamlit va oculto: lo reemplaza el menú de fases de la barra lateral (src/ui_laboratorio.py).
# El laboratorio es una sola página que muestra una fase a la vez; las demás páginas se abren con enlaces.
laboratorio = st.Page("paginas/laboratorio.py", title="Laboratorio ML", icon=":material/science:", default=True)
OTRAS = [
    ("variables_3280", st.Page("paginas/variables_3280.py", title="Variables 3280", icon=":material/fact_check:")),
    # Provisional: demo del triaje de la Fase 2; la app de usuario final es el Módulo 2 (Flutter, web y móvil)
    ("triaje", st.Page("paginas/triaje.py", title="Triaje (Módulo 2)", icon=":material/stethoscope:")),
]
otras = [p for permiso, p in OTRAS if puede(usuario, permiso)]
pagina = st.navigation([laboratorio, *otras], position="hidden")
en_laboratorio = pagina.title == laboratorio.title
if st.session_state.pop("abrir_laboratorio", False) and not en_laboratorio:
    st.switch_page(laboratorio)  # se eligió una fase desde otra página
with st.sidebar:
    lab.menu(en_laboratorio, otras)
pagina.run()
lugar_login.empty()

# Después de la página, para no cambiar el orden de los botones propios de cada página en la barra lateral
with st.sidebar:
    html(ui.tarjeta_usuario(usuario["nombre"], ROLES[usuario["rol"]]))
    if st.button("Cerrar sesión", icon=":material/logout:", width="stretch"):
        for clave in ("usuario", "entrenamiento", "experimento_hp", "curvas_exp", "archivo_ips", "ingesta_ips", "crudo",
                      "depurado", "lote_eval", "patron_evento", "reentrenamiento", "publicacion", "paridad_dart",
                      "vista", "vistas_recorridas", "particion", "registro_ejecucion", "sesion_anotada"):
            st.session_state.pop(clave, None)
        st.rerun()
