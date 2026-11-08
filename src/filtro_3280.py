"""Fase 3 — Filtro de variables según la Ruta Materno Perinatal (Resolución 3280 de 2018).

Lee el catálogo config/variables_3280.json y decide qué hacer con cada columna de un archivo:
  - modelo            entra al Random Forest + reglas (las 11 variables de la Fase 2);
  - capturar_alertar  se conserva y puede disparar una alerta de la ruta, pero NO entra al modelo;
  - auditoria         etnia y territorio: solo para auditar sesgos;
  - seudonimizar      documento de identidad -> id_seudonimo (ver seudonimizacion.py);
  - eliminar          datos personales y administrativos.
Las columnas que el catálogo no reconoce se descartan (privacidad por defecto) y se informan.

Las alertas de la ruta no entran al modelo. Los signos de alarma obstétricos ("escala_a_alto" en el catálogo)
elevan el triaje FINAL a Alto Riesgo, como las reglas críticas: ver clinical_rules.evaluar_riesgo_hibrido.
"""
import json
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np
import pandas as pd

from src.config import RAIZ, VARS_CATEGORICAS, VARS_CONTINUAS
from src.seudonimizacion import seudonimizar_dataframe

RUTA_CATALOGO = RAIZ / "config" / "variables_3280.json"
DECISIONES = ("modelo", "capturar_alertar", "auditoria", "seudonimizar", "eliminar")
VALORES_VERDADERO = {"1", "si", "s", "true", "verdadero", "x", "positivo", "reactivo"}
VALORES_FALSO = {"0", "no", "n", "false", "falso", "negativo", "no reactivo"}


@lru_cache(maxsize=1)
def cargar_catalogo(ruta=RUTA_CATALOGO):
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def variables(decision=None):
    """Entradas del catálogo, opcionalmente filtradas por decisión."""
    return [v for v in cargar_catalogo()["variables"] if decision is None or v["decision"] == decision]


def nombres(decision):
    return [v["nombre"] for v in variables(decision)]


def tabla_decisiones():
    """Tabla explicativa para la consola web: variable, sección, decisión, justificación y verificación."""
    cat = cargar_catalogo()
    filas = [
        {
            "Variable": v["etiqueta"],
            "Columna": v["nombre"],
            "Sección 3280": v["seccion"],
            "Decisión": v["decision"],
            "Justificación": v["justificacion"],
            "Verificación": cat["_verificacion"][v["verificacion"]],
        }
        for v in cat["variables"]
    ]
    orden = {d: i for i, d in enumerate(DECISIONES)}
    return pd.DataFrame(filas).sort_values("Decisión", key=lambda s: s.map(orden), kind="stable").reset_index(drop=True)


def normalizar_nombre(texto):
    """'Presión Sistólica ' -> 'presion_sistolica'."""
    texto = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode("ascii")
    return "_".join(texto.strip().lower().replace("-", " ").replace("/", " ").split())


@lru_cache(maxsize=1)
def _mapa_sinonimos():
    mapa = {}
    for v in variables():
        for alias in [v["nombre"], *v.get("sinonimos", [])]:
            clave = normalizar_nombre(alias)
            if clave in mapa and mapa[clave] != v["nombre"]:
                raise ValueError(f"Sinónimo repetido en el catálogo: {alias}")
            mapa[clave] = v["nombre"]
    return mapa


def mapear_columnas(columnas):
    """{columna original: nombre del catálogo}; las no reconocidas quedan fuera."""
    mapa = _mapa_sinonimos()
    return {c: mapa[normalizar_nombre(c)] for c in columnas if normalizar_nombre(c) in mapa}


def _a_binaria(serie):
    texto = serie.astype("string").str.strip().str.lower()
    texto = texto.map(lambda t: normalizar_nombre(t).replace("_", " ") if isinstance(t, str) else t)
    return pd.Series(np.where(texto.isin(VALORES_VERDADERO), 1.0, np.where(texto.isin(VALORES_FALSO), 0.0, np.nan)),
                     index=serie.index)


def _a_categoria(serie, valores):
    canonicos = {normalizar_nombre(v): v for v in valores}
    return serie.map(lambda t: canonicos.get(normalizar_nombre(t)) if pd.notna(t) else None)


