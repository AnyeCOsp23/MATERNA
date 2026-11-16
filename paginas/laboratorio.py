"""MATERNA — Módulo 1: Laboratorio de ML auditable (fases 01 a 12, ética y lista de chequeo).

Audiencia: docente y equipo. La página muestra UNA fase a la vez, la que se elige en el menú lateral
(src/ui_laboratorio.py): cada fase tiene su encabezado y sus tarjetas, con los datos y resultados reales del
repositorio (reports/, models/) y, en «Código que se ejecuta», la función exacta de src/ que los produce.
La fase 02 incluye la ingesta auditable de archivos de la IPS. La fase 12 documenta lo que el Módulo 1 entrega
al Módulo 2 (app Flutter, web y móvil): modelo, preprocesamiento y reglas en JSON.
El administrador hace todo, incluido reentrenar; el médico auditor audita e ingiere archivos, pero no reentrena.
Lo que se entrena aquí va al conjunto de trabajo (src/experimentos.py): cada entrenamiento es una versión nueva
y el modelo en uso y las cifras oficiales de la Fase 2 no cambian.
La barra inferior es el registro de ejecución: lo último que se hizo en la sesión, con su hora.
"""
import hashlib
import inspect
import json
import os
import secrets
import tempfile
from pathlib import Path

import joblib
import pandas as pd
import streamlit as st

from src import (
    conjunto_trabajo, experimentos, graficos, interpretacion, publicacion, recorrido, ui_datos, ui_laboratorio as lab,
    ui_metricas, ui_patrones, ui_publicacion, ui_recorrido, ui_theme as ui,
)
from src.autenticacion import puede
from src.clinical_rules import evaluar_reglas, mascara_reglas
from src.config import CLASE_ALTO, DIR_METRICAS, DIR_MODELOS, NOMBRES_CLASES, SEMILLA
from src.consolidado_ips import datos_consolidados, guardar_carga, resumen_consolidado
from src.depuracion import contar_filas, depurar
from src.data_preprocessing import (
    PARTICION_OFICIAL, RANGOS_PLAUSIBLES, MedianaEstratificadaImputer, cargar_dataset, marcar_fuera_de_rango,
    particionar, pasos_preprocesamiento, separar_xy,
)
from src.evaluate import MATRIZ_COSTO, calcular_metricas, intervalo_bootstrap
from src.exportar_a_dart import RUTA_MODELO, dir_assets
from src.filtro_3280 import tabla_decisiones, variables_modelo
from src.generar_ejemplo_ips import DIR_EJEMPLOS, DIR_PLANTILLAS
from src.inspeccionar_ips import CENTINELAS, inspeccionar, reemplazar_centinelas
from src.lista_chequeo import ACTIVIDADES, ESTADOS, resumen as resumen_chequeo, tabla as tabla_chequeo
from src.seudonimizacion import LONGITUD_MINIMA_SAL, VARIABLE_SAL
from src.train_models import GRID_C_LR, con_estrategias_balanceo, grid_random_forest
from src.ui_theme import miles

usuario = st.session_state.get("usuario")
# Con menos casos de Alto Riesgo que estos en un conjunto, un solo error mueve su recall más de 10 puntos
MIN_ALTO = 10
AVISO_SVM = (f"El costo de la SVM crece aproximadamente con el cuadrado del número de registros: con más de "
             f"{miles(experimentos.MAX_SVM)} de entrenamiento se ajusta con una muestra estratificada de ese tamaño.")
ETIQUETAS = {"edad": "Edad (años)", "semanas_gestacion": "Semanas de gestación", "n_controles_prenatales": "Controles prenatales",
             "pas_mmhg": "PAS (mmHg)", "pad_mmhg": "PAD (mmHg)", "fcf_bpm": "FCF (lpm)", "glucosa_mgdl": "Glucosa (mg/dL)"}
# Particiones de un clic (fase 06); cualquier otra combinación es «Personalizada»
PRESETS = {"70-15-15": (70, 15, 15), "80-10-10": (80, 10, 10), "60-20-20": (60, 20, 20)}
PERSONALIZADA = "Personalizada"
CLAVES_PARTICION = ("part_entrenamiento", "part_validacion", "part_prueba")


def html(bloque):
    st.markdown(bloque, unsafe_allow_html=True)


def codigo(*objetos):
    with st.expander("Código que se ejecuta"):
        for objeto in objetos:
            st.code(inspect.getsource(objeto), language="python")


def grafico(chart):
    st.altair_chart(chart, width="stretch")


def decimal(valor, decimales=3):
    """0.957 -> «0,957»."""
    return f"{valor:.{decimales}f}".replace(".", ",")


@st.cache_data
def dataset():
    return cargar_dataset()


@st.cache_data
def metricas(nombre):
    return pd.read_csv(DIR_METRICAS / nombre)


@st.cache_data
def cargar_trabajo(huella):
    """El conjunto de trabajo activo; la huella es la clave de la caché (cambia si cambia el conjunto)."""
    return conjunto_trabajo.datos()


@st.cache_data
def particiones_resumen(proporciones=PARTICION_OFICIAL, semilla=SEMILLA, huella=None):
    datos = cargar_trabajo(huella).drop(columns="origen", errors="ignore") if huella else dataset()
    X, y = separar_xy(marcar_fuera_de_rango(datos))
    X_train, X_val, X_test, y_train, y_val, y_test = particionar(X, y, semilla, proporciones)
    filas = []
    for nombre, yp in [("Entrenamiento", y_train), ("Validación", y_val), ("Prueba", y_test)]:
        conteo = yp.value_counts().reindex(range(3), fill_value=0)
        filas.append({"Conjunto": nombre, "Gestantes": len(yp), "% del total": round(len(yp) / len(y) * 100, 1),
                      **{c: int(conteo[i]) for i, c in enumerate(NOMBRES_CLASES)},
                      "% Alto Riesgo": round(conteo[CLASE_ALTO] / len(yp) * 100, 2)})
    disjuntos = not (set(X_train.index) & set(X_val.index) or set(X_train.index) & set(X_test.index) or set(X_val.index) & set(X_test.index))
    return pd.DataFrame(filas), disjuntos


@st.cache_data
def ejemplo_ips():
    # La sal es aleatoria: aquí solo importan las distribuciones, no los seudónimos
    datos, _ = inspeccionar(DIR_EJEMPLOS / "ips_ficticio_3280.csv", secrets.token_hex(16))
    return datos


def sal_configurada():
    sal = os.environ.get(VARIABLE_SAL, "")
    if not sal:
        try:
            sal = st.secrets.get(VARIABLE_SAL, "")
        except Exception:  # sin secrets.toml
            sal = ""
    return sal if len(sal) >= LONGITUD_MINIMA_SAL else None


def por_columna(conteo):
    return ", ".join(f"{k}: {v}" for k, v in conteo.items()) or "ninguno"


