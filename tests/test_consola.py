"""Fase 3, bloque 3: Módulo 1 (Laboratorio de ML). Inicio de sesión, permisos, ingesta auditable y pestañas."""
import sqlite3

import pytest
from streamlit.testing.v1 import AppTest

from conftest import RAIZ
from src.autenticacion import (
    INTENTOS_MAXIMOS, PERMISOS, ROLES, autenticar, bloque_toml, generar_hash, puede, verificar_hash,
)
from src.consolidado_ips import datos_consolidados, guardar_carga, resumen_consolidado
from src.generar_ejemplo_ips import DIR_EJEMPLOS
from src.inspeccionar_ips import inspeccionar

APP = str(RAIZ / "app_demo.py")
PAGINA = lambda nombre: str(RAIZ / "paginas" / f"{nombre}.py")
SAL = "sal-solo-para-pruebas-0123456789"
CLAVES = {"admin": "clave-admin-123", "medico": "clave-medico-123", "profe": "clave-profe-123"}
ROL_DE = {"admin": "administrador", "medico": "medico_auditor", "profe": "evaluador"}


def sesion(rol):
    return {"usuario": rol, "nombre": f"Usuario {rol}", "rol": rol}


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    archivo = tmp_path / "usuarios.toml"
    archivo.write_text("".join(bloque_toml(u, ROL_DE[u], f"Prueba {u}", c) for u, c in CLAVES.items()), encoding="utf-8")
    monkeypatch.setenv("MATERNA_USUARIOS", str(archivo))
    monkeypatch.setenv("MATERNA_SAL", SAL)
    monkeypatch.setenv("MATERNA_BD", str(tmp_path / "triaje.sqlite"))
    monkeypatch.setenv("MATERNA_BD_IPS", str(tmp_path / "laboratorio.sqlite"))
    return tmp_path


def pagina(nombre, rol):
    at = AppTest.from_file(PAGINA(nombre), default_timeout=180)
    at.session_state["usuario"] = sesion(rol)
    return at.run()


def iniciar_sesion(at, usuario, clave):
    at.text_input[0].input(usuario)
    at.text_input[1].input(clave)
    at.button[0].click().run()
    return at


def boton(at, inicio):
    return next(b for b in at.button if b.label.startswith(inicio))


# ------------------------------------------------------------------ contraseñas y permisos
def test_hash_de_contrasena():
    h = generar_hash("una-clave-larga")
    assert h.startswith("scrypt$") and "una-clave-larga" not in h
    assert verificar_hash("una-clave-larga", h) and not verificar_hash("otra-clave", h)
    assert generar_hash("una-clave-larga") != h  # sal aleatoria por usuario
    assert not verificar_hash("x", "basura")
    with pytest.raises(ValueError):
        generar_hash("corta")


def test_autenticar():
    usuarios = {"profe": {"nombre": "Profe", "rol": "evaluador", "hash": generar_hash("clave-profe-123")}}
    assert autenticar(" PROFE ", "clave-profe-123", usuarios) == {"usuario": "profe", "nombre": "Profe", "rol": "evaluador"}
    assert autenticar("profe", "mala-clave", usuarios) is None
    assert autenticar("nadie", "clave-profe-123", usuarios) is None
    # un rol que no existe no entra aunque la contraseña sea correcta
    raro = {"otro": {"nombre": "O", "rol": "superusuario", "hash": generar_hash("clave-otro-123")}}
    assert autenticar("otro", "clave-otro-123", raro) is None


def test_permisos_por_rol():
    assert set(ROLES) == set(PERMISOS) == {"administrador", "medico_auditor", "evaluador"}
    assert puede(sesion("administrador"), "entrenar") and puede(sesion("administrador"), "ingesta_archivos")
    assert puede(sesion("medico_auditor"), "ingesta_archivos") and not puede(sesion("medico_auditor"), "entrenar")
    assert not puede(sesion("evaluador"), "entrenar") and not puede(sesion("evaluador"), "ingesta_archivos")
    assert puede(sesion("evaluador"), "laboratorio")
    assert not puede(None, "laboratorio")


# ------------------------------------------------------------------ inicio de sesión
def test_sin_sesion_muestra_el_login(entorno):
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert [t.label for t in at.text_input] == ["Usuario", "Contraseña"]
    assert not at.tabs


def test_login_abre_el_laboratorio(entorno):
    at = iniciar_sesion(AppTest.from_file(APP, default_timeout=180).run(), "profe", CLAVES["profe"])
    assert not at.exception
    assert at.session_state["usuario"]["rol"] == "evaluador"
    assert len(at.tabs) == 13  # la página de inicio es el laboratorio (Módulo 1)


