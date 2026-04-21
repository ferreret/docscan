# Pestaña Eventos — sub-proyecto 5 del configurador web (diseño)

**Fecha:** 2026-04-21
**Rama:** `feature/web`
**Estado:** aprobado — listo para plan de implementación
**Relación con v4:** extrae el editor CodeMirror de `ScriptStepForm.vue`
a un componente genérico `<CodeEditor>` reutilizable y construye sobre
él la pestaña de Eventos (13 entry points de ciclo de vida).

## 1 · Objetivo

Permitir editar los 13 eventos lifecycle (`on_app_start`, `on_app_end`,
`on_import`, `on_scan_complete`, `on_transfer_validate`,
`on_transfer_advanced`, `on_transfer_page`, `on_navigate_prev`,
`on_navigate_next`, `on_navigate_script`, `on_key_event`,
`init_global`, `verification_panel`) desde la web con paridad funcional
frente al desktop, autocompletado contextual adaptado por evento y una
plantilla inicial con la firma correcta.

**Fuera de scope:**

1. Validación de sintaxis Python en el navegador. Herencia de v4.
2. Ejecución/preview del evento desde la web. El runtime lo dispara el
   Workbench desktop.
3. UI especializada para `verification_panel` — se trata como otro
   evento con plantilla de clase.

## 2 · Arquitectura general

### 2.1 Cambios de alto nivel

- **Backend:** cero cambios. `applications.events_json` ya es string y
  se actualiza vía `PATCH /api/applications/{id}` con el payload
  `{events_json: "..."}`.
- **Refactor v4:** el wrapper CodeMirror de `script-editor/editor.ts`
  y el form `ScriptStepForm.vue` se reorganizan para que **el editor
  sea un componente genérico `<CodeEditor>`** que ambos consumidores
  (ScriptStep + Eventos) usan con sus propios `contextVariables` y
  `snippets`.
- **Frontend nuevo para Eventos:**
  - Catálogo `events-catalog.ts` con los 13 `EventDefinition`.
  - Vista `EventsEditorView.vue` en `/applications/:id/events`.
  - Componente `AppHeader.vue` con sub-navegación por tabs
    (Resumen | Pipeline | Eventos).

### 2.2 Contexto por evento (backend como referencia)

Los eventos se ejecutan vía `script_engine.run_event(...)` con `app` y
`batch` como base. Variables adicionales según firma:

| Evento | Firma efectiva | Variables extra |
| --- | --- | --- |
| `on_app_start` | `(app, batch)` | — |
| `on_app_end` | `(app, batch)` | — |
| `on_import` | `(app, batch)` | — |
| `on_scan_complete` | `(app, batch)` | — |
| `on_transfer_validate` | `(app, batch) -> bool` | — |
| `on_transfer_advanced` | `(app, batch, result)` | `result` |
| `on_transfer_page` | `(app, batch, page, result)` | `page`, `result` |
| `on_navigate_prev` | `(app, batch)` | — |
| `on_navigate_next` | `(app, batch)` | — |
| `on_navigate_script` | `(app, batch)` | — |
| `on_key_event` | `(app, batch, key)` | `key` (str) |
| `init_global` | `(app, batch)` | — |
| `verification_panel` | `class MyVerificationPanel(VerificationPanel)` | `self.api.*` |

## 3 · Componente `<CodeEditor>` genérico

Fichero nuevo: `web/frontend/src/components/CodeEditor.vue` (~230 líneas).

### 3.1 Props / emits

```ts
defineProps<{
  modelValue: string
  contextVariables: ContextVariable[]
  snippets?: Snippet[]                  // omitido → sin menú snippets
  minHeight?: number                    // default 420
  helpPanelStorageKey?: string          // default 'codeEditor.helpPanelOpen'
  disabled?: boolean
}>()
defineEmits<{ 'update:modelValue': [doc: string] }>()
```

### 3.2 Responsabilidades

