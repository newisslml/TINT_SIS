# Guía de uso — TINT_SIS

Sistema que toma los archivos expertos que entrega el departamento de tintometría
cada 15 días y genera los archivos listos para cargar en cada software de máquina
dispensadora de pintura (CorobLab, y a futuro Fluid, Santint, etc.).

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

- `--input`: carpeta donde van los archivos expertos a procesar (por defecto
  `data/input`, se puede omitir el flag si no cambiás la carpeta).
- `--output`: carpeta donde se generan los resultados (por defecto `data/output`).
- `--db`: ruta de la base SQLite donde queda el historial de cada corrida (por
  defecto `data/tint_sis.db`). No hace falta tocarlo en el uso normal.

El sistema procesa **todos** los archivos `.xlsx` que encuentre en `--input` en
una sola corrida, cada uno según el tipo que sea (ver sección 3).

## 3. Los dos tipos de archivo experto que el sistema reconoce

El sistema mira el **nombre del archivo** para decidir cómo procesarlo. Hay dos
flujos completamente distintos.

### 3.1. Archivo "FORMULARIO" clásico (ej. `expert.xlsx`)

Es el Excel tal como lo arma tintometría internamente: una hoja `FORMULARIO `,
con filas de colorantes en bloques (COL_1..COL_4) y sin una columna propia de
Clasificación (viene definida a mano, no en el Excel).

**Cómo agregarlo:**

1. Poné el `.xlsx` en `data/input/` (ej. `latex.xlsx`).
2. Al lado, con el **mismo nombre** pero extensión `.json`, creá el archivo de
   metadata (ej. `latex.json`) con los 4 datos que define tintometría para esa
   línea de producto:

   ```json
   {
     "clasificacion": "1.-Latex",
     "producto": "Ltx.Extracubriente Sipa/Ltx.Tecnoconstrucción Sipa/...",
     "cartilla": "Cartilla Ltx. Extracubriente",
     "formato": "Galon (3.785 Lts.)"
   }
   ```

   Si falta el `.json`, el sistema **omite el archivo** con una advertencia en
   vez de romper toda la corrida — revisá la sección "Advertencias de ingesta"
   que imprime el CLI al terminar.

**Qué genera** (por cada línea de producto, tomando el nombre del `.xlsx` como
identificador de línea):

| Archivo | Ubicación | Qué es |
|---|---|---|
| `filtrado_<linea>.xlsx` | `data/output/ajuste/` | Copia limpia/filtrada, columnas necesarias solamente. Material de respaldo. |
| `<linea>.txt` | `data/output/` | Archivo final para CorobLab: 20 columnas, tabulado, ISO-8859-1, CRLF. Este es el que se carga en la máquina. |

Antes de generar el `.txt`, cada fila se valida (rangos de R/G/B, campos
obligatorios, etc.). Las filas con error **no** entran al archivo final — quedan
listadas en "Hallazgos de validación" al final de la corrida para que las
revises con tintometría.

### 3.2. Archivo "passthrough" ya en formato final (ej. `expert_MP14_Corob4.1.2.xlsx`)

Son archivos que tintometría/otro sistema ya entrega como tabla plana lista
(Clasificación, Producto, Cartilla, Formato, Color, R, G, B, Base, colorantes,
etc. como columnas propias, una fila por fórmula). Acá **no se filtra ni se
valida nada** — el sistema solo cambia el contenedor al formato que pide la
máquina.

**Convención de nombre (obligatoria, así el sistema sabe qué hacer con el archivo):**

```
expert<sufijo opcional>_<GRUPO_DE_TIENDAS>_<MAQUINA>.xlsx
```

- `expert_MP14_Corob4.1.2.xlsx` ✅
- `expert1_MP14_Corob4.1.2.xlsx` ✅ (sufijos tipo `1`, `V2`, etc. después de "expert" están permitidos, mientras no lleven guión bajo pegado)
- `expertMP14Corob4.1.2.xlsx` ❌ (le faltan los guiones bajos separadores)

