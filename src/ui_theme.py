"""Capa visual de app_demo.py: estilo Apple med-tech con vidrio esmerilado y paleta ciruela sobre crema.

Paleta del sistema: ciruela #7D2F5F, #A54178, #D8639B, #EFC6D9 sobre crema #F3F3E7.
Colores de alerta: rojo #F099AB (Alto Riesgo / regla clínica), amarillo #F2E88F (Riesgo Medio / dato
faltante), verde #B6E39A (Bajo Riesgo / estado correcto) y ciruela #B85A8E (avisos informativos).

Movimiento: una sola curva, cubic-bezier(.32,.72,0,1); 0,2 s para respuestas y 0,35–0,5 s para entradas.
Todo es CSS + SVG en línea (sin fuentes ni librerías externas), así que la interfaz funciona offline.
Respeta `prefers-reduced-motion` (sin animaciones) y `prefers-reduced-transparency`.
"""
import html

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
  /* ---- movimiento: una sola curva para toda la página ---- */
  --mt-curva: cubic-bezier(.32, .72, 0, 1);
  --mt-rapida: .2s;            /* respuestas: hover, presión, cambios de color */
  --mt-entrada: .45s;          /* entrada de tarjetas y paneles */
  --mt-entrada-corta: .35s;    /* entrada de elementos pequeños */
  --mt-entrada-larga: .5s;     /* gráficas que crecen */
  --mt-cascada: 70ms;          /* retraso entre elementos consecutivos */
  --mt-subida: 14px;           /* desplazamiento vertical de entrada */
  --mt-rebote: 1.05;           /* escala máxima del rebote de elementos pequeños */

  /* ---- superficies ---- */
  --mt-radio-s: 16px;
  --mt-radio-m: 18px;
  --mt-radio-l: 20px;
  --mt-sombra: 0 1px 2px rgba(58, 31, 48, .04), 0 12px 40px -12px rgba(125, 47, 95, .16);
  --mt-sombra-alta: 0 2px 4px rgba(58, 31, 48, .05), 0 22px 56px -18px rgba(125, 47, 95, .26);
  --mt-borde: 1px solid rgba(125, 47, 95, .08);
  --mt-vidrio: rgba(255, 255, 255, .62);
  --mt-desenfoque: blur(20px) saturate(180%);

  /* ---- paleta del sistema ---- */
  --mt-ciruela-900: #7D2F5F;
  --mt-ciruela-700: #A54178;
  --mt-ciruela-500: #D8639B;
  --mt-ciruela-100: #EFC6D9;
  --mt-crema: #F3F3E7;
  --mt-tinta: #3A1F30;
  --mt-tinta-suave: #76606D;

  /* ---- colores de alerta ---- */
  --mt-rojo: #F099AB;
  --mt-amarillo: #F2E88F;
  --mt-verde: #B6E39A;
  --mt-info: #B85A8E;

  --mt-fuente: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", system-ui, sans-serif;
}

/* ---------- lienzo ---------- */
/* No usar un selector genérico como [class*="st-"]: pisaría la fuente de íconos (Material Symbols) */
html, body, .stApp, p, label, input, button, textarea, li, h1, h2, h3, h4, .mt-hero, .mt-result, .mt-panel { font-family: var(--mt-fuente); }
.stApp {
  color: var(--mt-tinta);
  background:
    radial-gradient(1100px 650px at 6% -12%, rgba(239, 198, 217, .75) 0%, transparent 62%),
    radial-gradient(900px 600px at 104% 8%, rgba(216, 99, 155, .14) 0%, transparent 60%),
    radial-gradient(900px 700px at 50% 118%, rgba(239, 198, 217, .55) 0%, transparent 60%),
    var(--mt-crema);
  background-attachment: fixed;
}
.stApp::before, .stApp::after {
  content: ""; position: fixed; z-index: 0; pointer-events: none; border-radius: 50%; filter: blur(60px);
  will-change: transform;
}
.stApp::before {
  width: 520px; height: 520px; left: -140px; top: 22%;
  background: radial-gradient(circle, rgba(216, 99, 155, .22), transparent 70%);
  animation: mt-deriva-a 38s var(--mt-curva) infinite alternate;
}
.stApp::after {
  width: 460px; height: 460px; right: -120px; top: 48%;
  background: radial-gradient(circle, rgba(239, 198, 217, .7), transparent 70%);
  animation: mt-deriva-b 44s var(--mt-curva) infinite alternate;
}
@keyframes mt-deriva-a { to { transform: translate(120px, -80px) scale(1.12); } }
@keyframes mt-deriva-b { to { transform: translate(-140px, 60px) scale(1.08); } }

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
body:has(.st-key-mt-login) { overflow: hidden; }

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
/* el componente que monta la pantalla de bienvenida no debe dejar hueco en la página */
[data-testid="stElementContainer"]:has([data-testid="stBidiComponentRegular"]) { display: none; }
[data-testid="stToolbar"] { opacity: .55; }
.block-container { max-width: 1120px; padding-top: 2.2rem; padding-bottom: 4rem; position: relative; z-index: 1; }

