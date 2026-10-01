import { api } from "./api.js";
import { h, card, numcard, btn, tag, tabla, modal, bar } from "./dom.js";

// Panel del archivo maestro de tintometría dentro de "Nuevo ciclo". El maestro
// (el experto padre completo, formato Experto 1) se arrastra al dropzone de la
// vista; acá se sigue su análisis (compara con el ciclo anterior y la tabla de
// productos, no escribe nada), se deciden tiendas y nombres de los productos
// nuevos y se preparan Experto 1, 2 y 3 en la carpeta de entrada.

// Estados en los que no conviene ejecutar el ciclo todavía.
export const PREPARACION_PENDIENTE = new Set(["analizando", "preparando", "analizado"]);
const OCUPADO = new Set(["analizando", "preparando"]);

const miles = (n) => (typeof n === "number" ? n.toLocaleString("es-CL") : n ?? "-");
const fechaTxt = (f) => (f ? f.replaceAll("_", "/") : "-");
const linklike = (label, onClick) => h("button", { class: "linklike", onclick: onClick }, label);
const abrir = (ruta, modo) => api.reveal(ruta, modo).catch((e) => alert("No se pudo abrir: " + e.message));

function fmtSeg(seg) {
  return `${String(Math.floor(seg / 60)).padStart(2, "0")}:${String(seg % 60).padStart(2, "0")}`;
}

// "Sipamundo (7.902), Millennium (7.788), …" con las primeras `n` entradas
function topConteos(obj, n = 4) {
  const items = Object.entries(obj || {});
  const txt = items.slice(0, n).map(([k, v]) => `${k || "(vacío)"} (${miles(v)})`).join(", ");
  return items.length > n ? `${txt} y ${items.length - n} más` : txt;
}

