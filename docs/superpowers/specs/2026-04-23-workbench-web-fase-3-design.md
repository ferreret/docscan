# Workbench web — Fase 3 (edición y log)

**Fecha**: 2026-04-23
**Estado**: pendiente aprobación del usuario
**Sub-proyecto**: 3 de 4 del Workbench web

## Contexto

El sub-proyecto Workbench web se compone de cuatro fases secuenciales:

1. ✅ Sistema de tema global (cerrado el 2026-04-22)
2. ✅ Workbench base: layout multi-panel + componentes view-only (cerrado el 2026-04-22)
3. **Edición y log** (esta spec)
4. Shortcuts + 4 eventos lifecycle nuevos (pendiente)

La Fase 2 dejó un Workbench visualmente completo pero read-only salvo por los
handlers que ya traía `BatchDetailView` (subir, ejecutar pipeline, transferir,
descargar ZIP, eliminar página, eliminar lote). El operador no puede editar
páginas: no hay rotación, ni edición manual de barcodes, ni toggles de flags,
ni reordenado, ni log visible.

Esta Fase 3 cierra las seis features que faltan para igualar la operativa del
Workbench desktop.

## Objetivos

1. Añadir **rotación 90°/180°/270°** destructiva sobre la imagen, con ajuste automático de las coordenadas de los barcodes existentes.
2. Mostrar **overlays de fields** (valores con coords `{x,y,w,h,value}`) sobre la imagen del visor, con toggle independiente del toggle de barcodes.
3. Habilitar **edición manual de barcodes**: añadir (modal valor + symbology) y eliminar (× por fila con confirm).
4. Permitir **marcar/desmarcar páginas** como `is_excluded` y como `needs_review`, **eliminar la página actual** y **eliminar desde la página actual hasta el final**, todo vía menú contextual (right-click) sobre la miniatura.
5. **Reordenar páginas** arrastrando miniaturas dentro del `ThumbnailPanel`.
6. **Tab Log** funcional en el `MetadataPanel`: stream en vivo de eventos WS + errores persistidos de `processing_errors_json` y `script_errors_json` al cargar.
7. **Bloquear todas las ediciones** mientras el lote está en ejecución (`running` o `transferring`).

## No objetivos

- Shortcuts de teclado dedicados (F5 = re-procesar, Ctrl+T = transferir, Ctrl+W = cerrar lote, Ctrl+R = rotar, Delete = eliminar). Fase 4.
- Eventos lifecycle nuevos (`on_navigate_*`, `on_key_event`, `on_page_changed`, `on_batch_loaded`). Fase 4.
- Drag-drop de ficheros externos sobre el panel de miniaturas. Existe botón "Subir" dedicado.
- Multi-selección de miniaturas (Shift/Ctrl+click) para reorder o borrado masivo.
- Dibujo de rectángulo sobre la imagen para asignar coords al añadir un barcode manual.
- Editar valor/symbology/coords de un barcode existente. Sólo añadir y eliminar.
- Persistir el log en tabla dedicada. Los errores ya viven en `Page.processing_errors_json` y `Page.script_errors_json`.
- Añadir una columna `rotation` a `Page`. La rotación sobreescribe la imagen en disco, como en desktop.
- Mobile / responsive.

## Decisiones de diseño

- **Rotación destructiva, como desktop**: `POST /pages/:id/rotate` sobreescribe `image_path` y rota `pos_x/y/w/h` de cada barcode. Consistente con `workbench_window.py:_on_rotate_90`. Sin migración Alembic. `turns ∈ {1,2,3}` aplica N rotaciones de 90° CW.
- **Acciones por página en menú contextual** del thumbnail, no iconos hover ni botones en la toolbar superior. Thumbnail limpio, las 4 acciones caben sin presionar el layout.
- **Dos toggles independientes** de overlays (barcodes y fields) en el `ViewerToolbar`. Persistidos en `localStorage['workbench.overlays']` con defaults `true/true`.
- **Tab Log sin nueva tabla**. Se alimenta de (a) eventos WS del lote en curso, (b) `processing_errors_json` y `script_errors_json` ya persistidos en cada `Page`, (c) acciones locales del usuario (sólo en memoria).
- **`Batch.state` gana dos valores**: `"running"` mientras ejecuta el pipeline y `"transferring"` mientras ejecuta el transfer. Sin migración (la columna es `String(20)`). Los runners los setean en `try/finally` y garantizan un estado terminal (`read`/`error_read`) al salir.
- **Bloqueo de ediciones** si `batch.state in ('running','transferring')`. Cascada desde `WorkbenchView` a todos los hijos vía prop `readOnly`. Los endpoints nuevos también rechazan con 409 para defensa en profundidad.
- **`vue-draggable-plus`** para reordenado de miniaturas. Wrapper mantenido de SortableJS, compatible Vue 3. Alternativa `sortablejs` directa era más código frágil.
- **Semántica optimista con rollback**: las mutaciones (toggle flags, rotate, reorder, delete barcode) actualizan el estado local inmediatamente; si el endpoint falla, se revierte y se muestra toast.
- **Evento WS nuevo `page_updated`**: el backend emite `{type: "page_updated", page_id, action}` tras cada mutación de página para refrescar otros clientes del mismo lote.

