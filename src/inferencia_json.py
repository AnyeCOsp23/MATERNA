"""Fase 3 — Inferencia del sistema híbrido usando SOLO los JSON exportados (sin scikit-learn).

Es la especificación que replica la app Flutter en Dart: si este módulo da lo mismo que el
pipeline de scikit-learn (lo verifican las pruebas), los JSON contienen todo lo necesario.

Pasos, en el mismo orden que el pipeline entrenado:
  1. Imputación de glucosa y FCF con la mediana del estrato área × trimestre (o la del área,
     o la global), más los indicadores *_no_disponible.
  2. RobustScaler en las 7 variables continuas: (x - centro) / escala.
  3. One-Hot de área y quién atiende (una categoría desconocida queda en ceros).
  4. Random Forest: cada árbol compara float32(x) <= umbral, como scikit-learn, y la probabilidad
     es el promedio de las hojas de los 300 árboles.
  5. Reglas clínicas: si hay un signo crítico, el resultado es Alto Riesgo aunque el modelo diga otra cosa.
"""
import json
import math
import struct
from pathlib import Path


def a_float32(x):
    """Redondea un double a float32 (scikit-learn convierte X a float32 antes de recorrer los árboles)."""
    return struct.unpack("f", struct.pack("f", x))[0]


def _es_nulo(v):
    return v is None or (isinstance(v, float) and math.isnan(v))


class ClasificadorJSON:
    def __init__(self, preproceso, modelo, reglas):
        self.pre, self.rf, self.reglas = preproceso, modelo, reglas

    @classmethod
    def desde_carpeta(cls, carpeta):
        carpeta = Path(carpeta)
        cargar = lambda nombre: json.loads((carpeta / nombre).read_text(encoding="utf-8"))
        return cls(cargar("preproceso.json"), cargar("modelo_rf.json"), cargar("reglas.json"))

    # ------------------------------------------------------------ preprocesamiento
    def trimestre(self, semanas):
        for t in self.pre["imputacion"]["trimestres"]:
            if t["desde_exclusivo"] < semanas <= t["hasta"]:
                return t["nombre"]
        return None

    def imputar(self, registro):
        imp = self.pre["imputacion"]
        area = str(registro.get("area_residencia"))
        tri = self.trimestre(registro["semanas_gestacion"])
        valores, faltantes = {}, {}
        for col in imp["columnas"]:
            v = registro.get(col)
            faltantes[col] = _es_nulo(v)
            if not faltantes[col]:
                valores[col] = float(v)
                continue
            por_estrato = imp["mediana_estrato"][col].get(area, {})
            if tri in por_estrato:
                valores[col] = por_estrato[tri]
            elif area in imp["mediana_area"][col]:
                valores[col] = imp["mediana_area"][col][area]
            else:
                valores[col] = imp["mediana_global"][col]
        return valores, faltantes

    def vector(self, registro):
        """Las 17 variables de entrada del árbol, en el orden de preproceso.json."""
        pre = self.pre
        for col in pre["obligatorias"]:
            if _es_nulo(registro.get(col)):
                raise ValueError(f"Falta la variable obligatoria: {col}")
        imputados, faltantes = self.imputar(registro)
        x = []
        for col, centro, escala in zip(pre["escalado"]["columnas"], pre["escalado"]["centro"], pre["escalado"]["escala"]):
            v = imputados[col] if col in imputados else float(registro[col])
            x.append((v - centro) / escala)
        for col in pre["discretas"]:
            if col in pre["indicadores"]:
                x.append(1.0 if faltantes[pre["indicadores"][col]] else 0.0)
            else:
                x.append(float(int(registro[col])))
        for item in pre["one_hot"]:
            valor = registro.get(item["columna"])
            x.extend(1.0 if valor == cat else 0.0 for cat in item["categorias"])
        return x

    # ------------------------------------------------------------ modelo
    def _hoja(self, arbol, x32):
        nodo = 0
        while arbol["variable"][nodo] >= 0:
            if x32[arbol["variable"][nodo]] <= arbol["umbral"][nodo]:
                nodo = arbol["izquierda"][nodo]
            else:
                nodo = arbol["derecha"][nodo]
        return arbol["hojas"][arbol["izquierda"][nodo]]

    def probabilidades(self, x):
        x32 = [a_float32(v) for v in x]
        total = [0.0] * len(self.rf["clases"])
        for arbol in self.rf["arboles"]:
            hoja = self._hoja(arbol, x32)
            for k in range(len(total)):
                total[k] += hoja[k]
        n = len(self.rf["arboles"])
        return [t / n for t in total]

    # ------------------------------------------------------------ reglas + resultado
    def signos_criticos(self, registro):
        activadas = []
        for regla in self.reglas["reglas"]:
            v = registro.get(regla["variable"])
            if _es_nulo(v):
                continue
            if regla["condicion"] == "mayor_igual" and float(v) >= regla["umbral"]:
                activadas.append(regla["id"])
            elif regla["condicion"] == "verdadero" and bool(v):
                activadas.append(regla["id"])
        return activadas

    def evaluar(self, registro):
        """Mismo resultado que clinical_rules.evaluar_riesgo_hibrido."""
        proba = self.probabilidades(self.vector(registro))
        clase_modelo = max(range(len(proba)), key=lambda k: (proba[k], -k))  # argmax: el primer máximo
        activadas = self.signos_criticos(registro)
        clase = self.reglas["clase_alto"] if activadas else clase_modelo
        return {
            "probabilidades": proba,
            "clase_modelo": clase_modelo,
            "clase": clase,
            "categoria": self.rf["clases"][clase],
            "origen": "regla_clinica" if activadas else "modelo_ml",
            "reglas_activadas": activadas,
        }
