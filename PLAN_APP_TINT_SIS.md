# Plan: app de escritorio TINT_SIS (vistas gráficas + ajustes para comenzar)

Plan de trabajo para envolver el motor de TINT_SIS (hoy CLI) en una **app de
escritorio con interfaz gráfica**, y los ajustes previos al motor que hacen falta
para empezar. El detalle de pantallas está en `VISTAS_TINT_SIS.md`.

---

## 0. Estado actual del motor

- CLI: `python -m tint_sis.cli run`. Código en `src/tint_sis/`
  (`pipeline`, `adapters`, `routing`, `db`, `validation`, `ingestion`).
- Flujos que **ya funcionan y están verificados**:
  1. **FORMULARIO clásico** → `.txt` CorobLab (piloto, validado contra archivo
     real).
  2. **Passthrough CSV** — `expert_<GRUPO>_<MAQUINA>.xlsx`, máquina `Corob4.1.2`
     → `.csv` + copia `.xlsx`.
  3. **Filtro por homólogos (xData)** — `homologos_TINT.xlsx` (maestro fijo) +
     `xData_DATACOMPLETA_<DD_MM_YYYY>.xlsx` (experto por fecha, se toma el más
     nuevo) → por tienda (MP14 / MP12 / Tiendas 14 / Tiendas 12) un
     `<grupo>_ready.xlsx` + `<grupo>_ready.csv` (ISO-8859-1, coma, CRLF).
     Verificado end-to-end: 186.475 / 186.004 / 162.129 / 156.741 filas, 0
     duplicados, 0 IDs perdidos.
- Auditoría en `data/tint_sis.db` (SQLite): `batches`, fórmulas, `issues`,
  archivos generados.
- Tests: **54 en verde** (`pytest -q`).

---

## 1. Objetivo de esta fase

Que el **Departamento de Desarrollo e Investigación** opere TINT_SIS sin terminal:
cargar el experto del ciclo, revisar qué se va a procesar, correr, revisar
resultados y advertencias, y entregar la GData a los técnicos de máquina.

---

## 2. Decisiones tomadas

| Tema | Decisión |
|---|---|
| Formato | App de escritorio, **ejecutable Windows** (carpeta con `.exe`, sin instalar Python). |
| Usuarios | **1 usuario, 1 PC**, offline. |
| Perfil del usuario | Depto. Desarrollo e Investigación (técnico de dominio; vocabulario de tintometría OK). |
| Homólogos | **Editables desde la app** (no hace falta abrir Excel). |
| Multi-software | La app debe servir a **todos** los softwares de máquina. Hoy CorobLab + xData; próximo **SANTINT**; luego Fluid / Tintwise_Lab / Ibicus. |

---

## 3. Arquitectura

- **Motor intacto:** `tint_sis` (pipeline / adapters / routing / db) **no cambia
  su lógica**; solo se le agregan puntos de extensión (config, progreso,
  preview) — ver §5.
- **Capa app nueva:** `src/tint_sis/app/`
  - `api.py` — funciones que la UI llama: correr ciclo, previsualizar,
    leer historial, leer/escribir config, leer/escribir homólogos.
  - `server.py` — FastAPI local que expone `api.py` en `127.0.0.1`.
  - `ui/` — HTML/CSS/JS (las vistas de `VISTAS_TINT_SIS.md`).
  - `main.py` — arranca el server y abre la ventana pywebview.
- **Adaptadores por software (patrón ya presente en el repo):** cada software es
  un módulo en `src/tint_sis/adapters/` + un registro en `routing.py` / config.
  **Sumar SANTINT = `adapters/santint.py` + una entrada de config**, sin tocar la
  UI.

---

## 4. Stack y empaquetado

| Pieza | Elección | Motivo |
|---|---|---|
| UI | HTML/CSS/JS (vanilla + Alpine/htmx, o React si se prefiere) | Traduce casi 1:1 el diseño de Figma; rápido de iterar. |
| Ventana | **pywebview** | Ventana de escritorio propia (no una pestaña de navegador). |
| Backend local | **FastAPI** + uvicorn en `127.0.0.1`, puerto efímero | Reusa Python; deja la puerta abierta al "panel web / nube" del `plan-tint_sis.md`. |
| Empaquetado | **PyInstaller `--onedir`** → carpeta `TINT_SIS/` con `TINT_SIS.exe` | `--onefile` posible pero arranque más lento (openpyxl + `Formulas` de 186k filas). |
| Trabajo largo | El `run` en hilo/proceso aparte; progreso a la UI por WebSocket o polling | El filtro tarda ~10 min; la UI no debe bloquear. |

*Alternativa 100% nativa:* PySide6 + PyInstaller. Más "escritorio puro" pero más
lento de estilar y de mapear contra Figma. Para un tool interno de 1 usuario,
pywebview rinde mejor.

---

## 5. Ajustes al motor previos a la UI

