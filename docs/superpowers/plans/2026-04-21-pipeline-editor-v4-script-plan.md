# Editor de Pipeline v4 — ScriptStep — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir crear, editar, reordenar y eliminar pasos de tipo `ScriptStep` desde el editor web con paridad frente al desktop, usando CodeMirror 6 lazy-loaded como editor de código, panel lateral de ayuda con variables del contexto y menú de snippets.

**Architecture:** Frontend puro. Nuevo componente `ScriptStepForm.vue` (~280 líneas) orquesta 3 campos básicos (`label`, `entry_point`, `enabled`), un editor CodeMirror 6 (envuelto en un wrapper lazy-chunked `script-editor/editor.ts`), un panel lateral de ayuda colapsable y un menú de snippets. Datos declarativos en `script-context-help.ts` (variables del contexto + snippets + plantilla). Integración mínima en `AddStepMenu`, `PipelineStepDrawer` (con lazy import + ancho condicional), `PipelineStepRow` y el store. Cero cambios en backend.

**Tech Stack:** Vue 3 + TypeScript + Pinia + Tailwind CSS + **CodeMirror 6** (`codemirror`, `@codemirror/lang-python`, `@codemirror/autocomplete`) + vitest + `@vue/test-utils` + `jsdom`.

**Spec:** `docs/superpowers/specs/2026-04-21-pipeline-editor-v4-script-design.md`

---

## Estructura de ficheros

### Nuevos

| Fichero | Responsabilidad |
| --- | --- |
| `web/frontend/src/api/script-context-help.ts` | Exporta `CONTEXT_VARIABLES`, `SNIPPETS` y `DEFAULT_SCRIPT_TEMPLATE`. Datos puros, sin lógica. |
| `web/frontend/src/components/pipeline/forms/script-editor/editor.ts` | Wrapper de CodeMirror 6. Concentra todas las importaciones para que Vite genere un chunk separado. Exporta `createEditor(args) → EditorHandle`, `shouldPrefixNewline(line)` y `contextCompletions`. |
| `web/frontend/src/components/pipeline/forms/ScriptStepForm.vue` | Form principal del ScriptStep: 3 campos base + editor CodeMirror (lazy) + menú de snippets + panel lateral de ayuda. |
| `web/frontend/tests/api/script-context-help.test.ts` | Tests del catálogo estático (3). |
| `web/frontend/tests/script-editor/editor.test.ts` | Tests unitarios de las funciones puras `shouldPrefixNewline` y `contextCompletions` (4). |
| `web/frontend/tests/ScriptStepForm.test.ts` | Tests del form mockeando el wrapper (8). |

### Modificados

| Fichero | Cambio |
| --- | --- |
| `web/frontend/package.json` + `package-lock.json` | Añadir deps `codemirror`, `@codemirror/lang-python`, `@codemirror/autocomplete`. |
| `web/frontend/src/api/types-pipeline.ts` | Añadir `ScriptStep` al union `PipelineStep`. |
| `web/frontend/src/stores/pipeline.ts` | Rama `script` en `defaultsFor` usando `DEFAULT_SCRIPT_TEMPLATE`. |
| `web/frontend/src/components/pipeline/AddStepMenu.vue` | Promover `script` a opción activa con badge v4, eliminar bloque "Próximamente". |
| `web/frontend/src/components/pipeline/PipelineStepDrawer.vue` | Rama `script` con `defineAsyncComponent`, `max-w-4xl` condicional, eliminar fallback. |
| `web/frontend/src/components/pipeline/PipelineStepRow.vue` | Summary para `script`. |
| `web/frontend/tests/stores/pipeline.store.test.ts` | 1 test nuevo para `addStep('script')`. |

---

## Task 1: Tipo `ScriptStep` en el dominio TypeScript

**Files:**
- Modify: `web/frontend/src/api/types-pipeline.ts`

- [ ] **Step 1: Añadir la interfaz `ScriptStep`**

Abrir el fichero y añadir debajo de la interfaz `OcrStep` (tras su cierre, antes del comentario `// Union para el resto de tipos`):

```ts
export interface ScriptStep extends BasePipelineStep {
  type: 'script'
  label: string
  entry_point: string
  script: string
}
```

- [ ] **Step 2: Actualizar el union `PipelineStep`**

Cambiar:
```ts
export type PipelineStep = BarcodeStep | ImageOpStep | OcrStep | GenericStep
```

Por:
```ts
export type PipelineStep = BarcodeStep | ImageOpStep | OcrStep | ScriptStep | GenericStep
```

- [ ] **Step 3: Verificar tests existentes**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run
```

Expected: 55/55 PASS (sin cambios respecto al cierre de v3).

- [ ] **Step 4: Commit**

```bash
git add web/frontend/src/api/types-pipeline.ts
git commit -m "feat(web-frontend): añadir tipo ScriptStep al dominio TS"
```

---

## Task 2: Catálogo `script-context-help.ts`

**Files:**
- Create: `web/frontend/src/api/script-context-help.ts`
- Test: `web/frontend/tests/api/script-context-help.test.ts`

- [ ] **Step 1: Escribir el test del catálogo**

Crear `web/frontend/tests/api/script-context-help.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import {
  CONTEXT_VARIABLES,
  SNIPPETS,
  DEFAULT_SCRIPT_TEMPLATE,
} from '@/api/script-context-help'

describe('script-context-help', () => {
  it('CONTEXT_VARIABLES incluye todas las variables inyectadas', () => {
    const names = CONTEXT_VARIABLES.map((v) => v.name)
    const expected = [
      'app', 'batch', 'page', 'pipeline',
      'log', 'http', 're', 'json', 'datetime', 'Path',
    ]
    for (const name of expected) {
      expect(names).toContain(name)
    }
    // page y pipeline deben exponer members
    const page = CONTEXT_VARIABLES.find((v) => v.name === 'page')!
    expect(page.members?.map((m) => m.name)).toEqual(
      expect.arrayContaining(['image', 'barcodes', 'ocr_text', 'fields', 'flags']),
    )
    const pipeline = CONTEXT_VARIABLES.find((v) => v.name === 'pipeline')!
    expect(pipeline.members?.map((m) => m.name)).toEqual(
      expect.arrayContaining([
        'skip_step', 'skip_to', 'abort', 'repeat_step',
        'replace_image', 'get_metadata', 'set_metadata',
      ]),
    )
  })

  it('SNIPPETS tiene 4 entradas con id único', () => {
    expect(SNIPPETS).toHaveLength(4)
    const ids = SNIPPETS.map((s) => s.id)
    expect(new Set(ids).size).toBe(4)
    for (const snippet of SNIPPETS) {
      expect(snippet.label).toBeTruthy()
      expect(snippet.code).toBeTruthy()
    }
  })

  it('DEFAULT_SCRIPT_TEMPLATE empieza con la firma process(...)', () => {
    expect(DEFAULT_SCRIPT_TEMPLATE.startsWith(
      'def process(app, batch, page, pipeline):',
    )).toBe(true)
  })
})
```

- [ ] **Step 2: Verificar que el test falla**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run tests/api/script-context-help.test.ts
```

Expected: FAIL con "Cannot find module '@/api/script-context-help'".

- [ ] **Step 3: Crear el fichero del catálogo**

