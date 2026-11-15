"""Fase 3, bloque 3: Módulo 1 (Laboratorio de ML). Inicio de sesión, permisos, ingesta auditable y pestañas."""
import sqlite3

import pytest
from streamlit.testing.v1 import AppTest

from conftest import RAIZ
from src.autenticacion import (
    INTENTOS_MAXIMOS, PERMISOS, ROLES, autenticar, bloque_toml, generar_hash, puede, verificar_hash,
)
from src.consolidado_ips import datos_consolidados, guardar_carga, resumen_consolidado
from src import conjunto_trabajo
from src.experimentos import leer_registro
from src.generar_ejemplo_ips import DIR_EJEMPLOS
from src.inspeccionar_ips import inspeccionar
from src.lista_chequeo import ACTIVIDADES, ESTADOS

APP = str(RAIZ / "app_demo.py")
PAGINA = lambda nombre: str(RAIZ / "paginas" / f"{nombre}.py")
SAL = "sal-solo-para-pruebas-0123456789"
CLAVES = {"admin": "clave-admin-123", "medico": "clave-medico-123"}
ROL_DE = {"admin": "administrador", "medico": "medico_auditor"}


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
    monkeypatch.setenv("MATERNA_EXPERIMENTOS", str(tmp_path / "experimentos"))
    return tmp_path


def pagina(nombre, rol):
    at = AppTest.from_file(PAGINA(nombre), default_timeout=180)
    at.session_state["usuario"] = sesion(rol)
    return at.run()


def app_abierta():
    """La app tras la bienvenida (el simulador no ejecuta el JavaScript que avisa que la capa ya cubre la pantalla)."""
    at = AppTest.from_file(APP, default_timeout=180)
    at.session_state["bienvenida_mostrada"] = True
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
    usuarios = {"medico": {"nombre": "Médico", "rol": "medico_auditor", "hash": generar_hash("clave-medico-123")}}
    assert autenticar(" MEDICO ", "clave-medico-123", usuarios) == {"usuario": "medico", "nombre": "Médico", "rol": "medico_auditor"}
    assert autenticar("medico", "mala-clave", usuarios) is None
    assert autenticar("nadie", "clave-medico-123", usuarios) is None
    # un rol que no existe (como el antiguo "evaluador") no entra aunque la contraseña sea correcta
    for rol in ("evaluador", "superusuario"):
        raro = {"otro": {"nombre": "O", "rol": rol, "hash": generar_hash("clave-otro-123")}}
        assert autenticar("otro", "clave-otro-123", raro) is None


def test_permisos_por_rol():
    assert set(ROLES) == set(PERMISOS) == {"administrador", "medico_auditor"}
    assert puede(sesion("administrador"), "entrenar") and puede(sesion("administrador"), "ingesta_archivos")
    assert puede(sesion("medico_auditor"), "ingesta_archivos") and not puede(sesion("medico_auditor"), "entrenar")
    assert puede(sesion("medico_auditor"), "laboratorio")
    assert not puede(sesion("evaluador"), "laboratorio")  # el rol se eliminó
    assert not puede(None, "laboratorio")


# ------------------------------------------------------------------ inicio de sesión
def test_sin_sesion_muestra_el_login(entorno):
    at = app_abierta()
    assert [t.label for t in at.text_input] == ["Usuario", "Contraseña"]
    assert not at.tabs


def test_login_abre_el_laboratorio(entorno):
    at = iniciar_sesion(app_abierta(), "medico", CLAVES["medico"])
    assert not at.exception
    assert at.session_state["usuario"]["rol"] == "medico_auditor"
    assert len(at.tabs) == 14  # la página de inicio es el laboratorio (Módulo 1)
    # el login se borra en la misma ejecución: no queda ningún campo ni texto suyo debajo del laboratorio
    assert not at.text_input and not any("Inicie sesión" in m.value for m in at.markdown)


def test_login_incorrecto_y_bloqueo(entorno):
    at = app_abierta()
    for _ in range(INTENTOS_MAXIMOS):
        iniciar_sesion(at, "admin", "clave-equivocada")
        assert "usuario" not in at.session_state
    iniciar_sesion(at, "admin", CLAVES["admin"])  # clave correcta, pero bloqueado
    assert "usuario" not in at.session_state and "Demasiados intentos" in at.error[0].value


