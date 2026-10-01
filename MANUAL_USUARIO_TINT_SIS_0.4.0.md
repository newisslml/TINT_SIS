# Manual de usuario — TINT_SIS 0.4.0

**Departamento de Desarrollo e Investigación**
Versión del sistema: 0.4.0 · Fecha del manual: 01-10-2026

---

## Contenido

1. [¿Qué es TINT_SIS?](#1-qué-es-tint_sis)
2. [Resumen rápido: un ciclo en 7 pasos](#2-resumen-rápido-un-ciclo-en-7-pasos)
3. [Instalación y primer arranque](#3-instalación-y-primer-arranque)
4. [Conceptos básicos](#4-conceptos-básicos)
5. [La pantalla principal](#5-la-pantalla-principal)
6. [Paso a paso: un ciclo completo](#6-paso-a-paso-un-ciclo-completo)
7. [Avisos al terminar](#7-avisos-al-terminar)
8. [Advertencias del ciclo](#8-advertencias-del-ciclo)
9. [Otras vistas](#9-otras-vistas)
10. [Todo en galón: formatos de envase](#10-todo-en-galón-formatos-de-envase)
11. [Mensajes frecuentes y cómo resolverlos](#11-mensajes-frecuentes-y-cómo-resolverlos)
12. [Limitaciones conocidas de la versión 0.4.0](#12-limitaciones-conocidas-de-la-versión-040)
13. [Novedades desde la versión 0.2.0](#13-novedades-desde-la-versión-020)

---

## 1. ¿Qué es TINT_SIS?

Cada ~15 días tintometría envía el **archivo maestro** con todas las fórmulas
de color (`Todo MP14 <DDMMAAAA>.xlsx`). Cada software de máquina tintométrica
necesita esas fórmulas en su propio formato y **solo con los productos que
vende cada tienda**.

TINT_SIS hace todo el recorrido desde la vista **Nuevo ciclo**:

1. **Prepara los expertos.** Lee el maestro y lo compara con el ciclo anterior.
   Suma los productos nuevos a la tabla de productos y genera los **3 archivos
   expertos** del ciclo (Experto 1, 2 y 3), todos por galón.
2. **Filtra por tienda.** Con la **tabla de productos** decide qué productos
   lleva cada tienda.
3. **Entrega.** Deja para cada software un archivo por tienda, **listo para
   importar**.

```
 Archivo maestro ─► Preparar ─► Experto 1 ─┐                         ┌─ Color_Pro3.1.1 / Color_Pro4.8 / Ibicus_Spa
 (tintometría)      expertos    Experto 2 ─┼─► Ejecutar ─► filtro ───┼─ Tinwise_Lab
                                Experto 3 ─┘   (tabla de productos)  └─ Santint / Corob_Tint
```

El archivo maestro que cargás **no se modifica**: TINT_SIS guarda una copia y
trabaja sobre ella.

---

## 2. Resumen rápido: un ciclo en 7 pasos

| # | Qué hacer | Dónde | Tiempo |
|---|---|---|---|
| 1 | Arrastrar el **archivo maestro** al recuadro punteado | **Nuevo ciclo** | ≈1 min de análisis |
| 2 | Revisar el análisis y, si hay **productos nuevos**, marcar sus tiendas | **Nuevo ciclo** | — |
| 3 | Pulsar **Preparar expertos** y confirmar | **Nuevo ciclo** | ≈3 min |
| 4 | Revisar los expertos del ciclo, pulsar **Ejecutar** y confirmar con **Ejecutar ciclo** | **Nuevo ciclo** | — |
| 5 | Esperar a que termine | **Ejecución** | ≈1 a 2 min |
| 6 | Revisar los archivos generados y las **advertencias** | **Resultados** | — |
| 7 | Importar cada archivo en su software | Carpeta `Archivos filtrados\<Software>\` | — |

> Mientras esperás podés usar otras vistas, o incluso otras aplicaciones.
> Cuando termina el análisis, la preparación o el ciclo, TINT_SIS **avisa**:
> aparece un cartel dentro de la app y una notificación de Windows
> ([sección 7](#7-avisos-al-terminar)).

> Antes de preparar o de ejecutar, **cerrá en Excel** la tabla de productos,
> los expertos y los archivos de salida. Si alguno está abierto, el sistema se
> detiene sin cambiar nada y te avisa cuál es.

**Colores de los avisos en toda la app:**

| Color | Significa |
|---|---|
| 🟠 **Naranjo** | **Advertencia**: se puede seguir, pero algo queda afuera o hay que revisarlo (por ejemplo, falta un experto o un producto no está en la tabla) |
| 🔴 **Rojo** | **Impide seguir** (no se puede preparar o ejecutar), o algo falló |
| 🔵 **Azul** | Información |
| 🟢 **Verde** | Todo bien |

---

## 3. Instalación y primer arranque

### 3.1 Instalar o actualizar

1. Ejecutá `TINT_SIS_Setup_0.4.0.exe` (pide permisos de administrador).
2. Seguí el asistente. Podés marcar **Crear un acceso directo en el escritorio**.
3. Si el equipo no tiene *Microsoft Edge WebView2*, el instalador lo agrega solo.
4. Al terminar, TINT_SIS se abre en su propia ventana, titulada **TINT_SIS 0.4.0**.

**Actualizar desde 0.2.x o 0.3.x:** ejecutá el instalador nuevo sobre el
anterior. Tus carpetas de trabajo, la tabla de productos, la configuración y el
historial se mantienen.

**Desinstalar:** desde *Configuración de Windows → Aplicaciones* o con el acceso
*Desinstalar TINT_SIS*. Desinstalar **no borra** tus archivos ni el historial.

### 3.2 Dónde guarda las cosas

Todo queda dentro de `Documentos\TINT_SIS\`:

| Qué | Carpeta |
|---|---|
| Entrada del ciclo: los 3 expertos y la tabla de productos | `input\` |
| Archivos maestros que cargaste | `maestros\` |
| Archivos listos para cada software | `output\Archivos filtrados\<Software>\` |
| Resumen de cada preparación (Excel) | `output\Preparacion expertos\` |
| Archivos de ciclos anteriores | `backups\<AAAA-MM-DD_HH-MM>\` |
| Expertos y tabla que reemplazó una preparación | `backups\expertos\<fecha>\` |
| Copias de la tabla antes de cada guardado en Homólogos | `backups\productos\<fecha>\` |

La configuración, el historial de ciclos y el registro de errores están en
`%LOCALAPPDATA%\TINT_SIS\` (`config.json`, `tint_sis.db`, `logs\tint_sis.log`).

Las carpetas se crean solas la primera vez. Las de entrada y salida se pueden
cambiar en **Configuración** ([sección 9.4](#94-configuración)).

### 3.3 Antes del primer ciclo

La carpeta de entrada tiene que tener la **tabla de productos**
(`productos_TINT.xlsx`) y los **expertos del ciclo anterior**. La preparación
usa el Experto 2 y el Experto 3 anteriores como *plantilla*, porque de ellos
toma las macros y las hojas auxiliares. Si es un PC nuevo, pedí esos archivos
a Desarrollo e Investigación y dejalos en `Documentos\TINT_SIS\input\`. Al
actualizar sobre una instalación anterior ya están ahí.

---

## 4. Conceptos básicos

### 4.1 El archivo maestro

Es el archivo que envía tintometría con **todos** los productos y fórmulas, en
el formato de Experto 1: una hoja con Clasificación, Producto, Cartilla,
Formato, Tolerancia luz, Primer, Color, R, G, B, Base, Oz base y las columnas
`Col.N-1/48 onzas` (código y cantidad juntos, por ejemplo `AO-26.5`).

- Tiene que venir en **`.xlsx`**. El formato `.xls` corta en 65.535 filas y el
  maestro tiene más de 200 mil.
- La **fecha del ciclo** se toma del nombre (`Todo MP14 28092026.xlsx` →
  28/09/2026). Si el nombre no la trae, se usa la fecha de hoy y se avisa.
- **No le pongas un nombre que empiece con `Experto_`**. Un nombre así se toma
  como un experto ya preparado y no como el maestro.

### 4.2 Los 3 archivos expertos

TINT_SIS los **genera** a partir del maestro (sección 6) y los deja en la
carpeta de entrada:

| Experto | Para | Cómo vienen las cantidades | Archivo |
|---|---|---|---|
| **Experto 1** | Color Pro, Ibicus | Código y cantidad juntos: `AO-26.5` (1/48 oz por galón) | `Experto_1_<DD_MM_AAAA>.xlsx` |
| **Experto 2** | Tintwise Lab | Colorante y cantidad separados, **en cm³** por galón. Libro con macros | `Experto_2_<DD_MM_AAAA>.xlsm` |
| **Experto 3** | Santint, Corob | `colorant_N` / `qnt_ml_N` en 1/48 oz por galón | `Experto_3_<DD_MM_AAAA>.xlsx` |

- Si en la carpeta hay varios archivos del mismo experto, se usa **el de fecha
  más nueva** y los demás se ignoran.
- Experto 3 **no lleva cartilla**: si un color aparece en varias cartillas, va
  una sola vez (la primera). Por eso Experto 3 puede tener algunas fórmulas
  menos que Experto 1 y 2.
- También se puede cargar un experto suelto (por ejemplo, uno que corrigió
  tintometría) arrastrándolo a Nuevo ciclo con su nombre `Experto_N_…`: se
  copia tal cual a la carpeta de entrada.

### 4.3 La tabla de productos

`productos_TINT.xlsx` indica **qué productos lleva cada tienda**, con una fila
por producto y el nombre que tiene ese producto en cada experto. Se edita en
la vista **Homólogos** ([sección 9.3](#93-homólogos-tabla-de-productos)). La
preparación agrega sola los productos nuevos del maestro.

| Situación | Qué hace el sistema |
|---|---|
| El producto está en la tabla con tiendas marcadas | Se entrega a esas tiendas |
| El producto está en la tabla **sin ninguna tienda marcada** | No se entrega y **no avisa** (se da por decidido) |
| Un experto trae un producto que **no está en la tabla** | No se entrega a ninguna tienda y **avisa en cada ciclo** |

### 4.4 Tiendas

Hay 4 grupos de tiendas: **MP14**, **MP12**, **Tiendas 14** y **Tiendas 12**.

### 4.5 Softwares y archivos que se generan

| Software (carpeta) | Usa | Tiendas | Formato |
|---|---|---|---|
| `Santint` | Experto 3 | Tiendas 14 | Excel (`.xlsx`) |
| `Corob_Tint` | Experto 3 | Tiendas 14, Tiendas 12, MP12, MP14 | Excel (`.xlsx`) |
| `Tinwise_Lab` | Experto 2 | Tiendas 14 | Excel con macros (`.xlsm`) |
| `Color_Pro3.1.1` | Experto 1 | Tiendas 14, Tiendas 12, MP12, MP14 | CSV |
| `Color_Pro4.8` | Experto 1 | Tiendas 14 | Excel (`.xlsx`) |
| `Ibicus_Spa` | Experto 1 | Tiendas 14 | Excel (`.xlsx`) |

En total, **12 archivos** por ciclo cuando todo está habilitado. Cada uno lleva
en el nombre la **fecha del experto** que lo alimenta:

```
Archivos filtrados\
├── Santint\          Tiendas 14_ready_28_09_2026.xlsx
├── Corob_Tint\       MP12_ready_… · MP14_ready_… · Tiendas 12_ready_… · Tiendas 14_ready_…  (.xlsx)
├── Tinwise_Lab\      Tiendas 14_ready_28_09_2026.xlsm
├── Color_Pro3.1.1\   MP12_ready_… · MP14_ready_… · Tiendas 12_ready_… · Tiendas 14_ready_…  (.csv)
├── Color_Pro4.8\     Tiendas 14_ready_28_09_2026.xlsx
└── Ibicus_Spa\       Tiendas 14_ready_28_09_2026.xlsx
```

**Cómo son los archivos generados:**

- **Excel:** son el mismo libro del experto, con la hoja de fórmulas reducida a
  los productos de esa tienda. Todo lo demás viaja intacto: las hojas
  `Colorants`, `Bases`, `Cans`, `Settings` y las macros en Tinwise_Lab, y la
  hoja `IntegrityData` en Santint y Corob.
- **CSV (Color_Pro3.1.1):** el mismo contenido del Experto 1, separado por
  comas. Las celdas del tipo `AO-26.5` pasan tal cual.

---

## 5. La pantalla principal

```
┌──────────────┬──────────────────────────────────────────────────────────┐
│ TINT_SIS     │ Carpeta: …   Último ciclo: …   Software: …              │ ← barra de estado
│              ├──────────────────────────────────────────────────────────┤
│ Inicio       │                                                          │
│ Nuevo ciclo  │                                                          │
│ Resultados   │                 contenido de la vista                    │
│ Historial    │                                                          │
│ Homólogos    │                                        ┌───────────────┐ │
│ Configuración│                                        │ aviso al      │ │ ← avisos (sección 7)
│              │                                        │ terminar      │ │
└──────────────┴────────────────────────────────────────┴───────────────┴─┘
```

- **Menú lateral:** cambia de vista.
- **Barra de estado** (arriba): carpeta de trabajo, fecha del último ciclo y
  softwares activos, según las tiendas y expertos encendidos. Si muestra
  *"sin conexión con el servicio local"*, cerrá y volvé a abrir la app.
- **Avisos** (abajo a la derecha): aparecen cuando termina un trabajo largo.

---

## 6. Paso a paso: un ciclo completo

### Paso 1 — Cargar el archivo maestro

Entrá a **Nuevo ciclo** y **arrastrá el maestro** al recuadro punteado (o hacé
clic en él para buscarlo).

- El maestro se guarda en `Documentos\TINT_SIS\maestros\` y empieza el
  **análisis**, que tarda alrededor de un minuto y **no cambia nada**. Una
  barra muestra el avance.
- Mientras tanto podés ir a otra vista. Al terminar aparece el aviso
  **"Análisis del maestro listo"**.

> El recuadro decide por el nombre. Un `Experto_1/2/3…`, la tabla de productos
> o un archivo del flujo anterior se **copian tal cual** a la carpeta de
> entrada. **Cualquier otro Excel se toma como el maestro.**

### Paso 2 — Revisar el análisis

La vista muestra, de arriba hacia abajo:

**a) Resumen.** El maestro, la fecha del ciclo, el Experto 1 anterior con el
que se comparó y los números principales:

- fórmulas, incluidas las duplicadas que se quitan;
- productos y productos nuevos;
- fórmulas agregadas y quitadas respecto del ciclo anterior.

**b) Recuadros rojos:** algo **impide preparar**. Por ejemplo, un formato
de envase sin equivalencia a galón o una celda de colorante ilegible. Ver
[sección 11](#11-mensajes-frecuentes-y-cómo-resolverlos). El botón **Preparar
expertos** queda desactivado.

**c) Productos nuevos:** productos del maestro que no están en la tabla de
productos. Para cada uno:

- Marcá las **tiendas** que lo llevan. Por defecto vienen todas marcadas.
  Si no marcás ninguna, el producto se agrega a la tabla pero no se entrega.
- Revisá su **nombre en Experto 2 y 3**. En Experto 3 va como `Línea / Producto`.

**d) Cambios respecto del ciclo anterior:** por producto, las fórmulas de antes
y de ahora, cuántas se agregaron y cuántas se quitaron. Los productos que ya no
vienen se marcan **"ya no viene"**.

**e) Expertos que se generan:** archivo, cantidad de fórmulas y productos que
entran o salen de cada experto. Un experto que no se puede generar (porque
falta su plantilla, ver 3.3) figura en naranjo como **"no se genera: falta su
plantilla"**, y además llega el aviso **"Falta un experto"**.

**f) Recuadros naranjos (advertencias):** no impiden preparar, pero conviene
leerlos. Por ejemplo:

- **Fórmulas duplicadas.** Dos filas con la misma *Clasificación, Producto,
  Cartilla, Color y Base* son la misma fórmula, aunque cambien RGB, notas o
  colorantes. Se deja **la primera** y se avisa por producto cuántas traían
  colorantes distintos.
- **Mismo color en otra cartilla.** No va a Experto 3, que no lleva cartilla.
- **Formato que no es galón.** Se pasa a galón ([sección 10](#10-todo-en-galón-formatos-de-envase)).

Si el maestro no era el correcto, pulsá **Descartar este maestro**.

### Paso 3 — Preparar los expertos

Pulsá **Preparar expertos**. Se muestra un resumen con los archivos que se
generan y las tiendas de cada producto nuevo. Confirmá con **Preparar**.

En alrededor de **3 minutos**:

1. Los productos nuevos **se agregan a la tabla de productos** con las tiendas
   elegidas. También se completan los nombres de Experto 2 y 3 que falten. Las
   filas tocadas quedan con la nota *"Preparación <fecha>"* en la columna
   `Revisar`.
2. Se generan `Experto_1/2/3_<fecha>` en la carpeta de entrada, **todo por
   galón** y sin fórmulas duplicadas.
3. Los expertos y la tabla anteriores se mueven a `backups\expertos\<fecha>\`.
4. Queda un **resumen en Excel** en `output\Preparacion expertos\Resumen_<fecha>.xlsx`.
   Tiene las hojas Resumen, Productos nuevos, Cambios, Expertos, Duplicadas
   (fila que queda y fila quitada) y Advertencias.

Al terminar aparece el aviso **"Expertos preparados"**, y la vista muestra los
archivos generados con enlaces a la carpeta, al resumen y al backup.
**Cerrar** deja solo una línea con la última preparación.

> Si la tabla o un experto que hay que reemplazar está **abierto en Excel**, la
> preparación se corta **sin cambiar nada**. Cerralo y pulsá de nuevo
> **Preparar expertos**: el análisis sigue disponible.

### Paso 4 — Revisar los expertos del ciclo y ejecutar

Debajo del panel del maestro, la misma vista muestra:

**a) Tabla de productos y tiendas habilitadas.** Debe decir `productos_TINT.xlsx`.

**b) Expertos del ciclo:** un renglón por experto, con el archivo que se va a
usar, la fecha con que salen sus archivos y los softwares a los que alimenta.

| Estado | Significado |
|---|---|
| 🟢 **OK** | Se va a usar el archivo indicado |
| 🟠 **Falta** | No hay archivo de ese experto: el ciclo se puede ejecutar, pero sus softwares no se generan (y al terminar llega el aviso **"Falta un experto"**) |
| 🔴 **Desactivado** | El experto está apagado en Configuración: sus softwares no se generan |

**c) Archivos en la carpeta de entrada**, con su estado:

- **OK:** se usa.
- **Se omite:** hay uno más nuevo, ningún software lo usa o es del flujo anterior.
- **Desactivado:** su experto está apagado.
- **Revisar:** nombre no reconocido, o un experto en `.xls`.

**d) Recuadros:** rojo = algo impide ejecutar (el botón queda desactivado);
naranjo = se puede ejecutar, pero algo queda afuera (por ejemplo, *"Falta
Experto 2: se omiten Tinwise_Lab"*).

Pulsá **Ejecutar** (el botón del cohete). La app vuelve a revisar la carpeta y
muestra el **Resumen del nuevo ciclo**:

- tiendas que se filtran;
- expertos activos, con cada software, sus tiendas y su formato;
- lo que no entra en este ciclo;
- cuántos archivos se generan.

Si está bien, pulsá **Ejecutar ciclo**.

> **Ejecutar** queda bloqueado mientras haya un maestro analizándose,
> analizado sin preparar o preparándose. Terminá de prepararlo o descartalo.
> Solo se corre **un ciclo a la vez**.

### Paso 5 — Seguir el progreso

La vista **Ejecución / progreso** muestra:

- el porcentaje total y el tiempo transcurrido;
- una barra por experto;
- un registro de lo que va haciendo.

Con los 3 expertos tarda **alrededor de 1 a 2 minutos**. Podés cambiar de vista
o de aplicación: al terminar aparece el aviso **"Ciclo terminado"**, con la
cantidad de archivos y de advertencias. No cierres la app mientras corre.

Al empezar, lo que había en `Archivos filtrados` (el ciclo anterior) se mueve a
`backups\<fecha de ese ciclo>\`. Así la carpeta queda solo con lo nuevo.

**Cancelar:** el botón **Cancelar** detiene el ciclo al terminar el paso en
curso. Los softwares de los expertos que ya habían terminado quedan generados.

**Si falla:** aparece *"La corrida falló"* con el detalle, y el aviso *"El ciclo
falló"*. La causa más común es un archivo de `Archivos filtrados` abierto en
Excel: cerralo y volvé a ejecutar desde **Nuevo ciclo**.

### Paso 6 — Revisar los resultados

La vista **Resultados** muestra:

- **Tres indicadores:** archivos generados, filas totales y advertencias. El
  de advertencias lleva a la lista de abajo.
- **Una tabla por software:** cada archivo con su tipo, sus filas y dos
  acciones. **Abrir** lo abre en Excel; **Carpeta** lo muestra en el Explorador.
- **Advertencias:** la lista completa de lo que quedó afuera del ciclo y por
  qué ([sección 8](#8-advertencias-del-ciclo)).

**Qué revisar:**

- Que estén todos los archivos esperados (12 con todo habilitado).
- Que las filas sean parecidas a las del ciclo anterior. Comparalas en Historial.
- Que no haya advertencias, o que estén entendidas. La más habitual es un
  **producto que no está en la tabla**: agregalo en Homólogos y volvé a ejecutar.

### Paso 7 — Importar en cada software

Cada software tiene su carpeta dentro de `Archivos filtrados`. Importá en cada
máquina el archivo de su tienda (`<Tienda>_ready_<fecha>.<ext>`) con la función
de importación del propio software.

---

## 7. Avisos al terminar

Los trabajos largos avisan cuando terminan, para que no tengas que quedarte
mirando la pantalla:

| Cuándo | Aviso | Color | Botón |
|---|---|---|---|
| Termina el análisis del maestro | **Análisis del maestro listo** (cuántos productos nuevos hay) | verde | Ir a Nuevo ciclo |
| Termina la preparación | **Expertos preparados** (qué archivos quedaron) | verde | Ir a Nuevo ciclo |
| Termina el ciclo sin advertencias | **Ciclo terminado** (archivos generados) | verde | Ver resultados |
| Termina el ciclo con advertencias | **Ciclo terminado** (archivos generados y cuántas advertencias) | naranjo | Ver resultados |
| **Falta un experto** en el ciclo (no estaba, venía en `.xls` o no se pudo leer) | **Falta un experto** / **Faltan N expertos**, con qué experto y qué softwares quedaron afuera. Llega aparte, además de "Ciclo terminado" | naranjo | Ver resultados |
| La preparación no puede generar un experto (falta su plantilla) | **Falta un experto**, al terminar el análisis y al terminar la preparación | naranjo | Ir a Nuevo ciclo |
| Algo falla | **No se pudo analizar el maestro**, **No se pudieron preparar los expertos** o **El ciclo falló**, con el motivo | rojo | Ir a Nuevo ciclo / Ver el detalle |

Cada aviso llega de dos formas:

1. **Dentro de la app:** un cartel abajo a la derecha, en cualquier vista. Tiene
   la hora y un botón a la vista que corresponde. Se cierra con la **×** o al
   entrar a esa vista. Si aparece cuando ya estás en esa vista, se va solo a
   los pocos segundos. Los de cancelación también se van solos.
2. **En Windows:** una notificación de **TINT_SIS** en la esquina de la pantalla.
   Queda también en el centro de notificaciones. Si la ventana de TINT_SIS no es
   la activa, su botón **parpadea** en la barra de tareas hasta que la abras.
   Las notificaciones de Windows no tienen color. Por eso las de advertencia y
   las de error llevan **⚠** en el título y **quedan en pantalla hasta que
   pulses Cerrar**, en vez de irse solas.

La notificación de Windows se puede apagar en **Configuración → Avisos al
terminar → Notificaciones de Windows**. El cartel dentro de la app sale siempre.

> Si no ves las notificaciones de Windows, revisá que el modo **No molestar**
> (o *Asistente de concentración*) esté apagado. Revisá también que TINT_SIS
> tenga permitidas las notificaciones en *Configuración de Windows → Sistema →
> Notificaciones*.

---

## 8. Advertencias del ciclo

Una advertencia es algo que **quedó afuera** del ciclo o que conviene revisar.
El ciclo igual se completa. Cada ciclo **guarda sus advertencias**, así que se
pueden ver después aunque se cierre la app:

- en **Resultados**, el último ciclo;
- en **Historial**, cualquier ciclo, con **Ver advertencias (N)**.

Se muestran **en naranjo**, numeradas. Cuando nombran productos, la **lista
completa** va debajo, con las filas de cada uno; si es larga, se despliega con
**Ver los N**. Cuando hay advertencias, el indicador de **Inicio** y el de
**Resultados** también se ponen en naranjo; el de Inicio lleva a la lista.

| Advertencia | Qué significa | Qué hacer |
|---|---|---|
| *Experto_N…: X filas de N producto(s) que no están en productos_TINT.xlsx no se entregaron a ninguna tienda* | El experto trae productos que no están en la tabla. Debajo va la lista con las filas de cada uno | Agregarlos en **Homólogos** (o asignar el nombre a un producto existente) y ejecutar de nuevo |
| *Falta Experto N: se omiten …* | No había archivo de ese experto (llega además el aviso **"Falta un experto"**) | Cargarlo, o prepararlo desde el maestro, y volver a ejecutar |
| *Experto N: … en formato .xls* | Llegó en `.xls`, que corta en 65.535 filas (también avisa **"Falta un experto"**) | Guardarlo como `.xlsx` y volver a cargarlo |
| *ningún producto marcado para <Tienda>* | Esa tienda no tiene ninguna `x` en la tabla | Revisar esa tienda en **Homólogos** |
| *no tiene columna para <Tienda>* | La tabla no tiene la columna de esa tienda | Revisar la tabla de productos |
| *no se pudo filtrar (…)* | El experto está dañado o no tiene el formato esperado | Revisar el archivo o pedirlo de nuevo |

> Los ciclos ejecutados con versiones anteriores a la 0.4.0 no guardaban sus
> advertencias. En ellos se muestra *"Este ciclo se ejecutó con una versión
> anterior"* y el conteo aparece como **"-"**.

---

## 9. Otras vistas

### 9.1 Inicio

Es el resumen de un vistazo:

- **Avisos**, con los mismos problemas que se verían en Nuevo ciclo: en rojo lo
  que impide ejecutar y en naranjo lo que quedaría afuera (por ejemplo, un
  experto que falta).
- **Último ciclo:** fecha, expertos en uso, archivos generados y cantidad de
  advertencias (en naranjo si hay alguna; al hacer clic lleva a la lista).
- Accesos directos a **Nuevo ciclo**, **Ver resultados**, **Historial** y
  **Configuración**.

### 9.2 Historial

Lista los ciclos ejecutados, del más reciente al más antiguo. Cada tarjeta
muestra:

- la fecha y hora (DD/MM/AA HH:MM) y la carpeta donde quedaron sus archivos;
- el estado de los archivos en disco: **backup completo**, **backup parcial
  (n/total)** o **backup no disponible**;
- la cantidad de archivos, de filas y de advertencias;
- **Abrir carpeta del backup**, **Ver archivos** (con Abrir / Carpeta por
  archivo) y **Ver advertencias (N)**.

Cada ciclo nuevo mueve los archivos del anterior a `backups\<fecha>\`, así que
los archivos de cada ciclo siguen disponibles. Los backups no se borran solos.
Cuando ya no hagan falta, se pueden eliminar a mano desde `Documentos\TINT_SIS\backups\`.

### 9.3 Homólogos (tabla de productos)

Es el editor de `productos_TINT.xlsx`:

- Los productos aparecen agrupados por **línea**. Cada uno muestra:
  - su nombre en Experto 1, 2 y 3;
  - cuántas fórmulas trae cada experto del ciclo con ese nombre, o un aviso si
    el nombre no está en el experto;
  - las **tiendas** que lo llevan, como casillas.

  Un producto sin tiendas lleva la marca *"sin tiendas: no se entrega"*.
- **Agregar producto** (o *Agregar producto a esta línea*) y **Nueva línea**
  abren un formulario. Tiene línea, producto, SUBP, el nombre en cada experto
  (con sugerencias) y las tiendas.
- **Eliminar** saca el producto de la tabla. Si los expertos lo siguen
  trayendo, el ciclo avisará que no está en la tabla.
- Abajo, **"Productos de los expertos que no están en la tabla"** lista lo que
  traen los expertos y no calza con ninguna fila. Cada uno tiene un botón para
  agregarlo.
- Los cambios se guardan recién al pulsar **Guardar cambios**. **Descartar**
  los deshace. Antes de guardar se deja una copia de la tabla en
  `backups\productos\<fecha>\`.
- No se guarda si la tabla está **abierta en Excel** o si cambió en el disco
  mientras se editaba. En ambos casos se avisa.
- Si salís de la vista con cambios sin guardar, la app pregunta antes.

Los nombres se comparan sin importar mayúsculas, tildes ni espacios:
`Ltx.Extracubriente Sipa` y `Ltx. Extracubriente Sipa` cuentan como el mismo.
También se puede seguir editando la tabla en Excel. Una `x` en la columna de
una tienda indica que la lleva.

### 9.4 Configuración

Los cambios se aplican al pulsar **Guardar**, al pie de la página. Aparece
*"Guardado en …"* para confirmar.

- **Carpeta de trabajo:** Entrada, Salida (base) y Base de datos. Las rutas están
  bloqueadas para evitar cambios por error: **Editar** (lápiz) desbloquea una,
  **Enter** o **Guardar** la guarda y **Bloquear** la vuelve a proteger.
- **Tiendas habilitadas:** un interruptor ON/OFF por tienda. Con una tienda
  apagada, sus archivos no se generan en ningún software.
- **Expertos habilitados:** un interruptor por experto, con los softwares que
  alimenta. Con un experto apagado, el sistema no lo lee y sus softwares no se
  generan. Por ejemplo, dejá solo el **Experto 3** para actualizar Santint y
  Corob.
- **Avisos al terminar:** el interruptor **Notificaciones de Windows** (sección 7).
- **Convención de nombres:** cómo tienen que llamarse los archivos de entrada
  (`productos_TINT.xlsx`, `Experto_1*.xlsx`, `Experto_2*.xls[xm]`,
  `Experto_3*.xlsx`). El `*` significa "cualquier texto". Solo conviene
  cambiarlos si los archivos empiezan a llegar con otro nombre.
- **Softwares:** tabla de solo lectura con cada software, su experto, sus
  tiendas y su formato.

---

## 10. Todo en galón: formatos de envase

Los 3 expertos salen siempre **por galón**, sin importar el envase con que
venga cada fórmula en el maestro (la columna **Formato**):

| Formato en el maestro | Qué hace TINT_SIS |
|---|---|
| `Galon` o `Galon (3.785 Lts.)` | Ya es galón: queda igual |
| `Tineta 4 gl` | Trae las cantidades para 4 galones: se **divide por 4** |
| Otro formato cuyo nombre dice la cantidad (`Balde 5 gl`, `1/4 galón`, `1 litro`) | Se divide por esa cantidad, y el análisis **avisa** que la equivalencia salió del nombre, para que la revises |
| Un formato cuyo nombre no dice cuánto trae (`Balde`, `Cuarto de galón`) | **Bloquea** la preparación: hay que pedir a tintometría el formato correcto o avisar a Desarrollo e Investigación |

En el **Experto 1**, una fórmula convertida queda con:

- Formato `Galon`;
- **Oz base** y la cantidad de cada colorante divididas. Por ejemplo,
  `OC-62.8` en tineta pasa a `OC-15.7`.

El código del colorante y la forma de escribir la celda no cambian. En Experto
2 y 3 las cantidades van siempre por galón (cm³ en Experto 2, 1/48 oz en
Experto 3).

El análisis muestra cuántas fórmulas se pasan a galón. Lo vas a ver en un
recuadro naranjo por formato y en "Expertos que se generan". El resumen en Excel
lo indica en la fila *"Fórmulas pasadas a galón"*.

> TINT_SIS se guía por la columna **Formato**. Si una fórmula dice `Galon` pero
> sus cantidades son de una tineta, no hay forma de detectarlo: esas cantidades
> pasan tal cual. Ya ocurrió con las Texturas el 28/09/2026. Si un producto nuevo
> trae cantidades que parecen 4 veces más altas que las de sus homólogos,
> consultalo con tintometría.

---

## 11. Mensajes frecuentes y cómo resolverlos

| Mensaje / síntoma | Causa | Qué hacer |
|---|---|---|
| *El maestro tiene que ser .xlsx* | El maestro llegó en `.xls` | Abrirlo en Excel, *Guardar como → Libro de Excel (.xlsx)* y volver a cargarlo |
| *Formato sin equivalencia a galón: '…'* | El maestro trae un envase cuyo nombre no dice cuántos galones o litros tiene | Pedir a tintometría el formato correcto, o avisar a Desarrollo e Investigación |
| *N celda(s) de colorante sin la forma CODIGO-CANTIDAD (fila …)* | Hay una celda de colorante mal escrita (por ejemplo `AO26.5`) | Corregirla en el maestro y volver a cargarlo |
| *No hay un Experto 2/3 anterior … que sirva de plantilla* | Falta el experto del ciclo anterior en la entrada | Ese experto no se genera. Copiá el anterior a la carpeta de entrada (ver 3.3) y volvé a cargar el maestro |
| *… está abierto (por ejemplo en Excel): cerrarlo y volver a preparar* | La tabla o un experto está abierto | Cerrar Excel y pulsar **Preparar expertos** de nuevo |
| *Hay un archivo maestro analizado: prepará los expertos (o descartalo)* | Quedó un maestro a medio camino | Prepararlo o pulsar **Descartar este maestro** |
| *Falta la tabla de productos (productos_TINT.xlsx)* | No está la tabla, o tiene otro nombre | Copiarla a la carpeta de entrada con ese nombre exacto |
| *No hay ningún experto habilitado* | Todos los expertos están apagados | Encender al menos uno en Configuración y pulsar **Guardar** |
| *No hay ningún archivo experto habilitado… en la carpeta de entrada* | No hay expertos o sus nombres no cumplen el patrón | Preparar los expertos desde el maestro, o revisar los nombres |
| Archivo en **Revisar**: *Nombre no reconocido por la convención* | El nombre no cumple ningún patrón | Renombrarlo o sacarlo de la carpeta de entrada |
| *La corrida falló* / *no se pudo respaldar el ciclo anterior* | Un archivo de `Archivos filtrados` está abierto en Excel | Cerrar Excel y volver a ejecutar |
| Advertencia: *… producto(s) que no están en productos_TINT.xlsx…* | Producto que la tabla no tiene | Agregarlo en **Homólogos** (sección 9.3) |
| No aparecen las notificaciones de Windows | Están apagadas en Configuración, o Windows está en *No molestar* | Ver sección 7. El cartel dentro de la app sale igual |
| *Ya hay una corrida en curso* | Hay un ciclo en marcha | **Ir al proceso actual** y esperar a que termine |
| Barra superior: *sin conexión con el servicio local* | El servicio interno de la app se detuvo | Cerrar y volver a abrir TINT_SIS |
| La app no abre | Error al iniciar | Revisar `%LOCALAPPDATA%\TINT_SIS\logs\tint_sis.log` y enviarlo a Desarrollo e Investigación |

---

## 12. Limitaciones conocidas de la versión 0.4.0

- **El CSV de Color_Pro3.1.1 todavía no está validado** contra un archivo de
  referencia del propio software. Si la importación falla o los datos se ven
  mal, avisá a Desarrollo e Investigación. Idealmente, mandá un archivo
  exportado por Color Pro 3.1.1.
- **La lista de softwares no se edita desde la app.** Para agregar o cambiar
  un software, contactar a Desarrollo e Investigación.
- La preparación necesita el **Experto 2 y 3 del ciclo anterior** en la
  carpeta de entrada, como plantilla (sección 3.3).
- La notificación de Windows **solo informa**: hacer clic en ella no abre la
  app. Para volver, usá el botón de TINT_SIS en la barra de tareas, que parpadea.
- Las advertencias de los ciclos anteriores a la 0.4.0 no quedaron guardadas
  (sección 8).
- Se corre **un ciclo a la vez**, y una preparación a la vez.

---

## 13. Novedades desde la versión 0.2.0

**0.4.0 (01-10-2026)**

- **Advertencias listadas:** Resultados y el Historial muestran cada
  advertencia del ciclo, con la lista completa de productos sin asignar. Quedan
  guardadas con cada ciclo.
- **Avisos al terminar:** cartel dentro de la app y notificación de Windows
  cuando terminan el análisis del maestro, la preparación de los expertos o un
  ciclo. La notificación se puede apagar en Configuración.
- **Aviso aparte cuando falta un experto**, en el ciclo y en la preparación.
- **Advertencias en naranjo** en toda la app; lo que impide seguir, en rojo.
- **Experto 1 también por galón:** si el maestro trae fórmulas en otro formato
  (por ejemplo `Tineta 4 gl`), se pasan siempre a `Galon` en los 3 expertos.

**0.3.1 (30-09-2026)**

- Las fórmulas duplicadas se detectan por *Clasificación + Producto + Cartilla
  + Color + Base*, y se deja la primera.
- Experto 3 no lleva cartilla: el mismo color en varias cartillas va una sola vez.
- Inicio ya no muestra el aviso de "carpeta de entrega".

**0.3.0 (28-09-2026)**

- **Preparar los expertos desde el archivo maestro**, dentro de Nuevo ciclo.
- **Homólogos** pasa a ser el editor de la tabla de productos.
- Los archivos de salida llevan la fecha del experto en el nombre, y cada ciclo
  respalda el anterior en `backups\`.
- Fechas DD/MM/AA en el Historial.

---

*Soporte: Departamento de Desarrollo e Investigación.*
