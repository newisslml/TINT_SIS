import { api } from "../api.js";
import { h, card, numcard, btn } from "../dom.js";

export async function render(view, { navigate }) {
  const data = await api.inicio();
  const lc = data.ultimo_ciclo;

  view.append(h("h1", { class: "view__title" }, "Inicio"));
  view.append(h("p", { class: "muted" }, "Estado de un vistazo y entrada a un ciclo nuevo."));

  for (const a of data.alertas || []) {
    view.append(h("div", { class: `banner banner--${a.nivel}` }, a.texto));
  }

  view.append(
    card(
      h("h2", { class: "section__title" }, "Último ciclo"),
      h(
        "div",
        { class: "row" },
        h("div", { class: "stack" }, h("span", { class: "muted" }, "Fecha"), h("span", { class: "mono" }, lc.fecha)),
        h("div", { class: "stack" }, h("span", { class: "muted" }, "Experto usado"), h("span", { class: "mono" }, lc.experto))
      ),
      h(
        "div",
        { class: "row" },
        numcard(lc.archivos_generados, "archivos generados (_ready)"),
        numcard(lc.advertencias, "advertencias")
      )
    )
  );

  view.append(
    h(
      "div",
      { class: "row" },
      btn("Nuevo ciclo", { variant: "morado", onClick: () => navigate("nuevo-ciclo") }),
      btn("Ver resultados", { onClick: () => navigate("resultados") }),
      btn("Historial", { onClick: () => navigate("historial") }),
      btn("Configuración", { onClick: () => navigate("configuracion") })
    )
  );
}