1. **Lazy-mount** CodeMirror vía `await import('./code-editor/editor')`
   en `onMounted`. Flag `cancelled` + `destroy()` en unmount
   (mismo patrón que v4 post-review).
2. **Emisión**: `update:modelValue` en cada cambio del editor.
3. **No escucha cambios externos** de `modelValue` ni de
   `contextVariables`. Ambos se leen en `onMounted` y se pasan a
   `createEditor`. Si el consumidor necesita sustituir el documento o
   las variables (p. ej. al cambiar de evento en `EventsEditorView` o
   de ScriptStep en el drawer), debe re-montar el componente con
   `:key="currentIdentifier"`. Evita el loop doc-toString ↔ dispatch y
   simplifica el ciclo de vida del `EditorView`.
4. **Snippets**: si `snippets.length > 0`, muestra el dropdown
   "Insertar snippet ▾". Si no, oculto.
5. **Panel de ayuda**: colapsable, persistido en
   `localStorage[helpPanelStorageKey]`. Permite múltiples vistas con
   preferencias independientes (ScriptStep usa una clave, Eventos
   otra).
6. **Autocompletado**: el componente pasa `contextVariables` al
   `createEditor`, que construye los completions desde esa lista
   concreta. Ya no hay import global de `CONTEXT_VARIABLES`.

### 3.3 Cleanup

`onBeforeUnmount`: `cancelled = true` + `editorHandle?.destroy()`.

## 4 · Wrapper `code-editor/editor.ts`

Fichero: `web/frontend/src/components/code-editor/editor.ts` (renombrado
desde `pipeline/forms/script-editor/editor.ts`).

### 4.1 Cambios vs v4

- **Recibe `contextVariables` como argumento** de `createEditor`:
  ```ts
  export interface CreateEditorArgs {
    parent: HTMLElement
    initialDoc: string
    contextVariables: ContextVariable[]
    onChange: (doc: string) => void
  }
  ```
- `TOP_LEVEL_COMPLETIONS` y `MEMBER_COMPLETIONS` ya no son constantes
  globales; se construyen dentro de `createEditor` a partir del
  argumento.
- `buildContextSuggestions(prefix, vars)` gana el segundo parámetro
  para tests directos.
- **Regex de prefijo extendido** para soportar identificadores con
  puntos (`self.api.`). El regex pasa de `(\w+)\.$` a `([\w.]+)\.$`
  y el lookup en el Map usa el identificador completo como clave
  (`self.api`).
- Import de `@/api/script-context-help` **eliminado**: el wrapper queda
  desacoplado del dominio ScriptStep.

### 4.2 API expuesta (sin cambios)

```ts
export function shouldPrefixNewline(line: string): boolean
export function buildContextSuggestions(prefix: string, vars: ContextVariable[]): Completion[]
export async function createEditor(args: CreateEditorArgs): Promise<EditorHandle>

export interface EditorHandle {
  insertAtCursor: (text: string) => void
  destroy: () => void
}
```

## 5 · Catálogo `events-catalog.ts`

Fichero nuevo: `web/frontend/src/api/events-catalog.ts`.

### 5.1 Tipos

```ts
import type { ContextVariable } from './script-context-help'

export interface EventDefinition {
  name: string
  description: string
  signature: string
  template: string
  contextVariables: ContextVariable[]
}
```

### 5.2 Variables compartidas

