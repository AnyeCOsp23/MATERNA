"""Sub-fase 2.2 — Experimentación, ajuste de hiperparámetros y entrenamiento de modelos.

Decisiones metodológicas (ver README, sección "Decisiones técnicas"):
- SMOTE se aplica DENTRO de cada fold mediante un Pipeline de imbalanced-learn. Aplicarlo antes de
  GridSearchCV contaminaría los folds de validación con muestras sintéticas derivadas de ellos.
- SMOTE y class_weight='balanced' son estrategias alternativas de balanceo y se comparan como un
  hiperparámetro más; usarlas a la vez compensaría el desbalance dos veces.
- En scikit-learn >= 1.8 `SVC(probability=True)` está deprecado: las probabilidades del SVM se
  obtienen calibrando el mejor pipeline con CalibratedClassifierCV (Platt / sigmoide, 5 folds).
- `LogisticRegression(multi_class='multinomial')` ya no existe: con solver lbfgs el modelo
  multiclase es multinomial por defecto.
- Random Forest se agregó tras las pruebas de coherencia clínica (tests/test_coherencia_clinica.py):
  el SVM clasificaba como Bajo Riesgo casos con un único factor de riesgo cerca del umbral
  (p. ej. PA 140/90 o cero controles prenatales). Los árboles capturan umbrales de forma nativa y no
  extrapolan fuera del rango de entrenamiento.

Uso:  python -m src.train_models
"""
import json
import time

import joblib
import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline as ImbPipeline
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, make_scorer, precision_score, recall_score
from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_validate
from sklearn.svm import SVC

from src.config import CLASE_ALTO, DIR_METRICAS, DIR_MODELOS, SEMILLA
from src.data_preprocessing import pasos_preprocesamiento, preparar_datos

CV = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEMILLA)

SCORING = {
    "f1_macro": "f1_macro",
    "f1_weighted": "f1_weighted",
    "balanced_accuracy": "balanced_accuracy",
    "accuracy": "accuracy",
    "recall_alto": make_scorer(recall_score, labels=[CLASE_ALTO], average="macro", zero_division=0),
    "precision_alto": make_scorer(precision_score, labels=[CLASE_ALTO], average="macro", zero_division=0),
    "f1_alto": make_scorer(f1_score, labels=[CLASE_ALTO], average="macro", zero_division=0),
}
METRICA_REFIT = "f1_macro"

GRID_C_LR = list(np.logspace(-3, 3, 13))
GRID_C_SVM = [0.1, 1, 10, 100]
GRID_GAMMA = ["scale", 0.01, 0.1, 1]


def construir_pipeline(modelo, incluir_demograficas=False):
    return ImbPipeline([
        *pasos_preprocesamiento(incluir_demograficas),
        ("balanceo", "passthrough"),
        ("modelo", modelo),
    ])


def con_estrategias_balanceo(grid_modelo):
    """Duplica cada grilla: (a) SMOTE sin pesos, (b) sin SMOTE con class_weight='balanced'."""
    grids = []
    for g in grid_modelo:
        grids.append({**g, "balanceo": [SMOTE(random_state=SEMILLA)], "modelo__class_weight": [None]})
        grids.append({**g, "balanceo": ["passthrough"], "modelo__class_weight": ["balanced"]})
    return grids


def grid_regresion_logistica():
    return con_estrategias_balanceo([{"modelo__C": GRID_C_LR}])


def grid_svm():
    return con_estrategias_balanceo([
        {"modelo__kernel": ["rbf"], "modelo__C": GRID_C_SVM, "modelo__gamma": GRID_GAMMA},
        {"modelo__kernel": ["linear"], "modelo__C": GRID_C_SVM},
        {"modelo__kernel": ["poly"], "modelo__C": GRID_C_SVM, "modelo__gamma": GRID_GAMMA, "modelo__degree": [2, 3]},
    ])


def grid_random_forest():
    return con_estrategias_balanceo([{
        "modelo__n_estimators": [300],
        "modelo__max_depth": [None, 8, 12],
        "modelo__min_samples_leaf": [1, 3, 5],
        "modelo__max_features": ["sqrt", 0.5],
    }])


def buscar_hiperparametros(nombre, estimador, grid, X_train, y_train):
    busqueda = GridSearchCV(
        construir_pipeline(estimador), grid, scoring=SCORING, refit=METRICA_REFIT,
        cv=CV, n_jobs=-1, return_train_score=False,
    )
    inicio = time.perf_counter()
    busqueda.fit(X_train, y_train)
    duracion = time.perf_counter() - inicio
    print(f"[{nombre}] {len(busqueda.cv_results_['params'])} configuraciones x 5 folds en {duracion:.1f} s")
    print(f"[{nombre}] mejor {METRICA_REFIT} CV = {busqueda.best_score_:.4f} | {describir_params(busqueda.best_params_)}")
    return busqueda, duracion


def describir_params(params):
    legible = {}
    for k, v in params.items():
        if k == "balanceo":
            legible["balanceo"] = "SMOTE" if not isinstance(v, str) else "class_weight"
        elif k != "modelo__class_weight":
            legible[k.replace("modelo__", "")] = round(v, 4) if isinstance(v, float) else v
    return legible


