"""Fase 3 — Patrones nuevos: agregar a mano una gestante al conjunto de datos (10.000 -> 10.001).

Un patrón nuevo es un registro con las 11 variables del modelo y su clase. La clase puede venir de dos fuentes:
  asignada_usuario  la pone quien registra el caso (p. ej. el médico que lo conoce);
  proxy_reglas      la calcula el sistema en uso (modelo + reglas). No aporta información nueva: solo
                    repite lo que el sistema ya cree. Queda marcada para que se sepa.

Antes de aceptarlo se valida contra el catálogo de la Resolución 3280 (config/variables_3280.json): cada
valor debe estar en su rango o en su lista de valores, y no puede repetir un registro que ya existe.

Los patrones NO se mezclan con el archivo del conjunto de trabajo ni con el dataset base: viven aparte, en
experimentos/patrones/, con su bitácora (quién, cuándo, qué valores, contador antes y después):

    patrones.csv     los patrones vigentes
    eventos.jsonl    bitácora; solo se agrega, nunca se reescribe

Al reentrenar se suman SOLO al conjunto de entrenamiento (src/experimentos.entrenar, parámetro `patrones`):
la validación y la prueba quedan idénticas, así que las métricas de antes y después son comparables.
"""
import json
from datetime import datetime

import joblib
import numpy as np
import pandas as pd

from src import experimentos
from src.clinical_rules import evaluar_riesgo_hibrido
from src.config import DIR_MODELOS, MAPA_TARGET, TARGET, VARS_CON_NULOS, VARS_DEMOGRAFICAS
from src.filtro_3280 import variables

ORIGEN = "patron_manual"
ASIGNADA, PROXY = "asignada_usuario", "proxy_reglas"
ETIQUETAS_ORIGEN = {ASIGNADA: "Asignada por el usuario", PROXY: "Proxy por reglas (la calculó el sistema)"}
COLUMNA_ETIQUETA = "etiqueta_origen"


def carpeta():
    return experimentos.directorio() / "patrones"


def catalogo_modelo():
    """Las variables del modelo con su rango o sus valores, tal como están en el catálogo 3280."""
    return variables("modelo")


def validar(registro):
    """Lista de motivos por los que el registro no se acepta (vacía si es válido)."""
    errores = []
    for v in catalogo_modelo():
        nombre, etiqueta, valor = v["nombre"], v["etiqueta"], registro.get(v["nombre"])
        falta = valor is None or (isinstance(valor, float) and np.isnan(valor))
        if falta:
            if nombre not in VARS_CON_NULOS:
                errores.append(f"{etiqueta}: es obligatoria.")
            continue
        if v["tipo"] == "categorica":
            if valor not in v["valores"]:
                errores.append(f"{etiqueta}: «{valor}» no es un valor del catálogo ({', '.join(v['valores'])}).")
        elif v["tipo"] == "binaria":
            if valor not in (0, 1):
                errores.append(f"{etiqueta}: debe ser Sí o No.")
        else:
            lo, hi = v["rango"]
            if not lo <= valor <= hi:
                errores.append(f"{etiqueta}: {valor:g} {v.get('unidad', '')} está fuera del rango del catálogo 3280 "
                               f"({lo} a {hi}).")
            elif v["tipo"] == "entero" and float(valor) != int(valor):
                errores.append(f"{etiqueta}: debe ser un número entero.")
    return errores


def _clave(registro):
    """Lo que identifica a un registro: los valores de las variables del modelo."""
    partes = []
    for v in catalogo_modelo():
        valor = registro.get(v["nombre"])
        if valor is None or (isinstance(valor, float) and np.isnan(valor)):
            partes.append(None)
        elif v["tipo"] == "categorica":
            partes.append(str(valor))
        else:
            partes.append(round(float(valor), 1))
    return tuple(partes)


def buscar_duplicado(registro, datos):
    """Identificador y clase del registro de `datos` con las mismas variables del modelo, o None."""
    if datos is None or datos.empty:
        return None
    nombres = [v["nombre"] for v in catalogo_modelo()]
    clave = _clave(registro)
    candidatos = datos[(datos["edad"] == registro["edad"]) & (datos["pas_mmhg"] == registro["pas_mmhg"])
                       & (datos["pad_mmhg"] == registro["pad_mmhg"])]
    for _, fila in candidatos.iterrows():
        if _clave({n: fila[n] for n in nombres}) == clave:
            return fila["id_gestante"], fila[TARGET]
    return None