```ts
const BASE_VARS: ContextVariable[] = [
  { name: 'app',      summary: 'AppContext: id, name.' },
  { name: 'batch',    summary: 'BatchContext: id, state, fields, page_count.' },
  { name: 'log',      summary: 'logger estándar: log.info(...), log.warning(...).' },
  { name: 'http',     summary: 'httpx — http.get(url), http.post(url, json=...).' },
  { name: 're',       summary: 'módulo re de Python.' },
  { name: 'json',     summary: 'módulo json de Python.' },
  { name: 'datetime', summary: 'módulo datetime de Python.' },
  { name: 'Path',     summary: 'pathlib.Path.' },
]

const PAGE_VAR: ContextVariable = {
  name: 'page',
  summary: 'PageContext: imagen y datos extraídos.',
  members: [
    { name: 'image',    description: 'np.ndarray BGR.' },
    { name: 'barcodes', description: 'list[Barcode] con .value, .symbology.' },
    { name: 'ocr_text', description: 'str — OCR acumulado.' },
    { name: 'fields',   description: 'dict[str, Any] — metadatos de la página.' },
    { name: 'flags',    description: 'dict[str, Any] — banderas internas.' },
  ],
}

const RESULT_VAR: ContextVariable = {
  name: 'result',
  summary: 'TransferResult: destino, status, detalles de la transferencia.',
}

const KEY_VAR: ContextVariable = {
  name: 'key',
  summary: 'str — nombre de la tecla pulsada (ej. "F2", "Ctrl+S").',
}

const VERIFICATION_PANEL_VARS: ContextVariable[] = [
  {
    name: 'self.api',
    summary: 'API del panel de verificación (acceso a lote/páginas).',
    members: [
      { name: 'get_page_image',    signature: 'get_page_image(index)',       description: 'Devuelve la imagen np.ndarray de la página.' },
      { name: 'get_page_barcodes', signature: 'get_page_barcodes(index)',    description: 'Lista de barcodes de la página.' },
      { name: 'get_page_ocr_text', signature: 'get_page_ocr_text(index)',    description: 'Texto OCR de la página.' },
      { name: 'get_page_fields',   signature: 'get_page_fields(index)',      description: 'Dict de fields de la página.' },
      { name: 'set_page_field',    signature: 'set_page_field(name, value)', description: 'Actualiza un field de la página actual.' },
      { name: 'get_batch_fields',  signature: 'get_batch_fields()',          description: 'Dict de fields del lote.' },
      { name: 'set_batch_field',   signature: 'set_batch_field(name, value)', description: 'Actualiza un field del lote.' },
      { name: 'navigate_to',       signature: 'navigate_to(index)',          description: 'Navega a la página indicada.' },
      { name: 'log',               signature: 'log(msg)',                    description: 'Loguea un mensaje.' },
    ],
  },
]
```

### 5.3 Entradas

Las 13 entradas siguen la forma:

```ts
{
  name: 'on_app_start',
  description: 'Al abrir la aplicación.',
  signature: 'on_app_start(app, batch)',
  template: `def on_app_start(app, batch):
    """Se ejecuta al abrir la aplicación en el Workbench."""
    pass
`,
  contextVariables: BASE_VARS,
}
```

Variables por evento:

- `on_app_start`, `on_app_end`, `on_import`, `on_scan_complete`,
  `on_transfer_validate`, `on_navigate_prev`, `on_navigate_next`,
  `on_navigate_script`, `init_global` → `BASE_VARS`.
- `on_transfer_advanced` → `[...BASE_VARS, RESULT_VAR]`.
- `on_transfer_page` → `[...BASE_VARS, PAGE_VAR, RESULT_VAR]`.
- `on_key_event` → `[...BASE_VARS, KEY_VAR]`.
- `verification_panel` → `VERIFICATION_PANEL_VARS` (solo, no hereda
  `BASE_VARS` porque el contexto de la clase es diferente).

### 5.4 `verification_panel` (caso especial)

Plantilla:

```python
class MyVerificationPanel(VerificationPanel):
    """Panel de verificación personalizado.

    Métodos sobreescribibles: setup_ui(), on_page_changed(index),
    on_pipeline_completed(index), on_batch_loaded(),
    validate_page(index) -> (bool, str), validate() -> (bool, str), cleanup().
    """

    def setup_ui(self):
        pass
```

Signature: `class MyVerificationPanel(VerificationPanel)`.

## 6 · Vista `EventsEditorView.vue`

Fichero nuevo:
`web/frontend/src/views/applications/EventsEditorView.vue` (~280 líneas).

### 6.1 Ruta y cabecera

