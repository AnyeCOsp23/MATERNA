"""Fase 3 — Gráficos de la consola web (Altair), con la paleta de MATERNA.

Colores validados para daltonismo con el validador de paletas (adyacentes y todos los pares):
- clases de riesgo: Bajo #2F9C8A, Medio #E0A33A, Alto #9B2D5C. El ámbar tiene poco contraste
  sobre fondo claro: por eso cada gráfico lleva leyenda, tooltip y una tabla al lado.
- dos series (entrenamiento / validación, sintético / IPS): ciruela #7D2F5F y rosa #D8639B.
"""
import altair as alt
import pandas as pd

from src.config import NOMBRES_CLASES

COLOR_CLASE = dict(zip(NOMBRES_CLASES, ["#2F9C8A", "#E0A33A", "#9B2D5C"]))
SERIE_1, SERIE_2 = "#7D2F5F", "#D8639B"
TINTA, TINTA_SUAVE, REJILLA = "#3A1F30", "#76606D", "#E6D6DF"


def _tema(grafico, alto=320):
    return (grafico.properties(height=alto)
            .configure(background="transparent", font="system-ui")
            .configure_axis(labelColor=TINTA_SUAVE, titleColor=TINTA, gridColor=REJILLA, domainColor=REJILLA,
                            tickColor=REJILLA, labelFontSize=12, titleFontSize=12, titleFontWeight="normal")
            .configure_legend(labelColor=TINTA, titleColor=TINTA, orient="top", labelFontSize=12, symbolType="circle", symbolOpacity=1)
            .configure_view(stroke=None))


def escala_clases():
    return alt.Scale(domain=list(COLOR_CLASE), range=list(COLOR_CLASE.values()))


def dispersion_presion(df):
    """PAS vs PAD por clase, con los umbrales de hipertensión (140/90) y de hipertensión severa (160/110)."""
    puntos = alt.Chart(df).mark_circle(size=60, opacity=0.75, stroke="white", strokeWidth=1).encode(
        x=alt.X("pas_mmhg:Q", title="Presión sistólica (mmHg)", scale=alt.Scale(zero=False)),
        y=alt.Y("pad_mmhg:Q", title="Presión diastólica (mmHg)", scale=alt.Scale(zero=False)),
        color=alt.Color("riesgo_obstetrico:N", title="Clase", scale=escala_clases(), sort=NOMBRES_CLASES),
        tooltip=[alt.Tooltip("riesgo_obstetrico:N", title="Clase"), alt.Tooltip("pas_mmhg:Q", title="PAS"),
                 alt.Tooltip("pad_mmhg:Q", title="PAD"), alt.Tooltip("proteinuria:Q", title="Proteinuria")],
    )
    umbrales = pd.DataFrame({"valor": [140, 160], "tipo": ["140/90 hipertensión", "160/110 severa (regla)"]})
    vert = alt.Chart(umbrales).mark_rule(strokeDash=[4, 4], color=TINTA_SUAVE).encode(x="valor:Q", tooltip=["tipo:N"])
    hori = alt.Chart(pd.DataFrame({"valor": [90, 110], "tipo": umbrales["tipo"]})).mark_rule(
        strokeDash=[4, 4], color=TINTA_SUAVE).encode(y="valor:Q", tooltip=["tipo:N"])
    return _tema(alt.layer(puntos, vert, hori), 380)


def barras_nulos(pct):
    """% de valores faltantes por variable (una sola serie: sin leyenda)."""
    df = pd.DataFrame({"variable": list(pct), "pct": list(pct.values())})
    barras = alt.Chart(df).mark_bar(color=SERIE_1, cornerRadiusEnd=4, size=26).encode(
        x=alt.X("pct:Q", title="% de registros sin el dato"), y=alt.Y("variable:N", title=None, sort="-x"),
        tooltip=[alt.Tooltip("variable:N", title="Variable"), alt.Tooltip("pct:Q", title="% faltante", format=".2f")])
    etiquetas = barras.mark_text(align="left", dx=6, color=TINTA).encode(text=alt.Text("pct:Q", format=".2f"))
    return _tema(barras + etiquetas, 50 * len(df) + 30)


