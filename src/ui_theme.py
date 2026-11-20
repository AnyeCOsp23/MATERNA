"""Capa visual de la consola (Módulo 1): estilo «Apple suave» con tarjetas blancas y la paleta de la app MATERNA.

Paleta del sistema: vino #7B2D5B, malva #8A4A6D, rosa #F5D3E3 y #EFE0E7, tinta #3A1230, sobre un fondo crema
(#F8F6F1 a #F1EFE8). Es la misma de la app Flutter (Módulo 2). Los colores de riesgo de los gráficos
(src/graficos.py) no cambian: están validados para daltonismo.
Colores de alerta del triaje: rojo #F099AB (Alto Riesgo / regla clínica), amarillo #F2E88F (Riesgo Medio / dato
faltante) y verde #B6E39A (Bajo Riesgo / estado correcto).

Movimiento: cubic-bezier(.32,.72,0,1) para respuestas (0,2 s) y una curva con rebote mínimo para entradas (0,55 s).
Todo es CSS + SVG en línea (sin fuentes ni librerías externas), así que la interfaz funciona offline.
Respeta `prefers-reduced-motion` (sin animaciones) y `prefers-reduced-transparency`.
"""
import html
import re

from streamlit import components


# Por categoría: fondo pastel (color de alerta), tinta legible sobre ese fondo (contraste >= 5:1),
# un tono más intenso del mismo color para el anillo y una barra en degradado.
ESTILO_CATEGORIA = {
    "Alto Riesgo": {
        "clase": "alto", "titulo": "Alto riesgo", "sub": "Emergencia obstétrica · remisión inmediata",
        "fondo": "linear-gradient(135deg, #F099AB 0%, #F6B9C6 55%, #FAD6DE 100%)", "tinta": "#6B1832",
        "acento": "#D9667F", "barra": "linear-gradient(90deg, #E07A92, #F099AB)",
    },
    "Riesgo Medio": {
        "clase": "medio", "titulo": "Riesgo medio", "sub": "Valoración médica prioritaria",
        "fondo": "linear-gradient(135deg, #F2E88F 0%, #F6EEB0 55%, #FAF5D2 100%)", "tinta": "#5A4F0E",
        "acento": "#CDBE45", "barra": "linear-gradient(90deg, #D8C955, #F2E88F)",
    },
    "Bajo Riesgo": {
        "clase": "bajo", "titulo": "Bajo riesgo", "sub": "Control prenatal de rutina",
        "fondo": "linear-gradient(135deg, #B6E39A 0%, #CBECB6 55%, #E0F4D3 100%)", "tinta": "#2C5219",
        "acento": "#7DBB59", "barra": "linear-gradient(90deg, #8CC96A, #B6E39A)",
    },
}

# Isotipo del logo (sin la palabra MATERNA), con fondo transparente; lo sirve Streamlit desde static/
LOGO_ISOTIPO = '<img src="./app/static/logo_isotipo.webp" width="62" height="62" alt="" aria-hidden="true">'


# Trazo en currentColor: el ícono toma la tinta de la tarjeta de resultado
_TRAZO = 'fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"'
ICONOS = {
    "alto": f'<svg viewBox="0 0 24 24" width="26" height="26" {_TRAZO}><path d="M12 3.5 21 19.5H3z"/><path d="M12 10v4.2"/><path d="M12 17.2h.01"/></svg>',
    "medio": f'<svg viewBox="0 0 24 24" width="26" height="26" {_TRAZO}><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/></svg>',
    "bajo": f'<svg viewBox="0 0 24 24" width="26" height="26" {_TRAZO}><circle cx="12" cy="12" r="8.5"/><path d="m8 12.3 2.7 2.7L16.2 9.5"/></svg>',
}


def _pct(p):
    return f"{p * 100:.1f}".replace(".", ",") + " %"


def _html(bloque):
    """Compacta el HTML: el renderizador de Markdown de Streamlit convierte las líneas indentadas
    en bloques de código y corta el HTML en las líneas vacías."""
    return " ".join(linea.strip() for linea in bloque.strip().splitlines() if linea.strip())