def seccion_ingesta():
    """Ingesta auditable: lectura por lotes, centinelas, filtro 3280 y seudonimización, paso a paso."""
    st.markdown(
        "Un archivo **CSV, TXT o Excel (.xlsx)** pasa por: lectura por lotes → valores centinela a nulo → **filtro de la "
        "Resolución 3280** (cada columna se conserva, se seudonimiza o se elimina) → **seudonimización** del documento con "
        "HMAC-SHA256 y sal secreta → rangos fisiológicos → reporte de calidad. Nombres, teléfonos y columnas desconocidas "
        "se descartan antes de mostrar o guardar nada."
    )
    with st.expander("Plantilla de captura para la IPS"):
        st.markdown("La hoja *Diccionario* explica cada columna: tipo, unidad, rango válido y para qué la usa MATERNA.")
        st.download_button("Plantilla Excel (.xlsx)", (DIR_PLANTILLAS / "plantilla_ips_3280.xlsx").read_bytes(),
                           "plantilla_ips_3280.xlsx")
    propio = puede(usuario, "ingesta_archivos")
    sal = sal_configurada()
    if propio:
        if sal is None:
            st.error(f"Falta la sal de seudonimización: defina `{VARIABLE_SAL}` en `.streamlit/secrets.toml` y reinicie.")
            return
        subido = st.file_uploader("Archivo de la IPS", type=["csv", "txt", "xlsx"])
        if subido is not None:
            st.session_state["archivo_ips"] = (subido.name, subido.getvalue())
    else:
        st.caption("Su rol solo puede ingerir el ejemplo ficticio.")
    if st.button("Ingerir el ejemplo ficticio (307 gestantes inventadas)", icon=":material/science:"):
        st.session_state["archivo_ips"] = ("ips_ficticio_3280.csv", (DIR_EJEMPLOS / "ips_ficticio_3280.csv").read_bytes())
    if "archivo_ips" not in st.session_state:
        return

    nombre, contenido = st.session_state["archivo_ips"]
    # Con el ejemplo ficticio basta una sal temporal si no hay una configurada: no se guarda nada
    sal_uso = sal or secrets.token_hex(16)
    # Caché por archivo: no se vuelve a ingerir en cada interacción (importa con 30.000 filas)
    huella = hashlib.sha256(contenido + (sal or "").encode()).hexdigest()
    guardado = st.session_state.get("ingesta_ips")
    if guardado and guardado[0] == huella and sal:
        datos, reporte = guardado[1], guardado[2]
    else:
        barra = st.progress(0.0, text="Ingiriendo por lotes…")
        with tempfile.TemporaryDirectory() as carpeta:
            # El archivo solo existe en una carpeta temporal mientras se procesa; luego se borra
            ruta = Path(carpeta) / Path(nombre).name
            ruta.write_bytes(contenido)
            total = contar_filas(ruta)
            try:
                datos, reporte = inspeccionar(ruta, sal_uso, al_avanzar=lambda leidas: barra.progress(
                    min(leidas / total, 1.0) if total else 0.5, text=f"{miles(leidas)} filas leídas…"))
            except ValueError as error:
                barra.empty()
                st.error(str(error))
                return
        barra.empty()
        if not guardado or guardado[0] != huella:
            lab.anotar(f"Ingesta de {miles(reporte.filas_leidas)} filas de la IPS · {miles(reporte.aptas_modelo)} aptas para el modelo")
        st.session_state["ingesta_ips"] = (huella, datos, reporte)

    st.markdown(f"**Reporte de calidad · {reporte.archivo}** ({reporte.formato}, separador "
                f"{reporte.separador!r}, {reporte.lotes} lote(s))")
    m = st.columns(4)
    m[0].metric("Filas leídas", reporte.filas_leidas)
    m[1].metric("Gestantes únicas", reporte.gestantes_unicas, help="Por seudónimo del documento")
    m[2].metric("Aptas para el modelo", reporte.aptas_modelo)
    m[3].metric("Duplicadas eliminadas", reporte.filas_duplicadas_eliminadas)
    c1, c2 = st.columns(2, gap="large")
    with c1:
        filas = [(d, len(c), ", ".join(c)) for d, c in reporte.columnas_por_decision.items()]
        filas += [("eliminadas", len(reporte.columnas_eliminadas), ", ".join(reporte.columnas_eliminadas)),
                  ("no reconocidas (descartadas)", len(reporte.columnas_desconocidas), ", ".join(reporte.columnas_desconocidas))]
        st.dataframe(pd.DataFrame(filas, columns=["Decisión 3280", "N.º", "Columnas"]), hide_index=True, width="stretch")
    with c2:
        limpieza = [("Valores centinela → nulo", por_columna(reporte.centinelas)),
                    ("Fuera de rango fisiológico → nulo", por_columna(reporte.fuera_de_rango)),
                    ("Gestantes con varias atenciones", reporte.gestantes_con_varias_atenciones),
                    ("Filas sin documento", reporte.sin_documento),
                    ("Faltantes que impiden el modelo", por_columna(reporte.faltantes_que_impiden_modelo))]
        st.dataframe(pd.DataFrame([(k, str(v)) for k, v in limpieza], columns=["Revisión", "Resultado"]),
                     hide_index=True, width="stretch")
    with st.expander(f"Datos seudonimizados ({len(datos)} filas, sin nombres ni documentos)"):
        st.dataframe(datos.head(100), width="stretch")
    st.download_button("Descargar datos seudonimizados (CSV)", datos.to_csv(index=False).encode("utf-8"),
                       "ips_seudonimizado.csv", "text/csv", icon=":material/download:")
    if propio and st.button("Guardar en la base del laboratorio", type="primary", icon=":material/database:"):
        id_carga = guardar_carga(datos, reporte, usuario["usuario"])
        lab.anotar(f"Carga n.º {id_carga} guardada en la base del laboratorio · {miles(len(datos))} atenciones")
        st.toast(f"Carga n.º {id_carga} guardada: {len(datos)} atenciones seudonimizadas.", icon=":material/check:", duration=3)
    cargas, gestantes = resumen_consolidado()
    if not cargas.empty:
        st.markdown(f"**Base del laboratorio:** {len(cargas)} carga(s) · {gestantes} gestante(s) distintas")
        st.dataframe(cargas, hide_index=True, width="stretch")


# ---------------------------------------------------------------- partición elegida (fase 06)
def particion_elegida():
    """Porcentajes y semilla elegidos en la fase 06. Viven en la sesión, no en los controles: Streamlit olvida el
    valor de un control cuando deja de dibujarse, y las fases 08 y 09 entrenan con esta partición."""
    return st.session_state.setdefault("particion", {"proporciones": PARTICION_OFICIAL, "semilla": SEMILLA})


def estado_particion():
    """(proporciones, semilla, conteos por clase, disjuntos, error). Con error, los conteos son los de la oficial."""
    elegida = particion_elegida()
    proporciones, semilla = tuple(elegida["proporciones"]), elegida["semilla"]
    try:
        tabla, disjuntos = particiones_resumen(proporciones, semilla, trabajo["huella"] if trabajo else None)
        return proporciones, semilla, tabla, disjuntos, None
    except ValueError as error:
        tabla, disjuntos = particiones_resumen()
        return proporciones, semilla, tabla, disjuntos, str(error)


def aplicar_preset():
    valores = PRESETS.get(st.session_state.get("part_preset"))
    if valores:
        for clave, valor in zip(CLAVES_PARTICION, valores):
            st.session_state[clave] = valor


def aviso_particion_invalida(error):
    st.error(f"La partición elegida no es válida: {error} Corríjala en {lab.nombre_fase('06')} para poder entrenar.")
    lab.boton_ir("06")


# ---------------------------------------------------------------- entrenamiento (fases 08 y 09)
def entrenar_con_avance(algoritmo, hiperparametros, proporciones, semilla, patrones=None):
    """Entrena una versión nueva mostrando el avance. Devuelve el resultado, o None si la configuración falla.

    `patrones`: patrones nuevos que se suman solo al entrenamiento (reentrenamiento de la fase 08)."""
    progreso = st.progress(0.0, text="Validación cruzada…")
    zona = st.empty()
    folds = []

    def al_avanzar(etapa, detalle):
        if etapa == "cv":
            folds.append(detalle["f1_macro"])
            progreso.progress(len(folds) / 8, text=f"Partición {detalle['particion']} de 5 · F1-macro {detalle['f1_macro']:.4f}")
            zona.altair_chart(graficos.f1_por_particion(folds), width="stretch")
        elif etapa == "ajuste":
            progreso.progress(6 / 8, text=f"Ajuste final con {detalle['n']} gestantes…")
        else:
            progreso.progress(7 / 8 if detalle["conjunto"] == "validación" else 1.0, text=f"Evaluación en {detalle['conjunto']}…")

    try:
        resultado = experimentos.entrenar(
            algoritmo, hiperparametros, proporciones, semilla, usuario["usuario"], datos=datos_trabajo,
            nombre_datos=nombre_datos, huella_datos=trabajo["huella"] if trabajo else None, patrones=patrones,
            al_avanzar=al_avanzar)
        resultado.pop("modelo")  # ya quedó guardado como versión; no hace falta en la sesión
        r = resultado["registro"]
        lab.anotar(f"{r['algoritmo']} entrenado · {ui_datos.segundos(r['tiempo_s'])} · versión {r['version']} guardada")
    except ValueError as error:
        st.error(f"No se pudo entrenar: {error}")
        resultado = None
    progreso.empty()
    zona.empty()  # el resultado final se dibuja aparte
    return resultado


