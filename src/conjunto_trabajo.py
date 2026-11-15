"""Fase 3 — Conjunto de trabajo del laboratorio: los datos con que se entrenan los experimentos.

Por defecto el laboratorio entrena con el dataset base (1.200 gestantes). Desde la pestaña 04 se puede
establecer otro conjunto de trabajo: registros generados (src/generador_sintetico.py) o un archivo crudo
subido y depurado (src/depuracion.py). Queda en experimentos/conjunto/ (fuera del repositorio):

    trabajo.csv             lo que se parte en entrenamiento, validación y prueba
    lote_demostracion.csv   reserva estratificada que NUNCA entra al entrenamiento ni a esas particiones
    meta.json               nombre, tamaños, semilla de la reserva, usuario, fecha y huella SHA-256

El lote de demostración se aparta ANTES de partir: sirve para cargarlo en vivo y medir el modelo sobre
registros que no usó. Aviso: si los datos son generados a partir de las 1.200, el lote no es evidencia
independiente (todos salen de las mismas gestantes); demuestra el procedimiento, no el desempeño clínico.

También mide la escalabilidad: tiempo de carga, de limpieza y de entrenamiento, y memoria, según N.
"""
import hashlib
import json
import tempfile
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

from src import experimentos
from src.clinical_rules import predecir_hibrido
from src.config import MAPA_TARGET, SEMILLA, TARGET
from src.data_preprocessing import PARTICION_OFICIAL, particionar, separar_xy
from src.depuracion import depurar, leer_crudo
from src.evaluate import calcular_metricas
from src.generador_sintetico import a_texto, ensuciar, generar

TAMANOS_ESCALABILIDAD = (5000, 10000, 20000, 30000)


def carpeta():
    return experimentos.directorio() / "conjunto"


def establecer(limpio, nombre, usuario, n_lote=0, semilla=SEMILLA):
    """Guarda `limpio` como conjunto de trabajo, apartando antes un lote de demostración estratificado."""
    if not 0 <= n_lote < len(limpio):
        raise ValueError(f"El lote de demostración debe tener entre 0 y {len(limpio) - 1} registros.")
    if n_lote:
        if n_lote < len(MAPA_TARGET):
            raise ValueError(f"El lote de demostración necesita al menos {len(MAPA_TARGET)} registros (uno por clase).")
        trabajo, lote = train_test_split(limpio, test_size=n_lote, stratify=limpio[TARGET], random_state=semilla)
    else:
        trabajo, lote = limpio, limpio.iloc[0:0]
    destino = carpeta()
    destino.mkdir(parents=True, exist_ok=True)
    trabajo.to_csv(destino / "trabajo.csv", index=False)
    lote.to_csv(destino / "lote_demostracion.csv", index=False)
    meta = {
        "nombre": nombre, "n_total": len(limpio), "n_trabajo": len(trabajo), "n_lote": len(lote), "semilla_lote": int(semilla),
        "usuario": usuario, "fecha": datetime.now().isoformat(timespec="seconds"),
        "huella": hashlib.sha256((destino / "trabajo.csv").read_bytes()).hexdigest(),
    }
    (destino / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return meta


def restablecer():
    """Vuelve al dataset base (borra el conjunto de trabajo; las versiones ya entrenadas se conservan)."""
    for nombre in ("trabajo.csv", "lote_demostracion.csv", "meta.json"):
        (carpeta() / nombre).unlink(missing_ok=True)


def meta():
    ruta = carpeta() / "meta.json"
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else None


def _leer(nombre):
    return pd.read_csv(carpeta() / nombre)


def datos():
    """El conjunto de trabajo activo, o None si se usa el dataset base."""
    return _leer("trabajo.csv") if meta() else None


def lote():
    return _leer("lote_demostracion.csv")


def descripcion(m=None):
    """Nombre con que queda en el registro de experimentos."""
    m = m or meta()
    return experimentos.DATOS_BASE if m is None else f"{m['nombre']} · {m['n_trabajo']} registros de trabajo"


def evaluar_lote(modelo):
    """Métricas del sistema híbrido sobre el lote de demostración (registros que el modelo no usó)."""
    X, y = separar_xy(lote())
    pred, proba, _ = predecir_hibrido(modelo, X)
    return calcular_metricas(y, pred, proba)


# ------------------------------------------------------------------ escalabilidad
def medir_escalabilidad(tamanos=TAMANOS_ESCALABILIDAD, algoritmo="Random Forest", semilla=SEMILLA,
                        al_avanzar=lambda n, etapa: None):
    """Para cada N: genera un archivo crudo, lo carga, lo depura y entrena una vez; mide tiempos y memoria.

    El entrenamiento es un solo ajuste del pipeline (mejores hiperparámetros de la Fase 2) sobre el 70 % de
    los registros limpios. La SVM se limita a experimentos.MAX_SVM registros de entrenamiento.
    """
    filas = []
    with tempfile.TemporaryDirectory() as tmp:
        for n in tamanos:
            al_avanzar(n, "generando")
            crudo, _ = ensuciar(generar(n, semilla), semilla)
            ruta = Path(tmp) / f"crudo_{n}.txt"
            ruta.write_text(a_texto(crudo), encoding="utf-8", newline="")

            al_avanzar(n, "cargando")
            inicio = time.perf_counter()
            leido, _ = leer_crudo(ruta)
            t_carga = time.perf_counter() - inicio

            al_avanzar(n, "limpiando")
            inicio = time.perf_counter()
            limpio, _ = depurar(leido)
            t_limpieza = time.perf_counter() - inicio

            al_avanzar(n, "entrenando")
            X, y = separar_xy(limpio)
            X_train, _, _, y_train, _, _ = particionar(X, y, semilla, PARTICION_OFICIAL)
            X_train, y_train, _ = experimentos.limitar_svm(algoritmo, X_train, y_train, semilla)
            inicio = time.perf_counter()
            experimentos.construir(algoritmo, experimentos.hiperparametros_base(algoritmo), semilla).fit(X_train, y_train)
            t_entrenamiento = time.perf_counter() - inicio

            filas.append({
                "registros": n, "archivo_mb": round(ruta.stat().st_size / 1e6, 2), "filas_crudas": len(leido),
                "filas_limpias": len(limpio), "carga_s": round(t_carga, 2), "limpieza_s": round(t_limpieza, 2),
                "entrenamiento_s": round(t_entrenamiento, 2), "n_entrenamiento": len(X_train),
                "memoria_mb": round(limpio.memory_usage(deep=True).sum() / 1e6, 2), "algoritmo": algoritmo,
            })
    tabla = pd.DataFrame(filas)
    experimentos.directorio().mkdir(parents=True, exist_ok=True)
    tabla.to_csv(experimentos.directorio() / "escalabilidad.csv", index=False)
    return tabla


def escalabilidad_guardada():
    ruta = experimentos.directorio() / "escalabilidad.csv"
    return pd.read_csv(ruta) if ruta.exists() else None