def convertir_tipos(df):
    """Convierte cada columna al tipo del catálogo. Lo que no se puede convertir queda nulo.

    Devuelve (df, fuera_de_rango) con el conteo de valores fuera del rango fisiológico, que también
    se vuelven nulos (igual que marcar_fuera_de_rango de la Fase 2).
    """
    df = df.copy()
    fuera_de_rango = {}
    por_nombre = {v["nombre"]: v for v in variables()}
    for col in df.columns:
        v = por_nombre.get(col)
        if v is None:
            continue
        if v["tipo"] in ("entero", "decimal"):
            texto = df[col].astype("string").str.strip().str.replace(",", ".", regex=False)
            df[col] = pd.to_numeric(texto, errors="coerce").astype(float)
            if "rango" in v:
                lo, hi = v["rango"]
                fuera = (df[col] < lo) | (df[col] > hi)
                if fuera.any():
                    fuera_de_rango[col] = int(fuera.sum())
                    df.loc[fuera, col] = np.nan
        elif v["tipo"] == "binaria":
            df[col] = _a_binaria(df[col])
        elif v["tipo"] == "categorica" and "valores" in v:
            df[col] = _a_categoria(df[col], v["valores"])
        elif v["tipo"] == "fecha":
            df[col] = pd.to_datetime(df[col], errors="coerce", format="%Y-%m-%d")
    return df, fuera_de_rango


@dataclass
class ResultadoFiltro:
    datos: pd.DataFrame
    columnas_por_decision: dict
    columnas_eliminadas: list
    columnas_desconocidas: list
    fuera_de_rango: dict = field(default_factory=dict)


def aplicar_filtro(df, sal):
    """Renombra según el catálogo, seudonimiza, descarta lo eliminable y lo desconocido y convierte tipos."""
    mapeo = mapear_columnas(df.columns)
    desconocidas = [c for c in df.columns if c not in mapeo]
    df = df[list(mapeo)].rename(columns=mapeo)
    df = df.loc[:, ~df.columns.duplicated()]

    decision = {v["nombre"]: v["decision"] for v in variables()}
    eliminadas = [c for c in df.columns if decision[c] == "eliminar"]
    df = df.drop(columns=eliminadas)
    if "numero_documento" in df:
        df = seudonimizar_dataframe(df, sal)
    else:
        df = df.drop(columns=[c for c in df.columns if decision.get(c) == "seudonimizar"])

    df, fuera = convertir_tipos(df)
    por_decision = {d: [c for c in df.columns if decision.get(c) == d] for d in DECISIONES if d not in ("seudonimizar", "eliminar")}
    return ResultadoFiltro(df, por_decision, eliminadas, desconocidas, fuera)


def variables_modelo():
    """Las 11 variables de entrada del modelo según el catálogo (deben coincidir con src/config.py)."""
    return nombres("modelo")


def variables_modelo_config():
    return VARS_CONTINUAS + ["proteinuria", "convulsiones"] + VARS_CATEGORICAS


# ----------------------------------------------------------------- alertas de la ruta
def _cumple(alerta, valor, semanas):
    condicion = alerta["condicion"]
    if condicion == "pendiente_desde_semana":
        # Se alerta si el suplemento o la vacuna NO se ha dado y ya pasó la semana indicada
        return semanas is not None and semanas >= alerta["umbral"] and valor == 0
    if valor is None:
        return False
    if condicion == "verdadero":
        return bool(valor)
    if condicion == "menor_que":
        return valor < alerta["umbral"]
    if condicion == "mayor_igual":
        return valor >= alerta["umbral"]
    raise ValueError(f"Condición de alerta desconocida: {condicion}")


def signos_alarma_que_escalan(registro):
    """Variables cuya alerta se activa y que, por ser signos de alarma obstétricos, elevan el triaje a Alto Riesgo."""
    escalan = {v["nombre"] for v in variables("capturar_alertar") if v.get("alerta", {}).get("escala_a_alto")}
    return [a["variable"] for a in evaluar_alertas_3280(registro) if a["variable"] in escalan]


def evaluar_alertas_3280(registro):
    """Alertas de la ruta para un registro (dict). No modifican la predicción del modelo.

    Devuelve una lista de dicts {variable, etiqueta, severidad, mensaje, verificada}, de la más
    a la menos urgente. 'verificada' es False cuando el corte es un criterio clínico por validar.
    """
    semanas = registro.get("semanas_gestacion")
    semanas = None if semanas is None or pd.isna(semanas) else float(semanas)
    orden = {"urgente": 0, "atencion": 1, "seguimiento": 2}
    alertas = []
    for v in variables("capturar_alertar"):
        alerta = v.get("alerta")
        if alerta is None or v["nombre"] not in registro:
            continue
        valor = registro[v["nombre"]]
        valor = None if valor is None or pd.isna(valor) else float(valor)
        if _cumple(alerta, valor, semanas):
            alertas.append({
                "variable": v["nombre"],
                "etiqueta": v["etiqueta"],
                "severidad": alerta["severidad"],
                "mensaje": alerta["mensaje"],
                "verificada": v["verificacion"] != "criterio_clinico_por_validar",
            })
    return sorted(alertas, key=lambda a: orden[a["severidad"]])
