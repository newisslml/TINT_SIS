import { api } from "../api.js";
import { h, btn, tag, tabla } from "../dom.js";

const ESTADO_TAG = {
  ok: () => tag("ok", "OK"),
  "no-habilitado": () => tag("no-habilitado", "Se omite"),
  error: () => tag("error", "Nombre no reconocido"),
};

export async function render(view, { navigate }) {
  let data = await api.preview();

  view.append(h("h1", { class: "view__title" }, "Nuevo ciclo — cargar y revisar"));

  // ---------- dropzone real ----------
  const fileInput = h("input", { type: "file", accept: ".xlsx", style: "display:none" });
  const dz = h(
    "div",
    { class: "dropzone" },
    h("div", { style: "font-weight:600;color:var(--ink)" }, "Arrastrá un archivo .xlsx acá"),
    h("div", {}, "o hacé clic para elegirlo — se copia a la carpeta de entrada"),
    fileInput
  );
  const refresh = async () => {
    data = await api.preview();
    rerender();
  };
  const upload = async (file) => {
    if (!file) return;
    dz.classList.add("is-busy");
    try {
      const res = await api.uploadInput(file);
      data = res.preview;
      rerender();
    } catch (e) {
      alert("No se pudo subir el archivo: " + e.message);
    } finally {
      dz.classList.remove("is-busy");
    }
  };
  dz.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", () => upload(fileInput.files[0]));
  dz.addEventListener("dragover", (e) => {
    e.preventDefault();
    dz.classList.add("is-over");
  });
  dz.addEventListener("dragleave", () => dz.classList.remove("is-over"));
  dz.addEventListener("drop", (e) => {
    e.preventDefault();
    dz.classList.remove("is-over");
    upload(e.dataTransfer.files[0]);
  });
  view.append(dz);

  // ---------- contexto + tabla + acciones (rerender) ----------
  const dyn = h("div", { style: "display:flex;flex-direction:column;gap:24px" });
  view.append(dyn);

  function rerender() {
    dyn.replaceChildren();

    dyn.append(
      h(
        "div",
        { class: "row", style: "align-items:center" },
        h("span", { class: "muted" }, "Homólogos activo:"),
        h("span", { class: "mono" }, data.homologos_activo || "— (falta)"),
        h("span", { class: "muted", style: "margin-left:12px" }, "Experto:"),
        h("span", { class: "mono" }, data.experto_activo || "— (falta)"),
        ...data.tiendas_habilitadas.map((t) => h("span", { class: "chip" }, t))
      )
    );

    dyn.append(
      tabla(
        [
          { label: "Archivo", w: "2fr" },
          { label: "Software / destino", w: "1fr" },
          { label: "Flujo", w: "1.2fr" },
          { label: "Estado", w: "150px" },
        ],
        data.archivos.length
          ? data.archivos.map((a) => [
              h("div", {}, h("div", { class: "mono" }, a.archivo), h("div", { class: "muted", style: "font-size:12px" }, a.detalle)),
              a.software,
              a.flujo,
              (ESTADO_TAG[a.estado] || (() => a.estado))(),
            ])
          : [[h("span", { class: "muted" }, "La carpeta de entrada está vacía."), "", "", ""]]
      )
    );

    for (const b of data.bloqueantes || []) {
      dyn.append(h("div", { class: "banner banner--advertencia" }, b));
    }

    dyn.append(
      h(
        "div",
        { class: "row", style: "align-items:center" },
        btn("Abrir carpeta de entrada", { onClick: () => api.openInput().catch((e) => alert(e.message)) }),
        btn("Actualizar", { onClick: refresh }),
        btn("Ejecutar", {
          variant: "primary",
          disabled: !data.puede_ejecutar,
          onClick: async () => {
            try {
              await api.runStart();
              navigate("ejecucion");
            } catch (e) {
              alert("No se pudo iniciar: " + e.message);
            }
          },
        })
      )
    );
  }

  rerender();
}