CSS = """
<style>
@property --mt-num { syntax: '<integer>'; initial-value: 0; inherits: false; }

:root {
  /* ---- movimiento: una curva para respuestas y otra, con un rebote mínimo, para entradas ---- */
  --mt-curva: cubic-bezier(.32, .72, 0, 1);
  --mt-curva-entrada: cubic-bezier(.2, .9, .25, 1.08);
  --mt-rapida: .2s;            /* respuestas: hover, presión, cambios de color */
  --mt-entrada: .55s;          /* entrada de tarjetas y paneles */
  --mt-entrada-corta: .35s;    /* entrada de elementos pequeños */
  --mt-entrada-larga: .75s;    /* gráficas que crecen (600-900 ms con el escalonado) */
  --mt-cascada: 70ms;          /* retraso entre elementos consecutivos */
  --mt-subida: 16px;           /* desplazamiento vertical de entrada */
  --mt-rebote: 1.05;           /* escala máxima del rebote de elementos pequeños */

  /* ---- paleta del sistema (la misma de la app MATERNA) ---- */
  --mt-vino: #7B2D5B;
  --mt-vino-oscuro: #5C1F45;
  --mt-malva: #8A4A6D;
  --mt-rosa-medio: #CF97B5;
  --mt-rosa-barra: #D3A0BB;
  --mt-rosa: #F5D3E3;
  --mt-rosa-suave: #EFE0E7;
  --mt-rosa-palido: #FBF4F8;
  --mt-linea: #E9DDE3;
  --mt-linea-tarjeta: #EFE6EA;
  --mt-tinta: #3A1230;
  --mt-tinta-suave: #6B4A5E;
  --mt-tinta-tenue: #8B6F7F;
  --mt-fondo-a: #F8F6F1;
  --mt-fondo-b: #F1EFE8;
  --mt-verde: #4E9A72;
  --mt-ok-fondo: #E9F5EE; --mt-ok-tinta: #1B5E36; --mt-ok-linea: #CFE8D8;
  --mt-warn-fondo: #FFF6E3; --mt-warn-tinta: #7A4A00; --mt-warn-linea: #F1DDB0;
  --mt-error-fondo: #FDECEF; --mt-error-tinta: #7A1F3A; --mt-error-linea: #F3C6D0;
  --mt-info-fondo: #F8EEF3; --mt-info-tinta: #5C1F45; --mt-info-linea: #EBD5E0;
  /* nombres anteriores, que siguen usando el inicio de sesión y el triaje */
  --mt-ciruela-900: var(--mt-vino);
  --mt-ciruela-700: #9A4474;
  --mt-ciruela-500: #C4709C;
  --mt-ciruela-100: var(--mt-rosa);
  --mt-crema: var(--mt-fondo-a);

  /* ---- colores de alerta del triaje ---- */
  --mt-rojo: #F099AB;
  --mt-amarillo: #F2E88F;
  --mt-verde-alerta: #B6E39A;
  --mt-info: #B85A8E;

  /* ---- superficies ---- */
  --mt-radio-s: 12px;
  --mt-radio-m: 14px;
  --mt-radio-l: 18px;
  --mt-sombra: 0 1px 2px rgba(60, 20, 45, .04), 0 8px 24px rgba(60, 20, 45, .05);
  --mt-sombra-alta: 0 2px 4px rgba(60, 20, 45, .05), 0 14px 36px rgba(60, 20, 45, .10);
  --mt-borde: 1px solid var(--mt-linea-tarjeta);

  --mt-fuente: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", Inter, system-ui, "Segoe UI", sans-serif;
}

/* ---------- lienzo ---------- */
/* No usar un selector genérico como [class*="st-"]: pisaría la fuente de íconos (Material Symbols) */
html, body, .stApp, p, label, input, button, textarea, li, .mt-hero, .mt-result, .mt-panel,
[data-testid="stMarkdownContainer"], [data-testid="stCaptionContainer"] { font-family: var(--mt-fuente); }
h1, h2, h3, h4, h5 { font-family: var(--mt-fuente) !important; }
/* Streamlit resta 1 rem bajo cada bloque de Markdown porque espera un párrafo al final: con nuestras piezas
   (que no terminan en párrafo) el bloque siguiente se montaba encima. También vale para las piezas animadas,
   que van envueltas en <div data-mt> sin clase (barra de la partición, indicadores de la fase 10) */
[data-testid="stMarkdownContainer"]:has(> [class^="mt-"]:last-child),
[data-testid="stMarkdownContainer"]:has(> [data-mt]:last-child) { margin-bottom: 0 !important; }
/* sin el ícono de enlace que Streamlit agrega a los títulos */
.mt-cab [data-testid="stHeaderActionElements"], .mt-card-h [data-testid="stHeaderActionElements"],
.mt-section [data-testid="stHeaderActionElements"] { display: none; }
.stApp {
  color: var(--mt-tinta);
  background: linear-gradient(180deg, var(--mt-fondo-a), var(--mt-fondo-b));
  background-attachment: fixed;
}
header[data-testid="stHeader"] { background: transparent; }
/* ---------- inicio de sesión a pantalla completa: marca (50 %) | acceso (50 %) ----------
   El contenedor se fija a toda la ventana (100vw x 100vh): sin márgenes de Streamlit ni barras de desplazamiento.
   Entra con una transición continua tras la bienvenida: la vista se aclara del desenfoque y el contenido de
   cada panel sube en cascada. Las animaciones esperan en pausa (en su primer cuadro, invisibles bajo el logo)
   hasta que el logo empieza a desvanecerse (body.mt-revelado); si no hay bienvenida en pantalla (al cerrar
   sesión o al equivocarse de clave) corren de inmediato. Los tamaños escalan con la ventana (clamp). */
@keyframes mt-login-entra {
  from { opacity: 0; filter: blur(18px); }
  to { opacity: 1; filter: blur(0); }
}
@keyframes mt-login-aparece {
  from { opacity: 0; transform: translateY(18px); filter: blur(8px); }
  to { opacity: 1; transform: none; filter: blur(0); }
}
.st-key-mt-login {
  position: fixed; inset: 0; z-index: 99; margin: 0; padding: 0; gap: 0;
  overflow-x: hidden; overflow-y: auto; background: #FFFFFF;
}
.st-key-mt-login [data-testid="stHorizontalBlock"] {
  gap: 0 !important; min-height: 100vh; min-height: 100dvh; align-items: stretch; flex-wrap: nowrap;
  animation: mt-login-entra 1s var(--mt-curva) both;
}
.st-key-mt-login .mt-escalon, .st-key-mt-login-acceso div[data-testid="stForm"],
.st-key-mt-login-acceso [data-testid="stCaptionContainer"], .st-key-mt-login-acceso [data-testid="stAlert"] {
  animation: mt-login-aparece .75s var(--mt-curva) calc(.25s + var(--paso, 0) * 90ms) both;
}
.st-key-mt-login-acceso div[data-testid="stForm"] { --paso: 3; }
.st-key-mt-login-acceso [data-testid="stCaptionContainer"], .st-key-mt-login-acceso [data-testid="stAlert"] { --paso: 4; }
.st-key-mt-login [data-testid="stHorizontalBlock"], .st-key-mt-login .mt-escalon,
.st-key-mt-login-acceso div[data-testid="stForm"], .st-key-mt-login-acceso [data-testid="stCaptionContainer"],
.st-key-mt-login-acceso [data-testid="stAlert"] { animation-play-state: paused; }
body.mt-revelado .st-key-mt-login [data-testid="stHorizontalBlock"], body.mt-revelado .st-key-mt-login .mt-escalon,
body.mt-revelado .st-key-mt-login-acceso div[data-testid="stForm"],
body.mt-revelado .st-key-mt-login-acceso [data-testid="stCaptionContainer"],
body.mt-revelado .st-key-mt-login-acceso [data-testid="stAlert"],
body:not(:has(#mt-splash)) .st-key-mt-login [data-testid="stHorizontalBlock"],
body:not(:has(#mt-splash)) .st-key-mt-login .mt-escalon,
body:not(:has(#mt-splash)) .st-key-mt-login-acceso div[data-testid="stForm"],
body:not(:has(#mt-splash)) .st-key-mt-login-acceso [data-testid="stCaptionContainer"],
body:not(:has(#mt-splash)) .st-key-mt-login-acceso [data-testid="stAlert"] { animation-play-state: running; }
/* mientras el login cubre la ventana, la página de abajo no debe desplazarse */
/* los enlaces del login («¿Olvidó su contraseña?», recuperación) entran después del formulario */
.st-key-mt-login-acceso [data-testid="stButton"] {
  animation: mt-login-aparece .75s var(--mt-curva) calc(.25s + 5 * 90ms) both; animation-play-state: paused;
}
body.mt-revelado .st-key-mt-login-acceso [data-testid="stButton"],
body:not(:has(#mt-splash)) .st-key-mt-login-acceso [data-testid="stButton"] { animation-play-state: running; }
body:has(.st-key-mt-login) { overflow: hidden; }
.mt-acceso-logo.mt-compacto { margin-bottom: clamp(.8rem, 2vh, 1.4rem); }
.st-key-mt-recuperar-otra-vez { display: flex; justify-content: flex-end; }

/* panel de marca (izquierda) */
.st-key-mt-login [data-testid="stColumn"]:first-child {
  position: relative; overflow: hidden;
  background:
    radial-gradient(110% 80% at 0% 0%, rgba(216, 99, 155, .55) 0%, transparent 60%),
    radial-gradient(70% 60% at 100% 100%, rgba(239, 198, 217, .14) 0%, transparent 70%),
    linear-gradient(160deg, var(--mt-ciruela-900) 0%, #5C1F45 100%);
}
.mt-marca {
  position: relative; display: flex; flex-direction: column; min-height: 100vh; min-height: 100dvh; color: #FFFFFF;
  padding: clamp(2.2rem, 5vh, 4.5rem) clamp(2.2rem, 5.5vw, 6.5rem);
}
.mt-marca-arcos { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; }
/* isotipo en blanco: el filtro va en la imagen y la animación (que también usa filter) en su contenedor */
.mt-marca-logo {
  position: relative; display: block; width: clamp(76px, 6.4vw, 124px); height: auto;
  filter: brightness(0) invert(1); opacity: .96;
}
.mt-marca-texto { position: relative; margin: auto 0; }
.mt-marca-titulo {
  font-size: clamp(2.5rem, 3.9vw, 4.6rem); line-height: 1.05; font-weight: 700; letter-spacing: -.035em;
  color: #FFFFFF; margin-bottom: clamp(1rem, 2.4vh, 1.8rem); max-width: 14ch;
}
.mt-marca-texto p { margin: 0; max-width: 34ch; font-size: clamp(1.02rem, 1.2vw, 1.32rem); line-height: 1.6; color: rgba(255, 255, 255, .84); }
.mt-marca-pie { position: relative; font-size: clamp(.78rem, .8vw, .9rem); color: rgba(255, 255, 255, .66); }

/* panel de acceso (derecha) */
.st-key-mt-login [data-testid="stColumn"]:last-child { background: #FFFFFF; }
/* la columna envuelve el panel en un bloque vertical de alto completo: se centra ahí */
.st-key-mt-login [data-testid="stColumn"]:last-child > [data-testid="stVerticalBlock"] { justify-content: center; }
.st-key-mt-login-acceso {
  width: min(500px, 100%); margin: 0 auto; gap: clamp(1rem, 2vh, 1.5rem);
  padding: clamp(2rem, 5vh, 4rem) clamp(1.6rem, 4vw, 3rem);
}
.mt-acceso-logo { display: flex; align-items: center; gap: clamp(.7rem, 1vw, 1.1rem); margin-bottom: clamp(1.4rem, 4vh, 2.8rem); }
.mt-acceso-logo img { width: clamp(62px, 5vw, 92px); height: auto; }
.mt-acceso-logo span {
  font-size: clamp(2.1rem, 2.8vw, 3.1rem); font-weight: 700; letter-spacing: -.035em; line-height: 1;
  background: linear-gradient(120deg, var(--mt-ciruela-900) 0%, var(--mt-ciruela-700) 55%, var(--mt-ciruela-500) 100%);
  -webkit-background-clip: text; background-clip: text; color: transparent;
}
.mt-acceso-titulo { font-size: clamp(1.85rem, 2.3vw, 2.6rem); font-weight: 700; letter-spacing: -.03em; color: var(--mt-tinta); line-height: 1.12; }
.mt-acceso-sub { margin: .55rem 0 clamp(1rem, 2.4vh, 1.6rem); font-size: clamp(.95rem, 1vw, 1.1rem); color: var(--mt-tinta-suave); line-height: 1.5; }
/* el formulario va sin tarjeta propia; campos y botón más grandes */
.st-key-mt-login-acceso div[data-testid="stForm"] {
  background: transparent !important; border: 0 !important; box-shadow: none !important; padding: 0 !important;
  -webkit-backdrop-filter: none !important; backdrop-filter: none !important;
}
.st-key-mt-login-acceso label p { font-size: clamp(.86rem, .9vw, .98rem) !important; }
.st-key-mt-login-acceso [data-testid="stTextInputRootElement"] { min-height: clamp(2.9rem, 5.6vh, 3.4rem); }
.st-key-mt-login-acceso input { font-size: clamp(.98rem, 1vw, 1.08rem) !important; }
.st-key-mt-login-acceso [data-testid="stBaseButton-primaryFormSubmit"] {
  min-height: clamp(3rem, 6vh, 3.5rem); margin-top: .4rem; font-size: clamp(1rem, 1.05vw, 1.12rem);
}
/* «¿Olvidó su contraseña?» y los enlaces de la recuperación: texto en vino, sin caja */
.st-key-mt-olvido { margin-top: -.4rem; }
.st-key-mt-olvido button, .st-key-mt-recuperar-otra-vez button, .st-key-mt-recuperar-volver button {
  min-height: 0 !important; padding: 2px 0 !important; color: var(--mt-vino) !important; font-weight: 600 !important;
}
.st-key-mt-olvido button:hover p, .st-key-mt-recuperar-otra-vez button:hover p, .st-key-mt-recuperar-volver button:hover p {
  text-decoration: underline; text-underline-offset: 3px;
}
.st-key-mt-login-acceso [data-testid="stCaptionContainer"], .st-key-mt-login-acceso [data-testid="stCaptionContainer"] p {
  text-align: left; color: var(--mt-tinta-suave) !important; font-size: clamp(.8rem, .85vw, .9rem); line-height: 1.55;
}

/* pantallas angostas: los paneles se apilan y se desplaza el login completo */
@media (max-width: 760px) {
  .st-key-mt-login [data-testid="stHorizontalBlock"] { flex-wrap: wrap; }
  .mt-marca { min-height: 0; padding: 2rem 1.6rem 1.8rem; gap: 1.1rem; }
  .mt-marca-logo { width: 56px; }
  .mt-marca-titulo { font-size: 2rem; margin-bottom: .6rem; }
  .mt-marca-pie { display: none; }
  .st-key-mt-login-acceso { padding: 2rem 1.6rem 2.4rem; }
  .mt-acceso-logo { margin-bottom: 1.2rem; }
}
/* un solo ojito en la contraseña: el de la app (igual en todos los navegadores), no el que agrega Edge */
.st-key-mt-login input::-ms-reveal, .st-key-mt-login input::-ms-clear { display: none; }
/* el aviso "Press Enter to submit form" (en inglés) se montaba sobre el campo; Enter sigue enviando */
.st-key-mt-login [data-testid="InputInstructions"] { display: none; }
/* los componentes sin contenido visible (bienvenida y motor de animaciones) no deben dejar hueco; las gráficas sí se ven */
[data-testid="stElementContainer"]:has([data-testid="stBidiComponentRegular"]):not(:has(.mt-echart)) { display: none; }
[data-testid="stToolbar"] { opacity: .55; }
.block-container { max-width: 1240px; padding: 2.2rem 2rem 1.2rem; position: relative; z-index: 1; }

h1, h2, h3, h4 { color: var(--mt-tinta); letter-spacing: -.022em; }
p, label, span, div { -webkit-font-smoothing: antialiased; }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color: var(--mt-tinta-suave) !important; }
a { color: var(--mt-vino); }

/* ---------- movimiento base ---------- */
/* Entrada: sube 16 px mientras pasa de transparente a visible. --i fija su lugar en la cascada. */
@keyframes mt-entrar { from { opacity: 0; transform: translateY(var(--mt-subida)); } to { opacity: 1; transform: none; } }
/* Elementos pequeños: aparecen con un rebote muy sutil (máximo 105 %) */
@keyframes mt-rebotar {
  0%   { opacity: 0; transform: scale(.9); }
  60%  { opacity: 1; transform: scale(var(--mt-rebote)); }
  100% { opacity: 1; transform: scale(1); }
}
@keyframes mt-crecer { from { transform: scaleX(0); } to { transform: scaleX(1); } }
@keyframes mt-subir { from { transform: scaleY(0); } to { transform: scaleY(1); } }
/* "backwards": la animación solo rige hasta terminar; después el hover puede usar transform */
.mt-in, .mt-hero, .mt-result, .mt-note, .mt-panel, .mt-step, .mt-section, .mt-ruta, .mt-cab, [class*="st-key-mt-card-"] {
  animation: mt-entrar var(--mt-entrada) var(--mt-curva-entrada) backwards;
  animation-delay: calc(var(--i, 0) * var(--mt-cascada));
}
/* las tarjetas con gráficas no hacen fundido: el gráfico es el que entra animado (si no, se solaparían) */
[class*="st-key-mt-card-"]:has(.mt-echart) { animation: none; }
.mt-cab { --i: 1; }
.mt-kpi, .mt-badge, .mt-chip, .mt-icon, .mt-section .num, .mt-step .n, .mt-trace div {
  animation: mt-rebotar var(--mt-entrada-corta) var(--mt-curva) backwards;
  animation-delay: calc(var(--i, 0) * var(--mt-cascada) + 120ms);
}
/* Cambios de color, borde y fondo: se funden en 0,2 s */
.mt-pill, .mt-kpi, .mt-trace div, .mt-step, .mt-note, .mt-chip {
  transition: background-color var(--mt-rapida) var(--mt-curva), border-color var(--mt-rapida) var(--mt-curva),
              color var(--mt-rapida) var(--mt-curva), box-shadow var(--mt-rapida) var(--mt-curva),
              transform var(--mt-rapida) var(--mt-curva);
}

/* ---------- barra lateral y menú de fases ---------- */
section[data-testid="stSidebar"] {
  background: rgba(255, 255, 255, .72);
  -webkit-backdrop-filter: blur(20px); backdrop-filter: blur(20px);
  border-right: 1px solid var(--mt-linea);
}
section[data-testid="stSidebar"][data-collapsed="false"] { width: 272px !important; min-width: 272px !important; }
section[data-testid="stSidebar"] > div { background: transparent; }
[data-testid="stSidebarHeader"] { height: 1.6rem; min-height: 1.6rem; padding: .4rem .6rem 0; }
[data-testid="stSidebarUserContent"] { padding: 0 14px 20px; }
section[data-testid="stSidebar"] h4 {
  font-size: 11px !important; font-weight: 700 !important; letter-spacing: 1.2px; text-transform: uppercase;
  color: var(--mt-tinta-tenue) !important; margin: 12px 0 0; padding: 0 10px !important;
}
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"]:has(h4) { margin-bottom: 0 !important; }
section[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"] { height: auto; padding: 6px 14px !important; border-radius: 14px !important; }
.st-key-mt-menu { gap: 3px; }
.mt-menu-marca { display: flex; align-items: center; gap: 8px; margin: 0 0 10px; padding: 0 6px; }
.mt-menu-marca img { height: 32px; width: auto; }
.mt-menu-marca b { display: block; font-size: 16px; font-weight: 700; color: var(--mt-vino); line-height: 1.15; }
.mt-menu-marca span { display: block; font-size: 12px; color: var(--mt-tinta-suave); line-height: 1.2; }
.mt-gl { font-size: 11px; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase; color: var(--mt-tinta-tenue); padding: 12px 10px 4px; }
section[data-testid="stSidebar"] [class*="st-key-mt-nav-"] button {
  justify-content: flex-start; width: 100%; min-height: 32px; height: 32px; padding: 0 10px !important; border: 0 !important;
  border-radius: 10px !important; background: transparent !important; color: var(--mt-tinta) !important;
  font-weight: 500 !important; box-shadow: none !important; transform: none !important;
  transition: background-color var(--mt-rapida) var(--mt-curva), color var(--mt-rapida) var(--mt-curva) !important;
}
section[data-testid="stSidebar"] [class*="st-key-mt-nav-"] button > div,
section[data-testid="stSidebar"] [class*="st-key-mt-nav-"] button span,
section[data-testid="stSidebar"] [class*="st-key-mt-nav-"] button [data-testid="stMarkdownContainer"] { width: 100%; }
section[data-testid="stSidebar"] [class*="st-key-mt-nav-"] button p {
  display: flex; align-items: center; gap: 10px; width: 100%; margin: 0; font-size: 14px; font-weight: inherit; text-align: left;
}
section[data-testid="stSidebar"] [class*="st-key-mt-nav-"] button code {
  flex: none; width: 21px; height: 21px; padding: 0; border-radius: 50%; display: inline-flex; align-items: center;
  justify-content: center; font: 700 11px var(--mt-fuente); background: var(--mt-rosa-suave); color: var(--mt-tinta-suave);
}
section[data-testid="stSidebar"] [class*="st-key-mt-nav-"] button:hover { background: rgba(245, 211, 227, .5) !important; }
section[data-testid="stSidebar"] [class*="st-key-mt-nav-vista-"] button code { background: #E3F3E8; color: var(--mt-ok-tinta); }
section[data-testid="stSidebar"] [class*="st-key-mt-nav-activa-"] button {
  background: var(--mt-rosa) !important; color: var(--mt-vino) !important; font-weight: 700 !important;
}
section[data-testid="stSidebar"] [class*="st-key-mt-nav-activa-"] button code { background: var(--mt-vino); color: #fff; }
/* otras páginas (enlaces) con el mismo aspecto que las fases */
section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] {
  min-height: 32px; padding: 0 10px; border-radius: 10px; gap: 10px; background: transparent;
  transition: background-color var(--mt-rapida) var(--mt-curva);
}
section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] p { font-size: 14px; font-weight: 500; color: var(--mt-tinta); }
section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] [data-testid="stIconMaterial"] { color: var(--mt-tinta-suave); }
section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]:hover { background: rgba(245, 211, 227, .5); }
section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"][aria-current="page"] { background: var(--mt-rosa); }
section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"][aria-current="page"] p { color: var(--mt-vino); font-weight: 700; }
/* botones propios de cada página en la barra lateral (casos del triaje, cerrar sesión): más compactos */
section[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"] { min-height: 36px; padding: 0 14px; border-width: 1.5px; font-size: 13px; }
.mt-usuario { display: flex; align-items: center; gap: 10px; padding: 4px 8px 2px; }
.mt-usuario b { display: block; font-size: 13px; font-weight: 600; color: var(--mt-tinta); line-height: 1.25; }
.mt-usuario span { display: block; font-size: 12px; color: var(--mt-tinta-suave); line-height: 1.25; }
.mt-dot { flex: none; width: 8px; height: 8px; border-radius: 50%; background: #2E9E5B; box-shadow: 0 0 0 3px rgba(46, 158, 91, .16); }

/* ---------- encabezado de cada pantalla ---------- */
.mt-ruta { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap;
  font-size: 13px; font-weight: 500; color: var(--mt-tinta-suave); margin-bottom: 12px; }
.mt-ruta b { color: var(--mt-tinta); font-weight: 700; }
.mt-sesion { display: inline-flex; align-items: center; gap: 8px; }
.mt-cab { display: flex; justify-content: space-between; align-items: flex-end; gap: 12px 20px; flex-wrap: wrap; }
.mt-eyebrow { font-size: 12px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; color: var(--mt-vino); }
.mt-h1 { font-size: 30px !important; line-height: 1.15 !important; font-weight: 700 !important; letter-spacing: -.7px !important;
  color: var(--mt-tinta); margin: 2px 0 2px !important; padding: 0 !important; }
.mt-sub { margin: 0; color: var(--mt-tinta-suave); font-size: 14px; }
.mt-pills { display: flex; flex-wrap: wrap; gap: 8px; }
.mt-pill {
  display: inline-flex; align-items: center; gap: 6px; padding: 5px 12px; border-radius: 999px; white-space: nowrap;
  font-size: 12px; font-weight: 600; color: var(--mt-tinta-suave); background: #fff; border: 1px solid var(--mt-linea);
}
.mt-pill.ok { background: var(--mt-ok-fondo); color: var(--mt-ok-tinta); border-color: var(--mt-ok-linea); }
.mt-pill.warn { background: var(--mt-warn-fondo); color: var(--mt-warn-tinta); border-color: var(--mt-warn-linea); }
.mt-pill.on { background: var(--mt-rosa); color: var(--mt-vino); border-color: var(--mt-rosa); }
.mt-mut { color: var(--mt-tinta-suave); font-size: 13px; }

/* texto corrido: un punto menos que el de Streamlit, como en las tarjetas del diseño */
[data-testid="stMain"] [data-testid="stMarkdownContainer"] p, [data-testid="stMain"] [data-testid="stMarkdownContainer"] li { font-size: 14.5px; line-height: 1.6; }
[data-testid="stMain"] [data-testid="stCaptionContainer"] p { font-size: 13px; line-height: 1.5; }

/* ---------- tarjetas ---------- */
[class*="st-key-mt-card-"] {
  background: #fff; border: 1px solid var(--mt-linea-tarjeta) !important; border-radius: var(--mt-radio-l) !important;
  padding: 18px 20px !important; box-shadow: var(--mt-sombra); gap: .7rem;
}
.mt-card-h { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.mt-card-h h2 { margin: 0 !important; padding: 0 !important; font-size: 16px !important; font-weight: 700 !important; letter-spacing: -.01em; color: var(--mt-tinta); }
.mt-card-h span { font-size: 13px; color: var(--mt-tinta-suave); }
/* vidrio de la Fase 2: ahora es la misma tarjeta blanca */
.mt-glass, div[data-testid="stForm"] {
  background: #fff; border: var(--mt-borde); box-shadow: var(--mt-sombra); border-radius: var(--mt-radio-l);
}
div[data-testid="stForm"] { padding: 1.2rem 1.3rem 1.1rem; }
[class*="st-key-mt-card-"] div[data-testid="stForm"] { background: var(--mt-rosa-palido); border-color: var(--mt-linea); box-shadow: none; }

.mt-archivo { border: 2px dashed var(--mt-vino); border-radius: 16px; padding: 14px 16px; background: var(--mt-rosa-palido); }
.mt-archivo b { display: block; font-size: 15px; color: var(--mt-tinta); }
/* cifras grandes: 10.000 → 9.874 */
.mt-cifra { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.mt-big { font-size: 34px; line-height: 1.1; font-weight: 700; letter-spacing: -.8px; color: var(--mt-malva); font-variant-numeric: tabular-nums; }
.mt-big.ok { color: var(--mt-verde); }
.mt-filas { display: flex; flex-direction: column; gap: 9px; }
.mt-fila { display: flex; justify-content: space-between; align-items: baseline; gap: 16px; font-size: 14px; font-weight: 500; }
.mt-fila b { color: var(--mt-vino); font-variant-numeric: tabular-nums; white-space: nowrap; }
.mt-fila small { display: block; font-size: 12px; font-weight: 400; color: var(--mt-tinta-suave); }
/* diagramas: cuando cambian los datos, el mismo elemento se transforma (transiciones), sin repetir la entrada */
.mt-barras i { transition: height .75s var(--mt-curva); }
.mt-part i { transition: flex-grow .75s var(--mt-curva); }
.mt-tr i, .mt-fill { transition: width .75s var(--mt-curva); }
.mt-ring .arc { transition: stroke-dashoffset .75s var(--mt-curva); }
.mt-count { transition: --mt-num .75s var(--mt-curva); }
/* cifra contando: el número que dibuja el motor va encima del texto (que no se toca) */
[data-mt-contando] { position: relative; color: transparent !important; }
[data-mt-contando]::after { content: attr(data-mt-txt); position: absolute; left: 0; top: 0; color: var(--mt-c); white-space: nowrap; }
.mt-matriz .c { animation: mt-celda .5s var(--mt-curva) calc(var(--i, 0) * 40ms) both; transition: background-color .6s var(--mt-curva), color .6s var(--mt-curva); }
@keyframes mt-celda { from { opacity: 0; transform: scale(.82); } to { opacity: 1; transform: none; } }
/* barras de escalabilidad */
.mt-barras { display: flex; align-items: flex-end; gap: 18px; height: 132px; }
.mt-barras > div { flex: 1; text-align: center; min-width: 0; }
.mt-barras i { display: block; border-radius: 10px 10px 4px 4px; background: linear-gradient(180deg, #E8C6D8, var(--mt-rosa-barra));
  transform-origin: bottom; animation: mt-subir var(--mt-entrada-larga) var(--mt-curva) calc(.05s + var(--i, 0) * 60ms) both; }
.mt-barras span { display: block; margin-top: 4px; font-size: 12px; color: var(--mt-tinta-suave); white-space: nowrap; }
/* barra y filas de la partición */
.mt-part { display: flex; height: 22px; border-radius: 11px; overflow: hidden; background: var(--mt-rosa-suave);
  transform-origin: left; animation: mt-crecer var(--mt-entrada-larga) var(--mt-curva) .1s both; }
.mt-part i { display: block; min-width: 2px; }
.mt-sr { display: flex; justify-content: space-between; font-size: 14px; font-weight: 500; margin-bottom: 7px; }
.mt-sr b { color: var(--mt-vino); font-variant-numeric: tabular-nums; }
.mt-tr { height: 8px; border-radius: 4px; background: #F3E8EE; overflow: hidden; }
.mt-tr i { display: block; height: 8px; border-radius: 4px; background: var(--mt-rosa-medio); transform-origin: left;
  animation: mt-crecer var(--mt-entrada-larga) var(--mt-curva) calc(.1s + var(--i, 0) * 70ms) both; }
/* matriz en cuadros */
.mt-matriz { display: grid; grid-template-columns: 92px repeat(3, 1fr); gap: 6px; text-align: center; font-size: 13px; font-weight: 600; }
.mt-matriz .f { align-self: center; text-align: left; }
.mt-matriz .c { padding: 14px 0; border-radius: 12px; font-size: 18px; color: var(--mt-tinta); font-variant-numeric: tabular-nums; background: #F6F1F4; }
.mt-matriz .c.e { background: #F6E3EC; }
.mt-matriz .c.d { background: #DDAEC5; }
/* indicadores (KPI) */
.mt-kpi-t { font-size: 13px; font-weight: 600; color: var(--mt-tinta-suave); }
.mt-kpi-s { font-size: 13px; font-weight: 500; color: var(--mt-tinta); line-height: 1.4; }
[class*="st-key-mt-card-kpi"] { gap: .6rem; }
[class*="st-key-mt-card-kpi"] [data-testid="stPopoverButton"] {
  min-height: 26px !important; padding: 2px 10px !important; border: 1px solid var(--mt-linea) !important; background: #fff !important;
  color: var(--mt-tinta-suave) !important; font-size: 12px !important; font-weight: 600 !important; box-shadow: none !important;
}
/* viñetas de «Cómo leerlo» */
.mt-puntos { display: flex; flex-direction: column; gap: 8px; font-size: 14px; font-weight: 500; line-height: 1.45; }
.mt-puntos div { display: flex; gap: 10px; }
.mt-puntos div::before { content: ""; flex: none; width: 6px; height: 6px; margin-top: 7px; border-radius: 3px; background: var(--mt-vino); }
.mt-nota-warn { background: var(--mt-warn-fondo); color: var(--mt-warn-tinta); border: 1px solid var(--mt-warn-linea);
  border-radius: 14px; padding: 8px 12px; font-size: 12px; font-weight: 600; line-height: 1.4; }

/* st.metric como indicador */
[data-testid="stMetric"] {
  background: #fff; border: 1px solid var(--mt-linea-tarjeta); border-radius: var(--mt-radio-l); padding: 14px 18px; box-shadow: var(--mt-sombra);
}
[class*="st-key-mt-card-"] [data-testid="stMetric"] { background: var(--mt-rosa-palido); border-color: var(--mt-linea); box-shadow: none; border-radius: var(--mt-radio-m); }
[data-testid="stMetricLabel"] p { font-size: 13px !important; font-weight: 600 !important; color: var(--mt-tinta-suave) !important; }
[data-testid="stMetricValue"], [data-testid="stMetricValue"] p { font-size: 30px !important; font-weight: 700 !important; letter-spacing: -.7px; color: var(--mt-malva); font-variant-numeric: tabular-nums; line-height: 1.2 !important; }

/* ---------- registro de ejecución (barra inferior) ---------- */
.st-key-mt-registro { position: sticky; bottom: 12px; z-index: 40; margin-top: 4px; }
.mt-lg {
  display: flex; gap: 18px; align-items: center; background: #fff; border: 1px solid var(--mt-linea-tarjeta); border-radius: 14px;
  padding: 10px 16px; font-size: 12px; font-weight: 500; color: var(--mt-tinta-suave); box-shadow: var(--mt-sombra-alta);
  white-space: nowrap; overflow: hidden;
}
.mt-lg > span { overflow: hidden; text-overflow: ellipsis; }
.mt-lg b { color: var(--mt-tinta); font-variant-numeric: tabular-nums; }
.mt-lg .t { flex: none; color: var(--mt-vino); font-weight: 700; }

/* ---------- títulos de sección (triaje de la Fase 2) ---------- */
.mt-section { display: flex; align-items: baseline; gap: .6rem; margin: 1.4rem 0 .6rem; }
.mt-section .num { font-size: .72rem; font-weight: 700; color: #fff; background: var(--mt-vino); border-radius: 8px; padding: .14rem .45rem; letter-spacing: .02em; }
.mt-section h3 { margin: 0 !important; padding: 0 !important; font-size: 1.2rem !important; font-weight: 700 !important; }
.mt-group { font-size: 11px; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase; color: var(--mt-tinta-tenue); margin: .2rem 0 .4rem; }
.mt-hero { display: grid; grid-template-columns: auto 1fr auto; gap: 1.4rem; align-items: center; padding: 1.3rem 1.6rem; margin-bottom: 1.2rem; }
.mt-logo { width: 68px; height: 68px; border-radius: var(--mt-radio-m); display: grid; place-items: center; background: var(--mt-rosa-palido); border: 1px solid var(--mt-linea); }
.mt-title { font-size: 2.1rem !important; line-height: 1.05 !important; font-weight: 700 !important; letter-spacing: -.03em !important;
  margin: .15rem 0 .25rem !important; padding: 0 !important; color: var(--mt-vino) !important; }
.mt-kpis { display: grid; grid-template-columns: repeat(3, minmax(88px, 1fr)); gap: .6rem; }
.mt-kpi { padding: .7rem .85rem; border-radius: var(--mt-radio-m); background: var(--mt-rosa-palido); border: 1px solid var(--mt-linea); text-align: left; }
.mt-kpi b { display: block; font-size: 1.35rem; font-weight: 700; letter-spacing: -.02em; color: var(--mt-malva); font-variant-numeric: tabular-nums; }
.mt-kpi span { font-size: .7rem; color: var(--mt-tinta-suave); letter-spacing: .01em; }

/* ---------- controles ---------- */
[data-testid="stWidgetLabel"] p { font-size: 13px !important; font-weight: 500 !important; color: var(--mt-tinta-suave) !important; }
[data-testid="stNumberInputContainer"], [data-testid="stSelectbox"] div[role="group"], [data-testid="stTextInputRootElement"],
[data-testid="stMultiSelect"] div[role="group"] {
  border-radius: 12px !important; background: #fff !important; border: 1px solid var(--mt-linea) !important; box-shadow: none;
  transition: box-shadow var(--mt-rapida) var(--mt-curva), border-color var(--mt-rapida) var(--mt-curva);
}
[data-testid="stNumberInputContainer"]:hover, [data-testid="stSelectbox"] div[role="group"]:hover,
[data-testid="stTextInputRootElement"]:hover { border-color: var(--mt-rosa-medio) !important; }
[data-testid="stNumberInputContainer"]:focus-within, [data-testid="stSelectbox"] div[role="group"]:focus-within,
[data-testid="stTextInputRootElement"]:focus-within {
  border-color: var(--mt-vino) !important; box-shadow: 0 0 0 4px rgba(123, 45, 91, .12) !important;
}
[data-testid="stNumberInputContainer"] input, [data-testid="stSelectbox"] input, [data-testid="stTextInputRootElement"] input { background: transparent !important; }
input { font-variant-numeric: tabular-nums; }
[data-testid="stNumberInputStepDown"], [data-testid="stNumberInputStepUp"] {
  border-radius: 10px; background: transparent !important;
  transition: transform var(--mt-rapida) var(--mt-curva), background-color var(--mt-rapida) var(--mt-curva);
}
[data-testid="stNumberInputStepDown"]:hover, [data-testid="stNumberInputStepUp"]:hover { background: var(--mt-rosa-suave) !important; }
[data-testid="stNumberInputStepDown"]:active, [data-testid="stNumberInputStepUp"]:active { transform: scale(.88); }

/* radio horizontal como control segmentado */
[data-testid="stRadioGroup"][aria-orientation="horizontal"] {
  display: inline-flex !important; flex-wrap: wrap; gap: 2px !important; padding: 3px; border-radius: 12px; background: var(--mt-rosa-suave);
}
[data-testid="stRadioGroup"] > div { margin: 0 !important; }
[data-testid="stRadioGroup"][aria-orientation="horizontal"] [data-testid="stRadioOption"] {
  margin: 0 !important; padding: 7px 14px !important; border-radius: 9px; cursor: pointer;
  transition: background-color var(--mt-rapida) var(--mt-curva), box-shadow var(--mt-rapida) var(--mt-curva),
              transform var(--mt-rapida) var(--mt-curva);
}
[data-testid="stRadioGroup"][aria-orientation="horizontal"] [data-testid="stRadioOption"] > div > div:first-child { display: none !important; }
[data-testid="stRadioGroup"][aria-orientation="horizontal"] [data-testid="stRadioOption"] p { font-size: 13px !important; font-weight: 600; color: var(--mt-tinta-suave); white-space: nowrap; }
[data-testid="stRadioGroup"][aria-orientation="horizontal"] [data-testid="stRadioOption"]:has(input:checked) { background: #fff; box-shadow: 0 1px 5px rgba(0, 0, 0, .13); }
[data-testid="stRadioGroup"][aria-orientation="horizontal"] [data-testid="stRadioOption"]:has(input:checked) p { color: var(--mt-vino); }
[data-testid="stRadioGroup"][aria-orientation="horizontal"] [data-testid="stRadioOption"]:has(input:focus-visible) { outline: 2px solid var(--mt-vino); outline-offset: 1px; }
[data-testid="stRadioGroup"][aria-orientation="horizontal"] [data-testid="stRadioOption"]:active { transform: scale(.97); }

/* botones: primario relleno, secundario con borde, terciario de solo texto */
button[data-testid^="stBaseButton-"], [data-testid="stPopoverButton"] {
  border-radius: 999px !important; font-weight: 600 !important; letter-spacing: -.005em;
  transition: transform .3s cubic-bezier(.2, .9, .3, 1.4), box-shadow var(--mt-rapida) var(--mt-curva),
              background-color var(--mt-rapida) var(--mt-curva), border-color var(--mt-rapida) var(--mt-curva) !important;
}
button[data-testid^="stBaseButton-primary"] {
  min-height: 44px; padding: 0 24px !important; border: 0 !important; background: var(--mt-vino) !important; color: #fff !important;
  box-shadow: 0 2px 6px rgba(123, 45, 91, .25);
}
button[data-testid^="stBaseButton-secondary"], [data-testid="stPopoverButton"] {
  min-height: 42px; padding: 0 18px !important; border: 2px solid var(--mt-vino) !important; background: transparent !important;
  color: var(--mt-vino) !important;
}
button[data-testid^="stBaseButton-tertiary"] { color: var(--mt-vino) !important; }
button[data-testid^="stBaseButton-primary"] p, button[data-testid^="stBaseButton-secondary"] p { font-size: 14px; font-weight: 600; }
button[data-testid^="stBaseButton-primary"]:hover, button[data-testid^="stBaseButton-secondary"]:hover { transform: translateY(-2px); }
button[data-testid^="stBaseButton-primary"]:hover { background: var(--mt-vino-oscuro) !important; box-shadow: 0 8px 18px rgba(123, 45, 91, .28); }
button[data-testid^="stBaseButton-secondary"]:hover { background: var(--mt-rosa-palido) !important; }
button[data-testid^="stBaseButton-"]:active { transform: scale(.96) !important; }
button[data-testid^="stBaseButton-"]:focus-visible, [data-testid="stPopoverButton"]:focus-visible { outline: 2px solid var(--mt-vino); outline-offset: 2px; }
button[data-testid^="stBaseButton-"]:disabled {
  opacity: .45; transform: none !important; box-shadow: none !important; cursor: not-allowed;
}
/* los botones de los campos numéricos y del cargador de archivos no son pastillas de acción */
[data-testid="stNumberInputContainer"] button, [data-testid="stFileUploaderDropzone"] button[data-testid^="stBaseButton-"] {
  min-height: 0; border-width: 1.5px !important;
}
[data-testid="stFileUploaderDropzone"] {
  border: 2px dashed var(--mt-vino); border-radius: 16px; background: var(--mt-rosa-palido);
}
[data-testid="stFileUploaderDropzone"] button[data-testid^="stBaseButton-"] { min-height: 36px; padding: 0 14px !important; }

div[data-testid="stExpander"] details {
  background: #fff; border: 1px solid var(--mt-linea-tarjeta) !important; border-radius: var(--mt-radio-m) !important; box-shadow: none;
}
div[data-testid="stExpander"] summary { font-weight: 600; color: var(--mt-tinta); }
div[data-testid="stExpander"] summary:hover { color: var(--mt-vino); }
[data-testid="stDataFrame"] { border: 1px solid var(--mt-linea-tarjeta); border-radius: var(--mt-radio-m); overflow: hidden; }
[data-testid="stCode"] pre, [data-testid="stJson"] { border-radius: var(--mt-radio-m) !important; }

/* avisos de Streamlit con la paleta del sistema */
[data-testid="stAlertContainer"] { border-radius: var(--mt-radio-m) !important; border: 1px solid transparent; padding: 10px 14px; }
[data-testid="stAlertContainer"] p { font-size: 13.5px; line-height: 1.5; }
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) { background: var(--mt-info-fondo); border-color: var(--mt-info-linea); }
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) * { color: var(--mt-info-tinta); }
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) { background: var(--mt-warn-fondo); border-color: var(--mt-warn-linea); }
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) * { color: var(--mt-warn-tinta); }
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) { background: var(--mt-ok-fondo); border-color: var(--mt-ok-linea); }
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) * { color: var(--mt-ok-tinta); }
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) { background: var(--mt-error-fondo); border-color: var(--mt-error-linea); }
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) * { color: var(--mt-error-tinta); }

/* ---------- indicadores de carga: spinner discreto ---------- */
@keyframes mt-girar { to { transform: rotate(360deg); } }
[data-testid="stStatusWidgetRunningIcon"], [data-testid="stStatusWidgetRunningManIcon"] { display: none !important; }
[data-testid="stStatusWidget"]:has([data-testid="stStatusWidgetRunningIcon"])::before {
  content: ""; width: 14px; height: 14px; border-radius: 50%; margin-right: .5rem;
  border: 2px solid rgba(123, 45, 91, .2); border-top-color: var(--mt-vino);
  animation: mt-girar .8s linear infinite;
}
[data-testid="stSpinner"] { color: var(--mt-tinta-suave); font-size: .85rem; }
[data-testid="stSpinner"] i, [data-testid="stSpinner"] svg { color: var(--mt-vino) !important; border-color: rgba(123, 45, 91, .2) !important;
  border-top-color: var(--mt-vino) !important; }

/* ---------- avisos flotantes: emergen desde abajo y se retiran solos ---------- */
@keyframes mt-emerger { from { opacity: 0; transform: translateY(24px) scale(.98); } to { opacity: 1; transform: none; } }
/* Streamlit 1.66 ya los ubica abajo; aquí se les da ancho, material y la entrada desde abajo */
[data-testid="stToast"] {
  width: min(440px, calc(100vw - 2rem)) !important; max-width: none !important;
  background: #fff !important; border: var(--mt-borde) !important; border-radius: var(--mt-radio-m) !important;
  box-shadow: var(--mt-sombra-alta) !important; color: var(--mt-tinta) !important;
  animation: mt-emerger var(--mt-entrada) var(--mt-curva) both;
}

/* ---------- tarjeta de resultado (triaje de la Fase 2) ---------- */
.mt-result {
  position: relative; overflow: hidden; border-radius: var(--mt-radio-l); padding: 1.7rem 1.9rem;
  display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 1rem;
  border: 1px solid rgba(255, 255, 255, .6);
  box-shadow: var(--mt-sombra-alta), inset 0 1px 0 rgba(255, 255, 255, .6);
}
.mt-result::before {
  content: ""; position: absolute; inset: 0; pointer-events: none;
  background: radial-gradient(600px 220px at 85% -20%, rgba(255, 255, 255, .55), transparent 60%);
}
.mt-result .eyebrow { font-size: .74rem; font-weight: 600; letter-spacing: .1em; text-transform: uppercase; opacity: .8; }
.mt-result .cat { font-size: 2.5rem; font-weight: 700; letter-spacing: -.035em; line-height: 1.05; margin: .2rem 0; }
.mt-result .sub { font-size: 1rem; opacity: .9; }
.mt-badge {
  position: relative; display: inline-flex; align-items: center; gap: .45rem; padding: .5rem .95rem; border-radius: 999px;
  background: rgba(255, 255, 255, .55); border: 1px solid rgba(255, 255, 255, .8);
  -webkit-backdrop-filter: blur(12px); backdrop-filter: blur(12px); font-size: .82rem; font-weight: 600; white-space: nowrap;
}
.mt-icon { position: relative; width: 54px; height: 54px; border-radius: 50%; display: grid; place-items: center;
  background: rgba(255, 255, 255, .5); border: 1px solid rgba(255, 255, 255, .85); margin-bottom: .6rem; }
.mt-result.alto .mt-icon::after {
  content: ""; position: absolute; inset: -6px; border-radius: 50%; border: 2px solid currentColor; opacity: 0;
  animation: mt-pulso 1.6s var(--mt-curva) .4s 2;
}
@keyframes mt-pulso { from { transform: scale(.9); opacity: .5; } to { transform: scale(1.5); opacity: 0; } }

/* ---------- avisos en la página ---------- */
.mt-note { padding: 1.05rem 1.25rem; margin-top: .9rem; border-radius: var(--mt-radio-m); }
.mt-note h4 { margin: 0 0 .5rem !important; padding: 0 !important; font-size: .98rem !important; font-weight: 650 !important; }
.mt-note p { margin: .45rem 0 0; color: var(--mt-tinta-suave); font-size: .88rem; }
.mt-note.rule { background: linear-gradient(135deg, rgba(240, 153, 171, .34), rgba(240, 153, 171, .16)) !important; border-color: rgba(217, 102, 127, .25) !important; }
.mt-note.rule h4 { color: #6B1832 !important; }
.mt-note.warn { background: linear-gradient(135deg, rgba(242, 232, 143, .48), rgba(242, 232, 143, .22)) !important; border-color: rgba(205, 190, 69, .3) !important; }
.mt-note.warn h4 { color: #5A4F0E !important; }
.mt-note.info { background: var(--mt-info-fondo) !important; border-color: var(--mt-info-linea) !important; }
.mt-note.info p { color: var(--mt-info-tinta) !important; }
.mt-note.ok { background: linear-gradient(135deg, rgba(182, 227, 154, .45), rgba(182, 227, 154, .2)) !important; border-color: rgba(125, 187, 89, .3) !important; }
.mt-chips { display: flex; flex-wrap: wrap; gap: .45rem; }
.mt-chip {
  display: inline-flex; align-items: center; gap: .4rem; padding: .38rem .8rem; border-radius: 12px; font-size: .84rem; font-weight: 500;
  background: rgba(255, 255, 255, .6); color: #6B1832; border: 1px solid rgba(217, 102, 127, .3);
}

/* ---------- gráficas del triaje ---------- */
.mt-panel { padding: 1.35rem 1.5rem; border-radius: var(--mt-radio-l); margin-top: .9rem; }
.mt-panel-title { font-size: 11px; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase; color: var(--mt-tinta-tenue); margin-bottom: .9rem; }
.mt-chart { display: grid; grid-template-columns: 150px 1fr; gap: 1.6rem; align-items: center; }
.mt-ring { position: relative; width: 150px; height: 150px; }
.mt-ring svg { transform: rotate(-90deg); }
.mt-ring .arc { animation: mt-anillo var(--mt-entrada-larga) var(--mt-curva) .25s both; }
@keyframes mt-anillo { from { stroke-dashoffset: 339.29; } }
.mt-ring .center { position: absolute; inset: 0; display: grid; place-content: center; text-align: center; }
.mt-count { font-size: 2rem; font-weight: 700; letter-spacing: -.03em; color: var(--mt-tinta); font-variant-numeric: tabular-nums;
  animation: mt-contar var(--mt-entrada-larga) var(--mt-curva) .25s both; counter-reset: mt var(--mt-num); }
.mt-count::after { content: counter(mt) "%"; }
@keyframes mt-contar { from { --mt-num: 0; } }
.mt-ring .center small { font-size: .72rem; color: var(--mt-tinta-suave); }
.mt-bar-row { display: grid; grid-template-columns: 110px 1fr 54px; align-items: center; gap: .8rem; margin: .55rem 0; }
.mt-bar-row .lbl { font-size: .86rem; font-weight: 500; }
.mt-track { height: 12px; border-radius: 999px; background: var(--mt-rosa-suave); overflow: hidden; }
/* la barra crece con transform (no con width): más fluido */
.mt-fill { height: 100%; border-radius: 999px; transform-origin: left center; box-shadow: inset 0 1px 0 rgba(255, 255, 255, .5);
  animation: mt-crecer var(--mt-entrada-larga) var(--mt-curva) both; }
.mt-bar-row .val { text-align: right; font-size: .86rem; font-weight: 600; font-variant-numeric: tabular-nums; }
.mt-trace { display: grid; grid-template-columns: repeat(3, 1fr); gap: .6rem; margin-top: 1rem; }
.mt-trace div { padding: .7rem .85rem; border-radius: var(--mt-radio-m); background: var(--mt-rosa-palido); border: 1px solid var(--mt-linea); }
.mt-trace span { display: block; font-size: .7rem; color: var(--mt-tinta-suave); letter-spacing: .02em; }
.mt-trace b { font-size: .92rem; font-weight: 600; }

/* ---------- protocolo ---------- */
.mt-steps { display: grid; gap: .55rem; }
.mt-step { display: grid; grid-template-columns: 34px 1fr; gap: .85rem; align-items: start; padding: .9rem 1.1rem; border-radius: var(--mt-radio-m); }
.mt-step:hover { transform: translateY(-1px); box-shadow: var(--mt-sombra-alta); }
.mt-step .n { width: 30px; height: 30px; border-radius: 10px; display: grid; place-items: center; font-weight: 700; font-size: .85rem; }
.mt-step p { margin: .2rem 0 0; font-size: .93rem; line-height: 1.5; }
.mt-foot { margin-top: .8rem; font-size: .78rem; color: var(--mt-tinta-suave); }

/* ---------- adaptación ---------- */
@media (max-width: 900px) {
  .block-container { padding-left: 1rem; padding-right: 1rem; }
  .mt-h1 { font-size: 24px; }
  .mt-lg { flex-wrap: wrap; white-space: normal; gap: 4px 14px; }
}
@media (max-width: 760px) {
  .mt-hero { grid-template-columns: auto 1fr; }
  .mt-kpis { grid-column: 1 / -1; }
  .mt-chart { grid-template-columns: 1fr; justify-items: center; }
  .mt-trace { grid-template-columns: 1fr; }
  .mt-result { grid-template-columns: 1fr; }
  .mt-matriz { grid-template-columns: 70px repeat(3, 1fr); }
}
/* Movimiento reducido: sin animaciones ni transiciones */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important; }
}
/* Transparencia reducida (p. ej. Windows con "Efectos de transparencia" desactivados): barra lateral opaca */
@media (prefers-reduced-transparency: reduce) {
  section[data-testid="stSidebar"] { background: #FCFBF8 !important; -webkit-backdrop-filter: none !important; backdrop-filter: none !important; }
}
</style>
"""


