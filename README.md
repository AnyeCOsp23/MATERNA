# MATERNA — Sistema de Alerta Temprana de Riesgo Materno-Perinatal

**Zonas dispersas y comunidades indígenas de La Guajira y Cesar**
Proyecto de aula · Inteligencia Artificial · Ingeniería de Sistemas, 7.º semestre · Universidad Popular del Cesar (UPC) · 2026

Equipo: Anyelin Cecilia Ospino Rueda · Duan Andrés Pineda Corrales · Rigoberto Márquez Fernández
Docente: Tony Jiménez

> ⚠️ **Prototipo académico.** Los modelos se entrenaron con un dataset **sintético** (1.200 registros) que el equipo calibró con proporciones del DANE y del INS. No contiene historias clínicas reales y **no debe usarse para tomar decisiones clínicas.**

---

## 1. ¿Qué hace?

Clasifica a una gestante en **Bajo, Medio o Alto Riesgo** obstétrico a partir de datos que se pueden tomar en un puesto de salud rural: edad, edad gestacional, controles previos, presión arterial, frecuencia cardiaca fetal, glucosa, proteinuria en tira y convulsiones. El sistema es **híbrido**:

1. Un **motor de reglas clínicas** marca de inmediato Alto Riesgo si hay PAS ≥ 160, PAD ≥ 110, convulsiones o proteinuria ++. La regla prevalece sobre el modelo.
2. Si no hay signos críticos, decide un **modelo de aprendizaje automático** (SVM calibrado; la Regresión Logística es el baseline).

## 2. Arquitectura

```mermaid
flowchart LR
    A[Formulario en campo<br/>app_demo.py / app móvil] --> B{Motor de reglas<br/>clinical_rules.py}
    B -- signo crítico --> R[ALTO RIESGO<br/>origen: regla]
    B -- sin signos críticos --> P[Pipeline de preprocesamiento<br/>imputación · RobustScaler · One-Hot]
    P --> M[SVM calibrado<br/>predict_proba]
    M --> C[Categoría + probabilidades<br/>origen: modelo]
    R --> S[(SQLite local<br/>pendiente de sincronizar)]
    C --> S
    S -. con conectividad, Fase 3 .-> API[API FastAPI / consola ESE-IPS]
```

Pipeline de entrenamiento (todo lo que aprende de los datos se ajusta **solo** con entrenamiento o con cada fold):

```
CSV crudo ─► limpieza estructural ─► partición estratificada 70/15/15
                                          │
              train ──► [ imputación estratificada ─► RobustScaler + One-Hot ─► SMOTE | class_weight ─► modelo ]
                         └──────────────── GridSearchCV, 5-fold estratificado ─────────────────┘
              val   ──► selección del modelo del sistema híbrido
              test  ──► evaluación final (una sola vez)
```

## 3. Estructura del repositorio

```
MATERNA/
├── app_demo.py                      # Interfaz Streamlit (demo de sustentación, offline-first)
├── requirements.txt
├── data/
│   ├── raw/dataset_riesgo_materno_guajira_cesar.csv
│   └── processed/                   # Particiones train/val/test (se regeneran, no se versionan)
├── src/
│   ├── config.py                    # Rutas, semilla y definición de variables
│   ├── data_preprocessing.py        # Sub-fase 2.1
│   ├── train_models.py              # Sub-fase 2.2
│   ├── clinical_rules.py            # Sub-fase 2.3: evaluar_riesgo_hibrido()
│   └── evaluate.py                  # Sub-fase 2.4
├── models/                          # Modelos entrenados (.joblib) y metadatos
├── notebooks/
│   ├── EDA_Riesgo_Materno_Guajira_Cesar.ipynb       # EDA corregido de la Fase 1
│   └── Fase2_Modelado_y_Evaluacion_MATERNA.ipynb    # Notebook de la Fase 2
├── reports/
│   ├── metrics/                     # CSV/JSON con todas las métricas y experimentos
│   └── figures/                     # Matrices de confusión, ROC, comparación
├── docs/                            # Documento técnico y guion de sustentación
└── contexto/                        # Documentos de la Fase 1 y guías de la asignatura
```

## 4. Instalación y ejecución

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   ·   Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt

python -m src.data_preprocessing   # 2.1 reporte de calidad y particiones
python -m src.train_models         # 2.2 búsqueda de hiperparámetros (~1 min) y modelos
python -m src.evaluate             # 2.4 métricas, figuras y auditoría de sesgos
streamlit run app_demo.py          # 2.3 demo interactiva (http://localhost:8501)
```

Los modelos ya entrenados vienen en `models/`, así que la demo funciona sin reentrenar. Todo es reproducible con la semilla 42.

## 5. Resultados (conjunto de prueba, n = 180, de los cuales 23 son Alto Riesgo)

| Sistema | Accuracy | F1-macro (IC 95 %) | ROC-AUC OvR | Recall Alto (IC 95 %) | FN Alto | Costo clínico* |
|---|---|---|---|---|---|---|
| Regresión Logística (baseline) | 0,722 | 0,724 [0,64–0,79] | 0,854 | 0,870 [0,70–1,00] | 3 | 99 |
| SVM RBF calibrado | 0,856 | 0,846 [0,78–0,90] | 0,961 | 0,783 [0,59–0,94] | 5 | 54 |
| Híbrido (RL + reglas) | 0,733 | 0,742 [0,67–0,80] | 0,864 | 0,957 [0,85–1,00] | 1 | 89 |
| **Híbrido (SVM + reglas)** | **0,878** | **0,886 [0,83–0,93]** | **0,972** | **0,957 [0,85–1,00]** | **1** | **34** |

\*Matriz de costo ilustrativa que penaliza la subestimación del riesgo (Alto→Bajo = 10, Alto→Medio = 5, Medio→Bajo = 3; la sobreestimación cuesta 1–2). Ningún sistema clasificó un Alto Riesgo como Bajo.

**Desempeño sin signos críticos** (166 casos de prueba donde no actúa ninguna regla, que es el aporte real del modelo): SVM F1-macro 0,847 frente a Regresión Logística 0,673.

Validación cruzada (5-fold, entrenamiento): SVM RBF (C = 100, γ = scale, class_weight) F1-macro 0,861 ± 0,011; Regresión Logística (C = 10, class_weight) 0,750 ± 0,013. El registro de las 130 configuraciones está en `reports/metrics/experimentos_cv_completo.csv`.

## 6. Decisiones técnicas y correcciones

| Tema | Decisión | Motivo |
|---|---|---|
| SMOTE | Dentro de cada fold (`imblearn.Pipeline`) | Aplicarlo antes de la validación cruzada filtraría información sintética de los folds de validación. |
| SMOTE vs. `class_weight` | Se comparan como alternativas; ganó `class_weight` | Usarlos juntos compensaría el desbalance dos veces. |
| Probabilidades del SVM | `CalibratedClassifierCV` (Platt) | `SVC(probability=True)` está deprecado en scikit-learn 1.9. |
| Regresión Logística | `solver='lbfgs'` sin `multi_class` | El parámetro se eliminó; lbfgs ya es multinomial. |
| Imputación | Mediana por **área × trimestre** + indicador `*_no_disponible` | Es lo que definió el documento de la Fase 1; la FCF depende fisiológicamente de la edad gestacional. Con municipio × grupo de edad, 10 de los 24 estratos tenían menos de 10 valores en entrenamiento (Becerril ≥ 35 años: 1), y la mediana resultaba inestable. |
| Variables demográficas | Etnia, municipio y departamento **no** entran al modelo | No mejoran el desempeño (la ablación lo empeora: F1 0,861 → 0,828) y evitan que la identidad étnica funcione como *proxy* de riesgo. Se usan para auditar sesgos. |
| Selección | F1-macro en CV; modelo híbrido elegido en validación | La prueba se usa una sola vez. |

Correcciones a la Fase 1 (detalle en el notebook de EDA):
- El EDA entregado analizaba el dataset UCI y no el propio. Ahora el EDA usa el dataset de La Guajira y Cesar.
- Las conclusiones de ese notebook contradecían sus salidas (duplicados y umbral de desbalance).
- Los nulos **no** se concentran en el área rural en la glucosa (cabecera 14,2 %, rural 12,6 %).
- Se elimina la columna vacía `Unnamed: 16` que genera la coma final del CSV.
- Errores de digitación en el cronograma: "Blatter" → Flutter, "Fasta PI" → FastAPI, "F1/Real" → F1/Recall.

## 7. Limitaciones, ética y sesgos

- **Etiquetas sintéticas por reglas.** Las 89 gestantes con signos críticos están todas etiquetadas como Alto Riesgo, porque las etiquetas se generaron con esos umbrales. El híbrido acierta esos casos por construcción. Las métricas miden la capacidad de reproducir el etiquetado, no el desempeño clínico.
- **Brecha por subgrupo.** El recall de Alto Riesgo es menor en el área rural dispersa (0,78 frente a 0,94 en cabecera) y en la atención por partera o auxiliar (≈0,71–0,73), justo en la población objetivo (ver `reports/metrics/auditoria_subgrupos.csv`).
- **Incertidumbre.** Con 23 casos de Alto Riesgo en prueba, los intervalos de confianza son amplios.
- **Protocolos.** Los textos de acción de la app son orientativos y deben validarse con un ginecobstetra y con la red de referencia de cada ESE/IPS.
- **Idioma.** La interfaz en Wayuunaiki necesita una traducción validada con la comunidad; no se inventa.

## 8. Hoja de ruta (Fase 3)

API FastAPI documentada · app móvil Flutter offline (SQLite) con exportación del modelo · ampliación de la grilla del SVM (C > 100) · ajuste de umbrales orientado al recall en subgrupos rurales · validación con datos reales anonimizados mediante una alianza con una ESE/IPS · informe final con análisis ético.

## 9. Flujo de trabajo con Git

- Rama `main` estable; una rama por tarea (`feat/preprocesamiento`, `feat/app-demo`, `docs/informe-fase2`…) integrada mediante *pull request* revisado por otro integrante.
- Mensajes de commit con prefijo: `feat:`, `fix:`, `docs:`, `exp:` (experimentos), `refactor:`.
- Cada integrante sube su propio trabajo con su cuenta. El historial de `git log` es la evidencia de trabajo incremental que pide la rúbrica.
