"""Fase 3 — Ingesta e inspección de archivos de una IPS (CSV/TXT o Excel .xlsx).

Lee el archivo por lotes (sirve para archivos grandes), detecta la codificación (utf-8 o latin-1)
y el separador ('|', ',', ';' o tabulador), convierte los valores centinela en nulos, aplica el
filtro de la Resolución 3280 (src/filtro_3280.py) y seudonimiza los documentos.

El reporte dice cuántos registros son aptos para el modelo: las 11 variables de entrada, aceptando
glucosa y FCF faltantes porque el pipeline las imputa.

Uso:  set MATERNA_SAL=<sal secreta>
      python -m src.inspeccionar_ips data/ejemplos/ips_ficticio_3280.csv --salida data/salidas/ips_seudonimizado.csv
(data/salidas/ está en .gitignore: los datos de una IPS no se versionan.)
"""
import argparse
import codecs
import csv
import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from src.config import VARS_CON_NULOS
from src.filtro_3280 import aplicar_filtro, mapear_columnas, variables, variables_modelo
from src.seudonimizacion import COLUMNA_SEUDONIMO, obtener_sal

# Valores que los sistemas de información usan para decir "sin dato" (p. ej. la Resolución 4505)
CENTINELAS = {"1845-01-01", "9999", "999"}
TAM_LOTE = 5000
BYTES_MUESTRA = 1 << 20


def detectar_codificacion(ruta):
    muestra = Path(ruta).read_bytes()[:BYTES_MUESTRA]
    try:
        codecs.getincrementaldecoder("utf-8")().decode(muestra, final=False)
        return "utf-8-sig"
    except UnicodeDecodeError:
        return "latin-1"


def detectar_separador(ruta, codificacion):
    with open(ruta, encoding=codificacion, newline="") as f:
        muestra = "".join(f.readline() for _ in range(20))
    try:
        return csv.Sniffer().sniff(muestra, delimiters="|,;\t").delimiter
    except csv.Error:
        return ","


def _celda_a_texto(valor):
    if valor is None:
        return None
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))  # 1065432.0 -> '1065432' (documentos guardados como número)
    if isinstance(valor, (dt.datetime, dt.date)):
        return valor.strftime("%Y-%m-%d")
    return str(valor)


def _lotes_excel(ruta, tam_lote):
    from openpyxl import load_workbook

    libro = load_workbook(ruta, read_only=True, data_only=True)
    try:
        filas = libro.worksheets[0].iter_rows(values_only=True)
        encabezado = [str(c).strip() if c is not None else f"columna_{i}" for i, c in enumerate(next(filas))]
        lote = []
        for fila in filas:
            if all(c is None for c in fila):
                continue
            lote.append([_celda_a_texto(c) for c in fila])
            if len(lote) == tam_lote:
                yield pd.DataFrame(lote, columns=encabezado)
                lote = []
        if lote:
            yield pd.DataFrame(lote, columns=encabezado)
    finally:
        libro.close()


def leer_por_lotes(ruta, tam_lote=TAM_LOTE):
    """Generador de DataFrames de texto. Devuelve también (codificación, separador) para el reporte."""
    ruta = Path(ruta)
    sufijo = ruta.suffix.lower()
    if sufijo == ".xlsx":
        return _lotes_excel(ruta, tam_lote), ("xlsx", None)
    if sufijo in (".xls", ".xlsb", ".xlsm"):
        raise ValueError(f"Formato {sufijo} no soportado: guarde el archivo como .xlsx o .csv.")
    codificacion = detectar_codificacion(ruta)
    separador = detectar_separador(ruta, codificacion)
    lector = pd.read_csv(ruta, sep=separador, encoding=codificacion, dtype=str, chunksize=tam_lote,
                         skipinitialspace=True)
    return lector, (codificacion, separador)


def reemplazar_centinelas(lote):
    """Centinelas -> nulo en las columnas clínicas; nunca en documento o nombres."""
    lote = lote.copy()
    decision = {v["nombre"]: v["decision"] for v in variables()}
    conteo = {}
    for original, nombre in mapear_columnas(lote.columns).items():
        if decision[nombre] in ("seudonimizar", "eliminar"):
            continue
        es_centinela = lote[original].astype("string").str.strip().isin(CENTINELAS)
        if es_centinela.any():
            conteo[nombre] = int(es_centinela.sum())
            lote.loc[es_centinela, original] = None
    return lote, conteo


