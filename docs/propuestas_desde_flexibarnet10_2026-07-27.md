# Propuestas para DocScan Studio a partir de FlexibarNET 10

**Fecha:** 2026-07-27
**Fuente analizada:** `Tecnomedia/FlexibarNET10` @ `5f80686` (v1.11.0, push del 2026-07-27)
**Estado DocScan de referencia:** v0.1.5, 883 tests verdes, rama `main` limpia

---

## 1. Método

He clonado el repo en un scratchpad temporal y he leído:

- `CLAUDE.md`, `docs/changelog.md` completo (978 líneas, de v0.3.0 a v1.11.0),
  `docs/auditoria-paridad-docscan.md`, `docs/manual/` (conceptos, launcher, workbench,
  configurator, batchmanager) y las paletas `Themes/Palette.{Dark,Light}.xaml`.
- Las **capturas reales** del manual (`docs/manual/images/`): launcher, workbench,
  configurator, gestor de lotes, diseñador OMR.

Para comparar la estética en igualdad de condiciones he **regenerado capturas reales de
DocScan** con las ventanas de verdad en `QT_QPA_PLATFORM=offscreen` y tema oscuro
aplicado (mismo patrón de la validación del 22/07).

Todo lo que afirmo sobre DocScan está verificado contra el código, no supuesto. Donde no
he podido confirmarlo, lo marco explícitamente como **a verificar**.

> Nota: `docs/auditoria-paridad-docscan.md` del repo de Flexibar va en la dirección
> contraria (DocScan → Flexibar) y está **congelado en v0.3.4**, ~27 releases atrás. No lo
> he usado como fuente de verdad; el estado vigente es el changelog.

---

## 2. Resumen ejecutivo

FlexibarNET 10 lleva **v1.11.0, en producción real** (instalaciones kiosco, licenciamiento,
clientes de laboratorio). DocScan v0.1.5 está en validación de campo. La diferencia de
madurez no es de arquitectura —el núcleo de DocScan es sano— sino de **kilómetros de uso**:
casi todo lo interesante de Flexibar son cosas que se aprendieron rompiendo algo delante de
un operador.

Las tres ideas con más retorno, por orden:

1. **El separador como propiedad de la página, no como un barcode más.** Es un cambio de
   modelo pequeño que desbloquea documento lógico, transferencia por documento, token
   `{separator}` y una UI de separación entendible. Hoy DocScan lo resuelve por script.
2. **Transferencia asíncrona en cola.** El operador deja de esperar al export pesado.
3. **Launcher como hub**: grupos, icono/color por app y etiquetas derivadas de la config.
   Es la mejora estética con mayor relación impacto/esfuerzo.