def estilos():
    return CSS


# Bienvenida. Antes la insertaba un iframe invisible, pero el iframe carga su propio documento después de que
# Streamlit pinta el resto de la página, así que el login asomaba una fracción de segundo antes del logo.
# Ahora es un componente v2 montado directamente en la página (sin iframe): app_demo.py lo envía SOLO en la
# primera ejecución y se detiene; cuando la capa ya cubre la pantalla, el componente avisa a Python
# ("montada") y recién entonces se dibuja la app, debajo del logo. Sin esperas por tiempo.
# Usa la misma curva que el resto de la página.
CSS_BIENVENIDA = """
.mt-splash {
  position: fixed; inset: 0; z-index: 1000000; display: grid; place-items: center;
  background: #F7F7F7;  /* mismo gris que el fondo del logo: no se nota el recuadro */
  animation: mt-splash-out .5s cubic-bezier(.32, .72, 0, 1) 2.5s forwards;
}
.mt-splash img {
  width: min(320px, 64vw); height: auto;
  animation: mt-logo-in .5s cubic-bezier(.32, .72, 0, 1) .15s both;
}
@keyframes mt-logo-in { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: none; } }
@keyframes mt-splash-out { to { opacity: 0; visibility: hidden; } }
@media (prefers-reduced-motion: reduce) {
  /* sin animaciones: el logo aparece fijo y la capa se retira a los 2,5 s (ver el script) */
  .mt-splash, .mt-splash img { animation: none !important; }
}
"""


