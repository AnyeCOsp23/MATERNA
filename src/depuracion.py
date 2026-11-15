"""Fase 3 — Depuración de datos CRUDOS con etiqueta, paso a paso y con conteo antes y después.

Entra un archivo crudo (CSV, TXT con «|» o Excel) con las columnas del dataset de MATERNA y sale un conjunto
limpio, listo para partir y entrenar, más el reporte de lo que hizo cada paso:

  1. Estructura   columnas reconocidas; se descartan las vacías y las desconocidas.
  2. Centinelas   9999, 999 y 1845-01-01 significan «sin dato» y pasan a nulo.
  3. Tipos        números escritos como texto o con coma decimal, TRUE/FALSE, espacios sobrantes, clase.
  4. Rangos       un valor fisiológicamente imposible es un error de captura y pasa a nulo.
  5. Duplicados   filas idénticas (sin contar el identificador) se dejan una sola vez.
  6. Incompletos  sin clase o sin una variable obligatoria no se puede entrenar: la fila se retira.
  7. Imputación   glucosa y FCF faltantes NO se rellenan aquí: lo hace el pipeline, con la mediana por
                  área × trimestre aprendida solo con el entrenamiento (sin fuga de datos).

La lectura reutiliza src/inspeccionar_ips.leer_por_lotes (lotes de 5.000 filas, detección de codificación y
separador), así que sirve para archivos de decenas de miles de registros.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import MAPA_TARGET, TARGET, VARS_CATEGORICAS, VARS_CON_NULOS, VARS_CONTINUAS, VARS_DEMOGRAFICAS
from src.data_preprocessing import RANGOS_PLAUSIBLES
from src.generador_sintetico import COLUMNA_ORIGEN
from src.inspeccionar_ips import CENTINELAS, leer_por_lotes

ID = "id_gestante"
NUMERICAS = VARS_CONTINUAS + ["proteinuria"]
ENTERAS = [c for c in NUMERICAS if c not in VARS_CON_NULOS]
TEXTO = VARS_CATEGORICAS + VARS_DEMOGRAFICAS
OBLIGATORIAS = [c for c in NUMERICAS if c not in VARS_CON_NULOS] + ["convulsiones"] + VARS_CATEGORICAS + [TARGET]
COLUMNAS = [ID] + NUMERICAS + ["convulsiones"] + TEXTO + [TARGET, COLUMNA_ORIGEN]
BINARIO = {"true": 1, "verdadero": 1, "si": 1, "sí": 1, "1": 1, "1.0": 1, "false": 0, "falso": 0, "no": 0, "0": 0, "0.0": 0}


def contar_filas(ruta):
    """Filas de datos de un archivo de texto (para la barra de progreso). None si es Excel."""
    ruta = Path(ruta)
    if ruta.suffix.lower() == ".xlsx":
        return None
    with open(ruta, "rb") as f:
        return max(sum(bloque.count(b"\n") for bloque in iter(lambda: f.read(1 << 20), b"")) - 1, 1)


def leer_crudo(ruta, al_avanzar=lambda leidas, total: None):
    """Lee el archivo por lotes, todo como texto. Devuelve (datos, {'formato', 'separador', 'lotes', 'filas'})."""
    total = contar_filas(ruta)
    lotes, (formato, separador) = leer_por_lotes(ruta)
    partes, leidas = [], 0
    for lote in lotes:
        partes.append(lote)
        leidas += len(lote)
        al_avanzar(leidas, total)
    datos = pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()
    return datos, {"formato": formato, "separador": separador, "lotes": len(partes), "filas": len(datos)}


def _por_columna(conteo):
    return ", ".join(f"{k}: {v}" for k, v in conteo.items() if v) or "ninguno"


def depurar(crudo):
    """Devuelve (datos limpios, pasos). Cada paso: nombre, qué hizo, filas antes y después, celdas y detalle."""
    pasos = []

    def anotar(paso, que_hace, antes, df, celdas, detalle):
        pasos.append({"Paso": paso, "Qué hace": que_hace, "Filas antes": antes, "Filas después": len(df),
                      "Celdas cambiadas": int(celdas), "Detalle": detalle})

    # 1. Estructura
    df = crudo.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    vacias = [c for c in df.columns if c.startswith("unnamed") or df[c].isna().all()]
    desconocidas = [c for c in df.columns if c not in COLUMNAS and c not in vacias]
    faltan = [c for c in OBLIGATORIAS if c not in df.columns]
    if faltan:
        raise ValueError("El archivo no tiene las columnas obligatorias: " + ", ".join(faltan) + ".")
    df = df[[c for c in COLUMNAS if c in df.columns]].copy()
    for c in VARS_CON_NULOS:
        if c not in df:
            df[c] = None
    anotar("1. Estructura", "Reconoce las columnas y descarta las vacías y las desconocidas", len(crudo), df, 0,
           f"{len(df.columns)} columnas reconocidas; descartadas: {', '.join(vacias + desconocidas) or 'ninguna'}")

    # 2. Centinelas
    antes, conteo = len(df), {}
    for c in df.columns.drop(ID, errors="ignore"):
        es = df[c].astype("string").str.strip().isin(CENTINELAS)
        conteo[c] = int(es.sum())
        df[c] = df[c].where(~es, None)
    anotar("2. Centinelas", f"Los valores {', '.join(sorted(CENTINELAS))} significan «sin dato» y pasan a nulo",
           antes, df, sum(conteo.values()), _por_columna(conteo))

    # 3. Tipos
    conteo = {}
    for c in NUMERICAS:
        texto = df[c].astype("string").str.strip()
        con_coma = texto.str.contains(",", na=False)
        numero = pd.to_numeric(texto.str.replace(",", ".", regex=False), errors="coerce")
        conteo[f"{c} (coma decimal)"] = int(con_coma.sum())
        conteo[f"{c} (no es un número)"] = int((numero.isna() & texto.notna() & (texto != "")).sum())
        df[c] = numero
    texto = df["convulsiones"].astype("string").str.strip().str.lower()
    binario = texto.map(BINARIO)
    conteo["convulsiones (texto a 1/0)"] = int(texto.isin(["true", "false", "verdadero", "falso", "si", "sí", "no"]).sum())
    conteo["convulsiones (valor no reconocido)"] = int((binario.isna() & texto.notna()).sum())
    df["convulsiones"] = binario
    espacios = 0
    for c in [c for c in TEXTO + [TARGET, ID, COLUMNA_ORIGEN] if c in df]:
        original = df[c].astype("string")
        limpio = original.str.strip()
        espacios += int((original != limpio).fillna(False).sum())
        df[c] = limpio.replace("", pd.NA)
    conteo["textos con espacios sobrantes"] = espacios
    clase_rara = df[TARGET].notna() & ~df[TARGET].isin(MAPA_TARGET)
    conteo["clase no reconocida"] = int(clase_rara.sum())
    df[TARGET] = df[TARGET].where(~clase_rara, pd.NA)
    anotar("3. Tipos", "Convierte textos a números, la coma decimal a punto, TRUE/FALSE a 1/0 y quita espacios",
           antes, df, sum(conteo.values()), _por_columna(conteo))

    # 4. Rangos fisiológicos
    conteo = {}
    for c, (lo, hi) in RANGOS_PLAUSIBLES.items():
        fuera = (df[c] < lo) | (df[c] > hi)
        conteo[c] = int(fuera.sum())
        df.loc[fuera, c] = np.nan
    anotar("4. Rangos", "Un valor fisiológicamente imposible es un error de captura y pasa a nulo",
           antes, df, sum(conteo.values()), _por_columna(conteo))

    # 5. Duplicados
    df = df.drop_duplicates(subset=[c for c in df.columns if c != ID], ignore_index=True)
    anotar("5. Duplicados", "Deja una sola vez las filas idénticas (sin contar el identificador)",
           antes, df, 0, f"{antes - len(df)} fila(s) repetida(s) retirada(s)")

    # 6. Incompletos
    antes = len(df)
    nulos = df[OBLIGATORIAS].isna()
    df = df[~nulos.any(axis=1)].reset_index(drop=True)
    anotar("6. Incompletos", "Retira las filas sin clase o sin una variable obligatoria: no sirven para entrenar",
           antes, df, 0, _por_columna({c: int(n) for c, n in nulos.sum().items()}))

    # 7. Imputación (no se rellena aquí)
    for c in ENTERAS + ["convulsiones"]:
        df[c] = df[c].astype(int)
    for c in VARS_CON_NULOS:
        df[c] = df[c].astype(float)
    for c in [c for c in TEXTO + [TARGET, ID, COLUMNA_ORIGEN] if c in df]:
        df[c] = df[c].astype(object).where(df[c].notna(), None)
    if ID not in df:
        df.insert(0, ID, [f"R{i:06d}" for i in range(1, len(df) + 1)])
    faltantes = {c: int(df[c].isna().sum()) for c in VARS_CON_NULOS}
    anotar("7. Imputación", "Glucosa y FCF faltantes se rellenan dentro del pipeline, con la mediana por área × "
           "trimestre aprendida solo con el entrenamiento", len(df), df, 0,
           "quedan para imputar: " + _por_columna(faltantes))
    return df, pasos


def reporte(pasos):
    return pd.DataFrame(pasos)