def mostrar_entrenamiento(resultado, clave):
    r = resultado["registro"]
    st.success(f"Versión **{r['version']}** creada en {r['tiempo_s']:.1f} s · {r['algoritmo']} · partición {r['particion']} · "
               f"semilla {r['semilla']} · F1-macro en validación cruzada {r['cv_f1_macro']:.4f}")
    html('<div class="mt-pills">' + ui.pills([(f"Partición {i} · {decimal(v, 2)}", "ok")
                                              for i, v in enumerate(resultado["cv_f1_por_particion"], start=1)]) + "</div>")
    st.altair_chart(graficos.f1_por_particion(resultado["cv_f1_por_particion"]), width="stretch", key=f"folds_{clave}")
    st.dataframe(pd.DataFrame([{"Conjunto": c, "Gestantes": m["n"], "F1-macro": m["f1_macro"], "Recall Alto": m["recall_alto"],
                                "Accuracy": m["accuracy"], "ROC-AUC": m.get("roc_auc_ovr_macro"),
                                "Costo clínico": m["costo_clinico_total"]}
                               for c, m in resultado["metricas"].items()]).round(4), hide_index=True, width="stretch")
    if r.get("nota"):
        st.warning(r["nota"] + ".", icon=":material/info:")
    if resultado["identico_al_modelo_en_uso"]:
        st.info("**Reproducible:** con la misma partición, semilla e hiperparámetros, el modelo entrenado da probabilidades "
                "idénticas al modelo en uso.")
    st.caption(f"Datos: {r['datos']}. Métricas del sistema híbrido (modelo + reglas clínicas). La versión quedó guardada "
               "aparte; el modelo en uso no cambió.")
    ui_metricas.aviso()


COLUMNAS_REGISTRO = {
    "version": "Versión", "fecha": "Fecha", "usuario": "Usuario", "datos": "Datos", "algoritmo": "Algoritmo", "balanceo": "Balanceo",
    "hiperparametros": "Hiperparámetros", "particion": "Partición", "semilla": "Semilla", "n_patrones": "Patrones nuevos",
    "n_entrenamiento": "n entrenamiento",
    "cv_f1_macro": "F1-macro CV", "val_f1_macro": "F1-macro validación", "val_recall_alto": "Recall Alto validación",
    "val_costo_clinico_total": "Costo validación", "prueba_f1_macro": "F1-macro prueba", "prueba_recall_alto": "Recall Alto prueba",
    "tiempo_s": "Tiempo (s)",
}


def tabla_versiones(registro):
    st.dataframe(registro[list(COLUMNAS_REGISTRO)].rename(columns=COLUMNAS_REGISTRO).round(4), hide_index=True, width="stretch")


def mostrar_registro():
    """Tabla comparativa de las versiones del conjunto de trabajo y criterio de selección (fase 07)."""
    registro = experimentos.tabla_registro()
    if registro.empty:
        st.caption(f"Aún no hay experimentos. Entrene un modelo en {lab.nombre_fase('08')} o pruebe otra configuración en "
                   f"{lab.nombre_fase('09')}.")
        return
    mejor = registro.set_index("version").loc[experimentos.mejor_version(registro)]
    st.success(f"**Criterio de selección:** mayor F1-macro en validación y, en empate, mayor recall de Alto Riesgo en validación. "
               f"Con ese criterio, la mejor de {len(registro)} versión(es) es **{mejor.name}**: {mejor['algoritmo']}, partición "
               f"{mejor['particion']}, F1-macro {mejor['val_f1_macro']:.4f} y recall de Alto {mejor['val_recall_alto']:.4f}.")
    tabla_versiones(registro)
    ui_metricas.aviso()
    st.download_button("Descargar el registro de experimentos (CSV)", registro.to_csv(index=False).encode("utf-8-sig"),
                       "materna_registro_experimentos.csv", "text/csv", icon=":material/download:")
    st.caption("Cada fila es una versión guardada (modelo y parámetros); ninguna reemplaza al modelo en uso. "
               "El conjunto de prueba se informa, pero no se usa para elegir. Versiones con particiones o semillas distintas "
               "se midieron sobre gestantes distintas: compárelas con cuidado.")


def indice(opciones, valor):
    return opciones.index(valor) if valor in opciones else 0


def mas_cercano(opciones, valor):
    return min(opciones, key=lambda o: abs(o - valor))


def formulario_hiperparametros(algoritmo):
    """Controles de los hiperparámetros del algoritmo; parten de los mejores de la búsqueda de la Fase 2."""
    base = experimentos.hiperparametros_base(algoritmo)
    c = st.columns(4)
    if algoritmo == "Random Forest":
        profundidades, variables = [None, 4, 8, 12, 16, 20], ["sqrt", "log2", 0.3, 0.5, 0.8, 1.0]
        hp = {
            "n_estimators": c[0].number_input("Árboles (n_estimators)", 10, 1000, base["n_estimators"], step=50, key="hp_rf_arboles"),
            "max_depth": c[1].selectbox("Profundidad máxima (max_depth)", profundidades, indice(profundidades, base["max_depth"]),
                                        format_func=lambda v: "Sin límite" if v is None else str(v), key="hp_rf_profundidad"),
            "min_samples_leaf": c[2].number_input("Mínimo por hoja (min_samples_leaf)", 1, 50, base["min_samples_leaf"], key="hp_rf_hoja"),
            "max_features": c[3].selectbox("Variables por división (max_features)", variables, indice(variables, base["max_features"]),
                                           key="hp_rf_variables"),
        }
    elif algoritmo == "Regresión Logística":
        valores = [float(f"{v:.4g}") for v in GRID_C_LR]
        hp = {"C": c[0].select_slider("Regularización (C)", valores, mas_cercano(valores, base["C"]), key="hp_lr_c")}
    else:
        valores, gammas = [0.01, 0.1, 1.0, 10.0, 100.0, 1000.0], ["scale", 0.001, 0.01, 0.1, 1.0]
        kernel = c[0].selectbox("Kernel", list(experimentos.KERNELS), indice(list(experimentos.KERNELS), base["kernel"]), key="hp_svm_kernel")
        hp = {"kernel": kernel, "C": c[1].select_slider("Regularización (C)", valores, mas_cercano(valores, base["C"]), key="hp_svm_c")}
        if kernel != "linear":
            hp["gamma"] = c[2].selectbox("Gamma", gammas, indice(gammas, base["gamma"]), key="hp_svm_gamma")
        if kernel == "poly":
            hp["degree"] = c[3].selectbox("Grado del polinomio", [2, 3, 4, 5], key="hp_svm_grado")
    balanceos = list(experimentos.BALANCEOS)
    hp["balanceo"] = st.radio(
        "Balanceo de clases", balanceos, indice(balanceos, base["balanceo"]), horizontal=True, key=f"hp_balanceo_{algoritmo}",
        format_func={"SMOTE": "SMOTE (sobremuestreo dentro de cada partición)", "class_weight": "Pesos por clase"}.get)
    return hp


@st.cache_resource
def modelo_en_uso():
    return joblib.load(RUTA_MODELO)


@st.cache_data
def artefactos(huella_publicada):
    """Modelos y JSON entregados; la huella del modelo publicado es la clave de la caché."""
    filas = []
    for ruta in (sorted(DIR_MODELOS.glob("*.joblib")) + sorted(publicacion.carpeta().glob("*.joblib"))
                 + sorted(dir_assets().glob("*.json"))):
        filas.append({"Archivo": f"{ruta.parent.name}/{ruta.name}", "Tamaño (KB)": round(ruta.stat().st_size / 1024),
                      "SHA-256 (inicio)": hashlib.sha256(ruta.read_bytes()).hexdigest()[:16]})
    return pd.DataFrame(filas)


# ---------------------------------------------------------------- contexto común a todas las fases
df = dataset()
permitido = puede(usuario, "entrenar")
# Datos con que se entrena: el conjunto de trabajo activo (generado o subido y depurado) o, si no hay, el dataset base
trabajo = conjunto_trabajo.meta()
datos_trabajo = cargar_trabajo(trabajo["huella"]) if trabajo else None
nombre_datos = conjunto_trabajo.descripcion(trabajo)
test = metricas("metricas_test.csv").set_index("sistema")
principal = test.loc["Híbrido (Random Forest + reglas)"]