def test_sin_usuarios_configurados(tmp_path, monkeypatch):
    vacio = tmp_path / "vacio.toml"
    vacio.write_text("", encoding="utf-8")
    monkeypatch.setenv("MATERNA_USUARIOS", str(vacio))
    at = app_abierta()
    assert "No hay usuarios configurados" in at.warning[0].value and not at.text_input


def test_cerrar_sesion(entorno):
    at = iniciar_sesion(app_abierta(), "admin", CLAVES["admin"])
    next(b for b in at.sidebar.button if b.label == "Cerrar sesión").click().run()
    assert "usuario" not in at.session_state and at.text_input[0].label == "Usuario"


# ------------------------------------------------------------------ ingesta auditable (fase 02)
def test_reporte_de_la_ingesta_del_ejemplo(entorno):
    at = pagina("laboratorio", "medico_auditor")
    boton(at, "Ingerir el ejemplo").click().run()
    assert not at.exception
    metricas = {m.label: m.value for m in at.metric}
    assert metricas["Filas leídas"] == "307" and metricas["Aptas para el modelo"] == "300"


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
@pytest.mark.parametrize("rol", ["medico_auditor", "administrador"])
def test_laboratorio_tiene_las_14_pestanas(entorno, rol):
    at = pagina("laboratorio", rol)
    assert not at.exception
    etiquetas = [t.label for t in at.tabs]
    assert len(etiquetas) == 14 and etiquetas[1] == "02 Recolección e ingesta" and etiquetas[11] == "12 Entrega al Módulo 2"
    assert etiquetas[12] == "13 Ética y limitaciones" and etiquetas[13] == "Lista de chequeo"
    assert boton(at, "Entrenar en vivo").disabled == (rol != "administrador")


def test_entrenar_en_vivo_reproduce_el_modelo_y_crea_una_version(entorno):
    at = pagina("laboratorio", "administrador")
    assert any("Aún no hay experimentos" in c.value for c in at.caption)
    boton(at, "Entrenar en vivo").click().run()
    assert not at.exception
    assert any("Reproducible" in i.value for i in at.info)
    assert at.session_state["entrenamiento"]["identico_al_modelo_en_uso"]
    assert (entorno / "experimentos" / "modelos" / "exp-0001.joblib").exists()
    # la versión aparece en la misma ejecución en el registro de la pestaña 07, con el criterio de selección
    assert any("Criterio de selección" in s.value and "exp-0001" in s.value for s in at.success)


def numero(at, etiqueta):
    return next(n for n in at.number_input if n.label == etiqueta)


def test_particion_parametrizable(entorno):
    at = pagina("laboratorio", "administrador")
    numero(at, "Entrenamiento (%)").set_value(80)
    numero(at, "Validación (%)").set_value(10)
    numero(at, "Prueba (%)").set_value(10).run()
    assert not at.exception and not at.error
    conteos = next(d.value for d in at.dataframe if "Conjunto" in d.value)
    assert list(conteos["Gestantes"]) == [960, 120, 120]
    assert not boton(at, "Entrenar en vivo").disabled
    # si no suman 100 se explica y no se puede entrenar
    numero(at, "Prueba (%)").set_value(15).run()
    assert any("suman 105" in e.value for e in at.error)
    assert boton(at, "Entrenar en vivo").disabled and boton(at, "Entrenar esta configuración").disabled
    # con muy pocos casos de Alto en un conjunto, avisa
    numero(at, "Entrenamiento (%)").set_value(94)
    numero(at, "Validación (%)").set_value(3)
    numero(at, "Prueba (%)").set_value(3).run()
    assert any("Muy pocos casos de Alto Riesgo" in w.value for w in at.warning)


