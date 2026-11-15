"""Fase 3 — Experimentos del laboratorio: entrenar con parámetros propios y versionar cada resultado.

El modelo en uso (models/*.joblib) y las cifras oficiales de la Fase 2 NO se tocan aquí. Todo lo que se
entrena desde el laboratorio va a un conjunto de trabajo aparte, la carpeta experimentos/ (fuera del
repositorio; la variable MATERNA_EXPERIMENTOS puede apuntar a otra, y la usan las pruebas):

    experimentos/registro.jsonl          una línea por entrenamiento (nunca se reescribe: solo se agrega)
    experimentos/modelos/exp-0001.joblib el modelo de esa versión

Cada entrenamiento:
  1. parte los datos con las proporciones y la semilla elegidas (estratificado);
  2. hace validación cruzada estratificada de 5 particiones sobre el entrenamiento;
  3. ajusta el modelo con todo el entrenamiento (la SVM se calibra, como en la Fase 2, para dar probabilidades);
  4. mide el sistema híbrido (modelo + reglas clínicas) en validación y en prueba;
  5. guarda el modelo como una versión nueva y agrega la fila al registro.

Con Random Forest, los hiperparámetros de la búsqueda, la partición 70/15/15 y la semilla 42, el resultado
es idéntico al modelo en uso: es la prueba de que el laboratorio reproduce la Fase 2.

Criterio de selección entre versiones: mayor F1-macro en validación; si hay empate, mayor recall de
Alto Riesgo en validación. El conjunto de prueba se informa, pero no se usa para elegir.
"""
import hashlib
import json
import os
import time
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, recall_score
from sklearn.model_selection import StratifiedKFold, learning_curve
from sklearn.svm import SVC

from src.clinical_rules import predecir_hibrido
from src.config import CLASE_ALTO, DIR_MODELOS, RAIZ, SEMILLA
from src.data_preprocessing import (
    PARTICION_OFICIAL, cargar_dataset, marcar_fuera_de_rango, particionar, separar_xy,
)
from src.evaluate import calcular_metricas
from src.train_models import construir_pipeline

VARIABLE_DIRECTORIO = "MATERNA_EXPERIMENTOS"
ALGORITMOS = ("Random Forest", "Regresión Logística", "SVM")
BALANCEOS = ("SMOTE", "class_weight")
DATOS_BASE = "Dataset base (1.200 gestantes sintéticas)"
N_PARTICIONES_CV = 5
TAMANOS_CURVA = np.linspace(0.15, 1.0, 7)
METRICAS_REGISTRO = ("f1_macro", "recall_alto", "accuracy", "roc_auc_ovr_macro", "costo_clinico_total")

# Valores que admite cada hiperparámetro (los de la búsqueda de la Fase 2 están incluidos)
KERNELS = ("rbf", "linear", "poly")
MAX_FEATURES = ("sqrt", "log2")
LIMITES = {
    "Random Forest": {"n_estimators": (10, 1000), "max_depth": (1, 50), "min_samples_leaf": (1, 50)},
    "Regresión Logística": {"C": (1e-4, 1e4)},
    "SVM": {"C": (1e-4, 1e4), "gamma": (1e-5, 100), "degree": (2, 5)},
}


def directorio():
    return Path(os.environ.get(VARIABLE_DIRECTORIO) or RAIZ / "experimentos")


def hiperparametros_base(algoritmo):
    """Los mejores hiperparámetros de la búsqueda en grilla de la Fase 2 (models/metadatos_modelos.json)."""
    with open(DIR_MODELOS / "metadatos_modelos.json", encoding="utf-8") as f:
        return json.load(f)[algoritmo]["mejores_hiperparametros"]


def validar_hiperparametros(algoritmo, hiperparametros):
    """Lanza ValueError, explicando el motivo, si la configuración no es válida para el algoritmo."""
    if algoritmo not in ALGORITMOS:
        raise ValueError(f"Algoritmo desconocido: {algoritmo}. Use uno de: {', '.join(ALGORITMOS)}.")
    h = dict(hiperparametros)
    if h.pop("balanceo", None) not in BALANCEOS:
        raise ValueError(f"El balanceo debe ser uno de: {', '.join(BALANCEOS)}.")
    limites = LIMITES[algoritmo]
    permitidos = {"Random Forest": {*limites, "max_features"}, "Regresión Logística": {"C"},
                  "SVM": {*limites, "kernel"}}[algoritmo]
    sobran = set(h) - permitidos
    if sobran:
        raise ValueError(f"Hiperparámetros que no son de {algoritmo}: {', '.join(sorted(sobran))}.")
    for nombre, valor in h.items():
        if nombre == "kernel":
            valido = valor in KERNELS
        elif nombre == "max_features":
            valido = valor in MAX_FEATURES or (isinstance(valor, float) and 0 < valor <= 1)
        elif (nombre, valor) in {("max_depth", None), ("gamma", "scale")}:
            valido = True
        else:
            lo, hi = limites[nombre]
            entero = nombre in {"n_estimators", "max_depth", "min_samples_leaf", "degree"}
            valido = (isinstance(valor, (int, float)) and not isinstance(valor, bool) and lo <= valor <= hi
                      and (not entero or float(valor).is_integer()))
        if not valido:
            raise ValueError(f"Valor no válido para {nombre}: {valor!r}.")


