"""Fase 3, etapa 4: generador sintético, depuración de datos crudos, conjunto de trabajo, lote de demostración
y escalabilidad."""
import numpy as np
import pandas as pd
import pytest

from src import conjunto_trabajo, experimentos
from src.clinical_rules import mascara_reglas, predecir_hibrido
from src.config import CLASE_ALTO, MAPA_TARGET, TARGET, VARS_CONTINUAS
from src.data_preprocessing import RANGOS_PLAUSIBLES, cargar_dataset, separar_xy
from src.depuracion import depurar, leer_crudo
from src.generador_sintetico import COLUMNA_ORIGEN, ORIGEN, a_texto, ensuciar, generar


@pytest.fixture(scope="module")
def base():
    return cargar_dataset()


@pytest.fixture(scope="module")
def generados():
    return generar(20000)


@pytest.fixture
def carpeta(tmp_path, monkeypatch):
    monkeypatch.setenv(experimentos.VARIABLE_DIRECTORIO, str(tmp_path / "experimentos"))
    return tmp_path / "experimentos"


def fila(**cambios):
    """Una gestante cruda (todo texto), como llega en un archivo plano."""
    registro = {"id_gestante": "X1", "edad": "27", "departamento": "Cesar", "municipio": "Valledupar",
                "pertenencia_etnica": "Mestiza", "area_residencia": "Cabecera", "semanas_gestacion": "28",
                "n_controles_prenatales": "5", "atendido_por": "Medico", "pas_mmhg": "110", "pad_mmhg": "70",
                "fcf_bpm": "142.0", "glucosa_mgdl": "88.0", "proteinuria": "0", "convulsiones": "FALSE",
                "riesgo_obstetrico": "Bajo Riesgo"}
    return {**registro, **cambios}


def crudo(*filas):
    return pd.DataFrame(list(filas), dtype=object)


# ------------------------------------------------------------------ generador
def test_generador_reproducible_con_la_misma_semilla():
    assert generar(800, 7).equals(generar(800, 7))
    assert not generar(800, 7).equals(generar(800, 8))
    # los primeros registros no dependen de cuántos se pidan después... sí dependen: solo se garantiza misma N y semilla
    assert len(generar(1)) == 1
    with pytest.raises(ValueError):
        generar(0)


def test_n_generados_son_n_registros_distintos_y_limpios():
    """10.000 generados dan 10.000 limpios: el generador nunca entrega dos registros iguales."""
    datos = generar(10000)
    assert not datos.drop(columns="id_gestante").duplicated().any()
    limpio, pasos = depurar(datos)
    assert len(limpio) == 10000 and all(p["Filas después"] == 10000 for p in pasos)


def test_generador_marca_el_origen_y_conserva_las_columnas(base, generados):
    assert list(generados.columns) == list(base.columns) + [COLUMNA_ORIGEN]
    assert (generados[COLUMNA_ORIGEN] == ORIGEN).all() and ORIGEN == "sintetico_generado"
    assert generados["id_gestante"].is_unique and not set(generados["id_gestante"]) & set(base["id_gestante"])
    assert generados.dtypes[base.columns].equals(base.dtypes)


def test_generador_no_inventa_valores_fuera_de_lo_observado(base, generados):
    for col in VARS_CONTINUAS:  # interpolar entre dos gestantes nunca sale del rango de las 1.200
        assert base[col].min() <= generados[col].min() and generados[col].max() <= base[col].max(), col
    for col in ["proteinuria", "convulsiones", "area_residencia", "atendido_por", "departamento", "pertenencia_etnica", TARGET]:
        assert set(generados[col].unique()) <= set(base[col].unique()), col
    # proporciones de clase y de datos faltantes como en el dataset base
    for clase in MAPA_TARGET:
        assert abs((generados[TARGET] == clase).mean() - (base[TARGET] == clase).mean()) < 0.02
    for col in ["glucosa_mgdl", "fcf_bpm"]:
        assert abs(generados[col].isna().mean() - base[col].isna().mean()) < 0.02


def test_todo_registro_con_signo_critico_sale_alto(generados, modelo_principal):
    criticos = np.asarray(mascara_reglas(generados))
    assert criticos.sum() > 500
    # la etiqueta: ningún registro generado que no sea de Alto Riesgo recibe un signo crítico
    assert (generados.loc[criticos, TARGET] == "Alto Riesgo").all()
    # y el sistema híbrido en uso los clasifica a todos como Alto, diga lo que diga el modelo
    X, _ = separar_xy(generados.drop(columns=COLUMNA_ORIGEN))
    pred, _, activa = predecir_hibrido(modelo_principal, X)
    assert np.array_equal(activa, criticos) and (pred[activa] == CLASE_ALTO).all()