# ---------------------------------------------------------------- 01
def fase_problema():
    indicadores = [
        ("Recall de Alto Riesgo", decimal(principal["recall_alto"]), "Seguridad: de las gestantes graves, cuántas detecta"),
        ("F1-macro", decimal(principal["f1_macro"]), "Con ella se elige el modelo: pesa igual las tres clases"),
        ("ROC-AUC", decimal(principal["roc_auc_ovr_macro"]), "Capacidad de separar las clases, sin depender del umbral"),
        ("Costo clínico", str(int(principal["costo_clinico_total"])), "Errores pesados por su gravedad: menos es mejor"),
    ]
    for i, (columna, (nombre, valor, pie)) in enumerate(zip(st.columns(4, gap="small"), indicadores)):
        with columna, lab.tarjeta(f"kpi-{i}", alto="stretch"):
            html(ui.indicador(nombre, valor, pie))
    st.caption(f"Sistema final (Random Forest + reglas clínicas) en el conjunto de prueba: {int(principal['n'])} gestantes. "
               f"El detalle y cómo leer cada cifra están en {lab.nombre_fase('10')}.")
    c1, c2 = st.columns([3, 2], gap="medium")
    with c1, lab.tarjeta("problema", "Qué se predice y cómo se mide el éxito", alto="stretch"):
        st.markdown(
            "**Clasificación supervisada multiclase**: a partir de datos que se toman en el control prenatal, asignar a cada "
            "gestante **Bajo, Medio o Alto Riesgo** obstétrico, en zonas dispersas de La Guajira y Cesar y sin depender de internet. "
            "Un motor de **reglas clínicas** (GPC Minsalud 2013) garantiza que ningún signo crítico dependa de la probabilidad del modelo."
        )
        html(ui.filas([
            ("F1-macro", decimal(principal["f1_macro"]), "Métrica de selección del modelo: pesa igual las tres clases aunque estén desbalanceadas."),
            ("Recall de Alto Riesgo", decimal(principal["recall_alto"]), "Seguridad: de las gestantes graves, cuántas detecta. Un falso negativo puede costar una vida."),
            ("Costo clínico", int(principal["costo_clinico_total"]), "Suma de errores ponderada por su gravedad (matriz definida por el equipo). Menos es mejor."),
            ("ROC-AUC", decimal(principal["roc_auc_ovr_macro"]), "Capacidad de separar las clases, sin depender del umbral."),
        ]))
    with c2, lab.tarjeta("costo", "Matriz de costo clínico", "filas: clase real · columnas: clase asignada", alto="stretch"):
        html(ui.matriz(MATRIZ_COSTO.tolist(), tono=lambda i, j, v: "d" if v >= 5 else "e" if v else "",
                       descripcion="Matriz de costo clínico"))
        st.caption("Subestimar el riesgo pesa mucho más que sobreestimarlo: una gestante grave tratada como Bajo Riesgo pesa 10. "
                   "Los pesos son supuestos del equipo, por validar con un asesor clínico.")


# ---------------------------------------------------------------- 02
def fase_datos():
    c1, c2 = st.columns([3, 2], gap="medium")
    with c1, lab.tarjeta("dataset", "Dataset base", "sintético calibrado", alto="stretch"):
        html(ui.cifra(miles(len(df)), etiqueta=f"gestantes · {df.shape[1]} columnas · 65 % La Guajira y 35 % Cesar"))
        st.markdown("Calibrado con cifras del DANE (Estadísticas Vitales Wayúu 2015–2024), el INS y el ONS. "
                    "**No son pacientes reales**: las métricas no son evidencia clínica.")
        grafico(graficos.barras_clases(df))
        st.caption("Los archivos de la Resolución 4505 recibidos correspondían a recién nacidos, sin variables maternas: "
                   "no son aptos para el modelo y, por tener datos personales reales, no se cargan en el laboratorio.")
    with c2, lab.tarjeta("territorio", "Territorio y etnia", "solo para auditar sesgos", alto="stretch"):
        for col, titulo in [("departamento", "Departamento"), ("pertenencia_etnica", "Pertenencia étnica")]:
            st.dataframe(df[col].value_counts().rename_axis(titulo).reset_index(name="Gestantes"), hide_index=True, width="stretch")
    with lab.tarjeta("ingesta", "Ingesta auditable de archivos de la IPS", "filtro 3280 y seudonimización"):
        seccion_ingesta()
    with lab.tarjeta("conjunto", "Conjunto de trabajo: datos para entrenar", "generar o subir datos crudos"):
        ui_datos.seccion_conjunto(usuario, permitido, trabajo)
    with lab.tarjeta("escalabilidad", "Escalabilidad", "de 5.000 a 30.000 registros"):
        ui_datos.seccion_escalabilidad(permitido)
    with lab.tarjeta("patron", "Nuevo patrón manual", "validado con el catálogo 3280"):
        ui_patrones.seccion_formulario(usuario, puede(usuario, "ingesta_archivos"), permitido,
                                       df if datos_trabajo is None else datos_trabajo, nombre_datos)


# ---------------------------------------------------------------- 03
def fase_eda():
    c1, c2 = st.columns([2, 3], gap="medium")
    with c1, lab.tarjeta("nulos", "Datos faltantes", alto="stretch"):
        nulos = (df.isna().mean() * 100).round(2)
        nulos = nulos[nulos > 0].sort_values(ascending=False)
        grafico(graficos.barras_nulos({ETIQUETAS.get(k, k): v for k, v in nulos.items()}))
        st.caption("Glucosa y FCF faltan cuando no hay glucómetro o doppler fetal. Los nulos **no** se concentran en el área rural.")
    with c2, lab.tarjeta("presion", "Presión sistólica vs diastólica por clase", alto="stretch"):
        grafico(graficos.dispersion_presion(df))
        st.caption("Las líneas punteadas marcan 140/90 (hipertensión) y 160/110 (hipertensión severa, regla clínica).")
    with lab.tarjeta("comparacion", "Dataset sintético vs archivo de la IPS"):
        fuentes = {"Ejemplo ficticio (data/ejemplos)": ejemplo_ips}
        if not datos_consolidados().empty:
            fuentes["Base consolidada de la consola"] = datos_consolidados
        fuente = st.radio("Archivo de la IPS", list(fuentes), horizontal=True)
        ips = fuentes[fuente]()
        variables = [v for v in ETIQUETAS if v in ips]
        comparacion = pd.DataFrame([{
            "Variable": ETIQUETAS[v], "Media sintético": df[v].mean(), "Media IPS": ips[v].mean(),
            "Mediana sintético": df[v].median(), "Mediana IPS": ips[v].median(),
            "% nulos sintético": df[v].isna().mean() * 100, "% nulos IPS": ips[v].isna().mean() * 100,
        } for v in variables]).round(2)
        st.dataframe(comparacion, hide_index=True, width="stretch")
        elegida = st.selectbox("Distribución de", variables, format_func=ETIQUETAS.get)
        grafico(graficos.histogramas_comparados(df[elegida], ips[elegida], elegida, ETIQUETAS[elegida]))
        if fuente.startswith("Ejemplo"):
            st.caption("El ejemplo ficticio se construyó a partir del dataset sintético: por eso las distribuciones casi coinciden. "
                       "Con un archivo real de una IPS, esta comparación mostraría cuánto se parece el sintético a la realidad.")
    if datos_trabajo is not None:
        with lab.tarjeta("eda-trabajo", "EDA del conjunto de trabajo", "frente al dataset base"):
            ui_datos.seccion_eda(df, datos_trabajo, trabajo, ETIQUETAS)


