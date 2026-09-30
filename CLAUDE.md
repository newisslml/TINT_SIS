# TINT_SIS — contexto para Claude

Sistema del Departamento de Desarrollo e Investigación que toma los **3 archivos
expertos** de tintometría (llegan cada ~15 días), los filtra por tienda según la
**tabla de productos** y entrega a cada **software de máquina tintométrica** sus
archivos listos para importar. Motor en Python (`src/tint_sis/`) + app de
escritorio (FastAPI + UI HTML/JS vanilla + pywebview). Guía para el usuario:
`GUIA_USO.md` (mantenerla al día con cada cambio de flujo).

## Flujo actual (desde 2026-09-23; preparación desde el maestro desde 2026-09-28)

```
Archivo maestro de tintometría ("Todo  MP14 <DDMMAAAA>.xlsx", formato Experto 1)
        │  arrastrado arriba en "Nuevo ciclo" (preparar.py): compara con el E1 anterior y la tabla,
        │  suma productos nuevos a la tabla, genera E1/E2/E3 (E2/E3 sobre el
        │  experto anterior como plantilla); lo anterior → backups/expertos/<fecha>/
        ▼
data/input/
  Experto_1*.xlsx      Color Pro: Col.N-1/48 onzas = "AO-26.5" (código+cantidad juntos), hoja única
  Experto_2*.xls[xm]   Tintwise Lab: Col/Qty separados, cantidades YA en cm³, libro .xlsm con macros
  Experto_3*.xlsx      Santint/Corob: colorant_N / qnt_ml_N en Oz/48, hoja Formulas + IntegrityData
  productos_TINT.xlsx  tabla de productos (qué tiendas lleva cada producto, nombre en cada experto)
        │
        ▼  cada experto se lee UNA vez (adapters/sheet_filter.py)
data/output/Archivos filtrados/<Software>/<Tienda>_ready_<DD_MM_YYYY>.<ext>
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
- **Backup del ciclo anterior** (`backups.py`, pedido 2026-09-24): al empezar un
  ciclo que va a generar algo, todo `Archivos filtrados/` se mueve a
  `<output_dir>/../backups/<AAAA-MM-DD_HH-MM>/` (fecha local del ciclo más nuevo
  de la base que generó esos archivos; sin registro → mtime; colisión → `_2`).
  Se mueve con `os.replace` y si un archivo está abierto se revierte todo y se
  lanza `RespaldoError` (el runner lo muestra sin traceback). Los registros de la
  base pasan a la ruta del backup; Historial marca como no disponibles los
  archivos de ciclos viejos que un ciclo posterior pisó (antes del backup cada
  ciclo sobrescribía al anterior).
- **Fecha en el nombre de salida** (pedido 2026-09-24): `<Tienda>_ready_<DD_MM_YYYY>`
  con la fecha del experto que alimenta a ese software (`routing.fecha_experto`:
  la del nombre `_DD_MM_YYYY`; si no la trae, su mtime y se avisa en el log). En un
  ciclo cada software puede llevar fecha distinta. El nombre viaja igual a
  `backups/`. El preview expone `fecha`/`fecha_del_nombre` por experto.
- **No adivinar formatos de software**: todo formato nuevo se valida contra un
  archivo de referencia real. El CSV de Color Pro 3.1.1 (ISO-8859-1, coma, CRLF,
  celdas `AO-26.5` tal cual) todavía no tiene referencia real.
- **Preparar experto desde el maestro** (pedido y decisiones del usuario
  2026-09-28; `preparar.py`, `maestro.py`, `adapters/libro_writer.py`):
  - El maestro = formato E1. Reglas E1→E2/E3 **verificadas contra los expertos
    del 24/09** (E3: 174.124 filas idénticas en todas las columnas; E2: 173.977
    sin contar las columnas que el E2 anterior tenía desalineadas). Ver docstring
    de `maestro.py`. Detalles que importan: E3 `group_code` con la grafía exacta
    de la plantilla ("Látex " con espacio), bases normalizadas a la grafía de la
    plantilla E3 ("BASE N" → "Base N"), E2 `Clasificacion` con la grafía de la
    plantilla E2 ("Latex" → "Latex "), códigos de colorante en mayúscula, E2
    `ColN` con un espacio adelante (" AO"), E2 `Note2` = Primer.
  - **E2/E3 completos desde el maestro** (decisión del usuario), usando el
    E2/E3 anterior solo como plantilla: se reemplaza la hoja Formulas a nivel
    zip (sharedStrings: se reutilizan índices y se agregan textos al final;
    estilo de cada columna tomado de la 1.ª fila de datos). Sin plantilla ese
    experto no se genera.
  - **Todos los productos del maestro van a E2/E3**, incluidos los 11 "solo MP"
    (CP-70, CK-70, BM-70, NL7000S, Murovid, Stain Vid) que antes no estaban
    (decisión del usuario: Corob MP14/MP12 los recibe). Los nombres de E2/E3 que
    falten en la tabla se completan al preparar (E2 = nombre de E1; E3 =
    "<grupo de su clasificación> / <nombre E1>").
  - **Todo a galón en E2/E3** (decisión del usuario): `Tineta 4 gl` ÷ 4
    (`FORMATOS_GALONES`; verificado: Texturex = 4× sus homólogos en galón en
    53.706 pares). La preparación deja E1 tal cual. Formato desconocido o colorante ilegible
    → bloquea la preparación. El 28/09 (15:07) el usuario pidió **también E1 en
    galón**: se convirtió el maestro antes de preparar (Tineta 4 gl → `Galon`,
    colorantes y `Oz base` ÷ 4, con Decimal; script de sesión, no está en el repo).
    Si vuelve a llegar en tineta, preguntar si se lleva esa conversión a `preparar.py`.
    Ojo: un archivo `Experto_28_09_2026.xlsx` en la entrada calza con el glob
    `Experto_2*` y se toma como Experto 2 (bloquea la preparación por plantilla sin
    columnas): los maestros van en `data/maestros/`, nunca con nombre `Experto_*`.
  - **Fórmulas duplicadas se dejan una vez** (decisión del usuario, 2026-09-30):
    la clave es **Clasificación + Producto + Cartilla + Color + Base**
    (`maestro.CLAVE_FORMULA`, con `normalizar`; RGB, notas, formato y colorantes
    no cuentan). Se deja la primera fila del maestro en E1/E2/E3
    (`sheet_filter.quitar_filas_repetidas(clave=...)`), aviso por producto con
    cuántas traían colorantes distintos y hoja "Duplicadas" en el resumen. Antes
    (hasta el 30/09) solo se quitaban filas idénticas en todas las columnas.
    Maestro `data/maestros/Experto2_.xlsx` (30/09): 4.496 duplicadas (Construcolor
    4.064, 3 con colorantes distintos; 72 en cada una de las 6 texturas).
  - **E3 sin cartilla** (decisión del usuario, 2026-09-30): E3 no tiene columna
    Cartilla, así que su clave es `maestro.CLAVE_FORMULA_E3` (Clasificación +
    Producto + Color + Base) y del mismo color en varias cartillas va solo la
    primera. E1/E2 siguen con Cartilla. Con `Experto2_.xlsx`: E1/E2 = 228.179,
    E3 = 227.038 (1.141 fuera, 405 de ellas con colorantes distintos, p. ej.
    Acrilina GF 1088 Muestrario vs Sipamundo). El E3 original de tintometría
    (24/09) ya traía estos pares indistinguibles (color_key2/3 vacíos).
  - Producto del maestro que no está en la tabla = **producto nuevo**: el
    usuario elige tiendas (default: todas) y nombres E2/E3 en la app; se agrega
    a la tabla con nota `Preparación <fecha>` en `Revisar`.
  - Tabla o experto a reemplazar abierto en Excel → `PreparacionError` antes de
    mover nada. Expertos viejos que no se pueden mover quedan con aviso (el ciclo
    usa el más nuevo).

## Mapa del código

- `expertos.py` — `EXPERTOS` (label → columnas clave, glob), `SOFTWARES_DEFAULT`,
  `ENABLED_GRUPOS`, `PRODUCTOS_NAME`, `FILTRADOS_DIRNAME`, `normalizar`.
- `adapters/sheet_filter.py` — `filtrar_libro` (una lectura → un libro por tienda),
  `contar_claves` (catálogo de productos de un experto), `contar_valores`
  (grafía cruda), `iterar_filas`, `quitar_filas_repetidas`.
- `adapters/libro_writer.py` — `reescribir_hoja` (plantilla + filas nuevas en la
  hoja Formulas, resto byte a byte), `encabezado`.
- `adapters/productos.py` — `leer_tabla`, `leer_filas_tabla`, `actualizar_tabla`
  (productos nuevos + nombres faltantes) y `bootstrap_tabla` (arma la tabla desde
  homólogos + xData con ID_TINT + expertos; `cli productos-init`).
- `maestro.py` — lectura del archivo maestro y conversión por fórmula a E2/E3
  (`parse_colorante`, `FORMATOS_GALONES`, `Plantilla`, `fila_e2`, `fila_e3`).
- `preparar.py` — `analizar_maestro` (no escribe) / `preparar_expertos` /
  `ultimo_resumen`; resumen en `<salida>/Preparacion expertos/Resumen_<fecha>.xlsx|json`.
  App: `app/_preparar.py` (hilo + estado), rutas `/api/preparar/*`; panel
  `js/preparacion.js` dentro de "Nuevo ciclo" (pedido del usuario 2026-09-28: sin
  menú aparte, todo el flujo desde el dropzone de Nuevo ciclo). `/api/input/upload`
  decide por nombre (`api.es_archivo_de_entrada`): Experto_N*/tabla/legacy → entrada;
  cualquier otro Excel → maestro (se guarda en `data/maestros/` y se analiza).
  Ejecutar queda bloqueado con un maestro analizándose, analizado o preparándose.
