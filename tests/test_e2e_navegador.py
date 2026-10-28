"""Punta a punta en Chrome real: levanta la app, usa el formulario y revisa el resultado renderizado.

Ejecutar:  pytest -m e2e      (requiere Google Chrome y  pip install playwright)
"""
import os
import socket
import subprocess
import sys
import time

import pytest

from conftest import RAIZ

pytestmark = pytest.mark.e2e
playwright = pytest.importorskip("playwright.sync_api")


def puerto_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def url(tmp_path_factory):
    puerto = puerto_libre()
    env = {**os.environ, "MATERNA_BD": str(tmp_path_factory.mktemp("bd") / "e2e.sqlite")}
    proceso = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(RAIZ / "app_demo.py"), "--server.headless", "true",
         "--server.port", str(puerto)], cwd=RAIZ, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            socket.create_connection(("127.0.0.1", puerto), timeout=1).close()
            break
        except OSError:
            time.sleep(1)
    yield f"http://127.0.0.1:{puerto}"
    proceso.terminate()


@pytest.fixture(scope="module")
def pagina(url):
    with playwright.sync_playwright() as p:
        navegador = p.chromium.launch(channel="chrome")
        pg = navegador.new_page(viewport={"width": 1440, "height": 900})
        pg.errores = []
        pg.on("pageerror", lambda e: pg.errores.append(str(e)))
        pg.goto(url, wait_until="networkidle")
        pg.wait_for_selector('[data-testid="stNumberInputField"]', timeout=60000)
        # la bienvenida cubre la página ~3,3 s: se espera a que se retire antes de interactuar
        pg.wait_for_selector("#mt-splash", state="attached", timeout=60000)
        pg.wait_for_selector("#mt-splash", state="detached", timeout=10000)
        yield pg
        navegador.close()


EDAD_POR_CASO = {"Caso 1": "26", "Caso 2": "17", "Caso 3": "27"}


def esperar_fin_ejecucion(pg):
    """Streamlit vuelve a ejecutar el script tras cada interacción: se espera a que termine."""
    pg.wait_for_function("() => !document.querySelector('[data-testid=stStatusWidgetRunningIcon]')", timeout=30000)


def cargar_caso(pg, caso):
    """Carga un caso de demostración y espera a que el formulario muestre sus valores (no un tiempo fijo)."""
    pg.get_by_role("button", name=caso).click()
    pg.wait_for_function(
        "edad => document.querySelector('input[aria-label=\"Edad (años)\"]')?.value === edad",
        arg=EDAD_POR_CASO[caso], timeout=30000)
    esperar_fin_ejecucion(pg)


def test_pantalla_de_bienvenida(url):
    """El logo aparece centrado y, pasados 2,5 s, la capa se desvanece y deja usar la app."""
    with playwright.sync_playwright() as p:
        navegador = p.chromium.launch(channel="chrome")
        pg = navegador.new_page(viewport={"width": 1440, "height": 900})
        pg.goto(url)
        splash = pg.locator("#mt-splash")
        splash.wait_for(state="attached", timeout=60000)
        # el logo cargó desde static/ y terminó de subir (1,1 s + 0,15 s de espera inicial)
        pg.wait_for_function("() => { const i = document.querySelector('#mt-splash img'); return i && i.complete && i.naturalWidth > 0 }",
                             timeout=10000)
        pg.wait_for_function("() => document.querySelector('#mt-splash img').getAnimations().every(a => a.playState === 'finished')",
                             timeout=10000)
        caja = pg.locator("#mt-splash img").bounding_box()
        assert abs(caja["x"] + caja["width"] / 2 - 720) < 5 and abs(caja["y"] + caja["height"] / 2 - 450) < 5
        assert splash.evaluate("e => getComputedStyle(e).visibility") == "visible"
        splash.wait_for(state="detached", timeout=6000)  # 2,5 s + 0,8 s de desvanecimiento y se retira del DOM
        pg.get_by_role("button", name="Evaluar riesgo materno").click(timeout=10000)
        navegador.close()


@pytest.mark.parametrize("caso, clase", [("Caso 1", "alto"), ("Caso 2", "medio"), ("Caso 3", "bajo")])
def test_flujo_completo_por_caso(pagina, caso, clase):
    cargar_caso(pagina, caso)
    pagina.get_by_role("button", name="Evaluar riesgo materno").click()
    pagina.wait_for_selector(f".mt-result.{clase}", timeout=30000)
    pagina.wait_for_timeout(1500)
    # las animaciones terminan y las gráficas quedan dibujadas
    assert pagina.locator(".mt-ring .arc").count() == 1
    assert pagina.locator(".mt-fill").count() == 3
    assert pagina.locator(".mt-step").count() >= 3


def test_escribir_en_el_formulario(pagina):
    cargar_caso(pagina, "Caso 3")
    campo = pagina.get_by_label("Presión sistólica — PAS (mmHg)")
    campo.fill("172")
    campo.press("Enter")
    esperar_fin_ejecucion(pagina)
    pagina.get_by_role("button", name="Evaluar riesgo materno").click()
    pagina.wait_for_selector(".mt-result.alto", timeout=30000)
    assert "PAS 172 mmHg" in pagina.locator(".mt-chips").inner_text()


def test_sin_errores_de_javascript(pagina):
    assert pagina.errores == []
