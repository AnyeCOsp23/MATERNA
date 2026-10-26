"""Sub-fase 2.1 — Carga, limpieza, imputación, escalado, codificación y partición del dataset.

Todas las transformaciones que aprenden parámetros de los datos (medianas de imputación,
cuantiles del RobustScaler, categorías del One-Hot) viven dentro de un Pipeline de sklearn.
Así se ajustan solo con el conjunto de entrenamiento (y con cada fold en validación cruzada),
evitando fuga de información hacia validación y prueba.

Uso:  python -m src.data_preprocessing
"""
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, RobustScaler

from src.config import (
    DIR_PROCESADOS, MAPA_TARGET, RUTA_DATASET, SEMILLA, TARGET, VARS_CATEGORICAS,
    VARS_CON_NULOS, VARS_CONTINUAS, VARS_DEMOGRAFICAS, VARS_DISCRETAS,
)

# Rangos fisiológicamente plausibles para detectar errores de captura (no outliers clínicos).
# Un valor fuera de estos rangos se considera error y se marca como nulo.
RANGOS_PLAUSIBLES = {
    "edad": (10, 55),
    "semanas_gestacion": (4, 42),
    "n_controles_prenatales": (0, 20),
    "pas_mmhg": (60, 250),
    "pad_mmhg": (30, 150),
    "fcf_bpm": (60, 220),
    "glucosa_mgdl": (30, 600),
    "proteinuria": (0, 4),
}


def cargar_dataset(ruta=RUTA_DATASET):
    """Lee el CSV y aplica la limpieza estructural (sin aprender nada de los datos)."""
    df = pd.read_csv(ruta)
    # El CSV original termina cada línea en coma, lo que genera una columna vacía 'Unnamed: 16'
    df = df.loc[:, ~df.columns.str.startswith("Unnamed")]
    df["convulsiones"] = df["convulsiones"].astype(str).str.upper().map({"TRUE": 1, "FALSE": 0}).astype(int)
    for col in df.select_dtypes(include=["object", "string"]).columns:
        df[col] = df[col].str.strip()
    return df


def reporte_calidad(df):
    """Resumen de calidad: nulos, duplicados y valores fuera de rango fisiológico."""
    fuera_rango = {
        col: int(((df[col] < lo) | (df[col] > hi)).sum()) for col, (lo, hi) in RANGOS_PLAUSIBLES.items()
    }
    return {
        "registros": len(df),
        "columnas": df.shape[1],
        "ids_duplicados": int(df["id_gestante"].duplicated().sum()),
        "filas_duplicadas_sin_id": int(df.drop(columns="id_gestante").duplicated().sum()),
        "nulos": df.isna().sum()[lambda s: s > 0].to_dict(),
        "pct_nulos": (df.isna().mean() * 100).round(2)[lambda s: s > 0].to_dict(),
        "fuera_de_rango_fisiologico": {k: v for k, v in fuera_rango.items() if v > 0},
        "distribucion_target": df[TARGET].value_counts().to_dict(),
    }


def marcar_fuera_de_rango(df):
    """Convierte en NaN los valores fisiológicamente imposibles para que el imputador los trate."""
    df = df.copy()
    for col, (lo, hi) in RANGOS_PLAUSIBLES.items():
        df.loc[(df[col] < lo) | (df[col] > hi), col] = np.nan
    return df


def trimestre(semanas):
    return pd.cut(semanas, bins=[0, 13, 27, 45], labels=["T1", "T2", "T3"]).astype(str)


