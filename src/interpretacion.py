"""Fase 3 — Interpretación de las métricas: qué es cada una, por qué se usa, cómo se lee y qué dice hoy.

Las frases se arman con plantillas a partir de los números del sistema elegido (nada escrito a mano): si
cambian el modelo, la partición o los datos, cambian las frases.

Se mide el sistema híbrido (modelo + reglas clínicas) sobre patrones USADOS (entrenamiento, validación y
prueba) y NO USADOS (el lote de demostración y los registros nuevos agregados a mano), y se comparan.

Avisos que acompañan toda métrica (decisión del equipo):
- miden cuánto reproduce el sistema el etiquetado sintético, no el desempeño clínico;
- el 100 % de sensibilidad vale solo para los casos con signo crítico, que decide la regla;
  el recall global de Alto Riesgo se informa con su intervalo de confianza.
"""
import joblib
import numpy as np
from sklearn.metrics import confusion_matrix

from src import experimentos
from src.clinical_rules import mascara_reglas, predecir_hibrido
from src.config import CLASE_ALTO, DIR_MODELOS, NOMBRES_CLASES, SEMILLA
from src.data_preprocessing import PARTICION_OFICIAL
from src.evaluate import MATRIZ_COSTO, calcular_metricas, intervalo_bootstrap

MODELO_EN_USO = "Modelo en uso (v1, oficial de la Fase 2)"
LOTE = "Lote de demostración"
NUEVOS = "Registros nuevos"
# Qué hizo el modelo con cada conjunto
USO = {
    "Entrenamiento": "Usado: el modelo se ajustó con él",
    "Validación": "Usado: sirvió para elegir el modelo",
    "Prueba": "Usado solo para medir, al final",
    LOTE: "No usado: se apartó antes de partir",
    NUEVOS: "No usado: se agregó a mano después de entrenar",
}
AVISO = ("Estas métricas miden **cuánto reproduce el sistema el etiquetado sintético**, no su desempeño clínico. "
         "No hay todavía datos reales de gestantes para validarlo.")
EXPLICACION = (
    "- **Por qué salen tan altas.** Las etiquetas del dataset sintético se generaron con umbrales parecidos a los de las "
    "reglas clínicas. El sistema acierta en buena parte porque aprende esos mismos umbrales, no porque se haya comprobado "
    "con pacientes.\n"
    "- **Por qué suben con más registros generados.** Los registros generados se interpolan entre gestantes de la misma "
    "clase: quedan muy cerca unos de otros, así que la validación y la prueba se parecen al entrenamiento. Con más "
    "registros sintéticos las métricas tienden a 1,0 sin que haya más evidencia.\n"
    "- **El 100 % de sensibilidad no es global.** Vale solo para los casos con signo crítico (presión ≥ 160/110, "
    "convulsiones o proteinuria ≥ ++), que decide la regla. El recall global de Alto Riesgo es menor y se informa con "
    "su intervalo de confianza.\n"
    "- **Qué falta.** Validar con registros reales anonimizados de una ESE/IPS y con un asesor clínico."
)


def _fmt(valor, decimales=3):
    return f"{valor:.{decimales}f}".replace(".", ",")


def _pct(valor):
    return f"{valor * 100:.1f}".replace(".", ",") + " %"


def _matriz(y, pred):
    return np.bincount(y * 3 + pred, minlength=9).reshape(3, 3)


def _recall_alto(y, pred):
    """Igual que recall_score(labels=[Alto]) de scikit-learn, pero rápido: el bootstrap lo llama 2.000 veces."""
    matriz = _matriz(y, pred)
    return matriz[CLASE_ALTO, CLASE_ALTO] / matriz[CLASE_ALTO].sum()


def _f1_macro(y, pred):
    """Igual que f1_score(average='macro') de scikit-learn: promedia las clases presentes en y o en pred."""
    matriz = _matriz(y, pred)
    presentes = (matriz.sum(axis=0) + matriz.sum(axis=1)) > 0
    return float(np.mean(np.array(_f1_por_clase(matriz))[presentes]))


def evaluar(modelo, X, y, con_intervalos=False):
    """Métricas, matriz de confusión y signos críticos del sistema híbrido sobre un conjunto."""
    y = np.asarray(y)
    pred, proba, _ = predecir_hibrido(modelo, X)
    criticos = np.asarray(mascara_reglas(X))
    resultado = {
        "metricas": {k: float(v) for k, v in calcular_metricas(y, pred, proba).items()},
        "matriz": confusion_matrix(y, pred, labels=[0, 1, 2]).tolist(),
        "criticos": int(criticos.sum()), "criticos_alto": int((pred[criticos] == CLASE_ALTO).sum()),
    }
    if con_intervalos:
        resultado["ic_recall_alto"] = [float(v) for v in intervalo_bootstrap(y, pred, _recall_alto)]
        resultado["ic_f1_macro"] = [float(v) for v in intervalo_bootstrap(y, pred, _f1_macro)]
    return resultado


