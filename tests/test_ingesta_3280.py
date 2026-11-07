"""Fase 3, bloque 1: catálogo de la Resolución 3280, seudonimización e ingesta de archivos de la IPS."""
import json

import numpy as np
import pandas as pd
import pytest

from src.clinical_rules import predecir_hibrido
from src.config import VARS_CATEGORICAS, VARS_CONTINUAS
from src.filtro_3280 import (
    DECISIONES, aplicar_filtro, cargar_catalogo, evaluar_alertas_3280, mapear_columnas, nombres,
    normalizar_nombre, tabla_decisiones, variables, variables_modelo,
)
from src.generar_ejemplo_ips import DIR_EJEMPLOS, generar_ejemplo
from src.inspeccionar_ips import aptos_para_modelo, inspeccionar, leer_por_lotes
from src.seudonimizacion import COLUMNA_SEUDONIMO, obtener_sal, seudonimizar, seudonimizar_dataframe

SAL = "sal-solo-para-pruebas-0123456789"
EJEMPLO_CSV = DIR_EJEMPLOS / "ips_ficticio_3280.csv"
EJEMPLO_XLSX = DIR_EJEMPLOS / "ips_ficticio_3280.xlsx"


# ------------------------------------------------------------------ catálogo
def test_variables_del_modelo_coinciden_con_la_fase_2():
    assert sorted(variables_modelo()) == sorted(VARS_CONTINUAS + ["proteinuria", "convulsiones"] + VARS_CATEGORICAS)


def test_catalogo_bien_formado():
    cat = cargar_catalogo()
    vistos = set()
    for v in cat["variables"]:
        assert v["decision"] in DECISIONES, v["nombre"]
        assert v["verificacion"] in cat["_verificacion"], v["nombre"]
        assert v["justificacion"].strip(), v["nombre"]
        assert v["nombre"] not in vistos
        vistos.add(v["nombre"])
        if "rango" in v:
            assert v["rango"][0] < v["rango"][1], v["nombre"]
        if "alerta" in v:
            assert v["decision"] == "capturar_alertar", v["nombre"]


def test_etnia_y_territorio_solo_para_auditoria():
    assert set(nombres("auditoria")) == {"pertenencia_etnica", "departamento", "municipio"}
    assert not set(nombres("auditoria")) & set(variables_modelo())


def test_tabla_de_decisiones_para_la_consola():
    tabla = tabla_decisiones()
    assert len(tabla) == len(variables())
    assert tabla["Decisión"].iloc[0] == "modelo"
    assert {"Variable", "Sección 3280", "Decisión", "Justificación", "Verificación"} <= set(tabla.columns)


@pytest.mark.parametrize("original, esperado", [
    ("TAS", "pas_mmhg"), ("Presión Sistólica", "pas_mmhg"), ("FETOCARDIA", "fcf_bpm"),
    ("Glicemia", "glucosa_mgdl"), ("Numero Documento", "numero_documento"), ("Zona", "area_residencia"),
])
def test_reconoce_encabezados_con_otros_nombres(original, esperado):
    assert mapear_columnas([original]) == {original: esperado}


def test_normalizar_nombre():
    assert normalizar_nombre("  Visión  Borrosa ") == "vision_borrosa"


# ------------------------------------------------------------------ seudonimización
def test_seudonimo_estable_y_sin_el_documento():
    a = seudonimizar("CC", "1.065.432", SAL)
    assert a == seudonimizar(" cc ", "1065432", SAL)
    assert len(a) == 64 and "1065432" not in a


def test_seudonimo_depende_de_la_sal_y_del_tipo():
    assert seudonimizar("CC", "1065432", SAL) != seudonimizar("CC", "1065432", SAL + "x")
    assert seudonimizar("CC", "1065432", SAL) != seudonimizar("TI", "1065432", SAL)


def test_sal_obligatoria(monkeypatch):
    monkeypatch.delenv("MATERNA_SAL", raising=False)
    with pytest.raises(RuntimeError):
        obtener_sal()
    monkeypatch.setenv("MATERNA_SAL", "corta")
    with pytest.raises(RuntimeError):
        obtener_sal()
    with pytest.raises(ValueError):
        seudonimizar("CC", "1065432", "")