// Devuelve {el, mostrar(snapshot), refrescar(), destruir()}. `alCambiarEstado`
// recibe el estado nuevo ("idle", "analizando", "analizado", "preparando",
// "listo", "error") cada vez que cambia.
export function crearPreparacion({ alCambiarEstado } = {}) {
  const el = h("div", { class: "preparacion" });
  let timer = null;
  let estadoPintado = null;
  let decisiones = {}; // clave -> {tiendas:Set, nombre_e2, nombre_e3}
  let progreso = null; // nodos del card de progreso (se actualizan sin re-render)

  function mostrar(s) {
    const ocupado = OCUPADO.has(s.estado);
    if (ocupado && progreso && estadoPintado === s.estado) {
      actualizarProgreso(s);
    } else if (s.estado !== estadoPintado || ocupado) {
      const cambio = s.estado !== estadoPintado;
      pintar(s);
      if (cambio && alCambiarEstado) alCambiarEstado(s.estado);
    }
    if (ocupado && !timer) timer = setInterval(refrescar, 1000);
    if (!ocupado && timer) {
      clearInterval(timer);
      timer = null;
    }
  }

  async function refrescar() {
    try {
      mostrar(await api.prepararEstado());
    } catch (e) {
      /* servicio caído: se reintenta en el próximo tick */
    }
  }

  async function reiniciar() {
    mostrar(await api.prepararReiniciar());
  }

  function pintar(s) {
    estadoPintado = s.estado;
    progreso = null;
    el.replaceChildren();
    if (s.estado === "idle") pintarUltima(s);
    else if (OCUPADO.has(s.estado)) pintarProgreso(s);
    else if (s.estado === "analizado") pintarAnalisis(s);
    else if (s.estado === "listo") pintarListo(s);
    else pintarError(s);
    el.hidden = !el.childElementCount;
  }

  // ---------- sin maestro en curso: la última preparación ----------
  function pintarUltima(s) {
    const u = s.ultimo;
    if (!u) return;
    el.append(
      h(
        "div",
        { class: "muted", style: "font-size:13px" },
        "Última preparación: ",
        h("span", { class: "mono" }, u.maestro || "-"),
        ` (ciclo ${fechaTxt(u.fecha)}, ${(u.preparado_en || "-").replace("T", " ")})`,
        u.nuevos.length ? ` · productos nuevos: ${u.nuevos.map((n) => `${n.linea} / ${n.producto}`).join(", ")}` : "",
        u.resumen_xlsx ? " · " : "",
        u.resumen_xlsx ? linklike("abrir el resumen", () => abrir(u.resumen_xlsx, "archivo")) : null
      )
    );
  }

  // ---------- progreso (analizando / preparando) ----------
  function pintarProgreso(s) {
    const titulo = h("h2", { class: "section__title" }, "");
    const b = bar(0);
    b.classList.add("bar--working");
    const etapa = h("div", { class: "muted", style: "font-size:13px;min-height:16px" }, "");
    const log = h("div", { class: "log" });
    el.append(card(titulo, b, etapa), log);
    progreso = { titulo, fill: b.querySelector(".bar__fill"), etapa, log, n: 0 };
    actualizarProgreso(s);
  }

  function actualizarProgreso(s) {
    const verbo = s.estado === "analizando" ? "Analizando" : "Preparando los expertos de";
    progreso.titulo.textContent = `${verbo} ${s.maestro || ""} — ${s.progreso}% · ${fmtSeg(s.transcurrido_seg)}`;
    progreso.fill.style.width = `${s.progreso}%`;
    progreso.etapa.textContent = s.etapa || "";
    for (let i = progreso.n; i < (s.log || []).length; i++) {
      progreso.log.append(h("div", { class: "log__line" }, s.log[i]));
    }
    progreso.n = (s.log || []).length;
    progreso.log.scrollTop = progreso.log.scrollHeight;
  }

  // ---------- resumen del análisis + decisiones ----------
  function pintarAnalisis(s) {
    const a = s.analisis;
    decisiones = {};
    for (const n of a.nuevos) {
      decisiones[n.clave] = { tiendas: new Set(n.tiendas), nombre_e2: n.nombre_e2, nombre_e3: n.nombre_e3 };
    }

    if (s.error) el.append(h("div", { class: "banner banner--error" }, s.error));
    el.append(...resumenAnalisis(a, true));

    const preparar = btn("Preparar expertos", {
      variant: "primary",
      disabled: !a.puede_preparar,
      onClick: async () => {
        const eleccion = await modal(
          confirmacion(a),
          [
            { id: "cancelar", label: "Cancelar", variant: "secondary" },
            { id: "preparar", label: "Preparar", variant: "primary" },
          ],
          { amplio: true }
        );
        if (eleccion !== "preparar") return;
        const nuevos = {};
        for (const [clave, d] of Object.entries(decisiones)) {
          nuevos[clave] = { tiendas: [...d.tiendas], nombre_e2: d.nombre_e2, nombre_e3: d.nombre_e3 };
        }
        try {
          mostrar(await api.prepararConfirmar(nuevos));
        } catch (e) {
          alert("No se pudo preparar: " + e.message);
        }
      },
    });
    el.append(
      h(
        "div",
        { class: "row", style: "align-items:center" },
        preparar,
        btn("Descartar este maestro", { onClick: reiniciar })
      )
    );
  }

  // Bloques del resumen. `editable`: tiendas y nombres de los productos nuevos
  // se pueden cambiar (antes de preparar).
  function resumenAnalisis(a, editable) {
    const out = [];
    out.push(
      h(
        "div",
        { class: "row", style: "align-items:center" },
        h("span", { class: "muted" }, "Maestro:"),
        h("span", { class: "mono" }, a.maestro),
        h("span", { class: "chip chip--ok" }, `ciclo ${fechaTxt(a.fecha)}`),
        h("span", { class: "muted" }, "comparado con"),
        h("span", { class: "mono" }, a.anterior || "— (no hay Experto 1 anterior)")
      )
    );
    out.push(
      h(
        "div",
        { class: "row" },
        numcard(miles(a.filas_unicas), a.repetidas ? `fórmulas (de ${miles(a.filas)} filas; ${miles(a.repetidas)} duplicadas)` : "fórmulas en el maestro"),
        numcard(miles(a.productos), "productos"),
        numcard(miles(a.nuevos.length), "productos nuevos"),
        ...(a.anterior
          ? [
              numcard(`+${miles(a.filas_agregadas)}`, "fórmulas agregadas vs el ciclo anterior"),
              numcard(`−${miles(a.filas_quitadas)}`, "fórmulas quitadas vs el ciclo anterior"),
            ]
          : [])
      )
    );

    // rojo: impide preparar; naranjo (al final del resumen): advertencias
    for (const b of a.bloqueantes || []) out.push(h("div", { class: "banner banner--error" }, b));

    // productos nuevos
    out.push(h("h2", { class: "section__title" }, `Productos nuevos (${a.nuevos.length})`));
    if (!a.nuevos.length) {
      out.push(h("p", { class: "muted", style: "margin:0" }, "No hay productos nuevos: todos los productos del maestro ya están en la tabla de productos."));
    } else {
      out.push(
        h(
          "p",
          { class: "muted", style: "margin:0;font-size:13px" },
          "Se agregan a la tabla de productos con las tiendas marcadas. El nombre en Experto 3 va como «Línea / Producto»."
        )
      );
      out.push(
        tabla(
          [
            { label: "Producto", w: "1.6fr" },
            { label: "Fórmulas", w: "90px" },
            { label: "Tiendas", w: "1.1fr" },
            { label: "Nombre en Experto 2 y 3", w: "1.6fr" },
          ],
          a.nuevos.map((n) => filaNuevo(n, a.tiendas, editable))
        )
      );
    }

    // cambios respecto del ciclo anterior
    if (a.anterior) {
      out.push(h("h2", { class: "section__title" }, "Cambios respecto del ciclo anterior"));
      const filas = [
        ...a.cambios.map((c) => [c.producto, miles(c.antes), miles(c.ahora), `+${miles(c.agregadas)}`, `−${miles(c.quitadas)}`]),
        ...a.quitados.map((q) => [h("div", {}, q.producto, " ", tag("error", "ya no viene")), miles(q.filas), "0", "+0", `−${miles(q.filas)}`]),
      ];
      out.push(
        filas.length
          ? tabla(
              [
                { label: "Producto", w: "2fr" },
                { label: "Antes", w: "90px" },
                { label: "Ahora", w: "90px" },
                { label: "Agregadas", w: "100px" },
                { label: "Quitadas", w: "100px" },
              ],
              filas
            )
          : h("p", { class: "muted", style: "margin:0" }, "Los productos que ya estaban vienen sin cambios.")
      );
      out.push(h("p", { class: "muted", style: "margin:0;font-size:13px" }, `${miles(a.sin_cambios)} producto(s) sin cambios.`));
    }

    // qué se genera
    out.push(h("h2", { class: "section__title" }, "Expertos que se generan"));
    out.push(
      tabla(
        [
          { label: "Experto", w: "110px" },
          { label: "Archivo", w: "1.3fr" },
          { label: "Fórmulas", w: "100px" },
          { label: "Productos que entran", w: "2fr" },
        ],
        a.expertos.map((e) => [
          h("strong", {}, e.label),
          e.archivo
            ? h(
                "div",
                {},
                h("div", { class: "mono" }, e.archivo),
                h(
                  "div",
                  { class: "muted", style: "font-size:12px" },
                  e.plantilla
                    ? `plantilla: ${e.plantilla}`
                    : "copia del maestro" + (a.filas_a_galon ? ` (${miles(a.filas_a_galon)} fórmulas pasadas a galón)` : "")
                )
              )
            : tag("advertencia", "no se genera: falta su plantilla"),
          miles(e.filas),
          e.entran.length || e.salen.length
            ? h(
                "div",
                { style: "font-size:13px" },
                e.entran.length ? h("div", {}, e.entran.join(", ")) : null,
                e.salen.length ? h("div", { class: "muted" }, "Salen: ", e.salen.join(", ")) : null
              )
            : h("span", { class: "muted" }, "—"),
        ])
      )
    );

    for (const w of a.advertencias || []) out.push(h("div", { class: "banner banner--advertencia" }, w));
    return out;
  }

  function filaNuevo(n, tiendas, editable) {
    const d = decisiones[n.clave] || { tiendas: new Set(n.tiendas), nombre_e2: n.nombre_e2, nombre_e3: n.nombre_e3 };
    const detalle = h(
      "div",
      { class: "muted", style: "font-size:12px" },
      `${n.clasificacion} · ${topConteos(n.formatos, 2)}`,
      n.repetidas ? ` · ${miles(n.repetidas)} duplicadas quitadas` : "",
      h("br"),
      `Cartillas: ${topConteos(n.cartillas)}`
    );
    const producto = h("div", {}, h("div", { style: "font-weight:500" }, `${n.linea} / ${n.producto}`), detalle);

    const checks = h(
      "div",
      { class: "checks-inline" },
      ...tiendas.map((t) => {
        const input = h("input", { type: "checkbox", disabled: !editable });
        input.checked = d.tiendas.has(t);
        input.addEventListener("change", () => (input.checked ? d.tiendas.add(t) : d.tiendas.delete(t)));
        return h("label", {}, input, t);
      })
    );
    const texto = (valor, al) => {
      const input = h("input", { type: "text", class: "input-texto", value: valor, disabled: !editable });
      input.addEventListener("input", () => al(input.value));
      return input;
    };
    const nombres = h(
      "div",
      { class: "stack", style: "gap:6px" },
      h("label", { class: "campo" }, h("span", { class: "campo__label" }, "Experto 2"), texto(d.nombre_e2, (v) => (d.nombre_e2 = v))),
      h("label", { class: "campo" }, h("span", { class: "campo__label" }, "Experto 3"), texto(d.nombre_e3, (v) => (d.nombre_e3 = v)))
    );
    return [producto, h("div", { class: "mono" }, miles(n.filas)), checks, nombres];
  }

  function confirmacion(a) {
    const bloque = (label, ...contenido) =>
      h("div", { class: "resumen__bloque" }, h("div", { class: "resumen__label" }, label), ...contenido);
    const nuevos = a.nuevos.map((n) => {
      const tiendas = [...decisiones[n.clave].tiendas];
      return h("li", {}, `${n.linea} / ${n.producto} → `, tiendas.length ? tiendas.join(", ") : h("strong", {}, "ninguna tienda (no se entrega)"));
    });
    return h(
      "div",
      { class: "resumen" },
      h("h2", { class: "resumen__titulo" }, `Preparar el ciclo ${fechaTxt(a.fecha)}`),
      bloque(
        "Se generan en la carpeta de entrada",
        h("ul", { class: "resumen__lista" }, ...a.expertos.filter((e) => e.archivo).map((e) => h("li", {}, h("span", { class: "mono" }, e.archivo), ` (${miles(e.filas)} fórmulas)`)))
      ),
      bloque(
        "Tabla de productos",
        nuevos.length ? h("ul", { class: "resumen__lista" }, ...nuevos) : h("div", { style: "font-size:13px" }, "Sin productos nuevos."),
        h("div", { class: "resumen__fecha" }, "Además se completan los nombres de Experto 2/3 que falten en la tabla.")
      ),
      h(
        "div",
        { class: "resumen__pie" },
        "Los expertos y la tabla actuales se mueven a backups/expertos/<fecha>/. Si alguno está abierto en Excel, cerralo antes."
      )
    );
  }

  // ---------- expertos preparados ----------
  function pintarListo(s) {
    const r = s.resultado;
    el.append(
      h(
        "div",
        { class: "banner banner--info" },
        `Expertos del ciclo ${fechaTxt(r.fecha)} listos en la carpeta de entrada. Revisá los expertos del ciclo más abajo y ejecutá.`
      )
    );
    el.append(
      card(
        h("h2", { class: "section__title" }, "Expertos generados desde el maestro"),
        tabla(
          [
            { label: "Experto", w: "110px" },
            { label: "Archivo", w: "2fr" },
            { label: "Fórmulas", w: "110px" },
            { label: "Acciones", w: "150px" },
          ],
          r.archivos.map((f) => [
            h("strong", {}, f.label),
            h("span", { class: "mono" }, f.archivo),
            miles(f.filas),
            h("div", { class: "row", style: "gap:14px" }, linklike("Carpeta", () => abrir(f.ruta, "carpeta"))),
          ])
        ),
        h(
          "div",
          { style: "font-size:13px" },
          r.productos_agregados.length
            ? `Tabla de productos: se agregaron ${r.productos_agregados.map((p) => `${p.linea} / ${p.producto} (${p.tiendas.join(", ") || "sin tiendas"})`).join("; ")}.`
            : "Tabla de productos: sin productos nuevos.",
          r.nombres_completados ? ` Se completaron ${r.nombres_completados} nombre(s) de Experto 2/3.` : ""
        ),
        h("div", { class: "muted", style: "font-size:13px" }, "Lo anterior quedó en ", h("span", { class: "mono" }, r.backup || "-")),
        h(
          "div",
          { class: "row", style: "gap:14px" },
          linklike("Abrir el resumen (Excel)", () => abrir(r.resumen_xlsx, "archivo")),
          r.backup ? linklike("Abrir el backup", () => abrir(r.backup, "carpeta")) : null
        )
      )
    );
    for (const w of r.advertencias || []) el.append(h("div", { class: "banner banner--advertencia" }, w));
    if (s.analisis) {
      // se muestra lo que quedó en la tabla (no lo sugerido)
      decisiones = {};
      for (const n of s.analisis.nuevos) {
        const ag = r.productos_agregados.find((p) => p.producto === n.producto) || {};
        decisiones[n.clave] = {
          tiendas: new Set(ag.tiendas || []),
          nombre_e2: ag["Experto 2"] ?? n.nombre_e2,
          nombre_e3: ag["Experto 3"] ?? n.nombre_e3,
        };
      }
      el.append(
        h(
          "details",
          { class: "detalle-analisis" },
          h("summary", {}, "Ver el análisis del maestro (productos nuevos, cambios y expertos)"),
          h("div", { class: "detalle-analisis__cuerpo" }, ...resumenAnalisis(s.analisis, false))
        )
      );
    }
    el.append(h("div", { class: "row" }, btn("Cerrar", { onClick: reiniciar })));
  }

  function pintarError(s) {
    el.append(h("div", { class: "banner banner--error" }, "No se pudo procesar el archivo maestro."));
    el.append(h("pre", { class: "log", style: "white-space:pre-wrap" }, s.error || "sin detalle"));
    el.append(h("div", { class: "row" }, btn("Descartar", { variant: "primary", onClick: reiniciar })));
  }

  return {
    el,
    mostrar,
    refrescar,
    destruir() {
      if (timer) clearInterval(timer);
      timer = null;
    },
  };
}
