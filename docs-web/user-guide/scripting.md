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

### Un fichero por documento

Un **documento** es el tramo de páginas que va desde una página separadora
hasta la siguiente; las páginas anteriores a la primera separadora forman un
documento implícito. Es el mismo modelo que FlexibarNET 10, y no necesita
scripts:

1. En el paso **Barcode**, activa *Separador de documento* con su condición
   (ver [Pipeline](pipeline.md#separador-de-documento)). La página que la
   cumple queda marcada como separadora (`page.is_separator`) con el valor del
   código (`page.separator_value`).
2. En **Transferencia**, elige un modo multipágina (`pdf`, `pdfa` o `tiff`),
   *Un fichero por documento* y un patrón con `{separator}`, por ejemplo
   `{separator}_{batch_id}` (ver [Transferencia](transfer.md)).

Si la condición no se puede expresar en el paso Barcode, un **ScriptStep
posterior** tiene la última palabra y puede escribir la marca:

```python
def marcar(app, batch, page, pipeline):
    seps = [bc for bc in page.barcodes if bc.value.startswith("SEP-")]
    page.is_separator = bool(seps)
    page.separator_value = seps[0].value[4:] if seps else ""
```

El separador es de la **página**, no del barcode: poner `role = "separator"` a
un código ya no separa documentos.

### Script de nombre de fichero

Cuando el patrón no basta (recortar el código, una fecha sacada de un campo de
lote…), en Transferencia → *Nombre por: Script* se define:

```python
def file_name(page, document, batch, app):
    from datetime import datetime

    fecha = datetime.strptime(batch.fields["Data"], "%d/%m/%Y")
    codigo = document.separator_value[-9:]       # los 9 últimos dígitos
    return f"{fecha:%Y%m%d}/{codigo}"            # subruta SIN extensión
```

- Devuelve la subruta **sin extensión**; las `/` crean subcarpetas y cada
  segmento se sanea igual que con el patrón (nunca sale de la carpeta de
  destino).
- Si devuelve `None` o una cadena vacía, se usa el patrón.
- Si **lanza**, la transferencia no se hace y no queda nada escrito: los
  nombres se calculan todos antes de escribir el primer fichero.
- `page` es la primera página del fichero (en modo carpeta, cada página) y
  `document` su documento (`index`, `separator_value`, `pages`, `fields`).

### Validar antes de transferir

```python
def on_transfer_validate(app, batch, pages):
    sin_codigo = [p.page_index + 1 for p in pages if not p.is_separator]
    if sin_codigo:
        raise ValueError(
            f"Hay páginas sin código de barras. La primera es la {sin_codigo[0]}"
        )
    return True
```

`pages` y `documents` son parámetros **opcionales**: declara solo los que uses
(`def on_transfer_validate(app, batch)` sigue funcionando). Devolver `False`
cancela la transferencia; una excepción también. Para rechazar con un motivo,
lanza un **`ValueError`**: es un rechazo deliberado, el operador ve solo su
mensaje y el log lo registra como aviso. Cualquier otra excepción
(`TypeError`, `AttributeError`…) se trata como un fallo del script: se muestra
como «Ha fallado la validación previa…» y queda en el log con la traza. Es la
validación de las Apps de archivo del Hospital Arnau de Vilanova: toda página
tiene que llevar su código.

Para campos que solo tienen que estar rellenos no hace falta script: marca el
campo como **obligatorio** en la pestaña Campos de Lote.

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