def evaluar_sistema(sistema=MODELO_EN_USO):
    """Evalúa el modelo en uso o una versión del registro sobre sus conjuntos (y el lote, si le corresponde).

    Devuelve {'sistema', 'datos', 'conjuntos': {nombre: evaluación}}; la prueba y el lote llevan intervalos.
    """
    if sistema == MODELO_EN_USO:
        modelo = joblib.load(DIR_MODELOS / "modelo_random_forest.joblib")
        particiones = experimentos._particiones(None, PARTICION_OFICIAL, SEMILLA)
        conjuntos = dict(zip(["Entrenamiento", "Validación", "Prueba"], zip(particiones[:3], particiones[3:])))
        datos, usados_por_el_sistema = experimentos.DATOS_BASE, []
    else:
        registro, conjuntos = experimentos.conjuntos_de(sistema)
        modelo, datos = experimentos.cargar_modelo(sistema), registro["datos"]
        usados_por_el_sistema = registro.get("patrones") or []
        if registro.get("datos_huella"):
            from src import conjunto_trabajo
            from src.data_preprocessing import separar_xy

            if conjunto_trabajo.meta()["n_lote"]:
                conjuntos[LOTE] = separar_xy(conjunto_trabajo.lote().drop(columns="origen", errors="ignore"))
    from src import patrones
    from src.data_preprocessing import separar_xy as _separar

    nuevos = patrones.vigentes()
    if not nuevos.empty:  # los patrones que este sistema no usó para entrenar
        nuevos = nuevos[~nuevos["id_gestante"].isin(usados_por_el_sistema)]
    if len(nuevos):
        X, y = _separar(nuevos.drop(columns=["origen", "etiqueta_origen"], errors="ignore"))
        conjuntos[NUEVOS] = (X.reindex(columns=conjuntos["Prueba"][0].columns), y)
    return {"sistema": sistema, "datos": datos,
            "conjuntos": {nombre: evaluar(modelo, X, y, con_intervalos=nombre in ("Prueba", LOTE))
                          for nombre, (X, y) in conjuntos.items()}}


def tabla_comparativa(conjuntos):
    """Una fila por conjunto: usados y no usados, con las mismas métricas."""
    return [{
        "Conjunto": nombre, "¿Lo usó el modelo?": USO[nombre], "Registros": int(e["metricas"]["n"]),
        "Accuracy": e["metricas"]["accuracy"], "Precisión macro": e["metricas"]["precision_macro"],
        "Recall macro": e["metricas"]["recall_macro"], "F1-macro": e["metricas"]["f1_macro"],
        "Recall Alto": e["metricas"]["recall_alto"], "ROC-AUC": e["metricas"].get("roc_auc_ovr_macro"),
        "Costo clínico": int(e["metricas"]["costo_clinico_total"]),
    } for nombre, e in conjuntos.items()]


def frase_comparacion(conjuntos):
    """Compara lo usado con lo no usado: entrenamiento frente a prueba y, si hay, frente al lote."""
    f1 = {n: e["metricas"]["f1_macro"] for n, e in conjuntos.items()}
    partes = [f"En entrenamiento el F1-macro es {_fmt(f1['Entrenamiento'])} y en prueba {_fmt(f1['Prueba'])}: "
              f"{_fmt(f1['Entrenamiento'] - f1['Prueba'])} de diferencia. Esa caída es lo que el modelo memorizó y no generaliza."]
    if LOTE in f1:
        diferencia = f1["Prueba"] - f1[LOTE]
        partes.append(f"En el lote de demostración, que el modelo nunca usó, es {_fmt(f1[LOTE])}: "
                      + ("prácticamente igual que en prueba." if abs(diferencia) < 0.01 else
                         f"{_fmt(abs(diferencia))} {'menos' if diferencia > 0 else 'más'} que en prueba."))
    if NUEVOS in conjuntos:
        matriz = np.array(conjuntos[NUEVOS]["matriz"])
        partes.append(f"De los {int(matriz.sum())} registro(s) nuevo(s) agregados a mano, que el modelo tampoco usó, "
                      f"acertó {int(np.trace(matriz))}.")
    return " ".join(partes)


