"""Fase 3 — El recorrido de una gestante por el sistema híbrido, paso a paso, para explicarlo.

No es un modelo aparte ni una red neuronal: reconstruye lo que hace de verdad el modelo en uso (Random Forest
de 300 árboles + reglas clínicas) con una gestante concreta:

  1. sus 11 datos se convierten en las 17 variables de entrada (imputación, indicadores de dato faltante y One-Hot);
  2. cada árbol le hace preguntas («¿PAS ≤ 139,5?») hasta llegar a una hoja, que da una probabilidad por clase;
  3. se promedian las hojas de los 300 árboles: esas son las probabilidades del modelo;
  4. las reglas clínicas (y los signos de alarma de la ruta) prevalecen: si hay un signo crítico, es Alto Riesgo.

Los umbrales se muestran en las unidades originales (el modelo los guarda escalados con RobustScaler).
`recorrido()` devuelve solo tipos simples (listas, números y textos): lo dibuja src/ui_recorrido.py.
"""
import numpy as np
import pandas as pd

from src.clinical_rules import ETIQUETAS_PROTEINURIA, evaluar_riesgo_hibrido
from src.config import NOMBRES_CLASES, VARS_CON_NULOS

# Casos de demostración (los mismos de la página de triaje)
CASOS = {
    "Caso 1 · Emergencia (Uribia)": dict(
        edad=26, municipio="Uribia", area_residencia="Rural disperso", pertenencia_etnica="Wayuu",
        semanas_gestacion=31, n_controles_prenatales=1, atendido_por="Partera tradicional",
        pas_mmhg=165, pad_mmhg=108, fcf_bpm=None, glucosa_mgdl=110.5, proteinuria=2, convulsiones=1),
    "Caso 2 · Sin controles previos (Manaure)": dict(
        edad=17, municipio="Manaure", area_residencia="Rural disperso", pertenencia_etnica="Wayuu",
        semanas_gestacion=24, n_controles_prenatales=0, atendido_por="Auxiliar de enfermeria",
        pas_mmhg=128, pad_mmhg=82, fcf_bpm=150.0, glucosa_mgdl=None, proteinuria=0, convulsiones=0),
    "Caso 3 · Control de rutina (Valledupar)": dict(
        edad=27, municipio="Valledupar", area_residencia="Cabecera", pertenencia_etnica="Mestiza",
        semanas_gestacion=28, n_controles_prenatales=5, atendido_por="Medico",
        pas_mmhg=110, pad_mmhg=70, fcf_bpm=142.0, glucosa_mgdl=88.0, proteinuria=0, convulsiones=0),
}
ARBOLES_VISIBLES = 6
ULTIMA = "Última evaluación del triaje"
# (dato, etiqueta corta, unidad): los 11 datos de la gestante que usa el modelo, en el orden en que se dibujan
DATOS = [
    ("edad", "Edad", "años"), ("semanas_gestacion", "Semanas", "sem"), ("n_controles_prenatales", "Controles", ""),
    ("pas_mmhg", "PAS", "mmHg"), ("pad_mmhg", "PAD", "mmHg"), ("fcf_bpm", "FCF", "lpm"), ("glucosa_mgdl", "Glucosa", "mg/dL"),
    ("proteinuria", "Proteinuria", ""), ("convulsiones", "Convulsiones", ""), ("area_residencia", "Área", ""),
    ("atendido_por", "Atiende", ""),
]
ETIQUETA = {dato: etiqueta for dato, etiqueta, _ in DATOS}
UNIDAD = {dato: unidad for dato, _, unidad in DATOS}
INDICADORES = {"glucosa_no_disponible": "glucosa_mgdl", "fcf_no_disponible": "fcf_bpm"}
CATEGORICAS = ("area_residencia", "atendido_por")
ACENTOS = {"Medico": "Médico", "Auxiliar de enfermeria": "Auxiliar de enfermería"}


def _numero(valor, decimales=1):
    """128.0 -> «128»; 139.5 -> «139,5»."""
    texto = f"{float(valor):.{decimales}f}".rstrip("0").rstrip(".")
    return texto.replace(".", ",")


