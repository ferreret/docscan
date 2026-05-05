# Workbench web — Fase 4 (diseño)

**Fecha**: 2026-04-24
**Rama**: `feature/web`
**Estado previo**: Fase 3 cerrada con QA visual validado. 172 backend + 324
frontend tests passing.

## Objetivo

Cerrar el Workbench web añadiendo:

1. **Eventos lifecycle** que hoy solo existen en desktop o en el
   `VerificationPanel` (`on_navigate_prev`, `on_navigate_next`, `on_key_event`,
   `on_page_changed`, `on_batch_loaded`), disponibles como eventos
   server-side ejecutables por scripts Python desde el configurador web.
2. **Atajos de teclado** para las acciones más frecuentes del workbench,
   adaptados al navegador (sin chocar con teclas reservadas por Chrome/Firefox).
3. **Modal de ayuda** (`?`) con la lista completa de atajos.

**Fuera de alcance** (ver "No-objetivos"): cambios en desktop, equivalente web
del `VerificationPanel`, persistencia de preferencias de shortcuts por
usuario, macros grabables.

## No-objetivos

- **No se toca el código desktop**. Los dos eventos `on_page_changed` y
  `on_batch_loaded` se añaden únicamente al catálogo web. En desktop siguen
  existiendo solo como métodos del `VerificationPanel`. Una futura v0.1.1
  desktop los promocionará.
- **No se implementa `VerificationPanel` web**. Sigue siendo funcionalidad
  exclusiva de desktop; en web, para validación custom se usa
  `on_transfer_validate` (ya existente) y los nuevos eventos.
- **No hay cheatsheet editable por el usuario**. El catálogo de shortcuts es
  fijo; no se exponen preferencias por usuario/tenant.
- **Los scripts no pueden crear UI**. Los eventos son server-side puros; el
  único canal hacia la UI es el `EventResult` (fields_updated, logs, cancel,
  target_page_id).

## Decisiones clave

- **5 eventos nuevos en el catálogo web**: `on_batch_loaded`,
  `on_navigate_prev`, `on_navigate_next`, `on_page_changed`, `on_key_event`.
  Todos ejecutan scripts Python server-side reutilizando `ScriptEngine`.
- **Modelo de ejecución híbrido**:
  - **Bloqueantes** (el frontend `await`ea la respuesta): `on_batch_loaded`,
    `on_navigate_prev`, `on_navigate_next`. Pueden cancelar o redirigir.
  - **Fire-and-forget** (el frontend no espera): `on_page_changed`,
    `on_key_event`. Solo efectos laterales.
- **Atajos de teclado con teclas simples** (sin `Ctrl`), activos solo cuando
  ningún `input`/`textarea`/`contenteditable`/`[role=dialog]` tiene el foco.
  Las teclas que el navegador reserva (`Ctrl+T/W/R/P/F`) no se tocan.
- **Cheatsheet modal** accesible con `?` o `h`.
- **Solo-web**: ningún cambio en `app/`. El catálogo TS (`events-catalog.ts`)
  divergirá temporalmente del Python (`EVENT_NAMES`); se acepta.

## Arquitectura

### Backend

**Nuevo endpoint**:

```
POST /api/batches/{batch_id}/events/{event_name}
```

**Request (`EventFireIn`)**:

```python
class EventFireIn(BaseModel):
    page_id: int | None = None     # opcional; requerido para on_page_changed
    key: str | None = None         # requerido para on_key_event
    extra: dict[str, Any] = {}     # payload libre
```

**Response (`EventResult`)**:

```python
class EventResult(BaseModel):
    executed: bool                 # False si el script no está definido
    result: Any = None             # retorno crudo del script
    cancel: bool = False           # para on_navigate_*, indica no avanzar
    target_page_id: int | None = None   # redirección de navegación
    fields_updated: dict[str, Any] = {}         # page.fields que cambiaron
    batch_fields_updated: dict[str, Any] = {}   # batch.fields que cambiaron
    logs: list[dict[str, str]] = []             # [{level, message}]
    error: str | None = None       # stacktrace short si el script lanzó
```

**Semántica del retorno del script**:

| Return del script | Se mapea a |
|---|---|
| `None` o `True` | `{executed: true}` sin cambios |
| `False` | `{executed: true, cancel: true}` |
| `dict` | los campos del dict se copian a `EventResult` (`cancel`, `target_page_id`, etc.) |
| lanza `Exception` | `{executed: true, error: str(e)}` |

**Validaciones**:

- `batch_id` pertenece al tenant del usuario → 404 si no.
- `event_name` en la lista válida: `{on_batch_loaded, on_navigate_prev,
  on_navigate_next, on_page_changed, on_key_event}`. Si no → 400.
- **No se aplica `ensure_batch_mutable`**. Los eventos lifecycle pueden
  ejecutarse incluso con `batch.state ∈ {running, transferring}`: el script
  es responsabilidad del usuario y puede querer reaccionar precisamente en
  esos estados (p. ej. `on_batch_loaded` al entrar al workbench mientras se
  ejecuta un pipeline arrancado por otro equipo).
- Si el evento requiere `page_id` (`on_navigate_prev/next`, `on_page_changed`)
  y viene `null` → 422.
- Si el evento es `on_key_event` y falta `key` → 422.
- Timeout de script: 5 s. Si excede → `{error: "timeout"}`.

**Implementación**:

- `web/api/routers/events.py`: el router.
- `web/api/schemas/event.py`: los schemas.
- `web/api/services/event_dispatcher.py`: carga `events_json` del application
  del batch, compila el script (cache por `{app_id, event_name,
  app.updated_at}`), construye `app_ctx`/`batch_ctx`/`page_ctx`, invoca
  `ScriptEngine.run_event`, mapea el retorno a `EventResult`, persiste
  `fields_updated`/`batch_fields_updated` en BD.

### Frontend

**Composable `useWorkbenchEvents(batchId)`**
(`web/frontend/src/composables/useWorkbenchEvents.ts`):

- `fireSync(name, extra): Promise<EventResult>` — POST y `await`ea.
- `fireAsync(name, extra): void` — POST sin `await`; errores se loggean en el
  log panel (`useWorkbenchLog().appendFromEvent`).
- Ambos aplican automáticamente al store: si `fields_updated` no está vacío,
  hacen `store.patchPageFields(page_id, fields_updated)`; si
  `batch_fields_updated` no vacío, `store.patchBatchFields(...)`. Los logs
  del script se añaden al log panel.
- Cache corto (100 ms) en `fireAsync` para evitar doble dispatch si el
  `currentPage` cambia dos veces en el mismo frame.

**Composable `useWorkbenchShortcuts(handlers, isReadOnly)`**
(`web/frontend/src/composables/useWorkbenchShortcuts.ts`):

- `onMounted`: `document.addEventListener('keydown', onKey, { capture: true })`.
- `onUnmounted`: `removeEventListener`.
- `onKey(event)`:
  1. Si `event.target` cumple `{tagName in [INPUT, TEXTAREA, SELECT] ||
     isContentEditable || closest('[role=dialog]')}`, abortar (dejar al
     navegador).
  2. Buscar la tecla en el mapa `SHORTCUTS`.
  3. Si mapeada: `event.preventDefault()`, comprobar `isReadOnly` (si la
     acción es de edición, skip silencioso), llamar al handler.
  4. Si NO mapeada y el modificador no es vacío: `fireAsync('on_key_event',
     {key: eventToKeyString(event)})`.
- `SHORTCUTS` es el catálogo reusable importado de
  `web/frontend/src/constants/shortcuts.ts` (usado también por el dialog de
  ayuda para evitar divergencia).

**Componente `ShortcutsHelpDialog.vue`**
(`web/frontend/src/components/workbench/ShortcutsHelpDialog.vue`):

- Modal con overlay, cerrable con `Esc` o click fuera.
- Tabla agrupada por 4 categorías: **Lote**, **Edición**, **Navegación**,
  **Zoom**. Cada fila: `<kbd>R</kbd> — Rotar página actual`.
- Props: `isOpen: boolean`, emite `close`.
- Mismo estilo que `AddBarcodeDialog.vue`.

**Cambios en `WorkbenchView.vue`**:

- `onMounted` (después de cargar batch y pages):
  ```ts
  const res = await events.fireSync('on_batch_loaded')
  if (res.cancel) { toast.error('Carga de lote cancelada por script'); goBack(); return }
  ```
- `watch(currentPage)`: `events.fireAsync('on_page_changed', {page_id})` cuando
  cambia.
- Navegación prev/next (botones y teclas ←/→):
  ```ts
  async function goPrev() {
    const res = await events.fireSync('on_navigate_prev', {page_id: current.id})
    if (res.cancel) return
    if (res.target_page_id) goTo(res.target_page_id)
    else defaultPrev()
  }
  ```
