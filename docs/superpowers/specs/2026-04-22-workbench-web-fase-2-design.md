# Workbench web — Fase 2 (base)

**Fecha**: 2026-04-22
**Estado**: aprobado, pendiente plan de implementación
**Sub-proyecto**: 2 de 4 del Workbench web

## Contexto

El Workbench Qt (`app/ui/workbench/`) ofrece la operativa diaria para procesar lotes en desktop: layout multi-panel con miniaturas, visor con overlays, panel de barcodes y formulario de campos custom del lote. La web actual de DocScan Studio tiene `BatchDetailView.vue` que es una vista de gestión single-column (botones de acción + cards de info + lista plana de miniaturas) — funcional pero muy distinta del Workbench desktop.

Esta es la **Fase 2** del sub-proyecto Workbench web, que se descompone en cuatro fases secuenciales:

1. ✅ Sistema de tema global (cerrado el 2026-04-22)
2. **Workbench base** (esta spec)
3. Workbench polish (overlays fields, rotación, Log, edición barcodes, edición páginas, drag-drop)
4. Shortcuts + 4 eventos lifecycle nuevos

La Fase 2 reemplaza `BatchDetailView.vue` por un Workbench multi-panel equivalente al desktop, sin features avanzadas. La fase asume que la Fase 1 (tema global con paleta dual) está completada.

## Objetivos

- Sustituir `BatchDetailView.vue` por un Workbench multi-panel: miniaturas izda, visor central, panel dcha con barcodes (arriba) y formulario de lote (abajo).
- Mantener TODA la funcionalidad de `BatchDetailView` actual (subir, ejecutar pipeline, transferir, descargar ZIP, eliminar página, eliminar lote, listeners WebSocket, auto-transfer).
- Visor con zoom/pan/overlays barcode (reutiliza `DocumentViewer.vue`) más toolbar flotante con botones explícitos.
- Miniaturas con bordes coloreados según los 6 estados `PageState` del desktop.
- Navegación con ←→ entre páginas.
- Persistencia de tamaños de splitter en localStorage.
- Tab Lote con campos custom editables (PATCH al guardar).
- Coherente con el tema dual de Fase 1: ambos modos legibles.

## No objetivos

- **Tab Log** con stream WebSocket en tiempo real (Fase 3).
- Overlays de fields/coords OCR (Fase 3).
- Rotación de página, edición de barcodes manual, reordenado drag-drop, marcar excluida/revisión desde UI (Fase 3).
- Shortcuts de teclado más allá de ←→: F5, Ctrl+T, Ctrl+W (Fase 4).
- Eventos lifecycle `on_navigate_*`, `on_key_event`, `on_page_changed`, `on_batch_loaded` (Fase 4).
- Mobile / responsive (Workbench es interfaz desktop-first; ancho mínimo aceptable ~1280px).
- Migración de tests E2E (mantener QA Playwright manual hasta Fase 4).

## Arquitectura

`WorkbenchView.vue` orquesta un layout de tres paneles redimensionables (vue-splitpanes) con un toolbar superior. Componentes hijos puramente presentacionales reciben datos vía props y emiten eventos. Estado y side effects (HTTP, WebSocket, localStorage de layout) viven en `WorkbenchView` y composables (`usePageState`, `useWorkbenchLayout`).

### Layout

```
┌─────────────────────────────────────────────────────────────┐
│ ← Lote #X    [Subir] [▶ Pipeline] [↗ Transfer] [↓ ZIP] [🗑] │  WorkbenchToolbar
├──────┬──────────────────────────────┬───────────────────────┤
│      │                              │  BarcodePanel         │
│ Thum │  DocumentViewer              │  ● 12345 EAN motor1   │
│ bnai │  + ViewerToolbar (flotante)  │  ● ABCD QR motor2     │
│ lPan │                              ├───────────────────────┤  ← splitter horiz.
│ el   │                              │  MetadataPanel (Lote) │
│      │                              │  Cliente: ____        │
│      │                              │  Fecha:   ____        │
└──────┴──────────────────────────────┴───────────────────────┘
   ↑ splitter vert.    ↑ splitter vert.
```

Defaults: columnas [15, 55, 30], split horizontal derecha [50, 50]. Persistencia en `localStorage['workbench.layout']`.

