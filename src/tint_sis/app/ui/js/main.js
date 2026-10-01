import { api } from "./api.js";
import { h, clear, btn } from "./dom.js";
import * as inicio from "./views/inicio.js";
import * as nuevoCiclo from "./views/nuevo_ciclo.js";
import * as ejecucion from "./views/ejecucion.js";
import * as resultados from "./views/resultados.js";
import * as historial from "./views/historial.js";
import * as configuracion from "./views/configuracion.js";
import * as homologos from "./views/homologos.js";

const ROUTES = {
  inicio,
  "nuevo-ciclo": nuevoCiclo,
  ejecucion,
  resultados,
  historial,
  configuracion,
  homologos,
};

const DEFAULT_ROUTE = "inicio";
const viewEl = document.getElementById("view");
const stripEl = document.getElementById("strip");

function currentRoute() {
  const raw = (location.hash || "").replace(/^#\/?/, "").split("?")[0];
  return ROUTES[raw] ? raw : DEFAULT_ROUTE;
}

function setActiveNav(route) {
  // "ejecucion" no tiene item propio: mantiene "nuevo-ciclo" resaltado
  const navRoute = route === "ejecucion" ? "nuevo-ciclo" : route;
  document.querySelectorAll(".nav__item").forEach((a) => {
    a.classList.toggle("is-active", a.dataset.route === navRoute);
  });
}

async function renderStrip() {
  try {
    const e = await api.estado();
    clear(stripEl).append(
      h("span", {}, `Carpeta:  ${e.carpeta_trabajo}`),
      h("span", {}, `Último ciclo:  ${e.ultimo_ciclo}`),
      h("span", {}, `Software:  ${e.software}`)
    );
  } catch (err) {
    clear(stripEl).append(h("span", {}, "sin conexión con el servicio local"));
  }
}

// Una vista puede devolver de render() una función de limpieza, o
// {cleanup, puedeSalir}: si puedeSalir() da false (p. ej. cambios sin guardar
// en Homólogos) se cancela el cambio de vista.
let activeCleanup = null;
let activeGuard = null;
let activeName = null;
let volviendo = false;

async function route() {
  const name = currentRoute();
  if (volviendo) {
    volviendo = false;
    return;
  }
  if (activeGuard && name !== activeName && !activeGuard()) {
    volviendo = true;
    location.hash = `#/${activeName}`;
    return;
  }
  setActiveNav(name);
  // la barra superior (softwares activos, último ciclo) cambia al guardar la
  // configuración o al terminar un ciclo: se refresca en cada cambio de vista
  renderStrip();
  cerrarAvisosDe(name);
  if (typeof activeCleanup === "function") {
    try { activeCleanup(); } catch (e) {}
  }
  activeCleanup = null;
  activeGuard = null;
  activeName = name;
  clear(viewEl);
  try {
    const res = await ROUTES[name].render(viewEl, { navigate });
    activeCleanup = typeof res === "function" ? res : (res && res.cleanup) || null;
    activeGuard = (res && typeof res === "object" && res.puedeSalir) || null;
  } catch (err) {
    viewEl.append(h("div", { class: "banner banner--error" }, `Error cargando la vista: ${err.message}`));
  }
  viewEl.scrollTop = 0;
}

export function navigate(name) {
  location.hash = `#/${name}`;
}

// ---------- avisos de fin de trabajo ----------
// Cuando termina el análisis del maestro, la preparación de los expertos o un
// ciclo, el servidor deja un aviso (y, en la app instalada, una notificación de
// Windows). Se consultan cada 2 s desde cualquier vista y cada uno queda como
// un cartel abajo a la derecha, con un botón a su vista, hasta cerrarlo o
// entrar a esa vista. Si sale estando ya en su vista, se va solo: no debe tapar
// lo que hay abajo a la derecha (el botón Ejecutar de Nuevo ciclo).
const avisosEl = h("div", { class: "avisos-flotantes", "aria-live": "polite" });
document.body.append(avisosEl);
const MAX_AVISOS_VISIBLES = 4;
const SEG_AVISO_BREVE = 8;
const BOTON_AVISO = { resultados: "Ver resultados", "nuevo-ciclo": "Ir a Nuevo ciclo", ejecucion: "Ver el detalle" };
let ultimoAviso = null;

function cerrarAvisosDe(vista) {
  avisosEl.querySelectorAll(".aviso-flotante").forEach((el) => {
    if (el.dataset.vista === vista) el.remove();
  });
}

function mostrarAviso(a) {
  const el = h("div", { class: `aviso-flotante aviso-flotante--${a.nivel}`, role: "status", "data-vista": a.vista || "" });
  const cerrar = () => el.remove();
  const enSuVista = !a.vista || a.vista === currentRoute();
  const ir = enSuVista
    ? null
    : btn(BOTON_AVISO[a.vista] || "Ver", { variant: "primary", onClick: () => { cerrar(); navigate(a.vista); } });
  el.append(
    h(
      "div",
      { class: "aviso-flotante__cab" },
      h("strong", {}, a.titulo),
      h("span", { class: "aviso-flotante__hora mono" }, a.hora),
      h("button", { class: "aviso-flotante__cerrar", title: "Cerrar", "aria-label": "Cerrar", onclick: cerrar }, "×")
    ),
    h("div", { class: "aviso-flotante__texto" }, a.texto),
    ir ? h("div", { class: "row", style: "justify-content:flex-end" }, ir) : null
  );
  avisosEl.append(el);
  while (avisosEl.childElementCount > MAX_AVISOS_VISIBLES) avisosEl.firstElementChild.remove();
  if (enSuVista || a.nivel === "info") setTimeout(cerrar, SEG_AVISO_BREVE * 1000);
  // la barra superior muestra el último ciclo: se refresca al terminar uno
  renderStrip();
}

async function revisarAvisos() {
  try {
    const r = await api.avisos(ultimoAviso ?? -1);
    if (ultimoAviso !== null) r.avisos.forEach(mostrarAviso);
    ultimoAviso = r.ultimo;
  } catch (e) {
    /* servicio caído: se reintenta en el próximo tick */
  }
}
revisarAvisos();
setInterval(revisarAvisos, 2000);

window.addEventListener("hashchange", route);
if (!location.hash) location.hash = `#/${DEFAULT_ROUTE}`;
else route();
