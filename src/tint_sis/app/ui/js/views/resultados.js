import { api } from "../api.js";
import { h, numcard, tabla } from "../dom.js";
import { listaAdvertencias } from "../advertencias.js";

const linklike = (label, onClick) => h("button", { class: "linklike", onclick: onClick }, label);
const abrir = (ruta, modo) => api.reveal(ruta, modo).catch((e) => alert("No se pudo abrir: " + e.message));

export async function render(view) {
  const data = await api.resultados();
  const r = data.resumen;

  view.append(h("h1", { class: "view__title" }, "Resultados"));
  view.append(h("p", { class: "muted" }, data.fecha ? `Ciclo del ${data.fecha}. Revisá y entregá lo generado.` : "Revisá y entregá lo generado."));

  const tituloAvisos = h("h2", { class: "section__title" }, `Advertencias (${r.advertencias})`);
  const nAvisos = numcard(r.advertencias, "advertencias (ver abajo)");
  nAvisos.classList.add("numcard--link");
  if (r.advertencias > 0) nAvisos.classList.add("numcard--advertencia");
  nAvisos.addEventListener("click", () => tituloAvisos.scrollIntoView({ behavior: "smooth", block: "start" }));
  view.append(h("div", { class: "row" }, numcard(r.archivos, "archivos generados"), numcard(r.filas_totales, "filas totales"), nAvisos));

  for (const g of data.grupos) {
    view.append(h("h2", { class: "section__title" }, g.titulo));
    view.append(
      tabla(
        [
          { label: "Salida", w: "2fr" },
          { label: "Tipo", w: "80px" },
          { label: "Filas", w: "120px" },
          { label: "Acciones", w: "170px" },
        ],
        g.salidas.map((s) => [
          h("div", { class: "mono" }, s.salida),
          s.tipo,
          h("div", { class: "mono" }, s.filas),
          s.existe === false
            ? h("span", { class: "muted", style: "font-size:12px" }, "no disponible")
            : h(
                "div",
                { class: "row", style: "gap:14px" },
                linklike("Abrir", () => abrir(s.ruta, "archivo")),
                linklike("Carpeta", () => abrir(s.ruta, "carpeta"))
              ),
        ])
      )
    );
  }

  // qué quedó afuera del ciclo y por qué (productos que no están en la tabla,
  // expertos que faltan, tiendas sin productos…)
  view.append(tituloAvisos);
  view.append(listaAdvertencias(r.advertencias === "-" ? null : data.advertencias));
}
