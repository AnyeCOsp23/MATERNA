"""Sub-fase 2.4 — Evaluación cuantitativa en validación y prueba (datos no vistos).

Sistemas evaluados: Regresión Logística (baseline), SVM calibrado, y sus versiones híbridas
(modelo + reglas clínicas de sobreescritura).

Nota metodológica: en el dataset sintético, todos los registros que cumplen una regla crítica
están etiquetados como Alto Riesgo, porque las etiquetas se generaron con esos mismos umbrales.
Por eso el sistema híbrido acierta esos casos por construcción. Para medir el aporte real del
modelo se reporta además el desempeño en el subconjunto SIN signos críticos.

Uso:  python -m src.evaluate        (requiere haber ejecutado antes src.train_models)
"""
import json

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.metrics import (
    accuracy_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score, roc_curve,
)
from sklearn.model_selection import cross_val_predict

from src.clinical_rules import mascara_reglas, predecir_hibrido
from src.config import CLASE_ALTO, DIR_FIGURAS, DIR_METRICAS, DIR_MODELOS, NOMBRES_CLASES, SEMILLA
from src.data_preprocessing import cargar_dataset, marcar_fuera_de_rango, preparar_datos, separar_xy
from src.train_models import CV

ETIQUETAS_CORTAS = ["Bajo", "Medio", "Alto"]
COLORES_CLASE = {"Bajo": "#2E7D32", "Medio": "#F9A825", "Alto": "#C62828"}

# Matriz de costo clínico ilustrativa (filas = real, columnas = predicho).
# Subestimar el riesgo (debajo de la diagonal) cuesta mucho más que sobreestimarlo:
# un Alto clasificado como Bajo puede significar una muerte materna evitable; un Bajo clasificado
# como Alto genera una remisión innecesaria. Los pesos son supuestos del equipo, no valores oficiales.
MATRIZ_COSTO = np.array([
    [0, 1, 2],    # real Bajo
    [3, 0, 1],    # real Medio
    [10, 5, 0],   # real Alto
])


def cargar_modelos():
    return {
        "Regresión Logística": joblib.load(DIR_MODELOS / "modelo_regresion_logistica.joblib"),
        "SVM": joblib.load(DIR_MODELOS / "modelo_svm_calibrado.joblib"),
    }


def predecir_sistemas(modelos, X):
    """Predicciones y probabilidades de los 4 sistemas."""
    salidas = {}
    for nombre, modelo in modelos.items():
        proba = modelo.predict_proba(X)
        salidas[nombre] = (proba.argmax(axis=1), proba)
    for nombre, modelo in modelos.items():
        pred, proba, _ = predecir_hibrido(modelo, X)
        salidas[f"Híbrido ({nombre} + reglas)"] = (pred, proba)
    return salidas


def calcular_metricas(y, pred, proba=None):
    y = np.asarray(y)
    cm = confusion_matrix(y, pred, labels=[0, 1, 2])
    m = {
        "n": len(y),
        "accuracy": accuracy_score(y, pred),
        "precision_macro": precision_score(y, pred, average="macro", zero_division=0),
        "recall_macro": recall_score(y, pred, average="macro", zero_division=0),
        "f1_macro": f1_score(y, pred, average="macro", zero_division=0),
        "precision_weighted": precision_score(y, pred, average="weighted", zero_division=0),
        "recall_weighted": recall_score(y, pred, average="weighted", zero_division=0),
        "f1_weighted": f1_score(y, pred, average="weighted", zero_division=0),
        "recall_alto": recall_score(y, pred, labels=[CLASE_ALTO], average="macro", zero_division=0),
        "precision_alto": precision_score(y, pred, labels=[CLASE_ALTO], average="macro", zero_division=0),
        "falsos_negativos_alto": int(cm[2, 0] + cm[2, 1]),
        "alto_clasificado_como_bajo": int(cm[2, 0]),
        "costo_clinico_total": int((cm * MATRIZ_COSTO).sum()),
    }
    if proba is not None and len(np.unique(y)) == 3:
        m["roc_auc_ovr_macro"] = roc_auc_score(y, proba, multi_class="ovr", average="macro")
    return m


def intervalo_bootstrap(y, pred, metrica, n=2000, semilla=SEMILLA):
    """IC 95 % por bootstrap percentil: con ~23 casos de Alto Riesgo en prueba, la incertidumbre es grande."""
    rng = np.random.default_rng(semilla)
    y, pred = np.asarray(y), np.asarray(pred)
    valores = []
    for _ in range(n):
        idx = rng.integers(0, len(y), len(y))
        if (y[idx] == CLASE_ALTO).sum() == 0:
            continue
        valores.append(metrica(y[idx], pred[idx]))
    return np.percentile(valores, [2.5, 97.5])