Crear `web/frontend/src/api/script-context-help.ts`:

```ts
// Catálogo estático consumido por el editor de ScriptStep:
//   - CONTEXT_VARIABLES → panel lateral + autocompletado
//   - SNIPPETS          → menú "Insertar snippet"
//   - DEFAULT_SCRIPT_TEMPLATE → defaultsFor('script') en el store

export interface ContextMember {
  name: string
  signature?: string
  description: string
}

export interface ContextVariable {
  name: string
  summary: string
  members?: ContextMember[]
}

export const CONTEXT_VARIABLES: ContextVariable[] = [
  { name: 'app', summary: 'AppContext: id, name.' },
  { name: 'batch', summary: 'BatchContext: id, state, fields, page_count.' },
  {
    name: 'page',
    summary: 'PageContext: imagen y datos extraídos.',
    members: [
      { name: 'image', description: 'np.ndarray BGR.' },
      { name: 'barcodes', description: 'list[Barcode] con .value, .symbology.' },
      { name: 'ocr_text', description: 'str — OCR acumulado.' },
      { name: 'fields', description: 'dict[str, Any] — metadatos de la página.' },
      { name: 'flags', description: 'dict[str, Any] — banderas internas.' },
    ],
  },
  {
    name: 'pipeline',
    summary: 'Control de flujo del pipeline (solo ScriptStep).',
    members: [
      { name: 'skip_step', signature: 'skip_step(n=1)', description: 'Salta los siguientes n steps.' },
      { name: 'skip_to', signature: 'skip_to(step_id)', description: 'Salta hasta el step con ese id.' },
      { name: 'abort', signature: 'abort(reason="")', description: 'Interrumpe el pipeline para esta página.' },
      { name: 'repeat_step', signature: 'repeat_step()', description: 'Repite el step actual (max 3).' },
      { name: 'replace_image', signature: 'replace_image(img)', description: 'Sustituye page.image.' },
      { name: 'get_metadata', signature: 'get_metadata(key)', description: 'Lee metadata del pipeline.' },
      { name: 'set_metadata', signature: 'set_metadata(k, v)', description: 'Escribe metadata del pipeline.' },
    ],
  },
  { name: 'log', summary: 'logger estándar: log.info(...), log.warning(...).' },
  { name: 'http', summary: 'httpx — http.get(url), http.post(url, json=...).' },
  { name: 're', summary: 'módulo re de Python.' },
  { name: 'json', summary: 'módulo json de Python.' },
  { name: 'datetime', summary: 'módulo datetime de Python.' },
  { name: 'Path', summary: 'pathlib.Path.' },
]

export interface Snippet {
  id: string
  label: string
  description: string
  code: string
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

- [ ] **Step 4: Verificar que el test pasa**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run tests/api/script-context-help.test.ts
```

Expected: 3/3 PASS.

- [ ] **Step 5: Ejecutar la suite completa**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run
```

Expected: 58/58 PASS (55 previos + 3 nuevos).

- [ ] **Step 6: Commit**

```bash
git add web/frontend/src/api/script-context-help.ts web/frontend/tests/api/script-context-help.test.ts
git commit -m "feat(web-frontend): catálogo de contexto, snippets y plantilla ScriptStep"
```

---

## Task 3: `defaultsFor('script')` en el store

**Files:**
- Modify: `web/frontend/src/stores/pipeline.ts`
- Modify: `web/frontend/tests/stores/pipeline.store.test.ts`

- [ ] **Step 1: Añadir el test de `addStep('script')`**

Abrir `web/frontend/tests/stores/pipeline.store.test.ts`. Localizar el bloque de tests de `addStep` (bloque similar con tests `addStep('barcode')`, `addStep('image_op')`, `addStep('ocr')`). Añadir al final del mismo `describe`:

```ts
it('addStep("script") crea un step con defaults de plantilla', async () => {
  const { DEFAULT_SCRIPT_TEMPLATE } = await import('@/api/script-context-help')
  const store = usePipelineStore()
  const step = store.addStep('script') as ScriptStep
  expect(step.type).toBe('script')
  expect(step.enabled).toBe(true)
  expect(step.label).toBe('')
  expect(step.entry_point).toBe('process')
  expect(step.script).toBe(DEFAULT_SCRIPT_TEMPLATE)
  expect(step.id).toBeTruthy()
})
```

Si el fichero no importa aún `ScriptStep`, añadirlo al import de `@/api/types-pipeline` al inicio del fichero.

- [ ] **Step 2: Verificar que el test falla**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run tests/stores/pipeline.store.test.ts
```

Expected: FAIL. El error será algo como `entry_point` no coincide (porque la rama por defecto en `defaultsFor` devuelve `{ type, enabled: true }` genérico).

- [ ] **Step 3: Añadir la rama `script` en `defaultsFor`**

Abrir `web/frontend/src/stores/pipeline.ts`. Actualizar el import:

```ts
import type {
  PipelineStep, StepType,
  BarcodeStep, ImageOpStep, OcrStep, ScriptStep,
} from '@/api/types-pipeline'
import { DEFAULT_SCRIPT_TEMPLATE } from '@/api/script-context-help'
```

Dentro de `defaultsFor`, antes del comentario `// Otros tipos no son editables aún`, añadir:

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

- [ ] **Step 4: Verificar que el test pasa**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run tests/stores/pipeline.store.test.ts
```

Expected: todos los tests del store PASS.

- [ ] **Step 5: Ejecutar la suite completa**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run
```

Expected: 59/59 PASS (58 previos + 1 nuevo).

- [ ] **Step 6: Commit**

```bash
git add web/frontend/src/stores/pipeline.ts web/frontend/tests/stores/pipeline.store.test.ts
git commit -m "feat(web-frontend): defaultsFor script con plantilla process"
```

---

## Task 4: Instalar dependencias de CodeMirror 6

**Files:**
- Modify: `web/frontend/package.json`
- Modify: `web/frontend/package-lock.json`

- [ ] **Step 1: Instalar las deps**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm install codemirror@^6 @codemirror/lang-python@^6 @codemirror/autocomplete@^6
```

Expected: actualización silenciosa de `package.json` y `package-lock.json`.

- [ ] **Step 2: Verificar versiones instaladas**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm list codemirror @codemirror/lang-python @codemirror/autocomplete
```

Expected: las tres versiones `6.x.x` listadas sin warnings.

- [ ] **Step 3: Verificar que la suite sigue verde**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run
```

Expected: 59/59 PASS.

- [ ] **Step 4: Commit**

```bash
git add web/frontend/package.json web/frontend/package-lock.json
git commit -m "build(web-frontend): añadir CodeMirror 6 para editor de ScriptStep"
```

---

## Task 5: Wrapper `script-editor/editor.ts`

**Files:**
- Create: `web/frontend/src/components/pipeline/forms/script-editor/editor.ts`
- Test: `web/frontend/tests/script-editor/editor.test.ts`

- [ ] **Step 1: Escribir tests de las funciones puras**

Crear `web/frontend/tests/script-editor/editor.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import {
  shouldPrefixNewline,
  buildContextSuggestions,
} from '@/components/pipeline/forms/script-editor/editor'