# ---------------------------------------------------------------- 04
def fase_limpieza():
    with lab.tarjeta("depuracion", "Depuración de los datos crudos", "paso a paso, con el conteo antes y después"):
        ui_datos.seccion_depuracion(usuario, permitido)
    with lab.tarjeta("reglas", "Qué hace la limpieza"):
        st.markdown(
            "1. **Estructura:** se elimina la columna vacía `Unnamed: 16` y `convulsiones` pasa de TRUE/FALSE a 1/0.\n"
            f"2. **Valores centinela** de los sistemas de información → nulo: `{'`, `'.join(sorted(CENTINELAS))}`.\n"
            "3. **Filtro 3280:** cada columna se conserva, se seudonimiza o se elimina según el catálogo (página *Variables 3280*).\n"
            "4. **Rangos fisiológicos:** un valor imposible es un error de captura y se vuelve nulo.\n"
            "5. **Imputación estratificada** de glucosa y FCF: mediana por área × trimestre, aprendida solo con el entrenamiento."
        )
    c1, c2 = st.columns(2, gap="medium")
    with c1, lab.tarjeta("rangos", "Rangos fisiológicos plausibles", alto="stretch"):
        st.dataframe(pd.DataFrame([(ETIQUETAS.get(k, k), lo, hi) for k, (lo, hi) in RANGOS_PLAUSIBLES.items()],
                                  columns=["Variable", "Mínimo", "Máximo"]), hide_index=True, width="stretch")
    with c2, lab.tarjeta("decisiones", "Decisiones del filtro 3280", alto="stretch"):
        st.dataframe(tabla_decisiones()["Decisión"].value_counts().rename_axis("Decisión").reset_index(name="Variables"),
                     hide_index=True, width="stretch")
    with lab.tarjeta("imputador", "Medianas aprendidas por el imputador del modelo en uso",
                     "si un estrato tiene menos de 10 datos se usa la del área"):
        imp = modelo_en_uso().named_steps["imputacion"]
        filas = []
        for col in imp.columnas:
            for (area, tri), valor in sorted(imp.mediana_estrato_[col].items()):
                filas.append({"Variable": ETIQUETAS[col], "Área": area, "Trimestre": tri, "Mediana": valor})
            filas.append({"Variable": ETIQUETAS[col], "Área": "Global (respaldo)", "Trimestre": "—", "Mediana": imp.mediana_global_[col]})
        st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
    codigo(depurar, marcar_fuera_de_rango, reemplazar_centinelas, MedianaEstratificadaImputer.transform)


# ---------------------------------------------------------------- 05
def fase_variables():
    pre = json.loads((dir_assets() / "preproceso.json").read_text(encoding="utf-8"))
    tipo = {**{c: "Continua · RobustScaler" for c in pre["escalado"]["columnas"]},
            **{c: "Discreta · sin escalar" for c in pre["discretas"]},
            **{c: "Indicador de dato faltante" for c in pre["indicadores"]}}
    c1, c2 = st.columns(2, gap="medium")
    with c1, lab.tarjeta("entrada", "Variables de entrada", alto="stretch"):
        html(ui.cifra(len(variables_modelo()), len(pre["variables_entrada"]), "datos de la gestante → variables del modelo"))
        st.markdown("Etnia, municipio y departamento **no entran** al modelo.")
        st.dataframe(pd.DataFrame([{"N.º": i + 1, "Variable de entrada": v, "Tipo": tipo.get(v, "One-Hot")}
                                   for i, v in enumerate(pre["variables_entrada"])]), hide_index=True, width="stretch", height=420)
    with c2:
        with lab.tarjeta("escalado", "RobustScaler", "(x − mediana) / rango intercuartílico"):
            st.caption("Robusto a valores extremos.")
            st.dataframe(pd.DataFrame({"Variable": [ETIQUETAS[c] for c in pre["escalado"]["columnas"]],
                                       "Centro (mediana)": pre["escalado"]["centro"], "Escala (RIC)": pre["escalado"]["escala"]}),
                         hide_index=True, width="stretch")
        with lab.tarjeta("ablacion", "Ablación: ¿mejoran las variables demográficas?"):
            st.dataframe(metricas("ablacion_variables_demograficas.csv"), hide_index=True, width="stretch")
            st.caption("Agregar etnia y territorio no mejora el modelo: quedan fuera por ética y solo sirven para auditar sesgos.")
    codigo(pasos_preprocesamiento)


# ---------------------------------------------------------------- 06
def fase_division():
    elegida = particion_elegida()
    # Los controles se llenan desde la partición guardada (al volver a esta fase ya no existen en la sesión)
    for clave, valor in zip(CLAVES_PARTICION, elegida["proporciones"]):
        st.session_state.setdefault(clave, valor)
    st.session_state.setdefault("part_semilla", elegida["semilla"])
    actual = tuple(st.session_state[clave] for clave in CLAVES_PARTICION)
    st.session_state["part_preset"] = next((nombre for nombre, valores in PRESETS.items() if valores == actual), PERSONALIZADA)

    c1, c2 = st.columns([5, 4], gap="medium")
    with c1, lab.tarjeta("particion", "Partición de los datos", alto="stretch"):
        st.radio("Partición", [*PRESETS, PERSONALIZADA], horizontal=True, key="part_preset", on_change=aplicar_preset,
                 label_visibility="collapsed")
        c = st.columns(4)
        proporciones = (c[0].number_input("Entrenamiento (%)", 1, 98, key="part_entrenamiento"),
                        c[1].number_input("Validación (%)", 1, 98, key="part_validacion"),
                        c[2].number_input("Prueba (%)", 1, 98, key="part_prueba"))
        semilla_trabajo = c[3].number_input("Semilla", 0, 2**31 - 1, key="part_semilla")
        cambio = (proporciones, semilla_trabajo) != (tuple(elegida["proporciones"]), elegida["semilla"])
        elegida["proporciones"], elegida["semilla"] = proporciones, semilla_trabajo
        proporciones, semilla_trabajo, tabla, disjuntos, error = estado_particion()
        texto_particion = "/".join(str(p) for p in proporciones)
        if cambio and not error:
            lab.anotar(f"Partición {texto_particion} aplicada · semilla {semilla_trabajo}")
        if error:
            st.error(f"{error} Corríjalos para poder entrenar; abajo se muestra la partición oficial.")
            html('<div class="mt-pills">' + ui.pills([(f"Suma {sum(proporciones)}", "warn")]) + "</div>")
        else:
            html(ui.barra_particion([(f["Conjunto"], p, f["Gestantes"]) for p, (_, f) in zip(proporciones, tabla.iterrows())]))
            html('<div class="mt-pills">' + ui.pills([
                ("Suma 100", "ok"), ("Estratificada", "ok"),
                f"Alto Riesgo ≈ {decimal(tabla['% Alto Riesgo'].mean(), 1)} % en cada conjunto"]) + "</div>")
        st.caption(f"Datos: {nombre_datos}. La usan los entrenamientos de las fases 08 y 09.")
    with c2, lab.tarjeta("garantias", "Garantías de la partición", alto="stretch"):
        st.markdown(
            "- Partición **estratificada** por clase: la proporción de Alto Riesgo es la misma en los tres conjuntos.\n"
            f"- Conjuntos disjuntos (ninguna gestante se repite): **{'sí' if disjuntos else 'NO'}**.\n"
            "- **Sin fuga de datos:** imputador, escalador y One-Hot se ajustan solo con el entrenamiento, y SMOTE se aplica "
            "**dentro** de cada partición de la validación cruzada, nunca antes.\n"
            "- El conjunto de **prueba** de la Fase 2 se usó una sola vez, al final: el modelo se eligió con validación.\n"
            "- Las cifras oficiales de la Fase 2 se calcularon con 70/15/15 y semilla 42, y no cambian."
        )
    with lab.tarjeta("conteos", "Gestantes por clase en cada conjunto",
                     "partición oficial 70/15/15" if error else f"partición {texto_particion} · semilla {semilla_trabajo}"):
        st.dataframe(tabla, hide_index=True, width="stretch")
        es_oficial = proporciones == tuple(PARTICION_OFICIAL) and semilla_trabajo == SEMILLA and not trabajo
        if not error:
            pocos = tabla[tabla["Alto Riesgo"] < MIN_ALTO]
            if not pocos.empty:
                st.warning("Muy pocos casos de Alto Riesgo en " + " y ".join(f"{f['Conjunto']} ({f['Alto Riesgo']})" for _, f in pocos.iterrows())
                           + f": con menos de {MIN_ALTO}, un solo error mueve el recall de Alto más de 10 puntos.")
            if es_oficial:
                st.caption("Es la partición oficial de la Fase 2.")
            else:
                st.info(f"Partición de trabajo **{texto_particion}** con semilla {semilla_trabajo}. Solo afecta a lo que se entrene "
                        "desde aquí; las tablas oficiales de las fases 07, 09, 10 y 11 siguen siendo las de 70/15/15.")
    codigo(particionar)