def construir(algoritmo, hiperparametros, semilla=SEMILLA):
    """El pipeline sin ajustar: preprocesamiento sin fuga de datos, balanceo y modelo."""
    validar_hiperparametros(algoritmo, hiperparametros)
    params = dict(hiperparametros)
    balanceo = params.pop("balanceo")
    if algoritmo == "Random Forest":
        modelo = RandomForestClassifier(random_state=semilla, **params)
    elif algoritmo == "Regresión Logística":
        modelo = LogisticRegression(solver="lbfgs", max_iter=5000, **params)
    else:
        modelo = SVC(**params)
    pipeline = construir_pipeline(modelo)
    # SMOTE y class_weight son alternativas: nunca juntas (compensarían el desbalance dos veces)
    if balanceo == "SMOTE":
        pipeline.set_params(balanceo=SMOTE(random_state=semilla))
    else:
        pipeline.set_params(modelo__class_weight="balanced")
    return pipeline


def _validacion_cruzada(semilla):
    return StratifiedKFold(n_splits=N_PARTICIONES_CV, shuffle=True, random_state=semilla)


def _particiones(datos, proporciones, semilla):
    df = cargar_dataset() if datos is None else datos
    X, y = separar_xy(marcar_fuera_de_rango(df))
    return particionar(X, y, semilla, proporciones)


def _sha256(ruta):
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()


def _siguiente_version(carpeta):
    usados = [int(r["version"].split("-")[1]) for r in leer_registro(carpeta)]
    usados += [int(p.stem.split("-")[1]) for p in (carpeta / "modelos").glob("exp-*.joblib")]
    return f"exp-{max(usados, default=0) + 1:04d}"


def entrenar(algoritmo, hiperparametros=None, proporciones=PARTICION_OFICIAL, semilla=SEMILLA, usuario="terminal",
             datos=None, nombre_datos=DATOS_BASE, al_avanzar=lambda etapa, detalle: None):
    """Entrena, evalúa y guarda una versión nueva. al_avanzar(etapa, detalle) informa cada paso a la interfaz.

    Devuelve {'registro': fila del registro, 'modelo': modelo ajustado, 'cv_f1_por_particion': [...],
    'metricas': {'validación': {...}, 'prueba': {...}}, 'identico_al_modelo_en_uso': bool}.
    """
    inicio = time.perf_counter()
    hiperparametros = dict(hiperparametros_base(algoritmo) if hiperparametros is None else hiperparametros)
    base = construir(algoritmo, hiperparametros, semilla)
    X_train, X_val, X_test, y_train, y_val, y_test = _particiones(datos, proporciones, semilla)
    cv = _validacion_cruzada(semilla)

    f1_cv, recall_cv = [], []
    for i, (tr, va) in enumerate(cv.split(X_train, y_train), start=1):
        pred = clone(base).fit(X_train.iloc[tr], y_train.iloc[tr]).predict(X_train.iloc[va])
        f1_cv.append(f1_score(y_train.iloc[va], pred, average="macro"))
        recall_cv.append(recall_score(y_train.iloc[va], pred, labels=[CLASE_ALTO], average="macro", zero_division=0))
        al_avanzar("cv", {"particion": i, "f1_macro": f1_cv[-1]})

    if algoritmo == "SVM":  # la SVM no da probabilidades: se calibra (Platt), igual que en la Fase 2
        modelo = CalibratedClassifierCV(base, method="sigmoid", cv=cv).fit(X_train, y_train)
    else:
        modelo = clone(base).fit(X_train, y_train)
    al_avanzar("ajuste", {"n": len(X_train)})

    metricas = {}
    for nombre, X, y in [("validación", X_val, y_val), ("prueba", X_test, y_test)]:
        pred, proba, _ = predecir_hibrido(modelo, X)
        metricas[nombre] = calcular_metricas(y, pred, proba)
        al_avanzar("evaluacion", {"conjunto": nombre})

    identico = False
    if algoritmo == "Random Forest" and datos is None:
        en_uso = joblib.load(DIR_MODELOS / "modelo_random_forest.joblib")
        identico = bool(np.array_equal(modelo.predict_proba(X_test), en_uso.predict_proba(X_test)))

    registro = {
        "version": None, "fecha": datetime.now().isoformat(timespec="seconds"), "usuario": usuario,
        "algoritmo": algoritmo, "hiperparametros": hiperparametros,
        "particion": "/".join(str(p) for p in proporciones), "semilla": int(semilla), "datos": nombre_datos,
        "n_entrenamiento": len(X_train), "n_validacion": len(X_val), "n_prueba": len(X_test),
        "cv_f1_macro": float(np.mean(f1_cv)), "cv_f1_macro_std": float(np.std(f1_cv)),
        "cv_recall_alto": float(np.mean(recall_cv)),
        **{f"{prefijo}_{m}": float(metricas[conjunto][m]) for prefijo, conjunto in [("val", "validación"), ("prueba", "prueba")]
           for m in METRICAS_REGISTRO if m in metricas[conjunto]},
        "identico_al_modelo_en_uso": identico,
    }
    registro["tiempo_s"] = round(time.perf_counter() - inicio, 2)
    _guardar(modelo, registro)
    return {"registro": registro, "modelo": modelo, "cv_f1_por_particion": f1_cv, "metricas": metricas,
            "identico_al_modelo_en_uso": identico}