def barras_clases(df, columna="riesgo_obstetrico"):
    conteo = df[columna].value_counts().reindex(NOMBRES_CLASES).rename_axis("clase").reset_index(name="n")
    barras = alt.Chart(conteo).mark_bar(cornerRadiusEnd=4, size=34).encode(
        x=alt.X("clase:N", title=None, sort=NOMBRES_CLASES, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("n:Q", title="Gestantes"),
        color=alt.Color("clase:N", scale=escala_clases(), legend=None),
        tooltip=[alt.Tooltip("clase:N", title="Clase"), alt.Tooltip("n:Q", title="Gestantes")])
    return _tema(barras + barras.mark_text(dy=-8, color=TINTA).encode(text="n:Q"), 260)


def histogramas_comparados(sintetico, ips, variable, titulo):
    """Distribución de una variable en el dataset sintético y en el archivo de la IPS (dos paneles, mismo eje)."""
    df = pd.concat([pd.DataFrame({"valor": sintetico.dropna(), "fuente": "Sintético"}),
                    pd.DataFrame({"valor": ips.dropna(), "fuente": "IPS"})])
    return _tema(alt.Chart(df).mark_bar(cornerRadiusEnd=3).encode(
        x=alt.X("valor:Q", bin=alt.Bin(maxbins=25), title=titulo),
        y=alt.Y("count():Q", stack=None, title="Registros"),
        color=alt.Color("fuente:N", title="Fuente", scale=alt.Scale(domain=["Sintético", "IPS"], range=[SERIE_1, SERIE_2])),
        row=alt.Row("fuente:N", title=None, sort=["Sintético", "IPS"]),
        tooltip=[alt.Tooltip("fuente:N", title="Fuente"), alt.Tooltip("count():Q", title="Registros")],
    ).resolve_scale(y="independent"), 140)


def curva_aprendizaje(df, modelo, dominio_x=(50, 720)):
    """F1-macro en entrenamiento y en validación cruzada según el tamaño del entrenamiento.

    dominio_x=None ajusta el eje a los datos (para particiones distintas de la oficial).
    """
    d = df[df["modelo"] == modelo]
    if dominio_x is None:
        dominio_x = (d["n_entrenamiento"].min() * 0.85, d["n_entrenamiento"].max() * 1.05)
    largo = pd.concat([
        pd.DataFrame({"n": d["n_entrenamiento"], "f1": d["f1_entrenamiento"], "std": d["f1_entrenamiento_std"], "serie": "Entrenamiento"}),
        pd.DataFrame({"n": d["n_entrenamiento"], "f1": d["f1_cv"], "std": d["f1_cv_std"], "serie": "Validación cruzada"}),
    ])
    largo["bajo"], largo["alto"] = largo["f1"] - largo["std"], largo["f1"] + largo["std"]
    escala = alt.Scale(domain=["Entrenamiento", "Validación cruzada"], range=[SERIE_1, SERIE_2])
    base = alt.Chart(largo).encode(x=alt.X("n:Q", title="Gestantes de entrenamiento", scale=alt.Scale(domain=list(dominio_x), nice=False)),
                                   color=alt.Color("serie:N", title=None, scale=escala))
    piso = min(0.55, float(largo["bajo"].min()) - 0.02)  # una configuración mala no debe salirse del gráfico
    banda = base.mark_area(opacity=0.14).encode(y=alt.Y("bajo:Q", title="F1-macro", scale=alt.Scale(domain=[piso, 1.02])), y2="alto:Q")
    linea = base.mark_line(strokeWidth=2).encode(y="f1:Q")
    puntos = base.mark_point(size=70, filled=True, stroke="white", strokeWidth=2).encode(
        y="f1:Q", tooltip=[alt.Tooltip("serie:N", title="Serie"), alt.Tooltip("n:Q", title="n"),
                           alt.Tooltip("f1:Q", title="F1-macro", format=".3f"), alt.Tooltip("std:Q", title="± desv.", format=".3f")])
    return _tema(alt.layer(banda, linea, puntos), 300)


def escalabilidad(df):
    """Segundos de carga, limpieza y entrenamiento según el número de registros."""
    etapas = {"carga_s": "Carga", "limpieza_s": "Limpieza", "entrenamiento_s": "Entrenamiento"}
    largo = df.melt("registros", list(etapas), "etapa", "segundos").replace({"etapa": etapas})
    escala = alt.Scale(domain=list(etapas.values()), range=["#E0A33A", SERIE_2, SERIE_1])
    base = alt.Chart(largo).encode(
        x=alt.X("registros:Q", title="Registros", axis=alt.Axis(values=sorted(df["registros"].unique().tolist()), format="~s")),
        y=alt.Y("segundos:Q", title="Segundos"), color=alt.Color("etapa:N", title=None, scale=escala, sort=list(etapas.values())))
    puntos = base.mark_point(size=70, filled=True, stroke="white", strokeWidth=2).encode(
        tooltip=[alt.Tooltip("etapa:N", title="Etapa"), alt.Tooltip("registros:Q", title="Registros", format=","),
                 alt.Tooltip("segundos:Q", title="Segundos", format=".2f")])
    return _tema(alt.layer(base.mark_line(strokeWidth=2), puntos), 300)


def f1_por_particion(valores):
    df = pd.DataFrame({"particion": [f"P{i}" for i in range(1, len(valores) + 1)], "f1": valores})
    barras = alt.Chart(df).mark_bar(color=SERIE_1, cornerRadiusEnd=4, size=30).encode(
        x=alt.X("particion:N", title="Partición", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("f1:Q", title="F1-macro", scale=alt.Scale(domain=[0, 1])),
        tooltip=[alt.Tooltip("particion:N", title="Partición"), alt.Tooltip("f1:Q", title="F1-macro", format=".4f")])
    return _tema(barras + barras.mark_text(dy=-8, color=TINTA).encode(text=alt.Text("f1:Q", format=".3f")), 240)


def dispersion_hiperparametros(df):
    """F1-macro de cada configuración probada, por modelo y estrategia de balanceo."""
    escala = alt.Scale(domain=["Regresión Logística", "SVM", "Random Forest"], range=["#E0A33A", SERIE_2, SERIE_1])
    puntos = alt.Chart(df).mark_point(size=80, filled=True, opacity=0.8, stroke="white", strokeWidth=1).encode(
        x=alt.X("cv_recall_alto_media:Q", title="Recall de Alto Riesgo (CV)", scale=alt.Scale(zero=False)),
        y=alt.Y("cv_f1_macro_media:Q", title="F1-macro (CV)", scale=alt.Scale(zero=False)),
        color=alt.Color("modelo:N", title="Modelo", scale=escala),
        shape=alt.Shape("balanceo:N", title="Balanceo"),
        tooltip=[alt.Tooltip("modelo:N", title="Modelo"), alt.Tooltip("balanceo:N", title="Balanceo"),
                 alt.Tooltip("hiperparametros:N", title="Hiperparámetros"),
                 alt.Tooltip("cv_f1_macro_media:Q", title="F1-macro", format=".4f"),
                 alt.Tooltip("cv_recall_alto_media:Q", title="Recall Alto", format=".4f")])
    return _tema(puntos, 380)
