# Guía de uso — TINT_SIS

Sistema que toma los **3 archivos expertos** que entrega el departamento de
tintometría cada ~15 días y, con la **tabla de productos** (qué productos lleva
cada tienda), genera para cada software de máquina dispensadora sus archivos
filtrados por tienda, listos para cargar.

| Experto | Formato | Software → tiendas (formato de salida) |
|---|---|---|
| **Experto 1** (Color Pro) | `Col.N-1/48 onzas` = `AO-26.5` (código y cantidad juntos) | Color_Pro3.1.1 → MP12, MP14, Tiendas 12, Tiendas 14 (**CSV**) · Color_Pro4.8 → Tiendas 14 (Excel) · Ibicus_Spa → Tiendas 14 (Excel) |
| **Experto 2** (Tintwise, `.xlsm`) | `Col`/`Qty` separados, cantidades **ya en cm³** | Tinwise_Lab → Tiendas 14 (Excel `.xlsm`) |
| **Experto 3** (Santint / Corob) | `colorant_N` / `qnt_ml_N` en Oz/48 | Santint → Tiendas 14 · Corob_Tint → MP12, MP14, Tiendas 12, Tiendas 14 (Excel) |

*(El flujo anterior —un solo experto `xData_DATACOMPLETA` con columna `ID_TINT`
cruzado por ID contra `homologos_TINT.xlsx`, más la variante `_cm3`— se
reemplazó por este. El piloto CorobLab está en `plan-tint_sis.md`.)*

**Todo el ciclo se hace desde la vista "Nuevo ciclo", en dos pasos:**

1. **Preparar los expertos** (sección 2): se arrastra arriba el **archivo
   maestro** que envía tintometría (`Todo MP14 <DDMMAAAA>.xlsx`, el experto padre
   completo). TINT_SIS lo compara con el ciclo anterior, suma los productos
   nuevos a la tabla de productos y genera los 3 expertos del ciclo en
   `data/input`.
2. **Ejecutar** (secciones 3 a 5): filtra los 3 expertos por tienda y entrega los
   archivos de cada software.

## 1. Requisitos y arranque

El proyecto ya tiene todo instalado en un entorno virtual (`.venv`). Cada vez que
abras una terminal nueva hay que activarlo antes de correr el sistema.

```powershell
cd "C:\Users\cvidal\OneDrive - Industrias Ceresita S.A\Desktop\TINT_SIS"
.venv\Scripts\Activate.ps1
```

## 2. Preparar el experto de un ciclo nuevo (archivo maestro)

El archivo maestro tiene el **formato de Experto 1** (una hoja con
Clasificacion, Producto, Cartilla, Formato, Tolerancia luz, Primer, Color, R, G,
B, Base, Oz base y `Col.N-1/48 onzas` = `AO-26.5`) y trae **todos** los
productos, incluidos los nuevos. En la app: **Nuevo ciclo** → arrastrar el
maestro (`.xlsx`) al recuadro de arriba. Ese recuadro decide por el nombre: un
`Experto_1/2/3…`, la tabla de productos o los archivos del flujo anterior se
copian tal cual a la carpeta de entrada; **cualquier otro Excel se toma como el
maestro**. Mientras hay un maestro en proceso (analizándose, analizado sin
preparar o preparándose) el botón **Ejecutar** queda bloqueado. También por
consola:

```powershell
python -m tint_sis.cli preparar "C:\...\Todo  MP14 28092026.xlsx" --solo-analizar   # solo el resumen
python -m tint_sis.cli preparar "C:\...\Todo  MP14 28092026.xlsx" --tiendas todas   # prepara
```

(`--tiendas` dice a qué tiendas van los productos nuevos: `todas`, `ninguna` o
una lista `"MP14,MP12"`; es obligatorio si hay productos nuevos.)

**Paso 1 — análisis (≈1 minuto, no escribe nada).** El maestro se guarda en
`data/maestros/` y se compara con:

- el **Experto 1 del ciclo anterior**: productos nuevos, productos que ya no
  vienen y, por producto, fórmulas agregadas y quitadas;