## Arquitectura

### Backend

#### Cambios en modelos

- `Page`: sin cambios.
- `Batch.state`: mismo `String(20)`, vocabulario extendido con `"running"` y `"transferring"`.
- `Barcode`: sin cambios. Barcodes manuales se crean con `engine="manual"`, `step_id="manual"`, `symbology="MANUAL"` por defecto (o el valor que elija el usuario), `pos_x=pos_y=pos_w=pos_h=0`.

#### Endpoints nuevos (`web/api/routers/pages.py` y `batches.py`)

| Método | Ruta | Body | Respuesta | Guards |
|---|---|---|---|---|
| `PATCH` | `/api/pages/{page_id}` | `{is_excluded?: bool, needs_review?: bool, review_reason?: str}` | `PageResponse` | tenant, 409 si batch running/transferring |
| `POST` | `/api/pages/{page_id}/rotate` | `{turns: 1\|2\|3}` (default 1) | `PageResponse` | tenant, 409 si batch running/transferring |
| `POST` | `/api/pages/{page_id}/barcodes` | `{value: str, symbology: str}` | `BarcodeResponse` | tenant, valor no vacío (422), 409 si batch running/transferring |
| `DELETE` | `/api/pages/{page_id}/barcodes/{barcode_id}` | — | `204` | tenant, 404 si el barcode no pertenece a la página, 409 si batch running/transferring |
| `POST` | `/api/batches/{batch_id}/reorder` | `{page_ids: [int]}` | `BatchResponse` | tenant, 409 si running/transferring, 422 si el set no coincide |
| `DELETE` | `/api/batches/{batch_id}/pages/after/{page_id}` | — | `{deleted: int, batch_page_count: int}` | tenant, 404 si `page_id` no pertenece al lote, 409 si running/transferring |

Los endpoints existentes `POST /batches/:id/run` y `POST /batches/:id/transfer` añaden un check 409 si el lote ya está en `running`/`transferring`.

#### Lógica de rotación (`/pages/:id/rotate`)

```python
def rotate_page(page, turns, storage, db):
    img = cv2.imread(page.image_path, cv2.IMREAD_UNCHANGED)
    h, w = img.shape[:2]
    for _ in range(turns):
        img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    cv2.imwrite(page.image_path, img)
    # Actualizar coords barcodes por cada rotación
    for _ in range(turns):
        for bc in page.barcodes:
            old_x, old_y, old_w, old_h = bc.pos_x, bc.pos_y, bc.pos_w, bc.pos_h
            bc.pos_x, bc.pos_y = h - old_y - old_h, old_x
            bc.pos_w, bc.pos_h = old_h, old_w
        h, w = w, h  # dimensiones rotadas para siguiente iteración
    db.commit()
```

La altura y anchura se reasignan por iteración porque cada rotación cambia el sistema de referencia.

#### Lógica de reordenado

```python
def reorder_batch(batch_id, new_order, db):
    pages = db.query(Page).filter(Page.batch_id == batch_id).all()
    existing_ids = {p.id for p in pages}
    if set(new_order) != existing_ids or len(new_order) != len(existing_ids):
        raise HTTPException(422, "page_ids no coincide con el set actual")
    id_to_page = {p.id: p for p in pages}
    for idx, pid in enumerate(new_order):
        id_to_page[pid].page_index = idx
    db.commit()
```