### Componentes nuevos

| Archivo | Responsabilidad |
|---|---|
| `views/batches/WorkbenchView.vue` | Reemplaza `BatchDetailView.vue`. Orquesta layout, estado batch/pages, eventos teclado, listeners WS pipeline+transfer. |
| `components/workbench/WorkbenchToolbar.vue` | Top toolbar: nombre lote + botones acción. |
| `components/workbench/ThumbnailPanel.vue` | Panel izda scrollable. Lista de `<PageThumbnail>`. Emite `select`. |
| `components/workbench/PageThumbnail.vue` | Miniatura individual: imagen + borde coloreado por PageState + footer con #N + iconos ✓/!/×. |
| `components/workbench/BarcodePanel.vue` | Panel dcha-arriba. Tabla 5 cols + contadores. View-only en Fase 2. |
| `components/workbench/MetadataPanel.vue` | Panel dcha-abajo. Tab UI preparada (Lote activa, Log estructura preparada para Fase 3). Form dinámico de campos custom. |
| `components/workbench/ViewerToolbar.vue` | Toolbar flotante del visor: zoom in/out/100%/fit + indicador %. |
| `composables/usePageState.ts` | `determinePageState(page)` con 6 estados y prioridad UI igual que desktop. |
| `composables/useWorkbenchLayout.ts` | `useWorkbenchLayout()` → `{ sizes, setSizes }`. Persistencia localStorage. |

### Modificaciones

| Archivo | Cambio |
|---|---|
| `components/DocumentViewer.vue` | Añadir métodos públicos `zoomIn()`, `zoomOut()`, `resetView()`, `fitToViewport()` exponer via `defineExpose`. Sin cambios visuales — el toolbar es un componente externo. |
| `router/index.ts` | Cambiar el componente de la ruta `/batches/:id` de `BatchDetailView.vue` a `WorkbenchView.vue`. |
| `package.json` | Añadir dependencia `splitpanes` (versión Vue 3 compatible). |

### Eliminaciones

| Archivo | Razón |
|---|---|
| `views/batches/BatchDetailView.vue` | Reemplazado por `WorkbenchView.vue`. |

(Si los tests existentes referencian `BatchDetailView`, actualizar imports a `WorkbenchView`. Si no hay test específico, simplemente borrar el fichero.)

## PageState (composable `usePageState`)

Replica del enum del desktop con prioridad UI:

```ts
type PageState =
  | 'excluded'           // rojo  — página marcada como excluida
  | 'needs_review'       // rojo  — flag needs_review=true
  | 'separator_barcode'  // naranja — barcode con role=separator
  | 'has_fields'         // azul  — index_fields_json no vacío
  | 'barcode_no_role'    // verde — tiene barcodes pero sin role asignado
  | 'no_recognition'     // gris  — pipeline_processed=false o sin barcodes/fields
```

Función `determinePageState(page: PageResponse): PageState` con orden:
1. Si `page.is_excluded` → `'excluded'`
2. Si `page.needs_review` → `'needs_review'`
3. Si algún barcode tiene `role === 'separator'` → `'separator_barcode'`
4. Si `index_fields_json` parsea a objeto no vacío → `'has_fields'`
5. Si tiene barcodes (todos sin role) → `'barcode_no_role'`
6. En cualquier otro caso → `'no_recognition'`

Mapping de color (Tailwind) usado por `<PageThumbnail>`:

```ts
const STATE_COLOR: Record<PageState, string> = {
  excluded: 'border-danger',
  needs_review: 'border-danger',
  separator_barcode: 'border-warning',
  has_fields: 'border-primary',
  barcode_no_role: 'border-success',
  no_recognition: 'border-overlay-0',
}
```

## Flujo de datos

