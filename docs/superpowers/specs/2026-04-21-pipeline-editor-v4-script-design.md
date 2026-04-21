# Editor de pipeline v4 — ScriptStep (diseño)

**Fecha:** 2026-04-21
**Rama:** `feature/web`
**Estado:** aprobado — listo para plan de implementación
**Relación con v1/v2/v3:** reutiliza toda la infraestructura del editor
(store, REST `GET`/`PUT`, `PipelineStepList`, `PipelineStepRow`,
`PipelineStepDrawer`, `canSave`, `AddStepMenu`) sin modificar widgets
existentes. Introduce **CodeMirror 6** como primera dependencia de editor
de código en el proyecto.

## 1 · Objetivo

Permitir crear, editar, reordenar y eliminar pasos de tipo `ScriptStep`
desde el editor web, con paridad funcional frente al desktop y UX
moderna basada en CodeMirror 6.

**Fuera de scope:**

1. Validación de sintaxis Python en el navegador. El `ScriptEngine`
   del runtime captura errores y los vuelca a `page.flags.script_errors`.
2. Ejecución o preview del script desde el editor web. Solo se edita
   y se persiste; la ejecución ocurre en el pipeline runtime.
3. Integración con LSP / Pyright. Autocompletado limitado a las
   variables estáticas del contexto declaradas en frontend.

## 2 · Arquitectura general

### 2.1 Cambios de alto nivel

- **Backend:** cero cambios. `ScriptStep` y `serializer.deserialize()`
  ya lo soportan.
- **Frontend — dependencia nueva:** `codemirror` + `@codemirror/lang-python`
  + `@codemirror/autocomplete` (~200 KB gzipped). **Lazy-loaded** vía
  `defineAsyncComponent` en `PipelineStepDrawer` — solo se descarga al
  abrir un drawer de script.
- **Frontend — componente nuevo:** `ScriptStepForm.vue` (editor + panel
  de ayuda + menú de snippets, ~280 líneas) y un wrapper
  `script-editor/editor.ts` que concentra las importaciones de
  CodeMirror para que Vite las agrupe en un chunk separado.
- **Frontend — catálogo estático:** `script-context-help.ts` con
  variables del contexto, snippets y plantilla por defecto (datos puros,
  sin lógica).
- **Frontend — modificaciones mínimas:** `types-pipeline.ts`,
  `pipeline.ts` (store), `AddStepMenu.vue`, `PipelineStepDrawer.vue`,
  `PipelineStepRow.vue`.

### 2.2 Dataclass de referencia (backend, sin cambios)

```python
@dataclass
class ScriptStep(PipelineStep):
    type: Literal["script"] = "script"
    label: str = ""           # Nombre descriptivo
    entry_point: str = ""     # Función a llamar (default "process")
    script: str = ""          # Código Python
```

## 3 · Tipo TypeScript `ScriptStep`

Fichero a modificar: `web/frontend/src/api/types-pipeline.ts`.

```ts
export interface ScriptStep extends BasePipelineStep {
  type: 'script'
  label: string
  entry_point: string
  script: string
}

export type PipelineStep =
  | BarcodeStep | ImageOpStep | OcrStep | ScriptStep | GenericStep
```

`StepType` ya incluye `'script'` desde v1 — no se toca.

## 4 · Catálogo estático (`script-context-help.ts`)

Fichero nuevo: `web/frontend/src/api/script-context-help.ts`. Declara
tres exportaciones usadas por tres consumidores distintos:

| Export | Consumidores |
| --- | --- |
| `CONTEXT_VARIABLES` | Panel de ayuda + autocompletado CodeMirror |
| `SNIPPETS` | Menú "Insertar snippet" |
| `DEFAULT_SCRIPT_TEMPLATE` | `defaultsFor('script')` en el store |

### 4.1 Variables del contexto