Y un hallazgo de robustez que conviene mirar ya: **DocScan cachea los scripts compilados
por `step.id`, no por contenido** (`app/services/script_engine.py:57,85,138`). Flexibar
tenía exactamente ese bug y lo corrigió en v0.6.0 (#153) porque *editar un script podía
seguir ejecutando la versión antigua*.

---

## 3. Bloque A — Modelo de datos y funcionamiento

### A1. Separador como entidad de primera clase 🔴

**Flexibar** (v0.5.0): cada página tiene `SeparatorValue`, una instantánea del valor,
**disociada de la colección de códigos leídos**. Marcar/desmarcar separador y leer/borrar
barcodes son acciones independientes. La detección automática se configura por condición
(simbología / regex / valor fijo) en el paso Barcode; la marca manual abre un diálogo
validado por `SeparatorManualRegex`.

**DocScan hoy**: `CLAUDE.md` fija que «BarcodeStep es role-agnostic: acumula en
`page.barcodes` sin semántica de separador. Los roles los asigna un ScriptStep posterior».
El modelo `Barcode` tiene `role`, pero `Page` no tiene concepto de separador.

**Propuesta**: añadir `separator_value: str | None` a `Page` (migración Alembic) y una
condición de separador declarativa en `BarcodeStep`. **No rompe la regla role-agnostic**:
el paso sigue sin interpretar roles, solo evalúa una condición explícita que el usuario
configuró. El ScriptStep sigue pudiendo sobrescribirlo.

**Desbloquea**: A2, el token `{separator}` en transferencia, y la UI de A6.

### A2. Documento como vista lógica 🟠

**Flexibar**: el Documento *no es una entidad almacenada* — es el tramo entre separadores,
calculado al vuelo. Las páginas previas al primer separador forman un «documento
implícito», de modo que siempre hay al menos uno. Permite modo de transferencia
«por documento» (un PDF por albarán) y agrupación visual en las miniaturas.

**DocScan hoy**: no hay `document.py` en `app/models/`. La transferencia es por lote.

**Propuesta**: función pura `split_documents(pages) -> list[list[Page]]` en el dominio
(sin tabla nueva, sin migración) + modo «por documento» en `TransferService`. Barato y de
mucho valor para archivo masivo.

### A3. Transferencia asíncrona en cola 🟠

**Flexibar** (v1.1.0): «Transferir» libera el lote a una cola en segundo plano y el
operador sigue escaneando. Servicio en la bandeja del sistema, reintentos con backoff,
recuperación tras cierre brusco, escritura atómica y *keep-alive* (cerrar la ventana con
cola pendiente mantiene el proceso vivo hasta terminar). El modo síncrono se conserva
como opción y para depurar.

**DocScan hoy**: `TransferWorker` es un QThread síncrono respecto al flujo del operador.

**Propuesta**: cola persistida en SQLite + worker. Ojo a las dos lecciones que Flexibar
pagó: **idempotencia al encolar** (índice único parcial; encolar dos veces por doble clic
transfería por duplicado, v1.6.1) y **los eventos de la app deben cargarse también en el
worker de la cola** — en Flexibar `on_transfer_validate` no se evaluaba en modo asíncrono
y la validación se saltaba en silencio (v1.6.2).

### A4. Retención automática y borrado físico de lotes 🟠

**Flexibar** (v1.2.0/v1.3.0/v1.3.1): retención configurable en Preferencias (desactivada
por defecto, 90 días), borrado de la carpeta física además del registro, protección de
lotes con transferencia en curso, y —clave— **las carpetas se borran solo después de que
el borrado en BD quede confirmado**, nunca antes.

**DocScan hoy**: sin retención (`grep retention` no encuentra nada).

### A5. Cara anverso/reverso de la página 🟡

**Flexibar**: `Page.Side` (A/B/Unknown), del driver TWAIN si lo reporta o inferido
alternando en el ADF. Badge A/B en la miniatura y disponible para los scripts (rotar 180°
los reversos, descartarlos, etc.). Aplica igual a SANE en dúplex.

### A6. UX de separación en el Workbench 🟠

**Flexibar**: zona «Separador de documento» con borde naranja en el panel derecho, con el
valor de la página actual y botón «Editar valor»; las miniaturas marcan el inicio de cada
documento. Se ve en la captura del manual.

### A7. Botones programables 🟡

**Flexibar** (v0.5.4): hasta 2 botones por app en la barra del visor que ejecutan un script
propio, validados al guardar (avisan si no compila). DocScan tiene eventos de navegación
en el catálogo, pero no botones libres con rótulo configurable.

### A8. Campos obligatorios que bloquean la transferencia 🟡

**Flexibar** (v1.6.2): un campo de lote marcado obligatorio y vacío **detiene** la
transferencia antes de exportar nada, nombrando los campos pendientes. Hasta esa versión
la marca era decorativa. Merece la pena comprobar si en DocScan `required` es efectivo.

### A9. Perfiles de escaneo por escáner 🟡

**Flexibar** (v0.5.5): los perfiles cuelgan del escáner, no de la app; al elegir escáner
solo aparecen los suyos. Export/import suelto (`.flexiscan.json`) que **lleva dentro el
escáner de origen**, para que la configuración «viaje con el escáner» entre estaciones.

### A10. Consentimiento informado al importar apps 🟠 (seguridad)

**Flexibar** (v0.6.0 #159): importar un pack que contenga **código ejecutable** (scripts de
eventos, pasos, botones, transferencia) muestra un diálogo que **enumera todo ese
contenido** antes de continuar; si se cancela no se importa nada.

DocScan tiene `app_export_service` con la misma superficie de riesgo: un `.json` de app
trae scripts Python que se ejecutan. Esto es barato y evita un problema serio.

---

## 4. Bloque B — Estética y UX

Comparando las capturas reales (Flexibar v1.6.2 vs DocScan v0.1.5 en oscuro), la estructura
de DocScan es correcta —sidebar, título, buscador, tarjetas— pero le falta **jerarquía
visual y densidad de información**.

### B1. Paleta: de Catppuccin a navy profundo

DocScan usa Catppuccin Mocha (`#1e1e2e` base, `#313244` superficie, `#89b4fa` acento).
Flexibar partió de ahí y **viró a navy profundo** en v0.7.0 conservando las claves:

| Rol | DocScan hoy | Flexibar v1.x |
|---|---|---|
| Base | `#1e1e2e` | `#0d1422` |
| Mantle / fondo hundido | `#181825` | `#0a0f1b` |
| Surface 0 / 1 / 2 | `#313244` / `#45475a` / `#585b70` | `#141d2f` / `#1e2a40` / `#2b3a55` |
| Texto | `#cdd6f4` | `#e3eaf7` |
| Subtexto | `#a6adc8` | `#c2cde2` |
| Azul acento | `#89b4fa` | `#60a5fa` |
| Verde / Rojo | `#a6e3a1` / `#f38ba8` | `#4ade80` / `#f0718c` |
| Naranja (separador) | — | `#f97316` |

Dos detalles que ellos documentan en el propio XAML y que conviene robar: **aclararon
`Overlay0`/`Subtext0`** tras un reporte de legibilidad de textos pequeños sobre fondo
oscuro (#56), y el título del launcher usa un **degradado** de texto claro a azul acento.

### B2. Tarjetas de aplicación: el mayor salto visual

Flexibar muestra por app: **icono cuadrado de color** (12 iconos × 7 acentos, o
**derivados automáticamente** de lo que la app realmente hace), nombre, descripción,
**hasta 3 etiquetas automáticas** (`Códigos de barras`, `Scripts`, `TIFF`, `PDF / JBIG2`),
fecha localizada y menú **⋮** con todas las acciones.

DocScan muestra un avatar gris con la inicial, nombre, descripción y fecha en ISO
(`2026-07-27`). Sin etiquetas, sin menú contextual.

Lo potente es que **las etiquetas y el icono no se mantienen a mano**: se derivan de la
config. En DocScan es una función pura sobre `pipeline_json` + `transfer_json`.

### B3. Grupos colapsables en el Launcher

Flexibar (v0.8.0): grupo de un nivel por app (p. ej. por cliente), cabeceras colapsables
con contador, estado recordado entre sesiones, asignable desde el configurador o desde el
menú contextual. Con 7 apps ya se nota; con 20 es imprescindible.

### B4. Editor de pipeline master-detail

Diferencia de fondo, visible en las capturas:

- **Flexibar**: lista de pasos a la izquierda + **editor del paso seleccionado a la
  derecha, en la misma pantalla**. Cada paso con icono y color por tipo, checkbox real de
  activo/inactivo, y drag-and-drop.
- **DocScan**: lista plana donde el estado se pinta como **texto ASCII** (`[✓] Imagen:
  (sin operación)`), y editar abre un **diálogo modal** (`step_dialogs/`).

El master-detail elimina el modal del bucle de configuración, que es lo que más se repite
al montar una app.

### B5. Semántica de color en las acciones

Flexibar: **Transferir en verde**, **Cerrar lote en rojo**, claramente diferenciadas como
acciones de salida. En DocScan ambos son botones idénticos, uno al lado del otro.

### B6. Toolbar del Workbench

DocScan usa **radio buttons «Escáner / Importar»** + combos + botones de texto. Flexibar
usa botones con icono y un desplegable de perfil. Los radio buttons son el elemento que más
delata la edad del diseño.

### B7. Coherencia de iconografía en la barra del visor

En la captura de DocScan la fila de navegación mezcla iconos azules, naranjas y rojos con
grosores distintos (`>|||`, `>!`, tijeras, bandera). Flexibar mantiene un único trazo
monocromo y reserva el color para el estado.

### B8. Barra de estado con contenido

Flexibar: contador de apps a la izquierda y **indicador «● Listo»** a la derecha; en el
Workbench, `Procesado 5/5` y `1240x1754 — 150 DPI`. DocScan tiene texto suelto sin
contenedor.

### B9. Salto directo a página 🟢 (barato, alto valor)

Flexibar v1.11.0, **petición de campo de la primera semana de uso**: el «N» del contador
`N / M` es editable — clic, teclear, Intro. Pensado para lotes de 600 páginas. Nueve líneas
de código y el operador lo agradece de inmediato.

---

## 5. Bloque C — Robustez: lecciones ya pagadas

Estas salen de sus auditorías (2026-06-10, 2026-07-15, 2026-07-20). Son baratas de aplicar
y evitan fallos que solo aparecen en producción.

| # | Lección | Estado en DocScan |
|---|---|---|
| C1 | **Caché de scripts por contenido, no por id** (#153) | ⚠️ **DocScan cachea por `step.id`** (`script_engine.py:57,85,138`). Editar un script puede ejecutar la versión anterior si el engine sobrevive al guardado. **Revisar.** |
| C2 | **Paso sin configuración propia hereda la del anterior** (#146) | A verificar. En Flexibar, un `BarcodeStep` sin config heredaba la del último ejecutado *de cualquier app*: leer o no dependía del orden de uso. |
| C3 | **Regex con timeout** (v1.6.1) | A verificar. Un patrón patológico en `barcode_regex` puede colgar el pipeline. Límite de 1 s y criterio fail-open. |
| C4 | **Escritura atómica** (temp + rename) de preferencias y perfiles | A verificar. Evita JSON truncado si la app se cierra durante el guardado. |
| C5 | **Borrar carpetas solo tras confirmar la BD** (v1.3.1) | Aplicar en el borrado de lotes. |
| C6 | **Los `catch` best-effort dejan rastro en el log** (#275) | Alineado con la regla de DocScan de no tragar excepciones; conviene un barrido. |
| C7 | **Cancelación honesta** (v1.6.1) | Cancelar devolvía «terminado» en vez de propagar la cancelación. |
| C8 | **Ids de paso curados al cargar** (v1.6.1) | Ids vacíos o duplicados reventaban el ejecutor al final del proceso; regenerarlos al deserializar y rechazar packs malformados al importar. |
| C9 | **«Lo que ves es lo que se transfiere»** (#142) | **A verificar en DocScan**: en Flexibar las ImageOps solo se aplicaban a la imagen en pantalla y la transferencia enviaba el original sin procesar. En `executor.py:105` DocScan propaga la imagen al `page` solo si un script llamó a `replace_image`; hay que confirmar quién persiste el resultado de un `ImageOpStep` al fichero. |

Además, un patrón de ingeniería que merece copiarse: `app/models/__init__.py` está vacío,
y por eso correr un test suelto falla con mappers sin resolver (ya anotado como quirk
conocido). Importar los modelos ahí lo cierra en tres líneas.

---

## 6. Lo que NO conviene copiar

- **JBIG2 / JPEG2000 / PDF MRC**: dependen de licencias Vintasoft. En Python habría que ir
  a `jbig2enc` externo o `glymur`/OpenJPEG, con calidad y empaquetado peores. Coste alto,
  retorno dudoso salvo cliente que lo exija.
- **Motor OMR + diseñador de plantillas**: es un producto dentro del producto (v1.4.0-v1.5.0,
  registración por homografía, dropout de color, refinamiento local). No tiene sentido sin
  un cliente de volantes detrás.
- **Licenciamiento Keygen + AdminWeb + firma de código**: responde a que Flexibar se vende
  instalado en kioscos de terceros. Solo si DocScan toma ese camino.
- **Tienda de Apps**: elegante, pero DocScan ya tiene export/import y una sola estación.

---

## 7. Lo que DocScan hace mejor

No todo va en una dirección:

- **Overlay del visor**: DocScan pinta rectángulos de barcode con paleta rotatoria **y
  además overlays de campos extraídos con etiqueta y valor**
  (`document_viewer.py:150-210`). Flexibar cerró el overlay de barcodes en v0.3.3 y no
  tiene el de campos («sin IA» en su matriz).
- **Contadores de lote**: `Total / Con barcode / Separadores / Revisión` ya están en el
  panel derecho. En Flexibar seguían como gap 🟠 en la última matriz.
- **IA generativa**: asistente de pipelines y modo IA. En Flexibar es «Fase 8», nunca
  abordado.
- **Doble motor de barcode** (pyzbar + zxing-cpp) y **OCR alternativos**: Flexibar depende
  de un único SDK.
- **Multiplataforma** (SANE + TWAIN + WIA) frente a Windows-only.
- **Worker headless** operativo; su FlexiReader sigue siendo un stub.
- **Notificaciones** (webhook, y SMTP en camino): en Flexibar están descartadas.

---

## 8. Priorización propuesta

| Prio | Propuesta | Esfuerzo | Notas |
|---|---|---|---|
| 1 | C1 caché de scripts por contenido | XS | Bug latente, arreglo de minutos |
| 2 | B2+B3 tarjetas con icono/etiquetas + grupos | M | Mayor impacto visual por euro |
| 3 | A1 separador como propiedad de la página | M | Desbloquea A2 y A6 |
| 4 | A2 documento lógico + transferencia por documento | M | Depende de A1 |
| 5 | B9 salto directo a página | XS | Petición típica de operador |
| 6 | B5+B6 semántica de color y toolbar con iconos | S | Quita la cara «vieja» |
| 7 | A10 consentimiento al importar apps | S | Seguridad real |
| 8 | C4+C5+C8 robustez (atómica, borrado, ids) | S | Barato, evita corrupción |
| 9 | A3 transferencia asíncrona | L | Ojo a idempotencia y eventos en el worker |
| 10 | A4 retención automática | M | Depende de C5 |
| 11 | B1 viraje de paleta a navy | S | Cosmético; hacer aparte, no mezclar |
| 12 | B4 editor de pipeline master-detail | L | El más caro de los estéticos |
| 13 | A5 / A7 / A8 / A9 | M c/u | Según demanda de campo |

**Sugerencia de secuencia**: 1 + 5 + 8 como primer lote (una tarde, todo de bajo riesgo),
luego 2 + 3 + 4 como release temática de «separación de documentos y launcher», dejando
9 para cuando haya presión real de operador.

---

*Análisis generado el 2026-07-27 contra FlexibarNET10 @ `5f80686` (v1.11.0).*