```
WorkbenchView (orquestador)
   ├── store.fetchOne(batchId), store.fetchPages(batchId), appStore.fetchOne(appId) en onMounted
   ├── selectedPageIndex (ref number, default 0)
   ├── pages computed (sorted por page_index)
   ├── currentPage computed (pages[selectedPageIndex])
   ├── window keydown listener (Arrow Left/Right → cambia selectedPageIndex con clamp 0..n-1)
   │
   ├── <WorkbenchToolbar :batch :app :running :transferring
   │       @upload @run-pipeline @transfer @download-zip @delete-batch />
   ├── <Splitpanes>
   │   ├── <Pane><ThumbnailPanel :pages :selected="selectedPageIndex"
   │   │           @select="(idx) => selectedPageIndex = idx" /></Pane>
   │   ├── <Pane>
   │   │     <DocumentViewer :imageUrl :barcodes ref="viewerRef" />
   │   │     <ViewerToolbar :zoom-percent="viewerRef?.zoomPercent"
   │   │       @zoom-in="viewerRef.zoomIn()" @zoom-out="viewerRef.zoomOut()"
   │   │       @reset="viewerRef.resetView()" @fit="viewerRef.fitToViewport()" />
   │   │   </Pane>
   │   └── <Pane>
   │       <Splitpanes horizontal>
   │         <Pane><BarcodePanel :barcodes="currentPage?.barcodes ?? []" /></Pane>
   │         <Pane><MetadataPanel :app :batch @save="onSaveMetadata" /></Pane>
   │       </Splitpanes>
   │     </Pane>
   └── </Splitpanes>
```

### Navegación de páginas

- Click en thumbnail → `selectedPageIndex.value = N`
- ArrowLeft → `selectedPageIndex = Math.max(0, selectedPageIndex - 1)`
- ArrowRight → `selectedPageIndex = Math.min(pages.length - 1, selectedPageIndex + 1)`
- Watcher de `currentPage.id` → `store.fetchPage(batchId, currentPage.id)` (lazy: solo si los detalles no están en memoria — el store puede cachearlos).

### Save metadata (Lote)

- `MetadataPanel` mantiene `localFields` (clon mutable de `batch.fields_json` parseado).
- Al editar, `localFields[k] = v` y `hasChanges = true`.
- Click "Guardar" → emit `save` con `localFields`. `WorkbenchView` llama `store.update(batch.id, { fields_json: JSON.stringify(localFields) })`.
- Tras OK: toast success + `originalFields = clon(localFields)`. Tras error: toast error.

### Pipeline / Transfer (preservados de BatchDetailView)

- `onRunPipeline()`, `startTransfer()`, listeners WebSocket, auto-transfer tras `pipeline_completed` si `appStore.current?.auto_transfer === true`. Migrados sin cambios funcionales desde `BatchDetailView.vue`.

## Manejo de errores

- WebSocket falla a abrir → toast error, libera flags `running`/`transferring`. Mismo patrón que hoy.
- `fetchPage` 404 → muestra placeholder en visor: "Imagen no encontrada".
- localStorage bloqueado (splitter sizes) → silencioso, defaults.
- Pipeline error → toast con `event.error`. Estado `error` ref para banner sutil.
- Save metadata error → toast error. NO descarta cambios locales.
- Save metadata sin app cargada → botón Guardar deshabilitado.
- `pages` vacío → ThumbnailPanel muestra empty state ("Sin páginas — usa Subir ficheros").
- `currentPage` undefined → DocumentViewer muestra placeholder neutro.

## Testing

Tests vitest:

| Test file | Tests aprox |
|---|---|
| `composables/usePageState.test.ts` | 7 (uno por estado + casos límite con index_fields_json malformado) |
| `composables/useWorkbenchLayout.test.ts` | 4 (defaults, persistencia, fallback localStorage, sanitización) |
| `components/workbench/PageThumbnail.test.ts` | 6 (render por estado, click select, double-click fit, marca selected, iconos overlay, accesibilidad alt) |
| `components/workbench/ThumbnailPanel.test.ts` | 4 (render lista, empty state, click→emit select, scroll a selected) |
| `components/workbench/BarcodePanel.test.ts` | 5 (5 columnas, contadores total/con-barcode/separadores/revisión, copy a portapapeles, empty state) |
| `components/workbench/MetadataPanel.test.ts` | 7 (render dinámico texto/fecha/lista/numérico, hasChanges, save emit, sin batch_fields → empty, sin app → disable save, validación required) |
| `components/workbench/ViewerToolbar.test.ts` | 5 (4 botones emiten, indicador %, deshabilitado si !viewer ready) |
| `components/workbench/WorkbenchToolbar.test.ts` | 4 (5 botones emiten, deshabilitado durante running/transferring, no Transferir si state!=='read') |
| `views/batches/WorkbenchView.test.ts` | 5 (integración smoke: monta, navega ←→, guarda metadata, recibe WS pipeline_completed, limpieza listeners onUnmounted) |

