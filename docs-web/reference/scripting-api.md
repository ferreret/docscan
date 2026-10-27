# :material-api: API de scripting

Referencia completa de los objetos disponibles en scripts.

## Variables disponibles

Además de los argumentos de cada función, todo script (pasos Script, eventos y
script de nombre) tiene estos nombres a mano, sin importarlos:

| Nombre | Contenido |
|--------|-----------|
| `log` | Logger de la aplicación (`log.info`, `log.warning`…); va al panel Log y al fichero de log |
| `re`, `json`, `datetime` | Los módulos estándar |
| `Path` | `pathlib.Path` |
| `ImageLib` | Utilidades de imagen: `load`, `save`, `convert`, `merge_to_pdf`, `merge_to_tiff`, `split`, `get_dpi`, `resize_to_dpi`, `to_grayscale`, `to_color`, `to_bw`, `get_color_mode` |
| `http` | Cliente [`httpx.Client`](https://www.python-httpx.org/api/#client) compartido por todos los scripts de la aplicación, con 20 s de tiempo máximo por petición (10 s para conectar) y que sigue redirecciones |

```python
resp = http.post("https://api.ejemplo.com/clasificar", json={"text": page.ocr_text})
resp.raise_for_status()
```

Una petición que falla lanza la excepción de `httpx`, y se trata como cualquier
otro error del script. El cliente se cierra al cerrar la aplicación.

!!! info "Tiempo máximo"
    Un paso Script se corta a los **30 s**: el error queda en
    `page.flags.script_errors` y la página pasa a revisión. El límite se cambia
    con la variable de entorno `DOCSCAN_PIPELINE__SCRIPT_TIMEOUT_SECONDS`
    (en segundos) y vale para el Workbench, el worker desatendido y el modo
    directo. Los eventos no tienen límite.

## AppContext

| Atributo | Tipo | Descripción |
|----------|------|-------------|
| `id` | int | ID de la aplicación |
| `name` | str | Nombre de la aplicación |
| `description` | str | Descripción |
| `config` | dict | Configuración de IA |
| `batch_fields_def` | list[dict] | Definición de los campos de lote |
| `transfer_config` | dict | Configuración de transferencia |
| `pipeline_steps` | list[dict] | Pasos del pipeline, tal como se guardan (`id`, `type`, `enabled` y las opciones de cada tipo). En la prueba del pipeline del Configurador, los pasos que se están editando |
| `auto_transfer` | bool | Transferir automáticamente |
| `output_format` | str | Formato de salida |

!!! note "Contextos del worker desatendido y del modo directo"
    `app` trae los mismos atributos que en el Workbench. `batch` solo trae `id`
    y `state`; `batch.fields` se rellena justo antes de transferir, para los
    eventos de transferencia y el script de nombre.

## BatchContext

| Atributo | Tipo | Descripción |
|----------|------|-------------|
| `id` | int | ID del lote |
| `state` | str | Estado actual |
| `fields` | dict | Campos del lote (editable) |
| `page_count` | int | Número de páginas |
| `folder_path` | str | Carpeta del lote en disco |
| `hostname` | str | Equipo que creó el lote |

!!! warning "`batch` no contiene las páginas"
    No existe `batch.pages`. Las páginas llegan como argumento solo a los
    eventos que las reciben (ver [Argumentos de cada evento](#argumentos-de-cada-evento)).

## PageContext

| Atributo | Tipo | Descripción |
|----------|------|-------------|
| `id` | int | ID de la página en BD (disponible desde v0.1.1 / v0.1.2 desktop) |
| `page_index` | int | Índice 0-based dentro del lote |
| `image` | ndarray | Imagen actual (OpenCV). En `on_page_changed` vale `None` |
| `barcodes` | list[BarcodeResult] | Barcodes detectados |
| `ocr_text` | str | Texto OCR |
| `fields` | dict | Campos de indexación |
| `flags` | PageFlags | Flags de estado (ver [PageFlags](#pageflags)) |
| `ocr_regions` | list | Regiones de texto que devuelve el paso OCR |
| `is_separator` | bool | La página abre un documento (lectura y escritura) |
| `separator_value` | str | Valor que identifica el documento, `""` si no tiene (lectura y escritura) |

El paso Barcode con *Separador de documento* activo escribe `is_separator` y
`separator_value`; un ScriptStep posterior puede cambiarlos. Si el pipeline
no los toca, la página conserva la marca que ya tenía (por ejemplo, la manual).

En `on_page_changed`, `page` es una copia de lectura: lo que cambie el script
no se guarda.

## PageFlags

| Atributo | Tipo | Descripción |
|----------|------|-------------|
| `needs_review` | bool | La página queda a revisión (borde rojo en la miniatura) |
| `review_reason` | str | Motivo que ve el operador al abrir la página |
| `script_errors` | list[dict] | Errores de los pasos Script (`step_id`, `entry_point`, `error`, `type`) |
| `processing_errors` | list[str] | Errores de los demás pasos (motor no disponible, fallo de imagen…) |

Un paso Script que falla añade su error a `script_errors` y deja la página a
revisión; el pipeline sigue con el paso siguiente.

## BarcodeResult

| Atributo | Tipo | Descripción |
|----------|------|-------------|
| `value` | str | Valor del barcode |
| `symbology` | str | Tipo normalizado (`Code128`, `Code39`, `QR`, `EAN13`…) |
| `engine` | str | Motor que lo leyó: `motor1` (pyzbar), `motor2` (zxing-cpp) o `manual` |
| `step_id` | str | Paso Barcode que lo encontró |
| `quality` | float | Calidad que da el motor 1 (la de zbar, sin escala: mayor es mejor); el motor 2 siempre da `0.0` |
| `pos_x`, `pos_y`, `pos_w`, `pos_h` | int | Rectángulo en píxeles |
| `role` | str | Rol libre que asigna un script |

!!! note "El rol `separator` del barcode es el mecanismo antiguo"
    Antes del lote 6 la separadora se señalaba poniendo `role = "separator"` a
    un barcode. Hoy el separador es de la página (`page.is_separator`); la
    migración convirtió esos roles en marcas de página y la miniatura todavía
    pinta de naranja un barcode con ese rol, pero la transferencia solo mira
    la marca de página.

## PipelineContext

| Método | Descripción |
|--------|-------------|
| `skip_step(id)` | Saltar un paso |
| `skip_to(id)` | Saltar hasta un paso |
| `abort(reason)` | Abortar pipeline |
| `repeat_step(id)` | Repetir paso (máx. 3 por defecto; al superarlo, aborta) |
| `replace_image(img)` | Reemplazar imagen y marcarla para guardar |
| `set_metadata(k, v)` | Guardar un dato **de esta página** |
| `get_metadata(k)` | Recuperar un dato **de esta página** |
| `get_step_result(id)` | Resultado de paso anterior |
| `current_image` | Imagen actual (propiedad) |
| `aborted` | `True` si se llamó a `abort()` (propiedad) |
| `abort_reason` | Motivo pasado a `abort()` (propiedad) |

!!! warning "El metadata del pipeline dura una sola página"
    El pipeline crea un `PipelineContext` nuevo para cada página, así que
    `set_metadata` / `get_metadata` **no** pasan datos de una página a la
    siguiente. Para relacionar adjuntos con su separadora están el
    [documento lógico](#documento-logico) y la receta
    [Un fichero por documento](../user-guide/scripting.md#un-fichero-por-documento).

!!! warning "Qué imagen se guarda con `replace_image()`"

    `replace_image()` marca la página para que se persista en disco, pero
    lo que acaba en el fichero es el **estado final del pipeline**, no
    forzosamente la imagen que pasa tu script: si detrás corren más
    operaciones de imagen, el fichero recoge el resultado de estas.

    Si necesitas fijar un punto concreto, marca la casilla **«Guardar el
    resultado en el fichero de la página»** en el paso que corresponda.
    Esa guarda una instantánea de ese paso y tiene prioridad sobre el
    estado final.

## Argumentos de cada evento

Todos los eventos reciben `app` y `batch`. Además reciben estos argumentos
(el motor solo pasa los que declare tu función):

| Evento | Argumentos extra | Valor de retorno |
|--------|------------------|------------------|
| `on_app_start`, `on_app_end`, `on_batch_loaded`, `on_scan_complete` | — | ignorado |
| `on_import` | — | cualquier valor distinto de `None` sustituye la importación estándar |
| `on_page_changed` | `page`, `page_index` | ignorado |
| `on_key_event` | `key` (str, nombre Qt de la tecla, p. ej. `Key_A`; solo con Ctrl, Alt o Shift) | ignorado |
| `on_navigate_prev`, `on_navigate_next` | `current_page_index`, `total_pages` | índice de página a la que ir (int) |
| `on_navigate_script` | `current_page_index`, `total_pages`, `pages` (lista de dicts con `page_index`, `barcodes` y `needs_review`) | índice de página (int) |
| `on_transfer_validate` | `pages`, `documents` (opcionales) | `False` (o una excepción) cancela la transferencia. Un `ValueError` es un rechazo: el operador ve solo su mensaje |
| `on_transfer_advanced` | `pages`, `documents`, `result` (en el Workbench y en el worker) | `False` (o una excepción) hace fallar la transferencia. Un `TransferResult` devuelto se suma al de la transferencia simple (o lo sustituye si está desactivada) |
| `on_transfer_page` | `page_index`, `success` (solo en el Workbench) | ignorado |
| `init_global` | — (sin `app` ni `batch`) | ignorado |

### Dónde corre cada evento

| Evento | Workbench | Worker desatendido y modo directo |
|--------|-----------|-----------------------------------|
| `on_app_start` | Al abrir la aplicación | Worker: una vez por cada lote que importa |
| `on_app_end` | Al cerrar la aplicación | No |
| `on_scan_complete` | Al terminar el pipeline de todas las páginas | Worker: sí |
| `on_transfer_validate`, `on_transfer_advanced` | Sí | Sí (mismo flujo de transferencia) |
| `on_import`, `on_batch_loaded`, `on_page_changed`, `on_navigate_*`, `on_key_event`, `on_transfer_page` | Sí | No |
| `init_global` | Al arrancar el programa (launcher), una sola vez: el de la **primera** aplicación activa que lo defina | No |

### Eventos pausados

Cada evento de la pestaña Eventos tiene la casilla **«Activado»**. Un evento
desactivado (PAUSADO en la lista) conserva su código, pero no se compila y no
corre en ningún sitio: ni en el Workbench, ni en el worker, ni en la
transferencia.

## Orden de la transferencia

Igual en el Workbench y en el worker desatendido (lógica de FlexibarNET 10):

1. **Campos de lote obligatorios**: si alguno está vacío, la transferencia no
   empieza y el aviso nombra los campos.
2. **Documentos** (solo con la transferencia simple activada y fuera del modo
   CSV): si el patrón usa `{separator}` y algún documento no tiene
   valor, o si con la página separadora descartada un documento quedaría vacío
   o hay páginas antes de la primera hoja, la transferencia no empieza.
3. **`on_transfer_validate`**: si devuelve `False` **o lanza una excepción**, la
   transferencia no empieza. Un `ValueError` se toma como rechazo deliberado
   (aviso en el log, solo el mensaje al operador); otra excepción, como fallo
   del script (error con traza).
4. **Transferencia simple**, si está activada (con «solo script» no hace falta
   carpeta de destino). Antes de escribir nada comprueba que todas las imágenes
   están en disco y calcula todos los nombres: si falta una imagen o el script
   de nombre falla, no queda salida a medias.
5. **`on_transfer_advanced`**, con `pages`, `documents` y el `result` de la
   transferencia simple.
   Si devuelve `False` **o lanza**, la transferencia falla y el lote **no** se
   marca como exportado.

Solo en el Workbench, antes del paso 1, el [panel de verificación](#panel-de-verificacion)
valida cada página (`validate_page`) y el lote (`validate`); entre los pasos 3
y 4, el operador confirma la transferencia.

Cada elemento de `pages` tiene `image_path`, `page_index`, `fields`, `ocr_text`,
`first_barcode`, `barcodes` (cada uno con `value` y `symbology`),
`is_separator`, `separator_value` e `image` (se lee del disco al pedirla).
Llegan en orden de lote y sin las páginas excluidas.

```python
def on_transfer_advanced(app, batch, pages, result):
    ...
```

!!! warning "Scripts que escriben en sistemas externos"
    Si el script avanzado falla, el operador reintentará la transferencia. Si
    escribe en un sistema externo (LIS, base de datos, API), haz que se pueda
    repetir sin duplicar registros.

## Documento lógico

Un documento es el tramo de páginas que va de una página separadora a la
siguiente. No se guarda en ningún sitio: se calcula al vuelo a partir de las
marcas de página, así que reordenar o desmarcar páginas lo cambia solo. Lo
reciben `on_transfer_validate` y `on_transfer_advanced` (`documents`) y el
script de nombre (`document`).

| Atributo | Tipo | Descripción |
|----------|------|-------------|
| `index` | int | Número del documento en el lote, empezando en 1 |
| `separator_value` | str | Valor del separador (`""` en el implícito) |
| `pages` | list | Páginas del documento en orden, separadora incluida |
| `fields` | dict | Campos del documento: los de su página separadora |
| `is_implicit` | bool | `True` si son las páginas anteriores al primer separador |

Un lote sin separadores es un único documento implícito.

## Script de nombre de fichero

Con *Nombre por: Script* en la pestaña Transferencia
(`name_mode = "script"`), el nombre de cada fichero lo da:

```python
def file_name(page, document, batch, app):
    return f"{batch.fields['Data'].replace('/', '')}/{document.separator_value}"
```

| Argumento | Contenido |
|-----------|-----------|
| `page` | En modo carpeta, la página. En PDF/TIFF multipágina, la primera página del documento (la separadora, aunque se descarte); con un fichero por lote, la primera del lote. Tiene los mismos atributos que las `pages` de la transferencia |
| `document` | Documento lógico de esa página; con un fichero por lote, el primer documento. Puede ser `None` en algún caso límite |
| `batch` | `BatchContext`, con los campos del lote en `batch.fields` |
| `app` | `AppContext` |

Devuelve la subruta **sin extensión** (las `/` crean subcarpetas y cada
segmento se sanea). `None` o `""` usan el patrón. Si lanza, la transferencia
no se hace y no se escribe nada. En modo CSV el script no se usa: el nombre
sale siempre del patrón.

## Panel de verificación

El evento `verification_panel` no es una función: define una subclase de
`VerificationPanel` que el Workbench muestra en la pestaña Verificación. Se
sobrescriben los métodos que hagan falta:

| Método | Cuándo se llama |
|--------|-----------------|
| `setup_ui()` | Al crear el panel: construye la interfaz (widgets PySide6) |
| `on_page_changed(page_index)` | Al cambiar de página |
| `on_pipeline_completed(page_index)` | Al terminar el pipeline de una página |
| `on_batch_loaded()` | Al abrir o crear un lote |
| `validate_page(page_index)` → `(bool, str)` | Antes de transferir, para cada página; `False` lleva a esa página y cancela con el mensaje |
| `validate()` → `(bool, str)` | Antes de transferir, después de `validate_page`; `False` cancela |
| `cleanup()` | Al cerrar el Workbench |

`self.api` da acceso al lote: `current_page`, `get_page_count()`,
`navigate_to(i)`, `get_page_image(i)`, `get_page_barcodes(i)`,
`get_page_ocr_text(i)`, `get_page_fields(i)`, `set_page_field(i, nombre, valor)`,
`get_batch_fields()`, `set_batch_field(nombre, valor)` y `log(mensaje)`.

```python
class MiPanel(VerificationPanel):
    def validate_page(self, page_index):
        if not self.api.get_page_fields(page_index).get("nif"):
            return False, f"Página {page_index + 1}: NIF obligatorio"
        return True, ""
```