- Ruta `/applications/:id/events` con `meta: { requiresAuth: true }`.
- Cabecera compartida con `<AppHeader>` (§7) — título de la app, tabs
  Resumen/Pipeline/Eventos, slot `actions` con los botones de guardar.

### 6.2 Estado local

```ts
const originalEvents = ref<Record<string, string>>({})
const events = ref<Record<string, string>>({})
const currentEventName = ref<string>('on_app_start')
const saving = ref(false)
const saveError = ref<string | null>(null)

const currentEvent = computed(() =>
  EVENT_DEFINITIONS.find((e) => e.name === currentEventName.value)!
)

const hasChanges = computed(() => {
  const keys = new Set([
    ...Object.keys(originalEvents.value),
    ...Object.keys(events.value),
  ])
  for (const k of keys) {
    if ((originalEvents.value[k] ?? '') !== (events.value[k] ?? '')) return true
  }
  return false
})
```

### 6.3 Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│ {{ app.name }}                    [Deshacer] [Guardar cambios]       │
│ Resumen | Pipeline | Eventos                                         │
│                                                                      │
│ ┌─────────────┬────────────────────────────────────────────────────┐ │
│ │ Eventos     │  Código Python                [Insertar snippet ▾] │ │
│ │             │  ┌─────────────────┐  ┌─────────────────────────┐  │ │
│ │ on_app_start│  │                 │  │ Variables               │  │ │
│ │ ● on_app_end│  │  CodeMirror     │  │  app, batch, log, ...   │  │ │
│ │ on_import   │  │  (min 420px)    │  │                         │  │ │
│ │ ● on_scan…  │  │                 │  └─────────────────────────┘  │ │
│ │ ...         │  └─────────────────┘                               │ │
│ │ verification│  Firma: on_app_end(app, batch)                     │ │
│ │             │  Al cerrar la aplicación.                          │ │
│ └─────────────┴────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

- Sidebar `w-64 flex-shrink-0` con los 13 eventos. Cada item muestra
  `●` (verde) si `events[name]?.trim()` no vacío. Item activo
  resaltado con `bg-primary-soft text-primary font-semibold`. Click
  cambia `currentEventName`.
- Panel central: `<CodeEditor :key="currentEventName" ...>` + pie con
  `Firma:` y `description`. El `:key` fuerza remount al cambiar de
  evento, lo que inicializa el editor con el nuevo `modelValue` y las
  nuevas `contextVariables`.

### 6.4 Comportamiento al cambiar de evento

- Al hacer click en un evento `X` en la sidebar:
  - `currentEventName.value = X`.
  - El `<CodeEditor>` recibe como `modelValue` el contenido de
    `events[X]` si existe, o `currentEvent.template` en caso contrario.
  - `update:modelValue` del editor actualiza `events[X]`. **Si el doc
    resultante coincide exactamente con `template`**, no se persiste
    en `events` (no ensucia `hasChanges`).
  - Si el usuario escribe algo que luego deja exactamente el template,
    `events[X]` se borra (consistente con desktop: código vacío
    equivale a "sin evento").

### 6.5 Guardar y deshacer

- **Guardar cambios**: llama a `applicationsStore.update(appId, {
  events_json: JSON.stringify(events.value) })`. En éxito:
  `originalEvents.value = { ...events.value }`; `saveError = null`.
  En error: muestra banner rojo con `err.message`.
- **Deshacer**: `events.value = { ...originalEvents.value }` (sin
  confirm).
- **Navegación fuera con cambios**: `onBeforeRouteLeave` + `beforeunload`
  con `confirm('Hay cambios sin guardar. ¿Salir igualmente?')`.

### 6.6 Fetch inicial

- `onMounted`: `await applicationsStore.fetchOne(appId)`.
- Parse `events_json` con `try/catch`, fallback `{}` si JSON inválido
  (log warning).
- `originalEvents.value = parsed`; `events.value = { ...parsed }`.

## 7 · Componente `AppHeader.vue`

