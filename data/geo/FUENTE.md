# Datos geográficos de MATERNA (`data/geo/`)

Funcionan sin internet: los mapas dibujan solo estos límites y puntos, sin mapa de fondo ni teselas externas.
La ubicación **no es una variable del modelo**: solo sirve para ubicar y priorizar visitas.

| Archivo | Qué es | Origen |
|---|---|---|
| `municipios_guajira_cesar.geojson` | Límites de los 40 municipios de La Guajira (15) y el Cesar (25) | **Real.** DANE, Marco Geoestadístico Nacional 2024, capa *Municipio* (simplificada en el servidor con `maxAllowableOffset=0.003`) |
| `cabeceras_guajira_cesar.json` | Un punto por cabecera municipal (centro de su polígono) | **Real.** DANE, MGN 2024, capa *Centros Poblados* (clase 1, código terminado en `000`) |
| `puntos_concentracion.json` | 183 puntos (ranchería, vereda o resguardo) con nombres genéricos, p. ej. «Ranchería URI-03 (sintético)» | **Sintético.** Semilla 42, dentro de cada municipio. No son lugares reales: asignarles gestantes y riesgos inventados podría estigmatizar a comunidades reales |
| `ubicaciones_sinteticas.csv` | Una ubicación por gestante del dataset (`id_gestante`, municipio, punto, lon, lat) | **Sintético.** Semilla 42: las de cabecera, cerca de su cabecera; las rurales, alrededor de un punto de su municipio |

Servicio consultado (19-20/11/2026): `https://geoportal.dane.gov.co/mparcgis/rest/services/Divipola/Serv_DIVIPOLA_MGN_2024/FeatureServer`
(capas 317 *Municipio* y 305 *Centros Poblados*, filtros `DPTO_CCDGO IN ('44','20')`, `outSR=4326`, `f=geojson`).

Regenerar: `python -m src.georreferencia construir MUNICIPIOS.geojson CABECERAS.geojson` (con las descargas del DANE)
o solo lo sintético: `python -m src.georreferencia sinteticos`. Con la misma semilla el resultado es idéntico.
