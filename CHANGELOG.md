# 📋 Changelog

Todos los cambios relevantes de DocScan Studio están documentados en este fichero.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/).

---

## [Unreleased]

### 🧹 Retirado

- **Pipeline Assistant**: el asistente de IA por aplicación (`pipeline_assistant.py`,
  su panel, el asistente de eventos y su worker) se añadió en marzo pero nunca se
  conectó a la interfaz. Se retira el código y sus 30 tests; crear y modificar
  aplicaciones con IA sigue disponible en el **AI Mode** del launcher.

### 🏷️ Autoría

- DocScan Studio figura como **desarrollado por Nicolás Barceló**: README, «Acerca
  de», pantalla de inicio, editor del instalador de Windows y pie del manual web.
- Nuevos identificadores de la aplicación: `dev.nicolasbarcelo.docscan` (AppImage) y
  `nicolasbarcelo.docscan.studio` (AppUserModelID de Windows; un acceso anclado a la
  barra de tareas con el identificador anterior puede tener que volver a anclarse). El
  `AppId` del instalador no cambia, así que se actualiza sobre la instalación existente.
- En la versión web archivada, el tenant especial del superadmin pasa a llamarse
  «Plataforma» (slug `plataforma`).

### 🐛 Corregido

Errores de código que destapó el repaso del manual web (2026-10-27):

- **`http` ya no vale `None` en los scripts**: es un `httpx.Client` compartido
  (20 s por petición, 10 s para conectar, sigue redirecciones), en el Workbench,
  el worker desatendido, el modo directo, `init_global` y la prueba del pipeline
  del Configurador. Se cierra al cerrar la aplicación.
- **`on_key_event` se dispara**: `keyPressEvent` llamaba a `.decode()` sobre el
  nombre de la tecla, que en PySide6 ya es `str`, y el `AttributeError` impedía
  que el evento llegara a ejecutarse.
- **El tiempo máximo de los pasos Script se puede configurar**:
  `pipeline.script_timeout_seconds` (variable de entorno
  `DOCSCAN_PIPELINE__SCRIPT_TIMEOUT_SECONDS`, 30 s por defecto) no se leía en
  ningún sitio.
- **`AppContext.pipeline_steps` lleva los pasos del pipeline** en vez de ir
  siempre vacío. Además el worker y el modo directo pasan ahora a los scripts el
  `AppContext` completo, igual que el Workbench (antes solo `id`, `name` y
  `description`).
- **Paso Barcode**: el aviso «Solo la lee el motor 2 (zxing-cpp)» sale también en
  PDF417 y DataMatrix, que pyzbar tampoco decodifica, y el mapa de simbologías del
  motor 1 ya no las lista. Un paso `motor1` que solo pide simbologías que zbar no
  lee no encuentra nada; antes el filtro quedaba vacío y leía todas.
- Tildes en las etiquetas «Confirmar eliminación» y «Nueva conversación».

### 📚 Documentación

- **README bilingüe**: `README.md` en inglés (el que muestra GitHub) y
  `README.es.md` en castellano, con el mismo contenido. Puestos al día con la
  v0.1.8: instalación desde los instaladores, separador de documento,
  transferencia por documento, Configurador, atajos reales (los antiguos `Ctrl+S`,
  `R` y `M` ya no existían), formatos, métricas medidas y hoja de ruta.
- **Capturas nuevas**: los datos de demostración usan el separador nativo y la
  transferencia por documento con nombre por script, en lugar del script antiguo
  que ponía `role="separator"`.
- `docs/portfolio/metricas.md`: las cifras de la v0.1.8 y cómo se midió cada una.
- **Manual web repasado contra el código**, página a página. Lo principal:
  instalación con los instaladores (sin `alembic upgrade head`, que sobraba), 24
  operaciones de imagen, simbologías por motor (pyzbar no lee PDF417 ni
  DataMatrix), estados reales del gestor de lotes, opciones de transferencia
  (PDF, CSV, imágenes de salida, Group4 solo para B/N), atajos que faltaban
  (`Ctrl+M` excluye la página), glosario de documento y separador, dónde corre
  cada evento, panel de verificación y la versión web marcada como archivada.
  Quita el *Pipeline Assistant* del manual: su panel existe en el código pero
  nunca se ha conectado a la interfaz.
- **Informe del proyecto** (`docs/INFORME_PROYECTO.md`) puesto al día con la v0.1.8
  (versión 1.2 del documento). Corrige afirmaciones que ya no eran ciertas: pasos
  de IA, de condición y de petición HTTP que no existen, modo supervisor con
  contraseña, email SMTP en las notificaciones y el estado «en producción».
