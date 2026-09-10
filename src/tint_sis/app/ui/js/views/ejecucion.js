import { api } from "../api.js";
import { h, card, btn, bar } from "../dom.js";

function fmt(seg) {
  const m = String(Math.floor(seg / 60)).padStart(2, "0");
  const s = String(seg % 60).padStart(2, "0");
  return `${m}:${s}`;
}

export async function render(view, { navigate }) {
  view.append(h("h1", { class: "view__title" }, "Ejecución / progreso"));
  view.append(
    h("p", { class: "muted" }, "El sistema está trabajando. El filtro tarda entre 12 y 15 min con las 4 tiendas.")
  );

  const globalLbl = h("h2", { class: "section__title" }, "0%");
  const globalBar = bar(0);
  view.append(card(globalLbl, globalBar));

  const perStore = card(h("h2", { class: "section__title" }, "Progreso por tienda"));
  view.append(perStore);
  const storeRows = new Map(); // grupo -> {fill, pct, txt}

  const logBox = h("div", { class: "log" });
  view.append(logBox);
  let logLen = 0;

  const footer = h("div", { class: "row" });
  view.append(footer);
  const cancelBtn = btn("Cancelar", {
    onClick: async () => {
      cancelBtn.disabled = true;
      cancelBtn.textContent = "Cancelando…";
      try {
        await api.runCancel();
      } catch (e) {
        cancelBtn.disabled = false;
        cancelBtn.textContent = "Cancelar";
      }
    },
  });
  footer.append(cancelBtn);

  let timer = null;

  function ensureStoreRow(grupo) {
    if (storeRows.has(grupo)) return storeRows.get(grupo);
    const b = bar(0);
    const pct = h("span", { class: "mono" }, "0%");
    const txt = h("div", { class: "muted", style: "font-size:12px;min-height:14px" }, "");
    perStore.append(
      h(
        "div",
        { class: "store-block" },
        h(
          "div",
          { class: "store-block__head" },
          h("span", { style: "font-weight:500" }, grupo),
          pct
        ),
        b,
        txt
      )
    );
    const entry = { bar: b, fill: b.querySelector(".bar__fill"), pct, txt };
    storeRows.set(grupo, entry);
    return entry;
  }

  async function tick() {
    let snap;
    try {
      snap = await api.runCurrent();
    } catch (e) {
      return;
    }

    globalLbl.textContent = `${snap.progreso_global}%  ·  ${fmt(snap.transcurrido_seg)} transcurrido`;
    globalBar.querySelector(".bar__fill").style.width = `${snap.progreso_global}%`;

    for (const t of snap.tiendas || []) {
      const row = ensureStoreRow(t.grupo);
      row.fill.style.width = `${t.progreso}%`;
      row.pct.textContent = `${t.progreso}%`;
      row.txt.textContent = t.texto || "";
      const completa = t.progreso >= 100;
      row.bar.classList.toggle("bar--done", completa);
      row.bar.classList.toggle("bar--working", !completa && (t.texto || "").startsWith("guardando"));
    }

    for (let i = logLen; i < (snap.log || []).length; i++) {
      logBox.append(h("div", { class: "log__line" }, snap.log[i]));
    }
    logLen = (snap.log || []).length;
    logBox.scrollTop = logBox.scrollHeight;

    if (snap.estado === "ok") {
      clearInterval(timer);
      timer = null;
      footer.replaceChildren(
        btn("Ver resultados", { variant: "primary", onClick: () => navigate("resultados") })
      );
    } else if (snap.estado === "cancelado") {
      clearInterval(timer);
      timer = null;
      view.append(
        h(
          "div",
          { class: "banner banner--info" },
          "Ciclo cancelado. Las tiendas que ya habían terminado quedaron en data/output/xData/; el resto no se generó."
        )
      );
      footer.replaceChildren(
        btn("Volver a Nuevo ciclo", { variant: "primary", onClick: () => navigate("nuevo-ciclo") })
      );
    } else if (snap.estado === "error") {
      clearInterval(timer);
      timer = null;
      view.append(
        h("div", { class: "banner banner--error" }, "La corrida falló."),
        h("pre", { class: "log", style: "white-space:pre-wrap" }, snap.error || "sin detalle")
      );
      footer.replaceChildren(btn("Volver", { onClick: () => navigate("nuevo-ciclo") }));
    }
  }

  await tick();
  timer = setInterval(tick, 1000);
  return () => { if (timer) clearInterval(timer); };
}
