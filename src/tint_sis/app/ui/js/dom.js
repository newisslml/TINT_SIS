// Mini helper para construir DOM sin framework.
export function h(tag, props = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (k === "class") el.className = v;
    else if (k === "style") el.setAttribute("style", v);
    else if (k === "html") el.innerHTML = v;
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined && v !== false) el.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  return el;
}

export function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
  return node;
}

// ---------- componentes compartidos ----------
const TAG_LABEL = {
  ok: "OK",
  advertencia: "Advertencia",
  error: "Error",
  "no-habilitado": "Grupo no habilitado",
};

export function tag(estado, texto) {
  return h("span", { class: `tag tag--${estado}` }, texto || TAG_LABEL[estado] || estado);
}

export function numcard(value, label) {
  return h(
    "div",
    { class: "numcard" },
    h("div", { class: "numcard__value" }, value),
    h("div", { class: "numcard__label" }, label)
  );
}

export function btn(label, { variant = "secondary", onClick, disabled = false } = {}) {
  return h("button", { class: `btn btn--${variant}`, disabled, onclick: onClick }, label);
}

export function card(...children) {
  return h("div", { class: "card" }, ...children);
}

export function bar(pct) {
  return h("div", { class: "bar" }, h("div", { class: "bar__fill", style: `width:${pct}%` }));
}

// cols: array de {label, w} ; rows: array de array de (string|Node)
export function tabla(cols, rows) {
  const grid = `grid-template-columns:${cols.map((c) => c.w || "1fr").join(" ")}`;
  const head = h(
    "div",
    { class: "tabla__head", style: grid },
    ...cols.map((c) => h("div", {}, c.label))
  );
  const body = rows.map((cells) =>
    h("div", { class: "tabla__row", style: grid }, ...cells.map((c) => (c && c.nodeType ? c : h("div", {}, c ?? ""))))
  );
  return h("div", { class: "tabla" }, head, ...body);
}
