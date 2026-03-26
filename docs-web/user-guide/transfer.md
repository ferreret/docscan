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
def on_transfer_advanced(app, batch, page):
    # Control total del proceso de exportación
    for p in batch.pages:
        destino = Path(f"/archivo/{batch.fields['cliente']}/{p.fields['id_doc']}.pdf")
        destino.parent.mkdir(parents=True, exist_ok=True)
        # ... lógica de exportación personalizada
```
