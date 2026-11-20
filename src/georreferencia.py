"""Fase 3 — Georreferenciación: municipios del DANE, puntos de concentración y ubicaciones SINTÉTICAS.

Para qué: el docente pidió un mapa que ayude a encontrar a las gestantes en territorio (rancherías, veredas y
resguardos dispersos). Esto NO cambia el modelo: la ubicación nunca es una variable de entrada.

Archivos (data/geo/):
- municipios_guajira_cesar.geojson  Límites REALES de los 40 municipios de La Guajira y el Cesar (DANE, MGN 2024).
- cabeceras_guajira_cesar.json      Punto de cada cabecera municipal (centro del polígono del DANE). Sirve solo
                                    como referencia de distancia («distancia aproximada a la cabecera»).
- puntos_concentracion.json         Puntos SINTÉTICOS (ranchería, vereda o resguardo) con nombres genéricos. No se
                                    usan lugares reales: asignarles gestantes y riesgos inventados podría
                                    estigmatizar a comunidades reales.
- ubicaciones_sinteticas.csv        Una ubicación SINTÉTICA por gestante del dataset (id_gestante, municipio,
                                    punto, longitud, latitud), siempre dentro de su municipio. Semilla fija.

Regenerar (solo si cambian las descargas del DANE; con la misma semilla sale idéntico):
    python -m src.georreferencia construir RUTA_MUNICIPIOS.geojson RUTA_CABECERAS.geojson
Volver a generar solo lo sintético a partir de lo que ya está en data/geo/:
    python -m src.georreferencia sinteticos
"""
import argparse
import json
import math

import numpy as np
import pandas as pd

from src.config import NOMBRES_CLASES, RAIZ, SEMILLA, TARGET

DIR_GEO = RAIZ / "data" / "geo"
RUTA_MUNICIPIOS = DIR_GEO / "municipios_guajira_cesar.geojson"
RUTA_CABECERAS = DIR_GEO / "cabeceras_guajira_cesar.json"
RUTA_PUNTOS = DIR_GEO / "puntos_concentracion.json"
RUTA_UBICACIONES = DIR_GEO / "ubicaciones_sinteticas.csv"
ETIQUETA_SINTETICO = "sintético"
FUENTE_LIMITES = "DANE, Marco Geoestadístico Nacional (MGN) 2024, servicio Divipola · capas Municipio y Centros Poblados"

# Nombres del dataset -> código DIVIPOLA del municipio (el dataset no trae códigos)
CODIGO_MUNICIPIO = {
    "Uribia": "44847", "Riohacha": "44001", "Manaure": "44560", "Maicao": "44430",
    "Valledupar": "20001", "Codazzi": "20013", "La Paz": "20621", "Becerril": "20045",
}
# Tipo de punto de concentración más común en cada departamento (los resguardos se reparten en ambos)
TIPOS = {"La Guajira": ["Ranchería", "Ranchería", "Resguardo"], "Cesar": ["Vereda", "Vereda", "Resguardo"]}
# Radio (en grados, ~2 km) alrededor del punto en que se ubica una gestante sintética
DISPERSION = 0.02


# ------------------------------------------------------------------ geometría (sin librerías externas)
def _poligonos(geometria):
    """Lista de polígonos; cada uno es una lista de anillos [(lon, lat), ...] (el primero, el exterior)."""
    if geometria["type"] == "Polygon":
        return [geometria["coordinates"]]
    return list(geometria["coordinates"])


def _en_anillo(lon, lat, anillo):
    """Prueba del rayo: True si el punto está dentro del anillo."""
    dentro = False
    j = len(anillo) - 1
    for i in range(len(anillo)):
        xi, yi = anillo[i][:2]
        xj, yj = anillo[j][:2]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            dentro = not dentro
        j = i
    return dentro


def contiene(geometria, lon, lat):
    """True si el punto está dentro del polígono o multipolígono (respetando los huecos)."""
    for anillos in _poligonos(geometria):
        if _en_anillo(lon, lat, anillos[0]) and not any(_en_anillo(lon, lat, h) for h in anillos[1:]):
            return True
    return False


def _area_y_centro(anillo):
    """Área (con signo) y centroide de un anillo, en grados."""
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(anillo, anillo[1:] + anillo[:1]):
        cruz = x0 * y1 - x1 * y0
        a += cruz
        cx += (x0 + x1) * cruz
        cy += (y0 + y1) * cruz
    a /= 2
    return a, (cx / (6 * a), cy / (6 * a)) if a else tuple(np.mean(anillo, axis=0))


def centro(geometria):
    """Centroide del polígono más grande (para una cabecera urbana es un buen punto de referencia)."""
    mayor = max((_area_y_centro([tuple(p[:2]) for p in anillos[0]]) for anillos in _poligonos(geometria)),
                key=lambda ac: abs(ac[0]))
    return mayor[1]


def caja(geometria):
    puntos = [p for anillos in _poligonos(geometria) for anillo in anillos for p in anillo]
    xs, ys = [p[0] for p in puntos], [p[1] for p in puntos]
    return min(xs), min(ys), max(xs), max(ys)


