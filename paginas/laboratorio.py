"""MATERNA — Módulo 1: Laboratorio de ML auditable (fases 01 a 11, entrega al Módulo 2 y ética).

Audiencia: docente y evaluadores. Cada pestaña muestra los datos y resultados reales del repositorio
(reports/, models/) y, en "Código que se ejecuta", la función exacta de src/ que los produce.
La fase 02 incluye la ingesta auditable de archivos de la IPS. La pestaña 12 documenta lo que el
Módulo 1 entrega al Módulo 2 (app Flutter, web y móvil): modelo, preprocesamiento y reglas en JSON.
Solo el administrador sube archivos propios y reentrena; el evaluador audita en modo lectura.
"""
import hashlib
import inspect
import json
import os
import secrets
import tempfile
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import streamlit as st

from src import graficos, ui_theme as ui
from src.autenticacion import ROLES, puede
from src.clinical_rules import evaluar_reglas, mascara_reglas
from src.config import CLASE_ALTO, DIR_METRICAS, DIR_MODELOS, NOMBRES_CLASES, VARS_CON_NULOS
from src.consolidado_ips import datos_consolidados, guardar_carga, resumen_consolidado
from src.data_preprocessing import (
    RANGOS_PLAUSIBLES, MedianaEstratificadaImputer, cargar_dataset, marcar_fuera_de_rango,
    particionar, pasos_preprocesamiento, separar_xy,
)
from src.entrenamiento_vivo import entrenar, mejores_hiperparametros
from src.evaluate import MATRIZ_COSTO, calcular_metricas, intervalo_bootstrap
from src.exportar_a_dart import DIR_ASSETS, RUTA_MODELO
from src.filtro_3280 import tabla_decisiones, variables_modelo
from src.generar_ejemplo_ips import DIR_EJEMPLOS, DIR_PLANTILLAS
from src.inspeccionar_ips import CENTINELAS, inspeccionar, reemplazar_centinelas
from src.seudonimizacion import LONGITUD_MINIMA_SAL, VARIABLE_SAL
from src.train_models import con_estrategias_balanceo, grid_random_forest

usuario = st.session_state.get("usuario")
ETIQUETAS = {"edad": "Edad (años)", "semanas_gestacion": "Semanas de gestación", "n_controles_prenatales": "Controles prenatales",
             "pas_mmhg": "PAS (mmHg)", "pad_mmhg": "PAD (mmHg)", "fcf_bpm": "FCF (lpm)", "glucosa_mgdl": "Glucosa (mg/dL)"}


def html(bloque):
    st.markdown(bloque, unsafe_allow_html=True)


def codigo(*objetos):
    with st.expander("Código que se ejecuta"):
        for objeto in objetos:
            st.code(inspect.getsource(objeto), language="python")


def grafico(chart):
    st.altair_chart(chart, width="stretch")


@st.cache_data
def dataset():
    return cargar_dataset()


@st.cache_data
def metricas(nombre):
    return pd.read_csv(DIR_METRICAS / nombre)


@st.cache_data
def particiones_resumen():
    X, y = separar_xy(marcar_fuera_de_rango(dataset()))
    X_train, X_val, X_test, y_train, y_val, y_test = particionar(X, y)
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
    st.markdown("#### Ingesta auditable de archivos de la IPS")
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
        st.caption("Su rol audita la ingesta con el ejemplo ficticio. Subir y guardar archivos reales de la IPS es del "
                   "administrador y del médico auditor.")
    if st.button("Ingerir el ejemplo ficticio (307 gestantes inventadas)", icon=":material/science:"):
        st.session_state["archivo_ips"] = ("ips_ficticio_3280.csv", (DIR_EJEMPLOS / "ips_ficticio_3280.csv").read_bytes())
    if "archivo_ips" not in st.session_state:
        return

    nombre, contenido = st.session_state["archivo_ips"]
    # Con el ejemplo ficticio basta una sal temporal si no hay una configurada: no se guarda nada
    sal_uso = sal or secrets.token_hex(16)
    with st.spinner("Ingiriendo…"), tempfile.TemporaryDirectory() as carpeta:
        # El archivo solo existe en una carpeta temporal mientras se procesa; luego se borra
        ruta = Path(carpeta) / Path(nombre).name
        ruta.write_bytes(contenido)
        try:
            datos, reporte = inspeccionar(ruta, sal_uso)
        except ValueError as error:
            st.error(str(error))
            return

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
        st.toast(f"Carga n.º {id_carga} guardada: {len(datos)} atenciones seudonimizadas.", icon=":material/check:", duration=3)
    cargas, gestantes = resumen_consolidado()
    if not cargas.empty:
        st.markdown(f"**Base del laboratorio:** {len(cargas)} carga(s) · {gestantes} gestante(s) distintas")
        st.dataframe(cargas, hide_index=True, width="stretch")


