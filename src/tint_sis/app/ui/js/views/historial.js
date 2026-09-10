import { api } from "../api.js";
import { h, card, btn, tag, tabla } from "../dom.js";

const linklike = (label, onClick) => h("button", { class: "linklike", onclick: onClick });

const abrir = (ruta, modo) => api.reveal(ruta, modo).catch((e) => alert("No se pudo abrir: " + e.message));

function estadoBackup(disp, total) {
  if (total === 0) return tag("advertencia", "sin archivos");
  if (disp === 0) return tag("error", "backup no disponible");
  if (disp < total) return tag("advertencia", `backup parcial (${disp}/${total})`);
  return tag("ok", "backup completo");
}

function cicloCard(c) {
  const detalle = h("div", { style: "display:flex;flex-direction:column;gap:16px;margin-top:4px" });
  detalle.hidden = true;

  for (const g of c.grupos) {
    detalle.append(
      h("h2", { class: "section__title", style: "font-size:15px" }, g.titulo),
      tabla(
        [
          { label: "Archivo", w: "2fr" },
          { label: "Tipo", w: "70px" },
          { label: "Filas", w: "110px" },
          { label: "Backup", w: "170px" },
        ],
        g.salidas.map((s) => [
          h("div", { class: "mono" }, s.salida),
          s.tipo,
          h("div", { class: "mono" }, s.filas),
          s.existe
            ? h(
                "div",
                { class: "row", style: "gap:14px" },
                linklike("Abrir", () => abrir(s.ruta, "archivo")),
                linklike("Carpeta", () => abrir(s.ruta, "carpeta"))
              )
            : h("span", { class: "muted", style: "font-size:12px" }, "no disponible"),
        ])
      )
    );
  }

  const toggle = btn("Ver archivos", {
    onClick: () => {
      detalle.hidden = !detalle.hidden;
      toggle.textContent = detalle.hidden ? "Ver archivos" : "Ocultar archivos";
      toggle.classList.toggle("is-active", !detalle.hidden);
    },
  });
  toggle.classList.add("btn--naranja");

  const abrirCarpeta =
    c.carpeta && c.carpeta_existe
      ? btn("Abrir carpeta del backup", { onClick: () => abrir(c.carpeta, "carpeta") })
      : null;
  if (abrirCarpeta) abrirCarpeta.classList.add("btn--naranja");

  const carpetaLbl = c.carpeta
    ? h(
        "span",
        { class: "mono", style: "font-size:12px;color:var(--ink-muted)" },
        (c.carpeta_existe ? "📁 " : "📁 (no está en disco) ") + c.carpeta
      )
    : null;

  return card(
    h(
      "div",
      { class: "row row--between" },
      h(
        "div",
        { class: "stack" },
        h("span", { class: "mono", style: "font-size:15px" }, c.fecha),
        carpetaLbl
      ),
      h(
        "div",
        { class: "row", style: "align-items:center;gap:12px" },
        estadoBackup(c.n_disponibles, c.n_archivos),
        h("span", { class: "muted", style: "font-size:12px" }, `${c.n_archivos} archivos · ${c.filas_totales} filas`)
      )
    ),
    h("div", { class: "row", style: "gap:12px;flex-wrap:wrap" }, abrirCarpeta, toggle),
    detalle
  );
}

export async function render(view) {
  const { ciclos } = await api.historial();

  view.append(h("h1", { class: "view__title" }, "Historial"));
  view.append(
    h("p", { class: "muted" }, "Ciclos ejecutados y su backup en disco. Cada ciclo abre directo la carpeta local donde quedaron sus archivos; “Abrir” usa la app por defecto y “Carpeta” los muestra en el explorador.")
  );

  if (!ciclos.length) {
    view.append(h("p", { class: "soon-view" }, "Todavía no se ejecutó ningún ciclo."));
    return;
  }

  for (const c of ciclos) view.append(cicloCard(c));
}
