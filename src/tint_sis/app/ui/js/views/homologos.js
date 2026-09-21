import { api } from "../api.js";
import { h, card, btn, tag } from "../dom.js";

const GRUPOS = ["MP14", "MP12", "Tiendas 14", "Tiendas 12"];

const linklike = (label, onClick) => h("button", { class: "linklike", onclick: onClick }, label);

function inlineForm(placeholder, onSubmit) {
  const input = h("input", {
    type: "text",
    placeholder,
    style: "flex:1;font-size:13px;padding:6px 8px;border:1px solid var(--linea);border-radius:6px",
  });
  const msg = h("span", { class: "muted", style: "font-size:12px" });
  const submit = async () => {
    const valor = input.value.trim();
    if (!valor) return;
    submitBtn.disabled = true;
    msg.textContent = "";
    try {
      await onSubmit(valor);
      input.value = "";
    } catch (e) {
      msg.textContent = e.message;
    } finally {
      submitBtn.disabled = false;
    }
  };
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      submit();
    }
  });
  const submitBtn = btn("Agregar", { onClick: submit });
  return h("div", { class: "stack", style: "gap:4px;margin-top:6px" }, h("div", { class: "row", style: "gap:8px" }, input, submitBtn), msg);
}

export async function render(view, { navigate }) {
  view.append(h("h1", { class: "view__title" }, "Homólogos"));
  view.append(h("p", { class: "muted" }, "Qué ID_TINT le corresponde a cada homólogo, por tienda. La primera carga del archivo maestro puede tardar — es un archivo grande."));

  const tabsRow = h("div", { class: "row", style: "gap:8px" });
  view.append(tabsRow);

  const guardarBanner = h("div", { hidden: true });
  view.append(guardarBanner);

  const content = h("div", { class: "stack", style: "gap:20px" });
  view.append(content);

  let tiendaActiva = GRUPOS[0];
  const abiertas = new Set(); // nombres "linea" / "linea::homologo" expandidos, se mantienen entre refrescos

  function renderGuardarBanner(dirty) {
    guardarBanner.hidden = false;
    guardarBanner.replaceChildren(
      h(
        "div",
        { class: "banner banner--advertencia", style: dirty ? "" : "display:none" },
        h("span", {}, "Hay cambios sin guardar en el archivo."),
        btn("Guardar cambios en el archivo", {
          variant: "primary",
          onClick: async () => {
            try {
              const res = await api.homologosGuardar();
              alert(`Guardado. Copia de respaldo del archivo anterior en:\n${res.backup}`);
              await cargar(tiendaActiva);
            } catch (e) {
              alert("No se pudo guardar: " + e.message);
            }
          },
        })
      )
    );
  }

  function coberturaCard(cobertura, experto_usado) {
    if (!cobertura) {
      return card(
        h("h2", { class: "section__title" }, "Cobertura"),
        h("p", { class: "muted" }, "No se pudo calcular: falta el archivo experto (xData_DATACOMPLETA_*.xlsx) en la carpeta de entrada.")
      );
    }
    const lista = (items, vacio) => {
      if (!items.length) return h("p", { class: "muted", style: "font-size:13px" }, vacio);
      const mostrar = items.slice(0, 200);
      return h(
        "div",
        { class: "mono", style: "font-size:12px;max-height:160px;overflow-y:auto;background:#f7f8f8;border-radius:6px;padding:8px" },
        mostrar.join(", ") + (items.length > mostrar.length ? ` … y ${items.length - mostrar.length} más` : "")
      );
    };

    return card(
      h("h2", { class: "section__title" }, "Cobertura"),
      h("p", { class: "muted", style: "font-size:12px;margin:0" }, experto_usado ? `Contra ${experto_usado}` : ""),
      h(
        "div",
        { class: "row" },
        tag(cobertura.ids_sin_asignar.length ? "advertencia" : "ok", `${cobertura.ids_sin_asignar.length} IDs del experto sin asignar`),
        tag(cobertura.homologos_sin_ids.length ? "advertencia" : "ok", `${cobertura.homologos_sin_ids.length} homólogos sin IDs`),
        tag(cobertura.ids_duplicados.length ? "error" : "ok", `${cobertura.ids_duplicados.length} IDs duplicados`),
        cobertura.ids_no_en_experto.length
          ? tag("advertencia", `${cobertura.ids_no_en_experto.length} IDs que ya no están en el experto`)
          : null
      ),
      h("div", { class: "stack", style: "gap:10px" },
        h("div", {}, h("strong", { style: "font-size:12px" }, "IDs del experto sin asignar: "), lista(cobertura.ids_sin_asignar, "ninguno")),
        h("div", {}, h("strong", { style: "font-size:12px" }, "Homólogos sin IDs: "), lista(cobertura.homologos_sin_ids.map((h2) => `${h2.linea} → ${h2.homologo}`), "ninguno")),
        h("div", {}, h("strong", { style: "font-size:12px" }, "IDs asignados a más de un homólogo: "), lista(cobertura.ids_duplicados.map((d) => `${d.id_tint} (${d.asignaciones.map((a) => a.homologo).join(" + ")})`), "ninguno"))
      )
    );
  }

  function homologoBlock(tienda, linea, h1) {
    const key = `${linea.nombre}::${h1.nombre}`;
    const idsBox = h("div", { hidden: !abiertas.has(key) });

    // Algunos homologos reales traen miles de IDs (ej. "Habitacional Ceresita"
    // con 3045): renderizar todos los chips de entrada, en cada edicion,
    // vuelve la vista notablemente mas lenta. Se muestran de a tanda con un
    // link para pedir el resto.
    const LIMITE_IDS = 300;
    let mostrarTodos = false;

    const chipId = (id) =>
      h(
        "span",
        { class: "chip", style: "gap:6px" },
        id,
        h(
          "button",
          {
            title: `Quitar ${id}`,
            style: "background:none;border:none;cursor:pointer;color:inherit;font-weight:700;padding:0 0 0 4px",
            onclick: async () => {
              if (!confirm(`¿Quitar "${id}" de "${h1.nombre}"?`)) return;
              try {
                await api.homologosQuitarId(tienda, linea.nombre, h1.nombre, id);
                await cargar(tienda);
              } catch (e) {
                alert(e.message);
              }
            },
          },
          "×"
        )
      );

    function renderIds() {
      const aMostrar = mostrarTodos ? h1.ids : h1.ids.slice(0, LIMITE_IDS);
      const ocultos = h1.ids.length - aMostrar.length;
      idsBox.replaceChildren(
        ...[
          h1.ids.length
            ? h("div", { class: "row", style: "gap:6px;flex-wrap:wrap" }, ...aMostrar.map(chipId))
            : h("p", { class: "muted", style: "font-size:12px" }, "Sin IDs asignados todavía (pendiente)."),
          ocultos > 0
            ? linklike(`Mostrar los ${ocultos} restantes`, () => {
                mostrarTodos = true;
                renderIds();
              })
            : null,
        ].filter(Boolean)
      );
      idsBox.append(
        inlineForm("Nuevo ID_TINT (ej. LátHab001)", async (valor) => {
          await api.homologosAgregarId(tienda, linea.nombre, h1.nombre, valor);
          await cargar(tienda);
        })
      );
    }
    renderIds();

    const toggle = linklike(`${abiertas.has(key) ? "▾" : "▸"} ${h1.nombre} (${h1.ids.length})`, () => {
      const abrir = idsBox.hidden;
      idsBox.hidden = !abrir;
      if (abrir) abiertas.add(key);
      else abiertas.delete(key);
      toggle.textContent = `${abrir ? "▾" : "▸"} ${h1.nombre} (${h1.ids.length})`;
    });

    return h(
      "div",
      { "data-homologo": h1.nombre, style: "padding:8px 0 8px 16px;border-left:2px solid var(--linea)" },
      h("div", { class: "row", style: "align-items:center;gap:10px" }, toggle, h1.pendiente ? tag("advertencia", "pendiente") : null, h1.nota ? tag("advertencia", `nota: ${h1.nota}`) : null),
      idsBox
    );
  }

  function lineaBlock(tienda, linea) {
    const key = linea.nombre;
    const body = h("div", { hidden: !abiertas.has(key) });

    function renderBody() {
      body.replaceChildren(...linea.homologos.map((h1) => homologoBlock(tienda, linea, h1)));
      body.append(
        h("div", { style: "padding-left:16px" }, inlineForm("Nombre del nuevo homólogo", async (valor) => {
          await api.homologosAgregarHomologo(tienda, linea.nombre, valor);
          await cargar(tienda);
        }))
      );
    }
    renderBody();

    const toggle = linklike(`${abiertas.has(key) ? "▾" : "▸"} ${linea.nombre} (${linea.homologos.length} homólogos)`, () => {
      const abrir = body.hidden;
      body.hidden = !abrir;
      if (abrir) abiertas.add(key);
      else abiertas.delete(key);
      toggle.textContent = `${abrir ? "▾" : "▸"} ${linea.nombre} (${linea.homologos.length} homólogos)`;
    });

    const wrapper = card(
      h("div", { class: "row", style: "align-items:center;gap:10px" }, toggle, linea.pendiente ? tag("advertencia", "sin homólogos") : null),
      body
    );
    wrapper.dataset.linea = linea.nombre;
    return wrapper;
  }

  async function cargar(tienda) {
    tiendaActiva = tienda;
    for (const el of tabsRow.children) {
      el.classList.toggle("is-active", el.dataset.tienda === tienda);
    }
    content.replaceChildren(h("p", { class: "soon-view" }, "Cargando homologos_TINT.xlsx… la primera vez puede tardar cerca de un minuto (es un archivo con cientos de miles de filas)."));

    let data;
    try {
      data = await api.homologosTienda(tienda);
    } catch (e) {
      content.replaceChildren(h("div", { class: "banner banner--error" }, `No se pudo cargar: ${e.message}`));
      return;
    }

    renderGuardarBanner(data.cambios_sin_guardar);

    content.replaceChildren(
      ...[
        coberturaCard(data.cobertura, data.experto_usado),
        data.filas_no_reconocidas
          ? h("p", { class: "muted", style: "font-size:12px" }, `${data.filas_no_reconocidas} filas del archivo no se reconocieron y no se muestran acá (quedan intactas si se guarda).`)
          : null,
        h("h2", { class: "section__title" }, "Líneas"),
        ...data.lineas.map((linea) => lineaBlock(tienda, linea)),
        card(
          h("h3", { style: "margin:0;font-size:14px" }, "Agregar línea / producto nuevo"),
          inlineForm("Nombre de la línea (ej. Chilcomar Top 20)", async (valor) => {
            await api.homologosAgregarLinea(tienda, valor);
            await cargar(tienda);
          })
        ),
      ].filter(Boolean)
    );
  }

  for (const g of GRUPOS) {
    const b = btn(g, { onClick: () => cargar(g) });
    b.classList.add("btn--naranja");
    b.dataset.tienda = g;
    tabsRow.append(b);
  }

  await cargar(tiendaActiva);
}
