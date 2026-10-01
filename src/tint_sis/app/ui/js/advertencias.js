import { h } from "./dom.js";

// Advertencias de un ciclo ([{texto, detalle}], las guarda el ciclo en la base):
// una por renglón, numeradas. Si nombra productos (detalle), la lista completa
// va debajo; si es larga queda plegada. `null` = ciclo de una versión anterior,
// que no guardaba sus advertencias.
const DETALLE_VISIBLE = 8;

export function listaAdvertencias(advertencias) {
  if (advertencias == null) {
    return h(
      "p",
      { class: "muted", style: "margin:0;font-size:13px" },
      "Este ciclo se ejecutó con una versión anterior de TINT_SIS: sus advertencias no quedaron guardadas."
    );
  }
  if (!advertencias.length) {
    return h("div", { class: "row", style: "align-items:center;gap:10px" }, h("span", { class: "tag tag--ok" }, "Sin advertencias"), h("span", { class: "muted", style: "font-size:13px" }, "Todo lo que traían los expertos se entregó según la tabla de productos."));
  }
  return h(
    "ol",
    { class: "avisos" },
    ...advertencias.map((a, i) =>
      h(
        "li",
        { class: "aviso" },
        h("span", { class: "aviso__num mono" }, String(i + 1)),
        h("div", { class: "aviso__cuerpo" }, h("div", { class: "aviso__texto" }, a.texto), detalle(a.detalle || []))
      )
    )
  );
}

function detalle(items) {
  if (!items.length) return null;
  const lista = h("ul", { class: "aviso__detalle" }, ...items.map((d) => h("li", {}, d)));
  if (items.length <= DETALLE_VISIBLE) return lista;
  return h("details", { class: "aviso__plegable" }, h("summary", {}, `Ver los ${items.length}`), lista);
}