@st.cache_resource
def modelo_en_uso():
    return joblib.load(RUTA_MODELO)


@st.cache_data
def artefactos():
    filas = []
    for ruta in sorted(DIR_MODELOS.glob("*.joblib")) + sorted(DIR_ASSETS.glob("*.json")):
        filas.append({"Archivo": f"{ruta.parent.name}/{ruta.name}", "Tamaño (KB)": round(ruta.stat().st_size / 1024),
                      "SHA-256 (inicio)": hashlib.sha256(ruta.read_bytes()).hexdigest()[:16]})
    return pd.DataFrame(filas)


html(ui.cabecera("Módulo 1 · Laboratorio de aprendizaje automático auditable", "Laboratorio ML",
                 "Del problema y la ingesta de datos a la generalización: datos, resultados y código reales del repositorio.",
                 ["Semilla 42", "Datos sintéticos calibrados", ROLES.get(usuario["rol"], "Sin rol") if usuario else "Sin sesión"]))

pestanas = st.tabs(["01 Problema", "02 Recolección e ingesta", "03 EDA", "04 Limpieza", "05 Variables", "06 División",
                    "07 Algoritmo", "08 Entrenamiento", "09 Hiperparámetros", "10 Evaluación", "11 Generalización",
                    "12 Entrega al Módulo 2", "13 Ética y limitaciones"])
df = dataset()
test = metricas("metricas_test.csv").set_index("sistema")
principal = test.loc["Híbrido (Random Forest + reglas)"]

# ---------------------------------------------------------------- 01
with pestanas[0]:
    html(ui.titulo_seccion("01", "Definir el problema"))
    st.markdown(
        "**Clasificación supervisada multiclase**: a partir de datos que se toman en el control prenatal, asignar a cada "
        "gestante **Bajo, Medio o Alto Riesgo** obstétrico, en zonas dispersas de La Guajira y Cesar y sin depender de internet. "
        "Un motor de **reglas clínicas** (GPC Minsalud 2013) garantiza que ningún signo crítico dependa de la probabilidad del modelo."
    )
    st.dataframe(pd.DataFrame([
        ("F1-macro", "Métrica de selección del modelo: pesa igual las tres clases aunque estén desbalanceadas.", f"{principal['f1_macro']:.3f}"),
        ("Recall de Alto Riesgo", "Seguridad: de las gestantes graves, cuántas detecta. Un falso negativo puede costar una vida.", f"{principal['recall_alto']:.3f}"),
        ("Costo clínico", "Suma de errores ponderada por su gravedad (matriz definida por el equipo). Menos es mejor.", f"{int(principal['costo_clinico_total'])}"),
        ("ROC-AUC", "Capacidad de separar las clases, sin depender del umbral.", f"{principal['roc_auc_ovr_macro']:.3f}"),
    ], columns=["Métrica objetivo", "Por qué", "Sistema final en prueba"]), hide_index=True, width="stretch")
    st.markdown("**Matriz de costo clínico** (filas: clase real; columnas: clase predicha)")
    st.dataframe(pd.DataFrame(MATRIZ_COSTO, index=NOMBRES_CLASES, columns=NOMBRES_CLASES), width="content")

