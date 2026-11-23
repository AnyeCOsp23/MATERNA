"""Fase 3 — Exporta el sistema híbrido (Random Forest + reglas) a JSON para la app Flutter.

Genera en flutter_app/assets/:
  preproceso.json      medianas de imputación, centro/escala del RobustScaler y categorías del One-Hot
  modelo_rf.json       los 300 árboles (variable, umbral, hijos y probabilidades de las hojas)
  reglas.json          los 4 signos críticos, las clases y los protocolos orientativos (con título y etiqueta por paso)
  casos_paridad.json   200 gestantes con la respuesta exacta de scikit-learn, para la prueba en Dart
  variables_3280.json  copia exacta del catálogo config/variables_3280.json (formulario y alertas de la ruta)
  casos_alertas.json   gestantes con las alertas de la ruta y los signos de alarma que elevan el triaje a Alto,
                       según Python, para la prueba en Dart
  casos_carga.json     la carga masiva del ejemplo ficticio de la IPS (reporte, triaje ordenado de cada fila y
                       seudónimos) según src/carga_masiva.py, con una sal SOLO de prueba, para la prueba en Dart

Antes de escribir, verifica con src/inferencia_json.py (Python puro, sin scikit-learn) que los JSON
reproducen las probabilidades del pipeline. Carga el modelo .joblib existente: no reentrena.

Por defecto exporta el modelo oficial de la Fase 2 (v1). «Publicar al Módulo 2» (src/publicacion.py) llama
a exportar() con otra versión del Random Forest y su número de versión.

Uso:  python -m src.exportar_a_dart                 (todo)
      python -m src.exportar_a_dart --solo-catalogo  (solo catálogo y casos de alertas: no toca el modelo)
      python -m src.exportar_a_dart --solo-carga     (solo casos_carga.json: no toca el modelo)
"""
import datetime as dt
import os
import shutil
import sys
import hashlib
import json

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn

from src.clinical_rules import (
    PROTOCOLO, PROTOCOLO_TITULOS, UMBRAL_PAD_SEVERA, UMBRAL_PAS_SEVERA, UMBRAL_PROTEINURIA, evaluar_riesgo_hibrido,
)
from src.config import CLASE_ALTO, DIR_MODELOS, NOMBRES_CLASES, RAIZ, SEMILLA, VARS_CON_NULOS
from src.data_preprocessing import preparar_datos
from src.filtro_3280 import RUTA_CATALOGO, evaluar_alertas_3280, signos_alarma_que_escalan, variables
from src.carga_masiva import evaluar_archivo
from src.generar_ejemplo_ips import DIR_EJEMPLOS
from src.inferencia_json import ClasificadorJSON
from src.seudonimizacion import seudonimizar

RUTA_MODELO = DIR_MODELOS / "modelo_random_forest.joblib"
DIR_ASSETS = RAIZ / "flutter_app" / "assets"
VARIABLE_ASSETS = "MATERNA_ASSETS"  # otra carpeta de destino (la usan las pruebas)
TOLERANCIA = 1e-6
N_CASOS = 200
N_CASOS_ALERTAS = 160
VERSION_MODELO = "v1"
# Sal pública, SOLO para las pruebas de paridad: la de la IPS es secreta y nunca se exporta
SAL_PRUEBA = "sal-solo-para-pruebas-0123456789"
EJEMPLO_IPS = DIR_EJEMPLOS / "ips_ficticio_3280.csv"


def dir_assets():
    """Carpeta de los JSON que consume la app: flutter_app/assets, salvo que MATERNA_ASSETS indique otra."""
    return Path(os.environ.get(VARIABLE_ASSETS) or DIR_ASSETS)


