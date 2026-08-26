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
expert_<SUFIJO>.xlsx
homologos_<SUFIJO>.xlsx
```

Ambos archivos deben compartir el mismo `<SUFIJO>` para que el sistema los
empareje. Ejemplo real usado en las pruebas: `expert_test.xlsx` +
`homologos_test.xlsx` (sufijo `test`). En un ciclo real podría ser, por ejemplo,
`expert_2026_09.xlsx` + `homologos_2026_09.xlsx`.

Esta convención es **distinta** a la de la sección 3.2
(`expert_<GRUPO>_<MAQUINA>.xlsx`, con dos guiones bajos) a propósito: ese archivo
ya viene pre-filtrado por tienda; este es el maestro completo que hay que
filtrar. Si un nombre matchea la convención de 3.2, se rutea por ese flujo, no
por este.

**Cómo tienen que estar armados los archivos:**

- **`expert_<SUFIJO>.xlsx`**: una sola hoja, una fila por fórmula, con la columna
  `ID` (`TINT1`, `TINT2`, ...) en la primera columna. Esta columna de ID se
  genera una sola vez con `scripts/add_id_expert_mp14_corob.py` (numeración por
  posición de fila, no es un código de producto).
- **`homologos_<SUFIJO>.xlsx`**: una hoja por tienda (`MP12`, `MP14`, `Tiendas
  12`, `Tiendas 14`). Dentro de cada hoja no importa la estructura exacta (puede
  tener filas de categoría, encabezados, columnas variables) — el sistema
  **busca en todas las celdas de la hoja** cualquier valor con forma `TINT###` y
  arma la lista de IDs de esa tienda con eso. No hace falta que estén en una
  columna fija.

**Grupos habilitados hoy:** solo **MP12**, en
`ENABLED_GRUPOS` (`src/tint_sis/adapters/homologos_filter.py`). Si el archivo de
Homólogos trae otras hojas (MP14, Tiendas 12, Tiendas 14), el sistema las
reconoce pero **no genera archivo para ellas todavía** — avisa en "Advertencias
de ingesta" que hay que habilitarlas a mano. Esto es intencional (mismo criterio
que las máquinas en la sección 3.2): antes de habilitar una tienda nueva hay que
confirmar que su hoja de Homólogos está completa (sin IDs faltantes) contra el
archivo experto.

**Qué genera** (por cada tienda habilitada):

| Archivo | Ubicación | Qué es |
|---|---|---|
| `<GRUPO>_ready.xlsx` | `data/output/` | Solo las filas del experto cuyo ID está en la hoja de Homólogos de esa tienda. Mismas columnas y formato que el experto. |
| `<GRUPO>_ready.csv` | `data/output/` | El mismo contenido de `<GRUPO>_ready.xlsx`, convertido a CSV con las mismas reglas de formato validadas en la sección 3.2 (ISO-8859-1, coma, CRLF, redondeo "half up" en las columnas de onzas). |

Cada corrida **sobrescribe** `<GRUPO>_ready.xlsx`/`.csv` — no queda un archivo
distinto por ciclo, siempre refleja el último cruce hecho.

**Cómo habilitar una tienda nueva (ej. MP14) cuando su hoja de Homólogos esté
lista:**

1. Confirmá que la hoja de esa tienda en el archivo de Homólogos no tiene IDs
   faltantes respecto al experto (comparación manual o pedile a Claude que haga
   el cruce fila por fila, como se hizo para completar MP12).
2. Agregá el nombre exacto de la hoja (tal como aparece en el Excel, ej.
   `"MP14"` o `"Tiendas 12"` con el espacio) al set `ENABLED_GRUPOS` en
   `src/tint_sis/adapters/homologos_filter.py`.
3. Corré `python -m pytest -q tests` para confirmar que nada se rompió.
4. Corré el sistema (sección siguiente) — debería generar `MP14_ready.xlsx` /
   `.csv` sin la advertencia de "grupo no habilitado".

**Riesgo a tener presente:** el ID del experto está asignado por **posición de
fila**, no por contenido. Si en algún momento se insertan o eliminan filas del
Excel maestro sin volver a correr `add_id_expert_mp14_corob.py`, la
correspondencia ID↔producto se puede desalinear. Por eso el archivo maestro real
trae bloques de filas vacías entre líneas de producto (para dejar espacio a
agregar productos nuevos sin correr esa numeración de nuevo) — visto y
confirmado al analizar `expert_MP14_Corob4.1.2.xlsx` real.

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
