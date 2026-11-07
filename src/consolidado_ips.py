"""Fase 3 — Base de datos del laboratorio (Módulo 1) con los archivos de la IPS ya ingeridos.

Guarda cada carga ya filtrada y seudonimizada (sin nombres ni documentos) y su reporte de calidad,
para dejar trazabilidad de la ingesta y poder comparar los datos de la IPS con el dataset sintético.
El triaje por lotes con semáforo NO vive aquí: es del Módulo 2 (app Flutter, web y móvil).

La ruta se cambia con la variable de entorno MATERNA_BD_IPS; el archivo está en .gitignore.
"""
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.config import RAIZ

RUTA_POR_DEFECTO = RAIZ / "data" / "consolidado_ips.sqlite"


def ruta_bd():
    """Se lee en cada uso (no al importar) para que las pruebas puedan usar una base temporal."""
    return Path(os.environ.get("MATERNA_BD_IPS", RUTA_POR_DEFECTO))


def _conectar(ruta=None):
    ruta = Path(ruta or ruta_bd())
    ruta.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(ruta)
    con.execute("""CREATE TABLE IF NOT EXISTS cargas (
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, archivo TEXT, usuario TEXT,
        filas INTEGER, aptas INTEGER, reporte TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS atenciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT, id_carga INTEGER, id_seudonimo TEXT, datos TEXT)""")
    return con


def _a_json(registro):
    limpio = {k: (None if pd.isna(v) else v.isoformat() if hasattr(v, "isoformat") else v) for k, v in registro.items()}
    return json.dumps(limpio, ensure_ascii=False, default=str)


def guardar_carga(datos, reporte, usuario, ruta=None):
    """Guarda una carga ya seudonimizada y su reporte. Devuelve el número de la carga."""
    with _conectar(ruta) as con:
        cur = con.execute(
            "INSERT INTO cargas (fecha, archivo, usuario, filas, aptas, reporte) VALUES (?, ?, ?, ?, ?, ?)",
            (datetime.now().isoformat(timespec="seconds"), reporte.archivo, usuario, len(datos),
             reporte.aptas_modelo, reporte.a_texto()))
        id_carga = cur.lastrowid
        con.executemany("INSERT INTO atenciones (id_carga, id_seudonimo, datos) VALUES (?, ?, ?)",
                        [(id_carga, r.get("id_seudonimo"), _a_json(r)) for r in datos.to_dict("records")])
    return id_carga


def resumen_consolidado(ruta=None):
    """(cargas, número de gestantes distintas) de la base del laboratorio."""
    with _conectar(ruta) as con:
        cargas = pd.read_sql("SELECT id, fecha, archivo, usuario, filas, aptas FROM cargas ORDER BY id DESC", con)
        gestantes = con.execute("SELECT COUNT(DISTINCT id_seudonimo) FROM atenciones").fetchone()[0]
    return cargas, gestantes


def datos_consolidados(ruta=None):
    """Todas las atenciones guardadas, como DataFrame (para compararlas con el dataset sintético)."""
    with _conectar(ruta) as con:
        filas = [json.loads(d) for (d,) in con.execute("SELECT datos FROM atenciones")]
    return pd.DataFrame(filas)
