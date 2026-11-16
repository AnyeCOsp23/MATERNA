"""Fase 3, bloque 3: Módulo 1 (Laboratorio de ML). Inicio de sesión, permisos, ingesta auditable y pestañas."""
import json
import shutil
import sqlite3

import pytest
from streamlit.testing.v1 import AppTest

from conftest import RAIZ
from src.autenticacion import (
    INTENTOS_MAXIMOS, PERMISOS, ROLES, autenticar, bloque_toml, generar_hash, puede, verificar_hash,
)
from src.consolidado_ips import datos_consolidados, guardar_carga, resumen_consolidado
from src import conjunto_trabajo, patrones, publicacion
from src.exportar_a_dart import DIR_ASSETS
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
    # publicar desde una prueba nunca toca los JSON de la app ni los modelos del repositorio
    shutil.copytree(DIR_ASSETS, tmp_path / "assets", ignore=shutil.ignore_patterns("fonts", "*.webp"))
    monkeypatch.setenv("MATERNA_ASSETS", str(tmp_path / "assets"))
    monkeypatch.setenv("MATERNA_PUBLICACION", str(tmp_path / "publicados"))
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
    comparacion = next(d.value for d in at.dataframe if "Registros" in d.value and "¿Lo usó el modelo?" not in d.value)
    assert list(comparacion["Registros"]) == [fila["n_prueba"], 200]
    # y la interpretación de esa versión incluye el lote como patrones no usados
    next(s for s in at.selectbox if s.key == "interp_sistema").set_value("exp-0001").run()
    usados = next(d.value for d in at.dataframe if "¿Lo usó el modelo?" in d.value)
    assert list(usados["Conjunto"]) == ["Entrenamiento", "Validación", "Prueba", "Lote de demostración"]
    assert usados["Registros"].iloc[-1] == 200
    # y se puede volver al dataset base
    boton(at, "Volver al dataset base").click().run()
    assert conjunto_trabajo.meta() is None


def llenar_patron(at, **valores):
    for nombre, valor in valores.items():
        campo = next(c for c in [*at.number_input, *at.selectbox] if c.key == f"patron_{nombre}")
        campo.set_value(valor)
    return at


PATRON = dict(edad=31, semanas_gestacion=30, n_controles_prenatales=2, pas_mmhg=150, pad_mmhg=96, glucosa_mgdl=130.5,
              proteinuria=1, convulsiones="No", area_residencia="Rural disperso", atendido_por="Partera tradicional")


def test_nuevo_patron_manual_contador_rechazos_y_reentrenamiento(entorno):
    at = pagina("laboratorio", "administrador")
    # fuera de rango y sin un dato obligatorio: se rechaza y se explica; no queda nada guardado
    llenar_patron(at, **{**PATRON, "edad": 99, "pad_mmhg": None})
    boton(at, "Agregar el patrón").click().run()
    rechazo = next(e.value for e in at.error if "Patrón rechazado" in e.value)
    assert "fuera del rango del catálogo 3280 (10 a 55)" in rechazo and "Presión arterial diastólica: es obligatoria" in rechazo
    assert patrones.vigentes().empty and not patrones.eventos()
    # válido: contador 1.200 -> 1.201 y bitácora con usuario y valores
    llenar_patron(at, **PATRON)
    next(r for r in at.radio if r.key == "patron_clase").set_value("Alto Riesgo")
    boton(at, "Agregar el patrón").click().run()
    assert not at.exception
    assert any("NP0001" in s.value and "1.200 → 1.201" in s.value for s in at.success)
    (evento,) = patrones.eventos()
    assert evento["usuario"] == "administrador" and evento["valores"]["pas_mmhg"] == 150 and evento["valores"]["fcf_bpm"] is None
    assert (evento["contador_antes"], evento["contador_despues"], evento["clase"]) == (1200, 1201, "Alto Riesgo")
    # el mismo otra vez: duplicado
    boton(at, "Agregar el patrón").click().run()
    assert any("Duplicado" in e.value and "NP0001" in e.value for e in at.error) and len(patrones.vigentes()) == 1
    # el modelo en uso no lo usó: aparece como «Registros nuevos» en la interpretación
    usados = next(d.value for d in at.dataframe if "¿Lo usó el modelo?" in d.value)
    assert list(usados["Conjunto"])[-1] == "Registros nuevos" and usados["Registros"].iloc[-1] == 1
    # reentrenar: primero el «antes», luego la versión con el patrón sumado solo al entrenamiento
    assert any("Entrene primero una versión" in c.value for c in at.caption)
    next(s for s in at.selectbox if s.key == "entrenar_algoritmo").set_value("Regresión Logística").run()
    boton(at, "Entrenar en vivo").click().run()
    boton(at, "Reentrenar con el nuevo patrón").click().run()
    assert not at.exception
    antes, despues = leer_registro()
    assert (antes["patrones"], despues["patrones"]) == ([], ["NP0001"])
    assert (antes["n_entrenamiento"], despues["n_entrenamiento"]) == (840, 841)
    assert (despues["n_validacion"], despues["n_prueba"], despues["hiperparametros"]) == (180, 180, antes["hiperparametros"])
    comparacion = next(d.value for d in at.dataframe if "Patrones nuevos" in d.value and "Costo prueba" in d.value)
    assert list(comparacion["Versión"]) == ["exp-0001", "exp-0002"] and list(comparacion["Patrones nuevos"]) == [0, 1]