def _sha256(ruta):
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def exportar_preproceso(pipeline):
    imp = pipeline.named_steps["imputacion"]
    ct = pipeline.named_steps["transformacion"]
    columnas = {nombre: list(cols) for nombre, _, cols in ct.transformers_ if nombre != "remainder"}
    escalador = ct.named_transformers_["continuas"]
    one_hot = ct.named_transformers_["categoricas"]
    estrato = {}
    for col in imp.columnas:
        estrato[col] = {}
        for (area, tri), valor in imp.mediana_estrato_[col].items():
            estrato[col].setdefault(area, {})[tri] = float(valor)
    return {
        "variables_entrada": list(ct.get_feature_names_out()),
        "obligatorias": [c for c in columnas["continuas"] + ["proteinuria", "convulsiones"] + columnas["categoricas"]
                         if c not in VARS_CON_NULOS],
        "imputacion": {
            "columnas": list(imp.columnas),
            "estrato": ["area_residencia", "trimestre"],
            # pd.cut(semanas, [0, 13, 27, 45]) con intervalos cerrados a la derecha
            "trimestres": [{"nombre": "T1", "desde_exclusivo": 0, "hasta": 13},
                           {"nombre": "T2", "desde_exclusivo": 13, "hasta": 27},
                           {"nombre": "T3", "desde_exclusivo": 27, "hasta": 45}],
            "mediana_estrato": estrato,
            "mediana_area": {c: {a: float(v) for a, v in imp.mediana_area_[c].items()} for c in imp.columnas},
            "mediana_global": {c: float(imp.mediana_global_[c]) for c in imp.columnas},
        },
        "escalado": {"metodo": "RobustScaler: (x - centro) / escala", "columnas": columnas["continuas"],
                     "centro": [float(v) for v in escalador.center_], "escala": [float(v) for v in escalador.scale_]},
        "discretas": columnas["discretas"],
        "indicadores": {imp.NOMBRES_INDICADOR[c]: c for c in imp.columnas},
        "one_hot": [{"columna": col, "categorias": [str(c) for c in cats]}
                    for col, cats in zip(columnas["categoricas"], one_hot.categories_)],
    }


def exportar_arbol(estimador):
    t = estimador.tree_
    variable, umbral, izquierda, derecha, hojas = [], [], [], [], []
    for nodo in range(t.node_count):
        if t.children_left[nodo] == -1:
            valor = t.value[nodo, 0, :]
            hojas.append([float(v) for v in valor / valor.sum()])
            # En una hoja, 'izquierda' guarda el índice de su vector de probabilidades
            variable.append(-1), umbral.append(0.0), izquierda.append(len(hojas) - 1), derecha.append(-1)
        else:
            variable.append(int(t.feature[nodo])), umbral.append(float(t.threshold[nodo]))
            izquierda.append(int(t.children_left[nodo])), derecha.append(int(t.children_right[nodo]))
    return {"variable": variable, "umbral": umbral, "izquierda": izquierda, "derecha": derecha, "hojas": hojas}


def exportar_modelo(pipeline, version=VERSION_MODELO, ruta=RUTA_MODELO, exportado=None):
    rf = pipeline.named_steps["modelo"]
    if not hasattr(rf, "estimators_"):
        raise ValueError("Solo se exporta un Random Forest: la app solo tiene motor de árboles.")
    return {
        "version": version,
        "tipo": "RandomForestClassifier",
        "origen": Path(ruta).name,
        "sha256_joblib": _sha256(Path(ruta)),
        "scikit_learn": sklearn.__version__,
        "exportado": exportado or dt.date.today().isoformat(),
        "clases": NOMBRES_CLASES,
        "n_arboles": len(rf.estimators_),
        "n_variables": int(rf.n_features_in_),
        "comparacion": "float32(x) <= umbral -> izquierda",
        "arboles": [exportar_arbol(e) for e in rf.estimators_],
    }


def exportar_reglas():
    return {
        "descripcion": "Signos críticos (GPC Minsalud 2013): si se cumple cualquiera, el resultado es Alto Riesgo.",
        "clase_alto": CLASE_ALTO,
        "clases": NOMBRES_CLASES,
        "reglas": [
            {"id": "pas_severa", "variable": "pas_mmhg", "condicion": "mayor_igual", "umbral": UMBRAL_PAS_SEVERA,
             "mensaje": "Hipertensión severa: PAS ≥ 160 mmHg"},
            {"id": "pad_severa", "variable": "pad_mmhg", "condicion": "mayor_igual", "umbral": UMBRAL_PAD_SEVERA,
             "mensaje": "Hipertensión severa: PAD ≥ 110 mmHg"},
            {"id": "convulsiones", "variable": "convulsiones", "condicion": "verdadero",
             "mensaje": "Convulsiones: sospecha de eclampsia"},
            {"id": "proteinuria", "variable": "proteinuria", "condicion": "mayor_igual", "umbral": UMBRAL_PROTEINURIA,
             "mensaje": "Proteinuria ≥ ++ en tira reactiva"},
        ],
        "protocolo": PROTOCOLO,
        "protocolo_titulos": {c: [{"titulo": t, "etiqueta": e} for t, e in pasos]
                              for c, pasos in PROTOCOLO_TITULOS.items()},
        "aviso": "Protocolos orientativos para la demostración académica; deben validarse con un asesor clínico.",
    }


