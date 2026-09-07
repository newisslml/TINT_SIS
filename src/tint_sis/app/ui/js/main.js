import { api } from "./api.js";
import { h, clear } from "./dom.js";
import * as inicio from "./views/inicio.js";
import * as nuevoCiclo from "./views/nuevo_ciclo.js";
import * as ejecucion from "./views/ejecucion.js";
import * as resultados from "./views/resultados.js";
import * as configuracion from "./views/configuracion.js";

const ROUTES = {
  inicio,
  "nuevo-ciclo": nuevoCiclo,
  ejecucion,
  resultados,
  configuracion,
  historial: soon("Historial", "Auditoría y re-descarga de corridas anteriores. Llega en la v2."),
  homologos: soon("Homólogos (editor)", "Editar qué ID_TINT lleva cada tienda sin abrir Excel. Llega en la v2."),
  advertencias: soon("Advertencias", "Qué quedó afuera del ciclo y por qué. En la v1 puede vivir dentro de Resultados."),
};

function soon(title, texto) {
  return {
    async render(view) {
      view.append(
        h("h1", { class: "view__title" }, title),
        h("p", { class: "soon-view" }, texto)
      );
    },
  };
}

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

let activeCleanup = null;

async function route() {
  const name = currentRoute();
  setActiveNav(name);
  if (typeof activeCleanup === "function") {
    try { activeCleanup(); } catch (e) {}
    activeCleanup = null;
  }
  clear(viewEl);
  try {
    activeCleanup = (await ROUTES[name].render(viewEl, { navigate })) || null;
  } catch (err) {
    viewEl.append(h("div", { class: "banner banner--error" }, `Error cargando la vista: ${err.message}`));
  }
  viewEl.scrollTop = 0;
}

export function navigate(name) {
  location.hash = `#/${name}`;
}

window.addEventListener("hashchange", route);
renderStrip();
if (!location.hash) location.hash = `#/${DEFAULT_ROUTE}`;
else route();