def test_medico_auditor_agrega_patrones_pero_no_los_retira_ni_reentrena(entorno):
    at = pagina("laboratorio", "medico_auditor")
    llenar_patron(at, **PATRON)
    next(r for r in at.radio if r.key == "patron_clase").set_value("Que la calcule el sistema (proxy por reglas)")
    boton(at, "Agregar el patrón").click().run()
    assert not at.exception
    (evento,) = patrones.eventos()
    assert evento["etiqueta_origen"] == "proxy_reglas" and evento["usuario"] == "medico_auditor"
    assert boton(at, "Retirar").disabled


def test_publicar_al_modulo_2_solo_el_administrador_y_solo_random_forest(entorno):
    oficial = (entorno / "assets" / "modelo_rf.json").read_bytes()
    at = pagina("laboratorio", "administrador")
    assert any("La app usa hoy el modelo **v1**" in i.value for i in at.info)
    assert any("No hay versiones de Random Forest para publicar" in c.value for c in at.caption)
    assert any("al recompilar la app" in w.value for w in at.warning)
    # una Regresión Logística no aparece como publicable
    next(s for s in at.selectbox if s.key == "entrenar_algoritmo").set_value("Regresión Logística").run()
    boton(at, "Entrenar en vivo").click().run()
    assert any("No hay versiones de Random Forest para publicar" in c.value for c in at.caption)
    # un Random Forest sí; hay que confirmar antes de publicar
    next(s for s in at.selectbox if s.key == "hp_algoritmo").set_value("Random Forest").run()
    next(n for n in at.number_input if n.key == "hp_rf_arboles").set_value(20).run()
    boton(at, "Entrenar esta configuración").click().run()
    assert not at.exception
    assert boton(at, "Publicar al Módulo 2").disabled
    next(c for c in at.checkbox if c.key == "publicar_confirmar").check().run()
    boton(at, "Publicar al Módulo 2").click().run()
    assert not at.exception
    assert any("Publicado como **v2** (sale de exp-0002)" in s.value and "200 casos" in s.value for s in at.success)
    assert any("La app usa hoy el modelo **v2**" in i.value for i in at.info)
    modelo_json = json.loads((entorno / "assets" / "modelo_rf.json").read_text(encoding="utf-8"))
    assert modelo_json["version"] == "v2" and modelo_json["n_arboles"] == 20 and publicacion.assets_vigentes()
    assert publicacion.manifiesto()["actual"]["usuario"] == "administrador"
    # y se puede volver al oficial: los JSON quedan como estaban
    boton(at, "Volver al modelo oficial v1").click().run()
    assert not at.exception and publicacion.publicado()["oficial"]
    assert (entorno / "assets" / "modelo_rf.json").read_bytes() == oficial


def test_medico_auditor_no_publica(entorno):
    at = pagina("laboratorio", "medico_auditor")
    assert any("Solo el administrador publica" in c.value for c in at.caption)
    assert not any(b.label.startswith("Publicar al Módulo 2") for b in at.button)  # sin versiones no hay botón


def test_interpretacion_de_metricas_y_avisos_fijos(entorno):
    at = pagina("laboratorio", "medico_auditor")
    assert not at.exception
    # el aviso fijo acompaña las tablas de métricas oficiales (pestañas 07, 10, 11 y la interpretación)
    assert sum("reproduce el sistema el etiquetado sintético" in w.value for w in at.warning) >= 4
    etiquetas = [e.label for e in at.expander]
    for metrica in ("Accuracy", "Precisión", "Recall de Alto Riesgo", "F1-macro", "ROC-AUC", "Matriz de confusión", "Costo clínico"):
        assert any(e.startswith(metrica) for e in etiquetas), metrica
    assert any(e.startswith("Explicación para la sustentación") for e in etiquetas)
    textos = " ".join(m.value for m in at.markdown)
    assert "No es 100 %" in textos and "22 de 23" in textos and "¿Qué es?" in textos and "¿Cómo se lee?" in textos
    assert any("En prueba:" in i.value and "Acertó 175 de 180" in i.value for i in at.info)
    # al cambiar de conjunto, las frases cambian con los números
    next(r for r in at.radio if r.key == "interp_conjunto").set_value("Entrenamiento").run()
    assert any("En entrenamiento:" in i.value and "Acertó 840 de 840" in i.value for i in at.info)


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
