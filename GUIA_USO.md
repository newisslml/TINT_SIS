# Guía de uso — TINT_SIS

Sistema que toma el archivo experto que entrega el departamento de tintometría
cada ~15 días (xData) y lo cruza contra el archivo de Homólogos para generar,
por cada tienda, un Excel y un CSV listos para cargar en el software de la
máquina dispensadora de pintura de esa tienda.

*(El piloto CorobLab — flujo FORMULARIO → `.txt` y el passthrough
`expert_<GRUPO>_<MAQUINA>.xlsx` — se usó para validar el patrón y ya no está en
el sistema. Ver `plan-tint_sis.md` para el historial de esa etapa.)*

## 1. Requisitos y arranque

El proyecto ya tiene todo instalado en un entorno virtual (`.venv`). Cada vez que
abras una terminal nueva hay que activarlo antes de correr el sistema.

```powershell
cd "C:\Users\cvidal\OneDrive - Industrias Ceresita S.A\Desktop\TINT_SIS"
.venv\Scripts\Activate.ps1
```

## 2. Correr el sistema

```powershell
python -m tint_sis.cli run --input data/input --output data/output
```

- `--input`: carpeta donde van el experto y el archivo de Homólogos (por
  defecto `data/input`, se puede omitir el flag si no cambiás la carpeta).
- `--output`: carpeta **base** de salida (por defecto `data/output`). Los archivos
  finales se guardan ordenados por software: `data/output/xData/<GRUPO>_ready.*`.
  Cuando se sume otro software (SANTINT, etc.) sus salidas van a
  `data/output/SANTINT/`.
- `--db`: ruta de la base SQLite donde queda el historial de cada corrida (por
  defecto `data/tint_sis.db`). No hace falta tocarlo en el uso normal.

**Tarda entre 12 y 15 minutos** con las 4 tiendas habilitadas (el filtro lee el
experto completo, ~186k filas, una vez por tienda). Mientras corre, la terminal
imprime `Filtrando Data... (<GRUPO>)` para cada tienda — es normal que no haya
más salida hasta que termine cada una; no lo cortes con `Ctrl+C` pensando que se
colgó.

## 3. Filtro por Homólogos (archivo maestro + lista de IDs por tienda)

Hay **un solo Excel maestro** (el experto de xData) con todas las líneas de
producto (Látex, Óleos, Esmaltes, etc.), pero cada tienda/grupo (MP12, MP14,
Tiendas 12, Tiendas 14) solo usa un subconjunto de esos productos. El archivo de
Homólogos dice, por cada tienda, qué IDs le corresponden; el sistema cruza ambos
archivos por ID y genera, para cada tienda, un Excel y un CSV que contienen
**solo** las filas que le corresponden — el resto se descarta.

**Ninguno de los dos archivos de entrada se modifica**: se abren en modo lectura,
se leen como referencia y no se tocan.

**Convención de nombre (obligatoria):**

```
homologos_TINT.xlsx                     <- maestro de homólogos, nombre FIJO
xData_DATACOMPLETA_<DD_MM_YYYY>.xlsx     <- experto, con la fecha del ciclo
```

- El **maestro de homólogos** (`homologos_TINT.xlsx`) **no cambia entre ciclos**:
  solo se vuelve a tocar cuando entra una línea o un producto nuevo. Es la fuente
  de verdad de qué `ID_TINT` le corresponde a cada tienda.
- El **experto** llega cada ~15 días como un archivo nuevo, con la fecha en el
  nombre (`xData_DATACOMPLETA_03_09_2026.xlsx`). Puede traer cambios respecto al
  ciclo anterior (fórmulas de color ajustadas, productos eliminados). Si hay
  varios `xData_DATACOMPLETA_*.xlsx` en la carpeta, el sistema toma **el de fecha
  más nueva** (por la fecha del nombre; si no la trae, por fecha de archivo).

Regla: cada vez que aparece un `xData_DATACOMPLETA_*.xlsx` nuevo en `data/input/`,
el sistema lo cruza contra `homologos_TINT.xlsx` y regenera los
`<grupo>_ready.xlsx` / `.csv`.

*(Convención vieja, todavía soportada: `expert_<SUFIJO>.xlsx` +
`homologos_<SUFIJO>.xlsx` compartiendo sufijo, p. ej. `expert_test.xlsx` +
`homologos_test.xlsx`. Se usa para pruebas; el flujo real es el de arriba.)*

**Cómo tienen que estar armados los archivos:**

- **`xData_DATACOMPLETA_<fecha>.xlsx`**: el sistema lee la hoja llamada
  **`Formulas`** (si no existe, la primera hoja). Una fila por fórmula, con una
  columna de ID llamada `ID` o `ID_TINT` (se ubica por encabezado, no tiene que
  ser la primera). El `ID_TINT` es un código alfanumérico
  (`LátHab001`, `EsmSCereluxe Aquatech001`, `TexSipalinahidr4233`, ...). Las
  demás hojas del workbook (`ID_new`, etc.) se ignoran.