def frase_criticos(evaluacion):
    """El 100 % vale solo para los signos críticos; el recall global de Alto va con su intervalo."""
    m, matriz = evaluacion["metricas"], np.array(evaluacion["matriz"])
    reales_alto = int(matriz[CLASE_ALTO].sum())
    if not reales_alto:
        return "**Signos críticos y recall de Alto Riesgo:** en este conjunto no hay gestantes de Alto Riesgo; no se pueden medir."
    frase = (f"**Signos críticos:** {evaluacion['criticos_alto']} de {evaluacion['criticos']} casos con signo crítico salen "
             f"Alto Riesgo, porque los decide la regla (100 % por construcción). **Recall global de Alto Riesgo:** "
             f"{_fmt(m['recall_alto'])} ({int(matriz[CLASE_ALTO, CLASE_ALTO])} de {reales_alto})")
    if "ic_recall_alto" in evaluacion:
        lo, hi = evaluacion["ic_recall_alto"]
        frase += f", con intervalo de confianza del 95 % de {_fmt(lo)} a {_fmt(hi)}"
    if m["recall_alto"] < 1:
        return frase + ". No es 100 %: el sistema no detecta todos los casos graves."
    return frase + ". Aquí las detectó todas, pero eso vale solo para este conjunto: no es una garantía global."


def _f1_por_clase(matriz):
    valores = []
    for k in range(len(matriz)):
        tp, fp, fn = matriz[k, k], matriz[:, k].sum() - matriz[k, k], matriz[k].sum() - matriz[k, k]
        valores.append(2 * tp / (2 * tp + fp + fn) if tp else 0.0)
    return valores