describe('script-editor/editor — funciones puras', () => {
  describe('shouldPrefixNewline', () => {
    it('devuelve false si la línea actual está vacía', () => {
      expect(shouldPrefixNewline('')).toBe(false)
    })

    it('devuelve false si la línea solo tiene whitespace (indentación)', () => {
      expect(shouldPrefixNewline('    ')).toBe(false)
    })

    it('devuelve true si la línea tiene contenido', () => {
      expect(shouldPrefixNewline('x = 1')).toBe(true)
    })
  })

  describe('buildContextSuggestions', () => {
    it('para prefijo vacío devuelve todas las variables top-level', () => {
      const out = buildContextSuggestions('')
      const names = out.map((o) => o.label)
      expect(names).toEqual(expect.arrayContaining([
        'app', 'batch', 'page', 'pipeline', 'log', 'http', 're', 'json', 'datetime', 'Path',
      ]))
    })

    it('para prefijo "page." devuelve los members de page', () => {
      const out = buildContextSuggestions('page.')
      const names = out.map((o) => o.label)
      expect(names).toEqual(expect.arrayContaining([
        'image', 'barcodes', 'ocr_text', 'fields', 'flags',
      ]))
    })
  })
})
```

- [ ] **Step 2: Verificar que los tests fallan**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run tests/script-editor/editor.test.ts
```

Expected: FAIL con "Cannot find module".

- [ ] **Step 3: Crear el wrapper**

Crear `web/frontend/src/components/pipeline/forms/script-editor/editor.ts`:

```ts
// Wrapper de CodeMirror 6. Concentra todas las importaciones para
// que Vite genere un chunk separado al ser importado dinámicamente.

import { EditorState } from '@codemirror/state'
import { EditorView, keymap, lineNumbers, highlightActiveLine } from '@codemirror/view'
import { defaultKeymap, indentWithTab, history, historyKeymap } from '@codemirror/commands'
import { indentOnInput, bracketMatching } from '@codemirror/language'
import { closeBrackets, closeBracketsKeymap } from '@codemirror/autocomplete'
import { autocompletion } from '@codemirror/autocomplete'
import type { CompletionContext, CompletionResult, Completion } from '@codemirror/autocomplete'
import { python } from '@codemirror/lang-python'
import { CONTEXT_VARIABLES } from '@/api/script-context-help'

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

/** True si hay que prefijar `\n` al insertar texto en esa línea. */
export function shouldPrefixNewline(currentLineText: string): boolean {
  return currentLineText.trim().length > 0
}

/**
 * Dado un prefijo textual, devuelve las completions aplicables.
 * - "" → variables top-level
 * - "page."     → members de page
 * - "pipeline." → members de pipeline
 */
export function buildContextSuggestions(prefix: string): Completion[] {
  const dotMatch = prefix.match(/(\w+)\.$/)
  if (dotMatch) {
    const varName = dotMatch[1]
    const variable = CONTEXT_VARIABLES.find((v) => v.name === varName)
    if (variable?.members) {
      return variable.members.map((m) => ({
        label: m.name,
        type: m.signature ? 'method' : 'property',
        detail: m.signature,
        info: m.description,
      }))
    }
    return []
  }
  return CONTEXT_VARIABLES.map((v) => ({
    label: v.name,
    type: 'variable',
    info: v.summary,
  }))
}

function contextCompletions(context: CompletionContext): CompletionResult | null {
  const line = context.state.doc.lineAt(context.pos)
  const textBeforeCursor = line.text.slice(0, context.pos - line.from)

  const dotMatch = textBeforeCursor.match(/(\w+)\.(\w*)$/)
  if (dotMatch) {
    const base = dotMatch[1]
    const fragment = dotMatch[2]
    const suggestions = buildContextSuggestions(`${base}.`)
    if (suggestions.length === 0) return null
    return {
      from: context.pos - fragment.length,
      options: suggestions,
      validFor: /^\w*$/,
    }
  }

  const wordMatch = textBeforeCursor.match(/(\w+)$/)
  if (wordMatch) {
    return {
      from: context.pos - wordMatch[1].length,
      options: buildContextSuggestions(''),
      validFor: /^\w*$/,
    }
  }

  if (context.explicit) {
    return {
      from: context.pos,
      options: buildContextSuggestions(''),
      validFor: /^\w*$/,
    }
  }
  return null
}

const lightTheme = EditorView.theme(
  {
    '&': {
      fontSize: '13px',
      backgroundColor: '#fafafa',
      height: '100%',
    },
    '.cm-content': {
      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
      caretColor: '#1f2937',
    },
    '.cm-gutters': {
      backgroundColor: '#f3f4f6',
      color: '#9ca3af',
      border: 'none',
    },
    '.cm-activeLine': { backgroundColor: '#f1f5f9' },
    '.cm-activeLineGutter': { backgroundColor: '#e5e7eb' },
  },
  { dark: false },
)

export async function createEditor(args: CreateEditorArgs): Promise<EditorHandle> {
  const updateListener = EditorView.updateListener.of((update) => {
    if (update.docChanged) {
      args.onChange(update.state.doc.toString())
    }
  })

  const state = EditorState.create({
    doc: args.initialDoc,
    extensions: [
      lineNumbers(),
      highlightActiveLine(),
      history(),
      python(),
      indentOnInput(),
      bracketMatching(),
      closeBrackets(),
      autocompletion({ override: [contextCompletions] }),
      keymap.of([
        ...closeBracketsKeymap,
        ...defaultKeymap,
        ...historyKeymap,
        indentWithTab,
      ]),
      lightTheme,
      updateListener,
    ],
  })

  const view = new EditorView({ state, parent: args.parent })

  function insertAtCursor(text: string): void {
    const pos = view.state.selection.main.head
    const line = view.state.doc.lineAt(pos)
    const textBefore = line.text.slice(0, pos - line.from)
    const insert = shouldPrefixNewline(textBefore) ? `\n${text}` : text
    view.dispatch({ changes: { from: pos, insert } })
    view.focus()
  }

  function destroy(): void {
    view.destroy()
  }

  return { view, insertAtCursor, destroy }
}
```

- [ ] **Step 4: Verificar que los tests pasan**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run tests/script-editor/editor.test.ts
```

Expected: 5/5 PASS.

- [ ] **Step 5: Ejecutar la suite completa**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run
```

Expected: 64/64 PASS (59 previos + 5 nuevos).

- [ ] **Step 6: Commit**

```bash
git add web/frontend/src/components/pipeline/forms/script-editor/editor.ts web/frontend/tests/script-editor/editor.test.ts
git commit -m "feat(web-frontend): wrapper CodeMirror con autocompletado de contexto"
```

---

## Task 6: `ScriptStepForm.vue` — campos base con tests

**Files:**
- Create: `web/frontend/src/components/pipeline/forms/ScriptStepForm.vue`
- Test: `web/frontend/tests/ScriptStepForm.test.ts`

En esta task se implementan solo los 3 campos básicos (Activo, Nombre, Función) y la estructura del componente. El editor, los snippets y el panel de ayuda se añaden en las tasks 7-9. Tests correspondientes.

- [ ] **Step 1: Escribir los tests iniciales (1-5)**

