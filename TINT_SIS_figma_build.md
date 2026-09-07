# TINT_SIS — construir las 8 pantallas + prototype en Figma (script)

Este script termina los **pasos 4–7** de `TINT_SIS_figma_pasos.md` sin gastar cuota
del MCP de Figma. Lo corrés vos dentro del archivo de Figma.

## Qué asume

- Archivo **"TINT_SIS — UI"** (`AiqcNYuB3oRVGXnezoUcLY`), 1 página con las 4 secciones
  `Cover · Design system · Screens · Flow` **ya creadas**.
- El **sistema de diseño ya está armado** (lo hizo Claude por MCP antes de tocar el límite):
  - Colección de variables `TINT_SIS` con los 8 tokens de color.
  - Text styles `UI/*` y `Mono/*`.
  - Componentes: `Tag de estado`, `Botón`, `Barra de progreso`, `Card numérica`,
    `Fila de tabla`, `Item de nav`, `Shell / Base`.

Si algo de eso no está, el script avisa por `figma.notify` y no rompe nada.

## Cómo correrlo

1. Abrí el archivo **TINT_SIS — UI** en la **app de escritorio de Figma**.
2. Instalá el plugin **Scripter** (de Rasmus Andersson) desde Community — es una consola
   de Plugin API. (Menú → Plugins → busca "Scripter".)
3. Abrí Scripter sobre este archivo, **pegá todo el bloque de código de abajo** y dale
   **Run** (`Cmd/Ctrl + Enter`).
4. Al terminar muestra un aviso y hace zoom a la sección **Screens**.

Es **seguro re-correrlo**: borra las pantallas y los diagramas que él mismo generó
(`01 Inicio` … `08 Homólogos`, `Cover — contenido`, `Flow — diagrama`) y los rehace.
No toca el sistema de diseño ni las secciones.

## Qué construye

- **Screens**: los 8 frames `1440×900`, cada uno con una instancia del `Shell / Base`,
  el ítem de nav correcto marcado como *Activo*, y el contenido de cada pantalla según
  `VISTAS_TINT_SIS.md` (v1 con datos de ejemplo).
- **Cover**: portada con título, metadatos y leyenda de secciones.
- **Flow**: diagrama del flujo feliz (cajas + flechas) y las ramas laterales como nota.
- **Prototype**: los 6 ítems del nav de cada pantalla enlazados a su pantalla, más el
  flujo `Inicio → Nuevo ciclo → Ejecución → Resultados → Advertencias` y los accesos
  rápidos de Inicio.

## Límites conocidos

- El contenido es una **maqueta con datos de ejemplo**, no está pixel-perfect.
- Si Figma rechaza poner *reactions* sobre instancias anidadas del nav, el script lo
  ignora en silencio (el resto del prototype igual queda).
- Podés ajustar textos, spacing y enlaces a mano después.

---

