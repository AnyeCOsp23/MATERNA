"""Fase 3 — Carga masiva de un archivo de la IPS: la referencia en Python de la pestaña «Carga IPS» del Módulo 2.

Lee el archivo con la plantilla de la Resolución 3280 (src/inspeccionar_ips.py: centinelas, filtro 3280 y
seudonimización HMAC-SHA256), evalúa cada registro apto con el sistema híbrido (evaluar_riesgo_hibrido: reglas
críticas, signos de alarma de la ruta y modelo) y ordena el triaje por urgencia: rojo > ámbar > verde y, dentro
de cada color, de mayor a menor probabilidad de Alto Riesgo según el modelo. Las filas a las que les falta una
variable obligatoria no se evalúan y se informan.

src/exportar_a_dart.py guarda lo que calcula este módulo para el ejemplo ficticio en casos_carga.json, y la
prueba de Dart (flutter_app/test/carga_test.dart) exige que la app dé lo mismo, fila por fila.

Uso:  set MATERNA_SAL=<sal secreta>
      python -m src.carga_masiva data/ejemplos/ips_ficticio_3280.csv
"""
import argparse

import joblib
import pandas as pd

from src.clinical_rules import evaluar_riesgo_hibrido_lote
from src.config import CLASE_ALTO, DIR_MODELOS, NOMBRES_CLASES, VARS_CON_NULOS
from src.filtro_3280 import evaluar_alertas_3280, variables, variables_modelo
from src.inspeccionar_ips import COLUMNA_FILA, inspeccionar
from src.seudonimizacion import COLUMNA_SEUDONIMO, obtener_sal


def obligatorias():
    """Variables del modelo sin las que no se puede evaluar (glucosa y FCF se imputan si faltan)."""
    return [c for c in variables_modelo() if c not in VARS_CON_NULOS]


def _registro(fila):
    """Fila de la ingesta -> registro para el sistema híbrido (sin fila, seudónimo ni fechas)."""
    fechas = {v["nombre"] for v in variables() if v["tipo"] == "fecha"}
    registro = {k: (None if pd.isna(v) else v) for k, v in fila.items()
                if k not in (COLUMNA_FILA, COLUMNA_SEUDONIMO) and k not in fechas}
    for c in VARS_CON_NULOS:
        registro.setdefault(c, None)
    if registro.get("convulsiones") is not None:
        registro["convulsiones"] = int(registro["convulsiones"])
    return registro


def evaluar_archivo(ruta, sal, pipeline):
    """Devuelve (reporte de la ingesta, resultados ordenados por urgencia, filas rechazadas)."""
    datos, reporte = inspeccionar(ruta, sal, con_fila=True)
    aptas, rechazadas = [], []
    for fila in datos.to_dict("records"):
        registro = _registro(fila)
        faltan = [c for c in obligatorias() if registro.get(c) is None]
        if faltan:
            rechazadas.append({"fila": int(fila[COLUMNA_FILA]), "faltan": faltan})
        else:
            aptas.append((fila, registro))
    evaluaciones = evaluar_riesgo_hibrido_lote([r for _, r in aptas], pipeline)
    resultados = []
    for (fila, registro), res in zip(aptas, evaluaciones):
        seudonimo = fila.get(COLUMNA_SEUDONIMO)
        seudonimo = None if seudonimo is None or pd.isna(seudonimo) else seudonimo
        resultados.append({
            "fila": int(fila[COLUMNA_FILA]),
            "id_seudonimo": seudonimo,
            "clase": res.clase,
            "clase_modelo": NOMBRES_CLASES.index(res.categoria_modelo),
            "origen": res.origen,
            "probabilidades": [res.probabilidades_modelo[c] for c in NOMBRES_CLASES],
            "n_signos_criticos": len(res.alertas),
            "signos_alarma": res.signos_alarma,
            "alertas": [a["variable"] for a in evaluar_alertas_3280(registro)],
        })
    resultados.sort(key=lambda r: (-r["clase"], -r["probabilidades"][CLASE_ALTO], r["fila"]))
    return reporte, resultados, rechazadas


def main():
    parser = argparse.ArgumentParser(description="Evalúa todas las gestantes de un archivo de la IPS.")
    parser.add_argument("archivo")
    args = parser.parse_args()
    pipeline = joblib.load(DIR_MODELOS / "modelo_random_forest.joblib")
    reporte, resultados, rechazadas = evaluar_archivo(args.archivo, obtener_sal(), pipeline)
    print(reporte.a_texto())
    conteo = pd.Series([NOMBRES_CLASES[r["clase"]] for r in resultados]).value_counts()
    print(f"\nEvaluadas: {len(resultados)} ({conteo.to_dict()}); sin evaluar por faltantes: {len(rechazadas)}")
    for r in resultados[:10]:
        print(f"  fila {r['fila']:>4}  {NOMBRES_CLASES[r['clase']]:13s} {r['origen']:18s} "
              f"{(r['id_seudonimo'] or 'sin documento')[:12]}")


if __name__ == "__main__":
    main()