def distancia_km(lon1, lat1, lon2, lat2):
    """Distancia en línea recta (haversine), en km. Es solo información de apoyo: no entra al modelo."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def punto_al_azar(geometria, rng, cerca_de=None, radio=None, intentos=500):
    """Un punto dentro del municipio: al azar en todo el polígono o cerca de otro punto."""
    x0, y0, x1, y1 = caja(geometria)
    for _ in range(intentos):
        if cerca_de is None:
            lon, lat = rng.uniform(x0, x1), rng.uniform(y0, y1)
        else:
            ang, r = rng.uniform(0, 2 * math.pi), radio * math.sqrt(rng.uniform())
            lon, lat = cerca_de[0] + r * math.cos(ang), cerca_de[1] + r * math.sin(ang)
        if contiene(geometria, lon, lat):
            return round(lon, 5), round(lat, 5)
    return round(cerca_de[0], 5), round(cerca_de[1], 5)  # caso extremo: el propio punto de referencia


# ------------------------------------------------------------------ lectura
def municipios():
    """GeoJSON de los 40 municipios (propiedades: codigo, municipio, departamento, area_km2)."""
    return json.loads(RUTA_MUNICIPIOS.read_text(encoding="utf-8"))


def geometrias():
    return {f["properties"]["codigo"]: f for f in municipios()["features"]}


def cabeceras():
    return json.loads(RUTA_CABECERAS.read_text(encoding="utf-8"))["cabeceras"]


def puntos():
    return json.loads(RUTA_PUNTOS.read_text(encoding="utf-8"))["puntos"]


def ubicaciones():
    return pd.read_csv(RUTA_UBICACIONES, dtype={"codigo_municipio": str})


# ------------------------------------------------------------------ construcción
def _titulo(texto):
    pequeñas = {"de", "del", "la", "las", "los", "el", "y"}
    return " ".join(p if i and p in pequeñas else p.capitalize() for i, p in enumerate(texto.lower().split()))


def preparar_dane(ruta_municipios, ruta_cabeceras):
    """Deja en data/geo/ los límites y las cabeceras del DANE con propiedades simples y su fuente."""
    DIR_GEO.mkdir(parents=True, exist_ok=True)
    crudo = json.loads(open(ruta_municipios, encoding="utf-8").read())
    features = [{"type": "Feature", "geometry": f["geometry"], "properties": {
        "codigo": f["properties"]["MPIO_CDPMP"], "municipio": _titulo(f["properties"]["MPIO_CNMBRE"]),
        "departamento": _titulo(f["properties"]["DPTO_CNMBRE"]), "area_km2": round(f["properties"]["MPIO_NAREA"]),
    }} for f in sorted(crudo["features"], key=lambda f: f["properties"]["MPIO_CDPMP"])]
    geo = {"type": "FeatureCollection", "fuente": FUENTE_LIMITES, "features": features}
    RUTA_MUNICIPIOS.write_text(json.dumps(geo, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    cab = json.loads(open(ruta_cabeceras, encoding="utf-8").read())
    lista = []
    for f in sorted(cab["features"], key=lambda f: f["properties"]["MPIO_CDPMP"]):
        lon, lat = centro(f["geometry"])
        lista.append({"codigo": f["properties"]["MPIO_CDPMP"], "nombre": _titulo(f["properties"]["ZU_CNMBRE"].split(",")[0]),
                      "lon": round(lon, 5), "lat": round(lat, 5)})
    RUTA_CABECERAS.write_text(json.dumps({"fuente": FUENTE_LIMITES + " (centro de la cabecera, clase 1)",
                                          "cabeceras": lista}, ensure_ascii=False, indent=1), encoding="utf-8")


def construir_sinteticos(datos, semilla=SEMILLA):
    """Puntos de concentración (3 a 6 por municipio) y una ubicación por gestante, todo sintético y reproducible."""
    rng = np.random.default_rng(semilla)
    geos = geometrias()
    lista = []
    for codigo, f in sorted(geos.items()):
        depto, nombre = f["properties"]["departamento"], f["properties"]["municipio"]
        prefijo = "".join(ch for ch in nombre.upper() if ch.isalpha())[:3]
        for k in range(int(rng.integers(3, 7))):
            tipo = TIPOS[depto][int(rng.integers(0, len(TIPOS[depto])))]
            lon, lat = punto_al_azar(f["geometry"], rng)
            lista.append({"id": f"{codigo}-{k + 1:02d}", "codigo_municipio": codigo, "municipio": nombre,
                          "departamento": depto, "tipo": tipo, "nombre": f"{tipo} {prefijo}-{k + 1:02d} ({ETIQUETA_SINTETICO})",
                          "lon": lon, "lat": lat, "sintetico": True})
    cab = {c["codigo"]: c for c in cabeceras()}
    por_municipio = {}
    for p in lista:
        por_municipio.setdefault(p["codigo_municipio"], []).append(p)
    filas = []
    for _, g in datos.sort_values("id_gestante").iterrows():
        codigo = CODIGO_MUNICIPIO[g["municipio"]]
        geometria = geos[codigo]["geometry"]
        if g["area_residencia"] == "Cabecera":   # vive en el casco urbano: cerca de la cabecera
            ref, punto = (cab[codigo]["lon"], cab[codigo]["lat"]), f"{codigo}-CAB"
            radio = DISPERSION / 4
        else:                                     # rural disperso: alrededor de un punto de concentración
            elegido = por_municipio[codigo][int(rng.integers(0, len(por_municipio[codigo])))]
            ref, punto, radio = (elegido["lon"], elegido["lat"]), elegido["id"], DISPERSION
        lon, lat = punto_al_azar(geometria, rng, cerca_de=ref, radio=radio)
        filas.append({"id_gestante": g["id_gestante"], "codigo_municipio": codigo, "punto": punto,
                      "lon": lon, "lat": lat, "nivel": "punto", "sintetico": True})
    return lista, pd.DataFrame(filas)


def guardar_sinteticos(datos, semilla=SEMILLA):
    lista, ubic = construir_sinteticos(datos, semilla)
    RUTA_PUNTOS.write_text(json.dumps({"aviso": "Puntos SINTÉTICOS con nombres genéricos: no son lugares reales.",
                                       "semilla": semilla, "puntos": lista}, ensure_ascii=False, indent=1), encoding="utf-8")
    ubic.to_csv(RUTA_UBICACIONES, index=False)
    return lista, ubic


# ------------------------------------------------------------------ resúmenes para los mapas
def _con_ubicacion(datos, ubic=None):
    """Une cada gestante con su ubicación sintética (por id_gestante). Las que no tengan, quedan sin punto."""
    ubic = ubicaciones() if ubic is None else ubic
    juntos = datos.merge(ubic, on="id_gestante", how="left")
    faltan = juntos["codigo_municipio"].isna()
    juntos.loc[faltan, "codigo_municipio"] = juntos.loc[faltan, "municipio"].map(CODIGO_MUNICIPIO)
    return juntos


def _conteos(grupo):
    n = len(grupo)
    por_clase = grupo[TARGET].value_counts().reindex(NOMBRES_CLASES, fill_value=0)
    return {"gestantes": n, **{c: int(por_clase[c]) for c in NOMBRES_CLASES},
            "pct_alto": round(100 * por_clase["Alto Riesgo"] / n, 1) if n else 0.0,
            "predominante": por_clase.idxmax() if n else None}


def por_municipio(datos, ubic=None):
    """Una fila por municipio con gestantes: conteos por clase y % de Alto Riesgo."""
    juntos = _con_ubicacion(datos, ubic)
    props = {f["properties"]["codigo"]: f["properties"] for f in municipios()["features"]}
    filas = [{"codigo": c, "municipio": props[c]["municipio"], "departamento": props[c]["departamento"], **_conteos(g)}
             for c, g in juntos.groupby("codigo_municipio")]
    return pd.DataFrame(filas).sort_values(["departamento", "gestantes"], ascending=[True, False], ignore_index=True)


def por_punto(datos, ubic=None):
    """Una fila por punto de concentración (o cabecera) con su posición, conteos y nivel predominante."""
    juntos = _con_ubicacion(datos, ubic).dropna(subset=["punto"])
    info = {p["id"]: p for p in puntos()}
    for c in cabeceras():
        info[f"{c['codigo']}-CAB"] = {"nombre": f"Cabecera de {c['nombre']}", "tipo": "Cabecera municipal",
                                     "lon": c["lon"], "lat": c["lat"]}
    props = {f["properties"]["codigo"]: f["properties"] for f in municipios()["features"]}
    filas = [{"punto": p, "nombre": info[p]["nombre"], "tipo": info[p]["tipo"],
              "municipio": props[g["codigo_municipio"].iloc[0]]["municipio"],
              "departamento": props[g["codigo_municipio"].iloc[0]]["departamento"],
              "lon": info[p]["lon"], "lat": info[p]["lat"], **_conteos(g)} for p, g in juntos.groupby("punto")]
    return pd.DataFrame(filas).sort_values("gestantes", ascending=False, ignore_index=True)


def main():
    parser = argparse.ArgumentParser(description="Georreferenciación de MATERNA (datos geográficos locales)")
    sub = parser.add_subparsers(dest="accion", required=True)
    c = sub.add_parser("construir", help="prepara los límites del DANE y genera lo sintético")
    c.add_argument("municipios")
    c.add_argument("cabeceras")
    sub.add_parser("sinteticos", help="vuelve a generar solo los puntos y ubicaciones sintéticos")
    args = parser.parse_args()
    from src.data_preprocessing import cargar_dataset
    if args.accion == "construir":
        preparar_dane(args.municipios, args.cabeceras)
    lista, ubic = guardar_sinteticos(cargar_dataset())
    print(f"{len(geometrias())} municipios · {len(cabeceras())} cabeceras · {len(lista)} puntos sintéticos · "
          f"{len(ubic)} ubicaciones sintéticas en {DIR_GEO}")


if __name__ == "__main__":
    main()