```js
// ============================================================================
// TINT_SIS — build screens + prototype
// Pegar en el plugin "Scripter" sobre el archivo "TINT_SIS — UI" y Run.
// Seguro de re-correr.
// ============================================================================
(async () => {
  const page = figma.currentPage;

  // ---------- fonts ----------
  const FONTS = [
    { family: 'Inter', style: 'Regular' },
    { family: 'Inter', style: 'Medium' },
    { family: 'Inter', style: 'Semi Bold' },
    { family: 'JetBrains Mono', style: 'Regular' },
    { family: 'JetBrains Mono', style: 'Medium' },
  ];
  for (const f of FONTS) { try { await figma.loadFontAsync(f); } catch (e) {} }

  // ---------- color helpers ----------
  const RGB = (hex) => {
    const h = hex.replace('#', '');
    return {
      r: parseInt(h.slice(0, 2), 16) / 255,
      g: parseInt(h.slice(2, 4), 16) / 255,
      b: parseInt(h.slice(4, 6), 16) / 255,
    };
  };
  const allVars = await figma.variables.getLocalVariablesAsync();
  const V = (name) => allVars.find((v) => v.name === name && v.resolvedType === 'COLOR');
  const pVar = (name, opacity) => {
    let p = { type: 'SOLID', color: { r: 0, g: 0, b: 0 } };
    const v = V(name);
    if (v) p = figma.variables.setBoundVariableForPaint(p, 'color', v);
    if (opacity != null) p = { ...p, opacity };
    return p;
  };
  const pHex = (hex, opacity) => ({ type: 'SOLID', color: RGB(hex), ...(opacity != null ? { opacity } : {}) });
  const WHITE = () => pHex('#FFFFFF');
  const GHOST = () => pHex('#F7F8F8');

  // ---------- text ----------
  const txt = (chars, opt = {}) => {
    const { size = 14, lh = 20, weight = 'Regular', mono = false, color, hex, opacity } = opt;
    const family = mono ? 'JetBrains Mono' : 'Inter';
    const style = mono ? (weight === 'Medium' ? 'Medium' : 'Regular') : weight;
    const t = figma.createText();
    t.fontName = { family, style };
    t.characters = String(chars);
    t.fontSize = size;
    t.lineHeight = { unit: 'PIXELS', value: lh };
    if (color) t.fills = [pVar(color, opacity)];
    else if (hex) t.fills = [pHex(hex, opacity)];
    else t.fills = [pVar('ink')];
    return t;
  };

  // ---------- auto-layout ----------
  const AL = (dir, opt = {}) => {
    const f = figma.createFrame();
    f.layoutMode = dir;
    f.primaryAxisSizingMode = opt.primary || 'AUTO';
    f.counterAxisSizingMode = opt.counter || 'AUTO';
    f.itemSpacing = opt.gap != null ? opt.gap : 12;
    if (opt.pad != null) { f.paddingTop = f.paddingBottom = f.paddingLeft = f.paddingRight = opt.pad; }
    if (opt.padV != null) { f.paddingTop = f.paddingBottom = opt.padV; }
    if (opt.padH != null) { f.paddingLeft = f.paddingRight = opt.padH; }
    f.fills = opt.fill === undefined ? [] : opt.fill;
    f.name = opt.name || 'group';
    if (opt.radius) f.cornerRadius = opt.radius;
    if (opt.stroke) { f.strokes = [opt.stroke]; f.strokeWeight = opt.strokeWeight || 1; }
    if (opt.counterAlign) f.counterAxisAlignItems = opt.counterAlign;
    if (opt.primaryAlign) f.primaryAxisAlignItems = opt.primaryAlign;
    return f;
  };
  const put = (parent, node, sizing) => {
    parent.appendChild(node);
    if (sizing) {
      if (node.type === 'TEXT' && (sizing.h === 'FILL')) node.textAutoResize = 'HEIGHT';
      try { if (sizing.h) node.layoutSizingHorizontal = sizing.h; } catch (e) {}
      try { if (sizing.v) node.layoutSizingVertical = sizing.v; } catch (e) {}
    }
    return node;
  };
  // resize an auto-layout frame, then RE-ASSERT sizing modes
  // (Figma's resize() reverts primary/counter axis sizing to FIXED).
  const RS = (f, w, h, primary = 'AUTO', counter = 'AUTO') => {
    f.resize(w, h);
    try { f.primaryAxisSizingMode = primary; } catch (e) {}
    try { f.counterAxisSizingMode = counter; } catch (e) {}
    return f;
  };

  // ---------- design-system components ----------
  const dsNodes = page.findAllWithCriteria({ types: ['COMPONENT', 'COMPONENT_SET'] });
  const C = (name) => dsNodes.find((n) => n.name === name);
  const tagSet = C('Tag de estado');
  const btnSet = C('Botón');
  const barComp = C('Barra de progreso');
  const cardNumComp = C('Card numérica');
  const shellComp = C('Shell / Base');

  const missing = [];
  if (!tagSet) missing.push('Tag de estado');
  if (!btnSet) missing.push('Botón');
  if (!barComp) missing.push('Barra de progreso');
  if (!cardNumComp) missing.push('Card numérica');
  if (!shellComp) missing.push('Shell / Base');
  if (missing.length) { figma.notify('Faltan componentes: ' + missing.join(', ')); return; }

  const key = (node, base) => {
    const defs = node.componentPropertyDefinitions || {};
    return Object.keys(defs).find((k) => k === base || k.startsWith(base + '#')) || base;
  };
  const firstVariant = (set) => set.defaultVariant || set.children.find((c) => c.type === 'COMPONENT');

  const makeTag = (estado) => {
    const inst = firstVariant(tagSet).createInstance();
    try { inst.setProperties({ Estado: estado }); } catch (e) {}
    return inst;
  };
  const makeBtn = (tipo, label) => {
    const inst = firstVariant(btnSet).createInstance();
    const p = { Tipo: tipo };
    p[key(btnSet, 'label')] = label;
    try { inst.setProperties(p); } catch (e) {}
    return inst;
  };
  const makeCardNum = (value, label) => {
    const inst = cardNumComp.createInstance();
    const p = {};
    p[key(cardNumComp, 'value')] = String(value);
    p[key(cardNumComp, 'label')] = label;
    try { inst.setProperties(p); } catch (e) {}
    return inst;
  };
  const makeBar = (pct, width = 320) => {
    const inst = barComp.createInstance();
    try { inst.resize(width, inst.height); } catch (e) {}
    const fill = inst.findOne((n) => n.name === 'fill');
    if (fill) { try { fill.resize(Math.max(1, Math.round(width * pct / 100)), fill.height); } catch (e) {} }
    return inst;
  };

  // ---------- table ----------
  const TABLE_W = 1140;
  const headerRow = (cols, widths) => {
    const h = AL('HORIZONTAL', { primary: 'FIXED', counter: 'AUTO', gap: 16, padH: 16, padV: 10, fill: [GHOST()], name: 'header' });
    RS(h, TABLE_W, 40, 'FIXED', 'AUTO');
    cols.forEach((c, i) => {
      const cell = AL('HORIZONTAL', { gap: 0, fill: [], name: 'th' });
      put(cell, txt(c, { size: 12, lh: 16, weight: 'Medium', color: 'ink-muted' }));
      put(h, cell, { h: widths ? undefined : 'FILL', v: 'HUG' });
      if (widths) { cell.resize(widths[i], cell.height); cell.layoutSizingHorizontal = 'FIXED'; }
    });
    return h;
  };
  const dataRow = (cells, widths) => {
    const r = AL('HORIZONTAL', { primary: 'FIXED', counter: 'AUTO', gap: 16, padH: 16, padV: 12, fill: [WHITE()], name: 'fila', counterAlign: 'CENTER' });
    RS(r, TABLE_W, 44, 'FIXED', 'AUTO');
    r.strokes = [pVar('linea')];
    r.strokeAlign = 'INSIDE';
    r.strokeTopWeight = 0; r.strokeLeftWeight = 0; r.strokeRightWeight = 0; r.strokeBottomWeight = 1;
    cells.forEach((c, i) => {
      const node = typeof c === 'string' ? txt(c, { size: 14, lh: 20 }) : c;
      const cell = AL('HORIZONTAL', { gap: 0, fill: [], name: 'td', counterAlign: 'CENTER' });
      put(cell, node, node.type === 'TEXT' ? { h: 'FILL' } : undefined);
      put(r, cell, { v: 'HUG' });
      if (widths) { cell.resize(widths[i], cell.height); cell.layoutSizingHorizontal = 'FIXED'; }
      else cell.layoutSizingHorizontal = 'FILL';
    });
    return r;
  };
  const table = (header, rows) => {
    const wrap = AL('VERTICAL', { gap: 0, primary: 'AUTO', counter: 'FIXED', fill: [WHITE()], radius: 10, stroke: pVar('linea'), name: 'tabla' });
    RS(wrap, TABLE_W, 40, 'AUTO', 'FIXED');
    wrap.clipsContent = true;
    put(wrap, header, { h: 'FILL' });
    rows.forEach((row) => put(wrap, row, { h: 'FILL' }));
    return wrap;
  };

  // ---------- small bits ----------
  const chip = (label, on = true) => {
    const c = AL('HORIZONTAL', {
      gap: 6, padH: 10, padV: 4, radius: 20, name: 'chip',
      fill: [on ? pVar('accent', 0.1) : pHex('#EFEFEF')],
      stroke: on ? pVar('accent', 0.4) : pVar('linea'),
    });
    put(c, txt(label, { size: 12, lh: 16, weight: 'Medium', color: on ? 'accent' : 'ink-muted' }));
    return c;
  };
  const banner = (text, kind = 'advertencia') => {
    const b = AL('HORIZONTAL', { gap: 10, pad: 14, radius: 8, name: 'banner', fill: [pVar(kind, 0.1)], stroke: pVar(kind, 0.35), counterAlign: 'CENTER' });
    RS(b, TABLE_W, 48, 'FIXED', 'AUTO');
    put(b, txt(text, { size: 13, lh: 18, weight: 'Medium', color: kind }), { h: 'FILL' });
    return b;
  };
  const card = (name) => AL('VERTICAL', { gap: 12, pad: 20, radius: 10, name: name || 'card', fill: [WHITE()], stroke: pVar('linea') });
  const h1 = (s) => txt(s, { size: 26, lh: 32, weight: 'Semi Bold' });
  const h2 = (s) => txt(s, { size: 18, lh: 24, weight: 'Semi Bold' });
  const sub = (s) => txt(s, { size: 14, lh: 20, color: 'ink-muted' });
  const mono = (s) => txt(s, { size: 13, lh: 18, mono: true, color: 'ink-muted' });
  const badge = (s) => {
    const b = AL('HORIZONTAL', { gap: 0, padH: 8, padV: 2, radius: 4, name: 'badge', fill: [pVar('no-habilitado', 0.12)] });
    put(b, txt(s, { size: 11, lh: 14, weight: 'Medium', color: 'no-habilitado' }));
    return b;
  };

  // ---------- screen scaffold ----------
  const NAV_ITEMS = ['Inicio', 'Nuevo ciclo', 'Resultados', 'Historial', 'Homólogos', 'Configuración'];
  const makeScreen = (name, activeNav) => {
    const f = figma.createFrame();
    f.name = name;
    f.resize(1440, 900);
    f.clipsContent = true;
    f.fills = [WHITE()];
    const shell = shellComp.createInstance();
    shell.x = 0; shell.y = 0;
    f.appendChild(shell);
    let navs = shell.findAll((n) => n.type === 'INSTANCE' && (n.name === 'Item de nav' || n.name.indexOf('Estado=') === 0));
    // keep only the 6 nav items, top-to-bottom
    const ay = (n) => (n.absoluteBoundingBox ? n.absoluteBoundingBox.y : n.y);
    navs = navs.filter((n) => n.height <= 48).sort((a, b) => ay(a) - ay(b)).slice(0, 6);
    navs.forEach((n, i) => { try { n.setProperties({ Estado: i === activeNav ? 'Activo' : 'Inactivo' }); } catch (e) {} });
    const content = AL('VERTICAL', { gap: 24, primary: 'FIXED', counter: 'FIXED', fill: [], name: 'contenido' });
    RS(content, 1220, 860, 'FIXED', 'FIXED');
    content.paddingTop = 32; content.paddingBottom = 32; content.paddingLeft = 40; content.paddingRight = 40;
    content.clipsContent = true;
    f.appendChild(content);
    content.x = 220; content.y = 40;
    return { frame: f, content, navs };
  };
  const head = (content, title, subtitle, tag) => {
    const row = AL('HORIZONTAL', { gap: 10, counterAlign: 'CENTER', name: 'title' });
    put(row, h1(title));
    if (tag) put(row, badge(tag));
    put(content, row, { h: 'FILL' });
    if (subtitle) put(content, sub(subtitle), { h: 'FILL' });
  };

  // ---------- clean previous output ----------
  const GEN = ['01 Inicio', '02 Nuevo ciclo', '03 Ejecución', '04 Resultados', '05 Advertencias', '06 Historial', '07 Configuración', '08 Homólogos', 'Cover — contenido', 'Flow — diagrama'];
  page.children.filter((n) => GEN.includes(n.name)).forEach((n) => { try { n.remove(); } catch (e) {} });

  // ---------- sections ----------
  const sections = page.findAll((n) => n.type === 'SECTION');
  const sec = (name) => sections.find((s) => s.name === name);
  const secScreens = sec('Screens');
  const secCover = sec('Cover');
  const secFlow = sec('Flow');

  const links = []; // {from, to} resolved after build
  const screens = {};

  // ==========================================================================
  // 01 · INICIO
  // ==========================================================================
  {
    const S = makeScreen('01 Inicio', 0);
    head(S.content, 'Inicio', 'Estado de un vistazo y entrada a un ciclo nuevo.');

    const alert = banner('Falta configurar la carpeta de trabajo. Elegí entrada / salida / db en Configuración.', 'advertencia');
    put(S.content, alert, { h: 'FILL' });

    const last = card('Último ciclo');
    put(last, h2('Último ciclo'));
    const meta = AL('HORIZONTAL', { gap: 32, name: 'meta' });
    const m1 = AL('VERTICAL', { gap: 2 }); put(m1, sub('Fecha')); put(m1, mono('2026-08-25 10:42'));
    const m2 = AL('VERTICAL', { gap: 2 }); put(m2, sub('Experto usado')); put(m2, mono('experto_tint_2026-08.xlsx'));
    put(meta, m1); put(meta, m2);
    put(last, meta);
    const nums = AL('HORIZONTAL', { gap: 16, name: 'nums' });
    put(nums, makeCardNum(12, 'archivos generados (_ready)'));
    put(nums, makeCardNum(3, 'advertencias'));
    put(last, nums);
    put(S.content, last, { h: 'FILL' });

    const cta = AL('HORIZONTAL', { gap: 12, name: 'cta' });
    const bNuevo = makeBtn('Primario', 'Nuevo ciclo');
    const bRes = makeBtn('Secundario', 'Ver resultados');
    const bHist = makeBtn('Secundario', 'Historial');
    const bConf = makeBtn('Secundario', 'Configuración');
    put(cta, bNuevo); put(cta, bRes); put(cta, bHist); put(cta, bConf);
    put(S.content, cta);
    links.push({ from: bNuevo, to: '02 Nuevo ciclo' });
    links.push({ from: bRes, to: '04 Resultados' });
    links.push({ from: bHist, to: '06 Historial' });
    links.push({ from: bConf, to: '07 Configuración' });

    screens['01 Inicio'] = S;
  }

  // ==========================================================================
  // 02 · NUEVO CICLO — CARGAR Y REVISAR
  // ==========================================================================
  {
    const S = makeScreen('02 Nuevo ciclo', 1);
    head(S.content, 'Nuevo ciclo — cargar y revisar', 'Revisá qué se va a procesar antes de correr (el filtro tarda ~10 min).');

    const drop = AL('VERTICAL', { gap: 4, pad: 28, radius: 10, name: 'dropzone', fill: [GHOST()], stroke: pVar('linea'), counterAlign: 'CENTER', primaryAlign: 'CENTER' });
    RS(drop, TABLE_W, 120, 'FIXED', 'FIXED');
    drop.dashPattern = [6, 4];
    put(drop, txt('Arrastrá los archivos expertos acá', { size: 14, lh: 20, weight: 'Medium' }));
    put(drop, sub('o elegí una carpeta — se copian a la carpeta de entrada'));
    put(S.content, drop, { h: 'FILL' });

    const ctx = AL('HORIZONTAL', { gap: 10, counterAlign: 'CENTER', name: 'ctx' });
    put(ctx, sub('Homólogos activo:'));
    put(ctx, mono('homologos_TINT.xlsx'));
    put(ctx, sub('  ·  Tiendas:'));
    ['MP14', 'MP12', 'Tiendas 14', 'Tiendas 12'].forEach((c) => put(ctx, chip(c, true)));
    put(S.content, ctx);

    const t = table(
      headerRow(['Archivo', 'Software / destino', 'Flujo', 'Estado']),
      [
        dataRow(['experto_tint_2026-08.xlsx', 'xData', 'Filtro por homólogos', makeTag('OK')]),
        dataRow(['homologos_TINT.xlsx', 'xData', '—', makeTag('OK')]),
        dataRow(['listado_raro.xlsx', '—', '—', makeTag('Error')]),
      ]
    );
    put(S.content, t, { h: 'FILL' });

    const run = AL('HORIZONTAL', { gap: 16, counterAlign: 'CENTER', name: 'run' });
    const bRun = makeBtn('Primario', 'Ejecutar');
    put(run, bRun);
    put(run, sub('☐  ejecutar igual, omitiendo los que fallan'));
    put(S.content, run);
    links.push({ from: bRun, to: '03 Ejecución' });

    screens['02 Nuevo ciclo'] = S;
  }

  // ==========================================================================
  // 03 · EJECUCIÓN / PROGRESO
  // ==========================================================================
  {
    const S = makeScreen('03 Ejecución', 2);
    head(S.content, 'Ejecución / progreso', 'El sistema está trabajando. El filtro tarda ~10 min con las 4 tiendas.');

    const g = card('global');
    put(g, h2('62%  ·  06:12 transcurrido'));
    put(g, makeBar(62, TABLE_W - 40), { h: 'FILL' });
    put(S.content, g, { h: 'FILL' });

    const perStore = card('por tienda');
    put(perStore, h2('Progreso por tienda'));
    [['MP14', 100], ['MP12', 80], ['Tiendas 14', 45], ['Tiendas 12', 0]].forEach(([label, pct]) => {
      const row = AL('HORIZONTAL', { gap: 16, counterAlign: 'CENTER', name: 'store' });
      const l = txt(label, { size: 13, lh: 18, weight: 'Medium' });
      l.textAutoResize = 'HEIGHT';
      put(row, l); l.layoutSizingHorizontal = 'FIXED'; l.resize(90, l.height);
      put(row, makeBar(pct, 760));
      put(row, mono(pct + '%'));
      put(perStore, row);
    });
    put(S.content, perStore, { h: 'FILL' });

    const log = AL('VERTICAL', { gap: 3, pad: 14, radius: 8, name: 'log', fill: [pHex('#1B1F24')] });
    RS(log, TABLE_W, 120, 'FIXED', 'FIXED');
    ['▸ log en vivo (colapsable)', '[10:41:02] xData · MP14 · 128 IDs filtrados', '[10:44:19] xData · MP12 · 96 IDs filtrados', '[10:46:03] escribiendo _ready por tienda…'].forEach((line, i) => {
      put(log, txt(line, { size: 12, lh: 16, mono: true, hex: i === 0 ? '#E2E4E3' : '#8A94A0' }), { h: 'FILL' });
    });
    put(S.content, log, { h: 'FILL' });

    const bCancel = makeBtn('Secundario', 'Cancelar');
    put(S.content, bCancel);
    links.push({ from: S.frame, to: '04 Resultados' }); // click en cualquier lado → Resultados

    screens['03 Ejecución'] = S;
  }

  // ==========================================================================
  // 04 · RESULTADOS
  // ==========================================================================
  {
    const S = makeScreen('04 Resultados', 2);
    head(S.content, 'Resultados', 'Revisá y entregá lo generado.');

    const nums = AL('HORIZONTAL', { gap: 16, name: 'nums' });
    put(nums, makeCardNum(12, 'archivos generados'));
    put(nums, makeCardNum('240k', 'filas totales'));
    put(nums, makeCardNum(3, 'advertencias'));
    put(S.content, nums);

    put(S.content, h2('xData  →  MP14'));
    put(S.content, table(
      headerRow(['Salida', 'Tipo', 'Filas', 'Acciones']),
      [
        dataRow(['MP14_ready.csv', '.csv', '12.480', sub('Abrir · Carpeta · Previsualizar · Copiar')]),
        dataRow(['MP14_ready.xlsx', '.xlsx', '12.480', sub('Abrir · Carpeta · Previsualizar · Copiar')]),
      ]
    ), { h: 'FILL' });

    put(S.content, h2('xData  →  MP12'));
    put(S.content, table(
      headerRow(['Salida', 'Tipo', 'Filas', 'Acciones']),
      [dataRow(['MP12_ready.csv', '.csv', '9.610', sub('Abrir · Carpeta · Previsualizar · Copiar')])]
    ), { h: 'FILL' });

    const bWarn = makeBtn('Secundario', 'Ver advertencias y validación (3)');
    put(S.content, bWarn);
    links.push({ from: bWarn, to: '05 Advertencias' });

    screens['04 Resultados'] = S;
  }

  // ==========================================================================
  // 05 · ADVERTENCIAS
  // ==========================================================================
  {
    const S = makeScreen('05 Advertencias', 2);
    head(S.content, 'Advertencias', 'Qué quedó afuera y por qué. Puede vivir dentro de Resultados.');

    const filters = AL('HORIZONTAL', { gap: 12, counterAlign: 'CENTER', name: 'filtros' });
    put(filters, chip('Tipo: Todos', false));
    put(filters, chip('Archivo: Todos', false));
    put(filters, sub('  3 advertencias'));
    const bExport = makeBtn('Secundario', 'Exportar a texto');
    put(filters, bExport);
    put(S.content, filters);

    put(S.content, table(
      headerRow(['Tipo', 'Archivo', 'Detalle', 'Estado']),
      [
        dataRow(['Hoja no habilitada', 'experto_tint_2026-08.xlsx', 'Hoja "Tiendas 12" fuera de ENABLED_GRUPOS', makeTag('Advertencia')]),
        dataRow(['Hoja sin ID_TINT', 'experto_tint_2026-08.xlsx', 'Hoja "MP14 RAL" sin ningún ID_TINT', makeTag('Advertencia')]),
        dataRow(['Nombre no encontrado', '—', 'No hay homólogos con la convención esperada', makeTag('Advertencia')]),
      ]
    ), { h: 'FILL' });

    screens['05 Advertencias'] = S;
  }

  // ==========================================================================
  // 06 · HISTORIAL (v2)
  // ==========================================================================
  {
    const S = makeScreen('06 Historial', 3);
    head(S.content, 'Historial', 'Auditoría y re-descarga.', 'v2');

    put(S.content, table(
      headerRow(['Fecha / hora', 'Carpeta origen', 'Experto', 'Archivos', 'Advertencias']),
      [
        dataRow(['2026-08-25 10:42', 'D:\\TINT_SIS\\in\\ago', 'experto_tint_2026-08.xlsx', '12', '3']),
        dataRow(['2026-08-10 09:15', 'D:\\TINT_SIS\\in\\ago', 'experto_tint_2026-08a.xlsx', '12', '0']),
        dataRow(['2026-07-27 16:03', 'D:\\TINT_SIS\\in\\jul', 'experto_tint_2026-07.xlsx', '11', '1']),
      ]
    ), { h: 'FILL' });

    const note = card('nota');
    put(note, txt('Diff entre ciclos', { size: 13, lh: 18, weight: 'Semi Bold' }));
    put(note, sub('Colores nuevos / modificados / eliminados por línea contra el ciclo anterior — previsto para v2.'));
    put(S.content, note, { h: 'FILL' });

    screens['06 Historial'] = S;
  }

  // ==========================================================================
  // 07 · CONFIGURACIÓN
  // ==========================================================================
  {
    const S = makeScreen('07 Configuración', 5);
    head(S.content, 'Configuración', 'v1 mínimo: carpeta de trabajo + tiendas habilitadas.');

    const folders = card('Carpeta de trabajo');
    put(folders, h2('Carpeta de trabajo'));
    [['Entrada', 'D:\\TINT_SIS\\trabajo\\in'], ['Salida', 'D:\\TINT_SIS\\trabajo\\out'], ['Base de datos', 'D:\\TINT_SIS\\trabajo\\tint_sis.db']].forEach(([k, v]) => {
      const row = AL('HORIZONTAL', { gap: 16, counterAlign: 'CENTER' });
      const l = txt(k, { size: 13, lh: 18, weight: 'Medium' });
      l.textAutoResize = 'HEIGHT';
      put(row, l); l.layoutSizingHorizontal = 'FIXED'; l.resize(120, l.height);
      put(row, mono(v));
      put(folders, row);
    });
    put(S.content, folders, { h: 'FILL' });

    const stores = card('Tiendas habilitadas');
    put(stores, h2('Tiendas habilitadas'));
    [['MP14', true], ['MP12', true], ['Tiendas 14', true], ['Tiendas 12', false]].forEach(([name, on]) => {
      put(stores, txt((on ? '☑  ' : '☐  ') + name, { size: 14, lh: 20, color: on ? 'ink' : 'ink-muted' }));
    });
    put(S.content, stores, { h: 'FILL' });

    const note = card('nota');
    put(note, sub('v2: tabla de softwares / máquinas (nombre, formato, habilitado, carpeta de entrega) + nombres esperados de archivos. Hoy vive en ENABLED_GRUPOS de adapters/homologos_filter.py.'));
    put(S.content, note, { h: 'FILL' });

    screens['07 Configuración'] = S;
  }

  // ==========================================================================
  // 08 · HOMÓLOGOS (v2)
  // ==========================================================================
  {
    const S = makeScreen('08 Homólogos', 4);
    head(S.content, 'Homólogos (editor)', 'Mantener qué ID_TINT lleva cada tienda sin abrir Excel.', 'v2');

    const selector = AL('HORIZONTAL', { gap: 10, counterAlign: 'CENTER' });
    put(selector, sub('Tienda:'));
    put(selector, chip('MP14', true));
    put(S.content, selector);

    const cols = AL('HORIZONTAL', { gap: 24, name: 'cols' });

    const tree = card('árbol');
    RS(tree, 700, 40, 'AUTO', 'FIXED');
    put(tree, txt('▾  Línea: Látex', { size: 14, lh: 20, weight: 'Semi Bold' }));
    const homo = AL('VERTICAL', { gap: 4, name: 'homo' });
    homo.paddingLeft = 16;
    put(homo, txt('▾  Chilcomar Top 15 Ral', { size: 13, lh: 18, weight: 'Medium' }));
    const ids = AL('VERTICAL', { gap: 2 }); ids.paddingLeft = 16;
    ['TINT-0012', 'TINT-0034', 'TINT-0090', 'TINT-0142'].forEach((id) => put(ids, mono(id)));
    put(homo, ids);
    put(homo, txt('▸  Chilcomar Base Neutra', { size: 13, lh: 18, weight: 'Medium', color: 'ink-muted' }));
    put(tree, homo);
    put(cols, tree, { v: 'HUG' });

    const cover = card('cobertura');
    RS(cover, 380, 40, 'AUTO', 'FIXED');
    put(cover, h2('Cobertura'));
    put(cover, makeCardNum(14, 'ID_TINT del experto sin asignar'));
    put(cover, makeCardNum(2, 'homólogos sin ningún ID'));
    put(cols, cover, { v: 'HUG' });

    put(S.content, cols, { h: 'FILL' });

    const bSave = makeBtn('Primario', 'Guardar en homologos_TINT.xlsx');
    put(S.content, bSave);

    screens['08 Homólogos'] = S;
  }

  // ---------- place screens in the Screens section ----------
  const order = ['01 Inicio', '02 Nuevo ciclo', '03 Ejecución', '04 Resultados', '05 Advertencias', '06 Historial', '07 Configuración', '08 Homólogos'];
  const originX = secScreens ? secScreens.x + 80 : 3480;
  const originY = secScreens ? secScreens.y + 160 : 160;
  const STEP_X = 1560, STEP_Y = 1060, PER_ROW = 4;
  order.forEach((name, i) => {
    const S = screens[name];
    if (!S) return;
    if (secScreens) secScreens.appendChild(S.frame);
    S.frame.x = originX + (i % PER_ROW) * STEP_X;
    S.frame.y = originY + Math.floor(i / PER_ROW) * STEP_Y;
  });
  if (secScreens) {
    try { secScreens.resizeWithoutConstraints(Math.max(secScreens.width, PER_ROW * STEP_X + 160), Math.max(secScreens.height, 2 * STEP_Y + 220)); } catch (e) {}
  }

  // ==========================================================================
  // COVER
  // ==========================================================================
  {
    const cov = AL('VERTICAL', { gap: 14, pad: 48, radius: 16, name: 'Cover — contenido', fill: [pHex('#1B1F24')] });
    RS(cov, 1000, 560, 'FIXED', 'FIXED');
    put(cov, txt('TINT_SIS — UI', { size: 44, lh: 52, weight: 'Semi Bold', hex: '#FFFFFF' }));
    put(cov, txt('8 pantallas · app de escritorio Windows · 1440×900 · offline, 1 usuario', { size: 15, lh: 22, hex: '#8A94A0' }));
    put(cov, txt('Actualizado 2026-09-07', { size: 13, lh: 18, mono: true, hex: '#8A94A0' }));
    const legend = AL('VERTICAL', { gap: 6, name: 'legend' });
    legend.paddingTop = 24;
    [
      'Cover — esta portada',
      'Design system — tokens, text styles y 7 componentes',
      'Screens — las 8 pantallas con el Shell base',
      'Flow — flujo de navegación (prototype)',
    ].forEach((l) => put(legend, txt('•  ' + l, { size: 14, lh: 22, hex: '#E2E4E3' })));
    put(cov, legend);
    if (secCover) { secCover.appendChild(cov); cov.x = secCover.x + 60; cov.y = secCover.y + 120; }
    else { cov.x = 60; cov.y = 120; }
  }

  // ==========================================================================
  // FLOW — diagrama
  // ==========================================================================
  {
    const wrap = AL('VERTICAL', { gap: 0, pad: 40, name: 'Flow — diagrama', fill: [WHITE()], radius: 12, stroke: pVar('linea') });
    RS(wrap, 560, 40, 'AUTO', 'AUTO');
    put(wrap, txt('Flujo entre vistas', { size: 20, lh: 26, weight: 'Semi Bold' }));
    put(wrap, sub('Camino feliz. Los 6 ítems del nav conectan todas las pantallas entre sí (ver prototype en Screens).'));
    const spacerTop = AL('VERTICAL', { gap: 0 }); RS(spacerTop, 10, 16, 'FIXED', 'FIXED'); spacerTop.fills = []; put(wrap, spacerTop);

    const flowBox = (label, kind) => {
      const b = AL('HORIZONTAL', {
        gap: 0, padH: 18, padV: 12, radius: kind === 'end' ? 40 : 8, name: 'nodo',
        fill: [kind === 'end' ? pVar('accent', 0.12) : GHOST()],
        stroke: kind === 'end' ? pVar('accent', 0.5) : pVar('linea'),
        counterAlign: 'CENTER', primaryAlign: 'CENTER',
      });
      RS(b, 360, 44, 'FIXED', 'AUTO');
      put(b, txt(label, { size: 13, lh: 18, weight: 'Medium', color: kind === 'end' ? 'accent' : 'ink' }));
      return b;
    };
    const arrow = (caption) => {
      const a = AL('VERTICAL', { gap: 0, counterAlign: 'CENTER', name: 'arrow' });
      a.paddingTop = 6; a.paddingBottom = 6;
      put(a, txt('↓', { size: 18, lh: 20, weight: 'Medium', color: 'ink-muted' }));
      if (caption) put(a, txt(caption, { size: 11, lh: 14, color: 'ink-muted' }));
      return a;
    };

    const steps = [
      ['Inicio', null],
      ['Nuevo ciclo: cargar y revisar', null],
      ['Ejecución / progreso', 'Ejecutar'],
      ['Resultados', null],
      ['Advertencias', null],
    ];
    steps.forEach(([label, cap], i) => {
      if (i > 0) put(wrap, arrow(cap));
      put(wrap, flowBox(label));
    });
    put(wrap, arrow('Copiar a entrega'));
    put(wrap, flowBox('carpeta del técnico', 'end'));

    const branches = AL('VERTICAL', { gap: 4, name: 'ramas' });
    branches.paddingTop = 24;
    put(branches, txt('Ramas laterales', { size: 13, lh: 18, weight: 'Semi Bold' }));
    [
      'Inicio → Historial → Resultados',
      'Inicio → Homólogos (editor)',
      'Inicio → Configuración',
    ].forEach((l) => put(branches, sub(l)));
    put(wrap, branches);

    if (secFlow) {
      secFlow.appendChild(wrap);
      wrap.x = secFlow.x + 80; wrap.y = secFlow.y + 120;
      try { secFlow.resizeWithoutConstraints(Math.max(secFlow.width, 900), Math.max(secFlow.height, wrap.height + 260)); } catch (e) {}
    } else { wrap.x = 9980; wrap.y = 120; }
  }

  // ==========================================================================
  // PROTOTYPE — reactions
  // ==========================================================================
  const react = async (node, targetName) => {
    const target = screens[targetName] && screens[targetName].frame;
    if (!node || !target) return;
    const reaction = {
      trigger: { type: 'ON_CLICK' },
      actions: [{ type: 'NODE', destinationId: target.id, navigation: 'NAVIGATE', transition: null, preserveScrollPosition: false }],
    };
    try { await node.setReactionsAsync([reaction]); }
    catch (e) { try { node.reactions = [reaction]; } catch (e2) {} }
  };

  // nav → destino. Se intenta primero sobre los ítems del COMPONENTE Shell (una vez,
  // lo heredan las 8 pantallas); si Figma no deja, se reintenta por pantalla.
  const NAV_TO_SCREEN = ['01 Inicio', '02 Nuevo ciclo', '04 Resultados', '06 Historial', '08 Homólogos', '07 Configuración'];
  const wireNavList = async (list) => {
    for (let i = 0; i < list.length && i < NAV_TO_SCREEN.length; i++) {
      await react(list[i], NAV_TO_SCREEN[i]);
    }
  };
  let navOnComponent = false;
  try {
    const ay = (n) => (n.absoluteBoundingBox ? n.absoluteBoundingBox.y : n.y);
    let shellNavs = shellComp.findAll((n) => n.type === 'INSTANCE' && (n.name === 'Item de nav' || n.name.indexOf('Estado=') === 0));
    shellNavs = shellNavs.filter((n) => n.height <= 48).sort((a, b) => ay(a) - ay(b)).slice(0, 6);
    if (shellNavs.length === 6) { await wireNavList(shellNavs); navOnComponent = true; }
  } catch (e) {}
  if (!navOnComponent) {
    for (const name of order) {
      const S = screens[name];
      if (S) await wireNavList(S.navs);
    }
  }
  // explicit flow links collected during build
  for (const { from, to } of links) await react(from, to);

  // starting point
  try {
    if (screens['01 Inicio']) {
      page.flowStartingPoints = [{ nodeId: screens['01 Inicio'].frame.id, name: 'Flujo TINT_SIS' }];
    }
  } catch (e) {}

  // ---------- done ----------
  if (secScreens) { try { figma.viewport.scrollAndZoomIntoView([secScreens]); } catch (e) {} }
  figma.notify('TINT_SIS: 8 pantallas + Cover + Flow + prototype listos ✓');
})();
```
