import { api } from "../api.js";
import { h, card, btn, tabla } from "../dom.js";

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
  view.append(h("p", { class: "muted" }, "Carpeta de trabajo, tiendas habilitadas y nombres de los archivos de entrada."));

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
      h("p", { class: "muted", style: "font-size:12px;margin:0" }, "Los finales se guardan por software: <salida>/Archivos filtrados/<Software>/"),
      rutaRow("db_path", "Base de datos")
    )
  );

  // ---------- tiendas y expertos habilitados (interruptores on/off) ----------
  // Un switch es un checkbox real con la apariencia de .switch (app.css).
  const interruptor = (texto, activo, sub) => {
    const input = h("input", { type: "checkbox", class: "switch__input" });
    input.checked = activo;
    const el = h(
      "label",
      { class: "switch" },
      input,
      h("span", { class: "switch__track", "aria-hidden": "true" }),
      h("span", { class: "switch__estado", "aria-hidden": "true" }),
      h("span", { class: "switch__texto" }, h("span", {}, texto), sub ? h("span", { class: "switch__sub" }, sub) : null)
    );
    return { input, el };
  };

  const habilitadas = new Set(cfg.enabled_grupos || []);
  const tiendaSwitches = GRUPOS_CONOCIDOS.map((g) => ({ valor: g, ...interruptor(g, habilitadas.has(g)) }));
  view.append(
    card(
      h("h2", { class: "section__title" }, "Tiendas habilitadas"),
      h("div", { class: "switchlist" }, ...tiendaSwitches.map((s) => s.el))
    )
  );

  const expertosActivos = new Set(cfg.expertos_habilitados || []);
  const softwaresDe = (experto) => (cfg.softwares || []).filter((s) => s.experto === experto).map((s) => s.nombre);
  const expertoSwitches = Object.keys(cfg.expertos || {}).map((e) => ({
    valor: e,
    ...interruptor(e, expertosActivos.has(e), softwaresDe(e).join(", ") || "sin softwares"),
  }));
  view.append(
    card(
      h("h2", { class: "section__title" }, "Expertos habilitados"),
      h(
        "p",
        { class: "muted", style: "font-size:12px;margin:0" },
        "El ciclo solo filtra los expertos encendidos; los softwares de un experto apagado no se generan."
      ),
      h("div", { class: "switchlist" }, ...expertoSwitches.map((s) => s.el))
    )
  );

  // ---------- convención de nombres ----------
  const inputStyle =
    "flex:1;font-family:var(--font-mono);font-size:13px;padding:6px 8px;border:1px solid var(--linea);border-radius:6px";
  const productosInput = h("input", { type: "text", value: cfg.productos_name || "", style: inputStyle });
  const masterInput = h("input", { type: "text", value: cfg.homologos_master_name || "", style: inputStyle });
  const globInputs = Object.entries(cfg.expertos || {}).map(([label, glob]) => {
    const input = h("input", { type: "text", value: glob, style: inputStyle });
    input.dataset.experto = label;
    return input;
  });
  const filaNombre = (label, input) =>
    h("div", { class: "row", style: "align-items:center" }, h("span", { style: "width:150px;font-weight:500" }, label), input);
  view.append(
    card(
      h("h2", { class: "section__title" }, "Convención de nombres"),
      filaNombre("Tabla de productos", productosInput),
      ...globInputs.map((input) => filaNombre(`Patrón ${input.dataset.experto}`, input)),
      filaNombre("Homólogos (anterior)", masterInput),
      h(
        "p",
        { class: "muted", style: "font-size:12px;margin:0" },
        "Si hay varios archivos de un mismo experto se usa el de fecha más nueva (_DD_MM_YYYY al final del nombre)."
      )
    )
  );

  // ---------- softwares (solo lectura; se editan en config.json) ----------
  view.append(
    card(
      h("h2", { class: "section__title" }, "Softwares"),
      tabla(
        [
          { label: "Software", w: "1.2fr" },
          { label: "Experto", w: "1fr" },
          { label: "Tiendas", w: "2fr" },
          { label: "Formato", w: "90px" },
        ],
        (cfg.softwares || []).map((s) => [
          h("span", { class: "mono" }, s.nombre),
          s.experto,
          s.tiendas.join(", "),
          s.formato === "csv" ? "CSV" : "Excel",
        ])
      ),
      h(
        "p",
        { class: "muted", style: "font-size:12px;margin:0" },
        "Cada software recibe sus archivos en <salida>/Archivos filtrados/<Software>/. Se editan en config.json."
      )
    )
  );

  // ---------- guardar ----------
  const msg = h("span", { class: "muted" });
  guardar = async () => {
    const nuevo = {
      input_dir: rutaInputs.input_dir.value.trim(),
      output_dir: rutaInputs.output_dir.value.trim(),
      db_path: rutaInputs.db_path.value.trim(),
      enabled_grupos: tiendaSwitches.filter((s) => s.input.checked).map((s) => s.valor),
      expertos_habilitados: expertoSwitches.filter((s) => s.input.checked).map((s) => s.valor),
      productos_name: productosInput.value.trim(),
      expertos: Object.fromEntries(globInputs.map((i) => [i.dataset.experto, i.value.trim()])),
      homologos_master_name: masterInput.value.trim(),
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
      "v2: editar desde la app la lista de softwares (formato, tiendas, carpeta de entrega) y la tabla de productos."
    )
  );
}