class MedianaEstratificadaImputer(BaseEstimator, TransformerMixin):
    """Imputa con la mediana del estrato (área de residencia × trimestre gestacional).

    - Las medianas se aprenden solo en `fit` (entrenamiento), nunca con datos de validación o prueba.
    - Si un estrato tiene menos de `min_tamano` observaciones válidas, se usa la mediana por área
      y, si tampoco alcanza, la mediana global.
    - Agrega una columna indicadora `<variable>_no_disponible`: en campo, la ausencia de glucometría
      o de doppler fetal es en sí misma información sobre el acceso a la atención.
    """

    NOMBRES_INDICADOR = {"glucosa_mgdl": "glucosa_no_disponible", "fcf_bpm": "fcf_no_disponible"}

    def __init__(self, columnas=tuple(VARS_CON_NULOS), min_tamano=10):
        self.columnas = columnas
        self.min_tamano = min_tamano

    def _estratos(self, X):
        return X["area_residencia"].astype(str), trimestre(X["semanas_gestacion"])

    def fit(self, X, y=None):
        area, tri = self._estratos(X)
        self.mediana_global_, self.mediana_area_, self.mediana_estrato_ = {}, {}, {}
        for col in self.columnas:
            serie = X[col]
            self.mediana_global_[col] = serie.median()
            por_area = serie.groupby(area).agg(["median", "count"])
            self.mediana_area_[col] = por_area.loc[por_area["count"] >= self.min_tamano, "median"].to_dict()
            por_estrato = serie.groupby([area, tri]).agg(["median", "count"])
            self.mediana_estrato_[col] = por_estrato.loc[por_estrato["count"] >= self.min_tamano, "median"].to_dict()
        self.feature_names_in_ = np.array(X.columns)
        return self

    def transform(self, X):
        X = X.copy()
        area, tri = self._estratos(X)
        for col in self.columnas:
            faltante = X[col].isna()
            X[self.NOMBRES_INDICADOR.get(col, f"{col}_no_disponible")] = faltante.astype(int)
            valores = [
                self.mediana_estrato_[col].get((a, t), self.mediana_area_[col].get(a, self.mediana_global_[col]))
                for a, t in zip(area[faltante], tri[faltante])
            ]
            X.loc[faltante, col] = valores
        return X

    def get_feature_names_out(self, input_features=None):
        extra = [self.NOMBRES_INDICADOR.get(c, f"{c}_no_disponible") for c in self.columnas]
        return np.array(list(self.feature_names_in_) + extra)


def columnas_modelo(incluir_demograficas=False):
    categoricas = VARS_CATEGORICAS + (VARS_DEMOGRAFICAS if incluir_demograficas else [])
    return VARS_CONTINUAS, VARS_DISCRETAS, categoricas


def pasos_preprocesamiento(incluir_demograficas=False):
    """Pasos: imputación estratificada -> RobustScaler (continuas) + One-Hot (categóricas).

    Se devuelven como lista para poder insertarlos en un Pipeline de imbalanced-learn,
    que no admite Pipelines anidados antes del paso de SMOTE.
    """
    continuas, discretas, categoricas = columnas_modelo(incluir_demograficas)
    transformador = ColumnTransformer(
        [
            ("continuas", RobustScaler(), continuas),
            ("discretas", "passthrough", discretas),
            ("categoricas", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categoricas),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )
    return [("imputacion", MedianaEstratificadaImputer()), ("transformacion", transformador)]


def construir_preprocesador(incluir_demograficas=False):
    return Pipeline(pasos_preprocesamiento(incluir_demograficas))


def separar_xy(df):
    """X conserva todas las columnas útiles (el preprocesador elige cuáles usar); y es ordinal 0/1/2."""
    X = df.drop(columns=["id_gestante", TARGET])
    y = df[TARGET].map(MAPA_TARGET).astype(int)
    return X, y


def particionar(X, y, semilla=SEMILLA):
    """Partición estratificada 70 % entrenamiento / 15 % validación / 15 % prueba."""
    X_train, X_tmp, y_train, y_tmp = train_test_split(X, y, test_size=0.30, stratify=y, random_state=semilla)
    X_val, X_test, y_val, y_test = train_test_split(X_tmp, y_tmp, test_size=0.50, stratify=y_tmp, random_state=semilla)
    return X_train, X_val, X_test, y_train, y_val, y_test


def preparar_datos(guardar=True):
    """Ejecuta la sub-fase 2.1 completa y devuelve las particiones (sin imputar: eso ocurre en el Pipeline)."""
    df = cargar_dataset()
    df = marcar_fuera_de_rango(df)
    X, y = separar_xy(df)
    particiones = particionar(X, y)
    if guardar:
        DIR_PROCESADOS.mkdir(parents=True, exist_ok=True)
        for nombre, Xp, yp in zip(["train", "val", "test"], particiones[:3], particiones[3:]):
            Xp.assign(**{TARGET: yp}).to_csv(DIR_PROCESADOS / f"{nombre}.csv", index_label="indice_original")
    return particiones


if __name__ == "__main__":
    df = cargar_dataset()
    for clave, valor in reporte_calidad(df).items():
        print(f"{clave}: {valor}")
    X_train, X_val, X_test, y_train, y_val, y_test = preparar_datos()
    print("\nPartición estratificada:")
    for nombre, yp in [("train", y_train), ("val", y_val), ("test", y_test)]:
        print(f"  {nombre:5s} n={len(yp):4d}  proporciones={yp.value_counts(normalize=True).sort_index().round(3).to_dict()}")
    pre = construir_preprocesador().fit(X_train)
    print("\nVariables de entrada al modelo:", list(pre.get_feature_names_out()))
