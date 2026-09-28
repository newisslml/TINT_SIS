import { api } from "../api.js";
import { h, btn, tag, tabla, modal } from "../dom.js";
import { crearPreparacion, PREPARACION_PENDIENTE } from "../preparacion.js";

// Icono "cohete" para el botón Ejecutar. viewBox 0 0 32 32; las partes con la
// clase .rocket-upper despegan juntas y .rocket-flame es la llama del empuje.
const ROCKET_SVG = `
<svg class="rocket-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"
     fill="none" stroke="currentColor" stroke-width="1.5" stroke-miterlimit="10" aria-hidden="true">
  <path class="rocket-fin-left rocket-upper" d="m13.299,9h-3.891c-.892,0-1.738.397-2.308,1.083l-5.1,6.139,6.31,1.51"/>
  <path class="rocket-fin-bottom rocket-upper" d="m23,18.701v3.891c0,.892-.397,1.738-1.083,2.308l-6.139,5.1-1.51-6.31"/>
  <path class="rocket-body rocket-upper" d="m14.268,23.69c7.986-2.194,14.642-9.015,15.732-21.69-12.675,1.09-19.496,7.746-21.69,15.732l5.958,5.958Z"/>
  <path class="rocket-trajectory rocket-upper" d="m19,5c4.111,1.389,6.778,4.056,8,8" stroke-linecap="round"/>
  <circle class="rocket-window rocket-upper" cx="19" cy="13" r="2" fill="currentColor"/>
  <path class="rocket-flame" d="m2,30s.707-4.95,2.121-6.364c1.172-1.172,3.071-1.172,4.243,0s1.172,3.071,0,4.243c-1.414,1.414-6.364,2.121-6.364,2.121Z"/>
</svg>`;

// Icono "archivo con líneas" para el botón de agregar archivo al final de la vista.
// .file-fold y .file-lines se dibujan con stroke-dashoffset al hacer clic.
const FILE_SVG = `
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
     stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
  <path d="M17 21h-10a2 2 0 0 1 -2 -2v-14a2 2 0 0 1 2 -2h7l5 5v11a2 2 0 0 1 -2 2z"/>
  <path class="file-fold" pathLength="1" d="M14 3v4a1 1 0 0 0 1 1h4"/>
  <path class="file-lines" pathLength="1" d="M9 17h6"/>
  <path class="file-lines" pathLength="1" d="M9 13h6"/>
</svg>`;

const ESTADO_TAG = {
  ok: () => tag("ok", "OK"),
  "no-habilitado": () => tag("no-habilitado", "Se omite"),
  desactivado: () => tag("desactivado", "Desactivado"),
  error: () => tag("error", "Revisar"),
};

const FORMATO = { csv: "CSV", excel: "Excel" };

// Punto con el color del experto ("Experto 2" -> --experto-2); gris si no hay token.
// Fecha con que salen los archivos del experto (<tienda>_ready_<fecha>); si el
// nombre del experto no la trae, es su fecha de modificación.
const fechaSalida = (e) =>
  e.fecha ? `_ready_${e.fecha}` + (e.fecha_del_nombre ? "" : " (fecha de modificación: el nombre no trae fecha)") : "";

const expertoDot = (label) => {
  const n = (String(label).match(/\d+/) || [""])[0];
  return h("span", { class: "experto-dot", style: `background:var(--experto-${n}, var(--no-habilitado))`, "aria-hidden": "true" });
};