def _texto_dato(dato, valor):
    if dato == "convulsiones":
        return "Sí" if valor else "No"
    if dato == "proteinuria":
        return ETIQUETAS_PROTEINURIA.get(int(valor), str(int(valor)))
    if dato in CATEGORICAS:
        return ACENTOS.get(valor, str(valor))
    return f"{_numero(valor)} {UNIDAD[dato]}".strip()


def _origen(variable):
    """El dato de la gestante del que sale una variable de entrada, y la categoría si es One-Hot."""
    if variable in INDICADORES:
        return INDICADORES[variable], None
    for dato in CATEGORICAS:
        if variable.startswith(dato + "_"):
            return dato, variable[len(dato) + 1:]
    return variable, None


def _etiqueta_variable(variable):
    dato, categoria = _origen(variable)
    if variable in INDICADORES:
        return f"¿Falta {ETIQUETA[dato].lower() if dato != 'fcf_bpm' else 'FCF'}?"
    return ACENTOS.get(categoria, categoria) if categoria else ETIQUETA[dato]


def recorrido(registro, modelo, n_arboles=ARBOLES_VISIBLES):
    """El camino de una gestante por el modelo en uso y las reglas. Ver la descripción del módulo."""
    resultado = evaluar_riesgo_hibrido(registro, modelo)
    fila = pd.DataFrame([{k: (np.nan if v is None else v) for k, v in registro.items()}])
    imputada = modelo.named_steps["imputacion"].transform(fila)
    transformador = modelo.named_steps["transformacion"]
    x = np.asarray(transformador.transform(imputada), dtype=np.float64)[0]
    variables = [str(v) for v in transformador.get_feature_names_out()]
    escalador = transformador.named_transformers_["continuas"]
    continuas = {c: (float(centro), float(escala)) for c, centro, escala in
                 zip(next(cols for nombre, _, cols in transformador.transformers_ if nombre == "continuas"),
                     escalador.center_, escalador.scale_)}
    faltaba = {dato: registro.get(dato) is None or pd.isna(registro.get(dato)) for dato in VARS_CON_NULOS}

    datos = [{"nombre": dato, "etiqueta": etiqueta, "valor": _texto_dato(dato, imputada[dato].iloc[0]),
              "imputado": bool(faltaba.get(dato, False))} for dato, etiqueta, _ in DATOS]
    indice_dato = {d["nombre"]: i for i, d in enumerate(datos)}

    def valor_original(variable):
        """El valor de la variable en unidades legibles (deshace el escalado)."""
        if variable in continuas:
            return float(imputada[variable].iloc[0])
        return float(x[variables.index(variable)])

    entradas = [{"nombre": v, "etiqueta": _etiqueta_variable(v), "dato": indice_dato[_origen(v)[0]],
                 "valor": round(valor_original(v), 2)} for v in variables]

    def pregunta(variable, umbral, cumple):
        """La pregunta de un nodo en lenguaje claro, su respuesta y el valor de la gestante."""
        dato, categoria = _origen(variable)
        if variable in continuas:
            centro, escala = continuas[variable]
            limite = umbral * escala + centro
            return (f"¿{ETIQUETA[dato]} ≤ {_numero(limite)} {UNIDAD[dato]}?".replace(" ?", "?"),
                    f"{'sí' if cumple else 'no'} (vale {_texto_dato(dato, imputada[dato].iloc[0])})")
        if variable in INDICADORES:
            return f"¿Falta el dato de {'FCF' if dato == 'fcf_bpm' else ETIQUETA[dato].lower()}?", "no" if cumple else "sí"
        if categoria:  # One-Hot: x ≤ 0,5 quiere decir que NO es esa categoría
            return f"¿{ETIQUETA[dato]} es {ACENTOS.get(categoria, categoria)}?", "no" if cumple else "sí"
        if variable == "convulsiones":
            return "¿Tiene convulsiones?", "no" if cumple else "sí"
        if variable == "proteinuria":  # 0, 1 o 2 cruces: «≤ 0,5» es lo mismo que «negativa»
            hasta = int(np.floor(umbral))
            texto = "¿Proteinuria negativa?" if hasta <= 0 else "¿Proteinuria negativa o +?" if hasta == 1 else "¿Proteinuria hasta ++?"
            return texto, f"{'sí' if cumple else 'no'} (es {_texto_dato(dato, registro[dato])})"
        return (f"¿{ETIQUETA[dato]} ≤ {_numero(umbral)}?", f"{'sí' if cumple else 'no'} (vale {_texto_dato(dato, registro[dato])})")

    bosque = modelo.named_steps["modelo"]
    x32 = x.astype(np.float32)  # scikit-learn compara en float32
    hojas, arboles = [], []
    for k, estimador in enumerate(bosque.estimators_):
        arbol, nodo, pasos = estimador.tree_, 0, []
        while arbol.children_left[nodo] != -1:
            variable, umbral = int(arbol.feature[nodo]), float(arbol.threshold[nodo])
            cumple = float(x32[variable]) <= umbral  # el dato en float32 y el umbral en doble precisión, como scikit-learn
            if k < n_arboles:
                texto, respuesta = pregunta(variables[variable], umbral, cumple)
                pasos.append({"variable": variable, "pregunta": texto, "respuesta": respuesta, "izquierda": cumple})
            nodo = int(arbol.children_left[nodo] if cumple else arbol.children_right[nodo])
        valores = arbol.value[nodo][0]
        hoja = valores / valores.sum()
        hojas.append(hoja)
        if k < n_arboles:
            arboles.append({"numero": k + 1, "pasos": pasos, "hoja": [round(float(p), 4) for p in hoja],
                            "clase": int(np.argmax(hoja))})
    hojas = np.array(hojas)
    probabilidades = hojas.mean(axis=0)
    inclinacion = hojas.argmax(axis=1)  # la clase a la que se inclina cada árbol

    return {
        "datos": datos, "variables": entradas, "arboles": arboles, "n_arboles": int(bosque.n_estimators),
        "inclinacion": [int(c) for c in inclinacion],
        "arboles_por_clase": [int((inclinacion == c).sum()) for c in range(len(NOMBRES_CLASES))],
        "probabilidades": [round(float(p), 4) for p in probabilidades],
        "clases": list(NOMBRES_CLASES), "clase_modelo": int(np.argmax(probabilidades)),
        "reglas": list(resultado.alertas), "signos_alarma": list(resultado.signos_alarma),
        "origen": resultado.origen, "clase": int(resultado.clase), "categoria": resultado.categoria,
    }


