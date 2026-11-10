"""Fase 3, parte 4b (commit C): carga masiva de la IPS, la referencia en Python de la pestaña «Carga IPS» de la app."""
import json

import joblib
import pytest

from src.carga_masiva import evaluar_archivo, obligatorias
from src.clinical_rules import evaluar_riesgo_hibrido, evaluar_riesgo_hibrido_lote
from src.exportar_a_dart import DIR_ASSETS, EJEMPLO_IPS, RUTA_MODELO, SAL_PRUEBA, generar_casos_carga
from src.inspeccionar_ips import COLUMNA_FILA, inspeccionar
from src.seudonimizacion import seudonimizar

EJEMPLO_XLSX = EJEMPLO_IPS.with_suffix(".xlsx")


@pytest.fixture(scope="module")
def pipeline():
    return joblib.load(RUTA_MODELO)


@pytest.fixture(scope="module")
def carga(pipeline):
    return evaluar_archivo(EJEMPLO_IPS, SAL_PRUEBA, pipeline)


def test_la_fila_no_cambia_la_ingesta():
    sin, reporte_sin = inspeccionar(EJEMPLO_IPS, SAL_PRUEBA)
    con, reporte_con = inspeccionar(EJEMPLO_IPS, SAL_PRUEBA, con_fila=True)
    assert con.drop(columns=COLUMNA_FILA).equals(sin)
    assert reporte_con == reporte_sin
    assert con[COLUMNA_FILA].iloc[0] == 2 and con[COLUMNA_FILA].is_unique  # el encabezado es la fila 1


def test_evalua_las_aptas_y_rechaza_las_incompletas(carga):
    reporte, resultados, rechazadas = carga
    assert len(resultados) == reporte.aptas_modelo == 300
    assert rechazadas == [{"fila": 27, "faltan": ["pas_mmhg"]}, {"fila": 122, "faltan": ["edad"]},
                          {"fila": 202, "faltan": ["pas_mmhg"]}]
    assert set(obligatorias()) == {"edad", "semanas_gestacion", "n_controles_prenatales", "pas_mmhg", "pad_mmhg",
                                   "proteinuria", "convulsiones", "area_residencia", "atendido_por"}


def test_triaje_ordenado_por_urgencia(carga):
    _, resultados, _ = carga
    clases = [r["clase"] for r in resultados]
    assert clases == sorted(clases, reverse=True) and set(clases) == {0, 1, 2}
    for a, b in zip(resultados, resultados[1:]):
        if a["clase"] == b["clase"]:
            assert a["probabilidades"][2] >= b["probabilidades"][2]
    assert {r["origen"] for r in resultados if r["clase"] == 2} == {"regla_clinica", "signo_alarma_3280", "modelo_ml"}


def test_sin_documentos_ni_nombres(carga):
    _, resultados, _ = carga
    texto = json.dumps(resultados)
    assert "FICTICIO" not in texto and "Numero" not in texto
    assert sum(r["id_seudonimo"] is None for r in resultados) == 2  # las dos filas sin documento
    assert all(len(r["id_seudonimo"]) == 64 for r in resultados if r["id_seudonimo"])


def test_lote_igual_a_una_por_una(pipeline):
    registros = [
        {"edad": 27, "area_residencia": "Cabecera", "semanas_gestacion": 28, "n_controles_prenatales": 5, "atendido_por": "Medico",
         "pas_mmhg": 110, "pad_mmhg": 70, "fcf_bpm": None, "glucosa_mgdl": 88.0, "proteinuria": 0, "convulsiones": 0},
        {"edad": 17, "area_residencia": "Rural disperso", "semanas_gestacion": 34, "n_controles_prenatales": 1,
         "atendido_por": "Partera tradicional", "pas_mmhg": 165, "pad_mmhg": 100, "fcf_bpm": 150.0, "glucosa_mgdl": None,
         "proteinuria": 1, "convulsiones": 0, "cefalea": 1},
        {"edad": 30, "area_residencia": "Cabecera", "semanas_gestacion": 20, "n_controles_prenatales": 3, "atendido_por": "Medico",
         "pas_mmhg": 120, "pad_mmhg": 80, "fcf_bpm": 140.0, "glucosa_mgdl": 90.0, "proteinuria": 0, "convulsiones": 0,
         "sangrado_genital": 1},
    ]
    for lote, r in zip(evaluar_riesgo_hibrido_lote(registros, pipeline), registros):
        assert lote == evaluar_riesgo_hibrido(r, pipeline)
    assert evaluar_riesgo_hibrido_lote([], pipeline) == []


def test_excel_da_la_misma_carga(carga, pipeline):
    _, resultados, rechazadas = carga
    reporte_x, resultados_x, rechazadas_x = evaluar_archivo(EJEMPLO_XLSX, SAL_PRUEBA, pipeline)
    assert reporte_x.formato == "xlsx"
    assert resultados_x == resultados and rechazadas_x == rechazadas


def test_casos_de_carga_vigentes(pipeline):
    """Lo guardado en casos_carga.json es lo que hoy calcula Python (la prueba de Dart compara contra esto)."""
    guardado = json.loads((DIR_ASSETS / "casos_carga.json").read_text(encoding="utf-8"))
    assert guardado == json.loads(json.dumps(generar_casos_carga(pipeline)))
    assert guardado["sal_prueba"] == SAL_PRUEBA
    for s in guardado["seudonimos"]:
        assert s["id_seudonimo"] == seudonimizar(s["tipo"], s["numero"], SAL_PRUEBA)
    assert len({s["id_seudonimo"] for s in guardado["seudonimos"]}) == len(guardado["seudonimos"]) - 2  # 3 formas del mismo CC