def _guardar(modelo, registro):
    """Versión nueva: el archivo del modelo se abre en modo exclusivo, así que nunca pisa uno anterior."""
    carpeta = directorio()
    (carpeta / "modelos").mkdir(parents=True, exist_ok=True)
    registro["version"] = _siguiente_version(carpeta)
    ruta = carpeta / "modelos" / f"{registro['version']}.joblib"
    with open(ruta, "xb") as f:
        joblib.dump(modelo, f, compress=3)
    registro["sha256"] = _sha256(ruta)
    with open(carpeta / "registro.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")


def leer_registro(carpeta=None):
    """Las filas del registro tal como se guardaron (con los hiperparámetros como diccionario)."""
    ruta = (carpeta or directorio()) / "registro.jsonl"
    if not ruta.exists():
        return []
    return [json.loads(linea) for linea in ruta.read_text(encoding="utf-8").splitlines() if linea.strip()]


def tabla_registro():
    """El registro como tabla comparativa, lista para mostrar o descargar (una fila por versión)."""
    filas = leer_registro()
    if not filas:
        return pd.DataFrame()
    tabla = pd.DataFrame(filas)
    tabla.insert(4, "balanceo", [h["balanceo"] for h in tabla["hiperparametros"]])
    tabla["hiperparametros"] = [", ".join(f"{k}={v}" for k, v in h.items() if k != "balanceo") for h in tabla["hiperparametros"]]
    return tabla


def mejor_version(tabla):
    """Criterio de selección: mayor F1-macro en validación; en empate, mayor recall de Alto en validación
    y, si persiste, la versión más antigua."""
    if tabla.empty:
        return None
    orden = tabla.sort_values(["val_f1_macro", "val_recall_alto", "version"], ascending=[False, False, True])
    return orden.iloc[0]["version"]


def cargar_modelo(version):
    return joblib.load(directorio() / "modelos" / f"{version}.joblib")


def curva_aprendizaje(version):
    """Curva de aprendizaje de una versión, con su misma partición, semilla e hiperparámetros.

    Mismas columnas que reports/metrics/curvas_aprendizaje.csv. Solo para versiones entrenadas con el dataset base.
    """
    registro = next((r for r in leer_registro() if r["version"] == version), None)
    if registro is None:
        raise ValueError(f"No existe la versión {version}.")
    if registro["datos"] != DATOS_BASE:
        raise ValueError("La curva solo se calcula para versiones entrenadas con el dataset base.")
    semilla = registro["semilla"]
    proporciones = tuple(int(p) for p in registro["particion"].split("/"))
    X_train, _, _, y_train, _, _ = _particiones(None, proporciones, semilla)
    tamanos, entrenamiento, validacion = learning_curve(
        construir(registro["algoritmo"], registro["hiperparametros"], semilla), X_train, y_train,
        cv=_validacion_cruzada(semilla), scoring="f1_macro", train_sizes=TAMANOS_CURVA, n_jobs=-1, shuffle=True,
        random_state=semilla)
    return pd.DataFrame({
        "modelo": f"{version} · {registro['algoritmo']}", "n_entrenamiento": tamanos.astype(int),
        "f1_entrenamiento": entrenamiento.mean(axis=1), "f1_entrenamiento_std": entrenamiento.std(axis=1),
        "f1_cv": validacion.mean(axis=1), "f1_cv_std": validacion.std(axis=1),
    }).round(4)


if __name__ == "__main__":
    for algoritmo in ALGORITMOS:
        r = entrenar(algoritmo)["registro"]
        print(f"{r['version']}  {algoritmo:20s} F1-macro val {r['val_f1_macro']:.4f}  recall Alto val "
              f"{r['val_recall_alto']:.4f}  {r['tiempo_s']} s")