**Total**: ~47 tests nuevos.

Tests preexistentes que importen `BatchDetailView`: actualizar imports a `WorkbenchView` o eliminar si quedan obsoletos.

## QA visual con Playwright

Tras impl, recorrer:
1. Login con `demo2@demo.com / demo12345`.
2. Abrir un batch con páginas (`/batches/4`).
3. Verificar layout 3 paneles, splitters arrastrables.
4. Click en thumbnail → cambia visor.
5. ←→ teclado → cambia thumbnail seleccionado y visor.
6. Botones zoom/fit funcionan.
7. Editar campo lote → Guardar → toast.
8. Cambiar tema oscuro/claro → coherente.
9. Recargar → tamaños splitter restaurados.

## Restricciones / decisiones tomadas

- **vue-splitpanes** como librería de splitters (decisión del brainstorming).
- **`<html data-theme>` de Fase 1** ya disponible: usar variables semánticas de Tailwind, NUNCA hex hardcoded.
- **DocumentViewer** existente se reutiliza, ampliando con `defineExpose` para que `<ViewerToolbar>` lo controle.
- **6 estados PageState** como desktop (no simplificación).
- **Persistencia layout** en localStorage clave `workbench.layout`.
- **←→ teclado** ya en Fase 2 (no esperar a Fase 4).
- **Solo tab Lote** en MetadataPanel (Log para Fase 3, pero estructura tabs preparada).
- **`BatchDetailView.vue` se elimina** y se reemplaza por `WorkbenchView.vue` en `/batches/:id`.

## Out of scope (Fases siguientes)

- **Fase 3**: tab Log, overlays fields, rotación, edición barcodes manual, eliminar/marcar páginas, reordenado drag-drop.
- **Fase 4**: shortcuts F5/Ctrl+T/Ctrl+W, eventos `on_navigate_*`, `on_key_event`, `on_page_changed`, `on_batch_loaded`.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| `splitpanes` Vue 3 no compatible o con bugs | POC de 30 min antes de empezar implementación. Alternativa: `vue3-resize-panel` o CSS Grid + ResizeObserver custom. |
| `DocumentViewer.zoomIn/Out` requiere refactor mayor | Si la API del componente actual no lo permite con `defineExpose`, plantear refactor pequeño en Task 1 del plan. |
| Migración de WS listeners de BatchDetailView introduce regresión en pipeline+transfer | Tests de integración smoke en `WorkbenchView.test.ts` cubren los listeners con eventos mockeados. |
| Layout 3 paneles se ve apretado en pantallas <1280px | Documentar requisito mínimo. Banner soft "Recomendado 1280px+" si se detecta menos. (Opcional, no bloqueante.) |
| `<MetadataPanel>` con muchos campos custom (10+) → scroll infinito | El panel es scrollable verticalmente. Acceptable. |

## Plan de commits sugerido

1. POC + dependencia `splitpanes` añadida + variables CSS si hace falta
2. Composable `usePageState` + tests
3. Composable `useWorkbenchLayout` + tests
4. Componente `PageThumbnail` + tests
5. Componente `ThumbnailPanel` + tests
6. Componente `BarcodePanel` + tests
7. Componente `MetadataPanel` + tests
8. Componente `ViewerToolbar` + tests + extender `DocumentViewer` con `defineExpose`
9. Componente `WorkbenchToolbar` + tests
10. `WorkbenchView` ensamblado + tests integración
11. Router actualizado + eliminación `BatchDetailView.vue` + smoke pass
12. QA visual Playwright + push final

## Verificación de cierre

- Suite vitest: 100% passing (incluyendo nuevos ~47 tests).
- Typecheck OK.
- QA visual Playwright sobre las 9 verificaciones listadas.
- Sin regresión funcional respecto a `BatchDetailView` (uploads, pipeline, transfer, ZIP, delete).
- Push a `origin/feature/web`.