- **Retirado el manual en Word** (`docs/manual_docscan_studio.docx`, de marzo) y su
  generador `docs/generate_manual.py`: el manual que se mantiene es el web
  (<https://ferreret.github.io/docscan/>). Sale `python-docx` de
  `requirements-dev.txt`.

## [0.1.8] - 2026-10-27

Lote 6 de mejoras desde FlexibarNET 10: **separador de documento nativo**, con
la misma lógica que FlexibarNET 10. El caso de aceptación son las seis Apps de
archivo del Hospital Arnau de Vilanova, portadas de Flexibar. Incluye además el
Configurador revisado frente a Flexibar (editor de scripts con colores, Eventos
en lista, campos de lote en maestro-detalle) y los grupos de aplicaciones en el
launcher.

> **Cambios de comportamiento a revisar antes de actualizar**
> - «Incluir simbología en regex» del paso Barcode antepone ahora el número
>   legacy de la simbología (Code128 = `02`, ITF = `10`), como Flexibar. Antes
>   anteponía las dos primeras letras del nombre («Co»). Una regex escrita para
>   ese prefijo deja de casar.
> - Las páginas con un barcode `role="separator"` (puesto por script) pasan a
>   estar marcadas como separador al migrar. El rol se sigue respetando, pero ya
>   no es lo que manda.
> - En el worker desatendido, un lote cuya validación bloquea la transferencia
>   pasa a `error_export` y se notifica. Antes se quedaba en `ready_to_export`
>   con un aviso en el log que nadie veía.

### ✨ Separador de documento

- **El separador es una propiedad de la página** (`is_separator` y
  `separator_value`) y el **documento** es el tramo hasta el siguiente
  separador. Se calcula al vuelo y no se guarda. Las páginas anteriores al
  primer separador forman un documento implícito. La migración `d3f8a1c6e2b7`
  solo añade columnas.
- **Detección automática en el paso Barcode**, con las mismas claves que
  Flexibar (`separator_enabled`, `separator_by`, `separator_regex`…). Admite
  regex (opcionalmente sobre «NN + valor»), simbología o valor fijo. Es
  autoritativa: al reprocesar pisa la marca manual. Con varios pasos, la
  página es separador si casa cualquiera; en Flexibar el último pisaba al
  anterior. Un ScriptStep posterior puede cambiar `page.is_separator`.
- **Marca manual en el Workbench**: botón en la barra del visor y **Ctrl+D**.
  El diálogo propone el código que cumple la condición (o el primero de la
  página, o el valor por defecto) y lo valida en vivo contra la regex manual
  del paso. Desmarcar no toca los barcodes.
- **Zona «Separador de documento»** en el panel derecho, con el valor, el
  documento y «Editar valor». La miniatura y el visor de una página separadora
  van en naranja.
- **Reordenar páginas** con **Alt+↑ / Alt+↓**: la página viaja con su marca y
  los documentos se recalculan.

### ✨ Transferencia por documento

- **Modo TIFF multipágina** (`tiff`), además de PDF y PDF/A.
- **Un fichero por lote o por documento** (`grouping`).
- **La página separadora es portada o se descarta** (`separator_page`). Con
  hojas separadoras se bloquea la transferencia si un documento queda vacío o
  hay páginas antes de la primera hoja.
- **Tokens `{separator}`, `{document_index}` y `{document_id}`**, resueltos
  sobre el documento de cada página. En Flexibar, `{separator}` salía vacío en
  las páginas que no eran la separadora y `{document_id}` siempre vacío.
- **Nombre por script** (`name_mode` / `file_name_script`, claves de Flexibar):
  `def file_name(page, document, batch, app)` devuelve la subruta sin
  extensión. `None` usa el patrón. Si el script lanza, la transferencia no se
  hace; Flexibar caía en silencio al patrón.
- **Los nombres se calculan antes de escribir nada**: un script de nombre que
  falla o un documento sin valor con `{separator}` no dejan salida a medias.
  Los PDF y TIFF se escriben en un temporal y se renombran.
- Con la colisión **Fusionar**, un documento cuyo fichero ya existe se añade al
  final, también entre lotes.
- **Un `ValueError` en `on_transfer_validate` es un rechazo**, no un fallo: el
  operador ve solo su mensaje y el log lo registra como aviso, sin traza. Otra
  excepción sigue siendo un fallo del script, con traza.
- `on_transfer_validate` recibe `pages` y `documents`, y `on_transfer_advanced`
  también `documents`. Sus páginas traen `barcodes`, `is_separator` y
  `separator_value`. Son parámetros opcionales: las firmas anteriores siguen
  funcionando.

### 🎨 Configurador

- **El script de nombre de fichero se puede editar en VS Code**, con el botón
  «Abrir en VS Code» como en Eventos y en los pasos Script. El fichero lleva
  los tipos de `page` y `document` para el autocompletado, y los eventos de
  transferencia, los de `pages` y `documents`.
- **Editor de scripts con colores, números de línea y sangría automática** en
  los eventos, los pasos Script, el script de nombre y las vistas previas de
  los asistentes. Antes los scripts salían en la fuente proporcional del tema:
  el QSS pisaba la monoespaciada.
- **La pestaña Transferencia tiene scroll** y el nombre de los ficheros
  (patrón o script) va en su propio grupo. Con el script de nombre, la pestaña
  no cabía y Qt aplastaba los controles unos sobre otros.
- **Eventos como en FlexibarNET 10**: lista con punto de estado (vacío,
  ACTIVO, PAUSADO), nombre legible y nombre canónico en monoespaciada, en
  lugar del desplegable. El detalle muestra el resumen del código y **Editar
  script…** abre el editor con el panel de variables disponibles del evento.
  La pestaña se abre en el primer evento con código.
- **Casilla «Activado» por evento**: un evento pausado guarda
  `{"script": …, "enabled": false}` en `events_json` y no se compila, así que
  no corre en el Workbench, el worker desatendido ni `transfer_flow`. Los
  eventos activados se siguen guardando como texto. Todos los lectores de
  `events_json` pasan por `app/services/event_config.py`; el Workbench y el
  panel de verificación ya no fallan con la forma `{"script": …}`, que el worker
  aceptaba desde siempre.
- **Editor del paso Barcode por secciones**, como Flexibar: simbologías con
  casillas por familia (1D lineal, EAN/UPC, 2D) en lugar de texto libre;
  Lectura, Imagen (región de escaneo), Filtrado y Avanzado (JSON del paso). El
  separador va en dos bloques, *Detección automática* y *Marca manual*, y la
  leyenda de números de simbología se ve bajo la regex en lugar de en un
  tooltip. Los nombres de simbología que el editor no conoce se conservan.
- **Campos de lote en maestro-detalle**, como Flexibar, con **descripción** y
  **valor por defecto** por campo. El valor por defecto se propone al abrir un
  lote nuevo en el Workbench.
- **Opciones nuevas en General**, de FlexibarNET 10: *Mostrar el diálogo del
  escáner al capturar* (`ShowScannerUi`), como valor por defecto de la casilla
  de ⚙, y *Color del icono* (`IconAccent`), que fija el color de la tarjeta en
  el launcher. Migración `e2c7b9a4f160`, solo `ADD COLUMN`. Las dos viajan en
  la exportación.
- Un backend de escáner de otra plataforma (`twain` abierto en Linux) se
  conserva al guardar; antes se cambiaba al primero de la lista.
- **Grupo (launcher)** en General (`App.Group` de FlexibarNET 10): combo
  editable con los grupos ya usados; vacío = sin grupo. Migración
  `f3a8c1d72b95`, solo `ADD COLUMN`. Viaja en la exportación y en el clon.

### 🏠 Launcher

- **Grupos de aplicaciones** con cabecera plegable, como FlexibarNET 10: las
  aplicaciones sin grupo van primero y sin cabecera, y los grupos después, por
  orden alfabético, con el número de aplicaciones. El plegado se recuerda por
  equipo y la búsqueda cuenta lo encontrado en cada grupo.
- La lista de pasos indica la condición de separador del paso Barcode.
- **Group4 solo para páginas en blanco y negro**, como el ExportConfig de
  FlexibarNET 10: un TIFF con alguna página en gris o color va en LZW y no se
  binariza.

### 🐛 Corregido

- Guardar la pestaña Campos de lote ya no descarta las claves de cada campo
  que la pestaña no editaba (rehacía cada campo con `label`, `type`,
  `required` y `config`).

- **Borrar una página y capturar otra sobrescribía una imagen.** El índice de
  la página nueva salía del número de páginas, así que repetía el de la
  última y su fichero `page_NNNN` pisaba al de esa página. Además, el hueco
  hacía que el resultado del pipeline se guardara en otra página. Ahora se
  renumera al borrar y nunca se reutiliza un nombre de fichero.
- **Ninguna causa previsible deja la transferencia a medias**: una imagen que
  falta o una ruta no válida se detectan antes de escribir. Antes, con
  «Fusionar», el reintento anexaba otra vez las páginas ya archivadas. Un lote
  sin páginas ya no se da por transferido.
- **Un error del escáner dejaba el reconocimiento esperando para siempre**, y
  con él bloqueados reordenar y cerrar el lote.
- **La detección de blancos ya no excluye una página separadora** ni una con
  códigos: fundía dos documentos sin avisar.
- Los botones de los diálogos desactivados se pintaban igual que activos.
- La esquina de redimensionar de las barras de estado dejaba un cuadrado de
  otro color al final de la barra.
- **La fila seleccionada de las listas no se leía en el tema claro**: el texto
  salía en el blanco de selección del sistema sobre un fondo azul claro. En la
  lista de pestañas del Workbench, además, la casilla montaba sobre el borde
  de la fila.
- El log de la transferencia nombra el fichero final y no el temporal
  (`.nombre.tif.tmp`).
- Tras una migración lanzada con la CLI de Alembic, el proceso dejaba de
  registrar nada: `fileConfig` desactivaba los loggers ya creados.
- **Guardar en TIFF Group4 tumbaba la aplicación** (segfault de libtiff) si la
  imagen no era de 1 bit, por ejemplo una captura en B/N guardada en escala de
  grises. Ahora una página B/N se pasa a 1 bit y una en gris o color va en LZW.
- **Los scripts de transferencia del worker desatendido no veían los campos
  del lote**: un script que leyera la fecha del lote recibía siempre la de hoy.
- **El modo directo** (`--direct-mode`) transfiere por el mismo camino que el
  Workbench y el worker, con el script de nombre. Antes transfería también
  las páginas excluidas.
- Un campo de lote que se llamara como una variable del sistema (`batch_id`,
  `page_index`…) hacía fallar el nombre del fichero.

### 🧰 Herramientas

- `tools/seed_apps_arnau.py` siembra las seis Apps de archivo del Arnau
  (01, 02, 03, 05, 06 y 07), exporta sus packs y genera páginas de prueba con
  códigos reales. Las dos de control eCAP (04 y 08) quedan para después.
  Las seis van al grupo «Hospital Arnau de Vilanova», como en Flexibar.
- `tests/test_arnau_e2e.py` pasa esas Apps por el worker real de extremo a
  extremo, con lectura real de códigos.
- El campo de lote «Data» de las Apps del Arnau lleva la descripción de
  Flexibar («Data del lot (dd/MM/yyyy). Buida = avui.»).
- `tools/ui_snapshots.py` captura también el diálogo *Editar script* de un
  evento (`dialog_event_script`).

## [0.1.7] - 2026-10-27

Dos bloques: el lote 3 de mejoras desde FlexibarNET 10 y el rediseño visual con la
estética de FlexibarNET 10 (ver «Interfaz»). Incluye además el arreglo de las
migraciones que borraban datos en SQLite, presente en v0.1.5 y v0.1.6.

> **Actualizar desde v0.1.5 o v0.1.6 es urgente si hay datos reales**: esas
> versiones podían vaciar lotes, páginas y barcodes al migrar una base de datos
> antigua (ver «Corregido»).

Lote 3 de mejoras desde FlexibarNET 10: **nada falla en silencio**. La mayoría son
errores que se trataban como si todo hubiera ido bien, o que solo quedaban en el log.
Ahora el programa se detiene y lo dice, con la misma lógica que FlexibarNET 10
(v1.20, v1.26 y v1.27).

> **Cambios de comportamiento a revisar antes de actualizar**
> - Un `on_transfer_advanced` que lanza una excepción o devuelve `False` hace fallar
>   la transferencia y el lote no se marca como exportado. Si el script escribe en
>   un sistema externo, debe poder repetirse sin duplicar registros.
> - `on_transfer_advanced` corre ahora **después** de la transferencia simple, en el
>   Workbench igual que en el worker desatendido, y recibe `pages` y `result`.
> - Un `on_transfer_validate` que lanza una excepción cancela la transferencia.
> - Un campo de lote marcado como obligatorio y vacío bloquea la transferencia.
> - Un ScriptStep que falla, o un paso cuyo motor de barcode/OCR no está
>   disponible, deja la página «a revisión» con el motivo.
> - El Configurador no guarda una App si algún script no compila.
> - El actualizador rechaza una descarga sin checksum publicado.

### 🛡️ Seguridad

- **Un código de barras ya no puede sacar la transferencia de la carpeta de
  destino.** Con el patrón `{first_barcode}`, un código que empezara por `/` escribía
  en esa ruta absoluta. Ahora los valores interpolados (barcodes y campos) se sanean
  antes de usarlos: sus barras pasan a `_`, los caracteres no válidos y los nombres
  reservados de Windows (`CON`, `NUL`…) se neutralizan y cada segmento se limita a
  200 caracteres. Además, toda ruta final se comprueba contra la carpeta de destino.
- **El actualizador falla cerrado**: una descarga sin checksum ya no se da por buena.
  Las releases publican siempre `SHA256SUMS.txt`.
- **Las carpetas de datos y de configuración quedan solo para el usuario** (0700 en
  Linux). Con el umask por defecto, otras cuentas del equipo podían leer las
  imágenes de los lotes.

### 🐛 Corregido

- **Las migraciones ya no borran datos en SQLite.** `batch_alter_table` recrea la
  tabla con `DROP TABLE`, y con `PRAGMA foreign_keys=ON` ese borrado propagaba los
  `ON DELETE CASCADE`: al migrar una base de datos anterior a `e5b7c3d94f10`, se
  vaciaban `batches`, `pages` y `barcodes` sin aviso. Como la aplicación migra sola
  al arrancar desde v0.1.5, afectaba a cualquier instalación con una base de datos
  antigua. `alembic/env.py` desactiva ahora las claves foráneas durante la
  migración y las reactiva aunque falle.
- **`pywin32` sube a 311**: la 310 no tiene wheel para Python 3.14 y hacía abortar
  `pip install -r requirements.txt` entero en Windows.

- **Icono de DocScan en Linux con Wayland.** El escritorio ignora el icono que
  pone la aplicación y lo busca en el `.desktop` cuyo nombre coincide con el
  identificador de la ventana, que era el del intérprete de Python: salía un icono
  genérico. La aplicación se declara ahora como `docscan`, el nombre del
  `.desktop` del AppImage. Para ejecutar desde el código,
  `tools/install_desktop_entry.py` instala (o quita, con `--uninstall`) esa
  entrada en `~/.local/share/applications`.

- **Arrastrar un paso del pipeline ya cambia su orden.** La lista lo movía, pero el
  orden guardado seguía siendo el anterior: el cambio se perdía al guardar.
- **Las imágenes del tema ya no dependen del directorio de trabajo.** Las flechas de
  los campos numéricos se cargaban con una ruta relativa
  (`resources/icons/…`), que solo funcionaba arrancando desde la carpeta del
  programa. Ahora el tema usa la ruta absoluta (`$icons_dir`).

- **Un script de transferencia que falla ya no da la transferencia por hecha.**
  `on_transfer_advanced` podía lanzar una excepción, incluida la de la firma que
  enseñaba el asistente, y el lote se marcaba como exportado igualmente. En el worker
  desatendido, además, el script se ejecutaba después de marcar el lote.
- **La validación previa falla cerrada**: una excepción en `on_transfer_validate`
  dejaba pasar la transferencia.
- **Los campos de lote obligatorios bloquean la transferencia**, nombrando los que
  faltan. Hasta ahora el asterisco era decorativo.
- **El Workbench y el worker desatendido transfieren igual.** Los dos usan ahora el
  mismo flujo (`app/services/transfer_flow.py`). El worker ignoraba la transferencia
  simple desactivada, exigía carpeta de destino aunque la App solo transfiriera por
  script y dejaba `{first_barcode}` vacío.
- **Un script de pipeline que falla ya no es invisible**: si lanza, no compila o no
  define su función, la página queda «a revisión» con el motivo y el error en
  `script_errors`. Un script que no compila se intenta compilar una sola vez, no en
  cada página.
- **«Motor no disponible» ya no equivale a «página sin código».** Si falta pyzbar,
  libzbar, zxing-cpp o el motor OCR, el paso falla y la página queda «a revisión», en
  lugar de guardar un resultado vacío.
- **El Configurador no guarda una App con scripts que no compilan** (pasos del
  pipeline, eventos y panel de verificación): enumera el script y la línea.
- **Duplicar una App ya no pierde la configuración de notificaciones.** El clon copia
  ahora la misma lista de campos que la exportación, y un test impide que una columna
  nueva quede fuera de las dos.
- **El texto OCR de la página se ve en el Workbench** (pestaña OCR). La función que
  debía mostrarlo era un stub vacío.
- **Se respeta la pestaña inicial configurada** (`default_tab`). Antes se abría
  siempre la primera.
- **Duplicar una App desde el modo IA ya no pierde configuración**: enumeraba los
  campos a mano y se dejaba las notificaciones. Ahora usa la misma copia que el
  launcher.
- **Las excepciones no capturadas quedan en el log con su traza**, también las de los
  slots de Qt y los hilos. En el binario sin consola se perdían.
- **El worker desatendido y el modo directo leen barcodes.** No recibían el servicio
  de barcodes (el worker tampoco el de OCR) y saltaban esos pasos con un aviso en el
  log. Ahora un paso sin su servicio falla y deja la página «a revisión».
- **El worker guarda los barcodes que lee.** No los persistía: el lote quedaba sin
  rastro de lo leído y la transferencia, con `{first_barcode}` vacío.
- **`on_transfer_validate` ve los campos de lote actuales.** El Workbench guardaba
  los campos del panel después de validar, así que el script decidía con el valor del
  intento anterior.
- **El log registra versión, ejecutable y plataforma en cada arranque.**
- El patrón de nombre ya no escribe en el log el valor del barcode ni de los campos
  al fallar la interpolación: solo los nombres de las variables.

### 🎨 Interfaz

- **Panel derecho del Workbench como el de FlexibarNET 10.**
  - Arriba, «BARCODES DE LA PÁGINA · N» como lista de filas: punto de color,
    valor en monoespaciada, «simbología · motor · rol», distintivo MANUAL y
    papelera por fila. Crece hasta 280 px.
  - Debajo, «CAMPOS DE LOTE · N» como panel, hasta 180 px; antes era una
    pestaña.
  - Al fondo, las pestañas Verificación / OCR / Log.
  - Los dos paneles se pliegan.
  - La fila y su recuadro en el visor se resaltan mutuamente al pasar el ratón.
  - Atajos: **Ctrl+N** / **Insert** para añadir, **Supr** sobre la fila para
    borrar sin confirmación y **Ctrl+Z** para deshacer.
- **Pestañas del Workbench configurables por aplicación** (Configurador → General):
  - mostrar u ocultar cada panel y cada pestaña;
  - reordenar las pestañas;
  - ocultar «+ Añadir» junto con sus atajos.

  Lo guardan las columnas nuevas `workbench_layout_json` y
  `hide_add_barcode_button`. La migración `b4e2a7c9d1f3` las añade con
  `ADD COLUMN`, sin recrear la tabla, y se probó sobre una copia de una base de
  datos real con los recuentos intactos. Las dos viajan en la exportación.
- **Barra superior del Workbench como la de FlexibarNET 10.**
  - **Escanear** (botón primario, F5), **⚙** con el escáner y un distintivo
    «Escáner: …», **Importar…** (Ctrl+I), **Procesar** (F9), **Transferir** con
    contorno verde y **Cerrar lote** con contorno rojo, todos con icono.
  - Fuera los radio buttons Escáner/Importar, el combo de origen y el botón
    «Escanear / Importar»: escanear e importar son botones propios.
  - El escáner, la fuente (Flatbed/ADF) y «Mostrar las opciones del escáner al
    capturar» pasan al panel de ⚙, con ↻ para volver a buscar escáneres.
  - La lista de escáneres ya no se busca al abrir el Workbench (en SANE tarda
    segundos), sino al abrir ⚙ o al escanear sin escáner elegido. El elegido se
    recuerda por aplicación, como antes.
  - **Procesar es nuevo**: pasa el pipeline por todas las páginas del lote y
    termina por el mismo camino que una captura, como en Flexibar.
  - Mientras corre el pipeline, Escanear, Importar y Procesar se deshabilitan, y
    sus atajos tampoco actúan.
  - **Cambia un atajo:** F5 escanea (antes escaneaba o importaba según el radio).
    Ctrl+W sigue cerrando el lote.
- **Tarjetas del launcher como las de FlexibarNET 10.**
  - Cada aplicación lleva un **icono sobre un color**, deducidos de su
    configuración: barcodes → OCR → salida PDF → escáner elegido en el
    Workbench → documento. El color
    sale del nombre con el mismo hash que Flexibar (FNV-1a), así que una
    aplicación con el mismo nombre tiene el mismo color en los dos productos.
  - Hasta **tres etiquetas** automáticas: «Códigos de barras», «OCR», «Scripts» y
    el formato de salida («PDF», «PDF/A», «TIFF», «CSV»…), o «Digitalización».
  - Fecha de la última modificación (dd/mm/aaaa) y botón **⋮** con Abrir,
    Configurar, Clonar, Exportar y Eliminar. El botón derecho abre el mismo menú.
  - Las tarjetas crecen con el tamaño de letra (A+/A−).
  - Desaparece la línea de información bajo la lista: la tarjeta ya lo dice todo.
- **Barra de estado del launcher**: «N aplicación(es)» a la izquierda, que ya no
  desaparece a los 3 segundos, y «● Listo» a la derecha.
- **Barra de estado del Workbench**: tamaño y DPI de la página del visor
  («1240×1754 — 300 DPI»), barra de progreso fina de 120×3 px en verde y, al
  terminar, «Procesado N/M (k errores)» en lugar de «Procesamiento completado».
- **Lista de pasos del Configurador como la de Flexibar**: cada paso tiene una
  **casilla real** de activo, el **icono de su tipo** con su color (imagen, barcode,
  OCR, script) y su nombre. Un paso desactivado se ve atenuado. Desaparecen el
  botón «On/Off» y la marca de texto `[✓]`/`[✗]`, y subir/bajar llevan icono.
- **El campo de fecha lleva un icono de calendario**, como el DatePicker de
  Flexibar. Antes el desplegable era un cuadrado con borde que parecía una casilla.
- **Las casillas marcadas llevan tic.** Antes eran un cuadrado relleno sin marca.
  También lo llevan las de la lista «Pestañas del Workbench».
- **Los desplegables vuelven a tener flecha.** El estilo del tema quitaba la nativa
  sin poner otra, y parecían campos de texto. El de idioma del launcher es un poco
  más ancho para que quepan el código y la flecha.
- **La versión se ve en el título del launcher**: en la barra de la ventana
  («DocScan Studio v0.1.7», como el «FlexibarNET v1.30» de Flexibar) y junto al
  encabezado.
- **Contadores del lote en la barra de estado** (páginas, con barcode, separadores y
  a revisión), como el «Procesado 5/5» de Flexibar. Antes ocupaban el panel derecho.
- **Al abrir una página a revisión, la barra de estado dice por qué** y cuántos
  errores de procesado tiene.

- **Paleta de FlexibarNET 10**: navy profundo en el tema oscuro y el claro de
  Flexibar en el claro. Hay una única fuente de color (`app/ui/palette.py`) y una
  sola plantilla de estilos (`resources/styles/theme.qss`, con tokens) para los dos
  temas, en lugar de dos QSS copiados. Los colores de estado de página, del log y
  del gestor de lotes salen de la paleta y cambian con el tema: el texto INFO del
  log ya se lee en el tema claro.
- **La miniatura de la página que se ve en el visor se distingue claramente**:
  lleva un marco macizo del color de acento por dentro del borde de estado (que
  conserva su color: rojo a revisión, naranja separador…). Antes solo tenía 1 px
  más de borde y un fondo casi transparente. Además, cambiar el estado de la página
  seleccionada ya no le quita el resaltado.
- **Iconos Lucide** (ISC, `resources/icons/lucide`, paquete `lucide-static` 1.55.0
  verificado por su hash SHA-512): un único juego de trazo fino, recoloreado con la
  paleta del tema (`app/ui/icons.py`). Sustituye a los ~30 iconos dibujados a mano en
  la barra lateral, la barra superior y la barra del visor. La barra del visor tiene
  ahora botones planos y monocromos, con el rojo reservado para borrar, y el contador
  de página a tamaño normal en lugar de 36 px en rosa, ajustado a su texto y
  centrado entre las flechas (antes un campo de ancho fijo dejaba un hueco a la
  izquierda del número).
- **Tipografía Inter** empaquetada (OFL, `resources/fonts/inter`) y registrada al
  arrancar. En Windows se usa «Segoe UI», como Flexibar. Antes se pedía «Segoe UI»
  también en Linux y se caía en la fuente que hubiera.
- **La barra de herramientas del visor ya no tapa la página.** Antes flotaba sobre la
  parte inferior de la imagen y ocultaba lo que hubiera allí (a menudo, el código de
  barras). Ahora ocupa su propia franja bajo el visor, como en FlexibarNET 10.

### 📚 Documentación

- La tabla de atajos (`docs-web/reference/shortcuts.md`) se rehízo contra el código:
  decía `Ctrl+S`, `R` y `M`, que no existen (son `F5`, `Ctrl+R` y `Ctrl+M`).
- **Capturas regeneradas** con la interfaz nueva: las 15 de `docs/screenshots/` y
  `docs-web/assets/screenshots/`. Los lotes de la demo usan una estación neutra
  (`PUESTO-01`) en lugar del nombre del equipo en el que se generan.
- Las aplicaciones de demostración de `tools/ui_snapshots.py` tienen ahora configuraciones
  distintas, para que la captura del launcher enseñe iconos y etiquetas variados.
- **`tools/ui_snapshots.py`** regenera con un comando las 15 capturas de la
  documentación (`docs/screenshots/` y `docs-web/assets/screenshots/`) y, si se
  pide, la imagen del portfolio. Abre las ventanas reales sin mostrarlas, con datos
  de demostración ficticios y neutros, en un entorno aislado: no toca los datos ni
  las preferencias del usuario y no se conecta a la red. Su primera ejecución
  destapó que la pestaña General del Configurador ya no cabía y aplastaba los
  campos. Ahora tiene scroll.
- Firmas reales de todos los eventos en la plantilla del Configurador, los asistentes
  de IA, los stubs del editor externo, el README y docs-web, más la receta «Un PDF por
  documento» (hojas separadoras).

## [0.1.6] - 2026-07-28

### ✨ Salto directo a página en el visor

- El contador `N / M` de la barra flotante del visor **es editable**: clic, teclear
  el número y pulsar Intro lleva a esa página. Pensado para lotes largos, donde
  llegar a la página 427 de 600 a golpe de flecha no es viable. Escape o hacer clic
  fuera cancelan y restauran el valor. Los números fuera de rango se ignoran.
- Mientras se escribe en el contador, los atajos de tecla simple (flechas,
  Inicio/Fin y **Supr**) quedan desactivados: de lo contrario el atajo de ventana
  tiene prioridad sobre el campo de texto y `Supr` borraría una página en lugar de
  un dígito.

### ✨ Las operaciones de imagen pueden alterar el documento entregado

- Nueva casilla **«Guardar el resultado en el fichero de la página»** en el paso de
  operación de imagen. Hasta ahora las ImageOps solo afectaban a la imagen que
  circula por el pipeline —preparación para leer barcodes u OCR— y el fichero que
  se archivaba y transfería conservaba el original del escáneo. Eso es razonable
  para `FxGrayscale` o `ConvertTo1Bpp`, pero no para `AutoDeskew`,
  `CropWhiteBorders`, `Rotate` o `RemoveHolePunch`, donde el operador da por hecho
  que el documento sale enderezado y recortado. La única alternativa era escribir
  un script con `pipeline.replace_image()`.
- **Desactivada por defecto**: las aplicaciones existentes se comportan
  exactamente igual y no hay migración que aplicar.
- La casilla guarda una **instantánea de ese paso**, no el estado final del
  pipeline: se puede enderezar y archivar, y binarizar después solo para leer.
- El **worker desatendido** también persiste ahora la imagen procesada. Antes no
  lo hacía en ningún caso, así que el mismo pipeline transfería imágenes
  distintas según se ejecutara desde el workbench o sin supervisión.

### 🐛 Correcciones de robustez

- **La caché de scripts se indexa por contenido, no por identificador de paso.**
  Antes, editar un script podía seguir ejecutando la versión anterior si el motor
  sobrevivía al guardado, porque la entrada de caché se buscaba por `step.id`.
  Ahora la clave es el hash del código fuente y una edición se detecta sola; las
  versiones ya compiladas se reutilizan sin recompilar.
- **Los identificadores de paso se sanean al cargar el pipeline.** Un id vacío,
  ausente o duplicado rompía de forma difusa todo lo que indexa por id (caché de
  scripts, `skip_step`, `skip_to`, el límite de `repeat_step`). Ahora se regeneran
  al deserializar, dejando aviso en el log, en lugar de fallar más tarde y lejos de
  la causa.
- **Escritura atómica** (temporal + `rename`) del almacén cifrado de credenciales,
  de su clave y de los ficheros de exportación de aplicaciones. Un cierre a
  destiempo ya no puede dejar un `secrets.enc` truncado —y por tanto ilegible por
  completo— ni un pack de aplicación a medias.
- **Los ficheros de un lote se borran solo después de que la base de datos confirme
  la eliminación.** Al eliminar lotes o páginas, el borrado en disco se difiere al
  `commit`; si la transacción se revierte, las imágenes siguen en su sitio. El
  orden anterior (borrar primero, confirmar después) destruía imágenes de forma
  irrecuperable si la base de datos rechazaba el borrado.
- **Un script colgado ya no deja sin scripting al resto del lote.** El motor
  ejecuta los scripts en un hilo con límite de tiempo, pero ese hilo no se puede
  matar: al expirar el plazo se quedaba ocupado para siempre y todas las páginas
  siguientes se encolaban detrás, agotando el timeout una a una. En un lote de 600
  páginas eran horas de esperas con el scripting muerto y sin aviso. Ahora, tras un
  timeout, el motor descarta ese hilo y sigue con uno limpio.
- **Las expresiones regulares de usuario se evalúan con límite de tiempo** (1 s,
  criterio *fail-open*), tanto en el filtro del paso de barcode como en la
  validación del barcode manual —esta última corría en el hilo de la interfaz, así
  que un patrón con *backtracking* catastrófico congelaba la ventana entera. Se
  añade la dependencia `regex`: el `re` de la biblioteca estándar no admite timeout
  y no libera el GIL mientras evalúa, de modo que ningún vigilante escrito en
  Python puede rescatarlo.
- **Cancelar deja de reportarse como terminación correcta.** `ScanWorker` anunciaba
  el total completo de páginas tras una interrupción, y `RecognitionWorker` emitía
  la misma señal de «todo procesado» que en el camino normal —la señal que marca el
  lote como leído y dispara la auto-transferencia—. Ambos emiten ahora una señal
  propia de cancelación con el recuento real. Hoy la interrupción solo ocurre al
  cerrar la ventana, así que no había daño observable; quedaba como una mina para
  el día que se añada un botón de cancelar.

## [0.1.5] - 2026-07-22

### 🐛 La app desktop aplica migraciones al arrancar

- **Corregido el crash de arranque contra una base de datos preexistente**
  (`no such column: applications.notifications_json`). La app inicializaba el
  esquema con `create_all()`, que crea tablas nuevas pero **nunca añade columnas**
  a tablas ya existentes ni aplica migraciones. Al evolucionar el modelo (p.ej. el
  webhook de v0.1.4 añadió `notifications_json`), cualquier instalación con una BD
  anterior quedaba inservible.
- Ahora el arranque aplica migraciones Alembic de forma robusta a tres estados de
  BD: **nueva** (crea el esquema desde las migraciones), **versionada** (aplica lo
  que falte) y **heredada** (creada con `create_all` sin control de versión: se
  reconcilian por reflexión las columnas ausentes del modelo y se adopta en
  Alembic). Los datos existentes se preservan.
- Migraciones internas hechas idempotentes para no romper el proceso en SQLite.
- **Nota**: quien tenga la v0.1.4 instalada y sufriera el crash queda arreglado al
  actualizar; no hay que hacer nada manualmente.

## [0.1.4] - 2026-07-22

### ⬆️ Actualización de dependencias mayores

- **opencv-python 4.13 → 5.0.0.93** (salto de versión mayor). El uso del proyecto
  es 100 % API core (`cvtColor`, `resize`, `threshold`, morfología, `warpAffine`,
  `HoughCircles`…), no afectada por los breaking de OpenCV 5 (retirada del C API
  legacy, G-API/ML movidos a `contrib`, cambios de DNN/ONNX).
- **anthropic 0.84.0 → 0.117.1**. La superficie usada (`Anthropic()`,
  `messages.create`, iteración de bloques de contenido) es estable.
- **PySide6 6.10.2 → 6.11.1**, **SQLAlchemy 2.0.48 → 2.0.51**,
  **zxing-cpp 3.0.0 → 3.1.0**, **PyMuPDF 1.27.1 → 1.28.0**,
  **openai 2.26.0 → 2.46.0**.
- Sin cambios de código: los 879 tests siguen en verde y el smoke de importación
  de servicios y clientes IA pasa. Todos los paquetes tienen _wheels_ para
  Python 3.14.

### ✨ Notificaciones webhook por aplicación

- **Webhook configurable por aplicación**: nueva pestaña «Notificaciones» en el
  configurador para definir un webhook (URL, método POST/GET, cabeceras HTTP y
  timeout) que se dispara al completar o fallar la transferencia de un lote.
  Hasta ahora el servicio de notificaciones existía pero el webhook llegaba
  siempre `None` (un `TODO` en el worker); ahora se carga de la configuración.
- Persistencia en la columna nueva `applications.notifications_json` (migración
  Alembic `c1d5e9f34b28`); la estructura JSON anidada reserva sitio para email
  SMTP en el futuro. La config viaja al exportar/importar aplicaciones.
- Email SMTP queda pendiente (requiere cifrado Fernet del password).

### 🔧 Infraestructura de tests y unificación de Python

- **Unificación en Python 3.14**: desarrollo, CI e instaladores pasan a usar
  todos Python 3.14 (antes se desarrollaba en 3.14 pero se construía en 3.13).
  Esa divergencia había causado el bug de portabilidad de `except A, B:`
  (PEP 758). Con toda la cadena en 3.14, `ruff.toml` vuelve a `target-version =
  py314` y `ruff format` normaliza los `except` a la sintaxis 3.14. CI y
  `release.yml` construyen con 3.14.
- **Suite no interactiva y sin hardware**: nuevo `tests/conftest.py` global que
  (1) mockea todos los modales de Qt para que ningún test espere un clic,
  (2) inyecta un módulo `sane` falso antes de recolectar tests —ninguna ruta
  abre el escáner USB real, se elimina el prompt de administrador (polkit) y los
  ~33 s de enumeración de hardware—, y (3) autodescarta los tests de la web
  archivada cuando faltan sus dependencias. `pytest tests/` sin flags:
  861 passing en ~24 s, cero interacción. El CI delega en el conftest en vez de
  enumerar `--ignore`.

## [0.1.3] — 2026-07-21

### 🧹 Mantenimiento y saneamiento del desktop

La versión web SaaS quedó **archivada**; el proyecto se enfoca en DocScan
Desktop. Auditoría completa en `docs/auditoria_desktop_2026-07-21.md`.

- **Fix**: `--direct-mode` estaba roto por un import inexistente (`get_scanner`
  → `create_scanner` en `main.py`). Añadidos tests de regresión del modo directo.
- **Seguridad**: actualizadas dependencias con CVEs conocidos — Pillow
  12.1.1→12.3.0, cryptography 46.0.5→48.0.1, pydantic-settings→2.14.2,
  pytest→9.0.3. `pip-audit` limpio.
- **Limpieza**: eliminado `app/providers/` (código muerto desde el borrado de
  AiStep). Barrido `ruff check --fix` + `ruff format` sobre todo el código
  desktop; añadido `ruff.toml` (primera config de lint del proyecto).
  `ruff check .` totalmente limpio.
- **Tests**: mockeado el modal `QMessageBox.warning` que colgaba la suite; y
  mockeada la capa SANE en `test_scanner_service.py` (antes hacía enumeración
  real de hardware, ~33s y capaz de colgarse). Suite completa 861/861 en ~22s.
- **CI**: nuevo workflow `.github/workflows/ci.yml` (lint + tests en push/PR) y
  `pytest.ini` con `--timeout` por defecto contra cuelgues.
- **Portabilidad Python 3.13**: 20 bloques usaban `except A, B:` sin paréntesis,
  sintaxis exclusiva de Python 3.14 (PEP 758) que rompía la importación en 3.13
  (CI e instaladores). Corregido a `except (A, B):`; `ruff.toml` fijado a
  `target-version = py313` para que `ruff format` no vuelva a quitar los
  paréntesis. Detectado por el nuevo CI.

---

### 🗄️ Histórico versión web SaaS (archivada 2026-07-21)

> Las secciones siguientes documentan la versión web SaaS, archivada. Se
> conservan como referencia; no forman parte de las releases del desktop.

#### 🛡️ Sprint Superadmin (versión web SaaS) — 2026-05-05

Plataforma multi-tenant lista para SaaS con jerarquía de roles `superadmin > company_admin > operator`. Sólo el equipo de la plataforma (rol `superadmin`) puede crear tenants y administradores; el registro público está deshabilitado.

#### ✨ Backend (`web/api/`)

- **CLI bootstrap idempotente** del primer superadmin:
  ```
  docker compose exec api python -m web.api.bootstrap superadmin \
      --email admin@example.com --password ********** \
      --display "Admin Plataforma"
  ```
  Crea (o reutiliza) el tenant especial `Plataforma` y un usuario con rol `superadmin`. Volver a ejecutarlo con el mismo email es no-op.
- **Registro público eliminado**: `POST /api/auth/register` devuelve 404. La aceptación de invitaciones (`/accept-invitation/:token`) sigue siendo el camino para usuarios añadidos por invitación.
- **Login bloqueado en tenants suspendidos**: `tenant.active=False` rechaza el login con 401 y el `/auth/me` también, aunque el JWT siga vigente.
- **Modelo `AuditLog`** + helper `web/api/audit.py::audit(...)`: registra cada mutación administrativa (`tenant.created/updated/deleted`, `user.created/updated/deleted`) con actor, target y payload JSON.
- **Endpoints `/api/admin/tenants`** (5) — superadmin sólo:
  - `GET /admin/tenants` (paginado, con stats por tenant)
  - `POST /admin/tenants` (crea tenant + primer company_admin)
  - `GET /admin/tenants/{id}` (detalle + lista de usuarios)
  - `PATCH /admin/tenants/{id}` (name | plan | active)
  - `DELETE /admin/tenants/{id}` (hard-cascade BD + storage; rechaza con 409 si hay batches `running`/`transferring` o si el tenant es Plataforma)
- **Endpoints `/api/admin/users`** (4) — superadmin sólo, cross-tenant:
  - `GET /admin/users` (filtra por `?tenant_id=`)
  - `POST /admin/users` (crea directamente en cualquier tenant)
  - `PATCH /admin/users/{id}` (role | active | display_name)
  - `DELETE /admin/users/{id}`
  - Guards: rechaza con 409 al degradar/desactivar/borrar al último superadmin global o al último company_admin activo del tenant. Self-modify desde aquí también devuelve 409 (defense-in-depth).

#### ✨ Frontend (`web/frontend/`)

- **Store Pinia `admin.ts`** + tipos TypeScript que reflejan los schemas (`Tenant`, `TenantStats`, `TenantDetail`, `AdminUserListItem`, etc.).
- **Rutas `/admin/tenants`, `/admin/tenants/new`, `/admin/tenants/:id`** con `meta.superadmin: true`.
- **Guard global `enforceRoleAccess`** en el router:
  - `superadmin` en una ruta no `/admin/*` → redirige a `/admin/tenants`.
  - cualquier rol distinto de `superadmin` accediendo a `/admin/*` → redirige a `/`.
- **AppLayout dual**: sidebar reducido a "Tenants" + header "Plataforma · Administración" cuando el rol es `superadmin`. Sidebar normal para `company_admin`/`operator`.
- **Vista de listado**: tabla con stats por tenant, badge coloreado por plan, toggle Activo/Suspendido inline, eliminar con confirmación del nombre exacto.
- **Vista de creación**: formulario tenant + primer admin con validación local de password (≥8 caracteres) y feedback de errores 409 (email duplicado, plan inválido).
- **Vista de detalle**: edita name/plan/active del tenant + CRUD completo de sus usuarios (cambio de rol, toggle activo, delete con confirm, modal "Crear usuario").

#### 🧪 Tests añadidos en el sprint

- Backend: 81 tests TDD cubren bootstrap, audit, admin_tenants, admin_users, registro retirado y tenant suspendido. Suite web: **298 passing**.
- Frontend: 49 tests TDD nuevos para store, guard de rol, AppLayout y las 3 vistas admin. Suite frontend: **460 passing**.

#### 🔍 Smoke e2e

- `scripts/smoke_superadmin.sh` — matriz curl de 21 casos contra `docker compose` (registro 404, login + me, /admin/* con 3 roles, CRUD tenants, CRUD users cross-tenant, guards 409 último-admin / self-modify, suspensión + login bloqueado, cascade delete, protección de Plataforma).
- Smoke visual con Playwright recogido en `docs/screenshots/smoke-superadmin/`: listado, formulario de creación, detalle del tenant y bloqueo del guard cuando un company_admin intenta entrar a `/admin/*`.

#### 📝 Notas de migración

- **Nueva tabla `audit_logs`**: aplicar `alembic upgrade head` (la migración `a3b8d4e2f7c9_add_audit_logs.py` se ejecuta automáticamente en el `docker-bootstrap-db.py`).
- **Sin cambios** en la app de escritorio. Esta release sólo afecta a la versión web SaaS.

---

## [0.1.2] — 2026-04-30

### 🐛 Corregido

- **Editor de Eventos del configurador**: el placeholder del editor de código estaba hardcoded a la firma de `on_app_start` y nunca cambiaba al seleccionar otro evento del combo. Ahora se actualiza dinámicamente con la firma correcta del evento elegido (`on_page_changed(app, batch, page)`, `on_key_event(app, batch, key)`, etc.) usando el catálogo `EVENT_SIGNATURES`.
- **`page.id` accesible desde `on_page_changed` en el escritorio**: el dispatcher pasaba sólo `page_index` (un entero) y un script con la firma documentada `def on_page_changed(app, batch, page)` fallaba con `missing 1 required positional argument: 'page'`. Ahora el workbench construye un `PageContext` con `id`, `page_index`, `barcodes`, `ocr_text`, `fields` y `flags`, igualando el contrato con la versión web. Los scripts antiguos con `(app, batch)` o `(app, batch, page_index)` siguen funcionando — el `ScriptEngine` filtra los kwargs por la firma de la función.

### 📝 Notas

- Sin cambios en BD ni en el formato de pipeline. Actualización in-place desde 0.1.1.

---

## [0.1.1] — 2026-04-30

### ✨ Eventos lifecycle ampliados
- **`on_batch_loaded`** y **`on_page_changed`** promocionados al catálogo del configurador (pestaña Eventos) con descripciones traducibles. Hasta ahora estos dos hooks sólo existían en la versión web; ahora también pueden definirse como scripts lifecycle convencionales en la app de escritorio, manteniendo el hook del VerificationPanel para retrocompatibilidad.
- **`page.id`** ahora accesible desde scripts lifecycle (`on_navigate_*`, `on_page_changed`, etc.). Antes el contexto sólo exponía `page_index` y `page.id` lanzaba `AttributeError`.

### 🐛 Corregido
- Warning de Qt al cerrar el launcher: `QPropertyAnimation` sobre `fixedWidth` provocaba un mensaje en consola sin efecto funcional. Limpiado.

### 📝 Notas
- Sin cambios en BD ni en el formato de pipeline. Actualización in-place desde 0.1.0.

---

## [0.1.0] — 2026-03-26

### 🚀 Distribución e instaladores
- **UI de actualización**: diálogo de descarga con barra de progreso, notas de release y verificación SHA-256
- **Banner de actualización**: notificación no invasiva en el Launcher con botones "Ver novedades", "Actualizar" e "Ignorar"
- **Botón "Buscar actualizaciones"** en el diálogo Acerca de
- **Auto-check al inicio**: comprobación de nuevas versiones en segundo plano tras arrancar
- **PyInstaller specs**: configuración de empaquetado para Linux y Windows
- **AppImage**: recipe AppImageBuilder + fichero .desktop para distribución Linux
- **Inno Setup**: script de instalador Windows con español/inglés/catalán y modo silencioso
- **CI/CD**: GitHub Actions workflow para build automático y release al crear tags `v*`
- **Informe de licenciamiento**: análisis de licencias, modelos de negocio, plataformas de venta y protección de código

### 🏗️ Infraestructura
- Rama `production` para releases estables
- Versión centralizada en `app/_version.py`
- Auto-update service con GitHub Releases API + SHA-256
- Estilos QSS para banner de actualización (tema claro y oscuro)
- 21 tests nuevos para UI de actualización (849 total)

---

## [0.1 RC] — 2026-03-26

### 📖 Documentación
- README.md completo con badges, screenshots, arquitectura, pipeline, scripting, AI Mode y roadmap
- Manual de usuario Word (.docx) con 12 capítulos y 18 figuras reales
- Documentación web MkDocs Material con 13 páginas, publicada en GitHub Pages
- 73 tooltips añadidos a 14 ficheros UI (batch manager, configurador, workbench)
- Diálogo "Acerca de" con versión, logo, stack tecnológico y copyright
- Generador de documentos clínicos de ejemplo para demos
- Auditoría de seguridad: sin API keys ni credenciales expuestas
- `.gitignore` reforzado con exclusiones de seguridad

---

## [Release 3] — 2026-03-25

### ✨ Funcionalidades
- **AI MODE**: asistente conversacional integrado en el Launcher para crear y configurar aplicaciones mediante lenguaje natural (Anthropic / OpenAI)
- **Pipeline Assistant**: asistente IA contextual por aplicación en el configurador
- **Test Pipeline** (IMG-14): ejecución del pipeline sobre imagen de muestra con resultados paso a paso
- **Export/Import** (CFG-02/03): exportar e importar aplicaciones como ficheros `.docscan` (JSON)
- **Sidebar colapsable**: panel lateral con 10 iconos vectoriales QPainter, animación de 150ms
- **Política de colisión** (TRS-05): sufijo numérico, sobreescribir o fusionar multi-página PDF/TIFF
- **Detección de páginas en blanco** (APP-05): análisis por histograma con auto-exclusión configurable
- **Splash screen**: pantalla de carga con logo, versión y progreso de inicialización

### 🚫 Descartados
- ConditionStep / HttpRequestStep — redundantes con ScriptStep + AI MODE
- Perfiles de usuario (LCH-07/BAT-05) — innecesario para mono-estación
- batch.lock (BAT-03) — foco mono-estación
- Pipeline templates (IMG-13) — cubierto por AI MODE + Export/Import

---

## [Release 2b] — 2026-03-22

### ✨ Funcionalidades
- **Panel de verificación personalizado**: widget QWidget definido por script en `verification_panel`, insertado como pestaña en el Workbench

---

## [Release 2] — 2026-03-21

### ✨ Funcionalidades
- **Internacionalización** (i18n): soporte multilenguaje para Español, English y Català con `QT_TRANSLATE_NOOP` y funciones lazy
- **Atajos de teclado**: 17 shortcuts para el Workbench (navegación, zoom, rotación, marcado, eliminación)
- **OCR estructurado**: resultados con regiones word-level y coordenadas
- **Field overlays**: visualización de regiones OCR sobre el visor de documentos
- **Compatibilidad Windows**: soporte TWAIN + WIA para escáneres, ajustes cross-platform
- **Icono de aplicación**: en títulos de ventana y barra de tareas Windows

---

## [Release 1B] — 2026-03-20

### ✨ Funcionalidades
- **ImageLib**: librería de operaciones de imagen (load, save, merge, split, DPI, color)
- **ImageConfig**: dataclass de configuración de imagen con parse/serialize
- **Pestaña Imagen**: nueva pestaña en el configurador (formato, color, compresión)
- **Mejoras de transferencia**: conversión de formato, DPI y color al exportar

### 🔧 Cambios técnicos
- Eliminación de AiStep del pipeline (absorbido por ScriptStep)
- Unificación `ai_fields` → `custom_fields` → `page.fields`
- Fix memory leak: `WA_DeleteOnClose` + `deleteLater` en ventanas secundarias
- Guard para señales tardías post-cierre de ventana
- Resume automático de pipeline al reabrir lote
- 4 migraciones Alembic aplicadas
- `requirements-dev.txt` con dependencias de desarrollo separadas

### 🐛 Correcciones
- Navegación next-barcode / next-review
- Parsing de `events_json` para string y dict
- Tamaños de ventana ampliados (configurador 950×700, workbench 1440×900)

---

## [Release 1] — 2026-03-19

### ✨ Funcionalidades

#### Infraestructura (pasos 1-5)
- Pipeline engine: steps.py, context.py, executor.py, serializer.py
- PipelineContext con control de flujo: skip_step, skip_to, abort, repeat_step
- Settings con pydantic-settings + Secrets con Fernet
- Base de datos SQLite con WAL mode obligatorio + repositorios

#### Servicios (pasos 6-11)
- **ScriptEngine**: compilación de scripts al cargar app, ejecución con timeout
- **BarcodeService**: Motor 1 (pyzbar, 12 simbologías) + Motor 2 (zxing-cpp, 14 simbologías)
- **ImagePipeline**: 23+ operaciones de imagen (deskew, crop, filtros, morfología...)
- **OcrService**: RapidOCR (primary), EasyOCR (alternative), Tesseract (fallback)
- **Proveedores IA**: Anthropic (Claude) + OpenAI (GPT-4o) con Strategy pattern
- **PipelineExecutor**: ejecución stateless con max repeat limit

#### Soporte (pasos 12-15)
- **ScannerService**: SANE (Linux) con subprocess para thread-safety
- **ImportService**: TIFF multi-página, JPEG, PNG, BMP, PDF (rasterizado con PyMuPDF)
- **BatchService**: gestión de lotes con estados y auditoría
- **TransferService**: transferencia simple a carpeta + avanzada por script
- **NotificationService**: email + webhook

#### Launcher (paso 16)
- Ventana principal con lista de aplicaciones
- Crear, editar, duplicar, eliminar aplicaciones
- Búsqueda de aplicaciones

#### Configurador (pasos 17-18)
- 6 pestañas: General, Imagen, Campos de Lote, Pipeline, Eventos, Transferencia
- Editor visual de pipeline con drag & drop
- Diálogos de edición por tipo de paso (ImageOp, Barcode, OCR, Script)
- Editor de eventos del ciclo de vida con integración VS Code

#### Workbench (paso 19)
- Panel de miniaturas con estados de color
- Visor de documentos con zoom, pan y overlays
- Panel de barcodes con tabla y contadores
- Panel de metadatos con campos dinámicos
- Panel de log en tiempo real
- Workers QThread: scan, recognition, transfer
- Drag & drop para importación

#### Batch Manager (paso 20)
- Histórico de lotes con filtros (aplicación, estación, fecha)
- Panel de detalle con estadísticas, páginas e historial
- Reabrir lotes anteriores en el Workbench
- Auto-refresco cada 20 segundos

#### Worker (paso 21)
- DocScanWorker CLI para procesamiento desatendido
- Folder watcher con watchdog

#### Tests (paso 22)
- Suite de tests con pytest + pytest-qt
- Tests de repositorios, servicios, pipeline, UI y integración

---

## Métricas del proyecto

| Métrica | Valor |
|---------|-------|
| Líneas de código (app) | 19.776 |
| Líneas de test | 11.618 |
| Ficheros fuente | 94 |
| Tests | 813 passing ✅ |
| Operaciones de imagen | 23 |
| Simbologías barcode | 14 |
| Motores OCR | 3 |
| Idiomas de interfaz | 3 |
