"""Fase 3 — Seudonimización de documentos de identidad (Habeas Data, Ley 1581 de 2012).

El tipo y el número de documento se reemplazan por un HMAC-SHA256 con una sal secreta:
- el mismo documento produce siempre el mismo seudónimo, así que se puede deduplicar y unir
  atenciones de una misma gestante sin guardar la cédula;
- sin la sal no se puede recalcular el seudónimo probando cédulas, como sí pasaría con un
  SHA-256 simple (los números de documento son pocos y predecibles).

La sal se lee de la variable de entorno MATERNA_SAL y nunca se guarda en el repositorio.
Si se pierde, los seudónimos nuevos no coinciden con los anteriores.
"""
import hashlib
import hmac
import os
import re

import pandas as pd

VARIABLE_SAL = "MATERNA_SAL"
LONGITUD_MINIMA_SAL = 16
COLUMNA_SEUDONIMO = "id_seudonimo"


def obtener_sal():
    """Lee la sal del entorno; falla con un mensaje claro si falta o es muy corta."""
    sal = os.environ.get(VARIABLE_SAL, "")
    if len(sal) < LONGITUD_MINIMA_SAL:
        raise RuntimeError(
            f"Defina la variable de entorno {VARIABLE_SAL} con al menos {LONGITUD_MINIMA_SAL} caracteres "
            "antes de procesar archivos con documentos de identidad."
        )
    return sal


def normalizar_documento(tipo, numero):
    """'cc', '1.065.432-1 ' -> ('CC', '10654321'): el mismo documento escrito de distintas formas."""
    tipo = str(tipo).strip().upper()
    numero = re.sub(r"[\s.\-]", "", str(numero)).upper()
    return tipo, numero


def seudonimizar(tipo, numero, sal):
    """Seudónimo hexadecimal de 64 caracteres para un documento."""
    if not sal:
        raise ValueError("La sal no puede estar vacía.")
    tipo, numero = normalizar_documento(tipo, numero)
    if not numero:
        raise ValueError("El número de documento está vacío.")
    return hmac.new(sal.encode("utf-8"), f"{tipo}|{numero}".encode("utf-8"), hashlib.sha256).hexdigest()


def seudonimizar_dataframe(df, sal, col_tipo="tipo_documento", col_numero="numero_documento"):
    """Agrega la columna id_seudonimo y elimina las columnas de documento.

    Las filas sin número de documento quedan con seudónimo nulo: no se pueden deduplicar.
    """
    df = df.copy()
    tipos = df[col_tipo] if col_tipo in df else [""] * len(df)
    seudonimos = []
    for tipo, numero in zip(tipos, df[col_numero]):
        vacio = pd.isna(numero) or not str(numero).strip()
        seudonimos.append(None if vacio else seudonimizar("" if pd.isna(tipo) else tipo, numero, sal))
    df.insert(0, COLUMNA_SEUDONIMO, seudonimos)
    return df.drop(columns=[c for c in (col_tipo, col_numero) if c in df])
