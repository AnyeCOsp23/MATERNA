"""Fase 3: georreferenciación (límites del DANE y ubicaciones sintéticas). La ubicación nunca entra al modelo."""
import json

import pandas as pd
import pytest

from src import georreferencia as geo
from src.config import NOMBRES_CLASES, TARGET
from src.data_preprocessing import cargar_dataset
from src.exportar_a_dart import DIR_ASSETS


@pytest.fixture(scope="module")
def datos():
    return cargar_dataset()


@pytest.fixture(scope="module")
def geometrias():
    return geo.geometrias()


def test_limites_del_dane(geometrias):
    deptos = pd.Series([f["properties"]["departamento"] for f in geometrias.values()]).value_counts().to_dict()
    assert deptos == {"Cesar": 25, "La Guajira": 15}
    assert "DANE" in geo.municipios()["fuente"]
    # los 8 municipios del dataset tienen su límite
    assert set(geo.CODIGO_MUNICIPIO.values()) <= set(geometrias)


def test_cabeceras_dentro_de_su_municipio(geometrias):
    cabeceras = geo.cabeceras()
    assert len(cabeceras) == 40
    for c in cabeceras:
        assert geo.contiene(geometrias[c["codigo"]]["geometry"], c["lon"], c["lat"]), c["nombre"]


def test_puntos_sinteticos_rotulados_y_dentro(geometrias):
    puntos = geo.puntos()
    assert len(puntos) > 120 and all(p["sintetico"] and "(sintético)" in p["nombre"] for p in puntos)
    assert {p["tipo"] for p in puntos} <= {"Ranchería", "Vereda", "Resguardo"}
    for p in puntos:
        assert geo.contiene(geometrias[p["codigo_municipio"]]["geometry"], p["lon"], p["lat"]), p["id"]


def test_una_ubicacion_sintetica_por_gestante_dentro_de_su_municipio(datos, geometrias):
    ubic = geo.ubicaciones()
    assert len(ubic) == len(datos) and set(ubic["id_gestante"]) == set(datos["id_gestante"])
    assert ubic["sintetico"].all() and set(ubic["nivel"]) == {"punto"}
    # sin nombres ni documentos: solo el identificador del dataset
    assert set(ubic.columns) == {"id_gestante", "codigo_municipio", "punto", "lon", "lat", "nivel", "sintetico"}
    municipio = datos.set_index("id_gestante")["municipio"]
    for _, u in ubic.iterrows():
        assert u["codigo_municipio"] == geo.CODIGO_MUNICIPIO[municipio[u["id_gestante"]]]
        assert geo.contiene(geometrias[u["codigo_municipio"]]["geometry"], u["lon"], u["lat"]), u["id_gestante"]


def test_reproducible_con_la_semilla(datos):
    puntos, ubic = geo.construir_sinteticos(datos)
    assert puntos == geo.puntos()
    pd.testing.assert_frame_equal(ubic, geo.ubicaciones(), check_dtype=False)
    otros, _ = geo.construir_sinteticos(datos, semilla=7)
    assert otros != puntos


def test_las_cifras_del_mapa_coinciden_con_el_dataset(datos):
    """Prueba pedida: lo que muestra el mapa (por municipio y por punto) es exactamente lo del dataset."""
    m = geo.por_municipio(datos)
    esperado = datos.groupby("municipio")[TARGET].value_counts().unstack(fill_value=0)
    for _, fila in m.iterrows():
        nombre = next(k for k, v in geo.CODIGO_MUNICIPIO.items() if v == fila["codigo"])
        assert fila["gestantes"] == (datos["municipio"] == nombre).sum()
        for c in NOMBRES_CLASES:
            assert fila[c] == esperado.loc[nombre, c]
        assert fila["pct_alto"] == round(100 * esperado.loc[nombre, "Alto Riesgo"] / fila["gestantes"], 1)
    assert m["gestantes"].sum() == len(datos) == 1200 and m["Alto Riesgo"].sum() == 152
    p = geo.por_punto(datos)
    assert p["gestantes"].sum() == 1200 and [p[c].sum() for c in NOMBRES_CLASES] == [578, 470, 152]
    # las de cabecera quedan en el punto de su cabecera
    cab = p[p["tipo"] == "Cabecera municipal"]["gestantes"].sum()
    assert cab == (datos["area_residencia"] == "Cabecera").sum()


def test_la_ubicacion_no_entra_al_modelo():
    entrada = json.loads((DIR_ASSETS / "preproceso.json").read_text(encoding="utf-8"))["variables_entrada"]
    prohibidas = ("lon", "lat", "punto", "codigo_municipio", "municipio", "departamento", "distancia")
    assert not [v for v in entrada if any(p in v for p in prohibidas)]


def test_distancia_en_km():
    rio, vup = (-72.9118, 11.5286), (-73.2594, 10.4605)  # cabeceras de Riohacha y Valledupar
    assert 120 < geo.distancia_km(*rio, *vup) < 130
    assert geo.distancia_km(*rio, *rio) == 0


