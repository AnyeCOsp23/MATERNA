"""Fase 3 — «Publicar al Módulo 2»: lo único que cambia el modelo que usa la app.

Publicar toma una versión de Random Forest del registro de experimentos y:
  1. copia su modelo a models/publicados/ con un número de versión nuevo (v2, v3, …; nunca se reutiliza);
  2. arma los JSON (modelo, preprocesamiento, reglas, casos de prueba) y comprueba la PARIDAD en Python:
     la inferencia desde JSON debe dar lo mismo que scikit-learn; si no, no se publica nada;
  3. escribe los JSON en flutter_app/assets/, con la versión y la huella SHA-256 del modelo;
  4. anota la publicación (quién, cuándo, de qué versión salió, con qué datos y métricas).

Solo se publica el Random Forest, con las 4 reglas críticas y el catálogo 3280: la app solo tiene motor de
árboles. La Regresión Logística y la SVM se entrenan y se comparan en el laboratorio, pero no se publican.

Lo oficial de la Fase 2 no se toca: models/modelo_random_forest.joblib sigue siendo el modelo v1 y los
reportes no cambian. «Volver al modelo oficial» exporta otra vez el v1 y deja los JSON como estaban.

Los teléfonos reciben el modelo nuevo AL RECOMPILAR la app (los JSON van dentro de ella). La paridad en
Dart se comprueba con `flutter test`, donde esté instalado Flutter.

La variable MATERNA_PUBLICACION puede apuntar a otra carpeta para el manifiesto y los modelos publicados
(la usan las pruebas, junto con MATERNA_ASSETS para los JSON).
"""
import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import pandas as pd

from src import experimentos, exportar_a_dart
from src.config import DIR_MODELOS, RAIZ

VARIABLE_DIRECTORIO = "MATERNA_PUBLICACION"
ALGORITMO_PUBLICABLE = "Random Forest"
VERSION_OFICIAL = exportar_a_dart.VERSION_MODELO
PRUEBAS_DART = ["test/paridad_test.dart", "test/carga_test.dart"]


def carpeta():
    return Path(os.environ.get(VARIABLE_DIRECTORIO) or DIR_MODELOS / "publicados")


def _ruta_manifiesto():
    return carpeta() / "publicacion.json"


def manifiesto():
    ruta = _ruta_manifiesto()
    if ruta.exists():
        return json.loads(ruta.read_text(encoding="utf-8"))
    return {"oficial": None, "actual": None, "historial": []}


def _guardar(m):
    carpeta().mkdir(parents=True, exist_ok=True)
    _ruta_manifiesto().write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")


def publicado():
    """Lo que usa hoy la app: la última publicación o, si no hay, el modelo oficial de la Fase 2."""
    actual = manifiesto()["actual"]
    if actual:
        return {**actual, "ruta": carpeta() / actual["archivo"], "oficial": False}
    return {"version": VERSION_OFICIAL, "origen": "Modelo oficial de la Fase 2", "ruta": exportar_a_dart.RUTA_MODELO,
            "sha256": exportar_a_dart._sha256(exportar_a_dart.RUTA_MODELO), "oficial": True}


def ruta_publicada():
    return publicado()["ruta"]


def assets_vigentes():
    """¿Los JSON de la app corresponden al modelo publicado? (versión y huella)."""
    ruta = exportar_a_dart.dir_assets() / "modelo_rf.json"
    if not ruta.exists():
        return False
    # el archivo es grande: basta el encabezado, donde están la versión y la huella
    with open(ruta, encoding="utf-8") as f:
        cabecera = f.read(400)
    actual = publicado()
    return f'"version":"{actual["version"]}"' in cabecera and f'"sha256_joblib":"{actual["sha256"]}"' in cabecera


def _fecha_oficial():
    """Fecha de exportación del v1 que está en el repositorio: se conserva para poder volver a él sin diferencias."""
    ruta = exportar_a_dart.dir_assets() / "modelo_rf.json"
    with open(ruta, encoding="utf-8") as f:
        cabecera = f.read(400)
    if f'"version":"{VERSION_OFICIAL}"' not in cabecera:
        return None
    return cabecera.split('"exportado":"')[1].split('"')[0]