No necesita ningún `.json` al lado — el grupo y la máquina salen del nombre, y
Clasificación/Producto/Cartilla/Formato salen directo de las columnas del Excel.

**Qué genera** (mismo nombre base que el archivo de entrada):

| Archivo | Ubicación | Qué es |
|---|---|---|
| `<nombre>.csv` | `data/output/` | La tabla completa convertida a CSV en el formato exacto que espera la máquina (separador coma, ISO-8859-1, CRLF). |
| `<nombre>.xlsx` | `data/output/` | Copia exacta del Excel de entrada. Redundante a propósito: se piden los 2 formatos como entrega para este grupo. |

**Máquinas soportadas hoy:** solo `Corob4.1.2` (case-insensitive) tiene un
formato de salida registrado. Si el nombre de archivo trae una máquina que
todavía no está registrada (por ejemplo, cuando lleguen los archivos de MP12,
Tiendas12 o Tiendas14 con otra máquina), el sistema **no adivina el formato**:
omite el archivo y avisa en "Advertencias de ingesta" que hay que registrar esa
máquina. Esto es intencional — cada formato nuevo se valida contra un archivo de
referencia real antes de programarlo, para no generar un archivo mal formado
que la máquina rechace.

### 3.3. Filtro por Homólogos (archivo maestro + lista de IDs por tienda)

Este flujo resuelve un caso distinto a los dos anteriores: hay **un solo Excel
maestro** con todas las líneas de producto (Látex, Óleos, Esmaltes, etc.), pero
cada tienda/grupo (MP12, MP14, Tiendas 12, Tiendas 14) solo usa un subconjunto de
esos productos. El archivo de Homólogos dice, por cada tienda, qué IDs le
corresponden; este flujo cruza ambos archivos por ID y genera, para la tienda, un
Excel y un CSV que contienen **solo** las filas que le corresponden — el resto se
descarta.

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

Esta convención es **distinta** a la de la sección 3.2
(`expert_<GRUPO>_<MAQUINA>.xlsx`): ese archivo ya viene pre-filtrado por tienda;
este es el maestro completo que hay que filtrar.

*(Convención vieja, todavía soportada: `expert_<SUFIJO>.xlsx` +
`homologos_<SUFIJO>.xlsx` compartiendo sufijo, p. ej. `expert_test.xlsx` +
`homologos_test.xlsx`. Se usa para pruebas; el flujo real es el de arriba.)*

**Cómo tienen que estar armados los archivos:**

- **`xData_DATACOMPLETA_<fecha>.xlsx`**: el sistema lee la hoja llamada
  **`Formulas`** (si no existe, la primera hoja). Una fila por fórmula, con una
  columna de ID llamada `ID` o `ID_TINT` (se ubica por encabezado, no tiene que
  ser la primera). El `ID_TINT` es un código alfanumérico
  (`LátHab001`, `EsmSCereluxe Aquatech001`, `TexSipalinahidr4233`, ...), no el
  viejo formato `TINT###`. Las demás hojas del workbook (`ID_new`, etc.) se
  ignoran.
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
**no genera archivo para ella** — avisa en "Advertencias de ingesta" que hay que
habilitarla a mano. Antes de habilitar una tienda nueva hay que confirmar que su
hoja de Homólogos está completa (sin IDs faltantes) contra el experto.

**Qué genera** (por cada tienda habilitada):

| Archivo | Ubicación | Qué es |
|---|---|---|
| `<GRUPO>_ready.xlsx` | `data/output/` | Solo las filas de la hoja `Formulas` del experto cuyo `ID_TINT` está en la hoja de esa tienda. Mismas columnas y formato que el experto. |
| `<GRUPO>_ready.csv` | `data/output/` | El mismo contenido de `<GRUPO>_ready.xlsx`, convertido a CSV con las mismas reglas de formato de la sección 3.2 (ISO-8859-1, coma, CRLF). |

Cada corrida **sobrescribe** `<GRUPO>_ready.xlsx`/`.csv` — siempre reflejan el
último cruce hecho.