# ---------------------------------------------------------------- 02
with pestanas[1]:
    html(ui.titulo_seccion("02", "Recolección e ingesta de datos"))
    c1, c2 = st.columns([3, 2], gap="large")
    with c1:
        n_gestantes = f"{len(df):,}".replace(",", ".")
        st.markdown(f"**Dataset sintético calibrado:** {n_gestantes} gestantes y {df.shape[1]} columnas, 65 % La Guajira y 35 % Cesar. "
                    "Calibrado con cifras del DANE (Estadísticas Vitales Wayúu 2015–2024), el INS y el ONS. "
                    "**No son pacientes reales**: las métricas no son evidencia clínica.")
        grafico(graficos.barras_clases(df))
    with c2:
        for col, titulo in [("departamento", "Departamento"), ("pertenencia_etnica", "Pertenencia étnica")]:
            st.dataframe(df[col].value_counts().rename_axis(titulo).reset_index(name="Gestantes"), hide_index=True, width="stretch")
    st.caption("Los archivos de la Resolución 4505 recibidos correspondían a recién nacidos, sin variables maternas: "
               "no son aptos para el modelo y, por tener datos personales reales, no se cargan en el laboratorio.")
    seccion_ingesta()

# ---------------------------------------------------------------- 03
with pestanas[2]:
    html(ui.titulo_seccion("03", "Análisis exploratorio (EDA)"))
    c1, c2 = st.columns([2, 3], gap="large")
    with c1:
        st.markdown("**Datos faltantes**")
        nulos = (df.isna().mean() * 100).round(2)
        nulos = nulos[nulos > 0].sort_values(ascending=False)
        grafico(graficos.barras_nulos({ETIQUETAS.get(k, k): v for k, v in nulos.items()}))
        st.caption("Glucosa y FCF faltan cuando no hay glucómetro o doppler fetal. Los nulos **no** se concentran en el área rural.")
    with c2:
        st.markdown("**Presión sistólica vs diastólica por clase**")
        grafico(graficos.dispersion_presion(df))
        st.caption("Las líneas punteadas marcan 140/90 (hipertensión) y 160/110 (hipertensión severa, regla clínica).")
    st.markdown("**Comparación: dataset sintético vs archivo de la IPS**")
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

# ---------------------------------------------------------------- 04
with pestanas[3]:
    html(ui.titulo_seccion("04", "Limpieza"))
    st.markdown(
        "1. **Estructura:** se elimina la columna vacía `Unnamed: 16` y `convulsiones` pasa de TRUE/FALSE a 1/0.\n"
        f"2. **Valores centinela** de los sistemas de información → nulo: `{'`, `'.join(sorted(CENTINELAS))}`.\n"
        "3. **Filtro 3280:** cada columna se conserva, se seudonimiza o se elimina según el catálogo (página *Variables 3280*).\n"
        "4. **Rangos fisiológicos:** un valor imposible es un error de captura y se vuelve nulo.\n"
        "5. **Imputación estratificada** de glucosa y FCF: mediana por área × trimestre, aprendida solo con el entrenamiento."
    )
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("**Rangos fisiológicos plausibles**")
        st.dataframe(pd.DataFrame([(ETIQUETAS.get(k, k), lo, hi) for k, (lo, hi) in RANGOS_PLAUSIBLES.items()],
                                  columns=["Variable", "Mínimo", "Máximo"]), hide_index=True, width="stretch")
    with c2:
        st.markdown("**Decisiones del filtro 3280**")
        st.dataframe(tabla_decisiones()["Decisión"].value_counts().rename_axis("Decisión").reset_index(name="Variables"),
                     hide_index=True, width="stretch")
    imp = modelo_en_uso().named_steps["imputacion"]
    st.markdown("**Medianas aprendidas por el imputador del modelo en uso** (si un estrato tiene menos de 10 datos se usa la del área)")
    filas = []
    for col in imp.columnas:
        for (area, tri), valor in sorted(imp.mediana_estrato_[col].items()):
            filas.append({"Variable": ETIQUETAS[col], "Área": area, "Trimestre": tri, "Mediana": valor})
        filas.append({"Variable": ETIQUETAS[col], "Área": "Global (respaldo)", "Trimestre": "—", "Mediana": imp.mediana_global_[col]})
    st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
    codigo(marcar_fuera_de_rango, reemplazar_centinelas, MedianaEstratificadaImputer.transform)

