# TINT_SIS — contexto para Claude

Sistema del Departamento de Desarrollo e Investigación que toma los **3 archivos
expertos** de tintometría (llegan cada ~15 días), los filtra por tienda según la
**tabla de productos** y entrega a cada **software de máquina tintométrica** sus
archivos listos para importar. Motor en Python (`src/tint_sis/`) + app de
escritorio (FastAPI + UI HTML/JS vanilla + pywebview). Guía para el usuario:
`GUIA_USO.md` (mantenerla al día con cada cambio de flujo).

## Flujo actual (desde 2026-09-23)

```
data/input/
  Experto_1*.xlsx      Color Pro: Col.N-1/48 onzas = "AO-26.5" (código+cantidad juntos), hoja única
  Experto_2*.xls[xm]   Tintwise Lab: Col/Qty separados, cantidades YA en cm³, libro .xlsm con macros
  Experto_3*.xlsx      Santint/Corob: colorant_N / qnt_ml_N en Oz/48, hoja Formulas + IntegrityData
  productos_TINT.xlsx  tabla de productos (qué tiendas lleva cada producto, nombre en cada experto)
        │
        ▼  cada experto se lee UNA vez (adapters/sheet_filter.py)
data/output/Archivos filtrados/<Software>/<Tienda>_ready.<ext>
```

| Software | Experto | Tiendas | Formato |
|---|---|---|---|
| Santint | Experto 3 | Tiendas 14 | Excel |
| Corob_Tint | Experto 3 | Tiendas 14, Tiendas 12, MP12, MP14 | Excel |
| Tinwise_Lab | Experto 2 | Tiendas 14 | Excel (.xlsm) |
| Color_Pro3.1.1 | Experto 1 | Tiendas 14, Tiendas 12, MP12, MP14 | CSV |
| Color_Pro4.8 | Experto 1 | Tiendas 14 | Excel |
| Ibicus_Spa | Experto 1 | Tiendas 14 | Excel |

Definido en `SOFTWARES_DEFAULT` (`src/tint_sis/expertos.py`), pisable desde
`config.json` (clave `softwares`). Los nombres de carpeta son exactamente los que
pidió el usuario (incluido "Tinwise_Lab"). Santint era Tiendas 12 y el usuario lo
corrigió a Tiendas 14.

## Decisiones y por qué (no revertir sin hablarlo)

- **Filtro por PRODUCTO, no por ID_TINT.** Los 3 expertos no están alineados
  (distintas filas, orden y nombres de producto) y ninguno trae ID. En
  `homologos_TINT.xlsx` cada tienda toma productos completos (0 productos a
  medias) y cada homólogo `SUBP####` = 1 producto, así que una fila por producto
  en `productos_TINT.xlsx` alcanza. Con IDs se perdían fórmulas nuevas en
  silencio (p. ej. Látex/Extracubriente: 4.666 fórmulas en E3 vs 4.084 IDs).
- **Clave de producto:** Experto 1 y 2 → columna `Producto` (en E2 `Clasificacion`
  viene desalineada, no usarla); Experto 3 → `group_code / product_code`. Se
  ubican por encabezado. Comparación sin acentos, mayúsculas ni espacios
  (`expertos.normalizar`): E1 y E2 escriben distinto el mismo producto
  ("Ltx. Extracubriente Sipa" / "Ltx.Extracubriente Sipa").
- **Producto no listado en la tabla → no se entrega y se avisa en cada ciclo**
  (nunca se descarta en silencio). Producto en la tabla sin tiendas marcadas →
  no se entrega y no se avisa (decisión explícita).
- **Filtrado a nivel zip** (`sheet_filter.filtrar_libro`): copia byte a byte todo
  el libro salvo la hoja de fórmulas (streaming fila por fila, renumera filas,
  ajusta `<dimension>`, `<autoFilter>` y `_xlnm._FilterDatabase`). Así se
  conservan macros, ActiveX y hojas Colorants/Bases/Cans/Settings (E2) e
  IntegrityData (E3). openpyxl no sirve para esto (memoria y pierde macros).
  En E2 las únicas fórmulas son A1:F1 del encabezado y el calcChain solo las
  referencia; si alguna fila de datos trajera fórmulas, se deja el valor y se
  quita el calcChain. Cuidado: `writestr` muta el `ZipInfo` que recibe → siempre
  pasar uno nuevo (`_info_nueva`).
- **E2 ya viene en cm³** (26,5 oz/48 → 16,3273125 = ×29,574/48, verificado): no se
  convierte nada. La variante `_cm3` del flujo anterior se eliminó. Las cantidades
  son valores, no fórmulas de Excel.
- **Experto 1 debe venir en .xlsx**: el .xls corta en 65.535 filas (el real tiene
  204.056). Un `Experto_1*.xls` se detecta y se omiten sus softwares con aviso.
- **Expertos y tiendas habilitados** (interruptores ON/OFF en Configuración):
  un experto apagado no se lee, sus softwares no se generan y no hay aviso. En
  Nuevo ciclo figura "Desactivado" (rojo). Al pulsar Ejecutar se muestra un
  resumen (tiendas, expertos activos → softwares → tiendas/formato, lo que queda
  afuera, n° de archivos) que hay que confirmar.
- **No adivinar formatos de software**: todo formato nuevo se valida contra un
  archivo de referencia real. El CSV de Color Pro 3.1.1 (ISO-8859-1, coma, CRLF,
  celdas `AO-26.5` tal cual) todavía no tiene referencia real.

## Mapa del código