# ------------------------------------------------------------------ casos de paridad
def _casos_borde(base):
    """Casos que ejercitan cada rama: imputación por estrato/área/global, umbrales y categorías raras."""
    casos = []
    for semanas, area in [(10, "Rural disperso"), (10, "Cabecera"), (20, "Cabecera"), (35, "Rural disperso"), (43, "Cabecera")]:
        casos.append({**base, "semanas_gestacion": semanas, "area_residencia": area, "glucosa_mgdl": None, "fcf_bpm": None})
    for pas in (159, 160):
        casos.append({**base, "pas_mmhg": pas})
    for pad in (109, 110):
        casos.append({**base, "pad_mmhg": pad})
    for prot in (1, 2):
        casos.append({**base, "proteinuria": prot})
    casos.append({**base, "convulsiones": 1})
    casos.append({**base, "atendido_por": "Promotora"})  # categoría desconocida: One-Hot en ceros
    for cambio in [{"pas_mmhg": 145, "pad_mmhg": 95}, {"glucosa_mgdl": 145.0}, {"fcf_bpm": 165.0}, {"edad": 36},
                   {"n_controles_prenatales": 0}, {"edad": 15}, {"n_controles_prenatales": 20}]:
        casos.append({**base, **cambio})
    return casos


def generar_casos(pipeline, n=N_CASOS, semilla=SEMILLA):
    _, X_val, X_test, _, _, _ = preparar_datos(guardar=False)
    rng = np.random.default_rng(semilla)
    base = {"edad": 27, "area_residencia": "Cabecera", "semanas_gestacion": 28, "n_controles_prenatales": 5,
            "atendido_por": "Medico", "pas_mmhg": 110, "pad_mmhg": 70, "fcf_bpm": 142.0, "glucosa_mgdl": 88.0,
            "proteinuria": 0, "convulsiones": 0,
            # El pipeline las recibe pero no las usa (decisión ética); la paridad confirma que no influyen
            "departamento": "Cesar", "municipio": "Valledupar", "pertenencia_etnica": "Mestiza"}
    borde = _casos_borde(base)
    reales = pd.concat([X_test, X_val]).sample(n - len(borde), random_state=semilla)
    columnas = list(base)
    registros = []
    for _, fila in reales.iterrows():
        r = {c: (None if pd.isna(fila[c]) else fila[c].item() if hasattr(fila[c], "item") else fila[c]) for c in columnas}
        if rng.random() < 0.15:  # más faltantes que en el dataset, para ejercitar la imputación
            r[rng.choice(VARS_CON_NULOS)] = None
        registros.append(r)
    registros += borde

    casos = []
    for i, r in enumerate(registros):
        fila = pd.DataFrame([{k: (np.nan if v is None else v) for k, v in r.items()}])
        res = evaluar_riesgo_hibrido(r, pipeline)
        x = pipeline[:2].transform(fila)[0]
        casos.append({
            "id": i + 1,
            "entrada": r,
            "variables_entrada": [float(v) for v in x],
            "probabilidades": [float(p) for p in pipeline.predict_proba(fila)[0]],
            "clase_modelo": NOMBRES_CLASES.index(res.categoria_modelo),
            "clase": res.clase,
            "origen": res.origen,
            "n_signos_criticos": len(res.alertas),
        })
    return casos