# ---------------------------------------------------------------- 07
def seccion_recorrido():
    """«Ver el recorrido»: el camino real de una gestante por el modelo en uso y las reglas, animado."""
    st.markdown("Elija una gestante y vea, paso a paso, cómo llega el sistema a su resultado: sus datos se convierten en "
                "variables, cada árbol le hace sus preguntas, se promedian las 300 hojas y las reglas clínicas tienen la "
                "última palabra. Es el **Random Forest en uso**, no un esquema: los umbrales y las respuestas son los reales.")
    casos = dict(recorrido.CASOS)
    if st.session_state.get("recorrido_registro"):
        casos = {recorrido.ULTIMA: st.session_state["recorrido_registro"], **casos}
    if st.session_state.get("recorrido_caso") not in casos:
        st.session_state.pop("recorrido_caso", None)
    visible = st.session_state.get("recorrido_visible", False)
    c = st.columns([4, 1], vertical_alignment="bottom")
    nombre = c[0].radio("Gestante", list(casos), horizontal=True, key="recorrido_caso")
    if c[1].button("Ocultar" if visible else "Ver el recorrido", type="secondary" if visible else "primary",
                   icon=":material/visibility_off:" if visible else ":material/account_tree:", key="recorrido_boton"):
        st.session_state["recorrido_visible"] = visible = not visible
        st.rerun()
    if not visible:
        return
    datos = recorrido.recorrido(casos[nombre], modelo_en_uso())
    if st.session_state.get("recorrido_anotado") != nombre:
        st.session_state["recorrido_anotado"] = nombre
        lab.anotar(f"Recorrido de «{nombre.split(' (')[0]}»: {datos['categoria']}")
    ui_recorrido.mostrar(datos, clave=f"recorrido-{list(casos).index(nombre)}")
    st.caption(f"Se dibujan {len(datos['arboles'])} de los {datos['n_arboles']} árboles; el promedio y los puntos salen de los "
               f"{datos['n_arboles']}. Para otra gestante, evalúela en la página «Triaje (Fase 2)» y pulse «Ver cómo decidió el sistema».")
    with st.expander("El recorrido en texto"):
        for frase in recorrido.en_texto(datos):
            st.markdown(frase)


def fase_algoritmo():
    with lab.tarjeta("recorrido", "Cómo decide el sistema", "el recorrido de una gestante, paso a paso"):
        seccion_recorrido()
    with lab.tarjeta("cv", "Validación cruzada de los tres modelos", "5 particiones · mejor ajuste por modelo y balanceo"):
        comp = metricas("comparacion_cv_por_estrategia.csv")
        st.dataframe(comp[["modelo", "balanceo", "hiperparametros", "cv_f1_macro_media", "cv_f1_macro_std", "cv_recall_alto_media"]]
                     .rename(columns={"modelo": "Modelo", "balanceo": "Balanceo", "hiperparametros": "Hiperparámetros",
                                      "cv_f1_macro_media": "F1-macro", "cv_f1_macro_std": "± desv.", "cv_recall_alto_media": "Recall Alto"}),
                     hide_index=True, width="stretch")
    with lab.tarjeta("seleccion", "Selección del sistema híbrido", "en el conjunto de validación"):
        val = metricas("metricas_validacion.csv")
        st.dataframe(val[["sistema", "f1_macro", "recall_alto", "costo_clinico_total", "roc_auc_ovr_macro"]], hide_index=True, width="stretch")
        ui_metricas.aviso()
    with lab.tarjeta("porque", "Por qué Random Forest y no la SVM de la Fase 1"):
        st.markdown("Además de su mejor F1-macro, las pruebas de coherencia clínica cambian una sola variable de una gestante sana "
                    "(presión 145/95, glucosa 145, FCF 165, edad 36 o cero controles). La SVM respondía Bajo Riesgo en esos casos; "
                    "el Random Forest los clasifica al menos como Medio.")
    with lab.tarjeta("experimentos", "Experimentos del conjunto de trabajo", "versiones propias y criterio de selección"):
        mostrar_registro()
    codigo(con_estrategias_balanceo)


# ---------------------------------------------------------------- 08
def fase_entrenamiento():
    proporciones, semilla_trabajo, _, _, error = estado_particion()
    texto_particion = "/".join(str(p) for p in proporciones)
    with lab.tarjeta("entrenar", "Entrenamiento en vivo", f"partición {texto_particion} · semilla {semilla_trabajo}"):
        st.markdown(f"Entrena el algoritmo elegido con los **mejores hiperparámetros** de la búsqueda de la Fase 2, sobre la partición "
                    f"**{texto_particion}** con semilla {semilla_trabajo}, elegidas en {lab.nombre_fase('06')}. Muestra cada partición de la "
                    "validación cruzada al terminar y guarda el resultado como una **versión nueva**. **No reemplaza el modelo en uso.**")
        st.caption(f"Datos: {nombre_datos}.")
        if error:
            aviso_particion_invalida(error)
        algoritmo = st.radio("Algoritmo", experimentos.ALGORITMOS, horizontal=True, key="entrenar_algoritmo")
        html('<div class="mt-pills">' + ui.pills([f"{k}: {'sin límite' if v is None else v}"
                                                  for k, v in experimentos.hiperparametros_base(algoritmo).items()]) + "</div>")
        if algoritmo == "SVM":
            st.caption(AVISO_SVM)
        if st.button("Entrenar en vivo", type="primary", icon=":material/play_arrow:", disabled=not (permitido and not error)):
            st.session_state["entrenamiento"] = entrenar_con_avance(algoritmo, None, proporciones, semilla_trabajo)
        if not permitido:
            st.caption("Solo el administrador puede reentrenar.")
        if st.session_state.get("entrenamiento"):
            mostrar_entrenamiento(st.session_state["entrenamiento"], "vivo")
        st.caption(f"Para cambiar los hiperparámetros, use «Probar otra configuración» en {lab.nombre_fase('09')}.")
    with lab.tarjeta("reentrenar", "Reentrenar con los patrones nuevos", "antes y después"):
        ui_patrones.seccion_reentrenar(permitido, trabajo["huella"] if trabajo else None, entrenar_con_avance)
    codigo(experimentos.entrenar)


# ---------------------------------------------------------------- 09
def fase_parametros():
    proporciones, semilla_trabajo, _, _, error = estado_particion()
    texto_particion = "/".join(str(p) for p in proporciones)
    exp = metricas("experimentos_cv_completo.csv")
    por_modelo = exp.groupby("modelo").size()
    with lab.tarjeta("probar", "Probar otra configuración", f"partición {texto_particion} · semilla {semilla_trabajo}"):
        st.markdown(f"Cambie los hiperparámetros y entrene: se guarda como una **versión nueva** del conjunto de trabajo, con la "
                    f"partición {texto_particion} y la semilla {semilla_trabajo} elegidas en {lab.nombre_fase('06')}. Los controles "
                    "parten de la mejor configuración de la búsqueda.")
        st.caption(f"Datos: {nombre_datos}.")
        if error:
            aviso_particion_invalida(error)
        algoritmo_hp = st.radio("Algoritmo", experimentos.ALGORITMOS, horizontal=True, key="hp_algoritmo")
        hiperparametros = formulario_hiperparametros(algoritmo_hp)
        if algoritmo_hp == "SVM":
            st.caption(AVISO_SVM)
        if st.button("Entrenar esta configuración", type="primary", icon=":material/tune:",
                     disabled=not (permitido and not error)):
            st.session_state["experimento_hp"] = entrenar_con_avance(algoritmo_hp, hiperparametros, proporciones, semilla_trabajo)
        if not permitido:
            st.caption("Solo el administrador puede entrenar.")
        if st.session_state.get("experimento_hp"):
            mostrar_entrenamiento(st.session_state["experimento_hp"], "hp")
        registro = experimentos.tabla_registro()
        if not registro.empty and (registro["algoritmo"] == algoritmo_hp).any():
            st.markdown(f"**Versiones de {algoritmo_hp}**, de mayor a menor F1-macro en validación")
            tabla_versiones(registro[registro["algoritmo"] == algoritmo_hp].sort_values("val_f1_macro", ascending=False))
    with lab.tarjeta("grilla", "Búsqueda en grilla de la Fase 2", f"{len(exp)} configuraciones × 5 particiones"):
        st.markdown(f"**GridSearchCV:** {len(exp)} configuraciones × 5 particiones = **{len(exp) * 5} entrenamientos**. "
                    f"SMOTE y `class_weight` se comparan como un hiperparámetro más, nunca combinados. "
                    + " · ".join(f"{m}: {n}" for m, n in por_modelo.items()))
        grafico(graficos.dispersion_hiperparametros(exp))
        modelo = st.selectbox("Mejores configuraciones de", list(por_modelo.index), index=list(por_modelo.index).index("Random Forest"))
        st.dataframe(exp[exp["modelo"] == modelo].sort_values("cv_f1_macro_media", ascending=False)
                     [["balanceo", "hiperparametros", "cv_f1_macro_media", "cv_f1_macro_std", "cv_recall_alto_media", "tiempo_ajuste_s"]].head(10),
                     hide_index=True, width="stretch")
    codigo(grid_random_forest, experimentos.construir)