- la **tabla de productos**: los productos del maestro que no están en ella son
  los **productos nuevos** (con su línea, nombre, fórmulas, formatos y
  cartillas);
- el **Experto 2 y 3 anteriores**: qué productos entran y salen de cada uno.

También revisa que se pueda convertir y avisa:

- **Formato de envase**: los **3 expertos** van siempre por **galón** (E2/E3
  desde el 28/09/2026, también E1 desde el 01/10/2026). Una fórmula en
  `Tineta 4 gl` trae las cantidades para 4 galones, así que se divide por 4: en
  E1 la fila queda con Formato `Galon` y `Oz base` y cada colorante divididos
  (`OC-62.8` → `OC-15.7`, en decimal exacto y conservando el código y la grafía
  de la celda); en E2/E3 las cantidades por galón. Los galones de cada formato
  salen de `FORMATOS_GALONES` (`src/tint_sis/maestro.py`) o, si no está ahí, de
  la cantidad que dice el nombre (`Balde 5 gl` = 5, `1/4 galón` = 0,25,
  `1 litro` = 1/3,785), con un aviso para revisarla. Un formato cuyo nombre no
  dice cuánto trae (`Balde`, `Cuarto de galón`) **bloquea** la preparación.
- **Colorantes ilegibles** (una celda que no sea `CODIGO-CANTIDAD`): bloquean.
- **Fórmulas duplicadas**: dos filas con la misma **Clasificación, Producto,
  Cartilla, Color y Base** son la misma fórmula, aunque cambien RGB, notas,
  formato o colorantes (se comparan sin tildes, mayúsculas ni espacios). Se deja
  la **primera** que aparece en el maestro en los 3 expertos y se avisa por
  producto, indicando cuántas traían colorantes distintos. El detalle (fila que
  queda, fila quitada y si los colorantes eran iguales) está en la hoja
  **Duplicadas** del resumen de la preparación.
- **Mismo color en otra cartilla**: en Experto 1 y 2 van todas (llevan la
  columna Cartilla). **Experto 3 no lleva cartilla**, así que ahí la fórmula se
  identifica por Clasificación, Producto, Color y Base y va solo la primera que
  aparece en el maestro; por eso E3 puede traer menos fórmulas que E1/E2. Se
  avisa por producto y en la hoja Duplicadas figuran con "Se quita de: Experto 3"
  y la cartilla que quedó.

**Paso 2 — decidir y preparar (≈2 minutos).** Para cada producto nuevo se
marcan las **tiendas** que lo llevan y se revisa su **nombre en Experto 2 y 3**
(en Experto 3 va como `Línea / Producto`). Al pulsar **Preparar expertos** (y
confirmar):

1. Los productos nuevos se **agregan a `productos_TINT.xlsx`** con esas tiendas,
   y se completan los nombres de Experto 2/3 que falten en la tabla (todos los
   productos del maestro van a los 3 expertos). Las filas tocadas quedan con la
   nota `Preparación <fecha>` en `Revisar`.
2. Se generan en `data/input/`, con la fecha del nombre del maestro:
   - `Experto_1_<fecha>.xlsx`: el maestro (sin las fórmulas duplicadas y con
     las que no venían en galón pasadas a galón).
   - `Experto_3_<fecha>.xlsx` (Santint/Corob): `group_code`/`product_code` de la
     tabla, `color_key1` = Color, `comment` = Tolerancia luz, `base_code` con la
     grafía que ya usa Corob (`BASE N` → `Base N`), `can_code` `Galon`,
     `USoz/48`, 29,574, 48, 0, y `colorant_N`/`qnt_ml_N` en 1/48 oz por galón.
   - `Experto_2_<fecha>.xlsm` (Tintwise): Clasificacion, Producto, Cartilla,
     Color, Base, `Base_Qty` 3785, `ColN` = ` AO` (con espacio) y `QtyN` en cm³
     (1/48 oz × 29,574 / 48), R/G/B, `Note1` = Tolerancia luz, `Note2` = Primer.

   E2 y E3 usan **el del ciclo anterior como plantilla**: se reemplazan solo las
   filas de la hoja `Formulas`; macros, controles, hojas `Colorants`, `Bases`,
   `Cans`, `Settings` e `IntegrityData` quedan igual. Sin un E2/E3 anterior en
   `data/input` ese experto no se genera (se avisa).