# ------------------------------------------------------------------ Módulo 1: vista «Mapa territorial»
def test_el_grafico_del_mapa_usa_las_mismas_cifras(datos):
    from src import graficos
    m = geo.por_municipio(datos)
    g = graficos.mapa_coropletico(m)
    serie = g.opciones["series"][0]
    assert g.mapa[0] == "materna-ambos" and json.loads(g.mapa[1])["features"]  # GeoJSON local, sin teselas
    assert {d["name"]: d["value"] for d in serie["data"]} == dict(zip(m["municipio"], m["pct_alto"]))
    assert sum(d["gestantes"] for d in serie["data"]) == 1200
    p = geo.por_punto(datos)
    puntos = graficos.mapa_concentracion(p, ("Alto Riesgo",))
    anillos = [s for s in puntos.opciones["series"] if s["type"] == "pie"]
    assert sum(d["value"] for s in anillos for d in s["data"]) == 152 and "tile" not in json.dumps(puntos.opciones).lower()
    assert all(s["coordinateSystem"] == "geo" for s in anillos)
    cesar = graficos.mapa_coropletico(m[m["departamento"] == "Cesar"], "Cesar")
    assert {f["properties"]["departamento"] for f in json.loads(cesar.mapa[1])["features"]} == {"Cesar"}


def test_mapa_de_municipios_por_porcentaje_del_nivel_elegido(datos):
    """Con un nivel, el color es el % de ese nivel en cada municipio (no la cantidad, que sigue al tamaño del municipio)
    y la escala va del menor al mayor valor real, con el color de ese nivel."""
    from src import graficos
    m = geo.por_municipio(datos)
    g = graficos.mapa_coropletico(m, None, ("Riesgo Medio",))
    serie, escala = g.opciones["series"][0], g.opciones["visualMap"]
    esperado = {f["municipio"]: round(100 * f["Riesgo Medio"] / f["gestantes"], 1) for f in m.to_dict("records")}
    assert {d["name"]: d["value"] for d in serie["data"]} == esperado
    assert escala["min"] <= min(esperado.values()) and escala["max"] >= max(esperado.values()) and escala["min"] > 0
    assert escala["inRange"]["color"] == graficos.ESCALA_NIVEL["Riesgo Medio"]
    # dos niveles: vino; «Cantidad»: cuántas gestantes de esos niveles, desde 0
    dos = graficos.mapa_coropletico(m, None, ("Bajo Riesgo", "Riesgo Medio"), "cantidad")
    assert dos.opciones["visualMap"]["inRange"]["color"] == graficos.ESCALA_VARIOS and dos.opciones["visualMap"]["min"] == 0
    assert sum(d["value"] for d in dos.opciones["series"][0]["data"]) == int(m["Bajo Riesgo"].sum() + m["Riesgo Medio"].sum())


def test_un_anillo_por_lugar_con_la_mezcla_de_riesgo(datos):
    from src import graficos
    p = geo.por_punto(datos)
    g = graficos.mapa_concentracion(p)
    anillos = [s for s in g.opciones["series"] if s["type"] == "pie"]
    assert len(anillos) == len(p)  # uno por lugar (antes eran hasta tres círculos superpuestos)
    assert sum(d["value"] for s in anillos for d in s["data"]) == 1200
    grande = max(anillos, key=lambda s: s["radius"][1])
    fila = p.loc[p["nombre"] == grande["name"]].iloc[0]
    assert {d["name"]: d["value"] for d in grande["data"]} == {c: int(fila[c]) for c in geo.NOMBRES_CLASES if fila[c] > 0}
    assert grande["radius"][0] < grande["radius"][1]  # con hueco: anillo


def vista_mapa():
    from streamlit.testing.v1 import AppTest
    from conftest import RAIZ
    at = AppTest.from_file(str(RAIZ / "paginas" / "laboratorio.py"), default_timeout=180)
    at.session_state["usuario"] = {"usuario": "a", "nombre": "A", "rol": "administrador"}
    at.session_state["vista"] = "mapa"
    return at.run()


def test_vista_mapa_territorial_con_filtros():
    at = vista_mapa()
    assert not at.exception
    assert any("Datos sintéticos" in w.value for w in at.warning)
    municipios, puntos = at.dataframe[0].value, at.dataframe[1].value
    assert municipios["Gestantes"].sum() == 1200 and municipios["Alto"].sum() == 152 and puntos["Gestantes"].sum() == 1200
    at.pills(key="mapa_niveles").set_value(["Alto Riesgo"]).run()
    assert not at.exception
    assert at.dataframe[0].value["De Alto Riesgo"].sum() == 152 and (at.dataframe[1].value["Alto"] > 0).all()
    assert "% de Alto Riesgo" in at.dataframe[0].value.columns
    at.segmented_control(key="mapa_medida").set_value("Cantidad").run()
    assert not at.exception
    at.segmented_control(key="mapa_depto").set_value("La Guajira").run()
    guajira = at.dataframe[0].value
    assert set(guajira["Departamento"]) == {"La Guajira"} and guajira["Gestantes"].sum() == 769


def test_la_app_lleva_los_mismos_archivos_geograficos():
    """flutter_app/assets/geo/ es copia exacta de data/geo/ (si cambian, correr: python -m src.georreferencia app)."""
    for ruta in geo.PARA_LA_APP:
        assert (geo.DIR_GEO_APP / ruta.name).read_bytes() == ruta.read_bytes(), ruta.name
    assert not (geo.DIR_GEO_APP / geo.RUTA_UBICACIONES.name).exists()  # las 1.200 ubicaciones no van a la app
