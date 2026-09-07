import { api } from "../api.js";
import { h, card, numcard, btn, tabla } from "../dom.js";

export async function render(view, { navigate }) {
  const data = await api.resultados();
  const r = data.resumen;

  view.append(h("h1", { class: "view__title" }, "Resultados"));
  view.append(h("p", { class: "muted" }, "Revisá y entregá lo generado."));

  view.append(
    h(
      "div",
      { class: "row" },
      numcard(r.archivos, "archivos generados"),
      numcard(r.filas_totales, "filas totales"),
      numcard(r.advertencias, "advertencias")
    )
  );

  for (const g of data.grupos) {
    view.append(h("h2", { class: "section__title" }, g.titulo));
    view.append(
      tabla(
        [
          { label: "Salida", w: "2fr" },
          { label: "Tipo", w: "80px" },
          { label: "Filas", w: "120px" },
          { label: "Acciones", w: "1.4fr" },
        ],
        g.salidas.map((s) => [
          h("div", { class: "mono" }, s.salida),
          s.tipo,
          h("div", { class: "mono" }, s.filas),
          h("span", { class: "muted" }, "Abrir · Carpeta · Previsualizar · Copiar a entrega"),
        ])
      )
    );
  }

  view.append(
    h(
      "button",
      { class: "linklike", onclick: () => navigate("advertencias") },
      `Ver advertencias y validación (${r.advertencias})`
    )
  );
}
