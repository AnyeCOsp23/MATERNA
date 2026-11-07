"""Fase 3 — "Entrenar en vivo" del laboratorio: reentrena el Random Forest con los mejores
hiperparámetros de la búsqueda (models/metadatos_modelos.json), sin repetir la búsqueda completa.

1. Validación cruzada estratificada de 5 particiones sobre el entrenamiento, informando cada partición.
2. Ajuste final con todo el entrenamiento (n = 840).
3. Métricas en validación y prueba, y comparación con el modelo en uso (models/*.joblib).

No guarda nada: el modelo en uso no se reemplaza. Versionar modelos nuevos es parte del bloque 5.
"""
import json
import time

import joblib
import numpy as np
from imblearn.over_sampling import SMOTE
from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score

from src.clinical_rules import predecir_hibrido
from src.config import DIR_MODELOS, SEMILLA
from src.data_preprocessing import preparar_datos
from src.evaluate import calcular_metricas
from src.train_models import CV, construir_pipeline


def mejores_hiperparametros():
    with open(DIR_MODELOS / "metadatos_modelos.json", encoding="utf-8") as f:
        return json.load(f)["Random Forest"]["mejores_hiperparametros"]


def construir_rf():
    """El mismo pipeline que eligió GridSearchCV, armado a partir de los metadatos."""
    params = dict(mejores_hiperparametros())
    balanceo = params.pop("balanceo")
    pipeline = construir_pipeline(RandomForestClassifier(random_state=SEMILLA, **params))
    if balanceo == "SMOTE":
        pipeline.set_params(balanceo=SMOTE(random_state=SEMILLA))
    else:
        pipeline.set_params(modelo__class_weight="balanced")
    return pipeline


def entrenar(al_avanzar=lambda etapa, detalle: None):
    """Reentrena y evalúa. al_avanzar(etapa, detalle) se llama tras cada paso, para la interfaz."""
    inicio = time.perf_counter()
    X_train, X_val, X_test, y_train, y_val, y_test = preparar_datos(guardar=False)
    base = construir_rf()

    folds = []
    for i, (tr, va) in enumerate(CV.split(X_train, y_train), start=1):
        modelo = clone(base).fit(X_train.iloc[tr], y_train.iloc[tr])
        f1 = f1_score(y_train.iloc[va], modelo.predict(X_train.iloc[va]), average="macro")
        folds.append(f1)
        al_avanzar("cv", {"particion": i, "f1_macro": f1})

    modelo = clone(base).fit(X_train, y_train)
    al_avanzar("ajuste", {"n": len(X_train)})

    en_uso = joblib.load(DIR_MODELOS / "modelo_random_forest.joblib")
    resultados = {}
    for nombre, X, y in [("validación", X_val, y_val), ("prueba", X_test, y_test)]:
        for sistema, m in [("reentrenado", modelo), ("en uso", en_uso)]:
            pred, proba, _ = predecir_hibrido(m, X)
            resultados[(nombre, sistema)] = calcular_metricas(y, pred, proba)
        al_avanzar("evaluacion", {"conjunto": nombre})

    identicas = bool(np.array_equal(modelo.predict_proba(X_test), en_uso.predict_proba(X_test)))
    return {
        "hiperparametros": mejores_hiperparametros(),
        "cv_f1_por_particion": folds,
        "cv_f1_media": float(np.mean(folds)),
        "metricas": resultados,
        "identico_al_modelo_en_uso": identicas,
        "segundos": time.perf_counter() - inicio,
    }