Crear `web/frontend/tests/ScriptStepForm.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ScriptStepForm from '@/components/pipeline/forms/ScriptStepForm.vue'
import type { ScriptStep } from '@/api/types-pipeline'
import { DEFAULT_SCRIPT_TEMPLATE } from '@/api/script-context-help'

// Mock del wrapper del editor para no montar CodeMirror real.
const insertAtCursorMock = vi.fn()
const destroyMock = vi.fn()
const onChangeRef: { value: ((doc: string) => void) | null } = { value: null }

vi.mock('@/components/pipeline/forms/script-editor/editor', () => ({
  createEditor: vi.fn(async (args: { onChange: (doc: string) => void }) => {
    onChangeRef.value = args.onChange
    return {
      view: {} as unknown,
      insertAtCursor: insertAtCursorMock,
      destroy: destroyMock,
    }
  }),
  // Los tests 3-4 no necesitan estos pero se exportan igualmente.
  shouldPrefixNewline: vi.fn(() => false),
  buildContextSuggestions: vi.fn(() => []),
}))

function makeStep(overrides: Partial<ScriptStep> = {}): ScriptStep {
  return {
    id: 'step-1',
    type: 'script',
    enabled: true,
    label: '',
    entry_point: 'process',
    script: DEFAULT_SCRIPT_TEMPLATE,
    ...overrides,
  }
}

describe('ScriptStepForm — campos base', () => {
  beforeEach(() => {
    insertAtCursorMock.mockClear()
    destroyMock.mockClear()
    onChangeRef.value = null
    localStorage.clear()
  })

  it('renderiza Activo, Nombre y Función con los valores iniciales', () => {
    const step = makeStep({ label: 'mi-script', entry_point: 'process' })
    const wrapper = mount(ScriptStepForm, { props: { modelValue: step } })

    const enabled = wrapper.find('input[type="checkbox"]')
    expect((enabled.element as HTMLInputElement).checked).toBe(true)

    const label = wrapper.find('[data-test="field-label"]')
    expect((label.element as HTMLInputElement).value).toBe('mi-script')

    const entry = wrapper.find('[data-test="field-entry-point"]')
    expect((entry.element as HTMLInputElement).value).toBe('process')
  })

  it('cambio de label emite update:modelValue con el nuevo label', async () => {
    const step = makeStep()
    const wrapper = mount(ScriptStepForm, { props: { modelValue: step } })
    const label = wrapper.find('[data-test="field-label"]')
    await label.setValue('nuevo-nombre')
    const events = wrapper.emitted('update:modelValue')!
    const last = events[events.length - 1][0] as ScriptStep
    expect(last.label).toBe('nuevo-nombre')
  })

  it('cambio de entry_point emite con el nuevo valor', async () => {
    const step = makeStep()
    const wrapper = mount(ScriptStepForm, { props: { modelValue: step } })
    const entry = wrapper.find('[data-test="field-entry-point"]')
    await entry.setValue('run')
    const events = wrapper.emitted('update:modelValue')!
    const last = events[events.length - 1][0] as ScriptStep
    expect(last.entry_point).toBe('run')
  })

  it('entry_point vacío tras blur se restaura a "process"', async () => {
    const step = makeStep({ entry_point: 'run' })
    const wrapper = mount(ScriptStepForm, { props: { modelValue: step } })
    const entry = wrapper.find('[data-test="field-entry-point"]')
    await entry.setValue('')
    await entry.trigger('blur')
    const events = wrapper.emitted('update:modelValue')!
    const last = events[events.length - 1][0] as ScriptStep
    expect(last.entry_point).toBe('process')
  })

  it('toggle de enabled emite el booleano invertido', async () => {
    const step = makeStep({ enabled: true })
    const wrapper = mount(ScriptStepForm, { props: { modelValue: step } })
    const enabled = wrapper.find('input[type="checkbox"]')
    await enabled.setValue(false)
    const events = wrapper.emitted('update:modelValue')!
    const last = events[events.length - 1][0] as ScriptStep
    expect(last.enabled).toBe(false)
  })
})
```

- [ ] **Step 2: Verificar que los tests fallan**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run tests/ScriptStepForm.test.ts
```

Expected: FAIL con "Cannot find module '@/components/pipeline/forms/ScriptStepForm.vue'".

- [ ] **Step 3: Crear el componente con campos base (sin editor)**

Crear `web/frontend/src/components/pipeline/forms/ScriptStepForm.vue`:

```vue
<script setup lang="ts">
import type { ScriptStep } from '@/api/types-pipeline'

const props = defineProps<{ modelValue: ScriptStep }>()
const emit = defineEmits<{ 'update:modelValue': [step: ScriptStep] }>()

function patch(update: Partial<ScriptStep>): void {
  emit('update:modelValue', { ...props.modelValue, ...update })
}

function onEntryPointBlur(ev: Event): void {
  const raw = (ev.target as HTMLInputElement).value.trim()
  const next = raw === '' ? 'process' : raw
  if (next !== props.modelValue.entry_point) {
    patch({ entry_point: next })
  }
}
</script>

<template>
  <div class="space-y-4">
    <!-- Activo -->
    <div class="flex items-center gap-2">
      <input
        id="script_enabled"
        type="checkbox"
        :checked="modelValue.enabled"
        @change="(e) => patch({ enabled: (e.target as HTMLInputElement).checked })"
      />
      <label for="script_enabled" class="text-sm">Activo</label>
    </div>

    <!-- Nombre -->
    <div>
      <label for="script_label" class="block text-sm font-medium mb-1">Nombre</label>
      <input
        id="script_label"
        type="text"
        data-test="field-label"
        :value="modelValue.label"
        @input="(e) => patch({ label: (e.target as HTMLInputElement).value })"
        placeholder="Ej: Asignar roles barcode"
        class="w-full border border-surface-0 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
      />
    </div>

    <!-- Función -->
    <div>
      <label for="script_entry" class="block text-sm font-medium mb-1">Función</label>
      <input
        id="script_entry"
        type="text"
        data-test="field-entry-point"
        :value="modelValue.entry_point"
        @input="(e) => patch({ entry_point: (e.target as HTMLInputElement).value })"
        @blur="onEntryPointBlur"
        placeholder="process"
        title="Nombre de la función Python a ejecutar"
        class="w-full border border-surface-0 rounded-md px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary/40"
      />
      <p class="text-xs text-subtext mt-1">Nombre de la función Python a ejecutar (default: <code>process</code>).</p>
    </div>

    <!-- Placeholder para el editor (se implementa en Task 7) -->
    <div data-test="editor-placeholder" class="text-xs text-subtext italic">
      (editor de código — pendiente de implementar)
    </div>
  </div>
</template>
```

- [ ] **Step 4: Verificar que los 5 tests pasan**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run tests/ScriptStepForm.test.ts
```

Expected: 5/5 PASS.