def test_probar_otra_configuracion_guarda_particion_semilla_y_usuario(entorno):
    at = pagina("laboratorio", "administrador")
    numero(at, "Entrenamiento (%)").set_value(60)
    numero(at, "Validación (%)").set_value(20)
    numero(at, "Prueba (%)").set_value(20)
    next(n for n in at.number_input if n.key == "part_semilla").set_value(7)
    next(s for s in at.selectbox if s.key == "hp_algoritmo").set_value("Regresión Logística").run()
    next(s for s in at.select_slider if s.key == "hp_lr_c").set_value(1.0).run()
    boton(at, "Entrenar esta configuración").click().run()
    assert not at.exception
    (fila,) = leer_registro()
    assert fila["version"] == "exp-0001" and fila["algoritmo"] == "Regresión Logística" and fila["usuario"] == "administrador"
    assert fila["particion"] == "60/20/20" and fila["semilla"] == 7 and fila["n_entrenamiento"] == 720
    assert fila["hiperparametros"]["C"] == 1.0 and not fila["identico_al_modelo_en_uso"]
    # la curva de esa versión se calcula desde la pestaña 11
    boton(at, "Calcular la curva").click().run()
    assert not at.exception and len(at.session_state["curvas_exp"]["exp-0001"]) == 7


def test_medico_auditor_ve_el_registro_pero_no_entrena(entorno):
    at = pagina("laboratorio", "medico_auditor")
    assert boton(at, "Entrenar en vivo").disabled and boton(at, "Entrenar esta configuración").disabled
    assert boton(at, "Generar").disabled and boton(at, "Medir la escalabilidad").disabled


def test_generar_depurar_usar_como_conjunto_de_trabajo_y_medir_el_lote(entorno):
    at = pagina("laboratorio", "administrador")
    assert any("Aún no hay datos crudos" in c.value for c in at.caption)
    next(n for n in at.number_input if n.key == "gen_n").set_value(2000).run()
    boton(at, "Generar").click().run()
    assert not at.exception
    assert any("Datos crudos listos" in s.value and "2.020 filas" in s.value for s in at.success)
    # pestaña 04: los 7 pasos de la depuración, con el conteo antes y después
    pasos = next(d.value for d in at.dataframe if "Filas antes" in d.value)
    assert len(pasos) == 7 and pasos["Filas antes"].iloc[0] == 2020
    limpias = int(pasos["Filas después"].iloc[-1])
    next(n for n in at.number_input if n.key == "lote_n").set_value(200).run()
    boton(at, "Usar como conjunto de trabajo").click().run()
    assert not at.exception
    meta = conjunto_trabajo.meta()
    assert (meta["n_trabajo"], meta["n_lote"], meta["usuario"]) == (limpias - 200, 200, "administrador")
    assert any("Activo:" in i.value and "Sintético generado (N=2.000, semilla 42)" in i.value for i in at.info)
    # la partición y el entrenamiento usan ahora el conjunto de trabajo
    conteos = next(d.value for d in at.dataframe if "Conjunto" in d.value and "Gestantes" in d.value)
    assert conteos["Gestantes"].sum() == limpias - 200
    next(s for s in at.selectbox if s.key == "entrenar_algoritmo").set_value("Regresión Logística").run()
    boton(at, "Entrenar en vivo").click().run()
    assert not at.exception
    (fila,) = leer_registro()
    assert fila["datos_huella"] == meta["huella"] and fila["n_entrenamiento"] + fila["n_validacion"] + fila["n_prueba"] == limpias - 200
    # pestaña 10: se carga el lote de demostración y se mide la versión sobre él
    boton(at, "Cargar el lote de demostración").click().run()
    assert not at.exception
    comparacion = next(d.value for d in at.dataframe if "Registros" in d.value and "Conjunto" in d.value)
    assert list(comparacion["Registros"]) == [fila["n_prueba"], 200]
    # y se puede volver al dataset base
    boton(at, "Volver al dataset base").click().run()
    assert conjunto_trabajo.meta() is None


def test_motor_de_reglas_interactivo(entorno):
    at = pagina("laboratorio", "medico_auditor")
    next(n for n in at.number_input if n.label == "PAS").set_value(165).run()
    assert any("Alto Riesgo por regla clínica" in e.value for e in at.error)


def test_pagina_variables_3280(entorno):
    at = pagina("variables_3280", "medico_auditor")
    assert not at.exception and len(at.dataframe[0].value) == 71


def test_lista_de_chequeo_en_el_laboratorio(entorno):
    at = pagina("laboratorio", "administrador")
    assert not at.exception
    por_estado = {m.label: int(m.value) for m in at.metric if m.label in ESTADOS}
    assert set(por_estado) == set(ESTADOS) and sum(por_estado.values()) == len(ACTIVIDADES)
    assert any(len(d.value) == len(ACTIVIDADES) and "Evidencia en el aplicativo" in d.value for d in at.dataframe)