JS_BIENVENIDA = f"""
export default function ({{ setTriggerValue }}) {{
  const doc = document;
  if (doc.getElementById("mt-splash")) return;  // ya está en pantalla: no volver a avisar
  const estilo = doc.createElement("style");
  estilo.textContent = `{CSS_BIENVENIDA}`;
  doc.head.appendChild(estilo);
  const capa = doc.createElement("div");
  capa.id = "mt-splash";
  capa.className = "mt-splash";
  capa.setAttribute("role", "img");
  capa.setAttribute("aria-label", "MATERNA");
  const logo = doc.createElement("img");
  logo.src = "./app/static/logo_materna.webp";
  logo.alt = "MATERNA";
  capa.appendChild(logo);
  doc.body.appendChild(capa);
  // "mt-revelado": el login entra en cuanto el logo empieza a desvanecerse (transición continua)
  const revelar = () => doc.body.classList.add("mt-revelado");
  const retirar = () => {{ revelar(); capa.remove(); estilo.remove(); }};
  capa.addEventListener("animationstart", (e) => {{ if (e.animationName === "mt-splash-out") revelar(); }});
  capa.addEventListener("animationend", (e) => {{ if (e.animationName === "mt-splash-out") retirar(); }});
  // con movimiento reducido no hay animación que termine: se retira a los 2,5 s
  const sinMovimiento = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  setTimeout(retirar, sinMovimiento ? 2500 : 4000);  // respaldo por si el navegador no emite animationend
  // La capa ya tapa la página: en el siguiente cuadro, Python puede dibujar la app debajo
  requestAnimationFrame(() => setTriggerValue("montada", true));
}}
"""