# ---------------------------------------------------------------- 05
with pestanas[4]:
    html(ui.titulo_seccion("05", "Ingeniería de variables"))
    pre = json.loads((DIR_ASSETS / "preproceso.json").read_text(encoding="utf-8"))
    tipo = {**{c: "Continua · RobustScaler" for c in pre["escalado"]["columnas"]},
            **{c: "Discreta · sin escalar" for c in pre["discretas"]},
            **{c: "Indicador de dato faltante" for c in pre["indicadores"]}}
    st.markdown(f"Entran al modelo **{len(pre['variables_entrada'])} variables** construidas a partir de "
                f"**{len(variables_modelo())} datos** de la gestante. Etnia, municipio y departamento **no entran**.")
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.dataframe(pd.DataFrame([{"N.º": i + 1, "Variable de entrada": v, "Tipo": tipo.get(v, "One-Hot")}
                                   for i, v in enumerate(pre["variables_entrada"])]), hide_index=True, width="stretch", height=420)
    with c2:
        st.markdown("**RobustScaler**: (x − mediana) / rango intercuartílico, robusto a valores extremos")
        st.dataframe(pd.DataFrame({"Variable": [ETIQUETAS[c] for c in pre["escalado"]["columnas"]],
                                   "Centro (mediana)": pre["escalado"]["centro"], "Escala (RIC)": pre["escalado"]["escala"]}),
                     hide_index=True, width="stretch")
        st.markdown("**Ablación: ¿mejoran las variables demográficas?**")
        st.dataframe(metricas("ablacion_variables_demograficas.csv"), hide_index=True, width="stretch")
        st.caption("Agregar etnia y territorio no mejora el modelo: quedan fuera por ética y solo sirven para auditar sesgos.")
    codigo(pasos_preprocesamiento)

# ---------------------------------------------------------------- 06
with pestanas[5]:
    html(ui.titulo_seccion("06", "División de los datos"))
    tabla, disjuntos = particiones_resumen()
    st.dataframe(tabla, hide_index=True, width="stretch")
    st.markdown(
        f"- Partición **70/15/15 estratificada** por clase, con semilla 42: la proporción de Alto Riesgo es la misma en los tres conjuntos.\n"
        f"- Conjuntos disjuntos (ninguna gestante se repite): **{'sí' if disjuntos else 'NO'}**.\n"
        "- **Sin fuga de datos:** imputador, escalador y One-Hot se ajustan solo con el entrenamiento, y SMOTE se aplica "
        "**dentro** de cada partición de la validación cruzada, nunca antes.\n"
        "- El conjunto de **prueba se usó una sola vez**, al final: el modelo se eligió con validación."
    )
    codigo(particionar)

# ---------------------------------------------------------------- 07
with pestanas[6]:
    html(ui.titulo_seccion("07", "Selección del algoritmo"))
    st.markdown("**Validación cruzada (5 particiones) del mejor ajuste de cada modelo y estrategia de balanceo**")
    comp = metricas("comparacion_cv_por_estrategia.csv")
    st.dataframe(comp[["modelo", "balanceo", "hiperparametros", "cv_f1_macro_media", "cv_f1_macro_std", "cv_recall_alto_media"]]
                 .rename(columns={"modelo": "Modelo", "balanceo": "Balanceo", "hiperparametros": "Hiperparámetros",
                                  "cv_f1_macro_media": "F1-macro", "cv_f1_macro_std": "± desv.", "cv_recall_alto_media": "Recall Alto"}),
                 hide_index=True, width="stretch")
    st.markdown("**Selección del sistema híbrido en el conjunto de validación**")
    val = metricas("metricas_validacion.csv")
    st.dataframe(val[["sistema", "f1_macro", "recall_alto", "costo_clinico_total", "roc_auc_ovr_macro"]], hide_index=True, width="stretch")
    st.info("**Por qué Random Forest y no la SVM de la Fase 1:** además de su mejor F1-macro, las pruebas de coherencia clínica "
            "cambian una sola variable de una gestante sana (presión 145/95, glucosa 145, FCF 165, edad 36 o cero controles). "
            "La SVM respondía Bajo Riesgo en esos casos; el Random Forest los clasifica al menos como Medio.")
    codigo(con_estrategias_balanceo)