def tabla_metricas(salidas, y, mascara=None):
    filas = []
    for nombre, (pred, proba) in salidas.items():
        if mascara is not None:
            pred, proba, yy = pred[mascara], proba[mascara], np.asarray(y)[mascara]
        else:
            yy = y
        filas.append({"sistema": nombre, **calcular_metricas(yy, pred, proba)})
    return pd.DataFrame(filas).set_index("sistema")


def graficar_matrices_confusion(salidas, y, ruta):
    fig, axes = plt.subplots(2, len(salidas), figsize=(4.6 * len(salidas), 8.4))
    for j, (nombre, (pred, _)) in enumerate(salidas.items()):
        cm = confusion_matrix(y, pred, labels=[0, 1, 2])
        cm_norm = cm / cm.sum(axis=1, keepdims=True)
        sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", cbar=False, ax=axes[0, j],
                    xticklabels=ETIQUETAS_CORTAS, yticklabels=ETIQUETAS_CORTAS)
        sns.heatmap(cm_norm, annot=True, fmt=".2f", cmap="Blues", vmin=0, vmax=1, cbar=False, ax=axes[1, j],
                    xticklabels=ETIQUETAS_CORTAS, yticklabels=ETIQUETAS_CORTAS)
        axes[0, j].set_title(f"{nombre}\n(absoluta)", fontsize=10)
        axes[1, j].set_title("normalizada por clase real", fontsize=10)
        for i in range(2):
            axes[i, j].set_xlabel("Predicho")
            axes[i, j].set_ylabel("Real")
    fig.suptitle("Matrices de confusión — conjunto de prueba (n=180)", fontsize=13)
    fig.tight_layout()
    fig.savefig(ruta, dpi=150, bbox_inches="tight")
    plt.close(fig)


def graficar_roc(salidas, y, ruta):
    fig, axes = plt.subplots(1, len(salidas), figsize=(4.6 * len(salidas), 4.4), sharey=True)
    y = np.asarray(y)
    for ax, (nombre, (_, proba)) in zip(axes, salidas.items()):
        for c, etiqueta in enumerate(ETIQUETAS_CORTAS):
            fpr, tpr, _ = roc_curve(y == c, proba[:, c])
            auc = roc_auc_score(y == c, proba[:, c])
            ax.plot(fpr, tpr, color=COLORES_CLASE[etiqueta], lw=2, label=f"{etiqueta} vs resto (AUC={auc:.3f})")
        ax.plot([0, 1], [0, 1], ls="--", color="grey", lw=1)
        ax.set_title(nombre, fontsize=10)
        ax.set_xlabel("Tasa de falsos positivos")
        ax.legend(loc="lower right", fontsize=8)
    axes[0].set_ylabel("Tasa de verdaderos positivos (sensibilidad)")
    fig.suptitle("Curvas ROC One-vs-Rest — conjunto de prueba", fontsize=13)
    fig.tight_layout()
    fig.savefig(ruta, dpi=150, bbox_inches="tight")
    plt.close(fig)


def graficar_comparacion(tabla, ruta):
    metricas = ["accuracy", "f1_macro", "f1_weighted", "recall_alto", "roc_auc_ovr_macro"]
    datos = tabla[metricas].reset_index().melt(id_vars="sistema", var_name="métrica", value_name="valor")
    fig, ax = plt.subplots(figsize=(11, 4.6))
    sns.barplot(data=datos, x="métrica", y="valor", hue="sistema", ax=ax, palette="Blues_d")
    ax.set_ylim(0, 1.08)
    for cont in ax.containers:
        ax.bar_label(cont, fmt="%.2f", fontsize=7, padding=1)
    ax.set_title("Comparación de sistemas — conjunto de prueba", pad=34)
    ax.legend(fontsize=8, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=4, frameon=False)
    fig.tight_layout()
    fig.savefig(ruta, dpi=150, bbox_inches="tight")
    plt.close(fig)


def auditoria_subgrupos(modelo, nombre_modelo):
    """Sesgo por subgrupo con predicciones fuera de fold (5-fold) sobre los 1.200 registros.

    Se usa validación cruzada en lugar del conjunto de prueba porque algunos subgrupos étnicos
    (Kogui, Wiwa) tendrían menos de 5 gestantes en prueba.
    """
    df = marcar_fuera_de_rango(cargar_dataset())
    X, y = separar_xy(df)
    estimador = modelo.estimator if hasattr(modelo, "estimator") else modelo
    pred = cross_val_predict(estimador, X, y, cv=CV, n_jobs=-1)
    pred[mascara_reglas(X)] = CLASE_ALTO
    filas = []
    for variable in ["area_residencia", "pertenencia_etnica", "departamento", "atendido_por"]:
        for grupo, idx in X.groupby(variable).groups.items():
            yy, pp = y.loc[idx].to_numpy(), pred[X.index.get_indexer(idx)]
            filas.append({
                "variable": variable, "grupo": grupo, "n": len(idx), "n_alto_real": int((yy == CLASE_ALTO).sum()),
                "accuracy": round(accuracy_score(yy, pp), 3),
                "f1_macro": round(f1_score(yy, pp, average="macro", zero_division=0), 3),
                "recall_alto": round(recall_score(yy, pp, labels=[CLASE_ALTO], average="macro", zero_division=0), 3),
            })
    tabla = pd.DataFrame(filas)
    tabla.insert(0, "sistema", f"Híbrido ({nombre_modelo} + reglas), predicción fuera de fold")
    return tabla