**Cómo habilitar una tienda nueva cuando su hoja de Homólogos esté lista:**

1. Confirmá que la hoja de esa tienda en `homologos_TINT.xlsx` no tiene IDs
   faltantes respecto al experto (comparación manual o pedile a Claude que haga
   el cruce, como se hizo para completar las 4 hojas).
2. Agregá el nombre exacto de la hoja (tal como aparece en el Excel, ej.
   `"Tiendas 12"` con el espacio) al set `ENABLED_GRUPOS` en
   `src/tint_sis/adapters/homologos_filter.py`.
3. Corré `python -m pytest -q tests` para confirmar que nada se rompió.
4. Corré el sistema — debería generar `<GRUPO>_ready.xlsx` / `.csv` sin la
   advertencia de "grupo no habilitado".

## 4. Leer el resultado de una corrida

Al terminar, el CLI imprime un resumen:

```
Formulas leidas: ...
Formulas generadas: ...
Formulas con error (excluidas): ...
Archivos de ajuste (respaldo .xlsx): ...
Archivos generados (CorobLab .txt): ...
Archivos generados (CSV, formato completo): ...
Archivos generados (Excel, formato completo): ...

Advertencias de ingesta:
  - ...

Hallazgos de validacion:
  [error] archivo.xlsx fila 123: ...
```

- **Advertencias de ingesta**: archivos que se saltearon completos (falta
  metadata, máquina no registrada, etc.).
- **Hallazgos de validación**: filas puntuales con problemas dentro de un
  archivo que sí se procesó (solo aplica al flujo FORMULARIO — el passthrough no
  valida nada).

## 5. Estructura de carpetas

```
TINT_SIS/
├── data/
│   ├── input/            <- poné acá los archivos expertos de cada corrida
│   ├── output/
│   │   ├── ajuste/        <- respaldo filtrado (solo flujo FORMULARIO)
│   │   ├── <linea>.txt        <- salida CorobLab (flujo FORMULARIO)
│   │   ├── <nombre>.csv       <- salida CSV (flujo passthrough)
│   │   ├── <nombre>.xlsx      <- copia Excel (flujo passthrough)
│   │   ├── <GRUPO>_ready.csv  <- salida CSV (flujo filtro por homologos)
│   │   └── <GRUPO>_ready.xlsx <- salida Excel filtrada (flujo filtro por homologos)
│   └── tint_sis.db       <- historial de corridas (SQLite)
├── src/tint_sis/          <- código del sistema
└── tests/                 <- pruebas automáticas
```

## 6. Correr las pruebas automáticas

Antes de confiar en un cambio (o simplemente para chequear que todo sigue
funcionando), se puede correr la batería de tests:

```powershell
.venv\Scripts\Activate.ps1
python -m pytest -q tests
```

Todas las reglas de formato (columnas, redondeo, fechas, encoding) están
validadas contra archivos reales entregados por tintometría/Corob — si algo
falla acá, es una señal real de que un formato cambió.

## 7. Agregar soporte para una máquina/grupo nuevo

Cuando llegue un archivo experto de un grupo nuevo (MP12, Tiendas12, Tiendas14):

1. Definí qué formato de salida necesita esa máquina (CSV, TXT, delimitador,
   encoding, etc.) y conseguí **un archivo de referencia real** generado por esa
   máquina para validar contra él — así se trabajó con CorobLab y con
   Corob4.1.2, sin adivinar el formato.
2. Si el formato de salida es un CSV plano igual al de Corob4.1.2, alcanza con
   agregar una línea en `MACHINE_OUTPUT_FORMATS` (`src/tint_sis/routing.py`)
   mapeando el nombre de la máquina a `"csv_passthrough"`.
3. Si el formato es distinto (otro delimitador, otras columnas, reglas propias),
   se arma un adaptador nuevo en `src/tint_sis/adapters/` y se registra en el
   pipeline, igual que se hizo con `passthrough_csv.py`.
