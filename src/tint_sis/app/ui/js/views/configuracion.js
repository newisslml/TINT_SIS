import { api } from "../api.js";
import { h, card, btn } from "../dom.js";

const GRUPOS_CONOCIDOS = ["MP14", "MP12", "Tiendas 14", "Tiendas 12"];

export async function render(view) {
  const cfg = await api.config();

  view.append(h("h1", { class: "view__title" }, "Configuración"));
  view.append(h("p", { class: "muted" }, "v1 mínimo: carpeta de trabajo + tiendas habilitadas."));

  // ---------- rutas ----------
  const rutaInputs = {};
  const rutaRow = (key, label) => {
    const input = h("input", {
      type: "text",
      value: cfg[key] || "",
      style: "flex:1;font-family:var(--font-mono);font-size:13px;padding:6px 8px;border:1px solid var(--linea);border-radius:6px",
    });
    rutaInputs[key] = input;
    return h(
      "div",
      { class: "row", style: "align-items:center" },
      h("span", { style: "width:150px;font-weight:500" }, label),
      input
    );
  };

  view.append(
    card(
      h("h2", { class: "section__title" }, "Carpeta de trabajo"),
      rutaRow("input_dir", "Entrada"),
      rutaRow("output_dir", "Salida (base)"),
      h("p", { class: "muted", style: "font-size:12px;margin:0" }, "Los finales se guardan por software: <salida>/xData/…"),
      rutaRow("db_path", "Base de datos")
    )
  );

  // ---------- tiendas ----------
  const habilitadas = new Set(cfg.enabled_grupos || []);
  const checks = GRUPOS_CONOCIDOS.map((g) => {
    const input = h("input", { type: "checkbox" });
    if (habilitadas.has(g)) input.checked = true;
    input.dataset.grupo = g;
    return h("label", {}, input, g);
  });
  view.append(
    card(
      h("h2", { class: "section__title" }, "Tiendas habilitadas"),
      h("div", { class: "checklist" }, ...checks)
    )
  );

  // ---------- convención de nombres ----------
  const masterInput = h("input", {
    type: "text",
    value: cfg.homologos_master_name || "",
    style: "flex:1;font-family:var(--font-mono);font-size:13px;padding:6px 8px;border:1px solid var(--linea);border-radius:6px",
  });
  const globInput = h("input", {
    type: "text",
    value: cfg.expert_glob || "",
    style: "flex:1;font-family:var(--font-mono);font-size:13px;padding:6px 8px;border:1px solid var(--linea);border-radius:6px",
  });
  view.append(
    card(
      h("h2", { class: "section__title" }, "Convención de nombres"),
      h("div", { class: "row", style: "align-items:center" }, h("span", { style: "width:150px;font-weight:500" }, "Homólogos maestro"), masterInput),
      h("div", { class: "row", style: "align-items:center" }, h("span", { style: "width:150px;font-weight:500" }, "Patrón del experto"), globInput)
    )
  );

  // ---------- guardar ----------
  const msg = h("span", { class: "muted" });
  view.append(
    h(
      "div",
      { class: "row", style: "align-items:center" },
      btn("Guardar", {
        variant: "primary",
        onClick: async () => {
          const nuevo = {
            input_dir: rutaInputs.input_dir.value.trim(),
            output_dir: rutaInputs.output_dir.value.trim(),
            db_path: rutaInputs.db_path.value.trim(),
            enabled_grupos: checks.filter((l) => l.querySelector("input").checked).map((l) => l.querySelector("input").dataset.grupo),
            homologos_master_name: masterInput.value.trim(),
            expert_glob: globInput.value.trim(),
          };
          try {
            const res = await api.saveConfig(nuevo);
            msg.textContent = `Guardado en ${res.archivo}`;
          } catch (e) {
            msg.textContent = "No se pudo guardar: " + e.message;
          }
        },
      }),
      msg
    )
  );

  view.append(
    h(
      "p",
      { class: "muted", style: "font-size:13px" },
      "v2: tabla de softwares / máquinas (nombre, formato, habilitado, carpeta de entrega) + nombres esperados por software."
    )
  );
}