```ts
export interface ContextVariable {
  name: string
  summary: string
  members?: ContextMember[]
}

export interface ContextMember {
  name: string
  signature?: string   // solo métodos
  description: string
}

export const CONTEXT_VARIABLES: ContextVariable[] = [
  { name: 'app',      summary: 'AppContext: id, name.' },
  { name: 'batch',    summary: 'BatchContext: id, state, fields, page_count.' },
  { name: 'page',     summary: 'PageContext: imagen y datos extraídos.',
    members: [
      { name: 'image',     description: 'np.ndarray BGR.' },
      { name: 'barcodes',  description: 'list[Barcode] con .value, .symbology.' },
      { name: 'ocr_text',  description: 'str — OCR acumulado.' },
      { name: 'fields',    description: 'dict[str, Any] — metadatos de la página.' },
      { name: 'flags',     description: 'dict[str, Any] — banderas internas.' },
    ],
  },
  { name: 'pipeline', summary: 'Control de flujo del pipeline (solo ScriptStep).',
    members: [
      { name: 'skip_step',     signature: 'skip_step(n=1)',     description: 'Salta los siguientes n steps.' },
      { name: 'skip_to',       signature: 'skip_to(step_id)',   description: 'Salta hasta el step con ese id.' },
      { name: 'abort',         signature: 'abort(reason="")',   description: 'Interrumpe el pipeline para esta página.' },
      { name: 'repeat_step',   signature: 'repeat_step()',      description: 'Repite el step actual (max 3).' },
      { name: 'replace_image', signature: 'replace_image(img)', description: 'Sustituye page.image.' },
      { name: 'get_metadata',  signature: 'get_metadata(key)',  description: 'Lee metadata del pipeline.' },
      { name: 'set_metadata',  signature: 'set_metadata(k, v)', description: 'Escribe metadata del pipeline.' },
    ],
  },
  { name: 'log',      summary: 'logger estándar: log.info(...), log.warning(...).' },
  { name: 'http',     summary: 'httpx — http.get(url), http.post(url, json=...).' },
  { name: 're',       summary: 'módulo re de Python.' },
  { name: 'json',     summary: 'módulo json de Python.' },
  { name: 'datetime', summary: 'módulo datetime de Python.' },
  { name: 'Path',     summary: 'pathlib.Path.' },
]
```

### 4.2 Snippets

```ts
export interface Snippet {
  id: string
  label: string
  description: string
  code: string  // multi-línea, se inserta en la posición del cursor
}

export const SNIPPETS: Snippet[] = [
  {
    id: 'barcode-to-field',
    label: 'Asignar primer barcode a page.fields',
    description: 'Copia el valor del primer barcode detectado a page.fields["documento"].',
    code: 'if page.barcodes:\n    page.fields["documento"] = page.barcodes[0].value\n',
  },
  {
    id: 'ocr-to-field',
    label: 'Extraer campo con regex del OCR',
    description: 'Busca un patrón en page.ocr_text y lo guarda en page.fields.',
    code: 'm = re.search(r"NIF:\\s*([A-Z0-9]+)", page.ocr_text or "")\nif m:\n    page.fields["nif"] = m.group(1)\n',
  },
  {
    id: 'http-download',
    label: 'Consultar API externa',
    description: 'Envía el valor de un campo a una API y guarda la respuesta.',
    code: 'doc = page.fields.get("documento")\nif doc:\n    r = http.get(f"https://api.example.com/docs/{doc}")\n    if r.status_code == 200:\n        page.fields["doc_data"] = r.json()\n',
  },
  {
    id: 'abort-if-no-barcodes',
    label: 'Abortar si no hay barcodes',
    description: 'Interrumpe la página si el barcode step no detectó nada.',
    code: 'if not page.barcodes:\n    pipeline.abort(reason="sin barcodes")\n',
  },
]
```

### 4.3 Plantilla por defecto

