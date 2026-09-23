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

## 1. Requisitos y arranque

El proyecto ya tiene todo instalado en un entorno virtual (`.venv`). Cada vez que
abras una terminal nueva hay que activarlo antes de correr el sistema.

```powershell
cd "C:\Users\cvidal\OneDrive - Industrias Ceresita S.A\Desktop\TINT_SIS"
.venv\Scripts\Activate.ps1
```

## 2. Correr el sistema

```powershell
python -m tint_sis.cli run
```

- Toma las carpetas y la lista de softwares de la configuración (la misma que
  usa la app, `%LOCALAPPDATA%\TINT_SIS\config.json`; por defecto `data/input` y
  `data/output`). `--input`, `--output` y `--db` permiten pisarlas.
- **Tarda alrededor de 1-2 minutos** con los 3 expertos: cada experto se lee
  **una sola vez** y en esa pasada se arman los archivos de todas sus tiendas.
- Al terminar imprime los archivos generados agrupados por software y las
  advertencias (productos sin asignar, expertos faltantes, etc.).

## 3. Entradas: los 3 expertos + la tabla de productos

Todo va en `data/input/`:

```
productos_TINT.xlsx                    <- tabla de productos, nombre FIJO
Experto_1_<DD_MM_YYYY>.xlsx            <- Color Pro / Ibicus
Experto_2_<DD_MM_YYYY>.xlsm            <- Tintwise Lab (también acepta .xlsx)
Experto_3_<DD_MM_YYYY>.xlsx            <- Santint / Corob
```

- La fecha en el nombre es opcional. Si hay varios archivos del mismo experto,
  se usa **el de fecha más nueva** (por la fecha del nombre; si no la trae, por
  fecha de archivo). Los temporales `~$...` de Excel se ignoran.
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
la regenera y se pierde la revisión). Después se mantiene a mano en Excel: solo
cambia cuando entra un producto nuevo o una tienda cambia lo que lleva.

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

## 4. Salida: una carpeta por software

```
data/output/Archivos filtrados/
├── Santint/         Tiendas 14_ready.xlsx
├── Corob_Tint/      MP12 / MP14 / Tiendas 12 / Tiendas 14 _ready.xlsx
├── Tinwise_Lab/     Tiendas 14_ready.xlsm
├── Color_Pro3.1.1/  MP12 / MP14 / Tiendas 12 / Tiendas 14 _ready.csv
├── Color_Pro4.8/    Tiendas 14_ready.xlsx
└── Ibicus_Spa/      Tiendas 14_ready.xlsx
```

- **Salidas Excel**: son el **libro completo del experto** con la hoja
  `Formulas` filtrada a los productos de esa tienda. El resto viaja intacto: en
  Tinwise_Lab las hojas `Colorants`, `Bases`, `Cans`, `Settings`, `Validate`, las
  macros y los controles (`.xlsm`); en Santint/Corob la hoja `IntegrityData`.
  Mismas columnas, formatos y encabezado que el experto.
- **Salida CSV** (Color_Pro3.1.1): el mismo contenido que el Excel de Experto 1,
  separador coma, ISO-8859-1, CRLF. Las celdas `AO-26.5` pasan tal cual.
- **cm³**: solo Tinwise_Lab, porque Experto 2 ya viene en cm³. Ningún otro
  archivo se convierte.
- Cada corrida **sobrescribe** los archivos de cada carpeta. Si alguno está
  abierto en Excel, falla al guardarlo: cerralo antes de correr.
- La carpeta `data/output/Tiendas filtradas/` es la del flujo anterior
  (`MP12_ready.csv`, `Tiendas 14_cm3.xlsx`, …): no se usa ni se borra sola.

La lista de softwares (nombre = carpeta, experto, tiendas, formato `excel`/`csv`)
está en `SOFTWARES_DEFAULT` (`src/tint_sis/expertos.py`) y se puede pisar en
`config.json` (clave `softwares`).

## 5. Estructura de carpetas

```
TINT_SIS/
├── data/
│   ├── input/                 <- productos_TINT.xlsx + Experto_1/2/3 del ciclo
│   ├── output/
│   │   └── Archivos filtrados/ <- una subcarpeta por software (ver sección 4)
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

## 7. Agregar un software nuevo

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

## 8. Generar el ejecutable e instalador para Windows

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