// Resumen que se confirma antes de ejecutar: tiendas que se filtran, expertos
// activos (archivo -> softwares -> tiendas) y lo que queda afuera del ciclo.
function resumenCiclo(d) {
  const activos = d.expertos.filter((e) => e.estado === "ok");
  const afuera = d.expertos.filter((e) => e.estado !== "ok");
  const tiendas = [...new Set(activos.flatMap((e) => e.detalle.flatMap((s) => s.tiendas)))];
  const nArchivos = activos.reduce((n, e) => n + e.detalle.reduce((m, s) => m + s.tiendas.length, 0), 0);
  const bloque = (label, ...contenido) =>
    h("div", { class: "resumen__bloque" }, h("div", { class: "resumen__label" }, label), ...contenido);

  return h(
    "div",
    { class: "resumen" },
    h("h2", { class: "resumen__titulo" }, "Resumen del nuevo ciclo"),
    bloque(
      `Tiendas que se filtran (${tiendas.length})`,
      h("div", { class: "resumen__chips" }, ...tiendas.map((t) => h("span", { class: "chip chip--ok" }, t)))
    ),
    bloque(
      `Expertos activos (${activos.length})`,
      ...activos.map((e) =>
        h(
          "div",
          { class: "resumen__experto" },
          h("div", {}, expertoDot(e.label), h("strong", {}, e.label), "  ·  ", h("span", { class: "mono" }, e.archivo)),
          h("div", { class: "resumen__fecha" }, "Archivos ", h("span", { class: "mono" }, fechaSalida(e))),
          h(
            "ul",
            { class: "resumen__lista" },
            ...e.detalle.map((s) =>
              h("li", {}, h("span", { class: "mono" }, s.nombre), ` → ${s.tiendas.join(", ")} (${FORMATO[s.formato] || s.formato})`)
            )
          )
        )
      )
    ),
    afuera.length
      ? bloque(
          "No entran en este ciclo",
          h(
            "ul",
            { class: "resumen__lista" },
            ...afuera.map((e) =>
              h(
                "li",
                {},
                `${e.label}: ${e.estado === "desactivado" ? "desactivado en Configuración" : "falta el archivo"}`,
                ` (se omiten ${e.softwares.join(", ")})`
              )
            )
          )
        )
      : null,
    h("div", { class: "resumen__pie" }, `Se generan ${nArchivos} archivos en `, h("span", { class: "mono" }, d.salida || "-"))
  );
}