- `adapters/passthrough_csv.py` — xlsx → CSV (Color Pro 3.1.1).
- `pipeline.py` — `run_pipeline` / `planificar`: resuelve expertos (el de fecha
  más nueva, `routing.find_latest_expert`), respalda el ciclo anterior
  (`backups.respaldar_filtrados`), filtra, entrega por software, registra
  en SQLite. Eventos de progreso: `inicio`, `experto_inicio/progreso/ok`, `mensaje`, `fin`.
- `preview.py` — dry-run para "Nuevo ciclo" (clasifica archivos, expertos, detalle
  por software para el resumen, bloqueantes/advertencias).
- `config.py` — `AppConfig` en `%LOCALAPPDATA%\TINT_SIS\config.json` (hoy apunta a
  `data/` del repo); `expertos_habilitados`, `softwares`, `filtrados_dirname`…
- `app/` — `api.py` (FastAPI), `_runner.py` (corrida en hilo + cancelación),
  `ui/` (vistas en `js/views/`, estilos en `css/app.css`, tokens en `css/tokens.css`:
  paleta Codelpa de `paleta_colores_TINT_SIS.md`, fondo claro sin degradado y modo
  oscuro automático con `prefers-color-scheme`; colores nuevos siempre como token).
- Vista **Homólogos** (`js/views/homologos.js`, pedido del usuario 2026-09-28) =
  editor de `productos_TINT.xlsx`: agrupado por línea, nombre por experto con
  fórmulas contadas contra los expertos del ciclo, casillas de tienda,
  agregar producto / nueva línea, eliminar, "productos de los expertos que no
  están en la tabla". Copia de trabajo en el navegador; `PUT /api/productos`
  reescribe la hoja Productos (`productos.guardar_edicion`: valida producto sin
  nombre / mismo nombre de experto en dos productos / tiendas desconocidas,
  conserva Notas y demás hojas, respaldo en `backups/productos/<fecha>/`,
  rechaza si cambió en disco desde la versión leída o si está abierta en Excel).
  `GET /api/productos/catalogo` = `contar_claves` de cada experto, cacheado por
  mtime. Salir con cambios sin guardar pregunta (`main.js`: una vista puede
  devolver `{cleanup, puedeSalir}`). El editor viejo de `homologos_TINT.xlsx`
  por ID_TINT y sus rutas `/api/homologos/*` se quitaron.