- [ ] **Step 5: Ejecutar la suite completa**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run
```

Expected: 69/69 PASS (64 previos + 5 nuevos).

- [ ] **Step 6: Commit**

```bash
git add web/frontend/src/components/pipeline/forms/ScriptStepForm.vue web/frontend/tests/ScriptStepForm.test.ts
git commit -m "feat(web-frontend): ScriptStepForm con campos base (label, entry_point, enabled)"
```

---

## Task 7: `ScriptStepForm.vue` — montar el editor CodeMirror

**Files:**
- Modify: `web/frontend/src/components/pipeline/forms/ScriptStepForm.vue`
- Modify: `web/frontend/tests/ScriptStepForm.test.ts`

- [ ] **Step 1: Añadir el test de sincronización editor → modelValue**

Al final del `describe('ScriptStepForm — campos base', …)`, añadir un nuevo `describe` dentro del mismo fichero:

```ts
describe('ScriptStepForm — editor CodeMirror', () => {
  beforeEach(() => {
    insertAtCursorMock.mockClear()
    destroyMock.mockClear()
    onChangeRef.value = null
    localStorage.clear()
  })

  it('monta el wrapper y emite update:modelValue cuando el editor cambia', async () => {
    const step = makeStep({ script: 'x = 1\n' })
    const wrapper = mount(ScriptStepForm, { props: { modelValue: step } })

    // Esperar a que onMounted haga el import dinámico y llame createEditor.
    await new Promise((r) => setTimeout(r, 0))
    await wrapper.vm.$nextTick()

    expect(onChangeRef.value).toBeTypeOf('function')
    onChangeRef.value!('y = 2\n')

    const events = wrapper.emitted('update:modelValue')!
    const last = events[events.length - 1][0] as ScriptStep
    expect(last.script).toBe('y = 2\n')
  })
})
```

- [ ] **Step 2: Verificar que el test falla**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run tests/ScriptStepForm.test.ts
```

Expected: FAIL — el test nuevo da `onChangeRef.value` null porque aún no se monta el editor.

- [ ] **Step 3: Implementar el montaje del editor en el componente**

Abrir `web/frontend/src/components/pipeline/forms/ScriptStepForm.vue`. Sustituir el bloque `<script setup>` actual por:

```ts
<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, shallowRef } from 'vue'
import type { ScriptStep } from '@/api/types-pipeline'
import type { EditorHandle } from './script-editor/editor'

const props = defineProps<{ modelValue: ScriptStep }>()
const emit = defineEmits<{ 'update:modelValue': [step: ScriptStep] }>()

const editorHost = ref<HTMLDivElement | null>(null)
const editorHandle = shallowRef<EditorHandle | null>(null)
const editorError = ref<string | null>(null)

function patch(update: Partial<ScriptStep>): void {
  emit('update:modelValue', { ...props.modelValue, ...update })
}

function onEntryPointBlur(ev: Event): void {
  const raw = (ev.target as HTMLInputElement).value.trim()
  const next = raw === '' ? 'process' : raw
  if (next !== props.modelValue.entry_point) {
    patch({ entry_point: next })
  }
}

onMounted(async () => {
  if (!editorHost.value) return
  try {
    const { createEditor } = await import('./script-editor/editor')
    editorHandle.value = await createEditor({
      parent: editorHost.value,
      initialDoc: props.modelValue.script,
      onChange: (doc) => patch({ script: doc }),
    })
  } catch (err) {
    console.error('[ScriptStepForm] falló la carga del editor', err)
    editorError.value = 'No se pudo cargar el editor de código. Recarga la página o prueba de nuevo.'
  }
})

onBeforeUnmount(() => {
  editorHandle.value?.destroy()
  editorHandle.value = null
})
</script>
```

Sustituir el `<template>` actual por (nota: se reemplaza el `data-test="editor-placeholder"` por el host del editor):

```vue
<template>
  <div class="space-y-4">
    <!-- Activo -->
    <div class="flex items-center gap-2">
      <input
        id="script_enabled"
        type="checkbox"
        :checked="modelValue.enabled"
        @change="(e) => patch({ enabled: (e.target as HTMLInputElement).checked })"
      />
      <label for="script_enabled" class="text-sm">Activo</label>
    </div>

    <!-- Nombre -->
    <div>
      <label for="script_label" class="block text-sm font-medium mb-1">Nombre</label>
      <input
        id="script_label"
        type="text"
        data-test="field-label"
        :value="modelValue.label"
        @input="(e) => patch({ label: (e.target as HTMLInputElement).value })"
        placeholder="Ej: Asignar roles barcode"
        class="w-full border border-surface-0 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
      />
    </div>

    <!-- Función -->
    <div>
      <label for="script_entry" class="block text-sm font-medium mb-1">Función</label>
      <input
        id="script_entry"
        type="text"
        data-test="field-entry-point"
        :value="modelValue.entry_point"
        @input="(e) => patch({ entry_point: (e.target as HTMLInputElement).value })"
        @blur="onEntryPointBlur"
        placeholder="process"
        title="Nombre de la función Python a ejecutar"
        class="w-full border border-surface-0 rounded-md px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary/40"
      />
      <p class="text-xs text-subtext mt-1">Nombre de la función Python a ejecutar (default: <code>process</code>).</p>
    </div>

    <!-- Editor de código -->
    <div>
      <label class="block text-sm font-medium mb-1">Código Python</label>
      <div
        v-if="editorError"
        class="p-4 text-sm bg-red-50 border border-red-200 rounded"
      >
        {{ editorError }}
      </div>
      <div
        v-else
        ref="editorHost"
        data-test="editor-host"
        class="border border-surface-0 rounded-md overflow-hidden"
        style="min-height: 420px; height: 420px;"
      ></div>
    </div>
  </div>
</template>
```

- [ ] **Step 4: Verificar que los 6 tests pasan**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run tests/ScriptStepForm.test.ts
```

Expected: 6/6 PASS.

- [ ] **Step 5: Ejecutar la suite completa**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run
```

Expected: 70/70 PASS.

- [ ] **Step 6: Commit**

```bash
git add web/frontend/src/components/pipeline/forms/ScriptStepForm.vue web/frontend/tests/ScriptStepForm.test.ts
git commit -m "feat(web-frontend): montar CodeMirror lazy en ScriptStepForm"
```

---

## Task 8: `ScriptStepForm.vue` — menú de snippets

**Files:**
- Modify: `web/frontend/src/components/pipeline/forms/ScriptStepForm.vue`
- Modify: `web/frontend/tests/ScriptStepForm.test.ts`

- [ ] **Step 1: Añadir los tests de snippets**

Dentro del fichero de tests, añadir un nuevo `describe` al final:

```ts
describe('ScriptStepForm — snippets', () => {
  beforeEach(() => {
    insertAtCursorMock.mockClear()
    destroyMock.mockClear()
    onChangeRef.value = null
    localStorage.clear()
  })

  it('el dropdown lista los 4 snippets disponibles', async () => {
    const wrapper = mount(ScriptStepForm, { props: { modelValue: makeStep() } })
    await new Promise((r) => setTimeout(r, 0))
    await wrapper.vm.$nextTick()

    const button = wrapper.find('[data-test="snippets-button"]')
    await button.trigger('click')
    const items = wrapper.findAll('[data-test="snippet-item"]')
    expect(items).toHaveLength(4)
    const labels = items.map((it) => it.text())
    expect(labels.some((l) => l.includes('Asignar primer barcode'))).toBe(true)
  })

  it('elegir un snippet invoca insertAtCursor con su code', async () => {
    const wrapper = mount(ScriptStepForm, { props: { modelValue: makeStep() } })
    await new Promise((r) => setTimeout(r, 0))
    await wrapper.vm.$nextTick()

    await wrapper.find('[data-test="snippets-button"]').trigger('click')
    const items = wrapper.findAll('[data-test="snippet-item"]')
    await items[0].trigger('click')

    expect(insertAtCursorMock).toHaveBeenCalledTimes(1)
    const arg = insertAtCursorMock.mock.calls[0][0] as string
    expect(arg).toContain('page.barcodes')
    expect(arg).toContain('page.fields["documento"]')
  })
})
```

