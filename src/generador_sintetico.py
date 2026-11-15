"""Fase 3 — Generador sintético: N registros nuevos a partir de las 1.200 gestantes de la Fase 1.

Sirve para DEMOSTRAR ESCALABILIDAD (cargar, depurar y entrenar con 5.000 a 30.000 registros o más), no para
validar clínicamente: generar más registros sintéticos no agrega evidencia. Todo registro generado lleva la
columna origen = "sintetico_generado".

Método (nada de cifras inventadas: todo sale de las 1.200):
  1. Se elige al azar, con reemplazo, un registro base. Así se conservan las proporciones reales de clase,
     área, etnia, quién atiende, etc.
  2. Se elige uno de sus 5 vecinos más parecidos de la MISMA clase y la MISMA área de residencia.
  3. Las variables continuas (edad, semanas, controles, presión, FCF, glucosa) se interpolan entre los dos,
     como hace SMOTE; las demás (proteinuria, convulsiones, territorio, etnia, quién atiende) se copian del base.
  4. Si al registro base le faltaba glucosa o FCF, al generado también: se conserva la tasa de datos faltantes.

Etiqueta: el script que etiquetó el dataset de la Fase 1 no existe y sus criterios no se pueden reconstruir
completos, así que cada registro generado CONSERVA LA CLASE de su registro base. Como se interpola entre dos
gestantes de la misma clase, un registro que no es de Alto Riesgo nunca recibe un signo crítico (la presión
interpolada queda entre dos valores por debajo del umbral, y proteinuria y convulsiones se copian).

`ensuciar` agrega errores de captura simulados (centinelas, valores imposibles, duplicados, textos mal
escritos) para demostrar la depuración dentro del aplicativo; sus tasas son de demostración.

Uso:  python -m src.generador_sintetico 10000 --semilla 42 --salida data/salidas/sintetico_10000.txt [--crudo]
"""
import argparse

import numpy as np
import pandas as pd

from src.config import SEMILLA, TARGET, VARS_CON_NULOS, VARS_CONTINUAS
from src.data_preprocessing import cargar_dataset

ORIGEN = "sintetico_generado"
COLUMNA_ORIGEN = "origen"
K_VECINOS = 5
SEPARADOR = "|"
# Tasas de los errores de captura simulados (solo para la demostración de la depuración)
SUCIEDAD = {
    "centinela_opcional": 0.01,     # glucosa o FCF con 9999
    "centinela_obligatoria": 0.003,  # presión sistólica con 999
    "fuera_de_rango": 0.005,        # edad o semanas imposibles
    "duplicados": 0.01,             # filas repetidas
    "coma_decimal": 0.01,           # 113,4 en lugar de 113.4
    "sin_etiqueta": 0.002,          # clase vacía
}


def _vecinos(base):
    """Para cada registro, los índices de sus K vecinos más parecidos de la misma clase y área."""
    vecinos = np.empty((len(base), K_VECINOS), dtype=int)
    for _, grupo in base.groupby([TARGET, "area_residencia"]):
        valores = grupo[VARS_CONTINUAS].astype(float)
        valores = valores.fillna(valores.median())
        z = ((valores - valores.mean()) / valores.std(ddof=0).replace(0, 1)).to_numpy()
        distancias = np.linalg.norm(z[:, None, :] - z[None, :, :], axis=2)
        np.fill_diagonal(distancias, np.inf)
        posiciones = np.argsort(distancias, axis=1, kind="stable")[:, :K_VECINOS]
        vecinos[base.index.get_indexer(grupo.index)] = base.index.get_indexer(grupo.index)[posiciones]
    return vecinos


def generar(n, semilla=SEMILLA, base=None):
    """N registros con las columnas del dataset más `origen`. Reproducible: misma semilla, mismo resultado."""
    if n < 1:
        raise ValueError("El número de registros debe ser al menos 1.")
    base = (cargar_dataset() if base is None else base).reset_index(drop=True)
    rng = np.random.default_rng(semilla)
    elegidos = rng.integers(0, len(base), n)
    vecino = _vecinos(base)[elegidos, rng.integers(0, K_VECINOS, n)]
    paso = rng.random(n)

    nuevo = base.iloc[elegidos].reset_index(drop=True).copy()
    for col in VARS_CONTINUAS:
        a, b = base[col].to_numpy(float)[elegidos], base[col].to_numpy(float)[vecino]
        valor = a + paso * (np.where(np.isnan(b), a, b) - a)  # si al base le falta el dato, sigue faltando
        if col in VARS_CON_NULOS:
            nuevo[col] = np.round(valor, 1)
        else:
            nuevo[col] = np.rint(valor).astype(base[col].dtype)
    nuevo["id_gestante"] = [f"SG{i:06d}" for i in range(1, n + 1)]
    nuevo[COLUMNA_ORIGEN] = ORIGEN
    return nuevo