- `expertos.py` — `EXPERTOS` (label → columnas clave, glob), `SOFTWARES_DEFAULT`,
  `ENABLED_GRUPOS`, `PRODUCTOS_NAME`, `FILTRADOS_DIRNAME`, `normalizar`.
- `adapters/sheet_filter.py` — `filtrar_libro` (una lectura → un libro por tienda),
  `contar_claves` (catálogo de productos de un experto).
- `adapters/productos.py` — `leer_tabla` y `bootstrap_tabla` (arma la tabla desde
  homólogos + xData con ID_TINT + expertos; `cli productos-init`).
- `adapters/passthrough_csv.py` — xlsx → CSV (Color Pro 3.1.1).
- `pipeline.py` — `run_pipeline` / `planificar`: resuelve expertos (el de fecha
  más nueva, `routing.find_latest_expert`), filtra, entrega por software, registra
  en SQLite. Eventos de progreso: `inicio`, `experto_inicio/progreso/ok`, `mensaje`, `fin`.
- `preview.py` — dry-run para "Nuevo ciclo" (clasifica archivos, expertos, detalle
  por software para el resumen, bloqueantes/advertencias).
- `config.py` — `AppConfig` en `%LOCALAPPDATA%\TINT_SIS\config.json` (hoy apunta a
  `data/` del repo); `expertos_habilitados`, `softwares`, `filtrados_dirname`…
- `app/` — `api.py` (FastAPI), `_runner.py` (corrida en hilo + cancelación),
  `ui/` (vistas en `js/views/`, estilos en `css/app.css`, tokens en `css/tokens.css`).
- Flujo anterior, solo para `productos-init` y el editor de homólogos (legacy):
  `homologos_TINT.xlsx`, `xData_DATACOMPLETA_*.xlsx`, `adapters/homologos_filter.py`
  (`read_homologos_ids`, `read_expert_ids`), `adapters/homologos_editor.py`.

## Comandos

```powershell
.venv\Scripts\python -m pytest -q tests                  # 89 tests
.venv\Scripts\python -m tint_sis.cli run                 # ciclo completo (~90 s con los 3 expertos)
.venv\Scripts\python -m tint_sis.cli productos-init      # arma productos_TINT.xlsx (no sobrescribe; --force)
.venv\Scripts\python -m tint_sis.app --browser           # app en el navegador
# servidor suelto (como se viene usando): puerto fijo 8765
.venv\Scripts\python -c "import uvicorn; from tint_sis.app.server import app; uvicorn.run(app, host='127.0.0.1', port=8765)"
powershell -ExecutionPolicy Bypass -File scripts\build.ps1   # .exe + instalador
```

- Tras cambiar Python hay que **reiniciar el servidor** (JS/CSS se sirven sin caché:
  basta recargar el navegador).
- Pruebas de UI: Playwright con `p.chromium.launch(channel="msedge")` (el Chromium
  de Playwright instalado no coincide con la versión). Para no tocar la config
  real, levantar otra instancia con `LOCALAPPDATA` apuntando a una carpeta temporal
  (config.json propio) en otro puerto.
- Estilo: strings de Python sin tildes (convención existente del código); textos
  de la UI en JS con tildes. Tests con libros sintéticos en `tests/libros_prueba.py`.

## Datos reales (referencia, 2026-09-23)

- E1: 204.056 filas, 69 productos · E2: 186.478 filas, 58 productos · E3:
  174.368 filas, 58 productos. Tabla: 70 productos (70 homólogos de las 4 hojas).
- Salidas del último ciclo: Color Pro MP14/MP12/T14/T12 = 200.932 / 200.461 /
  175.358 / 168.742 filas; Tinwise T14 = 183.354; Santint T14 y Corob T14/MP14 =
  171.244; Corob T12 = 164.628; Corob MP12 = 170.824.
- `data/` está en `.gitignore` (expertos, tabla, salidas y DB quedan locales).
  `data/output/Tiendas filtradas/` es la salida del flujo anterior (legacy).

## Estado y pendientes

- Cambios en la rama `tres-expertos-por-software` (commit 78b818a, pusheada, sin
  mergear a `main`; el usuario suele commitear directo a `main`).
- **En curso:** el usuario prueba las importaciones de cada archivo filtrado en su
  software; los ajustes que salgan se corrigen sobre la marcha.
- Revisar `productos_TINT.xlsx`: ~20 filas con nota en `Revisar` (nombres
  sugeridos de E2/E1).
- "Tecnoconstrucción Mate Sipa" (E.A., 3.124 fórmulas en E1/E2/E3) está en la
  tabla sin tiendas: no va a ninguna hasta que el usuario lo marque.
- La vista "Advertencias" de la app es un marcador v2: los nombres de productos
  sin asignar solo se ven completos en la CLI (en la app solo el conteo).
  Propuesto (sin hacer): listar las advertencias en Resultados.
- v2: editar la tabla de productos y la lista de softwares desde la app.
- **Próximo plan (alcance por definir con el usuario):** "recibir un nuevo archivo
  experto que se adapte a los 3 formatos". Opciones planteadas:
  (a) un archivo maestro de tintometría del que TINT_SIS genere E1/E2/E3 (Oz/48
  concatenado, cm³ con hojas auxiliares, Oz/48 separado; falta definir de dónde
  salen Cartilla, Oz base y las hojas Colorants/Bases/Cans);
  (b) procedimiento de recepción cuando llegan los 3 actualizados (ya funciona:
  validar columnas al cargar, avisar productos nuevos, comparar con el ciclo
  anterior). Preguntar antes de planificar. Con el próximo experto con cambios se
  prueba un ciclo completo nuevo.