_BIENVENIDA = components.v2.component("materna_bienvenida", js=JS_BIENVENIDA, isolate_styles=False)


def bienvenida_montada():
    """Monta la capa de bienvenida. Devuelve True cuando ya cubre la pantalla (el logo lo sirve
    el propio servidor de Streamlit desde static/, con enableStaticServing: funciona sin internet)."""
    return bool(_BIENVENIDA(key="bienvenida", on_montada_change=lambda: None).montada)


def encabezado(modelo, pendientes, kpis):
    pills = (
        '<span class="mt-pill" style="--i:1"><i class="mt-dot"></i>Offline · inferencia local</span>'
        f'<span class="mt-pill" style="--i:2">{pendientes} registro(s) por sincronizar</span>'
        f'<span class="mt-pill" style="--i:3">Modelo: {html.escape(modelo)}</span>'
    )
    tarjetas = "".join(f'<div class="mt-kpi" style="--i:{i + 2}" data-mt="{_id(f"kpi{i}")}"><b>{_numeros(str(valor))}</b>'
                       f'<span>{nombre}</span></div>' for i, (nombre, valor) in enumerate(kpis))
    return _html(f"""
    <div class="mt-hero mt-glass" style="--i:0">
      <div class="mt-logo">{LOGO_ISOTIPO}</div>
      <div>
        <div class="mt-eyebrow">Alerta temprana materno-perinatal · La Guajira y Cesar</div>
        <h1 class="mt-title">MATERNA</h1>
        <p class="mt-sub">Clasificación del riesgo obstétrico en el punto de atención, incluso sin conexión.</p>
        <div class="mt-pills">{pills}</div>
      </div>
      <div class="mt-kpis">{tarjetas}</div>
    </div>""")


