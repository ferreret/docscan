# :material-monitor-dashboard: Workbench web

El workbench web es el equivalente navegador del workbench desktop. Carga
un lote, muestra sus páginas y permite editar metadatos, reprocesar el
pipeline o ejecutar la transferencia.

## Diferencias respecto al desktop

- **No tiene escáner**. La adquisición se hace por subida de ficheros
  (drag-drop o botón). El cliente local con TWAIN/SANE está en el roadmap.
- **El procesamiento ocurre en el servidor**. El navegador no calcula nada
  pesado: encola el job al servidor, el worker ARQ procesa y emite eventos
  WebSocket que la UI consume para refrescar.
- **Multi-usuario en el mismo lote**. Si dos personas abren el mismo lote
  a la vez, ven los mismos datos y los cambios se propagan por WebSocket.
- **Estado de solo lectura mientras se procesa**. Mientras el lote está
  en `running` o `transferring`, los controles destructivos (rotar
  página, añadir/borrar barcode, eliminar página) quedan deshabilitados.

## Carga de páginas

La carga se hace por **arrastrar y soltar** ficheros sobre la zona del
workbench, o pulsando `Subir` para abrir el selector. Formatos aceptados:
PNG, JPEG y TIFF (incluido multipágina — los TIFF se descomponen
automáticamente en una página por frame).

!!! info "Por qué se almacena como PNG"
    El servidor reconvierte cada página subida a PNG antes de guardarla.
    Razón: los navegadores no renderizan TIFF y los frames del TIFF se
    perderían. El original no se conserva.

## Atajos de teclado

El workbench web reproduce los atajos del desktop, con un filtro de foco
que evita disparos accidentales mientras editas un campo de texto, un
diálogo o un menú contextual.

| Tecla | Acción |
|---|---|
| `←` `→` | Navegar entre páginas |
| `Shift+→` | Marcar página como *necesita revisión* y avanzar |
| `Esc` | Cerrar el lote actual |
| `?` | Abrir el cheatsheet de atajos |
| `R` | Rotar la página actual 90° en sentido horario |
| `M` | Marcar/desmarcar como *necesita revisión* |
| `X` | Excluir/restaurar la página |
| `P` | Reprocesar la página actual (ScriptStep en debug) |
| `B` | Añadir barcode manual |
| `Delete` | Borrar la página (con confirmación) |
| `Ctrl+G` | Ir a página por número |
| `T` | Lanzar transferencia |
| `W` | Marcar lote como *escrito* (`written`) |
| `F5` | Reprocesar todo el lote |
| `0`, `+`, `-`, `F` | Zoom: reset, in, out, fit-to-width |

Pulsa `?` en cualquier momento para ver la lista completa contextualizada.

## Eventos lifecycle desde el web

El workbench web dispara los mismos eventos lifecycle que el desktop. Los
scripts asociados se ejecutan en el servidor con un timeout de 5 segundos
por evento.

| Evento | Cuándo se dispara |
|---|---|
| `on_batch_loaded` | Al abrir el lote en el workbench |
| `on_page_changed` | Al cambiar la página activa |
| `on_navigate_prev` / `on_navigate_next` | Al navegar (permite saltarse páginas) |
| `on_key_event` | Al pulsar una tecla no asignada (modificadores puros se ignoran) |
| `on_transfer_validate` | Antes de iniciar la transferencia |

Los scripts deben definir una función nombrada (no código top-level):

```python
def on_page_changed(app, batch, page, **kwargs):
    log.info("Cambiamos a página id=%s, índice=%s", page.id, page.page_index)
```

El parámetro `log` que se inyecta es un `logging.Logger` (no un callable
suelto). Devolver un `dict` con la clave `cancel: True` cancela la acción
asociada (por ejemplo, `on_navigate_next` puede impedir avanzar).

## Auto-refresh por WebSocket

Cada cliente conectado al workbench abre un WebSocket al servidor para
recibir eventos del lote: nuevas páginas, cambios de estado, progreso
del pipeline, finalización de la transferencia. La UI los aplica
automáticamente, por lo que dos personas viendo el mismo lote convergen
en el mismo estado en tiempo real.

Si el WebSocket cae (por ejemplo, sleep del portátil), la UI hace una
recarga al volver a la pestaña y vuelve a abrir la conexión.

## Reprocesar páginas

- **Una sola página**: tecla `P` o menú contextual → "Reprocesar". Útil
  para iterar sobre un ScriptStep que estás depurando — no toca las
  demás páginas del lote.
- **Lote entero**: tecla `F5` o botón "Reprocesar lote". Vuelve a ejecutar
  el pipeline en cada página.

Reprocesar **borra los flags manuales** (revisión, exclusión) — si
necesitas conservarlos, edítalos después o usa scripts que los recreen.

## Exportar lote

El botón "Exportar ZIP" descarga un fichero comprimido con todas las
páginas en `pages/page_NNNN.png` y un `manifest.json` con metadatos
(barcodes, OCR, campos) por página. Útil para archivado o para
reprocesar en otro entorno.
