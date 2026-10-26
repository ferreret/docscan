# :material-language-python: Scripting

DocScan Studio incluye un motor de scripting Python completo.

## Variables disponibles

| Variable | Tipo | Disponible en |
|----------|------|---------------|
| `app` | AppContext | ScriptStep y eventos (salvo `init_global`) |
| `batch` | BatchContext | ScriptStep y eventos (salvo `init_global`) |
| `page` | PageContext | ScriptStep y `on_page_changed` |
| `pipeline` | PipelineContext | Solo ScriptStep |
| `log` | Logger | Todos |
| `http` | httpx.Client | Todos |
| `re`, `json`, `datetime`, `Path` | módulos | Todos |

Los argumentos que recibe cada evento, y lo que significa su valor de retorno,
están en la [referencia de la API](../reference/scripting-api.md#argumentos-de-cada-evento).

## Eventos del ciclo de vida

| Evento | Cuándo se ejecuta |
|--------|-------------------|
| `on_app_start` | Al abrir la aplicación |
| `on_app_end` | Al cerrar la aplicación |
| `on_import` | Al iniciar una importación (si devuelve algo, sustituye la estándar) |
| `on_scan_complete` | Una vez, tras procesar todas las páginas |
| `on_batch_loaded` | Al abrir un lote (desktop v0.1.1+) |
| `on_page_changed` | Al cambiar de página activa (desktop v0.1.1+) |
| `on_transfer_validate` | Antes de transferir (`False` cancela) |
| `on_transfer_advanced` | Transferencia scripteada |
| `on_transfer_page` | Tras copiar cada página en la transferencia simple |
| `on_navigate_prev/next` | Navegación personalizable |
| `on_navigate_script` | Botón de navegación programable del visor |
| `on_key_event` | Tecla personalizada |
| `init_global` | Al iniciar el programa |
| `verification_panel` | Panel de verificación |

!!! info "Identificador de página"
    Desde la v0.1.1 (web) y v0.1.2 (desktop), `page.id` está disponible
    dentro del pipeline y de los eventos lifecycle. Útil para correlacionar
    con la BD o llamar a APIs externas con un identificador estable.

## Recetas

### Un PDF por documento

Un **documento** es el tramo de páginas que va desde una hoja separadora hasta
la siguiente; las páginas anteriores a la primera separadora forman un
documento implícito. Es el mismo modelo que FlexibarNET 10.

Hasta que la separación sea una función nativa (está diseñada en
`docs/diseno_separadores_documento_2026-10-26.md`), se monta en dos piezas.

**1. Un ScriptStep detrás del paso Barcode** marca la separadora:

```python
def marcar_separador(app, batch, page, pipeline):
    for bc in page.barcodes:
        if bc.symbology == "Code39":          # condición de separador
            bc.role = "separator"             # la miniatura se pinta como separadora
            page.fields["separator"] = bc.value
            return
```

**2. `on_transfer_advanced`** agrupa por tramos y escribe un PDF por documento
(con la transferencia simple desactivada):

```python
def on_transfer_advanced(app, batch, pages=None, result=None):
    from app.services.image_lib import ImageLib

    if pages is None:  # el worker desatendido no pasa las páginas
        return True
    destino = Path(app.transfer_config["destination"])
    destino.mkdir(parents=True, exist_ok=True)

    # Documento = tramo desde una separadora hasta la siguiente. Las páginas
    # previas a la primera separadora forman un documento implícito.
    documentos = []
    for p in pages:  # llegan en orden de lote, sin las excluidas
        valor = p.fields.get("separator")
        if valor or not documentos:
            documentos.append({"separator": valor or "", "paginas": []})
        documentos[-1]["paginas"].append(p.image_path)

    for i, doc in enumerate(documentos, start=1):
        # El valor viene del papel: nada de rutas ni caracteres reservados.
        nombre = re.sub(r'[\\/:*?"<>|.]', "_", doc["separator"]) or f"documento_{i}"
        ImageLib.merge_to_pdf(doc["paginas"], destino / f"{nombre}_{batch.id}.pdf")
    return True
```

!!! warning "Por qué no `pipeline.set_metadata`"
    El pipeline crea un contexto nuevo para cada página, así que el metadata no
    pasa de una página a la siguiente: un adjunto nunca vería el id de su
    separadora. La agrupación tiene que hacerse donde se ven todas las páginas
    a la vez, que es la transferencia.

### Validar antes de transferir

```python
def on_transfer_validate(app, batch):
    if not batch.fields.get("numero_factura"):
        log.warning("Falta el número de factura")
        return False  # cancela la transferencia
    return True
```

!!! danger "Devuelve `False`; no lances una excepción"
    Hoy una excepción en `on_transfer_validate` queda en el log y la
    transferencia **sigue adelante**. Se corregirá para que falle cerrado.

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
    - Acceder a barcodes siempre vía `page.barcodes`, con su atributo `value`
    - Los errores en scripts no detienen el pipeline: quedan en
      `page.flags.script_errors`
    - `pipeline.set_metadata()` comparte datos entre pasos **de la misma página**
    - Todo valor que venga del papel (barcodes, OCR) y acabe en una ruta debe
      sanearse antes
    - Timeout por defecto: 30 segundos
