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
  productos: () => req("GET", "/productos"),
  productosGuardar: (version, filas) => req("PUT", "/productos", { version, filas }),
  productosCatalogo: () => req("GET", "/productos/catalogo"),
  openInput: () => req("POST", "/input/open"),
  prepararEstado: () => req("GET", "/preparar/estado"),
  prepararConfirmar: (nuevos) => req("POST", "/preparar/confirmar", { nuevos }),
  prepararReiniciar: () => req("POST", "/preparar/reiniciar"),
  // Dropzone de Nuevo ciclo: {tipo: "entrada", preview} si era un experto o la
  // tabla (se copia a la carpeta de entrada) o {tipo: "maestro", preparar} si es
  // el archivo maestro (arranca su análisis).
  async uploadInput(file) {
    const fd = new FormData();
    fd.append("file", file, file.name);
    const res = await fetch("/api/input/upload", { method: "POST", body: fd });
    if (!res.ok) {
      let detail = `${res.status}`;
      try {
        const j = await res.json();
        if (j.detail) detail = j.detail;
      } catch (e) {}
      throw new Error(detail);
    }
    return res.json();
  },
};