- Nuevo `helpDialogOpen` ref, controlado por el shortcut `?` y un botón "?"
  nuevo en la toolbar.
- `useWorkbenchShortcuts` inyectado con los handlers concretos (rotar,
  marcar, excluir, reprocesar, insertar barcode, eliminar, ejecutar
  pipeline, transferir, cerrar, zoom in/out, fit, zoom 100, prev, next,
  siguiente revisión, ayuda).

### Catálogo de eventos (frontend)

`web/frontend/src/api/events-catalog.ts` añade 5 `EventDefinition`s:

- `on_batch_loaded` — signature: `def on_batch_loaded(app, batch)`, contextVars
  `[app, batch, log, http]`. Puede retornar dict con `cancel`.
- `on_navigate_prev` / `on_navigate_next` — signature:
  `def on_navigate_prev(app, batch, page)`, contextVars incluye `page`.
  Puede retornar `{cancel, target_page_id}`.
- `on_page_changed` — signature: `def on_page_changed(app, batch, page)`.
- `on_key_event` — signature: `def on_key_event(app, batch, key)`.

El test `tests/api/events-catalog.test.ts` se actualiza: esperar 9 eventos,
añadir afirmaciones para los 5 nuevos.

## Mapping de shortcuts

Activos solo cuando no hay input/textarea/dialog con foco. Durante
`batch.state in {running, transferring}`, los de categoría "Edición" son
no-op silencioso; el resto funciona.

### Lote
| Tecla | Acción |
|---|---|
| `F5` | Ejecutar pipeline |
| `T` | Transferir lote |
| `W` o `Esc` | Cerrar lote (volver a lista) |
| `?` o `h` | Abrir modal de ayuda |

### Edición
| Tecla | Acción |
|---|---|
| `R` | Rotar página actual 90° CW |
| `M` | Toggle marca de revisión |
| `X` | Toggle excluida |
| `P` | Reprocesar pipeline de la página actual |
| `B` | Insertar barcode manual (abre dialog) |
| `Delete` | Eliminar página actual |

### Navegación
| Tecla | Acción |
|---|---|
| `←` / `→` | Página anterior / siguiente |
| `Shift+→` | Siguiente con marca de revisión |
| `Ctrl+G` | Ejecutar `on_navigate_script` si existe |

### Zoom
| Tecla | Acción |
|---|---|
| `0` | Zoom 100% |
| `+` / `-` | Zoom in / out |
| `F` | Fit to page |

**Teclas no-mapeadas con modificador**: si `on_key_event` está definido en
`events_json`, se envía como fire-and-forget con `{key: 'Ctrl+Alt+L'}`.

**Teclas reservadas por el navegador que no tocamos**: `Ctrl+T`, `Ctrl+W`,
`Ctrl+R`, `Ctrl+P`, `Ctrl+F`, `Ctrl+N`, `Ctrl+Tab`.

## Edge cases

- **F5 vs refresh del navegador**: `preventDefault()` en el handler de
  captura. El listener se registra con `capture: true` para ganar al
  navegador.
- **Doble dispatch de `on_page_changed`**: cache 100 ms en `fireAsync`.
- **Eventos durante running/transferring**: todos los eventos lifecycle se
  permiten en cualquier estado del batch. El script decide si hace algo o no.
- **Timeout del script**: 5 s por defecto. Configurable en una fase futura
  mediante un campo en `application.ai_config_json` (aún no).
- **Shortcut con modal abierto**: el modal coloca `role=dialog` y es tapado
  por el filtro de foco del composable.
- **Pérdida de foco al abrir dialog de ayuda**: al cerrar, foco vuelve al
  último thumbnail activo (`ref` guardado al abrir).
- **Script que no respeta la signature**: `ScriptEngine.run_event` ya filtra
  argumentos por introspección con `inspect.signature`; si el script define
  solo `def on_batch_loaded(app)`, se le pasa solo `app`.

## Tests

**Backend** (`tests/test_web_api.py`, nueva clase `TestEventsFire`):

1. `test_fire_script_no_definido_devuelve_executed_false`
2. `test_fire_on_batch_loaded_devuelve_executed_true_result_none`
3. `test_fire_on_navigate_prev_con_cancel_true`
4. `test_fire_on_navigate_next_con_target_page_id`
5. `test_fire_on_page_changed_aplica_fields_updated_en_bd`
6. `test_fire_on_key_event_recibe_key_en_el_script`
7. `test_fire_script_lanza_excepcion_devuelve_error`
8. `test_fire_script_timeout_5s_devuelve_error_timeout`
9. `test_fire_batch_otro_tenant_404`
10. `test_fire_event_name_no_valido_400`
11. `test_fire_on_batch_loaded_permitido_durante_running`
12. `test_fire_on_page_changed_permitido_durante_running`
13. `test_fire_on_navigate_prev_sin_page_id_422`
14. `test_fire_on_key_event_sin_key_422`