def test_seudonimizar_dataframe_quita_el_documento():
    df = pd.DataFrame({"tipo_documento": ["CC", "CC", None], "numero_documento": ["123", "", "456"], "edad": [20, 21, 22]})
    out = seudonimizar_dataframe(df, SAL)
    assert list(out.columns) == [COLUMNA_SEUDONIMO, "edad"]
    assert out[COLUMNA_SEUDONIMO].isna().tolist() == [False, True, False]


# ------------------------------------------------------------------ filtro
def test_filtro_descarta_datos_personales_y_columnas_desconocidas():
    df = pd.DataFrame({"Primer Nombre": ["ANA"], "Numero Documento": ["123"], "Tipo Documento": ["CC"],
                       "TAS": ["120"], "Etnia": ["wayuu"], "Notas": ["x"]})
    r = aplicar_filtro(df, SAL)
    assert set(r.datos.columns) == {COLUMNA_SEUDONIMO, "pas_mmhg", "pertenencia_etnica"}
    assert r.columnas_eliminadas == ["primer_nombre"] and r.columnas_desconocidas == ["Notas"]
    assert r.datos.loc[0, "pertenencia_etnica"] == "Wayuu"
    assert "ANA" not in r.datos.to_string() and "123" not in r.datos.drop(columns=COLUMNA_SEUDONIMO).to_string()


def test_filtro_convierte_tipos_y_anula_valores_imposibles():
    df = pd.DataFrame({"pas_mmhg": ["120", "400", "abc"], "convulsiones": ["Sí", "no", "talvez"],
                       "atendido_por": ["Médico", "auxiliar de enfermería", "otro"], "hemoglobina_gdl": ["10,5", "12", None]})
    r = aplicar_filtro(df, SAL)
    d = r.datos
    assert d["pas_mmhg"].tolist()[0] == 120 and d["pas_mmhg"].isna().tolist() == [False, True, True]
    assert r.fuera_de_rango == {"pas_mmhg": 1}
    assert d["convulsiones"].tolist()[:2] == [1.0, 0.0] and np.isnan(d["convulsiones"].iloc[2])
    assert d["atendido_por"].tolist()[:2] == ["Medico", "Auxiliar de enfermeria"] and pd.isna(d["atendido_por"].iloc[2])
    assert d["hemoglobina_gdl"].tolist()[0] == 10.5


# ------------------------------------------------------------------ alertas de la ruta
def test_alerta_de_anemia():
    assert [a["variable"] for a in evaluar_alertas_3280({"hemoglobina_gdl": 10.5})] == ["hemoglobina_gdl"]
    assert evaluar_alertas_3280({"hemoglobina_gdl": 11.0}) == []


def test_signos_de_alarma_van_primero():
    alertas = evaluar_alertas_3280({"hemoglobina_gdl": 9, "cefalea": 1, "semanas_gestacion": 20, "calcio": 0})
    assert [a["severidad"] for a in alertas] == ["urgente", "atencion", "seguimiento"]


def test_calcio_pendiente_solo_desde_la_semana_14():
    assert evaluar_alertas_3280({"semanas_gestacion": 10, "calcio": 0}) == []
    assert evaluar_alertas_3280({"semanas_gestacion": 20, "calcio": 1}) == []
    assert len(evaluar_alertas_3280({"semanas_gestacion": 20, "calcio": 0})) == 1
    assert evaluar_alertas_3280({"semanas_gestacion": 20, "calcio": None}) == []


def test_cortes_por_validar_quedan_marcados():
    alerta = evaluar_alertas_3280({"ptog_ayunas_mgdl": 95})[0]
    assert alerta["verificada"] is False
    assert evaluar_alertas_3280({"hemoglobina_gdl": 9})[0]["verificada"] is True


# ------------------------------------------------------------------ ingesta del ejemplo ficticio
@pytest.fixture(scope="module")
def ingesta():
    return inspeccionar(EJEMPLO_CSV, SAL)