```ts
export const DEFAULT_SCRIPT_TEMPLATE = `def process(app, batch, page, pipeline):
    """Procesa cada página del pipeline.

    Args:
        app: AppContext (id, name)
        batch: BatchContext (id, state, fields, page_count)
        page: PageContext (image, barcodes, ocr_text, fields, flags)
        pipeline: PipelineContext (skip_step, abort, repeat_step, metadata)
    """
    pass
`
```

## 5 · Defaults en el store

Fichero a modificar: `web/frontend/src/stores/pipeline.ts`. Añadir rama
en `defaultsFor`:

```ts
if (type === 'script') {
  const defaults: Omit<ScriptStep, 'id'> = {
    type: 'script',
    enabled: true,
    label: '',
    entry_point: 'process',
    script: DEFAULT_SCRIPT_TEMPLATE,
  }
  return defaults
}
```

## 6 · Componente `ScriptStepForm.vue`

Fichero nuevo:
`web/frontend/src/components/pipeline/forms/ScriptStepForm.vue`.

### 6.1 Props / emits

```ts
defineProps<{ modelValue: ScriptStep }>()
defineEmits<{ 'update:modelValue': [step: ScriptStep] }>()
```

### 6.2 Layout

```
┌─────────────────────────────────────────────────────────────┐
│ ☐ Activo                                                    │
│ Nombre:       [_______________________________]             │
│ Función:      [process_____________]  (entry_point)         │
├─────────────────────────────────────────────────────────────┤
│ Código Python                       [Insertar snippet ▾]    │
│ ┌─────────────────────────────────┐  ┌────────────────────┐ │
│ │ CodeMirror                      │  │ Variables          │ │
│ │ (lang-python, tema light,       │  │  app               │ │
│ │ ~420px alto mínimo)             │  │  batch             │ │
│ │                                 │  │  page              │ │
│ │                                 │  │    · image         │ │
│ │                                 │  │    · barcodes      │ │
│ │                                 │  │    · ocr_text      │ │
│ │                                 │  │    · fields        │ │
│ │                                 │  │    · flags         │ │
│ │                                 │  │  pipeline          │ │
│ │                                 │  │    · skip_step(…)  │ │
│ │                                 │  │    · abort(…)      │ │
│ │                                 │  │    …               │ │
│ │                                 │  │  log, http, re …   │ │
│ └─────────────────────────────────┘  └────────────────────┘ │
│                                      [← Ocultar]            │
└─────────────────────────────────────────────────────────────┘
```

### 6.3 Comportamiento

1. **Activo / Nombre / Función** — inputs estándar. Cada cambio emite
   `update:modelValue` con el step completo (`{...modelValue, [key]: v}`).
2. **Función** tiene placeholder `process` y tooltip *"Nombre de la
   función Python a ejecutar"*. Si queda vacío al blur, se restaura a
   `process` (paridad con `ScriptStepDialog` desktop).
3. **CodeMirror** se monta dentro de `<div ref="editorHost">` en
   `onMounted`, usando `await import('./script-editor/editor')`.
   Extensiones cargadas:
   - `lineNumbers()`, `highlightActiveLine()`, `python()`,
     `keymap.of(defaultKeymap)`, `indentOnInput()`, `closeBrackets()`.
   - Tema light minimal custom: fondo `#fafafa`, monospace, keywords
     `#7c3aed`, strings `#059669`, comentarios `#9ca3af`.
   - `autocompletion({ override: [contextCompletions] })`. La función
     `contextCompletions` sugiere nombres de `CONTEXT_VARIABLES` al
     principio de un token y, cuando el cursor está tras `page.` o
     `pipeline.`, sugiere los `members` correspondientes.
   - Altura mínima 420 px, scroll interno si supera el alto.
4. **Sincronización** — el wrapper expone un callback `onChange(doc)`
   (implementado internamente con `EditorView.updateListener`). El
   form pasa un `onChange` que emite `update:modelValue` con
   `{...step, script: newDoc}` en cada cambio.