3. Los expertos y la tabla anteriores se mueven a
   `data/backups/expertos/<AAAA-MM-DD_HH-MM>/`.
4. Queda un **resumen** (Excel y JSON) en
   `data/output/Preparacion expertos/Resumen_<fecha>.xlsx`: productos nuevos,
   cambios por producto, qué entra a cada experto y advertencias.

Cuando termina el análisis y cuando termina la preparación, la app **avisa**
(ver "Avisos al terminar" en la sección 3).

Si `productos_TINT.xlsx` o un experto que hay que reemplazar está **abierto en
Excel**, la preparación se corta sin cambiar nada: cerralo y volvé a preparar.
Al terminar, la misma vista muestra los expertos nuevos en "Expertos del ciclo"
(son los de fecha más nueva) y **Ejecutar** queda habilitado. "Cerrar" deja
solo una línea con la última preparación y un enlace a su resumen. Un experto
viejo que no se pudo mover (abierto en Excel) queda en la entrada, pero no
afecta al ciclo.

## 3. Correr el sistema

```powershell
python -m tint_sis.cli run
```

- Toma las carpetas y la lista de softwares de la configuración (la misma que
  usa la app, `%LOCALAPPDATA%\TINT_SIS\config.json`; por defecto `data/input` y
  `data/output`). `--input`, `--output` y `--db` permiten pisarlas.
- **Tarda alrededor de 1-2 minutos** con los 3 expertos: cada experto se lee
  **una sola vez** y en esa pasada se arman los archivos de todas sus tiendas.
- Al terminar imprime los archivos generados agrupados por software y las
  advertencias (productos sin asignar, expertos faltantes, etc.), con la lista
  completa de productos sin asignar debajo de cada una.