Fichero nuevo: `web/frontend/src/components/AppHeader.vue` (~60 líneas).

### 7.1 Props / slots

```ts
defineProps<{
  appId: number
  appName: string
  description?: string
}>()
// Slot: "actions" para botones específicos de cada vista.
```

### 7.2 Estructura

- Back link a `/applications`.
- `<h1>` con `appName` + `<p>` con descripción (subtext).
- Botones del slot `actions` alineados a la derecha de la cabecera.
- Barra de tabs justo debajo:
  - `<router-link to="/applications/:id">Resumen</router-link>`
  - `<router-link to="/applications/:id/pipeline">Pipeline</router-link>`
  - `<router-link to="/applications/:id/events">Eventos</router-link>`
- Tab activa: usa `exact-active-class` para Resumen (tiene que
  coincidir la ruta exacta) y `active-class` para las otras.
- Estilo activo: `border-b-2 border-primary text-primary font-semibold`.
  Estilo inactivo: `border-b-2 border-transparent text-subtext hover:text-text`.

### 7.3 Uso

- `ApplicationDetailView.vue` usa `<AppHeader>` con slot vacío (o con
  botones "+ Nuevo lote" y "Eliminar"). Ya no renderiza el botón
  "Editar pipeline" (ahora es tab).
- `PipelineEditorView.vue` usa `<AppHeader>` sustituyendo su cabecera
  actual.
- `EventsEditorView.vue` usa `<AppHeader>` con slot = `[Deshacer]
  [Guardar cambios]` (+ indicador de cambios sin guardar).

## 8 · Refactor de `ScriptStepForm.vue`

Tras extraer `<CodeEditor>`, el form se simplifica:

- **Imports**: quita el lazy de `./script-editor/editor`; añade
  `import CodeEditor from '@/components/CodeEditor.vue'` y
  `import { CONTEXT_VARIABLES, SNIPPETS } from '@/api/script-context-help'`.
- **Estado**: elimina `editorHost`, `editorHandle`, `editorError`,
  `cancelled`, `onMounted`, `onBeforeUnmount` relacionados con el
  editor. El `<CodeEditor>` gestiona eso.
- **Template**: sustituye el bloque editor+snippets+help-panel por:
  ```vue
  <CodeEditor
    :key="modelValue.id"
    :model-value="modelValue.script"
    :context-variables="CONTEXT_VARIABLES"
    :snippets="SNIPPETS"
    help-panel-storage-key="scriptEditor.helpPanelOpen"
    :min-height="420"
    @update:model-value="(doc) => patch({ script: doc })"
  />
  ```
  El `:key="modelValue.id"` hereda la responsabilidad que tenía el
  `:key="draft.id"` del drawer (fix I2 de v4): al cambiar entre dos
  ScriptSteps distintos, el CodeEditor se re-monta con el nuevo doc.
  El `:key` del drawer sobre `<ScriptStepForm>` puede mantenerse o
  eliminarse; cubrirlo a nivel de CodeEditor es suficiente.
- **Resultado**: form pasa de ~240 a ~120 líneas. Tests del form se
  mantienen con el mock apuntando a `@/components/CodeEditor.vue`.

## 9 · Tests

### 9.1 Backend

Cero tests nuevos.

### 9.2 Frontend — vitest

#### `tests/CodeEditor.test.ts` (~6 tests)

Mock del wrapper `@/components/code-editor/editor`.

1. Renderiza el editor host. Si `snippets` está vacío, oculta el botón
   "Insertar snippet".
2. Cuando el mock dispara `onChange`, emite `update:modelValue`.
3. Cambios posteriores a `modelValue` NO se propagan al editor
   (el componente solo lee `modelValue` al montar). Verificado
   comprobando que, tras un cambio externo de prop, el mock del
   `view.dispatch` no se llama.
4. Elegir un snippet invoca `editorHandle.insertAtCursor(code)`.
5. Colapsar el panel de ayuda persiste en
   `localStorage[helpPanelStorageKey]` con la clave pasada por prop.