def verificar(preproceso, modelo, reglas, casos):
    """Diferencia máxima entre la inferencia desde JSON y scikit-learn; falla si hay discrepancias."""
    clf = ClasificadorJSON(preproceso, modelo, reglas)
    max_dif_x = max_dif_p = 0.0
    for c in casos:
        x = clf.vector(c["entrada"])
        res = clf.evaluar(c["entrada"])
        max_dif_x = max(max_dif_x, max(abs(a - b) for a, b in zip(x, c["variables_entrada"])))
        max_dif_p = max(max_dif_p, max(abs(a - b) for a, b in zip(res["probabilidades"], c["probabilidades"])))
        iguales = (res["clase_modelo"], res["clase"], res["origen"], len(res["reglas_activadas"])) == \
                  (c["clase_modelo"], c["clase"], c["origen"], c["n_signos_criticos"])
        if not iguales:
            raise AssertionError(f"Caso {c['id']}: la inferencia desde JSON no coincide con scikit-learn")
    if max(max_dif_x, max_dif_p) > TOLERANCIA:
        raise AssertionError(f"Diferencia mayor que {TOLERANCIA}: variables {max_dif_x:.2e}, probabilidades {max_dif_p:.2e}")
    return max_dif_x, max_dif_p


# ------------------------------------------------------------------ catálogo 3280 y alertas de la ruta
def _casos_borde_alertas():
    """Cortes exactos de cada alerta y los casos que no deben alertar (dato faltante, semana previa)."""
    casos = [{}, {"semanas_gestacion": None, "calcio": 0}, {"semanas_gestacion": 13, "calcio": 0},
             {"semanas_gestacion": 14, "calcio": 0}, {"semanas_gestacion": 14, "calcio": 1},
             {"semanas_gestacion": 14, "calcio": None}, {"semanas_gestacion": 26, "vacuna_tdap": 0, "vacuna_influenza": 0},
             {"semanas_gestacion": 25, "vacuna_tdap": 0}, {"cefalea": 1, "hemoglobina_gdl": 9.0, "semanas_gestacion": 30, "calcio": 0}]
    for v in variables("capturar_alertar"):
        alerta = v.get("alerta")
        if alerta and alerta["condicion"] in ("menor_que", "mayor_igual"):
            u = alerta["umbral"]
            casos += [{v["nombre"]: u}, {v["nombre"]: u - 0.01}, {v["nombre"]: u + 0.01}, {v["nombre"]: None}]
        elif alerta and alerta["condicion"] == "verdadero":
            casos += [{v["nombre"]: 1}, {v["nombre"]: 0}]
    return casos


def generar_casos_alertas(n=N_CASOS_ALERTAS, semilla=SEMILLA):
    """Registros aleatorios (con datos faltantes) más los casos borde, con las alertas que calcula Python."""
    rng = np.random.default_rng(semilla)
    con_alerta = [v for v in variables("capturar_alertar") if "alerta" in v]
    registros = _casos_borde_alertas()
    while len(registros) < n:
        r = {"semanas_gestacion": None if rng.random() < .1 else int(rng.integers(4, 43))}
        for v in con_alerta:
            sorteo = rng.random()
            if sorteo < .35:
                continue  # la variable no se registró
            if sorteo < .5:
                r[v["nombre"]] = None  # se registró «sin dato»
            elif v["tipo"] == "binaria":
                r[v["nombre"]] = int(rng.integers(0, 2))
            else:
                u = v["alerta"]["umbral"]
                r[v["nombre"]] = round(float(u + rng.choice([-2, -.5, 0, .5, 2]) * max(1.0, u * .05)), 2)
        registros.append(r)
    return [{"id": i + 1, "entrada": r, "alertas": evaluar_alertas_3280(r), "escalan": signos_alarma_que_escalan(r)}
            for i, r in enumerate(registros)]


def exportar_catalogo_y_alertas():
    dir_assets().mkdir(parents=True, exist_ok=True)
    destino = dir_assets() / "variables_3280.json"
    shutil.copyfile(RUTA_CATALOGO, destino)  # copia byte a byte: una sola fuente de verdad
    casos = generar_casos_alertas()
    return [destino, _escribir("casos_alertas.json", {"casos": casos})]


# ------------------------------------------------------------------ carga masiva y seudonimización
DOCUMENTOS_PRUEBA = [("CC", "1065432"), (" cc ", "1.065.432"), ("CC", "1065-432 "), ("TI", "1065432"), ("", "1065432"),
                     ("CE", "ab-12.34"), ("RC", "  99 88 77"), ("CC", "1999999999"), ("pa", "x9"), ("CC", "ñandú 1")]


