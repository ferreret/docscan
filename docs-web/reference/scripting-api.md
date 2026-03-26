# :material-api: API de scripting

Referencia completa de los objetos disponibles en scripts.

## AppContext

| Atributo | Tipo | Descripción |
|----------|------|-------------|
| `name` | str | Nombre de la aplicación |
| `description` | str | Descripción |

## BatchContext

| Atributo | Tipo | Descripción |
|----------|------|-------------|
| `id` | int | ID del lote |
| `state` | str | Estado actual |
| `fields` | dict | Campos del lote |
| `page_count` | int | Número de páginas |

## PageContext

| Atributo | Tipo | Descripción |
|----------|------|-------------|
| `image` | ndarray | Imagen actual (OpenCV) |
| `barcodes` | list[BarcodeResult] | Barcodes detectados |
| `ocr_text` | str | Texto OCR |
| `fields` | dict | Campos de indexación |
| `flags` | PageFlags | Flags de estado |

## BarcodeResult

| Atributo | Tipo | Descripción |
|----------|------|-------------|
| `data` | str | Valor del barcode |
| `symbology` | str | Tipo (Code128, QR, etc.) |
| `engine` | str | Motor usado |
| `quality` | float | Confianza (0.0–1.0) |
| `rect` | tuple | Coordenadas (x, y, w, h) |

## PipelineContext

| Método | Descripción |
|--------|-------------|
| `skip_step(id)` | Saltar un paso |
| `skip_to(id)` | Saltar hasta un paso |
| `abort(reason)` | Abortar pipeline |
| `repeat_step(id)` | Repetir paso (máx. 3) |
| `replace_image(img)` | Reemplazar imagen |
| `set_metadata(k, v)` | Guardar dato |
| `get_metadata(k)` | Recuperar dato |
| `get_step_result(id)` | Resultado de paso anterior |
| `current_image` | Imagen actual (propiedad) |