def publicar(version_experimento, usuario):
    """Publica una versión de Random Forest. Lanza ValueError, sin cambiar nada, si no se puede."""
    registro = next((r for r in experimentos.leer_registro() if r["version"] == version_experimento), None)
    if registro is None:
        raise ValueError(f"No existe la versión {version_experimento}.")
    if registro["algoritmo"] != ALGORITMO_PUBLICABLE:
        raise ValueError(f"Solo se publica el Random Forest: la app solo tiene motor de árboles. {version_experimento} es "
                         f"{registro['algoritmo']}; se compara en el laboratorio, pero no se publica.")
    origen = experimentos.directorio() / "modelos" / f"{version_experimento}.joblib"
    if not origen.exists():
        raise ValueError(f"No se encuentra el modelo de {version_experimento}.")

    m = manifiesto()
    if m["oficial"] is None:
        m["oficial"] = {"version": VERSION_OFICIAL, "exportado": _fecha_oficial()}
    numeros = [int(e["version"][1:]) for e in m["historial"] if e["accion"] == "publicado"]
    version = f"v{max(numeros, default=int(VERSION_OFICIAL[1:])) + 1}"
    archivo = f"{version}_modelo_random_forest.joblib"
    carpeta().mkdir(parents=True, exist_ok=True)
    destino = carpeta() / archivo
    if destino.exists():
        raise ValueError(f"Ya existe {archivo}: una versión publicada nunca se sobrescribe.")
    shutil.copyfile(origen, destino)
    try:
        info = exportar_a_dart.exportar(destino, version)
    except AssertionError as error:  # la paridad falló: no se escribió ningún JSON
        destino.unlink()
        raise ValueError(f"No se publicó: la prueba de paridad falló ({error}).") from error

    entrada = {
        "accion": "publicado", "version": version, "origen": version_experimento, "archivo": archivo,
        "sha256": info["sha256"], "fecha": datetime.now().isoformat(timespec="seconds"), "usuario": usuario,
        "datos": registro["datos"], "particion": registro["particion"], "semilla": registro["semilla"],
        "hiperparametros": registro["hiperparametros"], "n_arboles": info["n_arboles"],
        "val_f1_macro": registro["val_f1_macro"], "val_recall_alto": registro["val_recall_alto"],
        "casos_paridad": info["casos_paridad"], "dif_variables": info["dif_variables"],
        "dif_probabilidades": info["dif_probabilidades"],
    }
    m["actual"] = entrada
    m["historial"].append(entrada)
    _guardar(m)
    return {**entrada, "archivos": info["archivos"]}


def restablecer_oficial(usuario):
    """Vuelve a exportar el modelo oficial v1: los JSON quedan como estaban antes de publicar."""
    m = manifiesto()
    if m["actual"] is None:
        raise ValueError("La app ya usa el modelo oficial de la Fase 2.")
    info = exportar_a_dart.exportar(exportar_a_dart.RUTA_MODELO, VERSION_OFICIAL, (m["oficial"] or {}).get("exportado"))
    m["actual"] = None
    m["historial"].append({"accion": "restablecido", "version": VERSION_OFICIAL, "origen": "Modelo oficial de la Fase 2",
                           "sha256": info["sha256"], "fecha": datetime.now().isoformat(timespec="seconds"), "usuario": usuario})
    _guardar(m)
    return info


def tabla_historial():
    filas = [{
        "Fecha": e["fecha"], "Usuario": e["usuario"], "Acción": e["accion"], "Versión": e["version"], "Sale de": e["origen"],
        "Datos": e.get("datos", "—"), "F1-macro validación": e.get("val_f1_macro"), "Recall Alto validación": e.get("val_recall_alto"),
        "Casos de paridad": e.get("casos_paridad"), "SHA-256 (inicio)": e["sha256"][:16],
    } for e in reversed(manifiesto()["historial"])]
    return pd.DataFrame(filas)


# ------------------------------------------------------------------ paridad en Dart (solo donde está Flutter)
def flutter():
    """Ruta del ejecutable de Flutter, o None si este equipo no lo tiene a mano (PATH o FLUTTER_ROOT)."""
    encontrado = shutil.which("flutter")
    if encontrado:
        return encontrado
    raiz = os.environ.get("FLUTTER_ROOT")
    for nombre in ("flutter.bat", "flutter"):
        if raiz and (Path(raiz) / "bin" / nombre).exists():
            return str(Path(raiz) / "bin" / nombre)
    return None


def paridad_dart(tiempo_maximo=900):
    """Corre en Dart las pruebas de paridad del motor y de la carga masiva. Devuelve (pasó, últimas líneas)."""
    ejecutable = flutter()
    if ejecutable is None:
        raise ValueError("Flutter no está en el PATH de este equipo. Ejecute en una terminal: cd flutter_app; flutter test")
    proceso = subprocess.run([ejecutable, "test", *PRUEBAS_DART], cwd=RAIZ / "flutter_app", capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=tiempo_maximo)
    salida = (proceso.stdout + proceso.stderr).strip().splitlines()
    return proceso.returncode == 0, "\n".join(salida[-6:])