export async function render(view, { navigate }) {
  let data = await api.preview();

  view.append(h("h1", { class: "view__title" }, "Nuevo ciclo — cargar y revisar"));
  view.append(
    h(
      "p",
      { class: "muted", style: "margin:0" },
      "Arrastrá el archivo maestro que envía tintometría (el experto padre completo). TINT_SIS lo compara con el " +
        "ciclo anterior, suma los productos nuevos a la tabla de productos y genera Experto 1, 2 y 3; después " +
        "revisás los expertos del ciclo y ejecutás."
    )
  );

  // ---------- dropzone real ----------
  const fileInput = h("input", { type: "file", accept: ".xlsx,.xlsm", style: "display:none" });

  // icono "archivo" al pie del dropzone; el clic dibuja los trazos y burbujea al
  // dropzone (que abre el selector de archivos)
  const addIcon = h("button", {
    class: "add-file-icon",
    type: "button",
    title: "Agregar un archivo",
    onclick: () => {
      addIcon.classList.remove("is-drawing");
      void addIcon.offsetWidth; // fuerza reflow para reiniciar la animación
      addIcon.classList.add("is-drawing");
    },
  });
  addIcon.insertAdjacentHTML("afterbegin", FILE_SVG);

  const dz = h(
    "div",
    { class: "dropzone" },
    h("div", { style: "font-weight:600;color:var(--ink)" }, "Arrastrá acá el archivo maestro (.xlsx)"),
    h(
      "div",
      {},
      "o hacé clic para elegirlo — se analiza en alrededor de un minuto. Un Experto_1/2/3 o la tabla de productos se copian tal cual a la carpeta de entrada."
    ),
    addIcon,
    fileInput
  );
  const refresh = async () => {
    data = await api.preview();
    rerender();
  };

  // ---------- archivo maestro -> Experto 1, 2 y 3 ----------
  // Mientras hay un maestro en curso (analizándose, analizado sin preparar o
  // preparándose) no se ejecuta el ciclo; al quedar listos los expertos se relee
  // la carpeta de entrada.
  let estadoMaestro = "idle";
  let dyn = null; // contexto + tablas + acciones (se arma después del primer estado del maestro)
  const prep = crearPreparacion({
    alCambiarEstado: async (estado) => {
      estadoMaestro = estado;
      if (estado === "listo") data = await api.preview();
      if (dyn) rerender();
    },
  });

  const upload = async (file) => {
    if (!file) return;
    dz.classList.add("is-busy");
    try {
      const res = await api.uploadInput(file);
      if (res.tipo === "maestro") {
        prep.mostrar(res.preparar);
      } else {
        data = res.preview;
        rerender();
      }
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
  view.append(dz, prep.el);

  // ---------- contexto + tabla + acciones (rerender) ----------
  await prep.refrescar();
  dyn = h("div", { style: "display:flex;flex-direction:column;gap:24px" });
  view.append(dyn);

  function rerender() {
    dyn.replaceChildren();
    const maestroPendiente = PREPARACION_PENDIENTE.has(estadoMaestro);

    dyn.append(
      h(
        "div",
        { class: "row", style: "align-items:center" },
        h("span", { class: "muted" }, "Tabla de productos:"),
        h("span", { class: "mono" }, data.productos_activo || "— (falta)"),
        ...data.tiendas_habilitadas.map((t) => h("span", { class: "chip chip--ok" }, t))
      )
    );

    // Un renglón por experto: qué archivo se usa este ciclo y a qué softwares va.
    dyn.append(h("h2", { class: "section__title" }, "Expertos del ciclo"));
    dyn.append(
      tabla(
        [
          { label: "Experto", w: "1.4fr" },
          { label: "Softwares destino", w: "1.6fr" },
          { label: "Estado", w: "150px" },
        ],
        data.expertos.length
          ? data.expertos.map((e) => [
              h(
                "div",
                {},
                h("div", { style: "font-weight:500" }, expertoDot(e.label), e.label),
                h("div", { class: "mono muted", style: "font-size:12px" }, e.archivo || "falta en la carpeta de entrada"),
                e.fecha ? h("div", { class: "muted", style: "font-size:12px" }, "Salen como ", h("span", { class: "mono" }, fechaSalida(e))) : null
              ),
              e.softwares.join(", "),
              e.estado === "ok"
                ? tag("ok", "OK")
                : e.estado === "desactivado"
                  ? tag("desactivado", "Desactivado")
                  : tag("error", "Falta"),
            ])
          : [[h("span", { class: "muted" }, "Ningún software habilitado."), "", ""]]
      )
    );

    const COLS = [
      { label: "Archivo", w: "2fr" },
      { label: "Software / destino", w: "1fr" },
      { label: "Flujo", w: "1.2fr" },
      { label: "Estado", w: "150px" },
    ];
    const fila = (a) => [
      h("div", {}, h("div", { class: "mono" }, a.archivo), h("div", { class: "muted", style: "font-size:12px" }, a.detalle)),
      a.software,
      a.flujo,
      (ESTADO_TAG[a.estado] || (() => a.estado))(),
    ];

    dyn.append(h("h2", { class: "section__title" }, "Archivos en la carpeta de entrada"));
    dyn.append(
      tabla(
        COLS,
        data.archivos.length
          ? data.archivos.map(fila)
          : [[h("span", { class: "muted" }, "La carpeta de entrada está vacía."), "", "", ""]]
      )
    );

    for (const b of data.bloqueantes || []) {
      dyn.append(h("div", { class: "banner banner--advertencia" }, b));
    }
    for (const a of data.advertencias || []) {
      dyn.append(h("div", { class: "banner banner--info" }, a));
    }
    if (maestroPendiente) {
      dyn.append(
        h(
          "div",
          { class: "banner banner--advertencia" },
          estadoMaestro === "analizado"
            ? "Hay un archivo maestro analizado: prepará los expertos (o descartalo) arriba antes de ejecutar el ciclo."
            : "Se está procesando el archivo maestro: el ciclo se puede ejecutar cuando estén listos los expertos."
        )
      );
    }

    const ejecutar = btn("Ejecutar", {
      variant: "primary",
      disabled: !data.puede_ejecutar || maestroPendiente,
      onClick: async () => {
        if (ejecutar.classList.contains("is-launching")) return;
        // se relee la carpeta por si cambio algo desde que se abrio la vista
        data = await api.preview();
        if (!data.puede_ejecutar) {
          rerender();
          return;
        }
        const eleccion = await modal(
          resumenCiclo(data),
          [
            { id: "cancelar", label: "Cancelar", variant: "secondary" },
            { id: "ejecutar", label: "Ejecutar ciclo", variant: "primary" },
          ],
          { amplio: true }
        );
        if (eleccion !== "ejecutar") {
          rerender();
          return;
        }
        ejecutar.classList.add("is-launching");
        try {
          await api.runStart();
          // dejamos que el cohete despegue antes de cambiar de vista
          await new Promise((r) => setTimeout(r, 1150));
          navigate("ejecucion");
        } catch (e) {
          ejecutar.classList.remove("is-launching");
          if (/corrida en curso/i.test(e.message)) {
            const r = await modal("Ya hay una corrida en curso.", [
              { id: "ir", label: "Ir al proceso actual", variant: "primary" },
              { id: "ok", label: "Aceptar", variant: "secondary" },
            ]);
            if (r === "ir") navigate("ejecucion");
          } else {
            alert("No se pudo iniciar: " + e.message);
          }
        }
      },
    });
    ejecutar.classList.add("btn--ejecutar");
    ejecutar.insertAdjacentHTML("afterbegin", ROCKET_SVG);

    dyn.append(
      h(
        "div",
        { class: "row", style: "align-items:center" },
        btn("Abrir carpeta de entrada", { onClick: () => api.openInput().catch((e) => alert(e.message)) }),
        btn("Actualizar", { onClick: refresh }),
        ejecutar
      )
    );
  }

  rerender();
  return () => prep.destruir();
}
