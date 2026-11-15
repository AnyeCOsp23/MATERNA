"""Fase 3: la lista de chequeo del ciclo de vida no puede citar evidencia que no existe."""
from src.lista_chequeo import ACTIVIDADES, ESTADOS, ETAPAS, FASES, archivos_faltantes, resumen, tabla


def test_cubre_las_12_fases():
    assert list(FASES) == [f"{i:02d}" for i in range(1, 13)]
    assert {a[0] for a in ACTIVIDADES} == set(FASES)
    assert len(resumen()) == 12 and len(tabla()) == len(ACTIVIDADES)


def test_los_archivos_citados_existen():
    assert archivos_faltantes() == []


def test_estados_coherentes():
    for fase, actividad, estado, evidencia, archivos, etapa in ACTIVIDADES:
        assert estado in ESTADOS, actividad
        if estado == "Hecho":
            # lo hecho señala dónde verlo y con qué archivo; no le queda etapa pendiente
            assert archivos and evidencia != "—" and etapa is None, actividad
        else:
            assert etapa in ETAPAS, actividad