- [ ] **Step 2: Verificar que los tests fallan**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run tests/ScriptStepForm.test.ts
```

Expected: FAIL — no existen los elementos `[data-test="snippets-button"]`/`[data-test="snippet-item"]`.

- [ ] **Step 3: Añadir imports, estado y funciones en `<script setup>`**

En `web/frontend/src/components/pipeline/forms/ScriptStepForm.vue`, actualizar imports y añadir estado/funciones:

```ts
import { onMounted, onBeforeUnmount, ref, shallowRef } from 'vue'
import type { ScriptStep } from '@/api/types-pipeline'
import type { EditorHandle } from './script-editor/editor'
import { SNIPPETS } from '@/api/script-context-help'
```

Dentro de `<script setup>`, tras `onBeforeUnmount(…)`, añadir:

```ts
const snippetsOpen = ref(false)

function toggleSnippets(): void {
  snippetsOpen.value = !snippetsOpen.value
}

function applySnippet(id: string): void {
  const snippet = SNIPPETS.find((s) => s.id === id)
  if (!snippet || !editorHandle.value) return
  editorHandle.value.insertAtCursor(snippet.code)
  snippetsOpen.value = false
}
```

- [ ] **Step 4: Añadir el botón y dropdown en el template**

En el `<template>`, reemplazar el bloque actual del editor por:

```vue
<!-- Editor de código -->
<div>
  <div class="flex items-center justify-between mb-1">
    <label class="block text-sm font-medium">Código Python</label>
    <div class="relative">
      <button
        type="button"
        data-test="snippets-button"
        @click="toggleSnippets"
        class="text-xs text-primary hover:text-primary-hover border border-primary/40 rounded px-2 py-1"
      >
        Insertar snippet ▾
      </button>
      <div
        v-if="snippetsOpen"
        class="absolute right-0 mt-1 w-80 bg-white rounded-md border border-surface-0 shadow-lg py-1 z-10"
      >
        <button
          v-for="snippet in SNIPPETS"
          :key="snippet.id"
          type="button"
          data-test="snippet-item"
          @click="applySnippet(snippet.id)"
          class="w-full text-left px-3 py-2 hover:bg-surface-0"
        >
          <div class="text-sm font-medium">{{ snippet.label }}</div>
          <div class="text-xs text-subtext">{{ snippet.description }}</div>
        </button>
      </div>
    </div>
  </div>
  <div
    v-if="editorError"
    class="p-4 text-sm bg-red-50 border border-red-200 rounded"
  >
    {{ editorError }}
  </div>
  <div
    v-else
    ref="editorHost"
    data-test="editor-host"
    class="border border-surface-0 rounded-md overflow-hidden"
    style="min-height: 420px; height: 420px;"
  ></div>
</div>
```

- [ ] **Step 5: Verificar que los 8 tests pasan**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run tests/ScriptStepForm.test.ts
```

Expected: 8/8 PASS.

- [ ] **Step 6: Ejecutar la suite completa**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run
```

Expected: 72/72 PASS.

- [ ] **Step 7: Commit**

```bash
git add web/frontend/src/components/pipeline/forms/ScriptStepForm.vue web/frontend/tests/ScriptStepForm.test.ts
git commit -m "feat(web-frontend): menú de snippets insertables en ScriptStepForm"
```

---

## Task 9: `ScriptStepForm.vue` — panel lateral de ayuda colapsable

**Files:**
- Modify: `web/frontend/src/components/pipeline/forms/ScriptStepForm.vue`
- Modify: `web/frontend/tests/ScriptStepForm.test.ts`

- [ ] **Step 1: Añadir el test del panel colapsable**

Al final del fichero de tests, añadir un nuevo `describe`:

```ts
describe('ScriptStepForm — panel de ayuda', () => {
  beforeEach(() => {
    insertAtCursorMock.mockClear()
    destroyMock.mockClear()
    onChangeRef.value = null
    localStorage.clear()
    // Simular viewport md+ (≥768 px).
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1280 })
  })

  it('colapsar el panel persiste helpPanelOpen=false en localStorage', async () => {
    const wrapper = mount(ScriptStepForm, { props: { modelValue: makeStep() } })
    await new Promise((r) => setTimeout(r, 0))
    await wrapper.vm.$nextTick()

    // Por defecto en viewport ≥md el panel está abierto.
    expect(wrapper.find('[data-test="help-panel"]').exists()).toBe(true)

    await wrapper.find('[data-test="help-toggle"]').trigger('click')

    expect(wrapper.find('[data-test="help-panel"]').exists()).toBe(false)
    expect(localStorage.getItem('scriptEditor.helpPanelOpen')).toBe('false')

    // Re-montar y comprobar que persiste cerrado.
    wrapper.unmount()
    const wrapper2 = mount(ScriptStepForm, { props: { modelValue: makeStep() } })
    await new Promise((r) => setTimeout(r, 0))
    await wrapper2.vm.$nextTick()
    expect(wrapper2.find('[data-test="help-panel"]').exists()).toBe(false)
  })
})
```

- [ ] **Step 2: Verificar que el test falla**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run tests/ScriptStepForm.test.ts
```

Expected: FAIL — no existen `[data-test="help-panel"]` ni `[data-test="help-toggle"]`.

- [ ] **Step 3: Añadir imports y estado en `<script setup>`**

Actualizar imports:

```ts
import { onMounted, onBeforeUnmount, ref, shallowRef } from 'vue'
import type { ScriptStep } from '@/api/types-pipeline'
import type { EditorHandle } from './script-editor/editor'
import { SNIPPETS, CONTEXT_VARIABLES } from '@/api/script-context-help'
```

Tras la declaración de `snippetsOpen`, añadir:

```ts
const HELP_PANEL_KEY = 'scriptEditor.helpPanelOpen'

function resolveInitialPanelOpen(): boolean {
  const stored = localStorage.getItem(HELP_PANEL_KEY)
  if (stored === 'true' || stored === 'false') return stored === 'true'
  return window.innerWidth >= 768
}

const helpPanelOpen = ref(resolveInitialPanelOpen())

function toggleHelpPanel(): void {
  helpPanelOpen.value = !helpPanelOpen.value
  localStorage.setItem(HELP_PANEL_KEY, String(helpPanelOpen.value))
}

function copyToClipboard(text: string): void {
  navigator.clipboard?.writeText(text).catch(() => {
    // silencioso: si falla, el usuario puede copiar manualmente
  })
}
```

- [ ] **Step 4: Reestructurar el template (editor + panel lado a lado)**

Reemplazar el bloque del editor por:

```vue
<!-- Editor de código + panel lateral -->
<div>
  <div class="flex items-center justify-between mb-1">
    <label class="block text-sm font-medium">Código Python</label>
    <div class="flex items-center gap-2">
      <button
        v-if="!helpPanelOpen"
        type="button"
        data-test="help-toggle"
        @click="toggleHelpPanel"
        class="text-xs text-subtext hover:text-text border border-surface-0 rounded px-2 py-1"
      >
        Ayuda →
      </button>
      <div class="relative">
        <button
          type="button"
          data-test="snippets-button"
          @click="toggleSnippets"
          class="text-xs text-primary hover:text-primary-hover border border-primary/40 rounded px-2 py-1"
        >
          Insertar snippet ▾
        </button>
        <div
          v-if="snippetsOpen"
          class="absolute right-0 mt-1 w-80 bg-white rounded-md border border-surface-0 shadow-lg py-1 z-10"
        >
          <button
            v-for="snippet in SNIPPETS"
            :key="snippet.id"
            type="button"
            data-test="snippet-item"
            @click="applySnippet(snippet.id)"
            class="w-full text-left px-3 py-2 hover:bg-surface-0"
          >
            <div class="text-sm font-medium">{{ snippet.label }}</div>
            <div class="text-xs text-subtext">{{ snippet.description }}</div>
          </button>
        </div>
      </div>
    </div>
  </div>

  <div class="flex gap-3">
    <!-- Editor -->
    <div class="flex-1 min-w-0">
      <div
        v-if="editorError"
        class="p-4 text-sm bg-red-50 border border-red-200 rounded"
      >
        {{ editorError }}
      </div>
      <div
        v-else
        ref="editorHost"
        data-test="editor-host"
        class="border border-surface-0 rounded-md overflow-hidden"
        style="min-height: 420px; height: 420px;"
      ></div>
    </div>

    <!-- Panel lateral de ayuda -->
    <aside
      v-if="helpPanelOpen"
      data-test="help-panel"
      class="w-64 flex-shrink-0 border border-surface-0 rounded-md bg-surface-0/30 overflow-y-auto"
      style="max-height: 420px;"
    >
      <div class="flex items-center justify-between px-3 py-2 border-b border-surface-0">
        <div class="text-xs font-medium uppercase tracking-wide text-subtext">Variables</div>
        <button
          type="button"
          data-test="help-toggle"
          @click="toggleHelpPanel"
          class="text-xs text-subtext hover:text-text"
        >
          ← Ocultar
        </button>
      </div>
      <ul class="p-2 space-y-2 text-xs">
        <li v-for="v in CONTEXT_VARIABLES" :key="v.name">
          <button
            type="button"
            class="font-mono font-semibold text-primary hover:underline"
            @click="copyToClipboard(v.name)"
            :title="`Copiar «${v.name}»`"
          >{{ v.name }}</button>
          <span class="text-subtext"> — {{ v.summary }}</span>
          <ul v-if="v.members" class="pl-4 mt-1 space-y-0.5">
            <li v-for="m in v.members" :key="m.name">
              <button
                type="button"
                class="font-mono text-text hover:text-primary hover:underline"
                @click="copyToClipboard(`${v.name}.${m.name}`)"
                :title="`Copiar «${v.name}.${m.name}»`"
              >·&nbsp;{{ m.signature ?? m.name }}</button>
              <span class="text-subtext"> — {{ m.description }}</span>
            </li>
          </ul>
        </li>
      </ul>
    </aside>
  </div>
</div>
```

- [ ] **Step 5: Verificar que los 9 tests pasan**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run tests/ScriptStepForm.test.ts
```

Expected: 9/9 PASS.

- [ ] **Step 6: Ejecutar la suite completa**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run
```

Expected: 73/73 PASS (72 previos + 1 nuevo).

- [ ] **Step 7: Commit**

```bash
git add web/frontend/src/components/pipeline/forms/ScriptStepForm.vue web/frontend/tests/ScriptStepForm.test.ts
git commit -m "feat(web-frontend): panel lateral de ayuda colapsable con localStorage"
```

---

## Task 10: Activar `script` en `AddStepMenu.vue`

**Files:**
- Modify: `web/frontend/src/components/pipeline/AddStepMenu.vue`

- [ ] **Step 1: Reemplazar el bloque "Próximamente" por el botón activo**

Abrir `web/frontend/src/components/pipeline/AddStepMenu.vue`. Localizar desde `<div class="border-t border-surface-0 my-1"></div>` hasta el cierre del último `<div class="w-full text-left px-3 py-2 text-sm text-subtext flex items-center gap-2 cursor-not-allowed">` y reemplazar todo ese bloque por:

```vue
<button
  @click="pick('script')"
  class="w-full text-left px-3 py-2 text-sm hover:bg-surface-0 flex items-center gap-2"
>
  <span class="w-2 h-2 rounded-full bg-violet-500"></span>
  <span>Script Python</span>
  <span class="ml-auto text-xs text-subtext">v4</span>
</button>
```

Además, el botón de OCR debe quedar fuera de la sección "Próximamente" (pasa a estar al mismo nivel que Barcode e ImageOp). Verificar el bloque resultante: debe contener 4 botones consecutivos (Barcode v1, ImageOp v2, OCR v3, Script v4) sin separadores `border-t` ni títulos "Próximamente" entre ellos.

Resultado esperado en el template del menú:

```vue
<div
  v-if="open"
  class="absolute right-0 mt-1 w-64 bg-white rounded-md border border-surface-0 shadow-lg py-1 z-10"
>
  <button @click="pick('barcode')" …>Barcode v1</button>
  <button @click="pick('image_op')" …>Operación de imagen v2</button>
  <button @click="pick('ocr')" …>OCR v3</button>
  <button @click="pick('script')" …>Script Python v4</button>
</div>
```

- [ ] **Step 2: Verificar que la suite sigue verde**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run
```

Expected: 73/73 PASS.

- [ ] **Step 3: Commit**

```bash
git add web/frontend/src/components/pipeline/AddStepMenu.vue
git commit -m "feat(web-frontend): habilitar script en AddStepMenu"
```

---

## Task 11: Integrar `ScriptStepForm` en `PipelineStepDrawer.vue`

**Files:**
- Modify: `web/frontend/src/components/pipeline/PipelineStepDrawer.vue`

- [ ] **Step 1: Actualizar imports y añadir lazy component**

Abrir `web/frontend/src/components/pipeline/PipelineStepDrawer.vue`. Reemplazar el bloque de imports por:

```ts
import { ref, watch, computed, defineAsyncComponent } from 'vue'
import type { PipelineStep, BarcodeStep, ImageOpStep, OcrStep, ScriptStep } from '@/api/types-pipeline'
import BarcodeStepForm from './forms/BarcodeStepForm.vue'
import ImageOpStepForm from './forms/ImageOpStepForm.vue'
import OcrStepForm from './forms/OcrStepForm.vue'

const ScriptStepForm = defineAsyncComponent(
  () => import('./forms/ScriptStepForm.vue'),
)
```

- [ ] **Step 2: Extender `isEditable`**

Reemplazar:
```ts
const isEditable = computed(
  () =>
    props.step?.type === 'barcode' ||
    props.step?.type === 'image_op' ||
    props.step?.type === 'ocr',
)
```

Por:
```ts
const isEditable = computed(
  () =>
    props.step?.type === 'barcode' ||
    props.step?.type === 'image_op' ||
    props.step?.type === 'ocr' ||
    props.step?.type === 'script',
)
```

- [ ] **Step 3: Ancho del drawer condicional**

Reemplazar la línea:
```vue
<div
  class="absolute top-0 right-0 bottom-0 w-full max-w-lg bg-white shadow-2xl flex flex-col"