def paneles(evaluacion):
    """Los siete paneles: nombre, valor, «¿Qué es?», «¿Por qué la usamos?», «¿Cómo se lee?» y la frase del resultado."""
    m, matriz = evaluacion["metricas"], np.array(evaluacion["matriz"])
    n, reales, predichos = int(matriz.sum()), matriz.sum(axis=1), matriz.sum(axis=0)
    aciertos = int(np.trace(matriz))
    mayoritaria = int(reales.argmax())
    tp_alto = int(matriz[CLASE_ALTO, CLASE_ALTO])
    fn_alto, fp_alto = int(reales[CLASE_ALTO] - tp_alto), int(predichos[CLASE_ALTO] - tp_alto)
    f1_clase = _f1_por_clase(matriz)
    debil = int(np.argmin(f1_clase))

    errores = matriz.copy()
    np.fill_diagonal(errores, 0)
    if errores.sum():
        real, pred = np.unravel_index(errores.argmax(), errores.shape)
        frase_matriz = (f"De {n} gestantes, {aciertos} están en la diagonal (aciertos) y {int(errores.sum())} fuera. El error más "
                        f"frecuente: {int(errores[real, pred])} de {NOMBRES_CLASES[real]} clasificada(s) como {NOMBRES_CLASES[pred]}. "
                        f"Graves clasificadas como Bajo Riesgo, el error más peligroso: {int(matriz[CLASE_ALTO, 0])}.")
    else:
        frase_matriz = f"Las {n} gestantes están en la diagonal: no hay errores en este conjunto."
    costos = errores * MATRIZ_COSTO
    if costos.sum():
        real, pred = np.unravel_index(costos.argmax(), costos.shape)
        frase_costo = (f"Los {int(errores.sum())} errores suman {int(costos.sum())} puntos. Lo que más pesa: {int(errores[real, pred])} de "
                       f"{NOMBRES_CLASES[real]} clasificada(s) como {NOMBRES_CLASES[pred]} × {int(MATRIZ_COSTO[real, pred])} = "
                       f"{int(costos[real, pred])} puntos.")
    else:
        frase_costo = "Sin errores, el costo es 0."
    ic_recall = (f" Intervalo de confianza del 95 %: de {_fmt(evaluacion['ic_recall_alto'][0])} a {_fmt(evaluacion['ic_recall_alto'][1])}."
                 if "ic_recall_alto" in evaluacion else "")
    ic_f1 = (f" Intervalo de confianza del 95 %: de {_fmt(evaluacion['ic_f1_macro'][0])} a {_fmt(evaluacion['ic_f1_macro'][1])}."
             if "ic_f1_macro" in evaluacion else "")
    auc = m.get("roc_auc_ovr_macro")

    return [
        {"nombre": "Accuracy (exactitud)", "valor": _fmt(m["accuracy"]),
         "que_es": "La proporción de gestantes cuya clase el sistema acertó, sin distinguir cuál.",
         "por_que": "Es la más fácil de entender, pero se informa solo como referencia: con clases desbalanceadas engaña.",
         "como_se_lee": "De 0 a 1; más alto es mejor. Hay que compararla con lo que acertaría un sistema que no hace nada.",
         "frase": (f"Acertó {aciertos} de {n} ({_pct(m['accuracy'])}). Pero un sistema que respondiera siempre "
                   f"«{NOMBRES_CLASES[mayoritaria]}» acertaría {_pct(reales[mayoritaria] / n)} sin detectar un solo caso de Alto "
                   f"Riesgo, que son apenas {int(reales[CLASE_ALTO])} de {n}. Por eso el accuracy no basta.")},
        {"nombre": "Precisión", "valor": _fmt(m["precision_macro"]),
         "que_es": "De las gestantes que el sistema marcó en una clase, cuántas lo eran de verdad. Se promedian las tres clases (macro).",
         "por_que": "Mide las falsas alarmas: una remisión innecesaria cuesta traslado y confianza en zonas dispersas.",
         "como_se_lee": "De 0 a 1; más alto es mejor. Baja cuando el sistema alerta de más.",
         "frase": (f"Marcó {int(predichos[CLASE_ALTO])} como Alto Riesgo y {tp_alto} lo eran ({_pct(m['precision_alto'])}): "
                   f"{fp_alto} falsa(s) alarma(s). Promedio de las tres clases: {_fmt(m['precision_macro'])}.")},
        {"nombre": "Recall de Alto Riesgo (sensibilidad)", "valor": _fmt(m["recall_alto"]),
         "que_es": "De las gestantes que de verdad son de Alto Riesgo, cuántas detectó el sistema.",
         "por_que": "Es la métrica de seguridad: una grave no detectada puede costar una vida. Importa más que el accuracy.",
         "como_se_lee": "De 0 a 1; más alto es mejor. Lo que le falta para 1 son las graves que se escaparon.",
         "frase": (f"De {int(reales[CLASE_ALTO])} gestantes de Alto Riesgo detectó {tp_alto} ({_pct(m['recall_alto'])}) y dejó pasar "
                   f"{fn_alto}; de esas, {int(matriz[CLASE_ALTO, 0])} como Bajo Riesgo.{ic_recall}" if reales[CLASE_ALTO] else
                   "En este conjunto no hay gestantes de Alto Riesgo: el recall no se puede medir.")},
        {"nombre": "F1-macro", "valor": _fmt(m["f1_macro"]),
         "que_es": "El F1 combina precisión y recall de una clase; el macro promedia las tres clases dándoles el mismo peso.",
         "por_que": "Es la métrica con que se elige el modelo: no deja que la clase más numerosa tape a la de Alto Riesgo.",
         "como_se_lee": "De 0 a 1; más alto es mejor. Si una clase va mal, el promedio lo delata.",
         "frase": ("Por clase: " + ", ".join(f"{c} {_fmt(v)}" for c, v in zip(NOMBRES_CLASES, f1_clase))
                   + f". Promedio: {_fmt(m['f1_macro'])}. La clase más difícil es {NOMBRES_CLASES[debil]}.{ic_f1}")},
        {"nombre": "ROC-AUC", "valor": _fmt(auc) if auc is not None else "—",
         "que_es": "Qué tan bien ordenan las probabilidades del sistema a las gestantes de una clase por encima de las demás.",
         "por_que": "No depende del umbral de decisión: dice si el sistema separa las clases, aunque luego se ajuste el corte.",
         "como_se_lee": "0,5 es azar y 1 es separación perfecta. Se promedia cada clase contra las otras dos.",
         "frase": (f"{_fmt(auc)}: al tomar al azar una gestante de una clase y otra que no lo es, el sistema les da el orden "
                   f"correcto el {_pct(auc)} de las veces, en promedio." if auc is not None else
                   "No se puede calcular: en este conjunto no están las tres clases.")},
        {"nombre": "Matriz de confusión", "valor": f"{aciertos}/{n}",
         "que_es": "La tabla de clase real (filas) contra clase asignada (columnas). La diagonal son los aciertos.",
         "por_que": "Muestra en qué se equivoca el sistema, no solo cuánto: no es lo mismo confundir Bajo con Medio que Alto con Bajo.",
         "como_se_lee": "Debajo de la diagonal el sistema subestimó el riesgo (lo grave); encima, lo sobreestimó.",
         "frase": frase_matriz, "matriz": matriz.tolist()},
        {"nombre": "Costo clínico", "valor": str(int(m["costo_clinico_total"])),
         "que_es": "La suma de los errores, cada uno multiplicado por su gravedad según la matriz de costo del equipo.",
         "por_que": "Subestimar el riesgo es mucho peor que sobreestimarlo: una grave tratada como Bajo pesa 10; una sana remitida, 2.",
         "como_se_lee": "Menos es mejor; 0 es ningún error. Depende del tamaño del conjunto: se comparan conjuntos del mismo tamaño. "
                        "Los pesos son supuestos del equipo, por validar con un asesor clínico.",
         "frase": frase_costo, "matriz": MATRIZ_COSTO.tolist()},
    ]