def clase_proxy(registro):
    """La clase que el sistema en uso (modelo + reglas) asigna al registro."""
    modelo = joblib.load(DIR_MODELOS / "modelo_random_forest.joblib")
    completo = {**{c: None for c in VARS_DEMOGRAFICAS}, **registro}
    return evaluar_riesgo_hibrido(completo, modelo).categoria


def vigentes():
    """Los patrones nuevos vigentes, con las columnas del dataset más `origen` y `etiqueta_origen`."""
    ruta = carpeta() / "patrones.csv"
    return pd.read_csv(ruta) if ruta.exists() else pd.DataFrame()


def eventos():
    ruta = carpeta() / "eventos.jsonl"
    if not ruta.exists():
        return []
    return [json.loads(linea) for linea in ruta.read_text(encoding="utf-8").splitlines() if linea.strip()]


def _anotar(evento):
    carpeta().mkdir(parents=True, exist_ok=True)
    with open(carpeta() / "eventos.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(evento, ensure_ascii=False) + "\n")


def agregar(registro, clase, usuario, datos, etiqueta_origen=ASIGNADA):
    """Valida y agrega el patrón. `datos` es el conjunto al que se suma (para el contador y los duplicados).

    clase=None con etiqueta_origen=PROXY la calcula el sistema. Lanza ValueError con todos los motivos si
    se rechaza. Devuelve el evento registrado (con el contador antes y después).
    """
    errores = validar(registro)
    if etiqueta_origen not in ETIQUETAS_ORIGEN:
        errores.append("El origen de la etiqueta no es válido.")
    if not errores:
        actuales = vigentes()
        for conjunto, donde in [(datos, "el conjunto de datos"), (actuales, "los patrones nuevos")]:
            repetido = buscar_duplicado(registro, conjunto)
            if repetido:
                errores.append(f"Duplicado: ya hay un registro con estos mismos valores en {donde} ({repetido[0]}, "
                               f"clasificado como {repetido[1]}).")
                break
    if not errores:
        if etiqueta_origen == PROXY:
            clase = clase_proxy(registro)
        elif clase not in MAPA_TARGET:
            errores.append(f"La clase debe ser una de: {', '.join(MAPA_TARGET)}.")
    if errores:
        raise ValueError(" ".join(errores))

    usados = [int(e["id"][2:]) for e in eventos() if e["accion"] == "agregado"]
    identificador = f"NP{max(usados, default=0) + 1:04d}"
    columnas = list(datos.columns.drop(["origen", COLUMNA_ETIQUETA], errors="ignore"))
    fila = {c: None for c in columnas}
    fila.update(registro)
    fila.update({"id_gestante": identificador, TARGET: clase, "origen": ORIGEN, COLUMNA_ETIQUETA: etiqueta_origen})
    antes = len(datos) + len(actuales)
    carpeta().mkdir(parents=True, exist_ok=True)
    pd.concat([actuales, pd.DataFrame([fila])], ignore_index=True).to_csv(carpeta() / "patrones.csv", index=False)
    evento = {"accion": "agregado", "id": identificador, "fecha": datetime.now().isoformat(timespec="seconds"),
              "usuario": usuario, "valores": registro, "clase": clase, COLUMNA_ETIQUETA: etiqueta_origen,
              "contador_antes": antes, "contador_despues": antes + 1}
    _anotar(evento)
    return evento


def retirar(identificador, usuario, n_datos):
    """Retira un patrón vigente (p. ej. uno mal digitado). Queda anotado en la bitácora."""
    actuales = vigentes()
    if actuales.empty or identificador not in set(actuales["id_gestante"]):
        raise ValueError(f"No hay un patrón vigente con el identificador {identificador}.")
    antes = n_datos + len(actuales)
    actuales[actuales["id_gestante"] != identificador].to_csv(carpeta() / "patrones.csv", index=False)
    evento = {"accion": "retirado", "id": identificador, "fecha": datetime.now().isoformat(timespec="seconds"),
              "usuario": usuario, "contador_antes": antes, "contador_despues": antes - 1}
    _anotar(evento)
    return evento


def tabla_eventos():
    """La bitácora como tabla, de lo más reciente a lo más antiguo."""
    filas = [{
        "Fecha": e["fecha"], "Usuario": e["usuario"], "Acción": e["accion"], "Patrón": e["id"],
        "Clase": e.get("clase", "—"), "Etiqueta": ETIQUETAS_ORIGEN.get(e.get(COLUMNA_ETIQUETA), "—"),
        "Contador": f"{e['contador_antes']} → {e['contador_despues']}",
        "Valores": ", ".join(f"{k}={v}" for k, v in e.get("valores", {}).items()) or "—",
    } for e in reversed(eventos())]
    return pd.DataFrame(filas)