5. **Menú "Insertar snippet ▾"** — dropdown que lista `SNIPPETS`. Al
   seleccionar, el form invoca `editorHandle.insertAtCursor(code)`
   (método del wrapper, ver §6.4). El wrapper decide internamente si
   prefija `\n` cuando el cursor no está al principio de línea.
6. **Panel lateral** — renderiza `CONTEXT_VARIABLES` como árbol.
   Cada miembro con hover azul sutil. Click copia el nombre al
   clipboard y muestra tooltip *"Copiado"* ~1.5 s.
7. **Colapsar/expandir panel** — botón `[← Ocultar]` / `[Ayuda →]`.
   Resolución del estado inicial: (1) si existe
   `localStorage['scriptEditor.helpPanelOpen']`, usar ese valor; (2)
   si no, abierto en viewports ≥ `md` (768 px) y cerrado en móvil.
   Al togglear se persiste siempre en `localStorage`.
8. **Cleanup** — `onBeforeUnmount` llama `editorHandle?.destroy()`.

### 6.4 Wrapper `script-editor/editor.ts`

Fichero nuevo:
`web/frontend/src/components/pipeline/forms/script-editor/editor.ts`.

Concentra todas las importaciones de CodeMirror para que Vite las
agrupe en un chunk aparte. Exporta:

```ts
export interface CreateEditorArgs {
  parent: HTMLElement
  initialDoc: string
  onChange: (doc: string) => void
}

export interface EditorHandle {
  view: EditorView
  insertAtCursor: (text: string) => void
  destroy: () => void
}

export async function createEditor(args: CreateEditorArgs): Promise<EditorHandle>
```

Responsabilidades internas del wrapper:

- Montar `EditorView` con todas las extensiones (§6.3.3).
- Traducir cambios de documento a llamadas a `onChange(doc)` usando
  `EditorView.updateListener`.
- Implementar `insertAtCursor(text)` aplicando un `dispatch` con
  `changes: { from, insert }`, prefijando `\n` si la línea del cursor
  no está vacía.
- Implementar `contextCompletions` (autocompletado) consumiendo
  `CONTEXT_VARIABLES` desde `@/api/script-context-help`.

Así el componente Vue no importa directamente ningún símbolo de
`codemirror` y el chunk lazy contiene todo el peso del editor.

## 7 · Integración con el editor de pipeline

### 7.1 `AddStepMenu.vue`

Promover `script` a activo, eliminar la sección "Próximamente" (ya no
quedan tipos fuera):

```vue
<button @click="pick('script')"
        class="w-full text-left px-3 py-2 text-sm hover:bg-surface-0 flex items-center gap-2">
  <span class="w-2 h-2 rounded-full bg-violet-500"></span>
  <span>Script Python</span>
  <span class="ml-auto text-xs text-subtext">v4</span>
</button>
```

Se eliminan: el `<div class="border-t">` separador, el título
"Próximamente" y el botón gris deshabilitado.

### 7.2 `PipelineStepDrawer.vue`

1. Import lazy del form:
   ```ts
   const ScriptStepForm = defineAsyncComponent(
     () => import('./forms/ScriptStepForm.vue')
   )
   ```
2. Extender `isEditable`: `barcode || image_op || ocr || script`.
3. Rama `script` en el template con `v-else-if="draft?.type === 'script'"`.
4. Drawer de ancho condicional:
   ```vue
   <div :class="['absolute top-0 right-0 bottom-0 w-full bg-white shadow-2xl flex flex-col',
                 draft?.type === 'script' ? 'max-w-4xl' : 'max-w-lg']">
   ```
5. Eliminar el fallback *"Este tipo de step se edita desde desktop"* —
   ya no queda ningún tipo sin cubrir.
6. `canSave` para `script`: `true` siempre (todos los campos tienen
   defaults válidos).

### 7.3 `PipelineStepRow.vue` — summary compacto

Añadir rama `script`:

