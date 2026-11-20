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
from src.autenticacion import bloque_toml

pytestmark = pytest.mark.e2e
USUARIO, CLAVE = "e2e", "clave-de-prueba-e2e"

# Se instala antes de que cargue la página y registra, desde el primer instante, si algo de la app se
# pintó antes que la capa del logo y cuántas pantallas de login llegaron a verse a la vez.
OBSERVADOR = """
window.__mt = {contenidoAntesDelLogo: [], logoVisto: false, maxLogins: 0};
new MutationObserver(() => {
  const d = document;
  if (d.getElementById('mt-splash')) window.__mt.logoVisto = true;
  if (!window.__mt.logoVisto) {
    d.querySelectorAll('[data-testid="stForm"], [data-testid="stMarkdownContainer"], [data-testid="stSidebarNav"], input')
      .forEach(e => { const r = e.getBoundingClientRect();
        if (r.width > 0 && r.height > 0) window.__mt.contenidoAntesDelLogo.push(e.getAttribute('data-testid') || e.tagName); });
  }
  const logins = [...d.querySelectorAll('p')].filter(e => e.textContent.includes('Inicie sesión para continuar')).length;
  window.__mt.maxLogins = Math.max(window.__mt.maxLogins, logins);
}).observe(document, {childList: true, subtree: true});
"""
playwright = pytest.importorskip("playwright.sync_api")


def puerto_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def url(tmp_path_factory):
    puerto = puerto_libre()
    carpeta = tmp_path_factory.mktemp("bd")
    usuarios = carpeta / "usuarios.toml"
    usuarios.write_text(bloque_toml(USUARIO, "administrador", "Prueba E2E", CLAVE), encoding="utf-8")
    env = {**os.environ, "MATERNA_BD": str(carpeta / "e2e.sqlite"), "MATERNA_BD_IPS": str(carpeta / "ips.sqlite"),
           "MATERNA_USUARIOS": str(usuarios)}
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
        pg.add_init_script(OBSERVADOR)
        pg.goto(url, wait_until="networkidle")
        # la bienvenida cubre la página ~3,3 s: se espera a que se retire antes de interactuar
        pg.wait_for_selector("#mt-splash", state="attached", timeout=60000)
        pg.wait_for_selector("#mt-splash", state="detached", timeout=10000)
        iniciar_sesion(pg)
        ir_al_triaje(pg)
        yield pg
        navegador.close()


EDAD_POR_CASO = {"Caso 1": "26", "Caso 2": "17", "Caso 3": "27"}


def iniciar_sesion(pg):
    """Tras el login se abre el laboratorio (Módulo 1), que es la página de inicio."""
    pg.get_by_label("Usuario").fill(USUARIO)
    pg.get_by_label("Contraseña").fill(CLAVE)
    pg.get_by_role("button", name="Ingresar").click()
    menu(pg).get_by_role("button", name="Problema").wait_for(timeout=60000)
    esperar_fin_ejecucion(pg)


def menu(pg):
    """El menú de fases de la barra lateral."""
    return pg.locator('[data-testid="stSidebar"]')


def ir_al_triaje(pg):
    pg.get_by_role("link", name="Triaje (Módulo 2)").click()
    pg.wait_for_selector('[data-testid="stNumberInputField"]', timeout=60000)
    esperar_fin_ejecucion(pg)


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
        iniciar_sesion(pg)  # tras la bienvenida, el inicio de sesión queda usable
        ir_al_triaje(pg)
        pg.get_by_role("button", name="Evaluar riesgo materno").click(timeout=10000)
        navegador.close()


@pytest.mark.parametrize("caso, clase", [("Caso 1", "alto"), ("Caso 2", "medio"), ("Caso 3", "bajo")])
def test_flujo_completo_por_caso(pagina, caso, clase):
    cargar_caso(pagina, caso)
    pagina.get_by_role("button", name="Evaluar riesgo materno").click()
    pagina.wait_for_selector(f".mt-result.{clase}", timeout=30000)
    # se espera a que el resultado termine de dibujarse (no un tiempo fijo): el protocolo es lo último
    pagina.locator(".mt-step").first.wait_for(timeout=30000)
    esperar_fin_ejecucion(pagina)
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


def test_navegar_al_laboratorio(pagina):
    """Desde otra página, un clic en una fase del menú vuelve al laboratorio y abre esa fase."""
    menu(pagina).get_by_role("button", name="División").click()
    pagina.locator(".mt-h1", has_text="División de los datos").wait_for(timeout=60000)
    esperar_fin_ejecucion(pagina)
    assert pagina.locator('[class*="st-key-mt-nav-"] button').count() == 14  # 12 fases + ética + mapa territorial
    assert pagina.locator('[class*="st-key-mt-nav-activa-06"]').count() == 1
    assert "Fase 6 · de 12" in pagina.locator(".mt-eyebrow").first.text_content()
    # la tarjeta de la partición y la barra del registro de ejecución están en pantalla
    assert pagina.locator(".st-key-mt-card-particion .mt-part").count() == 1
    # regresión: las etiquetas («Suma 100»…) no se montan sobre la barra de «Prueba» (margen de -1rem de Streamlit)
    assert pagina.evaluate("""() => {
      const tr = [...document.querySelectorAll('.st-key-mt-card-particion .mt-tr')].pop();
      const pills = document.querySelector('.st-key-mt-card-particion .mt-pills');
      return pills.getBoundingClientRect().top >= tr.getBoundingClientRect().bottom; }""")
    assert "Sesión iniciada" in pagina.locator(".mt-lg").inner_text()
    # el ancho del menú deja ver el contenido sin barra horizontal
    assert pagina.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    ir_al_triaje(pagina)


def test_ver_como_decidio_el_sistema_anima_el_recorrido(pagina):
    """Del triaje al recorrido animado: el brillo corre, y «Ver el final» deja el resultado real en pantalla."""
    cargar_caso(pagina, "Caso 1")
    pagina.get_by_role("button", name="Evaluar riesgo materno").click()
    pagina.get_by_role("button", name="Ver cómo decidió el sistema").click(timeout=30000)
    pagina.locator(".mt-h1", has_text="Selección del algoritmo").wait_for(timeout=60000)
    recorrido = pagina.locator(".rec")
    recorrido.locator("svg").wait_for(timeout=30000)
    # el componente está en un shadow DOM: se consulta con localizadores, que lo atraviesan
    recorrido.locator(".brillo").first.wait_for(state="attached", timeout=15000)  # el brillo recorre las líneas
    assert "1 de 5" in recorrido.locator(".paso").inner_text() or "2 de 5" in recorrido.locator(".paso").inner_text()
    recorrido.get_by_role("button", name="Ver el final").click()
    recorrido.locator(".paso", has_text="5 de 5").wait_for(timeout=10000)
    texto = recorrido.locator(".paso").inner_text()
    assert "Alto Riesgo" in texto and "por regla clínica" in texto
    assert recorrido.locator(".puerta.activa").count() == 1 and recorrido.locator(".punto").count() == 300
    ir_al_triaje(pagina)


def test_nada_de_la_app_asoma_antes_del_logo(pagina):
    """Regresión: antes, el login se veía una fracción de segundo antes de la capa del logo."""
    assert pagina.evaluate("window.__mt.contenidoAntesDelLogo") == []


def test_un_solo_login_en_el_primer_arranque(pagina):
    """Regresión: al entrar con el servidor recién iniciado, el login aparecía duplicado y atenuado."""
    assert pagina.evaluate("window.__mt.maxLogins") == 1


def test_sin_errores_de_javascript(pagina):
    assert pagina.errores == []