def tabla_experimentos(nombre, busqueda):
    """Registro completo de experimentos: una fila por configuración probada."""
    res = pd.DataFrame(busqueda.cv_results_)
    legibles = [describir_params(p) for p in res["params"]]
    filas = pd.DataFrame(legibles)
    filas.insert(0, "modelo", nombre)
    # texto armado desde los parámetros originales: conserva enteros y valores None (p. ej. max_depth=None)
    filas.insert(2, "hiperparametros", [str({k: v for k, v in p.items() if k != "balanceo"}) for p in legibles])
    for m in SCORING:
        filas[f"cv_{m}_media"] = res[f"mean_test_{m}"].round(4)
        filas[f"cv_{m}_std"] = res[f"std_test_{m}"].round(4)
    filas["tiempo_ajuste_s"] = res["mean_fit_time"].round(4)
    filas["ranking"] = res[f"rank_test_{METRICA_REFIT}"]
    return filas.sort_values("ranking")


def resumen_por_estrategia(experimentos):
    """Mejor configuración de cada (modelo, estrategia de balanceo): la tabla comparativa del informe."""
    columnas = (["modelo", "balanceo", "hiperparametros"] + [c for c in experimentos.columns if c.startswith("cv_")]
                + ["tiempo_ajuste_s"])
    mejores = experimentos.sort_values(f"cv_{METRICA_REFIT}_media", ascending=False).groupby(["modelo", "balanceo"]).head(1)
    return mejores[columnas].reset_index(drop=True)


def ablacion_demograficas(busquedas, X_train, y_train):
    """¿Aportan municipio/departamento/etnia? Se reevalúa la mejor configuración incluyéndolas."""
    filas = []
    for nombre, busqueda in busquedas.items():
        for incluir in (False, True):
            pipe = construir_pipeline(busqueda.best_estimator_.named_steps["modelo"], incluir_demograficas=incluir)
            pipe.set_params(balanceo=busqueda.best_params_["balanceo"])
            r = cross_validate(pipe, X_train, y_train, cv=CV, scoring=SCORING, n_jobs=-1)
            filas.append({
                "modelo": nombre,
                "variables": "clínicas + acceso + demográficas" if incluir else "clínicas + acceso (por defecto)",
                **{f"cv_{m}_media": round(r[f"test_{m}"].mean(), 4) for m in ["f1_macro", "recall_alto", "balanced_accuracy"]},
            })
    return pd.DataFrame(filas)


def entrenar_todo():
    X_train, X_val, X_test, y_train, y_val, y_test = preparar_datos()
    DIR_METRICAS.mkdir(parents=True, exist_ok=True)
    DIR_MODELOS.mkdir(parents=True, exist_ok=True)

    candidatos = {
        "Regresión Logística": (LogisticRegression(solver="lbfgs", max_iter=5000), grid_regresion_logistica()),
        "SVM": (SVC(), grid_svm()),
        "Random Forest": (RandomForestClassifier(random_state=SEMILLA), grid_random_forest()),
    }
    busquedas, tiempos = {}, {}
    for nombre, (estimador, grid) in candidatos.items():
        busquedas[nombre], tiempos[nombre] = buscar_hiperparametros(nombre, estimador, grid, X_train, y_train)

    experimentos = pd.concat([tabla_experimentos(n, b) for n, b in busquedas.items()], ignore_index=True)
    experimentos.to_csv(DIR_METRICAS / "experimentos_cv_completo.csv", index=False)
    resumen = resumen_por_estrategia(experimentos)
    resumen.to_csv(DIR_METRICAS / "comparacion_cv_por_estrategia.csv", index=False)
    print("\nComparación en validación cruzada (mejor configuración por modelo y estrategia):")
    print(resumen.to_string(index=False))

    ablacion = ablacion_demograficas(busquedas, X_train, y_train)
    ablacion.to_csv(DIR_METRICAS / "ablacion_variables_demograficas.csv", index=False)
    print("\nAblación de variables demográficas:\n", ablacion.to_string(index=False))

    # Modelos finales ajustados sobre entrenamiento.
    modelo_lr = busquedas["Regresión Logística"].best_estimator_
    inicio = time.perf_counter()
    modelo_svm = CalibratedClassifierCV(busquedas["SVM"].best_estimator_, method="sigmoid", cv=CV).fit(X_train, y_train)
    tiempo_calibracion = time.perf_counter() - inicio
    modelo_rf = busquedas["Random Forest"].best_estimator_

    joblib.dump(modelo_lr, DIR_MODELOS / "modelo_regresion_logistica.joblib")
    joblib.dump(modelo_svm, DIR_MODELOS / "modelo_svm_calibrado.joblib")
    joblib.dump(modelo_rf, DIR_MODELOS / "modelo_random_forest.joblib", compress=3)
    metadatos = {
        nombre: {
            "mejores_hiperparametros": describir_params(b.best_params_),
            f"cv_{METRICA_REFIT}": round(b.best_score_, 4),
            "configuraciones_probadas": len(b.cv_results_["params"]),
            "tiempo_busqueda_s": round(tiempos[nombre], 1),
        }
        for nombre, b in busquedas.items()
    }
    metadatos["SVM"]["calibracion"] = {"metodo": "sigmoid (Platt)", "cv": 5, "tiempo_s": round(tiempo_calibracion, 1)}
    with open(DIR_MODELOS / "metadatos_modelos.json", "w", encoding="utf-8") as f:
        json.dump(metadatos, f, ensure_ascii=False, indent=2)
    return {"Regresión Logística": modelo_lr, "SVM": modelo_svm, "Random Forest": modelo_rf}


if __name__ == "__main__":
    entrenar_todo()