```ts
if (s.type === 'script') {
  const sc = s as ScriptStep
  const name = sc.label?.trim() || 'Script sin nombre'
  const entry = sc.entry_point?.trim() || 'process'
  const lines = (sc.script?.match(/\n/g)?.length ?? 0) + (sc.script ? 1 : 0)
  return `${name} · ${entry}() · ${lines} líneas`
}
```

Ejemplo: `asignar roles · process() · 12 líneas`. El color
`bg-violet-500` ya existe en `typeColors`.

## 8 · Validación y errores

### 8.1 Frontend

- Sin validación de sintaxis Python (decidido en brainstorm).
- `canSave` = `true` siempre para `script`.
- `entry_point` vacío tras blur → restaurar a `'process'`.
- Inserción de snippets: prefijar `\n` si el cursor no está al principio
  de línea.

### 8.2 Backend

- `deserialize()` ya valida la estructura de `ScriptStep` (422 si
  falla). Heredado de v1.
- `ScriptEngine` captura errores de sintaxis/runtime y los deposita
  en `page.flags.script_errors` sin abortar el pipeline (regla del
  CLAUDE.md).

### 8.3 Fallo de carga del chunk lazy

`defineAsyncComponent` muestra un fallback minimalista:

```vue
<div class="p-4 text-sm bg-red-50 border border-red-200 rounded">
  No se pudo cargar el editor de código. Recarga la página o prueba de nuevo.
</div>
```

El panel de ayuda es estático y no depende de CodeMirror, así que se
podría consultar el contexto aunque el editor fallara (aunque en la
práctica, si falla el chunk, el form entero queda en fallback).

## 9 · Tests

### 9.1 Backend

Cero tests nuevos.

### 9.2 Frontend — vitest

**Estrategia para CodeMirror:** jsdom no simula bien `contenteditable`.
Los tests del form mockean `./script-editor/editor` para validar la
lógica (emisiones, inserción de snippets, toggle de panel) sin montar
CodeMirror real.

#### `tests/ScriptStepForm.test.ts` (~8 tests)

1. Renderiza los 3 campos (Activo, Nombre, Función) con defaults.
2. Cambio de `label` emite `update:modelValue` con el nuevo label.
3. Cambio de `entry_point` emite con el nuevo valor.
4. `entry_point` vacío tras blur emite con `'process'`.
5. Toggle de `enabled` emite con el booleano invertido.
6. El dropdown "Insertar snippet" lista los 4 snippets de `SNIPPETS`.
7. Elegir un snippet llama `editorHandle.insertAtCursor(code)` (mock
   verifica el argumento).
8. Colapsar el panel persiste `scriptEditor.helpPanelOpen=false` en
   localStorage y al remontar vuelve a mostrarse cerrado.

#### `tests/api/script-context-help.test.ts` (~3 tests)

9. `CONTEXT_VARIABLES` incluye `page`, `pipeline`, `log`, `http`, `re`,
   `json`, `datetime`, `Path`.
10. `SNIPPETS` tiene exactamente 4 entradas con `id` único.
11. `DEFAULT_SCRIPT_TEMPLATE` empieza con
    `def process(app, batch, page, pipeline):`.

#### `tests/stores/pipeline.store.test.ts` (ampliación, +1 test)

12. `addStep('script')` devuelve un step con `type='script'`,
    `enabled=true`, `entry_point='process'`, `label=''` y
    `script=DEFAULT_SCRIPT_TEMPLATE`.

### 9.3 Total esperado al cierre

**~67 tests frontend** (55 actuales + 12 nuevos). Suite verde, cero
backend nuevos.

### 9.4 QA manual

1. Crear un `ScriptStep` desde web, guardar, recargar página →
   round-trip correcto en BD.
2. Abrir desktop y verificar que el step aparece con los mismos 3
   campos.
3. Ejecutar un lote con el pipeline que incluya el script y comprobar
   que el script ejecuta (log) o que los errores caen en
   `page.flags.script_errors`.
4. Verificar en `vite build` que CodeMirror aparece en un chunk
   separado (`dist/assets/script-editor-*.js`).