h1, h2, h3, h4 { color: var(--mt-tinta); letter-spacing: -.022em; }
p, label, span, div { -webkit-font-smoothing: antialiased; }

/* ---------- movimiento base ---------- */
/* Entrada: sube 14 px mientras pasa de transparente a visible. --i fija su lugar en la cascada. */
@keyframes mt-entrar { from { opacity: 0; transform: translateY(var(--mt-subida)); } to { opacity: 1; transform: none; } }
/* Elementos pequeños: aparecen con un rebote muy sutil (máximo 105 %) */
@keyframes mt-rebotar {
  0%   { opacity: 0; transform: scale(.9); }
  60%  { opacity: 1; transform: scale(var(--mt-rebote)); }
  100% { opacity: 1; transform: scale(1); }
}
/* "backwards": la animación solo rige hasta terminar; después el hover puede usar transform */
.mt-in, .mt-hero, .mt-result, .mt-note, .mt-panel, .mt-step, .mt-section, div[data-testid="stForm"] {
  animation: mt-entrar var(--mt-entrada) var(--mt-curva) backwards;
  animation-delay: calc(var(--i, 0) * var(--mt-cascada));
}
.mt-pill, .mt-kpi, .mt-badge, .mt-chip, .mt-icon, .mt-section .num, .mt-step .n, .mt-trace div {
  animation: mt-rebotar var(--mt-entrada-corta) var(--mt-curva) backwards;
  animation-delay: calc(var(--i, 0) * var(--mt-cascada) + 120ms);
}
/* Cambios de color, borde y fondo: se funden en 0,2 s */
.mt-pill, .mt-kpi, .mt-trace div, .mt-step, .mt-note, .mt-chip {
  transition: background-color var(--mt-rapida) var(--mt-curva), border-color var(--mt-rapida) var(--mt-curva),
              color var(--mt-rapida) var(--mt-curva), box-shadow var(--mt-rapida) var(--mt-curva),
              transform var(--mt-rapida) var(--mt-curva);
}

/* ---------- vidrio ---------- */
.mt-glass, div[data-testid="stForm"], div[data-testid="stExpander"] details {
  background: var(--mt-vidrio);
  -webkit-backdrop-filter: var(--mt-desenfoque);
  backdrop-filter: var(--mt-desenfoque);
  border: var(--mt-borde);
  box-shadow: var(--mt-sombra), inset 0 1px 0 rgba(255, 255, 255, .85);
  border-radius: var(--mt-radio-l);
}
div[data-testid="stForm"] { padding: 1.6rem 1.8rem 1.4rem; --i: 1; }

