"""Fase 3 — Exporta el sistema híbrido (Random Forest + reglas) a JSON para la app Flutter.

Genera en flutter_app/assets/:
  preproceso.json      medianas de imputación, centro/escala del RobustScaler y categorías del One-Hot
  modelo_rf.json       los 300 árboles (variable, umbral, hijos y probabilidades de las hojas)
  reglas.json          los 4 signos críticos, las clases y los protocolos orientativos
  casos_paridad.json   200 gestantes con la respuesta exacta de scikit-learn, para la prueba en Dart

Antes de escribir, verifica con src/inferencia_json.py (Python puro, sin scikit-learn) que los JSON
reproducen las probabilidades del pipeline. Carga el modelo .joblib existente: no reentrena.

Uso:  python -m src.exportar_a_dart
"""
import datetime as dt
import hashlib
import json

import joblib
import numpy as np
import pandas as pd
import sklearn

from src.clinical_rules import (
    PROTOCOLO, UMBRAL_PAD_SEVERA, UMBRAL_PAS_SEVERA, UMBRAL_PROTEINURIA, evaluar_riesgo_hibrido,
)
from src.config import CLASE_ALTO, DIR_MODELOS, NOMBRES_CLASES, RAIZ, SEMILLA, VARS_CON_NULOS
from src.data_preprocessing import preparar_datos
from src.inferencia_json import ClasificadorJSON

RUTA_MODELO = DIR_MODELOS / "modelo_random_forest.joblib"
DIR_ASSETS = RAIZ / "flutter_app" / "assets"
TOLERANCIA = 1e-6
N_CASOS = 200
VERSION_MODELO = "v1"


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


def exportar_modelo(pipeline):
    rf = pipeline.named_steps["modelo"]
    return {
        "version": VERSION_MODELO,
        "tipo": "RandomForestClassifier",
        "origen": RUTA_MODELO.name,
        "sha256_joblib": _sha256(RUTA_MODELO),
        "scikit_learn": sklearn.__version__,
        "exportado": dt.date.today().isoformat(),
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


def _escribir(nombre, datos, compacto=False):
    ruta = DIR_ASSETS / nombre
    with open(ruta, "w", encoding="utf-8") as f:
        if compacto:
            json.dump(datos, f, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(datos, f, ensure_ascii=False, indent=1)
    return ruta


def exportar():
    pipeline = joblib.load(RUTA_MODELO)
    preproceso, modelo, reglas = exportar_preproceso(pipeline), exportar_modelo(pipeline), exportar_reglas()
    casos = generar_casos(pipeline)
    dif_x, dif_p = verificar(preproceso, modelo, reglas, casos)
    DIR_ASSETS.mkdir(parents=True, exist_ok=True)
    rutas = [_escribir("preproceso.json", preproceso), _escribir("modelo_rf.json", modelo, compacto=True),
             _escribir("reglas.json", reglas), _escribir("casos_paridad.json", {"tolerancia": TOLERANCIA, "casos": casos})]
    print(f"Paridad JSON vs scikit-learn en {len(casos)} casos: variables {dif_x:.1e}, probabilidades {dif_p:.1e}")
    for r in rutas:
        print(f"  {r.relative_to(RAIZ)}  {r.stat().st_size / 1024:,.0f} KB")


if __name__ == "__main__":
    exportar()