**Advertencias:** cada ciclo las guarda en la base (tabla `batch_advertencias`:
texto + detalle, p. ej. cada producto sin asignar con sus filas). En la app se
listan en **Resultados** (último ciclo) y en **Historial** ("Ver advertencias
(N)" en cada ciclo). Los ciclos anteriores a la 0.4.0 no las guardaban ("-").

**Colores**: en toda la app las advertencias van en **naranjo** (recuadros,
lista, indicadores, carteles) y lo que impide preparar o ejecutar en **rojo**.

**Avisos al terminar** (app): cuando termina el análisis del maestro, la
preparación de los expertos o un ciclo (o fallan), aparece un cartel abajo a la
derecha en cualquier vista, con un botón a la vista que corresponde; se cierra
con la × o al entrar a esa vista. Si **falta un experto** (en el ciclo: no está,
viene en `.xls`, no se pudo leer o la tabla no tiene su columna; en la
preparación: no hay plantilla para generarlo) llega además un aviso aparte
**"Falta un experto"** en naranjo. Las notificaciones de Windows de advertencia o
error llevan ⚠ y quedan en pantalla hasta cerrarlas. La app instalada además manda una
notificación de Windows ("TINT_SIS", AppUserModelID `Codelpa.TINT_SIS`
registrado en HKCU) y hace parpadear su botón en la barra de tareas si no es la
ventana activa. Se apaga en Configuración → "Notificaciones de Windows"
(`notificaciones` en `config.json`); el cartel sale siempre. La CLI y los tests
no notifican.

## 4. Entradas: los 3 expertos + la tabla de productos

Todo va en `data/input/`:

```
productos_TINT.xlsx                    <- tabla de productos, nombre FIJO
Experto_1_<DD_MM_YYYY>.xlsx            <- Color Pro / Ibicus
Experto_2_<DD_MM_YYYY>.xlsm            <- Tintwise Lab (también acepta .xlsx)
Experto_3_<DD_MM_YYYY>.xlsx            <- Santint / Corob
```

- La fecha en el nombre (`_DD_MM_AAAA` al final, p. ej. `Experto_1_24_09_2026.xlsx`)
  es la que llevan los archivos de salida de ese experto (ver sección 5). Si no
  la trae, se usa la fecha de modificación del archivo y el ciclo lo avisa en el
  log. Si hay varios archivos del mismo experto, se usa **el de fecha más
  nueva** (por la fecha del nombre; si no la trae, por fecha de archivo). Los
  temporales `~$...` de Excel se ignoran.
- **Experto 1 tiene que venir en `.xlsx`**, no en `.xls`: el formato `.xls` corta
  en 65.535 filas y el experto completo tiene ~186 mil. Si el sistema encuentra
  un `Experto_1*.xls` avisa y omite sus softwares.
- **Los expertos se cargan tal como llegan: no necesitan columna de ID.** El
  sistema reconoce cada fila por su producto:
  - Experto 1 y 2: columna `Producto` (en Experto 2 la columna `Clasificacion`
    viene desalineada, por eso no se usa).
  - Experto 3: columnas `group_code` + `product_code`.
- Si falta un experto, el ciclo corre igual y solo se omiten sus softwares.
- Ninguno de los archivos de entrada se modifica: se abren en modo lectura.

### La tabla de productos (`productos_TINT.xlsx`)

Cada tienda lleva **productos completos** (no fórmulas sueltas), así que en vez
de listar IDs por tienda alcanza con una tabla de ~70 filas, una por producto:

| SUBP | Línea | Producto | Experto 1 | Experto 2 | Experto 3 | MP14 | MP12 | Tiendas 14 | Tiendas 12 | Revisar |
|---|---|---|---|---|---|---|---|---|---|---|
| SUBP0004 | Látex | Habitacional Ceresita | Ltx. Habitacional Ceresita | Ltx. Habitacional Ceresita | Látex / Habitacional | x | x | x | x | |

- **Experto 1 / 2 / 3**: cómo se llama ese producto en cada experto (en Experto
  3, `group_code / product_code`). Se comparan sin acentos, mayúsculas ni
  espacios (`Ltx.Extracubriente Sipa` = `Ltx. Extracubriente Sipa`). Si un
  producto tiene más de un nombre en un experto, van en la misma celda separados
  por `;`.
- **Columnas de tienda**: una `x` = esa tienda lleva el producto. Cualquier
  columna que no sea fija ni de experto se toma como tienda.
- Un producto que está en la tabla **sin ninguna tienda marcada** no se entrega
  (y no se avisa: es una decisión explícita).
- Un producto que un experto trae y **no está en la tabla** no se entrega a
  ninguna tienda y **se avisa en cada ciclo** con su nombre y cantidad de filas:
  hay que agregarlo a la tabla (a una fila existente o como fila nueva).
- `Revisar` y `Notas` son solo informativas.

**Se arma una sola vez** a partir de los homólogos por ID del flujo anterior:

```powershell
python -m tint_sis.cli productos-init
```

Toma las tiendas de cada producto de `homologos_TINT.xlsx`, el nombre exacto en
Experto 3 del `xData_DATACOMPLETA_*.xlsx` con `ID_TINT`, y **sugiere** los
nombres de Experto 1 y 2. Todo lo que conviene mirar queda anotado en la columna
`Revisar`, y la hoja `Sin asignar` lista los productos de los expertos que no
calzaron con ninguna fila. **Nunca sobrescribe una tabla existente** (`--force`
la regenera y se pierde la revisión). Después la mantiene la preparación del maestro
(agrega los productos nuevos de cada maestro con sus tiendas) y se edita en la
app, en la vista **Homólogos**:

- Los productos aparecen agrupados por **línea**. Cada uno muestra su nombre en
  Experto 1, 2 y 3, cuántas fórmulas trae cada experto del ciclo con ese nombre
  (o un aviso si el nombre no está en el experto) y las **tiendas** que lo
  llevan (casillas). Un producto sin tiendas lleva la marca "sin tiendas: no se
  entrega".
- **Agregar producto** (o "Agregar producto a esta línea") y **Nueva línea**
  abren un formulario con línea, producto, SUBP, el nombre en cada experto (con
  sugerencias de lo que traen los expertos) y las tiendas.
- **Eliminar** saca el producto de la tabla. Si los expertos lo siguen trayendo,
  el ciclo avisará que no está en la tabla.
- Abajo, **"Productos de los expertos que no están en la tabla"** lista lo que
  traen los expertos y no calza con ninguna fila, con un botón para agregarlo.
- Los cambios se hacen sobre una copia de trabajo y quedan en el archivo al
  pulsar **Guardar cambios**. Antes de escribir se deja una copia de la tabla
  anterior en `data/backups/productos/<fecha>/`. Si la tabla está abierta en
  Excel o se la modificó en Excel mientras se editaba en la app, no se guarda y
  se avisa. Si se intenta salir de la vista con cambios sin guardar, la app
  pregunta antes.

También se puede seguir editando a mano en Excel.

**Tiendas y expertos habilitados:** en la app, Configuración tiene un
interruptor ON/OFF por tienda (MP14, MP12, Tiendas 14, Tiendas 12) y otro por
experto. Un experto apagado no se lee y sus softwares no se generan (sin aviso):
sirve para correr solo lo que haga falta, por ejemplo únicamente el Experto 3
para Santint y Corob. Se guardan en `config.json` (`enabled_grupos`,
`expertos_habilitados`); por defecto todo está encendido. En "Nuevo ciclo" un
experto apagado figura como **Desactivado**, y al pulsar **Ejecutar** la app
muestra un resumen para confirmar: tiendas que se filtran, expertos activos
(archivo → softwares → tiendas y formato), lo que queda afuera y cuántos
archivos se generan.

## 5. Salida: una carpeta por software

```
data/output/Archivos filtrados/
├── Santint/         Tiendas 14_ready_<fecha E3>.xlsx
├── Corob_Tint/      MP12 / MP14 / Tiendas 12 / Tiendas 14 _ready_<fecha E3>.xlsx
├── Tinwise_Lab/     Tiendas 14_ready_<fecha E2>.xlsm
├── Color_Pro3.1.1/  MP12 / MP14 / Tiendas 12 / Tiendas 14 _ready_<fecha E1>.csv
├── Color_Pro4.8/    Tiendas 14_ready_<fecha E1>.xlsx
└── Ibicus_Spa/      Tiendas 14_ready_<fecha E1>.xlsx
```

- **Nombre con fecha**: cada archivo lleva la fecha del experto que lo alimenta,
  en el mismo formato `DD_MM_AAAA`. Con `Experto_1_24_09_2026.xlsx` sale
  `Tiendas 14_ready_24_09_2026.xlsx`. Así en un mismo ciclo cada software puede
  llevar una fecha distinta (la de su experto), y el nombre se conserva al pasar
  a `backups/`, lo que permite buscar por fecha. En "Nuevo ciclo" cada experto
  muestra con qué fecha van a salir sus archivos.

- **Salidas Excel**: son el **libro completo del experto** con la hoja
  `Formulas` filtrada a los productos de esa tienda. El resto viaja intacto: en
  Tinwise_Lab las hojas `Colorants`, `Bases`, `Cans`, `Settings`, `Validate`, las
  macros y los controles (`.xlsm`); en Santint/Corob la hoja `IntegrityData`.
  Mismas columnas, formatos y encabezado que el experto.
- **Salida CSV** (Color_Pro3.1.1): el mismo contenido que el Excel de Experto 1,
  separador coma, ISO-8859-1, CRLF. Las celdas `AO-26.5` pasan tal cual.
- **cm³**: solo Tinwise_Lab, porque Experto 2 ya viene en cm³. Ningún otro
  archivo se convierte.
- **Backup del ciclo anterior**: al empezar un ciclo, todo lo que hay en
  `Archivos filtrados/` se mueve a `data/backups/<fecha del último ciclo>/`
  (por ejemplo `data/backups/2026-09-24_11-29/Santint/Tiendas 14_ready_22_09_2026.xlsx`),
  así esa carpeta queda solo con lo del ciclo nuevo. La fecha es la del ciclo
  que generó esos archivos (si ya existe, se agrega `_2`). "Historial" abre cada
  ciclo en su carpeta de backup. Si el ciclo no va a generar nada (sin expertos
  o sin tabla), no se mueve nada.
- Si algún archivo de `Archivos filtrados/` está abierto en Excel, no se puede
  mover: el ciclo se corta **antes de generar**, todo queda como estaba y la app
  avisa cuál es. Cerralo y volvé a ejecutar.
- Los backups no se borran solos: cuando ya no hagan falta, se pueden eliminar a
  mano desde `data/backups/`.
- La carpeta `data/output/Tiendas filtradas/` es la del flujo anterior
  (`MP12_ready.csv`, `Tiendas 14_cm3.xlsx`, …): no se usa ni se borra sola.

La lista de softwares (nombre = carpeta, experto, tiendas, formato `excel`/`csv`)
está en `SOFTWARES_DEFAULT` (`src/tint_sis/expertos.py`) y se puede pisar en
`config.json` (clave `softwares`).

## 6. Estructura de carpetas

```
TINT_SIS/
├── data/
│   ├── input/                 <- productos_TINT.xlsx + Experto_1/2/3 del ciclo
│   ├── output/
│   │   ├── Archivos filtrados/ <- una subcarpeta por software (ver sección 5)
│   │   └── Preparacion expertos/ <- resumen de cada preparación (sección 2)
│   ├── maestros/              <- archivos maestros cargados en Nuevo ciclo
│   ├── backups/<fecha>/       <- archivos filtrados de cada ciclo anterior
│   ├── backups/expertos/<fecha>/ <- expertos y tabla que reemplazó una preparación
│   └── tint_sis.db            <- historial de corridas (SQLite)
├── src/tint_sis/               <- código del sistema
└── tests/                      <- pruebas automáticas
```

## 7. Correr las pruebas automáticas

Antes de confiar en un cambio (o simplemente para chequear que todo sigue
funcionando), se puede correr la batería de tests:

```powershell
.venv\Scripts\Activate.ps1
python -m pytest -q tests
```

## 8. Agregar un software nuevo

1. Si el software usa uno de los 3 expertos tal cual (filtrado por tienda),
   alcanza con **agregar una fila** a `softwares` en `config.json` (o a
   `SOFTWARES_DEFAULT`): `{"nombre": "...", "experto": "Experto N", "tiendas":
   [...], "formato": "excel" | "csv"}`. Sus archivos salen en
   `Archivos filtrados/<nombre>/`.
2. Si necesita un formato distinto, conseguí primero **un archivo de referencia
   real** generado por ese software — no se adivina el formato sin eso — y armá
   un adaptador en `src/tint_sis/adapters/` que tome el libro filtrado de la
   tienda y lo escriba en ese formato.
3. Si llega un experto nuevo, se agrega a `EXPERTOS` (`src/tint_sis/expertos.py`)
   con las columnas que forman su clave de producto, y una columna con su nombre
   en `productos_TINT.xlsx`.

## 9. Generar el ejecutable e instalador para Windows

Requisitos (una sola vez): el `.venv` del proyecto y **Inno Setup 6**
(`winget install JRSoftware.InnoSetup`). Para usar el logo, dejá
`assets\logo.png` (256×256 o más) o `assets\tint_sis.ico`.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build.ps1            # con tests
powershell -ExecutionPolicy Bypass -File scripts\build.ps1 -SkipTests # sin tests
```

La versión sale de `src\tint_sis\__init__.py` (`__version__`). Resultado:

- `dist\TINT_SIS\TINT_SIS.exe` — la app lista para correr (carpeta completa).
- `dist\installer\TINT_SIS_Setup_<versión>.exe` — instalador para otros PCs
  (instala en Program Files, crea accesos directos, instala WebView2 si falta).

Cerrá cualquier `TINT_SIS.exe` abierto antes de construir (bloquea `dist\`).

Dónde guarda los datos la app instalada:

- `Documentos\TINT_SIS\input` y `output` — archivos de trabajo y resultados.
- `%LOCALAPPDATA%\TINT_SIS\` — `config.json`, `tint_sis.db` y `logs\tint_sis.log`
  (revisar el log si la app no arranca).

Desinstalar no borra ninguna de esas carpetas.