def ensuciar(datos, semilla=SEMILLA):
    """Versión CRUDA, en texto, con errores de captura simulados. Devuelve (crudo, conteo de lo inyectado)."""
    rng = np.random.default_rng(semilla + 1)
    crudo = datos.copy()
    n = len(crudo)

    def filas(tasa):
        return rng.choice(n, size=int(round(n * tasa)), replace=False)

    crudo["convulsiones"] = crudo["convulsiones"].map({1: "TRUE", 0: "FALSE"})
    crudo = pd.DataFrame({col: pd.Series([None if pd.isna(v) else str(v) for v in crudo[col]], dtype=object)
                          for col in crudo.columns})
    inyectado = {}

    idx = filas(SUCIEDAD["coma_decimal"])
    col = crudo.columns.get_loc("glucosa_mgdl")
    con_dato = [i for i in idx if isinstance(crudo.iat[i, col], str)]
    for i in con_dato:
        crudo.iat[i, col] = crudo.iat[i, col].replace(".", ",")
    inyectado["Decimales con coma"] = len(con_dato)

    for nombre, columna in [("glucosa_mgdl", "glucosa_mgdl"), ("fcf_bpm", "fcf_bpm")]:
        idx = filas(SUCIEDAD["centinela_opcional"] / 2)
        crudo.iloc[idx, crudo.columns.get_loc(columna)] = "9999"
        inyectado[f"Centinela 9999 en {nombre}"] = len(idx)
    idx = filas(SUCIEDAD["centinela_obligatoria"])
    crudo.iloc[idx, crudo.columns.get_loc("pas_mmhg")] = "999"
    inyectado["Centinela 999 en pas_mmhg"] = len(idx)

    for columna, imposible in [("edad", "99"), ("semanas_gestacion", "60")]:
        idx = filas(SUCIEDAD["fuera_de_rango"] / 2)
        crudo.iloc[idx, crudo.columns.get_loc(columna)] = imposible
        inyectado[f"Valor imposible en {columna}"] = len(idx)

    idx = filas(SUCIEDAD["sin_etiqueta"])
    crudo.iloc[idx, crudo.columns.get_loc(TARGET)] = None
    inyectado["Sin etiqueta de riesgo"] = len(idx)

    crudo["area_residencia"] = [f" {v} " if i % 50 == 0 else v for i, v in enumerate(crudo["area_residencia"])]

    idx = filas(SUCIEDAD["duplicados"])
    crudo = pd.concat([crudo, crudo.iloc[idx]], ignore_index=True)
    inyectado["Filas duplicadas"] = len(idx)
    crudo = crudo.sample(frac=1, random_state=semilla).reset_index(drop=True)  # los duplicados no quedan al final
    return crudo, inyectado


def a_texto(datos):
    """El archivo plano como lo entregaría un sistema de información: .txt separado por «|»."""
    return datos.to_csv(index=False, sep=SEPARADOR)


def main():
    parser = argparse.ArgumentParser(description="Genera registros sintéticos a partir de las 1.200 gestantes")
    parser.add_argument("n", type=int)
    parser.add_argument("--semilla", type=int, default=SEMILLA)
    parser.add_argument("--salida", required=True)
    parser.add_argument("--crudo", action="store_true", help="con errores de captura simulados")
    args = parser.parse_args()
    datos = generar(args.n, args.semilla)
    if args.crudo:
        datos, inyectado = ensuciar(datos, args.semilla)
        print("Errores simulados:", inyectado)
    with open(args.salida, "w", encoding="utf-8", newline="") as f:
        f.write(a_texto(datos))
    print(f"{len(datos)} filas en {args.salida}")


if __name__ == "__main__":
    main()