/* ---------- encabezado ---------- */
.mt-hero {
  display: grid; grid-template-columns: auto 1fr auto; gap: 1.4rem; align-items: center;
  padding: 1.5rem 1.8rem; margin-bottom: 1.4rem;
}
.mt-logo {
  width: 76px; height: 76px; border-radius: var(--mt-radio-m); display: grid; place-items: center;
  background: linear-gradient(160deg, #FFFFFF 0%, #F8E6EF 100%);
  box-shadow: 0 10px 28px -12px rgba(165, 65, 120, .45), inset 0 1px 0 #fff;
}
.mt-eyebrow { font-size: .74rem; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: var(--mt-ciruela-700); }
.mt-title {
  font-size: 2.6rem !important; line-height: 1.02 !important; font-weight: 700 !important; letter-spacing: -.035em !important;
  margin: .15rem 0 .25rem !important; padding: 0 !important;
  background: linear-gradient(120deg, var(--mt-ciruela-900) 0%, var(--mt-ciruela-700) 55%, var(--mt-ciruela-500) 100%);
  -webkit-background-clip: text; background-clip: text; color: transparent !important;
}
.mt-sub { margin: 0; color: var(--mt-tinta-suave); font-size: .98rem; }
.mt-pills { display: flex; flex-wrap: wrap; gap: .45rem; margin-top: .75rem; }
.mt-pill {
  display: inline-flex; align-items: center; gap: .4rem; padding: .32rem .75rem; border-radius: 999px;
  font-size: .78rem; font-weight: 500; color: var(--mt-tinta);
  background: rgba(255, 255, 255, .72); border: var(--mt-borde);
}
.mt-dot { width: 7px; height: 7px; border-radius: 50%; background: #7DBB59; box-shadow: 0 0 0 3px rgba(182, 227, 154, .55); }
.mt-kpis { display: grid; grid-template-columns: repeat(3, minmax(88px, 1fr)); gap: .6rem; }
.mt-kpi { padding: .7rem .85rem; border-radius: var(--mt-radio-s); background: rgba(255, 255, 255, .7); border: var(--mt-borde); text-align: left; }
.mt-kpi b { display: block; font-size: 1.35rem; font-weight: 650; letter-spacing: -.02em; color: var(--mt-ciruela-900); font-variant-numeric: tabular-nums; }
.mt-kpi span { font-size: .7rem; color: var(--mt-tinta-suave); letter-spacing: .01em; }

/* ---------- títulos de sección ---------- */
.mt-section { display: flex; align-items: baseline; gap: .6rem; margin: 1.6rem 0 .7rem; }
.mt-section .num {
  font-size: .72rem; font-weight: 700; color: #fff; background: linear-gradient(135deg, var(--mt-ciruela-500), var(--mt-ciruela-900));
  border-radius: 8px; padding: .14rem .45rem; letter-spacing: .02em;
}
.mt-section h3 { margin: 0 !important; padding: 0 !important; font-size: 1.28rem !important; font-weight: 650 !important; }
.mt-group { font-size: .74rem; font-weight: 600; letter-spacing: .07em; text-transform: uppercase; color: var(--mt-ciruela-700); margin: .2rem 0 .4rem; }

/* ---------- controles ---------- */
[data-testid="stWidgetLabel"] p { font-size: .84rem !important; font-weight: 500 !important; color: var(--mt-tinta-suave) !important; }
[data-testid="stNumberInputContainer"], [data-testid="stSelectbox"] div[role="group"] {
  border-radius: 14px !important; background: rgba(255, 255, 255, .85) !important;
  border: 1px solid rgba(125, 47, 95, .12) !important; box-shadow: inset 0 1px 2px rgba(58, 31, 48, .04);
  transition: box-shadow var(--mt-rapida) var(--mt-curva), border-color var(--mt-rapida) var(--mt-curva),
              background-color var(--mt-rapida) var(--mt-curva);
}
[data-testid="stNumberInputContainer"]:hover, [data-testid="stSelectbox"] div[role="group"]:hover { border-color: rgba(165, 65, 120, .28) !important; }
[data-testid="stNumberInputContainer"]:focus-within, [data-testid="stSelectbox"] div[role="group"]:focus-within {
  border-color: var(--mt-ciruela-500) !important; box-shadow: 0 0 0 4px rgba(216, 99, 155, .16) !important;
}
[data-testid="stNumberInputContainer"] input, [data-testid="stSelectbox"] input { background: transparent !important; }
input { font-variant-numeric: tabular-nums; }
[data-testid="stNumberInputStepDown"], [data-testid="stNumberInputStepUp"] {
  border-radius: 10px; background: transparent !important;
  transition: transform var(--mt-rapida) var(--mt-curva), background-color var(--mt-rapida) var(--mt-curva);
}
[data-testid="stNumberInputStepDown"]:hover, [data-testid="stNumberInputStepUp"]:hover { background: rgba(216, 99, 155, .12) !important; }
[data-testid="stNumberInputStepDown"]:active, [data-testid="stNumberInputStepUp"]:active { transform: scale(.88); }

/* radio horizontal como control segmentado de iOS */
[data-testid="stRadioGroup"][aria-orientation="horizontal"] {
  display: inline-flex !important; gap: 2px !important; padding: 3px; border-radius: 12px;
  background: rgba(125, 47, 95, .08);
}
[data-testid="stRadioGroup"] > div { margin: 0 !important; }
[data-testid="stRadioOption"] {
  margin: 0 !important; padding: .4rem 1rem !important; border-radius: 9px; cursor: pointer;
  transition: background-color var(--mt-rapida) var(--mt-curva), box-shadow var(--mt-rapida) var(--mt-curva),
              transform var(--mt-rapida) var(--mt-curva);
}
[data-testid="stRadioOption"] > div > div:first-child { display: none !important; }
[data-testid="stRadioOption"] p { font-size: .88rem !important; font-weight: 500; }
[data-testid="stRadioOption"][data-selected="true"] {
  background: #fff; box-shadow: 0 3px 10px -4px rgba(125, 47, 95, .35), 0 0 0 .5px rgba(125, 47, 95, .08);
}
[data-testid="stRadioOption"]:active { transform: scale(.97); }

/* botones: se encogen al presionar y se elevan con sombra suave al pasar el cursor */
.stButton > button, [data-testid="stFormSubmitButton"] > button {
  border-radius: 999px !important; font-weight: 600 !important; letter-spacing: -.005em;
  transition: transform var(--mt-rapida) var(--mt-curva), box-shadow var(--mt-rapida) var(--mt-curva),
              background-color var(--mt-rapida) var(--mt-curva), border-color var(--mt-rapida) var(--mt-curva) !important;
}
.stButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover { transform: translateY(-1px); }
.stButton > button:active, [data-testid="stFormSubmitButton"] > button:active { transform: scale(.97) !important; }
.stButton > button {
  background: rgba(255, 255, 255, .75) !important; border: var(--mt-borde) !important; color: var(--mt-tinta) !important;
  padding: .55rem 1rem !important;
}
.stButton > button:hover { background: #fff !important; box-shadow: 0 10px 24px -12px rgba(125, 47, 95, .4); }
[data-testid="stFormSubmitButton"] > button {
  background: linear-gradient(135deg, var(--mt-ciruela-900) 0%, var(--mt-ciruela-700) 55%, var(--mt-ciruela-500) 100%) !important;
  color: #fff !important; border: 0 !important; padding: .85rem 1.2rem !important; font-size: 1rem !important;
  box-shadow: 0 14px 30px -14px rgba(125, 47, 95, .6), inset 0 1px 0 rgba(255, 255, 255, .25) !important;
}
[data-testid="stFormSubmitButton"] > button:hover { box-shadow: 0 20px 40px -14px rgba(125, 47, 95, .7), inset 0 1px 0 rgba(255, 255, 255, .28) !important; }

/* barra lateral */
section[data-testid="stSidebar"] > div {
  background: rgba(247, 246, 238, .66);
  -webkit-backdrop-filter: var(--mt-desenfoque); backdrop-filter: var(--mt-desenfoque);
  border-right: var(--mt-borde);
}
section[data-testid="stSidebar"] h4 { font-size: .74rem !important; letter-spacing: .08em; text-transform: uppercase; color: var(--mt-ciruela-700) !important; margin-top: .6rem; }

div[data-testid="stExpander"] details { border-radius: var(--mt-radio-l) !important; }
div[data-testid="stExpander"] summary { font-weight: 600; }

/* ---------- indicadores de carga: spinner discreto ---------- */
@keyframes mt-girar { to { transform: rotate(360deg); } }
[data-testid="stStatusWidgetRunningIcon"], [data-testid="stStatusWidgetRunningManIcon"] { display: none !important; }
[data-testid="stStatusWidget"]:has([data-testid="stStatusWidgetRunningIcon"])::before {
  content: ""; width: 14px; height: 14px; border-radius: 50%; margin-right: .5rem;
  border: 2px solid rgba(165, 65, 120, .22); border-top-color: var(--mt-ciruela-700);
  animation: mt-girar .8s linear infinite;
}
[data-testid="stSpinner"] { color: var(--mt-tinta-suave); font-size: .85rem; }
[data-testid="stSpinner"] i, [data-testid="stSpinner"] svg { color: var(--mt-ciruela-700) !important; border-color: rgba(165, 65, 120, .22) !important;
  border-top-color: var(--mt-ciruela-700) !important; }

/* ---------- avisos flotantes: emergen desde abajo y se retiran solos ---------- */
@keyframes mt-emerger { from { opacity: 0; transform: translateY(24px) scale(.98); } to { opacity: 1; transform: none; } }
/* Streamlit 1.66 ya los ubica abajo; aquí se les da ancho, material y la entrada desde abajo */
[data-testid="stToast"] {
  width: min(440px, calc(100vw - 2rem)) !important; max-width: none !important;
  background: rgba(255, 255, 255, .82) !important;
  -webkit-backdrop-filter: var(--mt-desenfoque); backdrop-filter: var(--mt-desenfoque);
  border: var(--mt-borde) !important; border-radius: var(--mt-radio-m) !important;
  box-shadow: var(--mt-sombra-alta) !important; color: var(--mt-tinta) !important;
  animation: mt-emerger var(--mt-entrada) var(--mt-curva) both;
}

/* ---------- tarjeta de resultado ---------- */
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
.mt-note.info { background: linear-gradient(135deg, rgba(184, 90, 142, .16), rgba(184, 90, 142, .07)) !important; border-color: rgba(184, 90, 142, .22) !important; }
.mt-note.info p { color: #6E2C55 !important; }
.mt-note.ok { background: linear-gradient(135deg, rgba(182, 227, 154, .45), rgba(182, 227, 154, .2)) !important; border-color: rgba(125, 187, 89, .3) !important; }
.mt-chips { display: flex; flex-wrap: wrap; gap: .45rem; }
.mt-chip {
  display: inline-flex; align-items: center; gap: .4rem; padding: .38rem .8rem; border-radius: 12px; font-size: .84rem; font-weight: 500;
  background: rgba(255, 255, 255, .6); color: #6B1832; border: 1px solid rgba(217, 102, 127, .3);
}

/* ---------- gráficas ---------- */
.mt-panel { padding: 1.35rem 1.5rem; border-radius: var(--mt-radio-l); margin-top: .9rem; }
.mt-panel-title { font-size: .74rem; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: var(--mt-ciruela-700); margin-bottom: .9rem; }
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
.mt-track { height: 12px; border-radius: 999px; background: rgba(125, 47, 95, .08); overflow: hidden; }
/* la barra crece con transform (no con width): más fluido */
.mt-fill { height: 100%; border-radius: 999px; transform-origin: left center; box-shadow: inset 0 1px 0 rgba(255, 255, 255, .5);
  animation: mt-crecer var(--mt-entrada-larga) var(--mt-curva) both; }
@keyframes mt-crecer { from { transform: scaleX(0); } to { transform: scaleX(1); } }
.mt-bar-row .val { text-align: right; font-size: .86rem; font-weight: 600; font-variant-numeric: tabular-nums; }
.mt-trace { display: grid; grid-template-columns: repeat(3, 1fr); gap: .6rem; margin-top: 1rem; }
.mt-trace div { padding: .7rem .85rem; border-radius: var(--mt-radio-s); background: rgba(255, 255, 255, .62); border: var(--mt-borde); }
.mt-trace span { display: block; font-size: .7rem; color: var(--mt-tinta-suave); letter-spacing: .02em; }
.mt-trace b { font-size: .92rem; font-weight: 600; }

/* ---------- protocolo ---------- */
.mt-steps { display: grid; gap: .55rem; }
.mt-step { display: grid; grid-template-columns: 34px 1fr; gap: .85rem; align-items: start; padding: .9rem 1.1rem; border-radius: var(--mt-radio-m); }
.mt-step:hover { transform: translateY(-1px); box-shadow: var(--mt-sombra-alta), inset 0 1px 0 rgba(255, 255, 255, .85); }
.mt-step .n { width: 30px; height: 30px; border-radius: 10px; display: grid; place-items: center; font-weight: 700; font-size: .85rem; }
.mt-step p { margin: .2rem 0 0; font-size: .93rem; line-height: 1.5; }
.mt-foot { margin-top: .8rem; font-size: .78rem; color: var(--mt-tinta-suave); }

/* ---------- adaptación ---------- */
@media (max-width: 760px) {
  .mt-hero { grid-template-columns: auto 1fr; }
  .mt-kpis { grid-column: 1 / -1; }
  .mt-chart { grid-template-columns: 1fr; justify-items: center; }
  .mt-trace { grid-template-columns: 1fr; }
  .mt-result { grid-template-columns: 1fr; }
}
/* Movimiento reducido: sin animaciones ni transiciones */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important; }
}
/* Transparencia reducida (p. ej. Windows con "Efectos de transparencia" desactivados):
   vidrio más esmerilado y opaco, en lugar de eliminar el material. */
@media (prefers-reduced-transparency: reduce) {
  .mt-glass, div[data-testid="stForm"], div[data-testid="stExpander"] details {
    background: rgba(255, 255, 252, .88) !important;
    -webkit-backdrop-filter: blur(14px) saturate(140%) !important; backdrop-filter: blur(14px) saturate(140%) !important;
  }
  section[data-testid="stSidebar"] > div { background: rgba(247, 246, 238, .92) !important; }
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
    tarjetas = "".join(f'<div class="mt-kpi" style="--i:{i + 2}"><b>{valor}</b><span>{nombre}</span></div>'
                       for i, (nombre, valor) in enumerate(kpis))
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
        <div class="mt-track"><div class="mt-fill" style="width:{p * 100:.1f}%;background:{ESTILO_CATEGORIA[c]['barra']};animation-delay:{0.3 + 0.07 * i:.2f}s"></div></div>
        <span class="val">{_pct(p)}</span></div>"""
        for i, (c, p) in enumerate(probabilidades.items())
    )
    origen_txt = "Regla clínica" if origen == "regla_clinica" else "Modelo ML"
    return _html(f"""
    <div class="mt-panel mt-glass" style="--i:3">
      <div class="mt-panel-title">Inferencia del modelo · {html.escape(nombre_modelo)}</div>
      <div class="mt-chart">
        <div class="mt-ring">
          <svg width="150" height="150" viewBox="0 0 150 150">
            <circle cx="75" cy="75" r="54" fill="none" stroke="rgba(125,47,95,.08)" stroke-width="14"/>
            <circle class="arc" cx="75" cy="75" r="54" fill="none" stroke="{color_top}" stroke-width="14" stroke-linecap="round"
              stroke-dasharray="{circunferencia}" stroke-dashoffset="{circunferencia * (1 - p_top):.2f}"/>
          </svg>
          <div class="center"><span class="mt-count" style="--mt-num:{round(p_top * 100)}"></span>
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


def login_encabezado():
    """Panel derecho del inicio de sesión: logo MATERNA destacado y bienvenida."""
    return _html("""
    <div class="mt-acceso-logo mt-escalon" style="--paso:1">
      <img src="./app/static/logo_isotipo.webp" alt="" aria-hidden="true"><span>MATERNA</span>
    </div>
    <div class="mt-escalon" style="--paso:2">
      <div class="mt-acceso-titulo" role="heading" aria-level="1">Le damos la bienvenida</div>
      <p class="mt-acceso-sub">Módulo 1 · Laboratorio de ML. Inicie sesión para continuar.</p>
    </div>""")


def cabecera(eyebrow, titulo, sub, pills=()):
    """Cabecera de las páginas de la consola, con el mismo vidrio y tipografía que la del triaje."""
    etiquetas = "".join(f'<span class="mt-pill" style="--i:{i + 1}">{html.escape(p)}</span>' for i, p in enumerate(pills))
    return _html(f"""
    <div class="mt-hero mt-glass" style="--i:0">
      <div class="mt-logo">{LOGO_ISOTIPO}</div>
      <div>
        <div class="mt-eyebrow">{html.escape(eyebrow)}</div>
        <h1 class="mt-title">{html.escape(titulo)}</h1>
        <p class="mt-sub">{html.escape(sub)}</p>
        {f'<div class="mt-pills">{etiquetas}</div>' if pills else ''}
      </div>
      <div></div>
    </div>""")


def tarjeta_usuario(nombre, rol):
    return _html(f"""
    <div class="mt-group">Sesión</div>
    <div class="mt-pill" style="--i:0"><i class="mt-dot"></i>{html.escape(nombre)} · {html.escape(rol)}</div>""")
