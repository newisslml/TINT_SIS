import { api } from "../api.js";
import { h, card, btn } from "../dom.js";

const GRUPOS_CONOCIDOS = ["MP14", "MP12", "Tiendas 14", "Tiendas 12"];

// Pen (equivalente al icono "pen-icon" de itshover; acá va como SVG inline porque
// la app no usa React). Se anima al pasar el mouse por el botón Editar.
const PENCIL_SVG = `
<svg class="icon-pencil" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
     stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
  <path d="M17 3a2.85 2.83 0 0 1 4 4L7.5 20.5 2 22l1.5 -5.5 13.5 -13.5z"/>
  <path d="M15 5l4 4"/>
</svg>`;

export async function render(view) {
  const cfg = await api.config();

  view.append(h("h1", { class: "view__title" }, "Configuración"));
  view.append(h("p", { class: "muted" }, "v1 mínimo: carpeta de trabajo + tiendas habilitadas."));

  // guardar() se define más abajo (necesita checks/inputs); se referencia antes
  // en el handler de Enter de cada ruta.
  let guardar = () => {};

  // ---------- rutas ----------
  // Se muestran igual que antes pero bloqueadas: cada fila tiene su propio botón
  // "Editar" (lápiz) para desbloquear solo esa ruta. Enter guarda los cambios.
  const rutaInputs = {};
  const rutaRow = (key, label) => {
    const input = h("input", {
      type: "text",
      value: cfg[key] || "",
      readonly: "",
      class: "ruta-input",
      style: "flex:1;font-family:var(--font-mono);font-size:13px;padding:6px 8px;border:1px solid var(--linea);border-radius:6px",
    });
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        guardar();
      }
    });
    rutaInputs[key] = input;

    const edit = btn("Editar", {
      onClick: () => {
        const desbloquear = input.readOnly;
        input.readOnly = !desbloquear;
        input.classList.toggle("is-editable", desbloquear);
        edit.classList.toggle("is-active", desbloquear);
        edit.lastChild.textContent = desbloquear ? "Bloquear" : "Editar";
        if (desbloquear) input.focus();
      },
    });
    edit.classList.add("btn--edit");
    edit.setAttribute("title", `Editar ${label}`);
    edit.insertAdjacentHTML("afterbegin", PENCIL_SVG);

    return h(
      "div",
      { class: "row", style: "align-items:center" },
      h("span", { style: "width:150px;font-weight:500" }, label),
      input,
      edit
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
  guardar = async () => {
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
  };

  const guardarBtn = btn("Guardar", { variant: "primary", onClick: guardar });
  guardarBtn.classList.add("btn--guardar");
  view.append(h("div", { class: "row", style: "align-items:center" }, guardarBtn, msg));

  view.append(
    h(
      "p",
      { class: "muted", style: "font-size:13px" },
      "v2: tabla de softwares / máquinas (nombre, formato, habilitado, carpeta de entrega) + nombres esperados por software."
    )
  );
}
