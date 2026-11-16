"""Fase 3 — Armazón del laboratorio: fases del ciclo de vida, menú lateral, encabezado, tarjetas y registro de ejecución.

El laboratorio muestra UNA fase a la vez. La fase visible vive en st.session_state["vista"]: el menú lateral
(que dibuja app_demo.py) la cambia y paginas/laboratorio.py dibuja solo esa fase. Así cada fase de la lista de
chequeo tiene su propia pantalla y no se recalculan las demás en cada interacción.

El registro de ejecución es la barra inferior: lo último que se ejecutó en esta sesión, con su hora real.
"""
from datetime import datetime

import streamlit as st

from src import ui_theme as ui
from src.autenticacion import ROLES
from src.lista_chequeo import ACTIVIDADES

INICIO = "01"
# (clave, nombre en el menú, título de la pantalla, subtítulo)
GRUPOS = [
    ("Preparación", [
        ("01", "Problema", "Definir el problema", "Qué se predice, para quién y cómo se mide el éxito"),
        ("02", "Datos", "Recolección e ingesta de datos", "Dataset base, archivos de la IPS, datos de trabajo y patrones nuevos"),
        ("03", "EDA", "Análisis exploratorio (EDA)", "Cómo son los datos antes de modelar"),
        ("04", "Limpieza", "Limpieza y depuración", "Se suben datos crudos y el sistema los limpia paso a paso"),
        ("05", "Variables", "Ingeniería de variables", "Qué entra al modelo y cómo se transforma"),
    ]),
    ("Modelado", [
        ("06", "División", "División de los datos", "Cómo se parten los datos en entrenamiento, validación y prueba"),
        ("07", "Algoritmo", "Selección del algoritmo", "Tres modelos comparados y el criterio para elegir"),
        ("08", "Entrenamiento", "Entrenamiento en vivo", "Cada entrenamiento crea una versión nueva; el modelo en uso no cambia"),
        ("09", "Parámetros", "Ajuste de hiperparámetros", "La búsqueda en grilla de la Fase 2 y sus propias configuraciones"),
    ]),
    ("Validación y entrega", [
        ("10", "Evaluación", "Evaluación", "¿Qué tan bien funciona y cómo se lee?"),
        ("11", "Generalización", "Generalización", "Sobreajuste y subajuste: curvas de aprendizaje"),
        ("12", "Entrega", "Entrega al Módulo 2", "Lo que el laboratorio le entrega a la app y cómo se publica"),
    ]),
]
TRANSVERSAL = "Transversal"
EXTRAS = [
    ("etica", "Ética y limitaciones", "Ética y limitaciones", "Sesgos, datos sintéticos y lo que falta validar"),
    ("chequeo", "Lista de chequeo", "Lista de chequeo del ciclo de vida", "Auditoría del repositorio contra las 12 fases"),
]
VISTAS = {clave: {"menu": menu, "titulo": titulo, "sub": sub, "grupo": grupo}
          for grupo, fases in [*GRUPOS, (TRANSVERSAL, EXTRAS)] for clave, menu, titulo, sub in fases}
N_FASES = sum(len(fases) for _, fases in GRUPOS)


# ------------------------------------------------------------------ fase visible
def vista():
    """La fase que se está viendo (por defecto, la 01)."""
    actual = st.session_state.get("vista", INICIO)
    return actual if actual in VISTAS else INICIO


def ir_a(clave):
    """Cambia de fase. Sirve de `on_click` de los botones: corre antes de que se vuelva a dibujar la página."""
    st.session_state["vista"] = clave
    st.session_state["abrir_laboratorio"] = True  # si se estaba en otra página, app_demo.py vuelve al laboratorio


def marcar_recorrida(clave):
    recorridas = st.session_state.setdefault("vistas_recorridas", [])
    if clave not in recorridas:
        recorridas.append(clave)