# ------------------------------------------------------------------ depuración
def test_centinelas_pasan_a_nulo():
    limpio, pasos = depurar(crudo(fila(glucosa_mgdl="9999"), fila(id_gestante="X2", fcf_bpm="999", edad="30"),
                                  fila(id_gestante="X3", pas_mmhg="999", edad="31")))
    centinelas = pasos[1]
    assert centinelas["Paso"] == "2. Centinelas" and centinelas["Celdas cambiadas"] == 3
    # glucosa y FCF pueden faltar (se imputan); la presión es obligatoria: esa fila se retira
    assert list(limpio["id_gestante"]) == ["X1", "X2"]
    assert pd.isna(limpio.loc[0, "glucosa_mgdl"]) and pd.isna(limpio.loc[1, "fcf_bpm"])


def test_valores_fuera_de_rango_pasan_a_nulo():
    limpio, pasos = depurar(crudo(fila(edad="99"), fila(id_gestante="X2", glucosa_mgdl="900", edad="30"),
                                  fila(id_gestante="X3", edad="31")))
    assert pasos[3]["Paso"] == "4. Rangos" and pasos[3]["Celdas cambiadas"] == 2
    assert list(limpio["id_gestante"]) == ["X2", "X3"] and pd.isna(limpio.loc[0, "glucosa_mgdl"])
    for col, (lo, hi) in RANGOS_PLAUSIBLES.items():
        assert limpio[col].dropna().between(lo, hi).all()


def test_duplicados_se_dejan_una_sola_vez():
    limpio, pasos = depurar(crudo(fila(), fila(), fila(id_gestante="OTRO"), fila(id_gestante="X2", edad="30")))
    duplicados = pasos[4]
    assert duplicados["Paso"] == "5. Duplicados"
    assert (duplicados["Filas antes"], duplicados["Filas después"]) == (4, 2)  # el identificador no cuenta
    assert list(limpio["edad"]) == [27, 30]


def test_tipos_coma_decimal_booleanos_espacios_y_clase():
    limpio, pasos = depurar(crudo(
        fila(glucosa_mgdl="113,4", convulsiones="TRUE", area_residencia="  Rural disperso ", riesgo_obstetrico="Alto Riesgo"),
        fila(id_gestante="X2", edad="treinta"), fila(id_gestante="X3", edad="31", riesgo_obstetrico="Gravísimo"),
        fila(id_gestante="X4", edad="32", riesgo_obstetrico=None)))
    assert len(limpio) == 1  # edad ilegible, clase desconocida y clase vacía se retiran
    r = limpio.iloc[0]
    assert r["glucosa_mgdl"] == 113.4 and r["convulsiones"] == 1 and r["area_residencia"] == "Rural disperso"
    assert limpio["edad"].dtype.kind == "i" and limpio["convulsiones"].dtype.kind == "i"
    assert pasos[5]["Paso"] == "6. Incompletos" and (pasos[5]["Filas antes"], pasos[5]["Filas después"]) == (4, 1)


def test_estructura_columnas_desconocidas_y_obligatorias():
    con_extra = crudo(fila(telefono="3001234567"))
    con_extra["Unnamed: 16"] = None
    limpio, pasos = depurar(con_extra)
    assert "telefono" not in limpio and "unnamed: 16" not in limpio and "telefono" in pasos[0]["Detalle"]
    with pytest.raises(ValueError, match="pas_mmhg"):
        depurar(crudo(fila()).drop(columns="pas_mmhg"))


def test_el_reporte_encadena_los_conteos_y_la_imputacion_no_rellena():
    sucio, inyectado = ensuciar(generar(4000))
    limpio, pasos = depurar(sucio)
    assert [p["Paso"][0] for p in pasos] == list("1234567")
    assert pasos[0]["Filas antes"] == len(sucio) == 4000 + inyectado["Filas duplicadas"]
    for anterior, siguiente in zip(pasos, pasos[1:]):
        assert anterior["Filas después"] == siguiente["Filas antes"]
    assert pasos[-1]["Filas después"] == len(limpio)
    # lo inyectado se detecta (una fila duplicada puede repetir un error: por eso «al menos»)
    assert pasos[1]["Celdas cambiadas"] >= sum(v for k, v in inyectado.items() if k.startswith("Centinela"))
    assert pasos[3]["Celdas cambiadas"] >= sum(v for k, v in inyectado.items() if k.startswith("Valor imposible"))
    assert pasos[4]["Filas antes"] - pasos[4]["Filas después"] >= inyectado["Filas duplicadas"]
    # glucosa y FCF siguen con nulos: los imputa el pipeline, solo con el entrenamiento
    assert limpio["glucosa_mgdl"].isna().any() and limpio[[c for c in limpio if c not in ("glucosa_mgdl", "fcf_bpm")]].notna().all().all()
    assert not limpio.drop(columns="id_gestante").duplicated().any()
    assert (limpio[COLUMNA_ORIGEN] == ORIGEN).all()


