"""Fase 3, etapa 6: nuevo patrón manual (10.000 -> 10.001), validación, bitácora y reentrenamiento."""
import hashlib

import pytest

from src import experimentos, interpretacion, patrones
from src.config import DIR_MODELOS
from src.data_preprocessing import cargar_dataset
from src.generador_sintetico import generar

REGISTRO = dict(edad=31, semanas_gestacion=30, n_controles_prenatales=2, pas_mmhg=150, pad_mmhg=96, fcf_bpm=None,
                glucosa_mgdl=130.5, proteinuria=1, convulsiones=0, area_residencia="Rural disperso",
                atendido_por="Partera tradicional")
RUTA_EN_USO = DIR_MODELOS / "modelo_random_forest.joblib"


@pytest.fixture(scope="module")
def base():
    return cargar_dataset()


@pytest.fixture
def carpeta(tmp_path, monkeypatch):
    monkeypatch.setenv(experimentos.VARIABLE_DIRECTORIO, str(tmp_path / "experimentos"))
    return tmp_path / "experimentos"


def test_el_contador_pasa_de_10000_a_10001_y_queda_el_evento(carpeta):
    datos = generar(10000)
    evento = patrones.agregar(REGISTRO, "Riesgo Medio", "ana", datos)
    assert (evento["contador_antes"], evento["contador_despues"]) == (10000, 10001)
    assert evento["id"] == "NP0001" and evento["usuario"] == "ana" and evento["valores"] == REGISTRO
    assert evento["clase"] == "Riesgo Medio" and evento["etiqueta_origen"] == "asignada_usuario" and evento["fecha"]
    assert patrones.eventos() == [evento]
    (fila,) = patrones.vigentes().to_dict("records")
    assert fila["id_gestante"] == "NP0001" and fila["origen"] == "patron_manual" and fila["riesgo_obstetrico"] == "Riesgo Medio"
    assert fila["pas_mmhg"] == 150 and fila["glucosa_mgdl"] == 130.5
    # el siguiente cuenta desde 10.001; los datos originales no se tocan
    otro = patrones.agregar({**REGISTRO, "edad": 22}, "Bajo Riesgo", "luis", datos)
    assert (otro["id"], otro["contador_antes"], otro["contador_despues"]) == ("NP0002", 10001, 10002)
    assert len(datos) == 10000 and len(patrones.tabla_eventos()) == 2


@pytest.mark.parametrize("cambio, motivo", [
    ({"edad": 99}, "Edad materna: 99 años está fuera del rango del catálogo 3280 (10 a 55)"),
    ({"pas_mmhg": 300}, "fuera del rango del catálogo 3280 (60 a 250)"),
    ({"glucosa_mgdl": 5}, "fuera del rango del catálogo 3280 (30 a 600)"),
    ({"proteinuria": 7}, "fuera del rango del catálogo 3280 (0 a 4)"),
    ({"pad_mmhg": None}, "Presión arterial diastólica: es obligatoria"),
    ({"edad": 30.5}, "Edad materna: debe ser un número entero"),
    ({"area_residencia": "Luna"}, "«Luna» no es un valor del catálogo"),
    ({"convulsiones": 3}, "Convulsiones: debe ser Sí o No"),
])
def test_rechaza_valores_fuera_del_catalogo_3280_y_explica_por_que(carpeta, base, cambio, motivo):
    with pytest.raises(ValueError) as error:
        patrones.agregar({**REGISTRO, **cambio}, "Alto Riesgo", "ana", base)
    assert motivo in str(error.value)
    assert patrones.vigentes().empty and not patrones.eventos()  # un rechazo no deja rastro en los datos


def test_los_rangos_son_los_del_catalogo_y_glucosa_y_fcf_son_opcionales(carpeta, base):
    assert patrones.validar(REGISTRO) == []
    assert patrones.validar({**REGISTRO, "glucosa_mgdl": None, "fcf_bpm": None}) == []
    for v in patrones.catalogo_modelo():
        if "rango" in v:  # los extremos del catálogo se aceptan; un paso más allá, no
            lo, hi = v["rango"]
            assert patrones.validar({**REGISTRO, v["nombre"]: lo}) == [] and patrones.validar({**REGISTRO, v["nombre"]: hi}) == []
            assert patrones.validar({**REGISTRO, v["nombre"]: hi + 1}) and patrones.validar({**REGISTRO, v["nombre"]: lo - 1})
    # varios errores a la vez se explican todos
    assert len(patrones.validar({**REGISTRO, "edad": 99, "pas_mmhg": None, "atendido_por": "Nadie"})) == 3


def test_rechaza_duplicados(carpeta, base):
    existente = {k: (None if v != v else v) for k, v in base.iloc[0][list(REGISTRO)].items()}
    with pytest.raises(ValueError, match="Duplicado: ya hay un registro con estos mismos valores en el conjunto de datos \\(G0001"):
        patrones.agregar(existente, "Alto Riesgo", "ana", base)
    patrones.agregar(REGISTRO, "Alto Riesgo", "ana", base)
    with pytest.raises(ValueError, match="Duplicado: .* en los patrones nuevos \\(NP0001, clasificado como Alto Riesgo\\)"):
        patrones.agregar(REGISTRO, "Bajo Riesgo", "luis", base)  # aunque cambie la clase
    assert len(patrones.vigentes()) == 1 and len(patrones.eventos()) == 1