@dataclass
class ReporteInspeccion:
    archivo: str
    formato: str
    separador: str | None
    filas_leidas: int = 0
    lotes: int = 0
    columnas_por_decision: dict = field(default_factory=dict)
    columnas_eliminadas: list = field(default_factory=list)
    columnas_desconocidas: list = field(default_factory=list)
    centinelas: dict = field(default_factory=dict)
    fuera_de_rango: dict = field(default_factory=dict)
    filas_duplicadas_eliminadas: int = 0
    gestantes_unicas: int = 0
    gestantes_con_varias_atenciones: int = 0
    sin_documento: int = 0
    pct_nulos_modelo: dict = field(default_factory=dict)
    aptas_modelo: int = 0
    faltantes_que_impiden_modelo: dict = field(default_factory=dict)

    def a_texto(self):
        lineas = [
            f"Archivo: {self.archivo}  ({self.formato}, separador {self.separador!r})",
            f"Filas leídas: {self.filas_leidas} en {self.lotes} lote(s)",
        ]
        for decision, cols in self.columnas_por_decision.items():
            lineas.append(f"  {decision:17s} {len(cols):2d}: {', '.join(cols) or '-'}")
        lineas += [
            f"  eliminadas        {len(self.columnas_eliminadas):2d}: {', '.join(self.columnas_eliminadas) or '-'}",
            f"  no reconocidas    {len(self.columnas_desconocidas):2d}: {', '.join(self.columnas_desconocidas) or '-'} (descartadas)",
            f"Valores centinela -> nulo: {self.centinelas or 'ninguno'}",
            f"Fuera de rango fisiológico -> nulo: {self.fuera_de_rango or 'ninguno'}",
            f"Filas duplicadas eliminadas: {self.filas_duplicadas_eliminadas}",
            f"Gestantes únicas (por seudónimo): {self.gestantes_unicas}; con varias atenciones: "
            f"{self.gestantes_con_varias_atenciones}; filas sin documento: {self.sin_documento}",
            f"% nulos en variables del modelo: {self.pct_nulos_modelo}",
            f"Registros aptos para el modelo: {self.aptas_modelo} de {self.filas_leidas - self.filas_duplicadas_eliminadas}",
        ]
        if self.faltantes_que_impiden_modelo:
            lineas.append(f"  Faltantes que lo impiden: {self.faltantes_que_impiden_modelo}")
        return "\n".join(lineas)


def _sumar(destino, origen):
    for k, v in origen.items():
        destino[k] = destino.get(k, 0) + v


def inspeccionar(ruta, sal, tam_lote=TAM_LOTE):
    """Procesa el archivo completo y devuelve (datos seudonimizados y filtrados, reporte)."""
    lotes, (formato, separador) = leer_por_lotes(ruta, tam_lote)
    reporte = ReporteInspeccion(archivo=Path(ruta).name, formato=formato, separador=separador)
    partes = []
    for lote in lotes:
        reporte.lotes += 1
        reporte.filas_leidas += len(lote)
        lote, centinelas = reemplazar_centinelas(lote)
        _sumar(reporte.centinelas, centinelas)
        resultado = aplicar_filtro(lote, sal)
        _sumar(reporte.fuera_de_rango, resultado.fuera_de_rango)
        if reporte.lotes == 1:
            reporte.columnas_por_decision = resultado.columnas_por_decision
            reporte.columnas_eliminadas = resultado.columnas_eliminadas
            reporte.columnas_desconocidas = resultado.columnas_desconocidas
        partes.append(resultado.datos)

    datos = pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()
    antes = len(datos)
    datos = datos.drop_duplicates(ignore_index=True)
    reporte.filas_duplicadas_eliminadas = antes - len(datos)

    if COLUMNA_SEUDONIMO in datos:
        ids = datos[COLUMNA_SEUDONIMO]
        reporte.sin_documento = int(ids.isna().sum())
        conteo = ids.value_counts()
        reporte.gestantes_unicas = int(len(conteo))
        reporte.gestantes_con_varias_atenciones = int((conteo > 1).sum())

    modelo = variables_modelo()
    presentes = [c for c in modelo if c in datos]
    reporte.pct_nulos_modelo = {c: round(float(datos[c].isna().mean() * 100), 2) for c in presentes if datos[c].isna().any()}
    obligatorias = [c for c in modelo if c not in VARS_CON_NULOS]
    faltan_columnas = [c for c in obligatorias if c not in datos]
    if faltan_columnas or datos.empty:
        reporte.aptas_modelo = 0
        reporte.faltantes_que_impiden_modelo = {c: "columna ausente" for c in faltan_columnas}
    else:
        nulos = datos[obligatorias].isna()
        reporte.aptas_modelo = int((~nulos.any(axis=1)).sum())
        reporte.faltantes_que_impiden_modelo = {c: int(n) for c, n in nulos.sum().items() if n}
    return datos, reporte


def aptos_para_modelo(datos):
    """Filas con todas las variables obligatorias, listas para el pipeline (convulsiones como entero)."""
    obligatorias = [c for c in variables_modelo() if c not in VARS_CON_NULOS]
    if any(c not in datos for c in obligatorias):
        return datos.iloc[0:0]
    aptos = datos.dropna(subset=obligatorias).copy()
    for c in VARS_CON_NULOS:
        if c not in aptos:
            aptos[c] = float("nan")
    aptos["convulsiones"] = aptos["convulsiones"].astype(int)
    return aptos


def main():
    parser = argparse.ArgumentParser(description="Inspecciona un archivo de la IPS y lo seudonimiza.")
    parser.add_argument("archivo")
    parser.add_argument("--salida", help="CSV donde guardar los datos seudonimizados y filtrados")
    parser.add_argument("--lote", type=int, default=TAM_LOTE, help="filas por lote")
    args = parser.parse_args()
    datos, reporte = inspeccionar(args.archivo, obtener_sal(), args.lote)
    print(reporte.a_texto())
    if args.salida:
        Path(args.salida).parent.mkdir(parents=True, exist_ok=True)
        datos.to_csv(args.salida, index=False, encoding="utf-8")
        print(f"\nGuardado: {args.salida} ({len(datos)} filas, sin nombres ni documentos)")


if __name__ == "__main__":
    main()