# ---------------------------------------------------------------- 10
def fase_evaluacion():
    ui_metricas.seccion_interpretacion(trabajo)
    with lab.tarjeta("oficial", "Los tres modelos en el conjunto de prueba", "cifras oficiales de la Fase 2"):
        st.markdown(f"Se usó **una sola vez**, con {int(test['n'].iloc[0])} gestantes (23 de Alto Riesgo). Los intervalos de confianza "
                    "del 95 % se calcularon con 2.000 remuestreos bootstrap: con tan pocos casos graves, la incertidumbre es grande.")
        st.dataframe(test[["f1_macro", "f1_macro_ic95", "recall_alto", "recall_alto_ic95", "roc_auc_ovr_macro",
                           "falsos_negativos_alto", "costo_clinico_total"]].rename(columns={
            "f1_macro": "F1-macro", "f1_macro_ic95": "IC 95 % F1", "recall_alto": "Recall Alto", "recall_alto_ic95": "IC 95 % recall",
            "roc_auc_ovr_macro": "ROC-AUC", "falsos_negativos_alto": "Graves no detectadas", "costo_clinico_total": "Costo clínico"}),
            width="stretch")
        c1, c2 = st.columns(2, gap="large")
        c1.image(str(DIR_METRICAS.parent / "figures" / "matrices_confusion_test.png"), caption="Matrices de confusión (prueba)")
        c2.image(str(DIR_METRICAS.parent / "figures" / "curvas_roc_test.png"), caption="Curvas ROC (prueba)")
        st.markdown("**Sin signos críticos** (lo que el modelo resuelve solo, sin las reglas)")
        st.dataframe(metricas("metricas_test_sin_signos_criticos.csv")[["sistema", "n", "f1_macro", "recall_alto", "costo_clinico_total"]],
                     hide_index=True, width="stretch")
    with lab.tarjeta("lote", "Lote de demostración: registros que el modelo no usó"):
        ui_datos.seccion_lote(trabajo)
    lab.boton_ir("12", "Continuar a la entrega al Módulo 2 (fase 12)")
    codigo(calcular_metricas, intervalo_bootstrap, interpretacion.paneles, conjunto_trabajo.establecer)


# ---------------------------------------------------------------- 11
def fase_generalizacion():
    curvas, brecha = metricas("curvas_aprendizaje.csv"), metricas("brecha_sobreajuste.csv")
    veredicto = {"Regresión Logística": "subajusta", "SVM": "sobreajusta", "Random Forest": "ajusta bien"}
    for i, (columna, modelo) in enumerate(zip(st.columns(3, gap="small"), veredicto)):
        with columna, lab.tarjeta(f"curva-{i}", modelo, veredicto[modelo], alto="stretch"):
            grafico(graficos.curva_aprendizaje(curvas, modelo))
    with lab.tarjeta("brecha", "Brecha entre entrenamiento y validación cruzada", "curvas oficiales de la Fase 2"):
        st.dataframe(brecha.rename(columns={"modelo": "Modelo", "f1_entrenamiento": "F1 entrenamiento", "f1_cv": "F1 validación cruzada",
                                            "f1_cv_std": "± desv.", "brecha": "Brecha"}), hide_index=True, width="stretch")
        ui_metricas.aviso()
        st.markdown(
            "- **Regresión Logística: subajusta.** Entrenamiento y validación quedan bajos y juntos: el modelo es demasiado simple.\n"
            "- **SVM: sobreajusta.** Memoriza el entrenamiento (1,000) pero valida en 0,861: la brecha es la mayor.\n"
            "- **Random Forest: ajusta bien.** También llega a 1,000 en entrenamiento, algo normal en un bosque, pero valida en 0,932 "
            "y se sostiene en validación (0,944) y prueba (0,943). Más datos reales seguirían ayudando: la curva aún sube."
        )
        st.caption("Calculado con `python -m src.curvas_aprendizaje` (validación cruzada de 5 particiones sobre 840 gestantes).")
    with lab.tarjeta("curva-version", "Curva de una versión del conjunto de trabajo"):
        versiones = {r["version"]: r for r in experimentos.leer_registro()}
        if not versiones:
            st.caption(f"Aún no hay versiones. Entrene un modelo en {lab.nombre_fase('08')} y vuelva para calcular su curva.")
        else:
            c = st.columns([3, 2], vertical_alignment="bottom")
            elegida = c[0].selectbox(
                "Versión", sorted(versiones, reverse=True), key="curva_version",
                format_func=lambda v: f"{v} · {versiones[v]['algoritmo']} · partición {versiones[v]['particion']} · semilla {versiones[v]['semilla']}")
            if c[1].button("Calcular la curva de aprendizaje", icon=":material/show_chart:", disabled=not permitido):
                with st.spinner("Entrenando con 7 tamaños × 5 particiones…"):
                    try:
                        st.session_state.setdefault("curvas_exp", {})[elegida] = experimentos.curva_aprendizaje(elegida)
                        lab.anotar(f"Curva de aprendizaje de {elegida} calculada · 7 tamaños × 5 particiones")
                    except ValueError as error:
                        st.error(str(error))
            if not permitido:
                st.caption("Solo el administrador puede calcular curvas nuevas.")
            curva = st.session_state.get("curvas_exp", {}).get(elegida)
            if curva is not None:
                grafico(graficos.curva_aprendizaje(curva, curva["modelo"].iloc[0], dominio_x=None))
                ultimo = curva.iloc[-1]
                brecha_v = ultimo["f1_entrenamiento"] - ultimo["f1_cv"]
                st.markdown(f"Con {int(ultimo['n_entrenamiento'])} gestantes de entrenamiento: F1-macro **{ultimo['f1_entrenamiento']:.3f}** "
                            f"en entrenamiento y **{ultimo['f1_cv']:.3f}** en validación cruzada (± {ultimo['f1_cv_std']:.3f}); "
                            f"brecha de **{brecha_v:.3f}**.")
                st.dataframe(curva.drop(columns="modelo").rename(columns={
                    "n_entrenamiento": "Gestantes", "f1_entrenamiento": "F1 entrenamiento", "f1_entrenamiento_std": "± desv. entr.",
                    "f1_cv": "F1 validación cruzada", "f1_cv_std": "± desv. CV"}), hide_index=True, width="stretch")
    codigo(experimentos.curva_aprendizaje)