def evaluar_todo():
    DIR_FIGURAS.mkdir(parents=True, exist_ok=True)
    _, X_val, X_test, _, y_val, y_test = preparar_datos(guardar=False)
    modelos = cargar_modelos()

    # 1) Validación: selección del modelo que alimentará el sistema híbrido.
    salidas_val = predecir_sistemas(modelos, X_val)
    tabla_val = tabla_metricas(salidas_val, y_val)
    tabla_val.round(4).to_csv(DIR_METRICAS / "metricas_validacion.csv")
    hibridos = tabla_val.loc[tabla_val.index.str.startswith("Híbrido")]
    seleccionado = hibridos.sort_values(["f1_macro", "recall_alto"], ascending=False).index[0]
    modelo_principal = "SVM" if "SVM" in seleccionado else "Regresión Logística"

    # 2) Prueba: evaluación final, una sola vez.
    salidas = predecir_sistemas(modelos, X_test)
    tabla_test = tabla_metricas(salidas, y_test)
    for nombre, (pred, _) in salidas.items():
        for metrica, fn in [("recall_alto", lambda a, b: recall_score(a, b, labels=[CLASE_ALTO], average="macro", zero_division=0)),
                            ("f1_macro", lambda a, b: f1_score(a, b, average="macro", zero_division=0))]:
            lo, hi = intervalo_bootstrap(y_test, pred, fn)
            tabla_test.loc[nombre, f"{metrica}_ic95"] = f"[{lo:.3f}, {hi:.3f}]"
    tabla_test.round(4).to_csv(DIR_METRICAS / "metricas_test.csv")

    # 3) Subconjunto sin signos críticos: aporte real del modelo estadístico.
    sin_reglas = ~mascara_reglas(X_test)
    tabla_sin_reglas = tabla_metricas(salidas, y_test, mascara=sin_reglas)
    tabla_sin_reglas.round(4).to_csv(DIR_METRICAS / "metricas_test_sin_signos_criticos.csv")

    # 4) Gráficas
    graficar_matrices_confusion(salidas, y_test, DIR_FIGURAS / "matrices_confusion_test.png")
    graficar_roc(salidas, y_test, DIR_FIGURAS / "curvas_roc_test.png")
    graficar_comparacion(tabla_test, DIR_FIGURAS / "comparacion_sistemas_test.png")

    # 5) Auditoría de sesgos por subgrupo
    subgrupos = auditoria_subgrupos(modelos[modelo_principal], modelo_principal)
    subgrupos.to_csv(DIR_METRICAS / "auditoria_subgrupos.csv", index=False)

    resumen = {
        "modelo_principal_para_hibrido": modelo_principal,
        "criterio_seleccion": "Mayor F1-macro del sistema híbrido en validación (desempate: recall Alto Riesgo)",
        "n_test": int(len(y_test)),
        "n_alto_riesgo_test": int((y_test == CLASE_ALTO).sum()),
        "n_test_con_signos_criticos": int((~sin_reglas).sum()),
        "matriz_costo_clinico": MATRIZ_COSTO.tolist(),
    }
    with open(DIR_METRICAS / "resumen_evaluacion.json", "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)

    columnas = ["accuracy", "precision_macro", "recall_macro", "f1_macro", "f1_weighted", "roc_auc_ovr_macro",
                "recall_alto", "falsos_negativos_alto", "alto_clasificado_como_bajo", "costo_clinico_total"]
    pd.set_option("display.width", 250)
    print("VALIDACIÓN (n=180):\n", tabla_val[columnas].round(3), "\n")
    print(f"Modelo seleccionado para el sistema híbrido: {modelo_principal}\n")
    print("PRUEBA (n=180):\n", tabla_test[columnas + ["recall_alto_ic95", "f1_macro_ic95"]].round(3), "\n")
    print(f"PRUEBA sin signos críticos (n={sin_reglas.sum()}):\n",
          tabla_sin_reglas[["accuracy", "f1_macro", "recall_alto", "falsos_negativos_alto", "costo_clinico_total"]].round(3), "\n")
    print("AUDITORÍA DE SUBGRUPOS:\n", subgrupos.drop(columns="sistema").to_string(index=False))
    return tabla_test, tabla_sin_reglas, subgrupos, resumen


if __name__ == "__main__":
    evaluar_todo()
