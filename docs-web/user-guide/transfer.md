# :material-export: Transferencia

## Transferencia simple

Copia los ficheros procesados a una carpeta de destino con patrón de nombres configurable.

### Configuración general

| Opción | Qué hace |
|--------|----------|
| Habilitar transferencia estándar | Desmarcada, solo se ejecuta el evento `on_transfer_advanced` (si está definido) |
| Modo | Ver la tabla de abajo |
| Destino | Carpeta donde se dejan los ficheros |
| Crear subdirectorios por lote | En modo `folder`, una subcarpeta `batch_<id>` por lote |
| Incluir metadatos JSON | En modo `folder`, un `.json` junto a cada fichero con los barcodes, el texto OCR y los campos de indexación |
| Si ya existe | Política de colisión (ver más abajo) |

### Modos

| Modo | Qué genera |
|------|-----------|
| `folder` | Un fichero por página en la carpeta de destino (con conversión de formato opcional) |
| `pdf` | PDF multipágina, por lote o por documento |
| `pdfa` | PDF/A (archivable), por lote o por documento |
| `tiff` | TIFF multipágina, por lote o por documento |
| `csv` | Un CSV con los campos de indexación |

### Imágenes de salida

En el modo `folder`, el grupo «Imágenes de salida» convierte cada página al
transferirla:

| Formato | Extensión | Características |
|---------|-----------|----------------|
| Original | la de origen | Se copia sin convertir |
| TIFF | .tif | Compresión LZW, Deflate (zip), Group4 o ninguna |
| JPEG | .jpg | Calidad configurable (1-100) |
| PNG | .png | Sin pérdida, compresión 0-9 |

También se pueden cambiar los DPI y el color (original, gris o B/N). Para PDF y
PDF/A se usan los modos `pdf` y `pdfa`.

!!! info "Group4 es solo blanco y negro"
    Como en FlexibarNET 10, un TIFF cuyas páginas son todas blanco y negro se
    guarda a 1 bit en Group4. Si alguna página está en gris o en color, el
    fichero entero va en LZW y no se binariza nada.

En el modo `tiff` se aplican también el color, los DPI y la compresión del
grupo «Imágenes de salida».

### Opciones PDF y CSV

- **Opciones PDF** (modos `pdf` y `pdfa`): *DPI del PDF* (200 por defecto, de 72
  a 600) y *Calidad JPEG* de las imágenes dentro del PDF (85).
- **Opciones CSV** (modo `csv`): *Separador* (`;` por defecto) y *Campos*, los
  campos de indexación que forman las columnas, separados por coma. Vacío = los
  de la primera página. El CSV lleva además `page_index` e `image_path`, una
  fila por página, y su nombre sale siempre del patrón, nunca del script de
  nombre.

### Documentos

Un **documento** es el tramo de páginas que va de una página separadora a la
siguiente (ver [Pipeline](pipeline.md#separador-de-documento)). En los modos
`pdf`, `pdfa` y `tiff`, la **agrupación** decide si sale un fichero por lote o
uno **por documento**. Sin separadores, el lote entero es un documento y
ambas opciones dan lo mismo.

La **página separadora** puede:

- **Incluirse** (por defecto): es la portada del documento, como en
  FlexibarNET 10.
- **Descartarse**: es una hoja separadora que no se transfiere. Vale para
  `folder`, `pdf`, `pdfa` y `tiff`; en `csv` no aparece el grupo Documentos.

Con la página separadora descartada, la transferencia no empieza si:

- un documento solo tiene la hoja separadora (quedaría vacío), o
- hay páginas antes de la primera hoja separadora (no pertenecen a ningún
  documento).

### Nombre de los ficheros

- **Por patrón**: ver [Patrones de nombre](../reference/naming-patterns.md),
  con las variables de documento `{separator}`, `{document_index}` y
  `{document_id}`.
- **Por script**: una función `file_name(page, document, batch, app)` devuelve
  la subruta sin extensión. Ver
  [Script de nombre de fichero](scripting.md#script-de-nombre-de-fichero).

Los nombres de todos los ficheros se calculan **antes de escribir el
primero**: si el script de nombre falla o un documento no tiene el valor que
pide el patrón, la transferencia no se hace y no queda salida a medias.

### Política de colisión

| Política | Comportamiento |
|----------|---------------|
| Sufijo | Añade `_1`, `_2`… si ya existe |
| Sobreescribir | Reemplaza el fichero existente |
| Fusionar | Añade las páginas **al final** del PDF/TIFF existente |

Con un modo multipágina y «Fusionar», las páginas que acaban con el mismo
nombre se juntan en un fichero aunque no sean consecutivas o lleguen en otro
lote. Es el archivo «un TIFF por número de petición» de las Apps del Hospital
Arnau de Vilanova. El fichero se reescribe de forma atómica: un fallo a mitad
no lo deja corrupto.

## Transferencia avanzada

Para necesidades complejas, usar el evento `on_transfer_advanced`:

```python
def on_transfer_advanced(app, batch, pages, result):
    # Corre después de la transferencia simple (si está activada), igual en
    # el Workbench y en el worker desatendido.
    for p in pages:
        destino = Path(f"/archivo/{batch.fields['cliente']}/{p.fields['id_doc']}.pdf")
        destino.parent.mkdir(parents=True, exist_ok=True)
        # ... lógica de exportación personalizada
    return True  # False (o una excepción) hace fallar la transferencia
```

Cada página de `pages` tiene `image_path`, `page_index`, `fields`, `ocr_text`,
`first_barcode`, `barcodes`, `is_separator`, `separator_value` e `image`; el
evento también puede declarar `documents`. Para un fichero por documento no
hace falta script: ver [Documentos](#documentos).
