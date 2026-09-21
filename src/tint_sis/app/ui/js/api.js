// Cliente HTTP minimo contra el FastAPI local.
async function req(method, path, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(`/api${path}`, opts);
  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      const j = await res.json();
      if (j.detail) detail = j.detail;
    } catch (e) {}
    throw new Error(detail);
  }
  return res.json();
}

export const api = {
  estado: () => req("GET", "/estado"),
  inicio: () => req("GET", "/inicio"),
  preview: () => req("GET", "/preview"),
  resultados: () => req("GET", "/resultados"),
  historial: () => req("GET", "/historial"),
  reveal: (ruta, modo = "carpeta") => req("POST", "/reveal", { ruta, modo }),
  runStart: () => req("POST", "/run"),
  runCurrent: () => req("GET", "/run/current"),
  runCancel: () => req("POST", "/run/cancel"),
  config: () => req("GET", "/config"),
  saveConfig: (c) => req("PUT", "/config", c),
  homologosTiendas: () => req("GET", "/homologos/tiendas"),
  homologosTienda: (tienda) => req("GET", `/homologos/${encodeURIComponent(tienda)}`),
  homologosAgregarId: (tienda, linea, homologo, id_tint) =>
    req("POST", `/homologos/${encodeURIComponent(tienda)}/ids`, { linea, homologo, id_tint }),
  homologosQuitarId: (tienda, linea, homologo, id_tint) =>
    req("DELETE", `/homologos/${encodeURIComponent(tienda)}/ids`, { linea, homologo, id_tint }),
  homologosAgregarHomologo: (tienda, linea, nombre) =>
    req("POST", `/homologos/${encodeURIComponent(tienda)}/homologos`, { linea, nombre }),
  homologosAgregarLinea: (tienda, nombre) =>
    req("POST", `/homologos/${encodeURIComponent(tienda)}/lineas`, { nombre }),
  homologosGuardar: () => req("POST", "/homologos/guardar"),
  openInput: () => req("POST", "/input/open"),
  async uploadInput(file) {
    const fd = new FormData();
    fd.append("file", file, file.name);
    const res = await fetch("/api/input/upload", { method: "POST", body: fd });
    if (!res.ok) throw new Error(`upload -> ${res.status}`);
    return res.json();
  },
};