def test_login_incorrecto_y_bloqueo(entorno):
    at = AppTest.from_file(APP, default_timeout=120).run()
    for _ in range(INTENTOS_MAXIMOS):
        iniciar_sesion(at, "admin", "clave-equivocada")
        assert "usuario" not in at.session_state
    iniciar_sesion(at, "admin", CLAVES["admin"])  # clave correcta, pero bloqueado
    assert "usuario" not in at.session_state and "Demasiados intentos" in at.error[0].value


def test_sin_usuarios_configurados(tmp_path, monkeypatch):
    vacio = tmp_path / "vacio.toml"
    vacio.write_text("", encoding="utf-8")
    monkeypatch.setenv("MATERNA_USUARIOS", str(vacio))
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert "No hay usuarios configurados" in at.warning[0].value and not at.text_input


def test_cerrar_sesion(entorno):
    at = iniciar_sesion(AppTest.from_file(APP, default_timeout=180).run(), "admin", CLAVES["admin"])
    next(b for b in at.sidebar.button if b.label == "Cerrar sesión").click().run()
    assert "usuario" not in at.session_state and at.text_input[0].label == "Usuario"


# ------------------------------------------------------------------ ingesta auditable (fase 02)
def test_evaluador_audita_la_ingesta_con_el_ejemplo(entorno):
    at = pagina("laboratorio", "evaluador")
    assert not any(u for u in at.get("file_uploader"))  # no puede subir archivos propios
    boton(at, "Ingerir el ejemplo").click().run()
    assert not at.exception
    metricas = {m.label: m.value for m in at.metric}
    assert metricas["Filas leídas"] == "307" and metricas["Aptas para el modelo"] == "300"
    assert not any(b.label.startswith("Guardar en la base") for b in at.button)  # tampoco guarda


@pytest.mark.parametrize("rol", ["administrador", "medico_auditor"])
def test_ingiere_y_guarda_archivos_reales(entorno, rol):
    at = pagina("laboratorio", rol)
    boton(at, "Ingerir el ejemplo").click().run()
    assert not at.exception
    boton(at, "Guardar en la base").click().run()
    with sqlite3.connect(entorno / "laboratorio.sqlite") as con:
        assert con.execute("SELECT COUNT(*) FROM atenciones").fetchone()[0] == 303
        assert con.execute("SELECT usuario FROM cargas").fetchone()[0] == rol
        assert "FICTICIO" not in " ".join(d for (d,) in con.execute("SELECT datos FROM atenciones"))


def test_administrador_sin_sal(entorno, monkeypatch):
    # Una sal demasiado corta se rechaza igual que una ausente, y no depende del secrets.toml del equipo
    monkeypatch.setenv("MATERNA_SAL", "corta")
    at = pagina("laboratorio", "administrador")
    assert any("Falta la sal" in e.value for e in at.error)


def test_base_del_laboratorio(entorno):
    datos, reporte = inspeccionar(DIR_EJEMPLOS / "ips_ficticio_3280.csv", SAL)
    guardar_carga(datos, reporte, "prueba")
    cargas, gestantes = resumen_consolidado()
    assert len(cargas) == 1 and cargas["aptas"].iloc[0] == 300 and gestantes == 298
    guardado = datos_consolidados()
    assert len(guardado) == 303 and "primer_nombre" not in guardado and "numero_documento" not in guardado


# ------------------------------------------------------------------ resto del laboratorio y variables 3280
@pytest.mark.parametrize("rol", ["evaluador", "medico_auditor", "administrador"])
def test_laboratorio_tiene_las_13_pestanas(entorno, rol):
    at = pagina("laboratorio", rol)
    assert not at.exception
    etiquetas = [t.label for t in at.tabs]
    assert len(etiquetas) == 13 and etiquetas[1] == "02 Recolección e ingesta" and etiquetas[11] == "12 Entrega al Módulo 2"
    assert boton(at, "Entrenar en vivo").disabled == (rol != "administrador")


def test_entrenar_en_vivo_reproduce_el_modelo(entorno):
    at = pagina("laboratorio", "administrador")
    boton(at, "Entrenar en vivo").click().run()
    assert not at.exception
    assert any("Reproducible" in i.value for i in at.info)
    assert at.session_state["entrenamiento"]["identico_al_modelo_en_uso"]


def test_motor_de_reglas_interactivo(entorno):
    at = pagina("laboratorio", "evaluador")
    next(n for n in at.number_input if n.label == "PAS").set_value(165).run()
    assert any("Alto Riesgo por regla clínica" in e.value for e in at.error)


def test_pagina_variables_3280(entorno):
    at = pagina("variables_3280", "evaluador")
    assert not at.exception and len(at.dataframe[0].value) == 71