def test_clase_asignada_o_proxy_por_reglas(carpeta, base):
    with pytest.raises(ValueError, match="La clase debe ser una de"):
        patrones.agregar(REGISTRO, "Gravísimo", "ana", base)
    with pytest.raises(ValueError, match="La clase debe ser una de"):
        patrones.agregar(REGISTRO, None, "ana", base)
    # proxy: la clase la calcula el sistema en uso; con un signo crítico siempre es Alto
    evento = patrones.agregar({**REGISTRO, "pas_mmhg": 170}, None, "ana", base, patrones.PROXY)
    assert evento["clase"] == "Alto Riesgo" and evento["etiqueta_origen"] == "proxy_reglas"
    sano = dict(REGISTRO, edad=27, semanas_gestacion=28, n_controles_prenatales=5, pas_mmhg=110, pad_mmhg=70, fcf_bpm=142.0,
                glucosa_mgdl=88.5, proteinuria=0, area_residencia="Cabecera", atendido_por="Medico")
    assert patrones.agregar(sano, None, "ana", base, patrones.PROXY)["clase"] == patrones.clase_proxy(sano) == "Bajo Riesgo"
    assert list(patrones.vigentes()["etiqueta_origen"]) == ["proxy_reglas", "proxy_reglas"]


def test_reentrenar_suma_los_patrones_solo_al_entrenamiento(carpeta, base):
    huella = hashlib.sha256(RUTA_EN_USO.read_bytes()).hexdigest()
    antes = experimentos.entrenar("Regresión Logística")["registro"]
    patrones.agregar(REGISTRO, "Alto Riesgo", "ana", base)
    patrones.agregar({**REGISTRO, "edad": 19}, "Riesgo Medio", "ana", base)
    despues = experimentos.entrenar("Regresión Logística", patrones=patrones.vigentes())["registro"]
    assert (antes["patrones"], despues["patrones"]) == ([], ["NP0001", "NP0002"])
    assert (antes["n_entrenamiento"], despues["n_entrenamiento"]) == (840, 842)
    assert (despues["n_validacion"], despues["n_prueba"]) == (antes["n_validacion"], antes["n_prueba"]) == (180, 180)
    # validación y prueba son exactamente las mismas gestantes: el antes y el después son comparables
    _, c_antes = experimentos.conjuntos_de(antes["version"])
    _, c_despues = experimentos.conjuntos_de(despues["version"])
    for conjunto in ("Validación", "Prueba"):
        assert list(c_antes[conjunto][0].index) == list(c_despues[conjunto][0].index)
    assert list(c_despues["Entrenamiento"][0].index[-2:]) == ["NP0001", "NP0002"]
    assert list(c_despues["Entrenamiento"][0].index[:-2]) == list(c_antes["Entrenamiento"][0].index)
    assert list(c_despues["Entrenamiento"][1].iloc[-2:]) == [2, 1]
    assert "NP0001" not in c_antes["Entrenamiento"][0].index
    # el modelo en uso no cambió y la tabla del registro cuenta los patrones
    assert hashlib.sha256(RUTA_EN_USO.read_bytes()).hexdigest() == huella
    assert list(experimentos.tabla_registro()["n_patrones"]) == [0, 2]


def test_los_registros_nuevos_se_miden_como_patrones_no_usados(carpeta, base):
    patrones.agregar(REGISTRO, "Alto Riesgo", "ana", base)
    en_uso = interpretacion.evaluar_sistema()
    nuevos = en_uso["conjuntos"][interpretacion.NUEVOS]
    assert nuevos["metricas"]["n"] == 1 and "ic_recall_alto" not in nuevos
    assert interpretacion.tabla_comparativa(en_uso["conjuntos"])[-1]["¿Lo usó el modelo?"].startswith("No usado: se agregó a mano")
    assert "1 registro(s) nuevo(s) agregados a mano" in interpretacion.frase_comparacion(en_uso["conjuntos"])
    # una versión que SÍ entrenó con él no lo cuenta como no usado; uno agregado después, sí
    version = experimentos.entrenar("Regresión Logística", patrones=patrones.vigentes())["registro"]["version"]
    assert interpretacion.NUEVOS not in interpretacion.evaluar_sistema(version)["conjuntos"]
    patrones.agregar({**REGISTRO, "edad": 40}, "Riesgo Medio", "ana", base)
    assert interpretacion.evaluar_sistema(version)["conjuntos"][interpretacion.NUEVOS]["metricas"]["n"] == 1
    # con un solo registro sin Alto, las frases no inventan un recall
    paneles = interpretacion.paneles(interpretacion.evaluar_sistema(version)["conjuntos"][interpretacion.NUEVOS])
    assert "no hay gestantes de Alto Riesgo" in paneles[2]["frase"]


def test_retirar_un_patron_queda_en_la_bitacora_y_no_reusa_el_identificador(carpeta, base):
    patrones.agregar(REGISTRO, "Alto Riesgo", "ana", base)
    version = experimentos.entrenar("Regresión Logística", patrones=patrones.vigentes())["registro"]["version"]
    evento = patrones.retirar("NP0001", "luis", len(base))
    assert (evento["accion"], evento["usuario"], evento["contador_antes"], evento["contador_despues"]) == ("retirado", "luis", 1201, 1200)
    assert patrones.vigentes().empty and [e["accion"] for e in patrones.eventos()] == ["agregado", "retirado"]
    with pytest.raises(ValueError):
        patrones.retirar("NP0001", "luis", len(base))
    assert patrones.agregar(REGISTRO, "Alto Riesgo", "ana", base)["id"] == "NP0002"  # ya no es duplicado; identificador nuevo
    with pytest.raises(ValueError, match="patrones nuevos que ya fueron retirados"):
        experimentos.conjuntos_de(version)