# ---------------------------------------------------------------- 12
def fase_entrega():
    modelo_json = json.loads((dir_assets() / "modelo_rf.json").read_text(encoding="utf-8"))
    vigente = publicacion.assets_vigentes()
    with lab.tarjeta("entrega", "Qué recibe el Módulo 2", "entrega vigente" if vigente else "entrega ANTIGUA"):
        st.markdown(
            "El despliegue es el **Módulo 2**: la app de usuario final (Flutter, **web y móvil**) para el personal de salud en "
            "territorio, con captura manual, carga masiva de archivos de la IPS y semáforo de riesgo. Los dos módulos son "
            "independientes y se integran **solo** a través de estos artefactos, que el Módulo 1 entrega ya validados:\n\n"
            f"- `flutter_app/assets/modelo_rf.json`: Random Forest **versión {modelo_json['version']}** ({modelo_json['n_arboles']} árboles), "
            "con la huella SHA-256 del `.joblib` del que salió.\n"
            "- `preproceso.json` y `reglas.json`: imputación, escalado, One-Hot y los 4 signos críticos.\n"
            "- `casos_paridad.json`: 200 casos con la respuesta exacta de scikit-learn, que la app debe reproducir.\n\n"
            f"Estado de la entrega: **{'vigente' if vigente else 'ANTIGUA: vuelva a publicar'}** respecto del modelo publicado. "
            "Con el modelo oficial v1, la inferencia desde JSON reproduce a scikit-learn con diferencia 0 en las 1.200 gestantes."
        )
        st.dataframe(artefactos(publicacion.publicado()["sha256"]), hide_index=True, width="stretch")
    with lab.tarjeta("publicar", "Publicar al Módulo 2", "solo el administrador · solo Random Forest"):
        ui_publicacion.seccion_publicar(usuario, permitido)
    with lab.tarjeta("modulos", "Los dos módulos «suman uno», pero no es lo mismo"):
        ui_publicacion.tabla_dos_modulos()
    with lab.tarjeta("motor", "Motor de reglas clínicas", "sensibilidad en signos críticos"):
        X, y = separar_xy(marcar_fuera_de_rango(df))
        mascara = mascara_reglas(X)
        _, _, X_test, _, _, y_test = particionar(X, y)
        mascara_test = mascara_reglas(X_test)
        c = st.columns(2)
        c[0].metric("Prueba: signos críticos detectados como Alto", f"{int((y_test[mascara_test] == CLASE_ALTO).sum())}/{int(mascara_test.sum())}")
        c[1].metric("Dataset completo", f"{int((y[mascara] == CLASE_ALTO).sum())}/{int(mascara.sum())}")
        st.caption("100 % de sensibilidad **solo** en los casos con signo crítico; el recall global de Alto Riesgo en prueba es "
                   f"{principal['recall_alto']:.3f}, con intervalo de confianza del 95 % {principal['recall_alto_ic95']}. Aviso: las etiquetas sintéticas se generaron con estos mismos "
                   "umbrales, así que esto demuestra que el sistema no deja escapar un caso crítico, no que las reglas sean clínicamente mejores.")
        st.markdown("**Pruebe el motor de reglas**")
        r = st.columns(4)
        prueba = {"pas_mmhg": r[0].number_input("PAS", 60, 250, 150), "pad_mmhg": r[1].number_input("PAD", 30, 150, 95),
                  "proteinuria": r[2].selectbox("Proteinuria", [0, 1, 2], format_func=lambda v: ["Negativa", "+", "++"][v]),
                  "convulsiones": int(r[3].toggle("Convulsiones"))}
        activadas = evaluar_reglas(prueba)
        if activadas:
            st.error("**Alto Riesgo por regla clínica:** " + " · ".join(activadas))
        else:
            st.success("Ninguna regla se activa: decide el modelo.")
    codigo(evaluar_reglas)


# ---------------------------------------------------------------- ética y limitaciones
def fase_etica():
    with lab.tarjeta("sesgos", "Auditoría de sesgos", "recall de Alto Riesgo por subgrupo"):
        aud = metricas("auditoria_subgrupos.csv")
        st.caption("Con predicciones fuera de partición sobre las 1.200 gestantes.")
        variable = st.radio("Subgrupo", ["area_residencia", "pertenencia_etnica", "atendido_por", "departamento"], horizontal=True,
                            format_func={"area_residencia": "Área", "pertenencia_etnica": "Etnia", "atendido_por": "Quién atiende",
                                         "departamento": "Departamento"}.get)
        st.dataframe(aud[aud["variable"] == variable][["grupo", "n", "n_alto_real", "recall_alto", "f1_macro"]]
                     .rename(columns={"grupo": "Grupo", "n": "Gestantes", "n_alto_real": "Alto Riesgo reales",
                                      "recall_alto": "Recall Alto", "f1_macro": "F1-macro"}), hide_index=True, width="stretch")
    with lab.tarjeta("limitaciones", "Limitaciones que deben decirse"):
        st.markdown(
            "- **Brecha rural:** el sistema detecta el 88 % de los casos graves rurales (71/81) frente al 94 % en cabecera (67/71). "
            "Plan: ajustar umbrales para el área rural con un especialista.\n"
            "- **Grupos pequeños:** Wiwa y Kogui tienen 20 gestantes cada uno, y la auxiliar de enfermería 11 casos graves: sus cifras son inestables.\n"
            "- **Etnia y territorio fuera del modelo** por decisión ética (la ablación muestra que no lo mejoran).\n"
            "- **Datos sintéticos:** las métricas miden cuánto reproduce el sistema su propio etiquetado, no su desempeño clínico. "
            "El siguiente paso es validar con datos reales anonimizados de una ESE/IPS.\n"
            "- **Habeas Data (Ley 1581 de 2012):** documentos seudonimizados con HMAC-SHA256 y sal secreta; nombres y contactos se descartan.\n"
            "- **Pendiente con un asesor clínico:** FCF de 60 o glucosa de 300 solo dan Riesgo Medio; validar la proteinuria ++ como "
            "criterio único, los textos de protocolo y los cortes de las alertas 3280 marcados como «por validar».\n"
            "- **Ajustes frente a la Resolución 3280:** FCF registrada antes de que sea medible, glucosa sin indicar si es en ayunas, "
            "controles prenatales sin relación con la semana y control prenatal hecho por auxiliares o parteras: MATERNA es una "
            "herramienta de **tamizaje y canalización comunitaria**, no reemplaza el control prenatal.\n"
            "- **Responsabilidad:** prototipo académico. No usar para decisiones clínicas reales."
        )


# ---------------------------------------------------------------- lista de chequeo
def fase_chequeo():
    chequeo = tabla_chequeo()
    conteo = chequeo["Estado"].value_counts().reindex(list(ESTADOS), fill_value=0)
    st.markdown(
        f"Auditoría del repositorio contra las **12 fases** del ciclo de aprendizaje automático: **{len(ACTIVIDADES)} actividades**. "
        "**Hecho** quiere decir que hoy se puede ver o ejecutar en el aplicativo; **Parcial**, que existe una parte; "
        "**Falta**, que aún no existe y en qué etapa del plan se construye. La columna *Evidencia* dice en qué fase verlo."
    )
    for columna, estado in zip(st.columns(3), ESTADOS):
        columna.metric(estado, int(conteo[estado]))
    with lab.tarjeta("resumen", "Resumen por fase"):
        st.dataframe(resumen_chequeo(), hide_index=True, width="stretch")
    with lab.tarjeta("actividades", "Actividades y su evidencia"):
        filtro = st.segmented_control("Mostrar", ["Todas", *ESTADOS], default="Todas", key="chequeo_estado")
        visibles = chequeo if filtro in (None, "Todas") else chequeo[chequeo["Estado"] == filtro]
        st.dataframe(visibles, hide_index=True, width="stretch", height=560)
        st.download_button("Descargar la lista de chequeo (CSV)", chequeo.to_csv(index=False).encode("utf-8-sig"),
                           "materna_lista_de_chequeo.csv", "text/csv", icon=":material/download:")


# ---------------------------------------------------------------- la fase elegida en el menú lateral
FASES = {
    "01": fase_problema, "02": fase_datos, "03": fase_eda, "04": fase_limpieza, "05": fase_variables, "06": fase_division,
    "07": fase_algoritmo, "08": fase_entrenamiento, "09": fase_parametros, "10": fase_evaluacion, "11": fase_generalizacion,
    "12": fase_entrega, "etica": fase_etica, "chequeo": fase_chequeo,
}
vista = lab.vista()
etiquetas = {
    "02": [(f"Conjunto de trabajo: {miles(trabajo['n_trabajo'])}", "on")] if trabajo else ["Dataset base: 1.200 gestantes"],
    "10": [("Random Forest + reglas", "ok")],
    "12": [(f"La app usa el modelo {publicacion.publicado()['version']}", "ok")],
}
# En la fase 06 la semilla se lee del control (ya trae el valor nuevo); en las demás, de la partición guardada
semilla_visible = st.session_state.get("part_semilla", particion_elegida()["semilla"]) if vista == "06" else particion_elegida()["semilla"]
lab.encabezado(vista, usuario, [*etiquetas.get(vista, []), f"Semilla {semilla_visible}", ("Datos sintéticos", "warn")])
# Cada fase va en un contenedor propio: al cambiar de fase, Streamlit retira de inmediato lo de la anterior
with st.container(key=f"mt-fase-{vista}"):
    FASES[vista]()
lab.marcar_recorrida(vista)
lab.registro()
