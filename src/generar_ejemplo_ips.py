"""Fase 3 — Plantilla de captura para la IPS y archivo de ejemplo FICTICIO.

  data/plantillas/plantilla_ips_3280.xlsx   hoja "Datos" vacía + hoja "Diccionario" (qué va en cada columna)
  data/plantillas/plantilla_ips_3280.csv    solo los encabezados
  data/ejemplos/ips_ficticio_3280.csv       300 gestantes del dataset sintético con variables de la 3280,
  data/ejemplos/ips_ficticio_3280.xlsx      separador '|' y latin-1, como los planos de una IPS

El ejemplo NO contiene datos reales: documentos y nombres son inventados. Trae a propósito los
problemas de un archivo real (encabezados con otros nombres, centinelas, valores imposibles,
filas duplicadas, gestantes con varias atenciones y una columna desconocida) para probar la ingesta.

Uso:  python -m src.generar_ejemplo_ips
"""
import numpy as np
import pandas as pd

from src.config import RAIZ, SEMILLA
from src.data_preprocessing import cargar_dataset
from src.filtro_3280 import variables

DIR_PLANTILLAS = RAIZ / "data" / "plantillas"
DIR_EJEMPLOS = RAIZ / "data" / "ejemplos"
N_EJEMPLO = 300

# Encabezados como los escribiría una IPS (el filtro los reconoce por los sinónimos del catálogo)
ENCABEZADOS = {
    "tipo_documento": "Tipo Documento", "numero_documento": "Numero Documento",
    "primer_nombre": "Primer Nombre", "primer_apellido": "Primer Apellido", "telefono": "Telefono",
    "codigo_ips": "Codigo IPS", "consecutivo": "Consecutivo",
    "edad": "Edad", "semanas_gestacion": "Semanas", "n_controles_prenatales": "Controles Prenatales",
    "pas_mmhg": "TAS", "pad_mmhg": "TAD", "fcf_bpm": "Fetocardia", "glucosa_mgdl": "Glicemia",
    "proteinuria": "Proteinuria", "convulsiones": "Convulsiones", "area_residencia": "Zona",
    "atendido_por": "Atiende", "pertenencia_etnica": "Etnia", "departamento": "Departamento",
    "municipio": "Municipio", "fecha_ultima_menstruacion": "FUM", "gestaciones": "Gestaciones",
    "partos": "Partos", "cesareas": "Cesareas", "preeclampsia_previa": "Preeclampsia previa",
    "peso_kg": "Peso", "talla_cm": "Talla", "hemoglobina_gdl": "Hemoglobina", "sifilis_reactiva": "Sifilis",
    "vih_reactivo": "VIH", "calcio": "Calcio", "vacuna_influenza": "Vacuna influenza", "cefalea": "Cefalea",
    "vision_borrosa": "Vision borrosa", "sangrado_genital": "Sangrado genital",
    "disminucion_movimientos_fetales": "Disminucion movimientos fetales",
}
ATIENDE_CON_TILDE = {"Medico": "Médico", "Auxiliar de enfermeria": "Auxiliar de enfermería"}


def generar_plantillas():
    DIR_PLANTILLAS.mkdir(parents=True, exist_ok=True)
    capturables = [v for v in variables() if v["decision"] != "eliminar"]
    pd.DataFrame(columns=[v["nombre"] for v in capturables]).to_csv(DIR_PLANTILLAS / "plantilla_ips_3280.csv", index=False)
    diccionario = pd.DataFrame([{
        "Columna": v["nombre"], "Variable": v["etiqueta"], "Sección 3280": v["seccion"],
        "Tipo": v["tipo"], "Unidad": v.get("unidad", ""),
        "Rango válido": f"{v['rango'][0]} a {v['rango'][1]}" if "rango" in v else "",
        "Valores": ", ".join(v.get("valores", [])) or ("Sí / No" if v["tipo"] == "binaria" else ""),
        "Uso en MATERNA": v["decision"],
    } for v in capturables])
    with pd.ExcelWriter(DIR_PLANTILLAS / "plantilla_ips_3280.xlsx", engine="openpyxl") as libro:
        pd.DataFrame(columns=diccionario["Columna"]).to_excel(libro, sheet_name="Datos", index=False)
        diccionario.to_excel(libro, sheet_name="Diccionario", index=False)


def _si_no(mascara):
    return np.where(mascara, "Si", "No")


