"""Sub-fase 2.3 — Motor híbrido: reglas clínicas de seguridad + modelo de aprendizaje automático.

Si una gestante presenta un signo de alarma crítico, la regla SOBRESCRIBE la predicción del modelo
y la clasifica como Alto Riesgo, sin depender de la confianza estadística.

Umbrales (definidos en el documento de propuesta de la Fase 1, sección 4):
  - PAS >= 160 mmHg o PAD >= 110 mmHg: hipertensión severa en el embarazo.
    Referencia: Minsalud / Colciencias (2013). Guía de Práctica Clínica para la prevención, detección
    temprana y tratamiento de las complicaciones del embarazo (GPC n.º 11-15), módulo de trastornos
    hipertensivos.
  - Convulsiones: sospecha de eclampsia.
  - Proteinuria en tira reactiva >= ++ (codificada como 2 en el dataset).

IMPORTANTE: los textos de protocolo son orientativos, para la demostración académica. Antes de cualquier
uso en campo, deben ser validados por un asesor clínico (ginecobstetricia) y ajustados a la ruta
materno-perinatal (Resolución 3280 de 2018) y a la red de referencia de cada ESE/IPS.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.config import CLASE_ALTO, NOMBRES_CLASES

UMBRAL_PAS_SEVERA = 160
UMBRAL_PAD_SEVERA = 110
UMBRAL_PROTEINURIA = 2  # ++ en tira reactiva

ETIQUETAS_PROTEINURIA = {0: "Negativa", 1: "+", 2: "++"}


def evaluar_reglas(registro):
    """Devuelve la lista de signos de alarma críticos presentes en un registro (dict o Series)."""
    alertas = []
    pas, pad = registro.get("pas_mmhg"), registro.get("pad_mmhg")
    if pas is not None and not pd.isna(pas) and pas >= UMBRAL_PAS_SEVERA:
        alertas.append(f"Hipertensión severa: PAS {pas:.0f} mmHg (umbral ≥ {UMBRAL_PAS_SEVERA})")
    if pad is not None and not pd.isna(pad) and pad >= UMBRAL_PAD_SEVERA:
        alertas.append(f"Hipertensión severa: PAD {pad:.0f} mmHg (umbral ≥ {UMBRAL_PAD_SEVERA})")
    if bool(registro.get("convulsiones", 0)):
        alertas.append("Convulsiones: sospecha de eclampsia")
    prot = registro.get("proteinuria")
    if prot is not None and not pd.isna(prot) and prot >= UMBRAL_PROTEINURIA:
        alertas.append(f"Proteinuria {ETIQUETAS_PROTEINURIA.get(int(prot), int(prot))} en tira reactiva (umbral ≥ ++)")
    return alertas


def mascara_reglas(X):
    """Versión vectorizada: True en las filas donde se activa al menos una regla crítica."""
    return (
        (X["pas_mmhg"] >= UMBRAL_PAS_SEVERA)
        | (X["pad_mmhg"] >= UMBRAL_PAD_SEVERA)
        | (X["convulsiones"].astype(bool))
        | (X["proteinuria"] >= UMBRAL_PROTEINURIA)
    ).to_numpy()


@dataclass
class ResultadoHibrido:
    categoria: str
    clase: int
    origen: str                       # "regla_clinica" o "modelo_ml"
    alertas: list = field(default_factory=list)
    probabilidades_modelo: dict = field(default_factory=dict)
    categoria_modelo: str = ""


def evaluar_riesgo_hibrido(registro, modelo):
    """Clasificación de una gestante: la regla clínica prevalece sobre el modelo.

    registro: dict con las variables de entrada (mismas columnas que el dataset, sin id ni target).
              glucosa_mgdl y fcf_bpm pueden ser None si no se pudieron medir (se imputan en el pipeline).
    modelo:   pipeline entrenado con predict_proba (SVM calibrado o Regresión Logística).
    """
    fila = pd.DataFrame([{k: (np.nan if v is None else v) for k, v in registro.items()}])
    proba = modelo.predict_proba(fila)[0]
    clase_modelo = int(np.argmax(proba))
    probabilidades = {NOMBRES_CLASES[i]: float(p) for i, p in enumerate(proba)}
    alertas = evaluar_reglas(registro)
    if alertas:
        return ResultadoHibrido(NOMBRES_CLASES[CLASE_ALTO], CLASE_ALTO, "regla_clinica", alertas,
                                probabilidades, NOMBRES_CLASES[clase_modelo])
    return ResultadoHibrido(NOMBRES_CLASES[clase_modelo], clase_modelo, "modelo_ml", [],
                            probabilidades, NOMBRES_CLASES[clase_modelo])


def predecir_hibrido(modelo, X):
    """Predicción híbrida vectorizada para evaluación: (clases, probabilidades, máscara de reglas).

    En las filas donde se activa una regla, la probabilidad se fija en [0, 0, 1] para que las
    curvas ROC reflejen la decisión real del sistema.
    """
    proba = modelo.predict_proba(X).copy()
    activa = mascara_reglas(X)
    pred = proba.argmax(axis=1)
    pred[activa] = CLASE_ALTO
    proba[activa] = np.eye(len(NOMBRES_CLASES))[CLASE_ALTO]
    return pred, proba, activa


# Acciones orientadoras por categoría (ver advertencia en el encabezado del módulo).
PROTOCOLO = {
    "Alto Riesgo": [
        "Remisión INMEDIATA a una institución con capacidad resolutiva obstétrica (II/III nivel, p. ej. Riohacha o Valledupar); coordinar el traslado con el CRUE departamental.",
        "Si hay hipertensión severa, proteinuria o convulsiones: iniciar el manejo de preeclampsia severa/eclampsia según la GPC de complicaciones hipertensivas del embarazo (Minsalud 2013), incluido el sulfato de magnesio y el antihipertensivo, solo por personal habilitado y con el esquema de la guía.",
        "No dejar sola a la gestante; vigilar signos vitales, conciencia y sangrado hasta la entrega en la institución receptora.",
        "Registrar el caso; se sincronizará con la consola de la ESE/IPS al recuperar conectividad.",
    ],
    "Riesgo Medio": [
        "Valoración por médico en los próximos días (no esperar al siguiente control de rutina).",
        "Completar los paraclínicos pendientes (glucemia, uroanálisis/proteinuria) y repetir la toma de presión arterial.",
        "Educar a la gestante y a la familia sobre los signos de alarma: cefalea intensa, visión borrosa, dolor epigástrico, sangrado, edema súbito, disminución de movimientos fetales.",
        "Programar el seguimiento con el equipo extramural / promotora de la zona.",
    ],
    "Bajo Riesgo": [
        "Continuar los controles prenatales según la ruta materno-perinatal (Resolución 3280 de 2018).",
        "Reforzar la educación en signos de alarma y el plan de parto institucional.",
        "Verificar la micronutrición y el esquema de vacunación.",
    ],
}
