# :material-export: Transferencia

## Transferencia simple

Copia los ficheros procesados a una carpeta de destino con patrón de nombres configurable.

### Formatos de salida

| Formato | Extensión | Características |
|---------|-----------|----------------|
| TIFF | .tif | Compresión LZW/JPEG/Deflate, multi-página |
| JPEG | .jpg | Calidad configurable (1-100) |
| PNG | .png | Sin pérdida |
| BMP | .bmp | Sin compresión |
| PDF | .pdf | Estándar |
| PDF/A | .pdf | PDF/A-1b y PDF/A-2b para archivo |

### Patrones de nombre

Ver [Patrones de nombre](../reference/naming-patterns.md) para la lista completa de variables.

### Política de colisión

| Política | Comportamiento |
|----------|---------------|
| Sufijo | Añade _001, _002... si ya existe |
| Sobreescribir | Reemplaza el fichero existente |
| Fusionar | Añade páginas al PDF/TIFF existente |

## Transferencia avanzada

Para necesidades complejas, usar el evento `on_transfer_advanced`:

```python
def on_transfer_advanced(app, batch, pages=None, result=None):
    # Workbench: recibe `pages`. Worker desatendido: recibe `result`.
    if pages is None:
        return True
    for p in pages:
        destino = Path(f"/archivo/{batch.fields['cliente']}/{p.fields['id_doc']}.pdf")
        destino.parent.mkdir(parents=True, exist_ok=True)
        # ... lógica de exportación personalizada
    return True  # False informa de un fallo
```

Cada página de `pages` tiene `image_path`, `page_index`, `fields`, `ocr_text`,
`first_barcode` e `image`. Para un PDF por documento (hojas separadoras), ver la
receta [Un PDF por documento](scripting.md#un-pdf-por-documento).
