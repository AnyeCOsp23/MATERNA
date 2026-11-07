"""Fase 3 — Curvas de aprendizaje y brecha entrenamiento vs validación cruzada (generalización).

Usa los pipelines ya entrenados (mismos hiperparámetros) y la misma validación cruzada estratificada
de 5 particiones sobre el conjunto de entrenamiento (n = 840). Para el SVM se usa el estimador sin
calibrar, como en el documento de la Fase 2. Guarda:
  reports/metrics/curvas_aprendizaje.csv   F1-macro por tamaño de entrenamiento
  reports/metrics/brecha_sobreajuste.csv   F1-macro en entrenamiento y en CV con el 100 % de los datos

Uso:  python -m src.curvas_aprendizaje      (unos 2 minutos)
"""
import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.model_selection import cross_validate, learning_curve

from src.config import DIR_METRICAS, DIR_MODELOS, SEMILLA
from src.data_preprocessing import preparar_datos
from src.train_models import CV

TAMANOS = np.linspace(0.15, 1.0, 7)


def modelos_base():
    return {
        "Regresión Logística": joblib.load(DIR_MODELOS / "modelo_regresion_logistica.joblib"),
        "SVM": joblib.load(DIR_MODELOS / "modelo_svm_calibrado.joblib").estimator,
        "Random Forest": joblib.load(DIR_MODELOS / "modelo_random_forest.joblib"),
    }


def calcular():
    X_train, _, _, y_train, _, _ = preparar_datos(guardar=False)
    curvas, brecha = [], []
    for nombre, modelo in modelos_base().items():
        tamanos, entrenamiento, validacion = learning_curve(
            clone(modelo), X_train, y_train, cv=CV, scoring="f1_macro", train_sizes=TAMANOS,
            n_jobs=-1, shuffle=True, random_state=SEMILLA)
        for n, tr, va in zip(tamanos, entrenamiento, validacion):
            curvas.append({"modelo": nombre, "n_entrenamiento": int(n),
                           "f1_entrenamiento": tr.mean(), "f1_entrenamiento_std": tr.std(),
                           "f1_cv": va.mean(), "f1_cv_std": va.std()})
        r = cross_validate(clone(modelo), X_train, y_train, cv=CV, scoring="f1_macro", return_train_score=True, n_jobs=-1)
        brecha.append({"modelo": nombre, "f1_entrenamiento": r["train_score"].mean(), "f1_cv": r["test_score"].mean(),
                       "f1_cv_std": r["test_score"].std(), "brecha": r["train_score"].mean() - r["test_score"].mean()})
    curvas, brecha = pd.DataFrame(curvas).round(4), pd.DataFrame(brecha).round(4)
    curvas.to_csv(DIR_METRICAS / "curvas_aprendizaje.csv", index=False)
    brecha.to_csv(DIR_METRICAS / "brecha_sobreajuste.csv", index=False)
    return curvas, brecha


if __name__ == "__main__":
    _, brecha = calcular()
    print(brecha.to_string(index=False))