## 10 · Archivos afectados

### 10.1 Nuevos

- `web/frontend/src/components/pipeline/forms/ScriptStepForm.vue`
- `web/frontend/src/components/pipeline/forms/script-editor/editor.ts`
- `web/frontend/src/api/script-context-help.ts`
- `web/frontend/tests/ScriptStepForm.test.ts`
- `web/frontend/tests/api/script-context-help.test.ts`

### 10.2 Modificados

- `web/frontend/package.json` + `package-lock.json` — añadir
  `codemirror`, `@codemirror/lang-python`, `@codemirror/autocomplete`.
- `web/frontend/src/api/types-pipeline.ts` — añadir `ScriptStep` al
  union.
- `web/frontend/src/stores/pipeline.ts` — rama `script` en
  `defaultsFor` usando `DEFAULT_SCRIPT_TEMPLATE`.
- `web/frontend/src/components/pipeline/AddStepMenu.vue` — activar
  `script`, eliminar bloque "Próximamente".
- `web/frontend/src/components/pipeline/PipelineStepDrawer.vue` — rama
  `script` con lazy import, `max-w-4xl` condicional, eliminar fallback.
- `web/frontend/src/components/pipeline/PipelineStepRow.vue` — summary
  para `script`.
- `web/frontend/tests/stores/pipeline.store.test.ts` — 1 test de
  `addStep('script')`.

### 10.3 Sin cambios

- Todo el backend.
- Widgets existentes (`NumberField`, `EnumField`, `BooleanField`,
  `ColorField`, `PointField`, `WindowField`, `TagInput`).
- Forms existentes (`BarcodeStepForm`, `ImageOpStepForm`,
  `OcrStepForm`).

## 11 · Riesgos y mitigaciones

| Riesgo | Mitigación |
| --- | --- |
| CodeMirror pesa ~200 KB gzipped y ralentizaría el first load | Lazy-load vía `defineAsyncComponent` + import dinámico en `ScriptStepForm`. Solo se descarga al abrir un drawer de script. |
| jsdom no simula bien `contenteditable` y los tests fallan | Mockear `./script-editor/editor` en `ScriptStepForm.test.ts`; validar lógica del form, no el editor. |
| Usuario escribe código que falla en runtime | Paridad desktop: `ScriptEngine` captura y escribe `page.flags.script_errors`. UI no valida Python. |
| Autocompletado de `page.`/`pipeline.` no acierta con alias (`p = page`) | Asumido; solo sugerimos cuando el prefijo exacto coincide. |
| Panel de ayuda ocupa demasiado espacio en pantallas medianas | Colapsable con persistencia en `localStorage`; default abierto en ≥ `md`, cerrado en móvil. |
| Regresión en otros forms por el cambio de ancho del drawer | Cambio condicionado a `draft?.type === 'script'`; los otros forms conservan `max-w-lg`. |
| Fallo de red al cargar chunk lazy | Fallback visible con mensaje de error; el usuario recarga la página. |

## 12 · Criterios de éxito

1. Desde la web se puede crear, editar y eliminar un `ScriptStep` con
   paridad de campos respecto al desktop.
2. El código se guarda correctamente (round-trip `GET` = `PUT`).
3. Un pipeline con un `ScriptStep` creado desde web ejecuta el código
   en runtime (verificado con script que escribe en `log.info`).
4. Los 55 tests frontend actuales siguen verdes; se añaden ~12 nuevos.
5. CodeMirror carga solo cuando se abre el drawer de un script (chunk
   separado verificable en `vite build`).
6. El panel de ayuda muestra todas las variables del contexto y
   permite copiar nombres con click.
7. Los 4 snippets se insertan correctamente y el código resultante es
   ejecutable.

## 13 · Próximo paso

Invocar `superpowers:writing-plans` para generar
`docs/superpowers/plans/2026-04-21-pipeline-editor-v4-script-plan.md`.