def generar_casos_carga(pipeline):
    """Lo que calcula src/carga_masiva.py con el ejemplo ficticio, más seudónimos de documentos escritos de varias formas."""
    reporte, resultados, rechazadas = evaluar_archivo(EJEMPLO_IPS, SAL_PRUEBA, pipeline)
    return {
        "sal_prueba": SAL_PRUEBA,
        "archivo": EJEMPLO_IPS.relative_to(RAIZ).as_posix(),
        "tolerancia": TOLERANCIA,
        "reporte": {
            "formato": reporte.formato, "separador": reporte.separador, "filas_leidas": reporte.filas_leidas,
            "columnas_por_decision": reporte.columnas_por_decision, "columnas_eliminadas": reporte.columnas_eliminadas,
            "columnas_desconocidas": reporte.columnas_desconocidas, "centinelas": reporte.centinelas,
            "fuera_de_rango": reporte.fuera_de_rango, "filas_duplicadas_eliminadas": reporte.filas_duplicadas_eliminadas,
            "gestantes_unicas": reporte.gestantes_unicas,
            "gestantes_con_varias_atenciones": reporte.gestantes_con_varias_atenciones,
            "sin_documento": reporte.sin_documento, "aptas_modelo": reporte.aptas_modelo,
            "faltantes_que_impiden_modelo": reporte.faltantes_que_impiden_modelo,
        },
        "resultados": resultados,
        "rechazadas": rechazadas,
        "seudonimos": [{"tipo": t, "numero": n, "id_seudonimo": seudonimizar(t, n, SAL_PRUEBA)} for t, n in DOCUMENTOS_PRUEBA],
    }


def exportar_casos_carga(pipeline=None):
    pipeline = pipeline if pipeline is not None else joblib.load(RUTA_MODELO)
    dir_assets().mkdir(parents=True, exist_ok=True)
    return _escribir("casos_carga.json", generar_casos_carga(pipeline))


def _escribir(nombre, datos, compacto=False):
    ruta = dir_assets() / nombre
    with open(ruta, "w", encoding="utf-8") as f:
        if compacto:
            json.dump(datos, f, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(datos, f, ensure_ascii=False, indent=1)
    return ruta


def exportar(ruta_modelo=RUTA_MODELO, version=VERSION_MODELO, exportado=None):
    """Exporta el modelo de `ruta_modelo` con el número de versión dado. Primero comprueba la paridad en Python
    (si falla, lanza AssertionError y no escribe nada). Devuelve la versión, la huella, la paridad y los archivos."""
    pipeline = joblib.load(ruta_modelo)
    preproceso, reglas = exportar_preproceso(pipeline), exportar_reglas()
    modelo = exportar_modelo(pipeline, version, ruta_modelo, exportado)
    casos = generar_casos(pipeline)
    dif_x, dif_p = verificar(preproceso, modelo, reglas, casos)
    dir_assets().mkdir(parents=True, exist_ok=True)
    rutas = [_escribir("preproceso.json", preproceso), _escribir("modelo_rf.json", modelo, compacto=True),
             _escribir("reglas.json", reglas), _escribir("casos_paridad.json", {"tolerancia": TOLERANCIA, "casos": casos})]
    rutas += exportar_catalogo_y_alertas()
    rutas.append(exportar_casos_carga(pipeline))
    return {"version": version, "sha256": modelo["sha256_joblib"], "n_arboles": modelo["n_arboles"],
            "casos_paridad": len(casos), "dif_variables": dif_x, "dif_probabilidades": dif_p,
            "archivos": [{"Archivo": r.name, "Tamaño (KB)": round(r.stat().st_size / 1024)} for r in rutas]}


if __name__ == "__main__":
    if "--solo-carga" in sys.argv:
        ruta = exportar_casos_carga()
        print(f"  {ruta.relative_to(RAIZ)}  {ruta.stat().st_size / 1024:,.0f} KB")
    elif "--solo-catalogo" in sys.argv:
        for ruta in exportar_catalogo_y_alertas():
            print(f"  {ruta.relative_to(RAIZ)}  {ruta.stat().st_size / 1024:,.0f} KB")
    else:
        info = exportar()
        print(f"Paridad JSON vs scikit-learn en {info['casos_paridad']} casos: variables {info['dif_variables']:.1e}, "
              f"probabilidades {info['dif_probabilidades']:.1e}")
        for archivo in info["archivos"]:
            print(f"  {archivo['Archivo']}  {archivo['Tamaño (KB)']:,} KB")