- Flujo anterior, solo para `productos-init` (legacy): `homologos_TINT.xlsx`,
  `xData_DATACOMPLETA_*.xlsx`, `adapters/homologos_filter.py`
  (`read_homologos_ids`, `read_expert_ids`), `adapters/homologos_editor.py`.

## Comandos

```powershell
.venv\Scripts\python -m pytest -q tests                  # 163 tests
.venv\Scripts\python -m tint_sis.cli preparar "<maestro>.xlsx" --solo-analizar   # resumen (~1 min)
.venv\Scripts\python -m tint_sis.cli preparar "<maestro>.xlsx" --tiendas todas   # genera E1/E2/E3 (~3 min en total)
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
- **Ojo con el config.json aislado**: escribirlo sin BOM (desde Python con
  `json.dump`, no con `Out-File -Encoding utf8` de PowerShell 5.1). Si no se puede
  leer, `load_config` vuelve en silencio a los defaults = `data/` real del repo
  (el 30/09 una prueba "aislada" de `cli preparar` pisó `data/input` por esto).
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
- Maestro del 28/09/2026 (`C:\videosWILLIAM\Archivos de Trabajo\GRANITEX Y HOMOLOGOS
  28092026\Todo  MP14 28092026.xlsx`): 232.675 filas = E1 del 24/09 − 31 filas
  "NO DISPONIBLE" + Texturas / "Texturex y Homologos" (28.650 filas = 6 × 4.775,
  Tineta 4 gl). `GARNITEX Y HOMOLOGOS 28092026.xlsx` = solo ese bloque (con
  Observaciones y "-0"). Preparado en una copia aislada: E1/E2/E3 de 208.800
  fórmulas; ciclo sin advertencias, T14 = 180.102 en los 6 softwares, MP14 =
  205.676, MP12 = 205.205, T12 = 173.486.
- Problemas de datos del maestro (avisados al usuario, para tintometría): Col.5
  corrida en 39 fórmulas (en el maestro está en Oleo Opaco CP-70 y Plastikote 13;
  en E2/E3 viejos en Cerestain Deck, Vitrolux 60 y Chilcostain Pro); Ltx.
  Construcolor con 4.083 colores duplicados (bloque Base P/W/N/U); E.A.
  Tecnoconstrucción Mate difiere en 184 colores del E2/E3 viejo. El E2 del 24/09
  tenía un bloque de texturas duplicado (12.110 filas) y Clasificacion/RGB/Note1
  desalineados en ~143 mil filas (el generado lo corrige).

## Estado y pendientes

- Cambios en la rama `tres-expertos-por-software` (commit 78b818a, pusheada, sin
  mergear a `main`; el usuario suele commitear directo a `main`).
- **Versión 0.3.0** (28/09/2026, "ya en producción"): preparación desde el maestro,
  editor de Homólogos y fechas DD/MM/AA en Historial. `dist/installer/TINT_SIS_Setup_0.3.0.exe`
  y paquete `dist/TINT_SIS_0.3.0_instalacion(.zip)` = instalador + LEEME (actualizar
  desde 0.2.x / PC nuevo) + `TINT_SIS\input` con la tabla y los E1/E2/E3 del 28/09.
  Exe probado aislado (LOCALAPPDATA temporal): ventana "TINT_SIS 0.3.0", rutas
  /api/preparar/* y /api/productos OK. Todo sin commitear.
- **Versión 0.3.1** (30/09/2026): duplicadas por Clasificación+Producto+Cartilla+
  Color+Base y sin el aviso de "carpeta de entrega" en Inicio.
  `dist/installer/TINT_SIS_Setup_0.3.1.exe` y `dist/TINT_SIS_0.3.1_instalacion(.zip)`
  = instalador + LEEME + `TINT_SIS\input\productos_TINT.xlsx` (sin expertos, a
  pedido del usuario). Exe sin probar abierto. Sin commitear. **Ojo:** ese
  instalador es anterior a la regla "E3 sin cartilla"; hay que regenerarlo.
- **En curso:** el usuario prueba las importaciones de cada archivo filtrado en su
  software; los ajustes que salgan se corrigen sobre la marcha.
- Revisar `productos_TINT.xlsx`: ~20 filas con nota en `Revisar` (nombres
  sugeridos de E2/E1).
- "Tecnoconstrucción Mate Sipa" (E.A., 3.124 fórmulas en E1/E2/E3) está en la
  tabla sin tiendas: no va a ninguna hasta que el usuario lo marque (por eso MP14
  sale con 205.676 y no 208.800; se marca desde la vista Homólogos).
- La vista "Advertencias" de la app es un marcador v2: los nombres de productos
  sin asignar solo se ven completos en la CLI (en la app solo el conteo).
  Propuesto (sin hacer): listar las advertencias en Resultados.
- v2: editar la lista de softwares desde la app (la tabla de productos ya se edita en Homólogos).
- **Preparación desde el maestro (2026-09-28)**: el usuario ya la corrió sobre
  `data/` real (12:28) con `Todo  MP14 28092026 (sin duplicados).xlsx` (archivo de
  prueba = maestro sin las 23.875 filas repetidas, 208.800 fórmulas, junto al
  original en `C:\videosWILLIAM\...\GRANITEX Y HOMOLOGOS 28092026\`): quedaron
  `Experto_1/2/3_28_09_2026` en `data/input` y lo anterior en
  `data/backups/expertos/2026-09-28_12-27/`. `Experto_1.xlsx` y `Experto_3.xlsx`
  (sin fecha) siguen en la entrada porque estaban abiertos en Excel. Falta probar
  las importaciones de E2 (Tintwise) y E3 (Corob/Santint) generados, sobre todo
  Texturex (galón, base "según producto") y los 11 productos MP nuevos en Corob.
  La hoja Bases del E2 no se toca (sus listas ya no coincidían con Formulas).
  Re-preparado el 28/09 a las 15:07 con `data/maestros/Todo  MP14 28092026 galon.xlsx`
  (el maestro completo que el usuario dejó en la entrada como `Experto_28_09_2026.xlsx`,
  idéntico fila a fila al original; movido a `data/maestros/... (original tineta).xlsx`):
  E1 = 208.800 fórmulas con Texturex en Galon (Oz base 68,625); E2/E3 byte a byte
  iguales a los de las 12:48; lo anterior en `data/backups/expertos/2026-09-28_15-07/`.
  El ciclo con estos expertos todavía no se ejecutó.
  **Maestro correcto (28/09, 15:52)**: el usuario entregó `data/maestros/Experto_.xlsx`
  con Texturex separado en 6 productos (Texturas GRANITEX GF/GM SOQUINA, ACRILINA
  GF/GM/GA CONSTRUCCION, SIPALINA G1 SIPA; 4.775 filas c/u, 72 repetidas exactas c/u)
  rotulados "Galon" pero con dosis de tineta (exactamente 4× sus homólogos en galón
  en todas las cantidades comparadas). Por decisión del usuario se dividió por 4 →
  `data/maestros/Todo  MP14 28092026 texturas.xlsx` (resto idéntico; Oz base viene
  vacío en esos 6). Tiendas: `data/Homologos.xlsx` (listado Twist por tienda, hojas
  MP14/MP12/Tiendas 14/Tiendas 12) tiene sus homólogos (Granitex GF-GM, Acrilina
  GF-GM-GA, Sipalina G1) en las 4 tiendas y coincide con la tabla en toda la línea
  Texturas → los 6 nuevos van a las 4. Preparado a las 15:57: E1/E2/E3 de 232.243
  fórmulas, tabla con 6 filas nuevas, anterior en `data/backups/expertos/2026-09-28_15-57/`.
  A validar en la importación: E3 `base_code` "BASE BLANCA" es nueva para Santint/Corob
  (las conocidas: Blanca, BU Universal, Base N…) y los `product_code` largos
  ("Texturas ACRILINA GF CONSTRUCCION"). "Texturex y Homologos" ya no viene en el
  maestro ni en Homologos.xlsx (su fila sigue en la tabla, sin fórmulas).
