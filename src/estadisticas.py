"""Fase 3 — Estadísticas descriptivas del EDA (fase 03): media, mediana, moda, desviación estándar y cuartiles.

Se calculan sobre los datos con que se entrena HOY: el conjunto de trabajo activo (o el dataset base) más los
patrones nuevos agregados a mano. Como la página se vuelve a calcular en cada interacción, la tabla se actualiza
sola al agregar o retirar un patrón (fase 02) o al cambiar el conjunto de trabajo (fase 04).
"""
import pandas as pd

# Vienen con decimales: su moda se calcula con los valores redondeados a enteros (si no, casi todos serían únicos)
REDONDEAR_PARA_MODA = ("fcf_bpm", "glucosa_mgdl")


def combinar(datos, nuevos):
    """Los datos más los patrones nuevos (solo las columnas en común)."""
    if nuevos is None or nuevos.empty:
        return datos
    comunes = [c for c in datos.columns if c in nuevos.columns]
    return pd.concat([datos, nuevos[comunes]], ignore_index=True)


def moda(serie, redondear=False):
    """(valor más frecuente, cuántas veces aparece). Si hay empate, el menor. (None, 0) si no hay datos."""
    valores = serie.dropna()
    if redondear:
        valores = valores.round()
    if valores.empty:
        return None, 0
    conteo = valores.value_counts()
    maximo = conteo.max()
    return float(min(conteo[conteo == maximo].index)), int(maximo)


def descriptivas(datos, etiquetas):
    """Una fila por variable numérica: N, media, mediana, moda, desviación estándar (muestral), cuartiles y % de nulos."""
    filas = []
    for columna, nombre in etiquetas.items():
        if columna not in datos:
            continue
        serie = pd.to_numeric(datos[columna], errors="coerce")
        validos = serie.dropna()
        valor_moda, veces = moda(validos, columna in REDONDEAR_PARA_MODA)
        filas.append({
            "Variable": nombre, "N": int(validos.count()), "Media": validos.mean(), "Mediana": validos.median(),
            "Moda": valor_moda, "Veces (moda)": veces, "Desv. estándar": validos.std(),
            "Mínimo": validos.min(), "Q1": validos.quantile(0.25), "Q3": validos.quantile(0.75), "Máximo": validos.max(),
            "% nulos": serie.isna().mean() * 100 if len(serie) else 0.0,
        })
    return pd.DataFrame(filas).round(2)


# Mediciones continuas: en ellas, que la moda caiga justo en el mínimo delata un piso artificial. En las discretas
# (proteinuria, controles) es natural: la mayoría tiene 0.
CONTINUAS = ("pas_mmhg", "pad_mmhg", "fcf_bpm", "glucosa_mgdl")


def moda_en_el_minimo(tabla, etiquetas):
    """Mediciones continuas cuya moda es su valor mínimo (suele indicar valores recortados al generar o capturar)."""
    continuas = {etiquetas[c] for c in CONTINUAS if c in etiquetas}
    return [f["Variable"] for _, f in tabla.iterrows()
            if f["Variable"] in continuas and pd.notna(f["Moda"]) and f["Moda"] == f["Mínimo"] and f["Veces (moda)"] > 1]