def titulo_seccion(numero, texto):
    return _html(f'<div class="mt-section"><span class="num">{numero}</span><h3>{html.escape(texto)}</h3></div>')


def grupo(texto):
    return f'<div class="mt-group">{html.escape(texto)}</div>'


def tarjeta_resultado(categoria, origen):
    e = ESTILO_CATEGORIA[categoria]
    icono = ICONOS[e["clase"]]
    insignia = "Regla clínica GPC Minsalud" if origen == "regla_clinica" else "Modelo de aprendizaje automático"
    return _html(f"""
    <div class="mt-result {e['clase']}" style="background:{e['fondo']};color:{e['tinta']};--i:0">
      <div>
        <div class="mt-icon" style="--i:1">{icono}</div>
        <div class="eyebrow">Categoría final</div>
        <div class="cat">{e['titulo']}</div>
        <div class="sub">{e['sub']}</div>
      </div>
      <div class="mt-badge" style="--i:2">{insignia}</div>
    </div>""")


def aviso_regla(alertas, categoria_modelo):
    chips = "".join(
        f'<span class="mt-chip" style="--i:{i + 2}">{html.escape(a)}</span>'
        for i, a in enumerate(alertas)
    )
    return _html(f"""
    <div class="mt-note mt-glass rule" style="--i:1">
      <h4>Regla de seguridad clínica activada</h4>
      <div class="mt-chips">{chips}</div>
      <p>Por sí solo, el modelo estadístico habría clasificado <b>{html.escape(categoria_modelo)}</b>.
      La regla prevalece sobre el modelo.</p>
    </div>""")