# ---------------------------------------------------------------- 08
with pestanas[7]:
    html(ui.titulo_seccion("08", "Entrenamiento en vivo"))
    st.markdown("Reentrena el Random Forest con los **mejores hiperparámetros** de la búsqueda, sin repetirla. "
                "Muestra cada partición de la validación cruzada al terminar y compara con el modelo en uso. "
                "**No reemplaza el modelo en uso.**")
    st.json(mejores_hiperparametros(), expanded=True)
    permitido = puede(usuario, "entrenar")
    if st.button("Entrenar en vivo", type="primary", icon=":material/play_arrow:", disabled=not permitido):
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

        st.session_state["entrenamiento"] = entrenar(al_avanzar)
        progreso.empty()
        zona.empty()  # el resultado final se dibuja abajo
    if not permitido:
        st.caption("Solo el rol administrador puede reentrenar. Este laboratorio está en modo lectura para su rol.")
    resultado = st.session_state.get("entrenamiento")
    if resultado:
        st.success(f"Listo en {resultado['segundos']:.1f} s · F1-macro en validación cruzada {resultado['cv_f1_media']:.4f}")
        grafico(graficos.f1_por_particion(resultado["cv_f1_por_particion"]))
        st.dataframe(pd.DataFrame([{"Conjunto": c, "Modelo": s, "F1-macro": m["f1_macro"], "Recall Alto": m["recall_alto"],
                                    "ROC-AUC": m["roc_auc_ovr_macro"], "Costo clínico": m["costo_clinico_total"]}
                                   for (c, s), m in resultado["metricas"].items()]).round(4), hide_index=True, width="stretch")
        if resultado["identico_al_modelo_en_uso"]:
            st.info("**Reproducible:** con la misma semilla, el modelo reentrenado da probabilidades idénticas al modelo en uso.")
    codigo(entrenar)

# ---------------------------------------------------------------- 09
with pestanas[8]:
    html(ui.titulo_seccion("09", "Ajuste de hiperparámetros"))
    exp = metricas("experimentos_cv_completo.csv")
    por_modelo = exp.groupby("modelo").size()
    st.markdown(f"**GridSearchCV:** {len(exp)} configuraciones × 5 particiones = **{len(exp) * 5} entrenamientos**. "
                f"SMOTE y `class_weight` se comparan como un hiperparámetro más, nunca combinados. "
                + " · ".join(f"{m}: {n}" for m, n in por_modelo.items()))
    grafico(graficos.dispersion_hiperparametros(exp))
    modelo = st.selectbox("Mejores configuraciones de", list(por_modelo.index), index=list(por_modelo.index).index("Random Forest"))
    st.dataframe(exp[exp["modelo"] == modelo].sort_values("cv_f1_macro_media", ascending=False)
                 [["balanceo", "hiperparametros", "cv_f1_macro_media", "cv_f1_macro_std", "cv_recall_alto_media", "tiempo_ajuste_s"]].head(10),
                 hide_index=True, width="stretch")
    codigo(grid_random_forest)

# ---------------------------------------------------------------- 10
with pestanas[9]:
    html(ui.titulo_seccion("10", "Evaluación en el conjunto de prueba"))
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
    codigo(calcular_metricas, intervalo_bootstrap)

# ---------------------------------------------------------------- 11
with pestanas[10]:
    html(ui.titulo_seccion("11", "Generalización: sobreajuste y subajuste"))
    curvas, brecha = metricas("curvas_aprendizaje.csv"), metricas("brecha_sobreajuste.csv")
    columnas = st.columns(3, gap="medium")
    for col, modelo in zip(columnas, ["Regresión Logística", "SVM", "Random Forest"]):
        with col:
            st.markdown(f"**{modelo}**")
            grafico(graficos.curva_aprendizaje(curvas, modelo))
    st.dataframe(brecha.rename(columns={"modelo": "Modelo", "f1_entrenamiento": "F1 entrenamiento", "f1_cv": "F1 validación cruzada",
                                        "f1_cv_std": "± desv.", "brecha": "Brecha"}), hide_index=True, width="stretch")
    st.markdown(
        "- **Regresión Logística: subajusta.** Entrenamiento y validación quedan bajos y juntos: el modelo es demasiado simple.\n"
        "- **SVM: sobreajusta.** Memoriza el entrenamiento (1,000) pero valida en 0,861: la brecha es la mayor.\n"
        "- **Random Forest: ajusta bien.** También llega a 1,000 en entrenamiento, algo normal en un bosque, pero valida en 0,932 "
        "y se sostiene en validación (0,944) y prueba (0,943). Más datos reales seguirían ayudando: la curva aún sube."
    )
    st.caption("Calculado con `python -m src.curvas_aprendizaje` (validación cruzada de 5 particiones sobre 840 gestantes).")

