# Plan Inicial: Sistema de Integración "Base de Datos Madre" → 6 Software de Tintometría

## 0. Resumen ejecutivo

Se construirá un sistema que tome como origen los Excel maestros que entrega el departamento de tintometría cada 15 días y genere, de forma automática, el archivo en el formato exacto que necesita cada una de las 6 máquinas de pintura/tintometría de la empresa.

La arquitectura elegida es un **hub central con adaptadores por máquina**: un único modelo de datos central que se transforma a 6 formatos de salida distintos, en vez de 6 procesos manuales independientes como se hace hoy.

El **piloto** del proyecto es el software **CorobLab 4.1.2**, cuyo formato de salida quedó **100% confirmado** a partir de un archivo real de referencia, el manual oficial del software y un Excel maestro real, todos entregados y analizados. El resto de los software (Fluid, Santint, Tintwise_Lab, Ibicus Spa, Xdata) se incorporan más adelante, cuando se cuente con su documentación.

---

## 1. Contexto del negocio

La empresa dispensa pintura a través de 6 máquinas, cada una controlada por un software distinto. Cada software necesita un archivo de fórmulas de color en su propio formato para funcionar.

Hoy, el departamento de tintometría entrega **un Excel maestro por cada línea de producto** (ej. "Latex Experto y Homologos", "Extracubriente", etc. — cada línea en su propio archivo), cada 15 días, con los cambios de colores, cantidades y valores. Ese Excel se transforma **manualmente**, hoja por hoja y con fórmulas, al formato que necesita cada máquina, y luego un técnico actualiza físicamente cada equipo con esa data.

El objetivo de este proyecto es automatizar esa transformación, comenzando por la máquina cuyo flujo ya se conoce completo: **CorobLab**.

| # | Software | Formato de salida | Estado |
|---|---|---|---|
| 1 | **CorobLab 4.1.2** | `.txt` delimitado por tabulación, 20 columnas, codificación ISO-8859-1, CRLF | ✅ Confirmado — piloto en construcción |
| 2 | Fluid | Por definir | Pendiente — se comparte más adelante |
| 3 | Santint | Por definir | Pendiente |
| 4 | Tintwise_Lab | Por definir | Pendiente |
| 5 | Ibicus Spa (CL-PC) | Por definir | Pendiente |
| 6 | Xdata | Por definir | Pendiente |

---

## 2. Terminología aclarada

Durante el levantamiento surgieron nombres que podían confundirse entre sí. Quedan aclarados así:

| Término | Qué es realmente |
|---|---|
| **CorobLab 4.1.2** | El software que administra la base de fórmulas de tintometría de la máquina piloto. |
| **GData** | Nombre que usa el fabricante (Corob) para la estructura de datos/base de fórmulas que gestiona CorobLab (colorantes + bases + fórmulas). No es un software aparte, es parte de CorobLab. |
| **TWIST** | Nombre de la **línea de concentrados/colorantes** que usan las máquinas. Se usó para nombrar el archivo de referencia (`TWIST_4_1_2.txt`), pero no identifica un software ni un sistema distinto de CorobLab. |
| **Archivo piloto / archivo GData** | El `.txt` de salida que CorobLab necesita para actualizar la máquina con las fórmulas de una línea de producto. |

---

## 3. Objetivo del proyecto

1. Ingerir **todos** los Excel maestros que entrega tintometría cada 15 días (uno por línea de producto).
2. Detectar automáticamente qué cambió respecto al ciclo anterior, por línea de producto (sin depender de un registro manual de cambios).
3. Validar y transformar los datos a un **modelo de datos único (canónico)**, independiente del formato de cada máquina.
4. Generar, a partir de ese modelo, el archivo `.txt` exacto que necesita CorobLab para cada línea de producto.
5. Dejar esos archivos listos para que los técnicos actualicen físicamente cada máquina.
6. Registrar auditoría: qué se generó, desde qué versión del Excel, y qué cambió.
7. Dejar la base construida para, más adelante, agregar los adaptadores de los otros 5 software sin rediseñar el sistema.

---

## 4. Arquitectura elegida: Hub central + Adaptadores por máquina