def aviso(texto, tipo="info", titulo=None, orden=1):
    """tipo: 'info' (ciruela), 'warn' (amarillo), 'rule' (rojo) u 'ok' (verde)."""
    cabecera = f"<h4>{html.escape(titulo)}</h4>" if titulo else ""
    return _html(f'<div class="mt-note mt-glass {tipo}" style="--i:{orden}">{cabecera}<p style="margin:0">{texto}</p></div>')


def panel_probabilidades(probabilidades, categoria_modelo, nombre_modelo, origen):
    circunferencia = 339.29  # 2·π·54
    p_top = probabilidades[categoria_modelo]
    color_top = ESTILO_CATEGORIA[categoria_modelo]["acento"]
    barras = "".join(
        f"""<div class="mt-bar-row">
        <span class="lbl">{ESTILO_CATEGORIA[c]['titulo']}</span>
        <div class="mt-track"><div class="mt-fill" data-mt-dim="width" style="width:{p * 100:.1f}%;background:{ESTILO_CATEGORIA[c]['barra']};animation-delay:{0.1 + 0.07 * i:.2f}s"></div></div>
        <span class="val">{_numeros(_pct(p))}</span></div>"""
        for i, (c, p) in enumerate(probabilidades.items())
    )
    origen_txt = "Regla clínica" if origen == "regla_clinica" else "Modelo ML"
    return _html(f"""
    <div class="mt-panel mt-glass" style="--i:3" data-mt="{_id('probabilidades')}">
      <div class="mt-panel-title">Inferencia del modelo · {html.escape(nombre_modelo)}</div>
      <div class="mt-chart">
        <div class="mt-ring">
          <svg width="150" height="150" viewBox="0 0 150 150">
            <circle cx="75" cy="75" r="54" fill="none" stroke="rgba(125,47,95,.08)" stroke-width="14"/>
            <circle class="arc" cx="75" cy="75" r="54" fill="none" stroke="{color_top}" stroke-width="14" stroke-linecap="round"
              stroke-dasharray="{circunferencia}" data-mt-dim="stroke-dashoffset" style="stroke-dashoffset:{circunferencia * (1 - p_top):.2f}"/>
          </svg>
          <div class="center"><span class="mt-count" data-mt-dim="--mt-num" style="--mt-num:{round(p_top * 100)}"></span>
          <small>{ESTILO_CATEGORIA[categoria_modelo]['titulo']}</small></div>
        </div>
        <div>{barras}</div>
      </div>
      <div class="mt-trace">
        <div style="--i:5"><span>Origen de la decisión</span><b>{origen_txt}</b></div>
        <div style="--i:6"><span>Predicción del modelo</span><b>{html.escape(categoria_modelo)}</b></div>
        <div style="--i:7"><span>Sobreescritura por regla</span><b>{'Sí' if origen == 'regla_clinica' else 'No'}</b></div>
      </div>
    </div>""")


def protocolo(categoria, pasos):
    e = ESTILO_CATEGORIA[categoria]
    filas = "".join(
        f'<div class="mt-step mt-glass" style="--i:{i}">'
        f'<span class="n" style="background:{e["fondo"]};color:{e["tinta"]};--i:{i}">{i}</span><p>{html.escape(p)}</p></div>'
        for i, p in enumerate(pasos, 1)
    )
    return _html(f"""
    <div class="mt-steps">{filas}</div>
    <div class="mt-foot">Texto orientativo para la demostración académica: debe validarse con un asesor clínico y con la red
    de referencia de cada ESE/IPS antes de cualquier uso en campo.</div>""")


# ---------------------------------------------------------------- consola de la Fase 3
def login_marca():
    """Panel izquierdo del inicio de sesión: isotipo en blanco, mensaje de la marca y arcos decorativos."""
    arcos = "".join(f'<circle cx="-40" cy="660" r="{r}" fill="none" stroke="#FFFFFF" stroke-opacity="{o}" stroke-width="1.2"/>'
                    for r, o in [(260, .16), (340, .13), (420, .11), (500, .09), (580, .07), (660, .05)])
    return _html(f"""
    <div class="mt-marca">
      <svg class="mt-marca-arcos" viewBox="0 0 520 600" preserveAspectRatio="xMinYMax slice" aria-hidden="true">{arcos}</svg>
      <div class="mt-escalon" style="--paso:0"><img class="mt-marca-logo" src="./app/static/logo_isotipo.webp" alt="" aria-hidden="true"></div>
      <div class="mt-marca-texto mt-escalon" style="--paso:1">
        <div class="mt-marca-titulo" role="heading" aria-level="2">Alerta temprana para cuidar cada gestación.</div>
        <p>Laboratorio auditable del modelo que clasifica el riesgo obstétrico en La Guajira y Cesar,
        de la ingesta de datos a la generalización.</p>
      </div>
      <div class="mt-marca-pie mt-escalon" style="--paso:2">© 2026 MATERNA · Universidad Popular del Cesar</div>
    </div>""")


def login_encabezado(recuperando=False):
    """Panel derecho del inicio de sesión: logo MATERNA destacado y bienvenida (o el título de la recuperación)."""
    titulo, sub = (("Recuperar la contraseña", "Le enviaremos un código a su correo registrado para elegir una nueva.")
                   if recuperando else ("Le damos la bienvenida", "Módulo 1 · Laboratorio de ML. Inicie sesión para continuar."))
    return _html(f"""
    <div class="mt-acceso-logo mt-escalon{' mt-compacto' if recuperando else ''}" style="--paso:1">
      <img src="./app/static/logo_isotipo.webp" alt="" aria-hidden="true"><span>MATERNA</span>
    </div>
    <div class="mt-escalon" style="--paso:2">
      <div class="mt-acceso-titulo" role="heading" aria-level="1">{titulo}</div>
      <p class="mt-acceso-sub">{sub}</p>
    </div>""")


# ---------------------------------------------------------------- animación de los diagramas HTML
# Cada diagrama (barras, partición, matrices, cifras, panel de probabilidades) lleva `data-mt="<id estable>"`.
#   - ENTRADA: al abrir la fase el diagrama es nuevo en la página: sus animaciones CSS lo construyen (barras que
#     crecen escalonadas, celdas que se rellenan una a una) y el motor hace contar sus cifras desde 0.
#   - TRANSFORMACIÓN: si los datos cambian por una interacción, Streamlit (React) actualiza el MISMO elemento en
#     su lugar: las medidas cambian con transiciones CSS (no se repite la entrada) y el motor cuenta cada cifra
#     desde su valor anterior (atributo `data-mt-num`).
#   - Una ejecución sin cambios no toca el DOM: no se anima nada.
# Con «reducir movimiento» del sistema no hay animaciones, transiciones ni conteos.
_ANIM = {"prefijo": "mt", "n": 0}


def contexto_animacion(prefijo):
    """Llamar al empezar a dibujar una fase o página: los ids de sus diagramas no chocan con los de otra fase."""
    _ANIM["prefijo"], _ANIM["n"] = str(prefijo), 0


def _id(nombre, id_=None):
    if id_:
        return f'{_ANIM["prefijo"]}-{id_}'
    _ANIM["n"] += 1
    return f'{_ANIM["prefijo"]}-{nombre}-{_ANIM["n"]}'


def _numeros(texto):
    """Envuelve las cifras del texto ya escapado («0,963», «1.200», «12,7 %») para que cuenten hasta su valor."""
    def envolver(m):
        crudo = m.group(0)
        decimales = len(crudo.split(",")[1]) if "," in crudo else 0
        valor = float(crudo.replace(".", "").replace(",", "."))
        miles_ = "1" if "." in crudo or (decimales == 0 and abs(valor) >= 1000) else "0"
        return f'<span data-mt-num="{valor}" data-mt-dec="{decimales}" data-mt-miles="{miles_}">{crudo}</span>'
    return re.sub(r"(?<![\w.,])\d{1,3}(?:\.\d{3})+(?:,\d+)?(?![\w])|(?<![\w.,])\d+(?:,\d+)?(?![\w.])", envolver, texto)


JS_MOTOR = r"""
function etiquetaDebug(activa) {
  let d = document.getElementById("mt-debug-movimiento");
  if (!activa) { if (d) d.remove(); return; }
  if (!d) {
    d = document.createElement("div");
    d.id = "mt-debug-movimiento";
    d.style.cssText = "position:fixed;right:16px;bottom:16px;z-index:100000;font:600 12px/1.4 system-ui;background:#FFF7D6;" +
                      "color:#5C4400;border:1px solid #E7CF77;border-radius:8px;padding:6px 10px;box-shadow:0 4px 14px rgba(0,0,0,.08)";
    document.body.appendChild(d);
    window.matchMedia("(prefers-reduced-motion: reduce)").addEventListener("change", () => etiquetaDebug(true));
  }
  const reducir = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  d.textContent = `Modo debug · prefers-reduced-motion: ${reducir ? "reduce (animaciones DESACTIVADAS)" : "no-preference (animaciones activas)"}`;
}
export default function ({ data }) {
  etiquetaDebug(!!(data && data.debug));
  if (window.__mtMotor) return;
  window.__mtMotor = true;
  const DUR = 750;
  const quieto = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const formato = (v, e) => {
    const dec = +e.dataset.mtDec || 0;
    let [ent, frac] = Math.abs(v).toFixed(dec).split(".");
    if (e.dataset.mtMiles === "1") ent = ent.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    return (v < 0 ? "−" : "") + ent + (frac ? "," + frac : "");
  };
  const suave = (t) => 1 - Math.pow(1 - t, 3);
  // Cuenta sin tocar el texto que maneja React: lo dibuja encima (::after) mientras dura el conteo.
  function contar(e, desde, hasta, retardo) {
    if (quieto() || desde === hasta || isNaN(hasta)) return;
    const turno = (e.__mtTurno || 0) + 1;
    e.__mtTurno = turno;
    e.style.setProperty("--mt-c", getComputedStyle(e).color);
    e.setAttribute("data-mt-txt", formato(desde, e));
    e.setAttribute("data-mt-contando", "");
    const t0 = performance.now() + retardo;
    const paso = (t) => {
      if (e.__mtTurno !== turno) return;  // llegó un valor más nuevo: ese conteo manda
      const k = Math.min(1, Math.max(0, (t - t0) / DUR));
      e.setAttribute("data-mt-txt", formato(desde + (hasta - desde) * suave(k), e));
      if (k < 1) requestAnimationFrame(paso);
      else { e.removeAttribute("data-mt-contando"); e.removeAttribute("data-mt-txt"); }
    };
    requestAnimationFrame(paso);
  }
  const raices = (n) => n.nodeType !== 1 ? [] : [...(n.matches("[data-mt]") ? [n] : []), ...n.querySelectorAll("[data-mt]")];
  new MutationObserver((cambios) => {
    for (const c of cambios) {
      if (c.type === "attributes") {  // un dato cambió en el mismo elemento: contar desde el valor anterior
        const e = c.target, viejo = parseFloat(c.oldValue), nuevo = parseFloat(e.dataset.mtNum);
        if (!isNaN(viejo)) contar(e, viejo, nuevo, 0);
        continue;
      }
      for (const n of c.addedNodes) for (const r of raices(n))  // diagrama nuevo (se abrió la fase): contar desde 0
        r.querySelectorAll("[data-mt-num]").forEach((e) => contar(e, 0, parseFloat(e.dataset.mtNum), 100));
    }
  }).observe(document.body, { childList: true, subtree: true, attributes: true,
                              attributeFilter: ["data-mt-num"], attributeOldValue: true });
}
"""