@pytest.mark.parametrize("extension", ["txt", "csv", "xlsx"])
def test_lee_archivos_grandes_por_lotes(tmp_path, extension):
    datos, _ = ensuciar(generar(12000))
    ruta = tmp_path / f"crudo.{extension}"
    if extension == "txt":
        ruta.write_text(a_texto(datos), encoding="utf-8", newline="")
    elif extension == "csv":
        datos.to_csv(ruta, index=False)
    else:
        datos.to_excel(ruta, index=False)
    avances = []
    leido, info = leer_crudo(ruta, lambda leidas, total: avances.append((leidas, total)))
    assert len(leido) == len(datos) == info["filas"] and info["lotes"] == 3  # lotes de 5.000 filas
    assert [a[0] for a in avances] == [5000, 10000, len(datos)]
    if extension != "xlsx":
        assert avances[0][1] == len(datos) and info["separador"] == ("|" if extension == "txt" else ",")
    assert len(depurar(leido)[0]) == len(depurar(datos)[0])


# ------------------------------------------------------------------ conjunto de trabajo y lote de demostración
def test_el_lote_de_demostracion_nunca_entra_al_entrenamiento(carpeta):
    limpio, _ = depurar(generar(3000))
    meta = conjunto_trabajo.establecer(limpio, "Sintético de prueba", "ana", n_lote=300)
    trabajo, lote = conjunto_trabajo.datos(), conjunto_trabajo.lote()
    assert (meta["n_total"], meta["n_trabajo"], meta["n_lote"]) == (len(limpio), len(limpio) - 300, 300)
    assert len(trabajo) == meta["n_trabajo"] and len(lote) == 300
    assert not set(trabajo["id_gestante"]) & set(lote["id_gestante"])
    assert set(trabajo["id_gestante"]) | set(lote["id_gestante"]) == set(limpio["id_gestante"])
    for clase in MAPA_TARGET:  # apartado de forma estratificada
        assert abs((lote[TARGET] == clase).mean() - (limpio[TARGET] == clase).mean()) < 0.01

    # lo que se parte y se entrena es SOLO el conjunto de trabajo: ningún registro del lote aparece
    particiones = experimentos._particiones(trabajo, (70, 15, 15), 42)
    usados = set().union(*(set(trabajo.loc[p.index, "id_gestante"]) for p in particiones[:3]))
    assert usados == set(trabajo["id_gestante"]) and not usados & set(lote["id_gestante"])
    resultado = experimentos.entrenar("Regresión Logística", datos=trabajo, nombre_datos=conjunto_trabajo.descripcion(),
                                      huella_datos=meta["huella"])
    r = resultado["registro"]
    assert r["n_entrenamiento"] + r["n_validacion"] + r["n_prueba"] == meta["n_trabajo"]
    assert r["datos_huella"] == meta["huella"] and "Sintético de prueba" in r["datos"] and not r["identico_al_modelo_en_uso"]

    # el lote se carga aparte y se mide sobre él
    metricas = conjunto_trabajo.evaluar_lote(resultado["modelo"])
    assert metricas["n"] == 300 and 0 < metricas["f1_macro"] <= 1
    # la curva se puede recalcular mientras el conjunto no cambie; después, se explica por qué no
    assert len(experimentos.curva_aprendizaje(r["version"])) == 7
    conjunto_trabajo.establecer(depurar(generar(1500, 9))[0], "Otro", "ana")
    with pytest.raises(ValueError, match="ya no es el conjunto"):
        experimentos.curva_aprendizaje(r["version"])


def test_establecer_y_restablecer(carpeta):
    assert conjunto_trabajo.meta() is None and conjunto_trabajo.datos() is None
    assert conjunto_trabajo.descripcion() == experimentos.DATOS_BASE
    limpio, _ = depurar(generar(1000))
    for n_lote in (-1, 1, len(limpio)):
        with pytest.raises(ValueError):
            conjunto_trabajo.establecer(limpio, "x", "ana", n_lote=n_lote)
    conjunto_trabajo.establecer(limpio, "Sin lote", "ana")
    assert conjunto_trabajo.meta()["n_lote"] == 0 and len(conjunto_trabajo.lote()) == 0
    conjunto_trabajo.restablecer()
    assert conjunto_trabajo.meta() is None


def test_la_svm_se_limita_a_10000_registros():
    X, y = separar_xy(generar(12500).drop(columns=COLUMNA_ORIGEN))
    Xs, ys, nota = experimentos.limitar_svm("SVM", X, y)
    assert len(Xs) == experimentos.MAX_SVM == 10000 and "10000 de 12500" in nota
    assert abs((ys == CLASE_ALTO).mean() - (y == CLASE_ALTO).mean()) < 0.005
    assert experimentos.limitar_svm("Random Forest", X, y) == (X, y, None)
    assert experimentos.limitar_svm("SVM", X.iloc[:9000], y.iloc[:9000])[2] is None


def test_escalabilidad(carpeta):
    etapas = []
    tabla = conjunto_trabajo.medir_escalabilidad((1000, 2000), "Regresión Logística", al_avanzar=lambda n, e: etapas.append((n, e)))
    assert list(tabla["registros"]) == [1000, 2000] and len(etapas) == 8
    assert (tabla[["carga_s", "limpieza_s", "entrenamiento_s", "memoria_mb"]] >= 0).all().all()
    assert tabla["memoria_mb"].is_monotonic_increasing and (tabla["filas_limpias"] <= tabla["filas_crudas"]).all()
    assert conjunto_trabajo.escalabilidad_guardada().equals(tabla)