**Patrón**: integración tipo ETL con Adapter Pattern — un origen de datos único (el conjunto de Excel maestros), un modelo canónico central, y un "traductor" (adaptador) independiente por cada máquina.

```
Excel línea 1  ─┐
Excel línea 2  ─┤
Excel línea 3  ─┼──▶  INGESTA + RESHAPE   ──▶  VALIDACIÓN  ──▶  MODELO CANÓNICO (BD)
Excel línea N  ─┘     (por archivo,             (reglas de          │  histórico por
                       consolidando               negocio,          │  línea de producto
                       varias líneas)              rangos, campos    │
                                                    obligatorios)     │
                                                                      ▼
                                                        ┌─────────────┼─────────────┬─────────────┬─────────────┬─────────────┐
                                                        ▼             ▼             ▼             ▼             ▼             ▼
                                                  Adaptador      Adaptador     Adaptador     Adaptador     Adaptador     Adaptador
                                                  CorobLab       Fluid         Santint       Tintwise_Lab  Ibicus Spa    Xdata
                                                  (PILOTO)       (a futuro)    (a futuro)     (a futuro)    (a futuro)    (a futuro)
                                                        ▼
                                            .txt tabulado, 20 columnas,
                                            ISO-8859-1, CRLF (1 por línea de producto)
                                                        ▼
                                          Carpeta de entrega → Técnico → Máquina física
                                                        ▼
                                          Log / Auditoría (por línea, por ciclo, cambios detectados)
```

### Por qué esta arquitectura es la adecuada

- **Un solo lugar para las reglas de negocio**: se validan los datos una vez, no 6 veces (una por máquina).
- **Agregar una máquina nueva = agregar un adaptador**, sin tocar los otros 5 ya construidos.
- **Trazabilidad centralizada**: se sabe qué se generó, cuándo y con qué datos de origen.
- **Ya es el patrón que la empresa usa manualmente hoy**: el Excel maestro real analizado trae una hoja llamada "Formulario para Alfa Tinting", que es, en la práctica, un adaptador manual (con fórmulas de Excel) hacia otro formato. Esto confirma que el patrón "un origen → varios formatos de salida" es una necesidad real y ya validada en la operación diaria.

*(Se descartaron, por ahora, arquitecturas más complejas como microservicios independientes por máquina o procesamiento por eventos en tiempo real — el proceso es por lotes cada 15 días, así que no se justifican. Si el equipo decide más adelante pasar a actualización por evento, esta arquitectura lo permite sin rediseño.)*

---

## 5. Formato de salida confirmado: CorobLab (piloto)

Se confirmó con tres fuentes: un archivo `.txt` real ya usado por la empresa, el manual oficial de CorobLab, y un Excel maestro real.

**Reglas del archivo de salida**:

- **Delimitador**: tabulación (`\t`)
- **Codificación**: ISO-8859-1 / Latin-1 — **no UTF-8** (importante por nombres con tildes y "ñ", ej. "Tecnoconstrucción")
- **Fin de línea**: CRLF (estilo Windows)
- **Primera fila**: encabezado con el nombre de cada columna
- **Separador decimal**: punto (`.`)
- **20 columnas fijas**, en este orden, incluso si alguna queda vacía:

1. Clasificacion
2. Producto
3. Cartilla
4. Formato
5. Tolerancia Luz
6. Primer
7. Color
8. R
9. G
10. B
11. Base
12. Oz Base
13. Col. 1
14. 1/48 onzas
15. Col. 2
16. 1/48 onzas
17. Col. 3
18. 1/48 onzas
19. Col. 4
20. 1/48 onzas

Hasta 4 colorantes por fórmula; si se usan menos, las columnas sobrantes quedan vacías (no se eliminan columnas).

Este formato coincide con la exportación nativa de fórmulas en modo texto que describe el propio manual de CorobLab, lo que reduce el riesgo técnico del piloto: no se está adivinando un formato propietario cerrado, sino replicando un export de texto plano ya documentado por el fabricante.

---

## 6. Del Excel maestro al archivo final: mapeo de columnas

El Excel maestro real (hoja **"FORMULARIO "**) no es una tabla simple: tiene **70 columnas**, porque además de los datos de la fórmula incluye cálculos de costos, densidades y conversiones a mililitros que **no van en el archivo final**. El mapeo confirmado es:

| Columna en el Excel maestro | Campo de salida en el `.txt` de CorobLab |
|---|---|
| FAMILIA | Clasificación *(requiere tabla de equivalencia — ver sección 10, pendiente)* |
| PRODUCTO | Producto |
| CARTILLA | Cartilla |
| FORMATO | Formato |
| TOLERANCIA LUZ | Tolerancia Luz |
| PRIMER | Primer |
| COLOR | Color |
| R, G, B | R, G, B |
| BASE | Base |
| Oz base | Oz Base |
| COL_1 + su cantidad en 1/48 onzas | Col. 1 + 1/48 onzas |
| COL_2 + su cantidad en 1/48 onzas | Col. 2 + 1/48 onzas |
| COL_3 + su cantidad en 1/48 onzas | Col. 3 + 1/48 onzas |
| COL_4 + su cantidad en 1/48 onzas | Col. 4 + 1/48 onzas |

**Ubicación dentro del Excel**: el encabezado de esta tabla está en la fila 40 (no en la fila 1; antes hay título y datos auxiliares de costo/densidad), y los datos de fórmulas comienzan en la fila 41.

**Columnas que se descartan** del archivo de salida (pero se recomienda conservarlas en el modelo canónico como metadata, útiles para costeo o reportes internos): costos por colorante, "Total Onzas galón", conversiones a mililitros, "Oz Total base + colorantes", "Sobrellenado", "concentrados repetidos", el resumen de 14 colorantes en columnas aparte, y los campos de revisión interna (REVISADO EN AT, RESULTADO DE CMC, VERSIÓN, RESPONSABLE, Observaciones).

*(Queda por validar, al recibir los Excel de otras líneas de producto, si todas siguen exactamente esta misma estructura de hoja/fila, o si varía de una línea a otra.)*

---

## 7. Ingesta multi-archivo (consolidación por ciclo)

Como cada línea de producto llega en un **archivo Excel separado**, la capa de ingesta debe:

1. Recibir un **lote de archivos Excel** en cada ciclo de 15 días (no un solo archivo).
2. Procesar cada archivo individualmente con el mapeo de columnas de la sección 6.
3. Identificar a qué línea de producto corresponde cada archivo (por nombre de archivo o por el campo "PRODUCTO"/"FAMILIA" dentro del Excel), y usar esa identificación para nombrar el `.txt` de salida correspondiente.
4. Guardar cada línea de producto en el modelo canónico de forma independiente, manteniendo histórico y detección de cambios por línea.

**Nota de diseño importante**: como cada línea de producto genera su propio archivo `.txt` (tal como se confirmó con el archivo de referencia real, que correspondía solo a una línea), lo más probable es que la relación sea **1 Excel de línea → 1 archivo `.txt` de esa línea**, no un archivo consolidado con todas las líneas. Esto se valida formalmente probando con la máquina real (ver Fase 6 del roadmap).

---

## 8. Ciclo operativo cada 15 días

1. Tintometría entrega los Excel maestros actualizados (uno por línea de producto), cada uno como una foto completa (snapshot con todo el histórico, no solo los cambios).
2. El sistema ingiere cada Excel, aplica el mapeo de columnas y arma el modelo canónico, identificando la línea de producto de cada archivo.
3. El sistema **compara automáticamente** cada línea contra su última versión procesada, generando un reporte de diferencias (colores nuevos, cantidades modificadas, colores eliminados) — sin depender de que alguien registre manualmente los cambios.
4. Se valida el modelo canónico (campos obligatorios, rangos numéricos válidos, formato correcto).
5. Se genera el archivo `.txt` de CorobLab para cada línea de producto.
6. Durante la etapa de pruebas, cada archivo generado se compara automáticamente contra el archivo de referencia conocido, hasta asegurar equivalencia exacta de formato.
7. Los archivos quedan disponibles para que los técnicos los copien a la máquina física.
8. Todo el proceso queda registrado en el log de auditoría (línea de producto, versión de origen, cambios detectados, resultado de validación).

---

## 9. Stack tecnológico sugerido

Pensado para trabajar hoy en PC local, pero listo para escalar a un servidor en la nube accesible desde cualquier dispositivo:

- **Lectura de Excel**: Python (`pandas`, `openpyxl`).
- **Base de datos maestra (staging + histórico)**: PostgreSQL desde el inicio (puede correr en Docker local), para no migrar de motor más adelante.
- **Empaquetado**: Docker desde el inicio, aunque se ejecute en PC local, para que mover el sistema a la nube después sea casi directo.
- **Adaptadores**: módulos Python independientes, uno por software (se construye primero el de CorobLab).
- **Generación del archivo de salida**: control explícito de codificación (ISO-8859-1), delimitador y fin de línea, ya que son requisitos exactos y no configuraciones por defecto de la mayoría de las librerías.
- **Acceso multi-dispositivo (meta futura)**: panel web simple para ver el estado de la última actualización, descargar archivos generados y revisar errores de validación.
- **Logs/auditoría**: tabla en la misma base PostgreSQL.

---

## 10. Roadmap de fases

1. **Fase 1 – Modelo canónico**: definir la estructura de datos única a partir del mapeo confirmado (sección 6).
2. **Fase 2 – Ingesta multi-archivo**: construir la lectura de varios Excel por ciclo (uno por línea de producto) y su consolidación en el modelo canónico.
3. **Fase 2.5 – Tabla de equivalencia Familia → Prefijo numérico** *(pendiente — ver sección 11)*: reunir con tintometría o el equipo técnico la tabla completa que traduce nombres de familia (ej. "Latex") al prefijo del archivo final (ej. "1.-Latex"), incluyendo todas las familias existentes.
4. **Fase 3 – Validación**: reglas de negocio (campos obligatorios, formato numérico, colorantes válidos), aplicadas por línea de producto.
5. **Fase 4 – Adaptador CorobLab (piloto)**: generar el `.txt` por línea de producto y compararlo contra el archivo de referencia hasta lograr equivalencia exacta.
6. **Fase 5 – Detección de cambios**: comparación automática entre versiones del Excel maestro, por línea de producto.
7. **Fase 6 – Prueba con la máquina real**: validar con los técnicos si CorobLab espera un archivo por línea o uno consolidado, y confirmar que la máquina acepta el archivo generado sin errores.
8. **Fase 7 – Definir los otros 5 formatos** (Fluid, Santint, Tintwise_Lab, Ibicus Spa, Xdata) cuando se compartan, replicando el patrón de adaptador ya validado.
9. **Fase 8 – Entrega, logs y monitoreo** más robustos.
10. **Fase 9 – Migración a servidor en la nube** accesible desde cualquier dispositivo.

---

## 11. Riesgos y consideraciones

- **Codificación de caracteres**: el archivo final debe ser ISO-8859-1, no UTF-8. Cuidado con tildes y "ñ".
- **Mapeo explícito por nombre de columna, no por posición**: para que un cambio de orden en el Excel no arruine el archivo generado.
- **Precisión numérica**: un error de decimal en "1/48 onzas" puede arruinar una mezcla física de pintura.
- **Identificación correcta de la línea de producto** al consolidar varios Excel por ciclo, para no mezclar datos de líneas distintas.
- **Variabilidad de estructura entre líneas**: falta confirmar si todas las líneas de producto siguen exactamente la misma estructura de hoja/fila del Excel analizado, o si alguna varía.

---

## 12. Preguntas abiertas restantes

1. **Tabla de equivalencia Familia → Prefijo numérico** (ej. "Latex" → "1.-Latex"), completa para todas las familias (esmaltes, barnices, etc.), no solo Latex. No bloquea el inicio del desarrollo, pero sí el cierre del piloto (Fase 2.5).
2. ¿CorobLab espera un archivo `.txt` por línea de producto, o se pueden/deben consolidar varias líneas en un mismo archivo? Se resuelve en la Fase 6, probando con la máquina real.
3. Formatos de los otros 5 software (Fluid, Santint, Tintwise_Lab, Ibicus Spa, Xdata): pendientes de que se compartan cuando estén disponibles.

---

*Este es el plan inicial consolidado y vigente del proyecto. Las Fases 1 a 6 (todo lo referido al piloto CorobLab) pueden comenzar a ejecutarse con la información ya confirmada en este documento.*