#### Runners (`web/api/tasks/pipeline_runner.py` y `transfer_runner.py`)

Ambos añaden al principio:

```python
batch.state = "running"   # o "transferring"
db.commit()
```

Y envuelven la ejecución en `try/finally`:

```python
try:
    # ejecución actual
    batch.state = "read" if not any_error else "error_read"
except Exception:
    batch.state = "error_read"
    raise
finally:
    # garantizar que nunca queda colgado
    if batch.state in ("running", "transferring"):
        batch.state = "error_read"
    db.commit()
```

#### Evento WebSocket nuevo

`/ws/batches/{batch_id}` emite tras cada mutación de página:

```json
{"type": "page_updated", "page_id": 42, "action": "rotated",
 "batch_page_count": 12}
```

`action ∈ {"rotated", "flags", "barcode_added", "barcode_deleted", "deleted", "reordered"}`. Para `reordered` se emite una sola vez con la lista completa en `{new_order: [...]}`.

### Frontend

#### Componentes nuevos

| Archivo | Responsabilidad |
|---|---|
| `components/workbench/LogPanel.vue` | Lista virtualizada de entries con filtro por nivel y auto-scroll. |
| `components/workbench/ThumbnailContextMenu.vue` | Menú contextual flotante con 4 acciones. Posicionado por coords del click. Cierre con ESC / click fuera. |
| `components/workbench/AddBarcodeDialog.vue` | Modal: input valor (obligatorio) + select symbology. |
| `components/workbench/DeleteBarcodeDialog.vue` | Modal de confirmación. |
| `composables/useWorkbenchLog.ts` | Store singleton del log del lote actual. `appendFromEvent(ev)`, `loadPersistedErrors(pages)`, `clear()`, `entries` ref, `filterLevel` ref. |
| `composables/usePageActions.ts` | Todas las mutaciones HTTP con rollback optimista y toast en 409. |
| `composables/useOverlayToggles.ts` | `{showBarcodes, showFields}` con persistencia localStorage. |

#### Componentes modificados

| Archivo | Cambio |
|---|---|
| `components/DocumentViewer.vue` | Props `fields: Record<string, any>`, `showBarcodes: boolean`, `showFields: boolean`. Pinta overlays de fields cuando `value` es dict con `{x,y,w,h,value}`. Estilo DashLine, paleta decalada `+3` respecto barcodes, etiqueta con `nombre: valor`. |
| `components/workbench/ViewerToolbar.vue` | Añade dropdown rotar (90°/180°/270°), toggle barcodes, toggle fields. |
| `components/workbench/ThumbnailPanel.vue` | Integra `vue-draggable-plus`. Emite `reorder(newOrder: number[])` y `contextmenu(pageId, x, y)`. |
| `components/workbench/PageThumbnail.vue` | Badges de estado (⊘ excluida, ⚐ revisión) en esquina inferior-izquierda. |
| `components/workbench/BarcodePanel.vue` | Botón `+` en header, × por fila. Emite `add-barcode`, `delete-barcode(id)`. Prop `readOnly`. |
| `components/workbench/MetadataPanel.vue` | Activa tab **Log** que renderiza `<LogPanel>`. Contador `(N ⚠)` en el label. |
| `views/batches/WorkbenchView.vue` | Handlers nuevos, extiende WS para `page_updated`, `readOnly` computed, carga errores persistidos al montar. |

#### Flujos UI

- **Rotar**: botón dropdown en ViewerToolbar → elige ángulo → POST → WS confirma → imagen recargada con cache-bust `?v=updated_at`.
- **Toggle excluir/revisar**: right-click thumbnail → menú → click → PATCH (optimista, rollback si 409).
- **Eliminar página actual**: menú contextual → DeleteDialog → DELETE `/pages/:id` → quitar del array local → navegar a la siguiente.
- **Eliminar desde aquí**: menú contextual → DeleteDialog "Se eliminarán N páginas" → DELETE `/batches/:id/pages/after/:page_id` → truncar array → navegar a la anterior.
- **Reordenar**: drag sobre ThumbnailPanel → onEnd → POST `/batches/:id/reorder` → si falla rollback.
- **Añadir barcode**: `+` en BarcodePanel → AddBarcodeDialog → POST `/pages/:id/barcodes` → append local.
- **Eliminar barcode**: × en fila → DeleteBarcodeDialog → DELETE → filter local.
- **Toggle overlay**: click en botón ViewerToolbar → actualiza store + localStorage.
- **Bloqueo**: computed `isReadOnly = batch.state in ('running','transferring')` se propaga como prop a todos los hijos editables. Toolbar y menú contextual deshabilitan con tooltip "Procesando…".