>
```

Por:
```vue
<div
  :class="[
    'absolute top-0 right-0 bottom-0 w-full bg-white shadow-2xl flex flex-col',
    draft?.type === 'script' ? 'max-w-4xl' : 'max-w-lg',
  ]"
>
```

- [ ] **Step 4: Añadir rama `script` en el template y eliminar fallback**

Reemplazar el bloque del `<div class="flex-1 overflow-y-auto p-4">`:

```vue
<div class="flex-1 overflow-y-auto p-4">
  <BarcodeStepForm
    v-if="draft?.type === 'barcode'"
    :model-value="draft as BarcodeStep"
    @update:model-value="onDraftUpdate"
    @validity-change="(v) => (valid = v)"
  />
  <ImageOpStepForm
    v-else-if="draft?.type === 'image_op'"
    :model-value="draft as ImageOpStep"
    @update:model-value="onDraftUpdate"
  />
  <OcrStepForm
    v-else-if="draft?.type === 'ocr'"
    :model-value="draft as OcrStep"
    @update:model-value="onDraftUpdate"
  />
  <ScriptStepForm
    v-else-if="draft?.type === 'script'"
    :model-value="draft as ScriptStep"
    @update:model-value="onDraftUpdate"
  />
</div>
```

(Se elimina el `<div v-else>` con el mensaje *"Este tipo de step se edita desde el configurador de escritorio"*.)

- [ ] **Step 5: Verificar que la suite sigue verde**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run
```

Expected: 73/73 PASS.

- [ ] **Step 6: Verificar build y chunk separado**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run build
```

Expected: build OK. Verificar visualmente en el output de Vite que aparecen al menos dos chunks nuevos:
- uno para `ScriptStepForm` (contiene `@codemirror/*`, `@lezer/*`) — peso ~200 KB gzipped.
- Puede aparecer también un chunk para `script-editor/editor`.

Si no se ve el chunk, comprobar que el import en el drawer es `defineAsyncComponent(() => import('./forms/ScriptStepForm.vue'))` y que dentro de `ScriptStepForm.vue` el import al wrapper es también dinámico: `await import('./script-editor/editor')`.

- [ ] **Step 7: Commit**

```bash
git add web/frontend/src/components/pipeline/PipelineStepDrawer.vue
git commit -m "feat(web-frontend): integrar ScriptStepForm en drawer con lazy load"
```

---

## Task 12: Summary de `script` en `PipelineStepRow.vue`

**Files:**
- Modify: `web/frontend/src/components/pipeline/PipelineStepRow.vue`

- [ ] **Step 1: Añadir import de `ScriptStep`**

Abrir `web/frontend/src/components/pipeline/PipelineStepRow.vue`. Reemplazar:

```ts
import type { PipelineStep, BarcodeStep, ImageOpStep, OcrStep } from '@/api/types-pipeline'
```

Por:

```ts
import type { PipelineStep, BarcodeStep, ImageOpStep, OcrStep, ScriptStep } from '@/api/types-pipeline'
```

- [ ] **Step 2: Añadir la rama `script` en el `computed` `summary`**

Justo antes del `return 'Editable desde configurador de escritorio'` del final del computed, añadir:

```ts
if (s.type === 'script') {
  const sc = s as ScriptStep
  const name = sc.label?.trim() || 'Script sin nombre'
  const entry = sc.entry_point?.trim() || 'process'
  const lines = (sc.script?.match(/\n/g)?.length ?? 0) + (sc.script ? 1 : 0)
  return `${name} · ${entry}() · ${lines} líneas`
}
```

- [ ] **Step 3: Verificar que la suite sigue verde**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run
```

Expected: 73/73 PASS.

- [ ] **Step 4: Commit**

```bash
git add web/frontend/src/components/pipeline/PipelineStepRow.vue
git commit -m "feat(web-frontend): resumen compacto para script en la fila"
```

---

## Task 13: QA manual y cierre

**Sin commits.** Validación end-to-end según criterios de éxito del spec.

- [ ] **Step 1: Arrancar el entorno local**

Abrir tres terminales:

```bash
# Terminal 1
docker start docscan-pg

# Terminal 2
cd /media/nicolas/DATA/Tecnomedia/FlexiPy && source .venv/bin/activate
uvicorn web.api.main:create_app --factory --reload --port 8001

# Terminal 3
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run dev
```

- [ ] **Step 2: Login y navegar al pipeline de la app de prueba**

Abrir `http://localhost:5173`, login como `demo2@demo.com / demo12345`, abrir la aplicación id 8 "Pipeline Test v1" y su pestaña Pipeline.

- [ ] **Step 3: Crear un ScriptStep**

Pulsar `+ Añadir step`, elegir `Script Python`. Verificar:
- El drawer se ensancha (más que para los otros tipos).
- Aparece la plantilla por defecto con `def process(app, batch, page, pipeline):`.
- El panel lateral de ayuda muestra las variables del contexto.
- El autocompletado funciona al escribir `page.` dentro del editor.

- [ ] **Step 4: Insertar un snippet**

Pulsar `Insertar snippet ▾` → elegir `Asignar primer barcode a page.fields`. Verificar que el código se inserta en la posición del cursor.

- [ ] **Step 5: Guardar y recargar**

Guardar el step, guardar el pipeline completo (`Guardar` en la página). Recargar la página con F5. Reabrir el ScriptStep y verificar que todo el contenido se mantiene (label, entry_point, script).

- [ ] **Step 6: Verificar en desktop (paridad)**

Abrir el configurador de escritorio, navegar al mismo app id 8, abrir el pipeline y editar el ScriptStep. Verificar que aparecen los mismos 3 campos con los mismos valores.

- [ ] **Step 7: Ejecutar el pipeline**

En desktop, abrir la aplicación "Pipeline Test v1" en Workbench, importar una página de prueba con barcode (`DOC-123`) y ejecutar el pipeline. Verificar en el log:
- Si el script funciona → aparece el valor en `page.fields["documento"]`.
- Si hay un error de sintaxis → aparece en `page.flags.script_errors` sin abortar el lote.

- [ ] **Step 8: Marcar el plan como completado**

Actualizar el informe diario (`docs/progreso_2026-04-21.md` o el que toque) y `memory/project_web_session_next.md` con el nuevo estado.

- [ ] **Step 9: Push al remote**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy && git push origin feature/web
```

Expected: push OK, rama `feature/web` actualizada con todos los commits de v4.

---

## Cierre

- **~73 tests frontend pasando** (55 previos + 18 nuevos: 3 del catálogo + 5 del wrapper + 9 del form + 1 del store).
- **Cero cambios backend.**
- Chunk de CodeMirror separado (~200 KB gzipped) cargado solo al abrir un drawer de script.
- Paridad funcional con el diálogo desktop `ScriptStepDialog`.

**Próximo paso:** actualizar `memory/project_web_session_next.md` marcando v4 como completado y proponiendo el siguiente sub-proyecto (pestañas Imagen/Eventos/Campos/Transferencia/General, según el roadmap).