def en_texto(r):
    """El recorrido contado en frases (lo mismo que la animación, para leerlo o para un lector de pantalla)."""
    pct = lambda p: f"{p * 100:.1f}".replace(".", ",") + " %"  # noqa: E731
    imputados = [d["etiqueta"] for d in r["datos"] if d["imputado"]]
    frases = [f"**1. Entradas.** Los {len(r['datos'])} datos de la gestante se convierten en {len(r['variables'])} variables"
              + (f"; {' y '.join(imputados)} no se midió y se completó con la mediana de su área y trimestre." if imputados else ".")]
    primero = r["arboles"][0]
    preguntas = "; ".join(f"{p['pregunta']} {p['respuesta']}" for p in primero["pasos"][:3])
    frases.append(f"**2. Bosque.** Cada uno de los {r['n_arboles']} árboles le hace preguntas hasta llegar a una hoja. "
                  f"El árbol 1 hizo {len(primero['pasos'])}: {preguntas}… y terminó en una hoja de {r['clases'][primero['clase']]}.")
    frases.append("**3. Promedio.** " + ", ".join(f"{n} árboles se inclinan por {c}" for n, c in zip(r["arboles_por_clase"], r["clases"]))
                  + ". El promedio de las 300 hojas da: " + ", ".join(f"{c} {pct(p)}" for c, p in zip(r["clases"], r["probabilidades"]))
                  + f". El modelo dice **{r['clases'][r['clase_modelo']]}**.")
    if r["origen"] == "regla_clinica":
        frases.append("**4. Reglas clínicas.** Se activa: " + "; ".join(r["reglas"]) + ". La regla prevalece sobre el modelo.")
    elif r["origen"] == "signo_alarma_3280":
        frases.append("**4. Signos de alarma.** " + "; ".join(r["signos_alarma"]) + ": el triaje sube a Alto Riesgo.")
    else:
        frases.append("**4. Reglas clínicas.** Ningún signo crítico: decide el modelo.")
    frases.append(f"**5. Resultado.** **{r['categoria']}**.")
    return frases