## Tab Log

### Modelo de entry

```ts
interface LogEntry {
  id: string          // uuid local para tracking
  timestamp: string   // ISO
  level: 'debug' | 'info' | 'warn' | 'error'
  source: 'pipeline' | 'transfer' | 'script' | 'editor' | 'user'
  message: string
}
```

### Fuentes

1. **WebSocket en vivo**. Mapeo de cada evento a una o más entries:
   - `pipeline_started` → `INFO · pipeline · Pipeline iniciado ({N} páginas)`
   - `page_processed` → `DEBUG · pipeline · Página {i}/{N} procesada`
   - `page_error` → `ERROR · pipeline · Página {i}: {error_msg}`
   - `pipeline_completed` → `INFO · pipeline · Pipeline completado en {Δs} s`
   - `transfer_started|page|completed|error|aborted` → análogo con `source: 'transfer'`
   - `page_updated` → `DEBUG · editor · Página {id}: {action}`
2. **Errores persistidos al cargar el batch**. Por cada página:
   - `processing_errors_json` → entries `ERROR · pipeline · Página {i}: {err}` con timestamp = `page.updated_at`.
   - `script_errors_json` → entries `WARN · script · Página {i} paso {step_id}: {err}`.
3. **Acciones locales del usuario** (opcional, no persistidas): `INFO · user · Rotada página 3`, `INFO · user · Reordenado`, etc.

### UI

- Header: select filtro nivel mínimo, botón `🗑 Limpiar`, contador `N entries`.
- Body: lista con color por nivel (coherente con paleta Catppuccin: subtext1 · text · yellow · red), mono-space, auto-scroll al fondo cuando el usuario no ha scrolleado manualmente hacia arriba.
- Empty state: "Sin eventos aún. Los mensajes aparecerán aquí mientras procesas el lote."
- Virtualización con `vue-virtual-scroller` sólo si >500 entries.

### Integración con MetadataPanel

El tab ya existe estructuralmente desde Fase 2 (deshabilitado). Se activa y su label muestra contador de warnings+errors: `Log (3 ⚠)`.

## Tests

### Backend (pytest, `web/tests/`)

| Archivo | Cobertura |
|---|---|
| `test_pages_patch.py` | Toggle flags; 404 tenant ajeno; 409 running/transferring. |
| `test_pages_rotate.py` | Rota imagen en disco (dimensiones invertidas); rota coords de barcodes (90°/180°/270°); 409 running. |
| `test_pages_barcodes.py` | POST crea con symbology; DELETE 204; 404 FK cruzado; valor vacío 422. |
| `test_batches_reorder.py` | Reorden correcto; 422 si `page_ids` no coincide; 409 running. |
| `test_batches_delete_after.py` | Elimina bulk; `batch.page_count` actualizado; cuenta coherente. |
| `test_pipeline_runner_state.py` | Arranque → `running`; fin OK → `read`; excepción → `error_read`; finally garantiza estado terminal. |
| `test_transfer_runner_state.py` | Mismo patrón para transfer → `transferring` → `read`. |
| `test_ws_page_updated.py` | Cada mutación emite `page_updated` con `action` correcto. |

### Frontend (vitest)