6. Cleanup en unmount: `editorHandle.destroy()` se llama exactamente
   una vez (verificado contra el mock `destroy`). Flag `cancelled`
   impide que un `createEditor` en vuelo deje un handle huérfano.

#### `tests/code-editor/editor.test.ts` (adaptación, 6 tests)

Mover desde `tests/script-editor/editor.test.ts` y actualizar:
- `buildContextSuggestions(prefix, vars)` acepta 2 args.
- Test nuevo: prefijo multi-nivel `'self.api.'` devuelve los miembros
  de `self.api` cuando la lista contiene esa variable con members.

#### `tests/api/events-catalog.test.ts` (~3 tests)

7. `EVENT_DEFINITIONS` tiene exactamente 13 entradas; los nombres
   coinciden con la lista hardcoded que replica `EVENT_NAMES` del
   desktop.
8. Cada `template` empieza con `def <name>(` salvo `verification_panel`
   (empieza con `class `).
9. `verification_panel` expone `self.api` con ≥ 9 miembros incluyendo
   `get_page_image`, `get_page_barcodes`, `navigate_to`, `log`.

#### `tests/views/EventsEditorView.test.ts` (~8 tests)

Con `<CodeEditor>` mockeado por un stub Vue que emite `update:modelValue`.

10. Fetch inicial carga `events_json` y rellena `events`.
11. Sidebar lista los 13 eventos; `on_app_start` seleccionado por
    defecto.
12. Sidebar marca con indicador los eventos con código no vacío.
13. Click en otro evento cambia el `modelValue` pasado a `<CodeEditor>`.
14. Editar en el stub del editor actualiza `events` y dispara
    `hasChanges`.
15. Seleccionar un evento sin código muestra el `template` del evento
    como `modelValue`, sin que quede reflejado en `events`.
16. "Guardar cambios" llama a `applicationsStore.update` con
    `events_json` stringified; resetea `hasChanges`.
17. "Deshacer" restaura `events` al snapshot original.

#### `tests/components/AppHeader.test.ts` (~2 tests)

18. Renderiza 3 tabs; la activa se determina por la ruta actual.
19. Slot `actions` se inyecta en la cabecera.

#### `tests/ScriptStepForm.test.ts` (adaptación)

Cambia el mock de `@/components/pipeline/forms/script-editor/editor`
a un stub de `@/components/CodeEditor.vue` con `v-model` y método
`insertAtCursor` via ref. Las 9 aserciones existentes se conservan.

### 9.3 Total esperado al cierre

**~92 tests frontend** (73 actuales + ~19 nuevos: 6 CodeEditor + 1
adaptación wrapper + 3 catálogo + 8 view + 2 AppHeader). Suite verde,
cero backend nuevos.

### 9.4 QA manual

1. Navegar a `/applications/8`. Comprobar tabs Resumen | Pipeline |
   Eventos.
2. Click en Eventos. Seleccionar `on_app_start`. Ver plantilla
   pre-cargada con la firma.
3. Escribir `log.info("hola")`. Ver que "Guardar cambios" se habilita.
4. Cambiar a `on_app_end` sin guardar. Volver a `on_app_start`.
   Comprobar que el código se conserva en el estado local.
5. "Guardar cambios". Recargar F5. Comprobar persistencia en BD.
6. Abrir `verification_panel`. Ver plantilla como clase. Escribir
   `self.api.`. Comprobar autocompletado con métodos.
7. Editar un evento. Click en "Deshacer". Verificar reset.
8. Editar sin guardar. Intentar navegar fuera. Comprobar `confirm`
   de abandono.
9. Volver a pipeline → abrir un ScriptStep. Comprobar que el editor
   sigue funcionando tras el refactor (sin regresiones v4).

## 10 · Archivos afectados

### 10.1 Nuevos

