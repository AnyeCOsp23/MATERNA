"""Fase 3 — «Ver el recorrido»: animación del camino de una gestante por el sistema híbrido (fase 07).

Dibuja, con SVG y JavaScript propios (sin librerías ni internet), lo que calcula src/recorrido.py:
datos → 17 variables → árboles del bosque (un brillo baja por el camino real de preguntas) → promedio de las
300 hojas → reglas clínicas → resultado. Tiene Pausar, Repetir y Ver el final, y con «reducir movimiento»
muestra directamente el estado final. No es una red neuronal: es el Random Forest que usa MATERNA.
"""
from streamlit import components

CSS = """
.rec { font-family: inherit; color: #3A1230; }
.rec svg { display: block; width: 100%; height: auto; }
.rec text { font-family: inherit; }
.rec .cab { font-size: 11.5px; font-weight: 700; letter-spacing: 1.1px; fill: #8B6F7F; text-transform: uppercase; }
.rec .eti { font-size: 13px; font-weight: 600; fill: #3A1230; }
.rec .val { font-size: 12px; fill: #6B4A5E; }
.rec .imp { font-style: italic; fill: #7A4A00; }
.rec .mini { font-size: 11px; fill: #8B6F7F; }
.rec .lin { fill: none; stroke: #E6D8DF; stroke-width: 1.2; transition: stroke .3s, stroke-width .3s; }
.rec .lin.on { stroke: #CF97B5; stroke-width: 1.6; }
.rec .lin.fuerte { stroke: #7B2D5B; stroke-width: 2.2; }
.rec .nodo { fill: #fff; stroke: #CFB9C6; stroke-width: 1.5; transition: fill .25s, stroke .25s, r .25s; }
.rec .nodo.on { fill: #F5D3E3; stroke: #7B2D5B; }
.rec .nodo.pulso { fill: #7B2D5B; stroke: #7B2D5B; }
.rec .oculto { opacity: 0; }
.rec .aparece { transition: opacity .35s; opacity: 1; }
.rec .punto { fill: #EFE0E7; transition: fill .2s; }
.rec .pista { fill: #F3E8EE; }
.rec .barra { transition: width .9s cubic-bezier(.32,.72,0,1); }
.rec .puerta { fill: #fff; stroke: #CFB9C6; stroke-width: 1.5; transition: fill .3s, stroke .3s; }
.rec .puerta.pasa { fill: #E9F5EE; stroke: #4E9A72; }
.rec .puerta.activa { fill: #FDECEF; stroke: #9B2D5C; stroke-width: 2.4; }
.rec .final { fill: #fff; stroke: #CFB9C6; stroke-width: 2; transition: fill .4s, stroke .4s; transform-box: fill-box; transform-origin: center; }
.rec .final.listo { animation: rec-pop .5s cubic-bezier(.2,.9,.3,1.4); }
@keyframes rec-pop { from { transform: scale(.6); } to { transform: scale(1); } }
.rec .brillo { fill: #fff; stroke: #7B2D5B; stroke-width: 2; filter: drop-shadow(0 0 5px #D8639B) drop-shadow(0 0 10px #F5D3E3); }
.rec .pie { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-top: 6px; }
.rec .paso { flex: 1 1 320px; min-height: 40px; display: flex; align-items: center; padding: 8px 14px; border-radius: 12px;
  background: #FBF4F8; border: 1px solid #E9DDE3; font-size: 13.5px; font-weight: 500; line-height: 1.4; }
.rec .paso b { color: #7B2D5B; margin-right: 6px; white-space: nowrap; }
.rec button { height: 36px; padding: 0 16px; border-radius: 18px; border: 2px solid #7B2D5B; background: transparent; color: #7B2D5B;
  font: 600 13px inherit; font-family: inherit; cursor: pointer; transition: transform .2s, background-color .2s; }
.rec button:hover { background: #FBF4F8; transform: translateY(-1px); }
.rec button:active { transform: scale(.96); }
.rec button:focus-visible { outline: 2px solid #7B2D5B; outline-offset: 2px; }
.rec button.lleno { background: #7B2D5B; color: #fff; }
.rec button.lleno:hover { background: #5C1F45; }
@media (prefers-reduced-motion: reduce) { .rec * { transition: none !important; animation: none !important; } }
"""

