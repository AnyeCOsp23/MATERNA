"""Fase 3, etapa 5: interpretación de las métricas con frases armadas desde los números y avisos fijos."""
import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import f1_score, recall_score

from src import conjunto_trabajo, experimentos, interpretacion
from src.config import DIR_METRICAS
from src.depuracion import depurar
from src.evaluate import MATRIZ_COSTO, calcular_metricas
from src.generador_sintetico import generar


@pytest.fixture(scope="module", autouse=True)
def experimentos_aislados(tmp_path_factory):
    """Carpeta de experimentos vacía: los patrones o versiones que alguien guardó al usar el laboratorio en este
    equipo (carpeta experimentos/, fuera del repositorio) no deben cambiar el resultado de las pruebas."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv(experimentos.VARIABLE_DIRECTORIO, str(tmp_path_factory.mktemp("experimentos")))
        yield


@pytest.fixture(scope="module")
def en_uso():
    return interpretacion.evaluar_sistema()


def evaluacion_de(matriz):
    """Una evaluación armada a mano a partir de una matriz de confusión."""
    matriz = np.array(matriz)
    y = np.repeat([0, 1, 2], matriz.sum(axis=1))
    pred = np.concatenate([np.repeat([0, 1, 2], fila) for fila in matriz])
    return {"metricas": calcular_metricas(y, pred), "matriz": matriz.tolist(), "criticos": 4, "criticos_alto": 4}


def test_las_metricas_rapidas_del_bootstrap_son_las_de_scikit_learn():
    rng = np.random.default_rng(0)
    for _ in range(300):
        n = rng.integers(5, 60)
        y, pred = rng.integers(0, 3, n), rng.integers(0, 3, n)
        if (y == 2).any():
            assert interpretacion._f1_macro(y, pred) == pytest.approx(f1_score(y, pred, average="macro", zero_division=0), abs=1e-12)
            assert interpretacion._recall_alto(y, pred) == pytest.approx(
                recall_score(y, pred, labels=[2], average="macro", zero_division=0), abs=1e-12)


def test_el_modelo_en_uso_da_las_cifras_oficiales_de_la_fase_2(en_uso):
    oficial = pd.read_csv(DIR_METRICAS / "metricas_test.csv").set_index("sistema").loc["Híbrido (Random Forest + reglas)"]
    prueba = en_uso["conjuntos"]["Prueba"]
    for metrica in ("accuracy", "precision_macro", "f1_macro", "recall_alto", "roc_auc_ovr_macro", "costo_clinico_total"):
        assert prueba["metricas"][metrica] == pytest.approx(oficial[metrica], abs=1e-4), metrica
    assert "[{:.3f}, {:.3f}]".format(*prueba["ic_recall_alto"]) == oficial["recall_alto_ic95"]
    assert "[{:.3f}, {:.3f}]".format(*prueba["ic_f1_macro"]) == oficial["f1_macro_ic95"]
    assert list(en_uso["conjuntos"]) == ["Entrenamiento", "Validación", "Prueba"]  # sin lote: no se entrenó con un conjunto de trabajo
    assert [int(e["metricas"]["n"]) for e in en_uso["conjuntos"].values()] == [840, 180, 180]


def test_el_100_por_ciento_solo_vale_para_los_signos_criticos(en_uso):
    prueba = en_uso["conjuntos"]["Prueba"]
    assert prueba["criticos"] == prueba["criticos_alto"] > 0  # la regla decide: todos salen Alto
    assert prueba["metricas"]["recall_alto"] < 1  # pero el recall global de Alto no es 100 %
    frase = interpretacion.frase_criticos(prueba)
    assert "100 % por construcción" in frase and "No es 100 %" in frase and "intervalo de confianza del 95 %" in frase
    assert "0,957" in frase and "22 de 23" in frase and "de 0,857 a 1,000" in frase
    assert "reproduce el sistema el etiquetado sintético" in interpretacion.AVISO and "no su desempeño clínico" in interpretacion.AVISO


def test_comparacion_de_usados_y_no_usados(en_uso):
    tabla = interpretacion.tabla_comparativa(en_uso["conjuntos"])
    assert [f["¿Lo usó el modelo?"] for f in tabla] == [interpretacion.USO[c] for c in ("Entrenamiento", "Validación", "Prueba")]
    assert tabla[0]["F1-macro"] > tabla[2]["F1-macro"]
    frase = interpretacion.frase_comparacion(en_uso["conjuntos"])
    assert "1,000" in frase and "0,963" in frase and "0,037" in frase and "lote" not in frase


def test_los_siete_paneles_se_arman_desde_los_numeros():
    paneles = interpretacion.paneles(evaluacion_de([[50, 2, 0], [1, 30, 1], [1, 2, 13]]))
    assert [p["nombre"].split(" (")[0] for p in paneles] == [
        "Accuracy", "Precisión", "Recall de Alto Riesgo", "F1-macro", "ROC-AUC", "Matriz de confusión", "Costo clínico"]
    for p in paneles:
        assert all(p[k] for k in ("valor", "que_es", "por_que", "como_se_lee", "frase")), p["nombre"]
    accuracy, precision, recall, f1, auc, confusion, costo = (p["frase"] for p in paneles)
    assert "Acertó 93 de 100 (93,0 %)" in accuracy and "«Bajo Riesgo» acertaría 52,0 %" in accuracy and "16 de 100" in accuracy
    assert "Marcó 14 como Alto Riesgo y 13 lo eran (92,9 %)" in precision and "1 falsa(s) alarma(s)" in precision
    assert "De 16 gestantes de Alto Riesgo detectó 13 (81,2 %) y dejó pasar 3; de esas, 1 como Bajo Riesgo" in recall
    assert "La clase más difícil es Alto Riesgo" in f1
    assert "No se puede calcular" in auc  # sin probabilidades no hay ROC-AUC
    assert "93 están en la diagonal" in confusion and "7 fuera" in confusion and "el error más peligroso: 1" in confusion
    # costo: 2×1 + 1×3 + 1×1 + 1×10 + 2×5 = 26; lo que más pesa empata en 10 y gana el primero (Alto como Bajo)
    assert paneles[6]["valor"] == "26" and "suman 26 puntos" in costo and "× 10 = 10 puntos" in costo
    assert paneles[5]["matriz"] == [[50, 2, 0], [1, 30, 1], [1, 2, 13]] and paneles[6]["matriz"] == MATRIZ_COSTO.tolist()


def test_paneles_sin_errores():
    paneles = interpretacion.paneles(evaluacion_de([[5, 0, 0], [0, 4, 0], [0, 0, 3]]))
    assert "no hay errores" in paneles[5]["frase"] and paneles[6]["frase"] == "Sin errores, el costo es 0."
    assert "dejó pasar 0" in paneles[2]["frase"]


def test_una_version_del_conjunto_de_trabajo_se_mide_tambien_en_el_lote(tmp_path, monkeypatch):
    monkeypatch.setenv(experimentos.VARIABLE_DIRECTORIO, str(tmp_path / "experimentos"))
    meta = conjunto_trabajo.establecer(depurar(generar(2500))[0], "Sintético de prueba", "ana", n_lote=250)
    version = experimentos.entrenar("Regresión Logística", datos=conjunto_trabajo.datos(), nombre_datos=conjunto_trabajo.descripcion(),
                                    huella_datos=meta["huella"])["registro"]["version"]
    evaluacion = interpretacion.evaluar_sistema(version)
    assert list(evaluacion["conjuntos"]) == ["Entrenamiento", "Validación", "Prueba", interpretacion.LOTE]
    lote = evaluacion["conjuntos"][interpretacion.LOTE]
    assert lote["metricas"]["n"] == 250 and "ic_recall_alto" in lote
    assert sum(e["metricas"]["n"] for n, e in evaluacion["conjuntos"].items() if n != interpretacion.LOTE) == meta["n_trabajo"]
    tabla = interpretacion.tabla_comparativa(evaluacion["conjuntos"])
    assert tabla[-1]["¿Lo usó el modelo?"].startswith("No usado")
    assert "lote de demostración, que el modelo nunca usó" in interpretacion.frase_comparacion(evaluacion["conjuntos"])
    # una versión sin lote (dataset base) no lo inventa; y si el conjunto cambia, se explica
    base = experimentos.entrenar("Regresión Logística")["registro"]["version"]
    assert interpretacion.LOTE not in interpretacion.evaluar_sistema(base)["conjuntos"]
    conjunto_trabajo.restablecer()
    with pytest.raises(ValueError, match="ya no es el conjunto"):
        interpretacion.evaluar_sistema(version)