def test_el_ejemplo_versionado_coincide_con_el_generador():
    guardado = pd.read_csv(EJEMPLO_CSV, sep="|", encoding="latin-1", dtype=str, keep_default_na=False)
    nuevo = generar_ejemplo().astype(str).replace({"nan": "", "None": ""})
    assert guardado.shape == nuevo.shape and list(guardado.columns) == list(nuevo.columns)


def test_reporte_de_inspeccion(ingesta):
    _, r = ingesta
    assert (r.formato, r.separador, r.filas_leidas) == ("latin-1", "|", 307)
    assert r.centinelas == {"glucosa_mgdl": 5, "fecha_ultima_menstruacion": 2}
    assert r.fuera_de_rango == {"pas_mmhg": 2}
    assert r.filas_duplicadas_eliminadas == 4
    assert (r.gestantes_con_varias_atenciones, r.sin_documento) == (3, 2)
    assert r.columnas_desconocidas == ["observaciones"]
    assert r.aptas_modelo == 300 and r.faltantes_que_impiden_modelo == {"edad": 1, "pas_mmhg": 2}


def test_no_quedan_nombres_ni_documentos(ingesta):
    datos, _ = ingesta
    texto = datos.to_csv()
    assert "FICTICIO" not in texto and "observaciones" not in datos.columns
    crudo = pd.read_csv(EJEMPLO_CSV, sep="|", encoding="latin-1", dtype=str)
    assert not any(doc in texto for doc in crudo["Numero Documento"].dropna().head(50))


def test_lectura_por_lotes_da_el_mismo_resultado(ingesta):
    datos, _ = ingesta
    por_lotes, r = inspeccionar(EJEMPLO_CSV, SAL, tam_lote=7)
    assert r.lotes == 44
    pd.testing.assert_frame_equal(datos, por_lotes)


def test_excel_da_el_mismo_resultado(ingesta):
    datos, _ = ingesta
    desde_excel, r = inspeccionar(EJEMPLO_XLSX, SAL, tam_lote=50)
    assert r.formato == "xlsx"
    pd.testing.assert_frame_equal(datos, desde_excel, check_dtype=False)


def test_lee_utf8_con_coma(tmp_path, ingesta):
    crudo = pd.read_csv(EJEMPLO_CSV, sep="|", encoding="latin-1", dtype=str)
    ruta = tmp_path / "ips_utf8.csv"
    crudo.to_csv(ruta, index=False, encoding="utf-8")
    datos, r = inspeccionar(ruta, SAL)
    assert (r.formato, r.separador) == ("utf-8-sig", ",")
    pd.testing.assert_frame_equal(ingesta[0], datos)


def test_rechaza_formatos_binarios_antiguos(tmp_path):
    with pytest.raises(ValueError, match="xlsx"):
        leer_por_lotes(tmp_path / "prevalidador.xlsb")


def test_aptos_entran_al_modelo_hibrido(ingesta, modelos):
    aptos = aptos_para_modelo(ingesta[0])
    assert len(aptos) == 300
    pred, proba, por_regla = predecir_hibrido(modelos["Random Forest"], aptos)
    assert proba.shape == (300, 3) and np.allclose(proba.sum(axis=1), 1)
    assert (pred[por_regla] == 2).all()


def test_archivo_sin_variables_clinicas_no_es_apto(tmp_path):
    ruta = tmp_path / "solo_admin.csv"
    pd.DataFrame({"Numero Documento": ["1", "2"], "Primer Nombre": ["A", "B"], "Edad": ["20", "30"]}).to_csv(ruta, index=False)
    datos, r = inspeccionar(ruta, SAL)
    assert r.aptas_modelo == 0 and r.faltantes_que_impiden_modelo["pas_mmhg"] == "columna ausente"
    assert aptos_para_modelo(datos).empty


def test_plantilla_tiene_diccionario():
    plantilla = DIR_EJEMPLOS.parent / "plantillas" / "plantilla_ips_3280.xlsx"
    dic = pd.read_excel(plantilla, sheet_name="Diccionario")
    assert set(dic["Uso en MATERNA"]) == {"modelo", "capturar_alertar", "auditoria", "seudonimizar"}
    assert json.dumps(dic.to_dict()).count("primer_nombre") == 0