def generar_ejemplo(semilla=SEMILLA):
    rng = np.random.default_rng(semilla)
    base = cargar_dataset().sample(N_EJEMPLO, random_state=semilla).reset_index(drop=True)
    n = len(base)
    alto = (base["riesgo_obstetrico"] == "Alto Riesgo").to_numpy()
    rural = (base["area_residencia"] == "Rural disperso").to_numpy()
    semanas = base["semanas_gestacion"].to_numpy()

    df = pd.DataFrame({
        "tipo_documento": rng.choice(["CC", "TI"], n, p=[0.9, 0.1]),
        "numero_documento": [str(x) for x in rng.integers(1_000_000_000, 1_999_999_999, n)],
        "primer_nombre": [f"NOMBRE FICTICIO {i:03d}" for i in range(n)],
        "primer_apellido": [f"APELLIDO FICTICIO {i:03d}" for i in range(n)],
        "telefono": "3000000000",
        "codigo_ips": "000000000000",
        "consecutivo": np.arange(1, n + 1),
    })
    for col in ["edad", "semanas_gestacion", "n_controles_prenatales", "pas_mmhg", "pad_mmhg", "fcf_bpm",
                "glucosa_mgdl", "proteinuria", "pertenencia_etnica", "departamento", "municipio"]:
        df[col] = base[col]
    df["convulsiones"] = _si_no(base["convulsiones"] == 1)
    df["area_residencia"] = np.where(rural & (rng.random(n) < 0.3), "RURAL DISPERSO", base["area_residencia"])
    df["atendido_por"] = base["atendido_por"].replace(ATIENDE_CON_TILDE)

    fum = pd.Timestamp("2026-10-31") - pd.to_timedelta(semanas * 7, unit="D")
    df["fecha_ultima_menstruacion"] = fum.strftime("%Y-%m-%d")
    gestaciones = rng.integers(1, 6, n)
    df["gestaciones"] = gestaciones
    df["partos"] = np.maximum(gestaciones - 1 - rng.integers(0, 2, n), 0)
    df["cesareas"] = np.minimum(df["partos"], rng.binomial(1, 0.25, n))
    df["preeclampsia_previa"] = _si_no((gestaciones > 1) & (rng.random(n) < np.where(alto, 0.25, 0.05)))
    df["peso_kg"] = np.round(rng.normal(62, 10, n).clip(40, 110), 1)
    df["talla_cm"] = np.round(rng.normal(155, 6, n).clip(138, 178), 1)
    df["hemoglobina_gdl"] = np.round(rng.normal(np.where(rural, 11.2, 11.9), 1.1).clip(6, 15.5), 1)
    df["sifilis_reactiva"] = _si_no(rng.random(n) < 0.02)
    df["vih_reactivo"] = _si_no(rng.random(n) < 0.005)
    df["calcio"] = _si_no((semanas >= 14) & (rng.random(n) < np.where(rural, 0.55, 0.8)))
    df["vacuna_influenza"] = _si_no((semanas >= 14) & (rng.random(n) < 0.6))
    for col, p_alto in [("cefalea", 0.3), ("vision_borrosa", 0.2), ("sangrado_genital", 0.05),
                        ("disminucion_movimientos_fetales", 0.1)]:
        df[col] = _si_no(rng.random(n) < np.where(alto, p_alto, 0.02))
    df["observaciones"] = "texto libre que no debe pasar al sistema"

    # Problemas de un archivo real
    df["glucosa_mgdl"] = df["glucosa_mgdl"].astype(object)
    df.loc[[3, 17, 41, 88, 150], "glucosa_mgdl"] = "999"              # centinela
    df.loc[[9, 60], "fecha_ultima_menstruacion"] = "1845-01-01"        # centinela de fecha
    df.loc[[25, 200], "pas_mmhg"] = 400                                # imposible fisiológicamente
    df.loc[[33, 210], "numero_documento"] = ""                         # sin documento
    df.loc[[120], "edad"] = None                                       # obligatoria faltante
    segunda = df.loc[[5, 70, 140]].copy()                              # misma gestante, control posterior
    segunda["semanas_gestacion"] = segunda["semanas_gestacion"] + 4
    segunda["n_controles_prenatales"] = segunda["n_controles_prenatales"] + 1
    duplicadas = df.loc[[11, 99, 180, 250]].copy()                     # filas repetidas al digitar
    df = pd.concat([df, segunda, duplicadas], ignore_index=True)

    return df.rename(columns=ENCABEZADOS)


def main():
    generar_plantillas()
    DIR_EJEMPLOS.mkdir(parents=True, exist_ok=True)
    ejemplo = generar_ejemplo()
    ejemplo.to_csv(DIR_EJEMPLOS / "ips_ficticio_3280.csv", sep="|", index=False, encoding="latin-1")
    ejemplo.to_excel(DIR_EJEMPLOS / "ips_ficticio_3280.xlsx", index=False, engine="openpyxl")
    print(f"Plantillas en {DIR_PLANTILLAS}")
    print(f"Ejemplo ficticio: {len(ejemplo)} filas, {ejemplo.shape[1]} columnas en {DIR_EJEMPLOS}")


if __name__ == "__main__":
    main()