_MOTOR = components.v2.component("materna_animaciones", js=JS_MOTOR, isolate_styles=False)


def motor_animaciones(debug=False):
    """Monta (una vez por página) el motor que anima la entrada y las transiciones de los diagramas HTML.
    Con `debug`, muestra en pantalla el valor de prefers-reduced-motion que detecta el navegador."""
    _MOTOR(key="mt-motor", data={"debug": bool(debug)}, height=0)


def miles(n):
    """10000 -> «10.000»."""
    return f"{int(n):,}".replace(",", ".")


def pills(etiquetas):
    """Etiquetas en pastilla. Cada una es un texto o un par (texto, tipo), con tipo '' | 'ok' | 'warn' | 'on'."""
    pares = [(e, "") if isinstance(e, str) else e for e in etiquetas]
    return "".join(f'<span class="mt-pill {tipo}">{html.escape(texto)}</span>' for texto, tipo in pares)


def encabezado_pagina(ruta, sesion, eyebrow, titulo, sub, chips=()):
    """Encabezado de cada pantalla: ruta de navegación y sesión, número de fase, título, subtítulo y etiquetas."""
    migas = " / ".join([html.escape(r) for r in ruta[:-1]] + [f"<b>{html.escape(ruta[-1])}</b>"])
    return _html(f"""
    <div class="mt-ruta"><span>{migas}</span><span class="mt-sesion"><i class="mt-dot"></i>{html.escape(sesion)}</span></div>
    <div class="mt-cab">
      <div>
        <div class="mt-eyebrow">{html.escape(eyebrow)}</div>
        <h1 class="mt-h1">{html.escape(titulo)}</h1>
        <p class="mt-sub">{html.escape(sub)}</p>
      </div>
      <div class="mt-pills">{pills(chips)}</div>
    </div>""")


def cabecera(eyebrow, titulo, sub, etiquetas=(), ruta=("MATERNA",)):
    """Encabezado de las páginas que no son fases del laboratorio (Variables 3280)."""
    migas = " / ".join(html.escape(r) for r in ruta)
    return _html(f"""
    <div class="mt-ruta"><span>{migas} / <b>{html.escape(titulo)}</b></span></div>
    <div class="mt-cab">
      <div>
        <div class="mt-eyebrow">{html.escape(eyebrow)}</div>
        <h1 class="mt-h1">{html.escape(titulo)}</h1>
        <p class="mt-sub">{html.escape(sub)}</p>
      </div>
      <div class="mt-pills">{pills(etiquetas)}</div>
    </div>""")


def menu_marca():
    """Marca del menú lateral: isotipo, MATERNA y el nombre del módulo."""
    return _html("""
    <div class="mt-menu-marca">
      <img src="./app/static/logo_isotipo.webp" alt="" aria-hidden="true">
      <div><b>MATERNA</b><span>Laboratorio ML</span></div>
    </div>""")


def menu_grupo(texto):
    return f'<div class="mt-gl">{html.escape(texto)}</div>'


def titulo_tarjeta(titulo, nota=None):
    extra = f"<span>{html.escape(nota)}</span>" if nota else ""
    return f'<div class="mt-card-h"><h2>{html.escape(titulo)}</h2>{extra}</div>'


def cifra(valor, despues=None, etiqueta="", id=None):
    """Cifra grande; con `despues`, el paso de una a otra (10.000 → 9.874 registros útiles)."""
    partes = f'<span class="mt-big">{_numeros(html.escape(str(valor)))}</span>'
    if despues is not None:
        partes += f'<span class="mt-mut" aria-hidden="true">→</span><span class="mt-big ok">{_numeros(html.escape(str(despues)))}</span>'
    return f'<div class="mt-cifra" data-mt="{_id("cifra", id)}">{partes}<span class="mt-mut">{html.escape(etiqueta)}</span></div>'


def archivo(nombre, detalle):
    """Recuadro punteado con el archivo o los datos crudos que están cargados."""
    return f'<div class="mt-archivo"><b>{html.escape(nombre)}</b><span class="mt-mut">{html.escape(detalle)}</span></div>'


def filas(pares):
    """Lista de concepto → valor. Cada elemento es (texto, valor) o (texto, valor, detalle)."""
    cuerpo = ""
    for texto, valor, *detalle in pares:
        nota = f"<small>{html.escape(detalle[0])}</small>" if detalle and detalle[0] else ""
        cuerpo += f'<div class="mt-fila"><span>{html.escape(texto)}{nota}</span><b>{html.escape(str(valor))}</b></div>'
    return f'<div class="mt-filas">{cuerpo}</div>'


def barras(elementos, id=None):
    """Barras verticales proporcionales. Cada elemento es (valor, texto que va debajo)."""
    maximo = max((v for v, _ in elementos), default=0) or 1
    cuerpo = "".join(f'<div><i data-mt-dim="height" style="height:{max(6, round(104 * v / maximo))}px;--i:{k}"></i>'
                     f'<span>{_numeros(html.escape(texto))}</span></div>' for k, (v, texto) in enumerate(elementos))
    return f'<div class="mt-barras" data-mt="{_id("barras", id)}">{cuerpo}</div>'


TONOS_PARTICION = ("#D3A0BB", "#E8C9D9", "#EADFE4")


def barra_particion(conjuntos, id=None):
    """Barra apilada y una fila por conjunto. Cada elemento es (nombre, porcentaje, registros)."""
    tramos = "".join(f'<i data-mt-dim="flex-grow" style="flex:{max(p, 0)} 1 0;background:{tono}"></i>'
                     for (_, p, _), tono in zip(conjuntos, TONOS_PARTICION))
    cuerpo = "".join(
        f'<div><div class="mt-sr"><span>{html.escape(nombre)}</span><b>{_numeros(f"{p} % · {miles(n)}")}</b></div>'
        f'<div class="mt-tr"><i data-mt-dim="width" style="width:{min(max(p, 0), 100)}%;--i:{k}"></i></div></div>'
        for k, (nombre, p, n) in enumerate(conjuntos))
    return _html(f'<div data-mt="{_id("particion", id)}"><div class="mt-part" role="img" aria-label="Proporción de cada conjunto">'
                 f'{tramos}</div><div class="mt-filas" style="margin-top:12px;gap:12px">{cuerpo}</div></div>')


def matriz(valores, clases=("Bajo", "Medio", "Alto"), prefijo="Real ", tono=None, descripcion="Matriz de confusión", id=None):
    """Matriz 3 × 3 en cuadros. `tono(i, j, v)` devuelve 'd' (fuerte), 'e' (medio) o '' (claro)."""
    tono = tono or (lambda i, j, v: "d" if i == j else "e" if v else "")
    celdas = "<span></span>" + "".join(f'<span class="mt-mut">{html.escape(c)}</span>' for c in clases)
    for i, fila in enumerate(valores):
        celdas += f'<span class="mt-mut f">{html.escape(prefijo + clases[i])}</span>'
        # se rellena celda por celda (--i: orden de lectura) y cada número cuenta hasta su valor
        celdas += "".join(f'<span class="c {tono(i, j, v)}" style="--i:{i * len(fila) + j}">{_numeros(miles(v))}</span>'
                          for j, v in enumerate(fila))
    return (f'<div class="mt-matriz" data-mt="{_id("matriz", id)}" role="img" aria-label="{html.escape(descripcion)}: '
            f'filas, clase real; columnas, clase asignada">{celdas}</div>')


def indicador(titulo, valor, pie, id=None):
    """Contenido de una tarjeta de indicador: nombre, cifra grande y una frase que la explica."""
    return _html(f"""
    <div data-mt="{_id("indicador", id)}">
    <div class="mt-kpi-t">{html.escape(titulo)}</div>
    <div class="mt-big">{_numeros(html.escape(str(valor)))}</div>
    <div class="mt-kpi-s">{html.escape(pie)}</div></div>""")


def puntos(frases):
    """Viñetas. Las frases ya vienen como HTML seguro (texto armado por la app)."""
    return '<div class="mt-puntos">' + "".join(f"<div><span>{f}</span></div>" for f in frases) + "</div>"


def nota_sintetico(texto):
    return f'<div class="mt-nota-warn">{html.escape(texto)}</div>'


def registro_ejecucion(eventos):
    """Barra inferior: los últimos eventos de la sesión, cada uno (hora, texto)."""
    if eventos:
        cuerpo = "".join(f"<span><b>{html.escape(hora)}</b> {html.escape(texto)}</span>" for hora, texto in eventos)
    else:
        cuerpo = "<span>Aún no se ha ejecutado nada en esta sesión.</span>"
    return f'<div class="mt-lg" role="status"><span class="t">Registro de ejecución</span>{cuerpo}</div>'


def tarjeta_usuario(nombre, rol):
    return _html(f"""
    <div class="mt-gl">Sesión</div>
    <div class="mt-usuario"><i class="mt-dot"></i><div><b>{html.escape(nombre)}</b><span>{html.escape(rol)}</span></div></div>""")