- **`homologos_TINT.xlsx`**: una hoja por tienda (`MP12`, `MP14`, `Tiendas 12`,
  `Tiendas 14`). Cada hoja tiene una columna **`ID_TINT`** (encabezado en su
  fila; el alias `TINT_ID` también vale) con una fila por ID debajo de cada
  homólogo. El sistema ubica esa columna por su encabezado y junta todos los
  valores de texto que hay debajo; las filas de estructura (título, categorías,
  encabezados de sección, filas de homólogo) dejan esa celda vacía, así que no se
  cuelan. **No debe tener una hoja `Formulas`** (esa se usó solo para insertar los
  IDs en cada homólogo y se borra después).

**Grupos habilitados hoy:** **MP14, MP12, Tiendas 14 y Tiendas 12**, en
`ENABLED_GRUPOS` (`src/tint_sis/adapters/homologos_filter.py`). Si el archivo de
Homólogos trae otra hoja que no esté en ese set, el sistema la reconoce pero
**no genera archivo para ella** — avisa en "Advertencias de ingesta" (ver
sección 4) que hay que habilitarla a mano. Antes de habilitar una tienda nueva
hay que confirmar que su hoja de Homólogos está completa (sin IDs faltantes)
contra el experto.

**Qué genera** (por cada tienda habilitada — 8 archivos con las 4 tiendas):

| Archivo | Ubicación | Qué es |
|---|---|---|
| `<GRUPO>_ready.xlsx` | `data/output/xData/` | Solo las filas de la hoja `Formulas` del experto cuyo `ID_TINT` está en la hoja de esa tienda. Mismas columnas y formato que el experto. |
| `<GRUPO>_ready.csv` | `data/output/xData/` | El mismo contenido de `<GRUPO>_ready.xlsx`, convertido a CSV (separador coma, ISO-8859-1, CRLF, redondeo "half up" en columnas de cantidad). |

Los finales se guardan **por software** en `data/output/<software>/` (hoy solo
`data/output/xData/`) para dejar ordenada la salida cuando se sumen más softwares.

Cada corrida **sobrescribe** `<GRUPO>_ready.xlsx`/`.csv` — siempre reflejan el
último cruce hecho. Si alguno está abierto en Excel al correr el sistema, falla
al guardarlo — cerralo antes de correr.

**Cómo habilitar una tienda nueva cuando su hoja de Homólogos esté lista:**

1. Confirmá que la hoja de esa tienda en `homologos_TINT.xlsx` no tiene IDs
   faltantes respecto al experto (comparación manual o pedile a Claude que haga
   el cruce, como se hizo para completar las 4 hojas actuales).
2. Agregá el nombre exacto de la hoja (tal como aparece en el Excel, ej.
   `"Tiendas 12"` con el espacio) al set `ENABLED_GRUPOS` en
   `src/tint_sis/adapters/homologos_filter.py`.
3. Corré `python -m pytest -q tests` para confirmar que nada se rompió.
4. Corré el sistema — debería generar `<GRUPO>_ready.xlsx` / `.csv` sin la
   advertencia de "grupo no habilitado".

## 4. Leer el resultado de una corrida

Al terminar, el CLI imprime un resumen:

```
Archivos generados (CSV, formato completo): ...
Archivos generados (Excel, formato completo): ...
```

Las advertencias de ingesta (hojas de tienda no habilitadas, hoja sin IDs, etc.)
se siguen juntando en `summary.ingestion_warnings` pero no se imprimen por
defecto — están comentadas en `src/tint_sis/cli.py` (descomentar ahí si hace
falta volver a verlas en la terminal).

## 5. Estructura de carpetas

```
TINT_SIS/
├── data/
│   ├── input/                 <- poné acá homologos_TINT.xlsx y el xData_DATACOMPLETA_*.xlsx del ciclo
│   ├── output/
│   │   └── xData/             <- salida final del software xData
│   │       ├── <GRUPO>_ready.csv  <- salida CSV por tienda
│   │       └── <GRUPO>_ready.xlsx <- salida Excel filtrada por tienda
│   └── tint_sis.db            <- historial de corridas (SQLite)
├── src/tint_sis/               <- código del sistema
└── tests/                      <- pruebas automáticas
```

## 6. Correr las pruebas automáticas

Antes de confiar en un cambio (o simplemente para chequear que todo sigue
funcionando), se puede correr la batería de tests:

```powershell
.venv\Scripts\Activate.ps1
python -m pytest -q tests
```

## 7. Agregar soporte para un software de máquina nuevo (ej. SANTINT)

El filtro por homólogos ya cubre "qué fila le toca a qué tienda"; lo que cambia
de un software a otro es el **formato del archivo de salida**. Hoy `_ready.csv`
sirve para xData. Para un software nuevo:

1. Conseguí **un archivo de referencia real** generado por ese software para
   validar contra él — no se adivina el formato sin eso (mismo criterio con el
   que se validó CorobLab en su momento).
2. Armá un adaptador nuevo en `src/tint_sis/adapters/` (ej. `santint.py`) que
   tome el mismo `<GRUPO>_ready.xlsx` (o las filas filtradas) y escriba el
   formato exacto que pide ese software.
3. Registralo en `run_homologos_filter` (`adapters/homologos_filter.py`) o en el
   pipeline, según si aplica a todas las tiendas o solo a alguna.
