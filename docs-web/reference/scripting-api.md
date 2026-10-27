# :material-api: API de scripting

Referencia completa de los objetos disponibles en scripts.

## AppContext

| Atributo | Tipo | Descripción |
|----------|------|-------------|
| `id` | int | ID de la aplicación |
| `name` | str | Nombre de la aplicación |
| `description` | str | Descripción |
| `config` | dict | Configuración de IA |
| `batch_fields_def` | list[dict] | Definición de los campos de lote |
| `transfer_config` | dict | Configuración de transferencia |
| `pipeline_steps` | list[dict] | Pasos del pipeline |
| `auto_transfer` | bool | Transferir automáticamente |
| `output_format` | str | Formato de salida |

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
| `image` | ndarray | Imagen actual (OpenCV) |
| `barcodes` | list[BarcodeResult] | Barcodes detectados |
| `ocr_text` | str | Texto OCR |
| `fields` | dict | Campos de indexación |
| `flags` | PageFlags | Flags de estado |
| `is_separator` | bool | La página abre un documento (lectura y escritura) |
| `separator_value` | str | Valor que identifica el documento, `""` si no tiene (lectura y escritura) |

El paso Barcode con *Separador de documento* activo escribe `is_separator` y
`separator_value`; un ScriptStep posterior puede cambiarlos. Si el pipeline
no los toca, la página conserva la marca que ya tenía (por ejemplo, la manual).

## BarcodeResult

| Atributo | Tipo | Descripción |
|----------|------|-------------|
| `value` | str | Valor del barcode |
| `symbology` | str | Tipo normalizado (`Code128`, `Code39`, `QR`, `EAN13`…) |
| `engine` | str | Motor que lo leyó (`pyzbar` o `zxing`) |
| `step_id` | str | Paso Barcode que lo encontró |
| `quality` | float | Calidad de lectura (0.0–1.0) |
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
| `repeat_step(id)` | Repetir paso (máx. 3) |
| `replace_image(img)` | Reemplazar imagen y marcarla para guardar |
| `set_metadata(k, v)` | Guardar un dato **de esta página** |
| `get_metadata(k)` | Recuperar un dato **de esta página** |
| `get_step_result(id)` | Resultado de paso anterior |
| `current_image` | Imagen actual (propiedad) |

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
| `on_key_event` | `key` (str) | ignorado |
| `on_navigate_prev`, `on_navigate_next` | `current_page_index`, `total_pages` | índice de página a la que ir (int) |
| `on_navigate_script` | `current_page_index`, `total_pages`, `pages` (lista de dicts) | índice de página (int) |
| `on_transfer_validate` | `pages`, `documents` (opcionales) | `False` (o una excepción) cancela la transferencia; el mensaje de la excepción llega al operador |
| `on_transfer_advanced` | `pages`, `documents`, `result` (en el Workbench y en el worker) | `False` (o una excepción) hace fallar la transferencia |
| `on_transfer_page` | `page_index`, `success` | ignorado |
| `init_global` | — (sin `app` ni `batch`) | ignorado |

## Orden de la transferencia

Igual en el Workbench y en el worker desatendido (lógica de FlexibarNET 10):

1. **Campos de lote obligatorios**: si alguno está vacío, la transferencia no
   empieza y el aviso nombra los campos.
2. **Documentos**: si el patrón usa `{separator}` y algún documento no tiene
   valor, o si con la página separadora descartada un documento quedaría vacío
   o hay páginas antes de la primera hoja, la transferencia no empieza.
3. **`on_transfer_validate`**: si devuelve `False` **o lanza una excepción**, la
   transferencia no empieza.
4. **Transferencia simple**, si está activada (con «solo script» no hace falta
   carpeta de destino). Antes de escribir nada calcula todos los nombres: si el
   script de nombre falla, no queda salida a medias.
5. **`on_transfer_advanced`**, con `pages` y el `result` de la transferencia simple.
   Si devuelve `False` **o lanza**, la transferencia falla y el lote **no** se
   marca como exportado.

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
| `page` | Primera página del fichero (en modo carpeta, la página), con los mismos atributos que las `pages` de la transferencia |
| `document` | Documento lógico de esa página |
| `batch` | `BatchContext`, con los campos del lote en `batch.fields` |
| `app` | `AppContext` |

Devuelve la subruta **sin extensión** (las `/` crean subcarpetas y cada
segmento se sanea). `None` o `""` usan el patrón. Si lanza, la transferencia
no se hace y no se escribe nada.