### 5.1 Configuración en archivo
- Nuevo `src/tint_sis/config.py`: carga `config.json` desde la carpeta de trabajo
  (o `%LOCALAPPDATA%\TINT_SIS\config.json`); **defaults = los valores actuales del
  código**.
- Migrar a config: `ENABLED_GRUPOS` (`adapters/homologos_filter.py`),
  `MACHINE_OUTPUT_FORMATS` (`routing.py`), rutas input/output/db, nombre del
  homólogos maestro y patrón del experto.
- Los módulos leen de config con fallback al default; los tests siguen
  monkeypatcheando.

### 5.2 Callback de progreso
- `run_pipeline(..., on_progress: Callable[[ProgressEvent], None] | None = None)`.
- `run_homologos_filter` y el loop de líneas emiten eventos
  `{fase, item, indice, total, mensaje}` en vez de solo `print`.
- La CLI pasa un callback que imprime (comportamiento actual); la app pasa uno
  que empuja a la UI.

### 5.3 Previsualizar ciclo (dry-run)
- Nueva función `preview_batch(input_dir) -> list[PlannedFile]`: por cada `.xlsx`
  de entrada devuelve `{archivo, software, flujo, estado, detalle}` **sin**
  ejecutar el filtro pesado.
- Reusa `parse_expert_filename`, `find_homologos_master_pair`, chequeo de
  sidecars, `ENABLED_GRUPOS`, `MACHINE_OUTPUT_FORMATS`.
- Alimenta la vista "Nuevo ciclo".

### 5.4 Carpeta de entrega por software/tienda
- Config: `delivery_paths: { "<software|grupo>": "<ruta>" }`.
- `api.py`: acción "copiar salida a entrega" (copia los `_ready` / `.txt` /
  `.csv` al destino).

### 5.5 Resultado estructurado
- `PipelineSummary` ya trae casi todo; agregar por archivo generado: software,
  línea/tienda, tipo, nº filas, ruta. Alimenta Resultados sin re-parsear.

---

## 6. Carpetas / configuración / datos

- **Carpeta de trabajo** (elegida en el primer arranque, guardada en config):
  contiene `input/`, `output/`, `tint_sis.db`.
  Default sugerido: `Documentos\TINT_SIS\` *(a confirmar)*.
- `config.json` junto a la carpeta de trabajo.
- El `.exe` y sus assets viven en su propia carpeta; **no asume layout de repo**.

---

## 7. Vistas y orden de construcción

Detalle en `VISTAS_TINT_SIS.md`. Hitos:

1. **MVP — reemplaza la terminal:** Config mínima + Nuevo ciclo (preview) +
   Ejecución (progreso) + Resultados + Advertencias. Cubre el **flujo xData
   completo** (el primero que se va a usar).
2. Historial + progreso fino + "copiar a entrega".
3. Editor de Homólogos.
4. Configuración completa (softwares/máquinas, Familia→prefijo) + preparado para
   SANTINT.

---

## 8. Multi-software — hoja de ruta

| Software | Estado | Qué falta |
|---|---|---|
| **CorobLab 4.1.2** | ✅ funcionando (`.txt`) | — |
| **xData** | ✅ funcionando (filtro homólogos → CSV) | consolidarlo como flujo principal en la app; es lo primero que se usará |
| **SANTINT** | ⏳ próximo | **archivo de referencia real** generado por esa máquina → nuevo `adapters/santint.py` + registro en config. No se adivina el formato (mismo criterio que CorobLab). Se avanza con xData mientras tanto. |
| Fluid / Tintwise_Lab / Ibicus Spa | pendiente | ídem, cuando se compartan sus formatos |

**La app no cambia al sumar un software:** es un adaptador + una fila de config +
(si el formato es nuevo) validación contra su archivo de referencia.

---

## 9. Consideraciones

- El filtro por homólogos lee el experto completo (~186k filas) una vez por
  tienda → **~10 min las 4**. La UI debe: correr en background, mostrar progreso,
  permitir cancelar, no bloquear.
- Cada corrida **sobrescribe** los `_ready`; si están abiertos en Excel, falla al
  guardar → la UI debe avisar "cerrá estos archivos" antes de correr.
- Mantener `pytest` en verde; agregar tests de `config`, `preview_batch` y
  `api.py`.
- Ciclo cada 15 días: la app debe hacer trivial *"llegó
  `xData_DATACOMPLETA_<nueva fecha>.xlsx` → soltar → revisar → correr"*.

---

## 10. Pendientes / qué se necesita para arrancar

- **Figma:** exportar en **PNG o PDF** el diagrama de flujo entre vistas y cada
  frame. Contra eso se define la estructura de componentes y qué función de
  `api.py` alimenta cada parte.
- **Archivo de referencia de SANTINT** (real, generado por esa máquina) para
  construir su adaptador.
- **Rutas de entrega** por software/tienda: a dónde copia el Depto la GData para
  cada técnico.
- Confirmar la **carpeta de trabajo por defecto** (`Documentos\TINT_SIS\` u otra).
