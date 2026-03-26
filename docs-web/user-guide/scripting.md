# :material-language-python: Scripting

DocScan Studio incluye un motor de scripting Python completo.

## Variables disponibles

| Variable | Tipo | Disponible en |
|----------|------|---------------|
| `app` | AppContext | Todos |
| `batch` | BatchContext | Todos |
| `page` | PageContext | Todos |
| `pipeline` | PipelineContext | Solo ScriptStep |
| `log` | Logger | Todos |
| `http` | httpx.Client | Todos |
| `re`, `json`, `datetime`, `Path` | módulos | Todos |

## Eventos del ciclo de vida

| Evento | Cuándo se ejecuta |
|--------|-------------------|
| `on_app_start` | Al abrir la aplicación |
| `on_app_end` | Al cerrar la aplicación |
| `on_import` | Al pulsar Procesar |
| `on_scan_complete` | Tras completar el pipeline |
| `on_transfer_validate` | Antes de transferir (False cancela) |
| `on_transfer_advanced` | Transferencia scripteada |
| `on_transfer_page` | Post-copia por página |
| `on_navigate_prev/next` | Navegación personalizable |
| `on_key_event` | Tecla personalizada |
| `init_global` | Al iniciar el programa |
| `verification_panel` | Panel de verificación |

## Recetas

### Separar documentos por barcode

```python
def separar(app, batch, page, pipeline):
    seps = [b for b in page.barcodes if b.symbology == "CODE128"]
    if seps:
        page.fields["id_documento"] = seps[0].data
        pipeline.set_metadata("ultimo_id", seps[0].data)
    else:
        page.fields["id_documento"] = pipeline.get_metadata("ultimo_id") or "SIN_ID"
```

### Validar antes de transferir

```python
def on_transfer_validate(app, batch, page):
    if not batch.fields.get("numero_factura"):
        raise ValueError("El número de factura es obligatorio")
```

### Llamar a una API externa

```python
def clasificar(app, batch, page, pipeline):
    resp = http.post("https://api.ejemplo.com/clasificar",
                     json={"text": page.ocr_text})
    if resp.status_code == 200:
        page.fields["tipo_doc"] = resp.json()["tipo"]
```

## Buenas prácticas

!!! tip "Recomendaciones"

    - Usar `log.info()`, `log.warning()` y `log.error()` en vez de `print()`
    - Acceder a barcodes siempre via `page.barcodes`
    - Los errores en scripts no detienen el pipeline
    - Usar `pipeline.set_metadata()` para compartir datos entre pasos
    - Timeout por defecto: 30 segundos
