import { api } from "../api.js";
import { h, card, btn, tag, modal } from "../dom.js";

// Homólogos = la tabla de productos (productos_TINT.xlsx) que usa el ciclo para
// filtrar: una fila por producto (homólogo), su línea, cómo se llama en cada
// archivo experto y qué tiendas lo llevan. Se edita acá en una copia de trabajo;
// "Guardar cambios" reescribe la tabla (con copia de respaldo de la anterior).

const EXPERTOS = ["Experto 1", "Experto 2", "Experto 3"];
const CORTO = { "Experto 1": "E1", "Experto 2": "E2", "Experto 3": "E3" };
const SIN_LINEA = "(sin línea)";

const miles = (n) => (typeof n === "number" ? n.toLocaleString("es-CL") : n ?? "-");
const linklike = (label, onClick) => h("button", { class: "linklike", onclick: onClick }, label);
// misma comparación que el ciclo (expertos.normalizar): sin acentos, espacios ni mayúsculas
const normalizar = (s) =>
  String(s ?? "")
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/\s+/g, "")
    .toLowerCase();
const nombresDe = (celda) =>
  String(celda || "")
    .split(";")
    .map((x) => x.trim())
    .filter(Boolean);

export async function render(view) {
  view.append(h("h1", { class: "view__title" }, "Homólogos — tabla de productos"));
  view.append(
    h(
      "p",
      { class: "muted" },
      "Cada fila es un producto (homólogo): su línea, cómo se llama en cada archivo experto y qué tiendas lo llevan. " +
        "Es la tabla productos_TINT.xlsx con la que el ciclo filtra; un producto sin tiendas marcadas no se entrega."
    )
  );

  const barra = h("div", { class: "guardar-barra", hidden: true });
  const buscar = h("input", { type: "search", class: "input-texto", placeholder: "Buscar producto, línea o nombre en un experto…", style: "max-width:380px" });
  const resumen = h("span", { class: "muted", style: "font-size:13px" });
  const datalists = h("div", { hidden: true });
  const cuerpo = h("div", { class: "stack", style: "gap:20px" });
  const sinAsignarBox = h("div", { class: "stack", style: "gap:12px" });

  view.append(
    h(
      "div",
      { class: "row", style: "align-items:center" },
      buscar,
      btn("Agregar producto", { variant: "primary", onClick: () => abrirFormulario({ titulo: "Agregar producto" }) }),
      btn("Nueva línea", { onClick: () => abrirFormulario({ titulo: "Nueva línea (con su primer producto)", nuevaLinea: true }) }),
      btn("Recargar", { onClick: recargar }),
      resumen
    ),
    barra,
    datalists,
    cuerpo,
    sinAsignarBox
  );

  let tabla = null; // última versión leída del servidor
  let filas = []; // copia de trabajo: {key, id, subp, linea, producto, nombres, tiendas:Set, revisar}
  let base = ""; // copia de trabajo serializada al cargar/guardar
  let catalogo = null; // Experto N -> {archivo, productos:{nombre: fórmulas}, error}
  let indice = {}; // Experto N -> Map(normalizado -> fórmulas)
  let aviso = null; // {nivel, texto, recargar?}
  let seq = 0;
  const actualizadores = new Set(); // refrescan contadores de una fila (al llegar el catálogo)

  const serial = () =>
    JSON.stringify(filas.map((f) => [f.id, f.subp, f.linea, f.producto, EXPERTOS.map((e) => f.nombres[e]), [...f.tiendas].sort()]));
  const hayCambios = () => serial() !== base;

  function desdeServidor(t) {
    tabla = t;
    filas = t.filas.map((f) => ({ ...f, key: ++seq, nombres: { ...f.nombres }, tiendas: new Set(f.tiendas) }));
    base = serial();
  }

  // ---------- barra de guardar ----------
  function pintarBarra() {
    const cambios = hayCambios();
    barra.hidden = !cambios && !aviso;
    barra.className = `guardar-barra${aviso && !cambios ? ` guardar-barra--${aviso.nivel}` : ""}`;
    if (cambios) {
      barra.replaceChildren(
        h("strong", {}, "Hay cambios sin guardar en la tabla de productos."),
        aviso && aviso.nivel === "error" ? h("span", {}, aviso.texto) : null,
        btn("Guardar cambios", { variant: "primary", onClick: guardar }),
        btn("Descartar", {
          onClick: () => {
            desdeServidor(tabla);
            aviso = null;
            pintar();
          },
        }),
        aviso && aviso.recargar ? btn("Recargar desde el archivo", { onClick: () => recargar(true) }) : null
      );
    } else if (aviso) {
      barra.replaceChildren(h("span", {}, aviso.texto), linklike("Cerrar", () => ((aviso = null), pintarBarra())));
    }
    const lineas = new Set(filas.map((f) => f.linea || SIN_LINEA));
    const sinTiendas = filas.filter((f) => !f.tiendas.size).length;
    resumen.textContent = `${filas.length} productos · ${lineas.size} líneas` + (sinTiendas ? ` · ${sinTiendas} sin tiendas (no se entregan)` : "");
  }

  // ---------- contador de fórmulas por experto ----------
  function cobertura(experto, celda) {
    const nombres = nombresDe(celda);
    if (!nombres.length) return { vacio: true };
    const cat = catalogo && catalogo[experto];
    if (!cat) return { cargando: true };
    if (cat.error) return { error: cat.error };
    let total = 0;
    const faltan = [];
    for (const n of nombres) {
      const v = indice[experto].get(normalizar(n));
      if (v === undefined) faltan.push(n);
      else total += v;
    }
    return { total, faltan };
  }

  function pintarCuenta(el, experto, celda) {
    const c = cobertura(experto, celda);
    el.replaceChildren();
    if (c.vacio) el.append(h("span", { class: "muted" }, "sin nombre"));
    else if (c.cargando) el.append(h("span", { class: "muted" }, "…"));
    else if (c.error) el.append(tag("advertencia", "experto no disponible"));
    else if (c.faltan.length) el.append(tag("advertencia", `no está en ${catalogo[experto].archivo}`));
    else el.append(`${miles(c.total)} fórmulas`);
  }

  // ---------- filas ----------
  function filaEl(f) {
    const producto = h("input", { type: "text", class: "input-texto", value: f.producto, "aria-label": "Producto" });
    producto.addEventListener("input", () => {
      f.producto = producto.value;
      pintarBarra();
    });
    const linea = h("input", { type: "text", class: "input-texto", value: f.linea, list: "dl-lineas", "aria-label": "Línea" });
    linea.addEventListener("input", () => {
      f.linea = linea.value;
      pintarBarra();
    });
    linea.addEventListener("change", pintar); // al cambiar de línea, la fila pasa a su grupo

    const cuentas = [];
    const nombres = h(
      "div",
      { class: "stack", style: "gap:6px" },
      ...EXPERTOS.map((e) => {
        const input = h("input", { type: "text", class: "input-texto", value: f.nombres[e] || "", list: `dl-${CORTO[e]}`, "aria-label": `Nombre en ${e}` });
        const cuenta = h("span", { class: "exp-campo__cuenta" });
        cuentas.push([cuenta, e]);
        input.addEventListener("input", () => {
          f.nombres[e] = input.value;
          pintarCuenta(cuenta, e, input.value);
          pintarBarra();
        });
        input.addEventListener("change", pintarSinAsignar);
        return h("div", { class: "exp-campo", title: e }, h("span", { class: "exp-campo__label" }, CORTO[e]), input, cuenta);
      })
    );
    const actualizar = () => cuentas.forEach(([el, e]) => pintarCuenta(el, e, f.nombres[e]));
    actualizar();
    actualizadores.add(actualizar);

    const sinTiendas = tag("advertencia", "sin tiendas: no se entrega");
    sinTiendas.hidden = f.tiendas.size > 0;
    const tiendas = h(
      "div",
      { class: "stack", style: "gap:6px" },
      h(
        "div",
        { class: "checks-inline" },
        ...tabla.tiendas.map((t) => {
          const input = h("input", { type: "checkbox" });
          input.checked = f.tiendas.has(t);
          input.addEventListener("change", () => {
            input.checked ? f.tiendas.add(t) : f.tiendas.delete(t);
            sinTiendas.hidden = f.tiendas.size > 0;
            pintarBarra();
          });
          return h("label", {}, input, t);
        })
      ),
      sinTiendas
    );

    const eliminar = btn("Eliminar", {
      onClick: async () => {
        const r = await modal(
          h(
            "div",
            {},
            h("p", { style: "margin-top:0" }, `¿Eliminar «${f.producto || "(sin nombre)"}» de la tabla de productos?`),
            h(
              "p",
              { class: "muted", style: "font-size:13px;margin-bottom:0" },
              "Si los expertos lo siguen trayendo, el ciclo avisará que no está en la tabla y no lo entregará. Se aplica al guardar los cambios."
            )
          ),
          [
            { id: "cancelar", label: "Cancelar", variant: "secondary" },
            { id: "eliminar", label: "Eliminar", variant: "primary" },
          ]
        );
        if (r !== "eliminar") return;
        filas = filas.filter((x) => x !== f);
        pintar();
      },
    });
    eliminar.classList.add("btn--chico");

    return h(
      "div",
      { class: "prod-fila", "data-producto": f.producto },
      h(
        "div",
        { class: "stack", style: "gap:6px" },
        producto,
        h("div", { class: "exp-campo exp-campo--linea", title: "Línea" }, h("span", { class: "exp-campo__label" }, "Lín."), linea),
        f.subp || f.revisar
          ? h("div", { class: "prod-fila__meta" }, [f.subp, f.revisar].filter(Boolean).join(" · "))
          : f.id
            ? null
            : h("div", { class: "prod-fila__meta" }, "nuevo (se agrega al guardar)")
      ),
      nombres,
      tiendas,
      eliminar
    );
  }

  // sugerencias al escribir: líneas existentes y productos de cada experto
  function pintarDatalists() {
    const lineas = [...new Set(filas.map((f) => f.linea.trim()).filter(Boolean))];
    datalists.replaceChildren(
      h("datalist", { id: "dl-lineas" }, ...lineas.map((l) => h("option", { value: l }))),
      ...EXPERTOS.map((e) =>
        h("datalist", { id: `dl-${CORTO[e]}` }, ...Object.keys((catalogo && catalogo[e] && catalogo[e].productos) || {}).map((n) => h("option", { value: n })))
      )
    );
  }

  function coincide(f, q) {
    if (!q) return true;
    return [f.linea, f.producto, f.subp, ...EXPERTOS.map((e) => f.nombres[e])].some((v) => normalizar(v).includes(q));
  }

  function pintar() {
    pintarBarra();
    actualizadores.clear();
    const q = normalizar(buscar.value);
    const grupos = new Map();
    for (const f of filas) {
      const l = f.linea.trim() || SIN_LINEA;
      if (!grupos.has(l)) grupos.set(l, []);
      grupos.get(l).push(f);
    }
    pintarDatalists();
    const bloques = [];
    for (const [l, fs] of grupos) {
      const visibles = fs.filter((f) => coincide(f, q));
      if (!visibles.length) continue;
      bloques.push(
        card(
          h(
            "div",
            { class: "prod-grupo__head" },
            h("h2", { class: "section__title" }, l),
            h("span", { class: "muted", style: "font-size:13px" }, `${fs.length} producto${fs.length === 1 ? "" : "s"}`),
            l === SIN_LINEA ? null : linklike("Agregar producto a esta línea", () => abrirFormulario({ titulo: `Agregar producto a ${l}`, linea: l }))
          ),
          h(
            "div",
            { class: "prod-fila prod-fila--head" },
            h("div", {}, "Producto / línea"),
            h("div", {}, "Nombre en cada experto"),
            h("div", {}, "Tiendas"),
            h("div", {})
          ),
          ...visibles.map(filaEl)
        )
      );
    }
    cuerpo.replaceChildren(
      ...(bloques.length ? bloques : [h("p", { class: "muted" }, q ? "Ningún producto coincide con la búsqueda." : "La tabla no tiene productos.")])
    );
    pintarSinAsignar();
  }

  // ---------- productos de los expertos que no están en la tabla ----------
  function pintarSinAsignar() {
    if (!catalogo) {
      sinAsignarBox.replaceChildren(
        h("p", { class: "muted", style: "font-size:13px" }, "Leyendo los expertos del ciclo para contar fórmulas (la primera vez tarda alrededor de medio minuto)…")
      );
      return;
    }
    const enTabla = Object.fromEntries(EXPERTOS.map((e) => [e, new Set(filas.flatMap((f) => nombresDe(f.nombres[e]).map(normalizar)))]));
    const faltan = [];
    for (const e of EXPERTOS) {
      for (const [nombre, n] of Object.entries((catalogo[e] && catalogo[e].productos) || {})) {
        if (!enTabla[e].has(normalizar(nombre))) faltan.push({ e, nombre, n });
      }
    }
    const archivos = EXPERTOS.map((e) => `${CORTO[e]}: ${(catalogo[e] && catalogo[e].archivo) || "—"}`).join(" · ");
    sinAsignarBox.replaceChildren(
      card(
        h("h2", { class: "section__title" }, `Productos de los expertos que no están en la tabla (${faltan.length})`),
        h("div", { class: "muted", style: "font-size:12px" }, archivos),
        faltan.length
          ? h(
              "div",
              { class: "stack", style: "gap:0" },
              ...faltan.map((x) =>
                h(
                  "div",
                  { class: "sin-asignar" },
                  h("span", { class: "exp-campo__label" }, CORTO[x.e]),
                  h("span", {}, x.nombre),
                  h("span", { class: "muted", style: "font-size:12px" }, `${miles(x.n)} fórmulas`),
                  linklike("Agregar a la tabla", () => agregarDesdeExperto(x.e, x.nombre))
                )
              )
            )
          : h("p", { class: "muted", style: "margin:0" }, "Todos los productos de los expertos del ciclo están en la tabla."),
        h(
          "p",
          { class: "muted", style: "font-size:12px;margin:0" },
          "Un producto que un experto trae y no está en la tabla no se entrega a ninguna tienda (el ciclo lo avisa)."
        )
      )
    );
  }

  function agregarDesdeExperto(experto, nombre) {
    const nombres = { [experto]: nombre };
    let producto = nombre;
    let linea = "";
    if (experto === "Experto 3" && nombre.includes(" / ")) {
      [linea, producto] = nombre.split(" / ", 2).map((x) => x.trim());
    }
    // el mismo nombre en otro experto (E1 y E2 suelen escribirlo igual)
    for (const e of EXPERTOS) {
      if (e === experto || !catalogo || !catalogo[e]) continue;
      const igual = Object.keys(catalogo[e].productos || {}).find((n) => normalizar(n) === normalizar(nombre));
      if (igual) nombres[e] = igual;
    }
    abrirFormulario({ titulo: "Agregar producto a la tabla", linea, producto, nombres });
  }

  // ---------- agregar producto / nueva línea ----------
  async function abrirFormulario({ titulo, linea = "", producto = "", subp = "", nombres = {}, tiendas = [], nuevaLinea = false }) {
    const campo = (label, input) => h("label", { class: "form-campo" }, h("span", { class: "form-campo__label" }, label), input);
    const iLinea = h("input", { type: "text", class: "input-texto", value: linea, list: nuevaLinea ? null : "dl-lineas", placeholder: nuevaLinea ? "Nombre de la línea nueva (ej. Texturas)" : "Línea" });
    const iProducto = h("input", { type: "text", class: "input-texto", value: producto, placeholder: "Nombre del producto (homólogo)" });
    const iSubp = h("input", { type: "text", class: "input-texto", value: subp, placeholder: "opcional (ej. SUBP0210)" });
    const iNombres = Object.fromEntries(
      EXPERTOS.map((e) => [e, h("input", { type: "text", class: "input-texto", value: nombres[e] || "", list: `dl-${CORTO[e]}`, placeholder: e === "Experto 3" ? "Línea / Producto, como en el experto" : "como figura en la columna Producto" })])
    );
    const checks = tabla.tiendas.map((t) => {
      const input = h("input", { type: "checkbox" });
      input.checked = tiendas.includes(t);
      return [t, input];
    });
    const form = h(
      "div",
      { class: "resumen" },
      h("h2", { class: "resumen__titulo" }, titulo),
      campo("Línea", iLinea),
      campo("Producto", iProducto),
      campo("SUBP", iSubp),
      h("div", { class: "resumen__label" }, "Nombre en cada experto"),
      ...EXPERTOS.map((e) => campo(e, iNombres[e])),
      h("div", { class: "resumen__label" }, "Tiendas que lo llevan"),
      h("div", { class: "checks-inline" }, ...checks.map(([t, input]) => h("label", {}, input, t))),
      h("div", { class: "resumen__pie" }, "Se agrega a la copia de trabajo; queda en productos_TINT.xlsx al pulsar «Guardar cambios».")
    );
    const pendiente = modal(
      form,
      [
        { id: "cancelar", label: "Cancelar", variant: "secondary" },
        { id: "agregar", label: "Agregar", variant: "primary" },
      ],
      { amplio: true }
    );
    setTimeout(() => (linea && !nuevaLinea ? iProducto : iLinea).focus(), 0);
    if ((await pendiente) !== "agregar") return;

    const nueva = {
      key: ++seq,
      id: null,
      subp: iSubp.value.trim(),
      linea: iLinea.value.trim(),
      producto: iProducto.value.trim() || nombresDe(iNombres["Experto 1"].value)[0] || "",
      nombres: Object.fromEntries(EXPERTOS.map((e) => [e, iNombres[e].value.trim()])),
      tiendas: new Set(checks.filter(([, i]) => i.checked).map(([t]) => t)),
      revisar: "",
    };
    const reabrir = (motivo) => {
      alert(motivo);
      abrirFormulario({ titulo, linea: nueva.linea, producto: nueva.producto, subp: nueva.subp, nombres: nueva.nombres, tiendas: [...nueva.tiendas], nuevaLinea });
    };
    if (!nueva.producto) return reabrir("Falta el nombre del producto.");
    if (nuevaLinea && !nueva.linea) return reabrir("Falta el nombre de la línea nueva.");
    // se ubica después del último producto de su línea (o al final si la línea es nueva)
    let pos = -1;
    filas.forEach((f, i) => {
      if (normalizar(f.linea) === normalizar(nueva.linea)) pos = i;
    });
    if (pos >= 0) filas.splice(pos + 1, 0, nueva);
    else filas.push(nueva);
    buscar.value = "";
    pintar();
    const el = cuerpo.querySelector(`[data-producto="${CSS.escape(nueva.producto)}"]`);
    if (el) el.scrollIntoView({ block: "center" });
  }

  // ---------- guardar / recargar ----------
  async function guardar() {
    const payload = filas.map((f) => ({
      id: f.id || null,
      subp: f.subp,
      linea: f.linea,
      producto: f.producto,
      nombres: f.nombres,
      tiendas: [...f.tiendas],
    }));
    try {
      const res = await api.productosGuardar(tabla.version, payload);
      desdeServidor(res);
      aviso = { nivel: "info", texto: `Guardado en ${res.archivo}. Copia de la versión anterior en ${res.respaldo}` };
      pintar();
    } catch (e) {
      aviso = { nivel: "error", texto: "No se pudo guardar: " + e.message, recargar: /cambió en disco/.test(e.message) };
      pintarBarra();
    }
  }

  async function recargar(forzar = false) {
    if (!forzar && hayCambios() && !confirm("Hay cambios sin guardar: se pierden al recargar. ¿Recargar igual?")) return;
    try {
      desdeServidor(await api.productos());
      aviso = null;
      pintar();
    } catch (e) {
      cuerpo.replaceChildren(h("div", { class: "banner banner--error" }, "No se pudo leer la tabla de productos: " + e.message));
    }
  }

  buscar.addEventListener("input", pintar);
  const alSalirDelNavegador = (ev) => {
    if (hayCambios()) {
      ev.preventDefault();
      ev.returnValue = "";
    }
  };
  window.addEventListener("beforeunload", alSalirDelNavegador);

  try {
    desdeServidor(await api.productos());
  } catch (e) {
    cuerpo.replaceChildren(h("div", { class: "banner banner--error" }, "No se pudo leer la tabla de productos: " + e.message));
    return () => window.removeEventListener("beforeunload", alSalirDelNavegador);
  }
  pintar();

  let viva = true;
  api
    .productosCatalogo()
    .then((c) => {
      if (!viva) return;
      catalogo = c.expertos;
      indice = Object.fromEntries(
        EXPERTOS.map((e) => [e, new Map(Object.entries((catalogo[e] && catalogo[e].productos) || {}).map(([n, v]) => [normalizar(n), v]))])
      );
      // sin redibujar las filas (no se pierde el foco si se está escribiendo)
      pintarDatalists();
      actualizadores.forEach((actualizar) => actualizar());
      pintarSinAsignar();
    })
    .catch(() => {
      if (viva) sinAsignarBox.replaceChildren(h("p", { class: "muted" }, "No se pudieron leer los expertos para contar fórmulas."));
    });

  return {
    cleanup: () => {
      viva = false;
      window.removeEventListener("beforeunload", alSalirDelNavegador);
    },
    puedeSalir: () => !hayCambios() || confirm("Hay cambios sin guardar en la tabla de productos. ¿Salir igual y perderlos?"),
  };
}