**Frontend**:

- `tests/composables/useWorkbenchEvents.test.ts` — 8 tests: `fireSync` OK,
  `fireSync` con cancel, `fireSync` con target_page_id, `fireAsync` no
  espera, apply de `fields_updated`, apply de `batch_fields_updated`, cache
  100 ms, manejo de error.
- `tests/composables/useWorkbenchShortcuts.test.ts` — 12 tests: cada tecla
  mapeada dispara handler, filtro INPUT/TEXTAREA/SELECT/contenteditable/
  dialog, readOnly cascade oculta edición pero permite navegación, fallback
  `on_key_event` con modificador, sin fallback si solo tecla simple,
  cleanup en onUnmounted.
- `tests/components/workbench/ShortcutsHelpDialog.test.ts` — 4 tests: abre
  con `?`, cierra con Esc, muestra las 4 categorías, tabla accesible.
- `tests/views/batches/WorkbenchView.test.ts` — extender con 5 tests:
  `on_batch_loaded` al mount, `on_page_changed` al cambiar de página, F5
  dispara pipeline, ? abre modal, `on_navigate_prev` con cancel no navega.

**Métricas objetivo**: de 172 backend + 324 frontend a **~186 backend +
~353 frontend = ~539 web passing** (+30 web). Desktop 849 sin cambios.

## Estructura de archivos

### Nuevos

- `web/api/routers/events.py`
- `web/api/schemas/event.py`
- `web/api/services/event_dispatcher.py`
- `web/frontend/src/composables/useWorkbenchEvents.ts`
- `web/frontend/src/composables/useWorkbenchShortcuts.ts`
- `web/frontend/src/components/workbench/ShortcutsHelpDialog.vue`
- `web/frontend/src/constants/shortcuts.ts`

### Modificados

- `web/api/main.py` — registrar router.
- `web/api/services/event_dispatcher.py` — puede compartir con los
  dispatchers existentes de `pipeline_runner.py` y `transfer_runner.py` si
  se detecta duplicación de lógica (candidato a refactor incremental).
- `web/frontend/src/api/events-catalog.ts` — 5 eventos nuevos.
- `web/frontend/src/views/batches/WorkbenchView.vue` — wiring completo.
- `web/frontend/tests/api/events-catalog.test.ts` — afirmaciones nuevas.
- `tests/test_web_api.py` — clase `TestEventsFire`.

## Plan de ejecución sugerido

Orden propuesto para el plan TDD (detalle exacto lo redacta el skill
`writing-plans`):

1. Backend: schema → dispatcher → router → tests.
2. Frontend composables: `useWorkbenchEvents` → tests.
3. Frontend shortcuts: `useWorkbenchShortcuts` + `constants/shortcuts.ts`
   → tests.
4. Componente `ShortcutsHelpDialog` → tests.
5. Catálogo `events-catalog.ts` actualizado + test.
6. Integración en `WorkbenchView` → tests.
7. QA visual rápido con Playwright (5 acciones clave).
8. Informe de progreso y push.

## Riesgos

- **Flakiness con timeout del script**: el timeout de 5 s puede ser
  insuficiente para scripts que hagan HTTP a servicios externos. La política
  del primer release es "el usuario lo sabrá", pero si en QA se detecta
  queja, hacerlo configurable.
- **Regresión en la UX de navegación**: si un `on_navigate_prev` rota o
  hace algo lento, el usuario percibe la latencia en cada clic. Mitigación:
  spinner en el botón de navegación mientras se ejecuta (~300 ms).
- **Conflicto con teclas nativas en edit mode**: si en el futuro se añade
  edición inline de campos, las teclas R/M/X podrían colisionar. El filtro
  de foco cubre el caso genérico.
- **Catálogo TS divergente del Python**: desktop no añadirá estos 2 eventos
  hasta v0.1.1. Los usuarios que abran el mismo `application.events_json`
  en el configurador desktop verán esos scripts como "unknown". Mitigación:
  cuando sea el momento de v0.1.1, recordar que desktop también debe
  añadirlos (anotado en MEMORY como follow-up).