def nombre_fase(clave):
    """«la fase 04 (Limpieza)», para remitir de una pantalla a otra."""
    return f"la fase {clave} ({VISTAS[clave]['menu']})"


def boton_ir(clave, texto=None, **opciones):
    """Botón que lleva a otra fase."""
    st.button(texto or f"Ir a {nombre_fase(clave)}", key=f"mt-ir-{clave}-{vista()}", icon=":material/arrow_forward:",
              on_click=ir_a, args=(clave,), **opciones)


# ------------------------------------------------------------------ menú lateral
def _item(clave, actual, recorridas, insignia=None):
    estado = "activa" if clave == actual else "vista" if clave in recorridas else "pend"
    if insignia is None:  # fases numeradas: la que ya se recorrió en esta sesión muestra un visto
        insignia = "✓" if estado == "vista" else clave
    etiqueta = f"`{insignia}` {VISTAS[clave]['menu']}" if insignia else VISTAS[clave]["menu"]
    st.button(etiqueta, key=f"mt-nav-{estado}-{clave}", type="tertiary", width="stretch", on_click=ir_a, args=(clave,))


def menu(en_laboratorio, otras_paginas=()):
    """Menú de la barra lateral: las 12 fases agrupadas, las vistas transversales y las demás páginas."""
    actual = vista() if en_laboratorio else None
    recorridas = st.session_state.get("vistas_recorridas", [])
    hechas = sum(1 for a in ACTIVIDADES if a[2] == "Hecho")
    with st.container(key="mt-menu"):
        st.markdown(ui.menu_marca(), unsafe_allow_html=True)
        for grupo, fases in GRUPOS:
            st.markdown(ui.menu_grupo(grupo), unsafe_allow_html=True)
            for clave, *_ in fases:
                _item(clave, actual, recorridas)
        st.markdown(ui.menu_grupo(TRANSVERSAL), unsafe_allow_html=True)
        _item("etica", actual, recorridas, insignia="")
        _item("chequeo", actual, recorridas, insignia=f"{hechas}/{len(ACTIVIDADES)}")
        if otras_paginas:
            st.markdown(ui.menu_grupo("Otras vistas"), unsafe_allow_html=True)
            for pagina in otras_paginas:
                st.page_link(pagina)


# ------------------------------------------------------------------ encabezado y tarjetas
def encabezado(clave, usuario, chips=()):
    """Ruta de navegación, sesión activa, número de fase, título y etiquetas de la pantalla."""
    v = VISTAS[clave]
    eyebrow = f"Fase {int(clave)} · de {N_FASES}" if clave.isdigit() else ("Auditoría" if clave == "chequeo" else TRANSVERSAL)
    rol = ROLES.get(usuario["rol"], "Sin rol") if usuario else "Sin sesión"
    st.markdown(ui.encabezado_pagina(["Laboratorio ML", v["grupo"], v["menu"]], f"Sesión activa · {rol}", eyebrow,
                                     v["titulo"], v["sub"], chips), unsafe_allow_html=True)


def tarjeta(clave, titulo=None, nota=None, alto="content"):
    """Tarjeta blanca redondeada. `alto="stretch"` iguala la altura de las tarjetas de una misma fila."""
    contenedor = st.container(border=True, key=f"mt-card-{clave}", height=alto)
    if titulo:
        contenedor.markdown(ui.titulo_tarjeta(titulo, nota), unsafe_allow_html=True)
    return contenedor


# ------------------------------------------------------------------ registro de ejecución
def anotar(texto):
    """Agrega un evento, con la hora real, al registro de ejecución de la sesión."""
    registro = st.session_state.setdefault("registro_ejecucion", [])
    registro.append((datetime.now().strftime("%H:%M:%S"), texto))
    del registro[:-40]


def registro(n=3):
    """Barra inferior con los últimos eventos de la sesión."""
    with st.container(key="mt-registro"):
        st.markdown(ui.registro_ejecucion(st.session_state.get("registro_ejecucion", [])[-n:]), unsafe_allow_html=True)