# ---------------------------------------------------------------- 12
with pestanas[11]:
    html(ui.titulo_seccion("12", "Entrega al Módulo 2 (despliegue)"))
    modelo_json = json.loads((DIR_ASSETS / "modelo_rf.json").read_text(encoding="utf-8"))
    vigente = modelo_json["sha256_joblib"] == hashlib.sha256(RUTA_MODELO.read_bytes()).hexdigest()
    st.markdown(
        "El despliegue es el **Módulo 2**: la app de usuario final (Flutter, **web y móvil**) para el personal de salud en "
        "territorio, con captura manual, carga masiva de archivos de la IPS y semáforo de riesgo. Los dos módulos son "
        "independientes y se integran **solo** a través de estos artefactos, que el Módulo 1 entrega ya validados:\n\n"
        f"- `flutter_app/assets/modelo_rf.json`: Random Forest **versión {modelo_json['version']}** ({modelo_json['n_arboles']} árboles), "
        "con la huella SHA-256 del `.joblib` del que salió.\n"
        "- `preproceso.json` y `reglas.json`: imputación, escalado, One-Hot y los 4 signos críticos.\n"
        "- `casos_paridad.json`: 200 casos con la respuesta exacta de scikit-learn, que la app debe reproducir.\n\n"
        f"Estado de la entrega: **{'vigente' if vigente else 'ANTIGUA: vuelva a exportar con python -m src.exportar_a_dart'}** "
        "respecto del modelo en uso. La inferencia desde JSON reproduce a scikit-learn con diferencia 0 en las 1.200 gestantes."
    )
    st.dataframe(artefactos(), hide_index=True, width="stretch")
    st.markdown("**Motor de reglas clínicas: sensibilidad en signos críticos**")
    X, y = separar_xy(marcar_fuera_de_rango(df))
    mascara = mascara_reglas(X)
    _, _, X_test, _, _, y_test = particionar(X, y)
    mascara_test = mascara_reglas(X_test)
    c = st.columns(2)
    c[0].metric("Prueba: signos críticos detectados como Alto", f"{int((y_test[mascara_test] == CLASE_ALTO).sum())}/{int(mascara_test.sum())}")
    c[1].metric("Dataset completo", f"{int((y[mascara] == CLASE_ALTO).sum())}/{int(mascara.sum())}")
    st.caption("100 % de sensibilidad en los casos con signo crítico. Aviso: las etiquetas sintéticas se generaron con estos mismos "
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

# ---------------------------------------------------------------- 13
with pestanas[12]:
    html(ui.titulo_seccion("13", "Ética y limitaciones"))
    aud = metricas("auditoria_subgrupos.csv")
    st.markdown("**Auditoría de sesgos:** recall de Alto Riesgo por subgrupo, con predicciones fuera de partición sobre las 1.200 gestantes.")
    variable = st.radio("Subgrupo", ["area_residencia", "pertenencia_etnica", "atendido_por", "departamento"], horizontal=True,
                        format_func={"area_residencia": "Área", "pertenencia_etnica": "Etnia", "atendido_por": "Quién atiende",
                                     "departamento": "Departamento"}.get)
    st.dataframe(aud[aud["variable"] == variable][["grupo", "n", "n_alto_real", "recall_alto", "f1_macro"]]
                 .rename(columns={"grupo": "Grupo", "n": "Gestantes", "n_alto_real": "Alto Riesgo reales",
                                  "recall_alto": "Recall Alto", "f1_macro": "F1-macro"}), hide_index=True, width="stretch")
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