- `web/frontend/src/components/CodeEditor.vue`
- `web/frontend/src/components/code-editor/editor.ts` (renombrado)
- `web/frontend/src/components/AppHeader.vue`
- `web/frontend/src/api/events-catalog.ts`
- `web/frontend/src/views/applications/EventsEditorView.vue`
- `web/frontend/tests/CodeEditor.test.ts`
- `web/frontend/tests/code-editor/editor.test.ts` (renombrado)
- `web/frontend/tests/api/events-catalog.test.ts`
- `web/frontend/tests/views/EventsEditorView.test.ts`
- `web/frontend/tests/components/AppHeader.test.ts`

### 10.2 Modificados

- `web/frontend/src/components/pipeline/forms/ScriptStepForm.vue` —
  usa `<CodeEditor>`, pasa a ~120 líneas.
- `web/frontend/src/views/applications/ApplicationDetailView.vue` —
  usa `<AppHeader>`; quita botón "Editar pipeline".
- `web/frontend/src/views/applications/PipelineEditorView.vue` — usa
  `<AppHeader>`.
- `web/frontend/src/router/index.ts` — ruta `/applications/:id/events`.
- `web/frontend/tests/ScriptStepForm.test.ts` — cambia el mock.

### 10.3 Movido / eliminado

- `web/frontend/src/components/pipeline/forms/script-editor/editor.ts`
  → `web/frontend/src/components/code-editor/editor.ts`.
- `web/frontend/tests/script-editor/editor.test.ts` →
  `web/frontend/tests/code-editor/editor.test.ts`.

### 10.4 Sin cambios

- Todo el backend.
- Resto del frontend (widgets `fields/*`, otros forms del pipeline,
  vistas de batches/team/auth).

## 11 · Riesgos y mitigaciones

| Riesgo | Mitigación |
| --- | --- |
| Extracción de `<CodeEditor>` rompe ScriptStep (v4) | Tests del form se ejecutan antes/después del refactor; mock adaptado a `@/components/CodeEditor.vue`. |
| Prefijo dotted multi-nivel (`self.api.`) no reconocido | Regex extendido a `([\w.]+)\.$` + test dedicado en `code-editor/editor.test.ts`. |
| Olvidar `:key` en el consumidor → editor muestra doc viejo al cambiar de evento | Regla documentada: los consumidores sustituyen doc/vars vía `:key`. Tests de EventsEditorView cubren el remount al cambiar de evento. |
| Usuario pierde cambios al salir | `onBeforeRouteLeave` + `beforeunload` con `confirm` si `hasChanges`. |
| `events_json` inválido en BD | `try/catch` con fallback `{}` y log warning; paridad desktop. |
| Template "ensucia" el dirty tracking | Comparación exacta contra `template`; no se persiste si coincide. |
| Sidebar no cabe en pantallas pequeñas | `overflow-y-auto` + responsive: `< md` usa `<select>` fallback; `≥ md` sidebar. |
| CodeMirror chunk crece tras el refactor | Build post-refactor verifica que `editor-*.js` mantiene tamaño ≈131 KB gzipped. |

## 12 · Criterios de éxito

1. Se crean/editan/eliminan los 13 eventos desde la web con paridad
   frente al desktop.
2. Guardar produce `PATCH /applications/{id}` con `events_json`
   válido; round-trip `GET` = `PATCH`.
3. Autocompletado sugiere variables específicas por evento (ej.
   `key` solo en `on_key_event`).
4. `verification_panel` carga con plantilla de clase y autocompleta
   `self.api.*`.
5. `ScriptStepForm` sigue funcionando (v4 no regresa). Tests verdes.
6. CodeMirror sigue en chunk separado tras la extracción
   (`editor-*.js` ≈131 KB gzipped).
7. Tabs Resumen/Pipeline/Eventos funcionan con estado activo correcto.
8. Suite frontend ~92 tests verdes; cero backend nuevos.

## 13 · Próximo paso

Invocar `superpowers:writing-plans` para generar
`docs/superpowers/plans/2026-04-21-events-tab-plan.md`.