| Archivo | Cobertura |
|---|---|
| `usePageActions.test.ts` | Cada mutación llama endpoint correcto; rollback en 409; toast de error. |
| `useWorkbenchLog.test.ts` | Carga desde pages con errores JSON; dedupe por `timestamp+message`; clear; filter por nivel. |
| `useOverlayToggles.test.ts` | Defaults; persistencia; cambios notificados. |
| `LogPanel.test.ts` | Render; filtro; auto-scroll; contador; empty state. |
| `ThumbnailContextMenu.test.ts` | Posición; 4 acciones; cierra con ESC y click fuera; deshabilitado si readOnly. |
| `BarcodePanel.test.ts` (extender) | Botón `+`; × por fila; emits correctos; modo readOnly. |
| `AddBarcodeDialog.test.ts` | Render; validación (valor no vacío); submit. |
| `DeleteBarcodeDialog.test.ts` | Render; confirm emite; cancel cierra. |
| `DocumentViewer.test.ts` (extender) | Overlays fields con `{x,y,w,h,value}`; toggles barcodes/fields. |
| `ThumbnailPanel.test.ts` (extender) | Right-click emite contextmenu; drag reorder emite evento. |
| `PageThumbnail.test.ts` (extender) | Badges ⊘ y ⚐ cuando corresponde. |
| `WorkbenchView.test.ts` (extender) | readOnly por `batch.state`; carga errores persistidos al montar; handler WS `page_updated` actualiza estado. |

### QA manual (Playwright visual)

- Los 6 flujos en tema claro y oscuro.
- Recarga a mitad de un pipeline en curso: verifica que el read-only persiste.
- Colisión: disparar rotate mientras pipeline corre → 409 + toast.

## Librerías nuevas

- `vue-draggable-plus@^0.5.x` (~30 KB, wrapper Vue 3 de SortableJS).

## Archivos que se crean o modifican

### Backend
- `web/api/routers/pages.py` (extendido)
- `web/api/routers/batches.py` (extendido)
- `web/api/tasks/pipeline_runner.py` (state + try/finally)
- `web/api/tasks/transfer_runner.py` (state + try/finally)
- `web/api/routers/ws.py` (nuevo evento `page_updated`)
- `web/api/schemas/page.py` (schemas de request/response nuevos)
- `web/tests/test_pages_*.py`, `test_batches_*.py`, `test_*_runner_state.py`, `test_ws_page_updated.py`

### Frontend
- `web/frontend/src/components/workbench/LogPanel.vue`
- `web/frontend/src/components/workbench/ThumbnailContextMenu.vue`
- `web/frontend/src/components/workbench/AddBarcodeDialog.vue`
- `web/frontend/src/components/workbench/DeleteBarcodeDialog.vue`
- `web/frontend/src/composables/useWorkbenchLog.ts`
- `web/frontend/src/composables/usePageActions.ts`
- `web/frontend/src/composables/useOverlayToggles.ts`
- `web/frontend/src/components/DocumentViewer.vue` (extender)
- `web/frontend/src/components/workbench/ViewerToolbar.vue` (extender)
- `web/frontend/src/components/workbench/ThumbnailPanel.vue` (extender)
- `web/frontend/src/components/workbench/PageThumbnail.vue` (extender)
- `web/frontend/src/components/workbench/BarcodePanel.vue` (extender)
- `web/frontend/src/components/workbench/MetadataPanel.vue` (extender)
- `web/frontend/src/views/batches/WorkbenchView.vue` (extender)
- Tests vitest correspondientes

## Riesgos y mitigaciones

- **Race condition run vs editar**: mitigado con (a) `batch.state` persistido, (b) check 409 en endpoints, (c) bloqueo UI propagado. Si aún así se cuela una acción, el 409 + toast es recuperable.
- **Estado `running` colgado** tras crash del worker: el `try/finally` en runners fuerza estado terminal. Pensable un comando de mantenimiento que resetee estados `running` al arrancar FastAPI, pero es fuera de scope.
- **Coords barcodes tras N rotaciones**: la fórmula se aplica secuencialmente con reasignación de `h/w` por iteración; cubierto por test explícito con tres escenarios (1/2/3 turns).
- **Log explota**: >10k entries degradan. Cutoff agresivo de 5000 (igual que desktop) + virtualización si >500.
- **Reorder con páginas añadidas concurrentemente** (otro usuario sube): el 422 del endpoint detecta desync de `page_ids` y el frontend recarga.

## Estimación

~15 commits backend + ~25 commits frontend + tests. 3-5 días, coherente con el rango previsto para Fase 3 en el informe del 2026-04-22.

## Próximos pasos

Tras aprobar esta spec, se genera el plan de implementación con `superpowers:writing-plans`, que descompone la fase en tasks secuenciales aptas para `subagent-driven-development`. Fase 4 queda pendiente de iniciarse al cerrar ésta.