JS = r"""
const NS = "http://www.w3.org/2000/svg";
const COLOR = ["#2F9C8A", "#E0A33A", "#9B2D5C"];
const CORTO = ["Bajo", "Medio", "Alto"];

export default function recorrido({ data, parentElement }) {
  const raiz = parentElement.querySelector(".rec");
  if (!raiz || !data) return;
  if (raiz.__ficha) raiz.__ficha.cancelado = true;      // se volvió a dibujar: se detiene la animación anterior
  const ficha = { cancelado: false, pausado: false };
  raiz.__ficha = ficha;
  raiz.textContent = "";
  const d = data;
  const sinMovimiento = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const el = (nombre, attrs = {}, padre = null, texto = null) => {
    const e = document.createElementNS(NS, nombre);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    if (texto !== null) e.textContent = texto;
    if (padre) padre.appendChild(e);
    return e;
  };
  const pct = (p) => (p * 100).toFixed(1).replace(".", ",") + " %";

  const svg = el("svg", { viewBox: "0 0 1204 640", role: "img",
    "aria-label": "Recorrido de una gestante por el sistema: datos, variables, árboles del bosque, promedio, reglas clínicas y resultado" }, raiz);
  const capaLineas = el("g", {}, svg), capaNodos = el("g", {}, svg), capaBrillo = el("g", {}, svg);

  // ---------- encabezados de las columnas
  [[20, "Datos de la gestante"], [262, d.variables.length + " variables"], [470, "Bosque · " + d.arboles.length + " de " + d.n_arboles + " árboles"],
   [856, "Los " + d.n_arboles + " árboles"], [1022, "Reglas"], [1124, "Resultado"]]
    .forEach(([x, t]) => el("text", { x, y: 22, class: "cab" }, svg, t));

  // ---------- datos y variables
  const yDato = (i) => 62 + i * 50, yVar = (j) => 56 + j * 33.5;
  const datos = d.datos.map((dato, i) => {
    const g = el("g", { class: "oculto" }, capaNodos);
    el("text", { x: 176, y: yDato(i) - 2, "text-anchor": "end", class: "eti" }, g, dato.etiqueta);
    el("text", { x: 176, y: yDato(i) + 12, "text-anchor": "end", class: "val" + (dato.imputado ? " imp" : "") }, g,
       dato.imputado ? "≈ " + dato.valor + " (imputada)" : dato.valor);
    const nodo = el("circle", { cx: 192, cy: yDato(i), r: 6, class: "nodo" }, g);
    return { g, nodo, x: 192, y: yDato(i) };
  });
  const variables = d.variables.map((v, j) => {
    const g = el("g", { class: "oculto" }, capaNodos);
    const nodo = el("circle", { cx: 290, cy: yVar(j), r: 5, class: "nodo" }, g);
    el("text", { x: 302, y: yVar(j) + 4, class: "val" }, g, v.etiqueta);
    const origen = datos[v.dato];
    const camino = `M${origen.x + 6},${origen.y} C${origen.x + 50},${origen.y} ${290 - 50},${yVar(j)} ${290 - 5},${yVar(j)}`;
    const linea = el("path", { d: camino, class: "lin oculto" }, capaLineas);
    return { g, nodo, linea, x: 290, y: yVar(j), desde: origen };
  });

  // ---------- árboles: el camino real de cada uno (nodo a nodo) y su hoja
  const arboles = d.arboles.map((a, k) => {
    const cx = 496 + k * 62, n = a.pasos.length, dy = Math.min(40, 490 / Math.max(n, 1));
    el("text", { x: cx, y: 46, "text-anchor": "middle", class: "mini" }, svg, "Árbol " + a.numero);
    const pts = [{ x: cx, y: 66 }];
    let desvio = 0;
    a.pasos.forEach((p, s) => {
      desvio = Math.max(-22, Math.min(22, desvio + (p.izquierda ? -8 : 8)));
      pts.push({ x: cx + desvio, y: 66 + (s + 1) * dy });
      // la rama que NO se tomó, apenas insinuada
      const lado = p.izquierda ? 9 : -9;
      el("line", { x1: pts[s].x, y1: pts[s].y, x2: pts[s].x + lado, y2: pts[s].y + dy * .55, class: "lin", "stroke-dasharray": "2 3" }, capaLineas);
    });
    const tramos = pts.slice(1).map((p, s) => el("line", { x1: pts[s].x, y1: pts[s].y, x2: p.x, y2: p.y, class: "lin" }, capaLineas));
    const nodos = pts.slice(0, -1).map((p) => el("circle", { cx: p.x, cy: p.y, r: 4, class: "nodo" }, capaNodos));
    const fin = pts[pts.length - 1];
    const hoja = el("rect", { x: fin.x - 7, y: fin.y - 7, width: 14, height: 14, rx: 4, class: "nodo" }, capaNodos);
    const sale = el("path", { d: `M${fin.x + 8},${fin.y} C${fin.x + 60},${fin.y} 790,160 846,160`, class: "lin oculto" }, capaLineas);
    return { pts, tramos, nodos, hoja, sale, fin, datos: a };
  });

  // ---------- los 300 árboles (un punto cada uno) y el promedio de sus hojas
  const puntos = d.inclinacion.map((c, i) =>
    el("rect", { x: 856 + (i % 15) * 9.6, y: 36 + Math.floor(i / 15) * 9.6, width: 7.2, height: 7.2, rx: 2, class: "punto" }, capaNodos));
  el("text", { x: 856, y: 258, class: "cab" }, svg, "Promedio de las hojas");
  const barras = d.clases.map((c, i) => {
    const y = 284 + i * 56;
    el("text", { x: 856, y, class: "eti" }, svg, c);
    el("rect", { x: 856, y: y + 6, width: 144, height: 10, rx: 5, class: "pista" }, svg);
    const barra = el("rect", { x: 856, y: y + 6, width: 0, height: 10, rx: 5, fill: COLOR[i], class: "barra" }, svg);
    const valor = el("text", { x: 1000, y, "text-anchor": "end", class: "val" }, svg, "—");
    const cuenta = el("text", { x: 856, y: y + 31, class: "mini" }, svg, "");
    return { barra, valor, cuenta };
  });
  const dice = el("text", { x: 856, y: 462, class: "eti oculto" }, svg, "El modelo dice: " + d.clases[d.clase_modelo]);

  // ---------- reglas clínicas y resultado
  const haciaReglas = el("path", { d: "M1004,351 L1022,351", class: "lin" }, capaLineas);
  const puerta = el("rect", { x: 1022, y: 296, width: 84, height: 110, rx: 14, class: "puerta" }, capaNodos);
  el("text", { x: 1064, y: 340, "text-anchor": "middle", class: "eti" }, svg, "Reglas");
  el("text", { x: 1064, y: 356, "text-anchor": "middle", class: "eti" }, svg, "clínicas");
  const estadoReglas = el("text", { x: 1064, y: 378, "text-anchor": "middle", class: "mini" }, svg, "");
  const haciaFinal = el("path", { d: "M1106,351 L1124,351", class: "lin" }, capaLineas);
  const final = el("circle", { cx: 1160, cy: 351, r: 34, class: "final" }, capaNodos);
  const finalTexto = el("text", { x: 1160, y: 356, "text-anchor": "middle", class: "eti oculto", fill: "#fff" }, svg, CORTO[d.clase]);
  finalTexto.style.fill = "#fff";
  const finalPie = el("text", { x: 1160, y: 408, "text-anchor": "middle", class: "eti oculto" }, svg, d.categoria);
  const ORIGEN = { regla_clinica: "por regla clínica", signo_alarma_3280: "por signo de alarma", modelo_ml: "lo decide el modelo" };
  const finalOrigen = el("text", { x: 1160, y: 424, "text-anchor": "middle", class: "mini oculto" }, svg, ORIGEN[d.origen] || "");

  // ---------- pie: qué está pasando y controles
  const pie = document.createElement("div"); pie.className = "pie"; raiz.appendChild(pie);
  const paso = document.createElement("div"); paso.className = "paso"; paso.setAttribute("role", "status"); paso.setAttribute("aria-live", "polite");
  pie.appendChild(paso);
  const boton = (texto, lleno) => { const b = document.createElement("button"); b.type = "button"; b.textContent = texto;
    if (lleno) b.className = "lleno"; pie.appendChild(b); return b; };
  const bPausa = boton("Pausar", false), bRepetir = boton("Repetir", true), bFinal = boton("Ver el final", false);
  const decir = (n, texto) => { paso.textContent = ""; const b = document.createElement("b"); b.textContent = n; paso.appendChild(b);
    paso.appendChild(document.createTextNode(texto)); };

  // ---------- estados (se usan tanto en la animación como para saltar al final)
  const ver = (e) => { e.classList.remove("oculto"); e.classList.add("aparece"); };
  const hojaLista = (a) => { a.hoja.style.fill = COLOR[a.datos.clase]; a.hoja.style.stroke = COLOR[a.datos.clase]; ver(a.sale); a.sale.classList.add("on"); };
  const puntosHasta = (n) => { for (let i = 0; i < n; i++) puntos[i].style.fill = COLOR[d.inclinacion[i]]; };
  const promedio = () => {
    barras.forEach((b, i) => { b.barra.setAttribute("width", Math.max(1.5, 144 * d.probabilidades[i]));
      b.valor.textContent = pct(d.probabilidades[i]); b.cuenta.textContent = d.arboles_por_clase[i] + " árboles se inclinan aquí"; });
    ver(dice);
  };
  const reglas = () => {
    const activa = d.origen !== "modelo_ml";
    puerta.classList.add(activa ? "activa" : "pasa");
    estadoReglas.textContent = activa ? "se activan" : "no se activan";
    haciaReglas.classList.add("fuerte");
  };
  const resultado = () => {
    haciaFinal.classList.add("fuerte");
    final.style.fill = COLOR[d.clase]; final.style.stroke = COLOR[d.clase]; final.classList.add("listo");
    [finalTexto, finalPie, finalOrigen].forEach(ver);
  };
  const textoReglas = () => d.origen === "regla_clinica" ? "Se activa una regla: " + d.reglas.join("; ") + ". La regla prevalece sobre el modelo."
    : d.origen === "signo_alarma_3280" ? "Signo de alarma de la ruta: " + d.signos_alarma.join("; ") + ". El triaje sube a Alto Riesgo."
    : "Ningún signo crítico: decide el modelo.";
  const textoFinal = () => "Resultado: " + d.categoria + " (" + (ORIGEN[d.origen] || "") + "). Probabilidades del modelo: "
    + d.clases.map((c, i) => c + " " + pct(d.probabilidades[i])).join(", ") + ".";

  const alFinal = () => {
    datos.forEach((x) => { ver(x.g); x.nodo.classList.add("on"); });
    variables.forEach((v) => { ver(v.g); ver(v.linea); v.linea.classList.add("on"); v.nodo.classList.add("on"); v.nodo.classList.remove("pulso"); });
    arboles.forEach((a) => { a.tramos.forEach((t) => t.classList.add("fuerte")); a.nodos.forEach((n) => { n.classList.add("on"); n.classList.remove("pulso"); }); hojaLista(a); });
    puntosHasta(puntos.length); promedio(); reglas(); resultado();
    decir("5 de 5", textoFinal());
    bPausa.disabled = true; bPausa.style.opacity = .45;
  };

  // ---------- animación: un brillo que recorre las líneas
  const esperar = (ms) => new Promise((listo) => {
    let t = 0, antes = performance.now();
    const cuadro = (ahora) => {
      if (ficha.cancelado) return;
      if (!ficha.pausado) t += ahora - antes;
      antes = ahora;
      t >= ms ? listo() : requestAnimationFrame(cuadro);
    };
    requestAnimationFrame(cuadro);
  });
  const viajar = (camino, ms) => new Promise((listo) => {     // camino: un <path> o una lista de puntos
    const porPuntos = Array.isArray(camino);
    const largo = porPuntos ? null : camino.getTotalLength();
    const brillo = el("circle", { r: 4.5, class: "brillo" }, capaBrillo);
    let t = 0, antes = performance.now();
    const cuadro = (ahora) => {
      if (ficha.cancelado) { brillo.remove(); return; }
      if (!ficha.pausado) t += ahora - antes;
      antes = ahora;
      const f = Math.min(1, t / ms), s = f < .5 ? 2 * f * f : 1 - Math.pow(-2 * f + 2, 2) / 2;   // entra y sale suave
      const p = porPuntos ? { x: camino[0].x + (camino[1].x - camino[0].x) * s, y: camino[0].y + (camino[1].y - camino[0].y) * s }
                          : camino.getPointAtLength(largo * s);
      brillo.setAttribute("cx", p.x); brillo.setAttribute("cy", p.y);
      if (f >= 1) { brillo.remove(); listo(); } else requestAnimationFrame(cuadro);
    };
    requestAnimationFrame(cuadro);
  });

  const animar = async () => {
    // 1. los datos se convierten en variables
    decir("1 de 5", "Los " + d.datos.length + " datos de la gestante se convierten en " + d.variables.length + " variables de entrada."
      + (d.datos.some((x) => x.imputado) ? " Lo que no se midió se completa con la mediana de su área y trimestre." : ""));
    for (const x of datos) { ver(x.g); x.nodo.classList.add("on"); await esperar(55); }
    await Promise.all(variables.map(async (v, j) => {
      await esperar(j * 45); ver(v.linea); await viajar(v.linea, 520);
      v.linea.classList.add("on"); ver(v.g); v.nodo.classList.add("on");
    }));
    await esperar(350);
    // 2. cada árbol hace sus preguntas: el primero despacio, los demás más rápido
    for (const [k, a] of arboles.entries()) {
      const ms = k === 0 ? 560 : 170;
      for (const [s, p] of a.datos.pasos.entries()) {
        const v = variables[p.variable];
        v.nodo.classList.add("pulso"); a.nodos[s].classList.add("pulso");
        decir("2 de 5", "Árbol " + a.datos.numero + " · pregunta " + (s + 1) + " de " + a.datos.pasos.length + ": " + p.pregunta + " → " + p.respuesta);
        await viajar([a.pts[s], a.pts[s + 1]], ms);
        a.tramos[s].classList.add("fuerte");
        v.nodo.classList.remove("pulso"); a.nodos[s].classList.remove("pulso"); a.nodos[s].classList.add("on");
      }
      hojaLista(a);
      decir("2 de 5", "Árbol " + a.datos.numero + ": su hoja se inclina por " + d.clases[a.datos.clase] + " (" + pct(a.datos.hoja[a.datos.clase]) + ").");
      await viajar(a.sale, 380);
      puntos[k].style.fill = COLOR[d.inclinacion[k]];
      await esperar(k === 0 ? 500 : 120);
    }
    // 3. los 300 árboles y el promedio de sus hojas
    decir("3 de 5", "Lo mismo ocurre en los " + d.n_arboles + " árboles. Cada punto es un árbol, con el color de la clase a la que se inclina.");
    for (let i = arboles.length; i <= puntos.length; i += 6) { puntosHasta(Math.min(i, puntos.length)); await esperar(22); }
    puntosHasta(puntos.length);
    await esperar(250);
    promedio();
    decir("3 de 5", "Se promedian las " + d.n_arboles + " hojas: " + d.clases.map((c, i) => c + " " + pct(d.probabilidades[i])).join(", ")
      + ". El modelo dice " + d.clases[d.clase_modelo] + ".");
    await esperar(1500);
    // 4. reglas clínicas
    await viajar(haciaReglas, 420);
    reglas();
    decir("4 de 5", textoReglas());
    await esperar(1500);
    // 5. resultado
    await viajar(haciaFinal, 420);
    resultado();
    decir("5 de 5", textoFinal());
    bPausa.disabled = true; bPausa.style.opacity = .45;
  };

  bPausa.onclick = () => { ficha.pausado = !ficha.pausado; bPausa.textContent = ficha.pausado ? "Seguir" : "Pausar"; };
  bFinal.onclick = () => { ficha.cancelado = true; capaBrillo.textContent = ""; alFinal(); };
  bRepetir.onclick = () => recorrido({ data, parentElement });
  sinMovimiento ? alFinal() : animar();
}
"""
_RECORRIDO = components.v2.component("materna_recorrido", html='<div class="rec"></div>', css=CSS, js=JS)


def mostrar(datos, clave="recorrido"):
    """Monta la animación con el recorrido que devuelve src.recorrido.recorrido()."""
    _RECORRIDO(data=datos, key=clave)
