# Pestaña Eventos (sub-proyecto 5) — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir la pestaña web de edición de los 13 eventos lifecycle de una aplicación, con editor CodeMirror reutilizable extraído a un componente `<CodeEditor>` genérico y sub-navegación por tabs (Resumen | Pipeline | Eventos) compartida entre las vistas de configuración.

**Architecture:** Frontend puro. El wrapper CodeMirror se desacopla del dominio ScriptStep (renombrado a `code-editor/editor.ts`, acepta `contextVariables` por parámetro, soporta prefijos dotted multi-nivel para `self.api.`). Un componente `<CodeEditor>` reutilizable encapsula editor + snippets + panel de ayuda. `ScriptStepForm` se refactoriza para consumirlo. Una nueva vista `EventsEditorView` monta una sidebar con los 13 eventos + `<CodeEditor>` con contexto adaptado por evento. Un `<AppHeader>` compartido añade tabs entre las vistas de configuración de aplicación. Cero cambios backend.

**Tech Stack:** Vue 3 + TypeScript + Pinia + Tailwind CSS + CodeMirror 6 (ya instalado) + vitest + `@vue/test-utils` + `jsdom`.

**Spec:** `docs/superpowers/specs/2026-04-21-events-tab-design.md`

---

## Estructura de ficheros

### Nuevos

| Fichero | Responsabilidad |
| --- | --- |
| `web/frontend/src/components/CodeEditor.vue` | Componente genérico (~230 líneas). Editor CodeMirror lazy, panel de ayuda colapsable, menú snippets opcional. Props: modelValue, contextVariables, snippets, minHeight, helpPanelStorageKey. |
| `web/frontend/src/components/AppHeader.vue` | Cabecera compartida (~60 líneas). Back link, título, tabs Resumen/Pipeline/Eventos, slot `actions`. |
| `web/frontend/src/api/events-catalog.ts` | Catálogo declarativo con 13 `EventDefinition` + `VERIFICATION_PANEL_VARS`. |
| `web/frontend/src/views/applications/EventsEditorView.vue` | Vista completa (~280 líneas). Sidebar + `<CodeEditor>`, dirty tracking, guardar/deshacer. |
| `web/frontend/tests/CodeEditor.test.ts` | Tests del componente (6). |
| `web/frontend/tests/api/events-catalog.test.ts` | Tests del catálogo (3). |
| `web/frontend/tests/views/EventsEditorView.test.ts` | Tests de la vista (8). |
| `web/frontend/tests/components/AppHeader.test.ts` | Tests del header (2). |

### Movidos / renombrados

| De | A |
| --- | --- |
| `web/frontend/src/components/pipeline/forms/script-editor/editor.ts` | `web/frontend/src/components/code-editor/editor.ts` |
| `web/frontend/tests/script-editor/editor.test.ts` | `web/frontend/tests/code-editor/editor.test.ts` |

### Modificados

| Fichero | Cambio |
| --- | --- |
| `web/frontend/src/components/code-editor/editor.ts` | `createEditor` recibe `contextVariables`; regex dotted extendido a `([\w.]+)\.$`; sin import de `script-context-help`. |
| `web/frontend/src/components/pipeline/forms/ScriptStepForm.vue` | Usa `<CodeEditor>` (pasa de ~240 a ~120 líneas). |
| `web/frontend/src/views/applications/ApplicationDetailView.vue` | Usa `<AppHeader>`; quita botón "Editar pipeline". |
| `web/frontend/src/views/applications/PipelineEditorView.vue` | Usa `<AppHeader>`. |
| `web/frontend/src/router/index.ts` | Ruta `/applications/:id/events` → `EventsEditorView`. |
| `web/frontend/tests/ScriptStepForm.test.ts` | Mock apunta a `@/components/CodeEditor.vue`. |
| `web/frontend/tests/code-editor/editor.test.ts` | `buildContextSuggestions` acepta 2 args + test prefijo multi-nivel. |

### Sin cambios

- Todo el backend.
- Resto del frontend.

---

## Task 1: Desacoplar el wrapper CodeMirror (mover + adaptar API)

**Files:**
- Move: `web/frontend/src/components/pipeline/forms/script-editor/editor.ts` → `web/frontend/src/components/code-editor/editor.ts`
- Move: `web/frontend/tests/script-editor/editor.test.ts` → `web/frontend/tests/code-editor/editor.test.ts`
- Modify: the new `web/frontend/src/components/code-editor/editor.ts`
- Modify: the new `web/frontend/tests/code-editor/editor.test.ts`

- [ ] **Step 1: Mover los dos ficheros**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy
mkdir -p web/frontend/src/components/code-editor
git mv web/frontend/src/components/pipeline/forms/script-editor/editor.ts \
       web/frontend/src/components/code-editor/editor.ts
rmdir web/frontend/src/components/pipeline/forms/script-editor

mkdir -p web/frontend/tests/code-editor
git mv web/frontend/tests/script-editor/editor.test.ts \
       web/frontend/tests/code-editor/editor.test.ts
rmdir web/frontend/tests/script-editor
```

- [ ] **Step 2: Actualizar tests con la nueva firma de `buildContextSuggestions` y añadir el test del prefijo multi-nivel**

Reemplazar el contenido de `web/frontend/tests/code-editor/editor.test.ts` por:

```ts
import { describe, it, expect } from 'vitest'
import {
  shouldPrefixNewline,
  buildContextSuggestions,
} from '@/components/code-editor/editor'
import type { ContextVariable } from '@/api/script-context-help'

const SAMPLE_VARS: ContextVariable[] = [
  { name: 'app', summary: 'AppContext.' },
  { name: 'batch', summary: 'BatchContext.' },
  {
    name: 'page',
    summary: 'PageContext.',
    members: [
      { name: 'image', description: 'np.ndarray.' },
      { name: 'barcodes', description: 'lista.' },
      { name: 'ocr_text', description: 'str.' },
      { name: 'fields', description: 'dict.' },
      { name: 'flags', description: 'dict.' },
    ],
  },
  {
    name: 'self.api',
    summary: 'API de verification panel.',
    members: [
      { name: 'get_page_image', signature: 'get_page_image(index)', description: 'Imagen.' },
      { name: 'navigate_to', signature: 'navigate_to(index)', description: 'Navega.' },
    ],
  },
  { name: 'log', summary: 'logger.' },
]

describe('code-editor/editor — funciones puras', () => {
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
      const out = buildContextSuggestions('', SAMPLE_VARS)
      const names = out.map((o) => o.label)
      expect(names).toEqual(expect.arrayContaining([
        'app', 'batch', 'page', 'self.api', 'log',
      ]))
    })

    it('para prefijo "page." devuelve los members de page', () => {
      const out = buildContextSuggestions('page.', SAMPLE_VARS)
      const names = out.map((o) => o.label)
      expect(names).toEqual(expect.arrayContaining([
        'image', 'barcodes', 'ocr_text', 'fields', 'flags',
      ]))
    })

    it('para prefijo multi-nivel "self.api." devuelve los members de self.api', () => {
      const out = buildContextSuggestions('self.api.', SAMPLE_VARS)
      const names = out.map((o) => o.label)
      expect(names).toEqual(expect.arrayContaining([
        'get_page_image', 'navigate_to',
      ]))
    })

    it('para lista vacía de vars devuelve []', () => {
      expect(buildContextSuggestions('', [])).toEqual([])
      expect(buildContextSuggestions('page.', [])).toEqual([])
    })
  })
})
```

- [ ] **Step 3: Verificar que los tests fallan**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run tests/code-editor/editor.test.ts
```

Expected: FAIL con "buildContextSuggestions expected 2 args but got 1" o similar.

- [ ] **Step 4: Refactorizar el wrapper**

Reemplazar el contenido completo de `web/frontend/src/components/code-editor/editor.ts` por:

```ts
import { EditorState } from '@codemirror/state'
import { EditorView, keymap, lineNumbers, highlightActiveLine } from '@codemirror/view'
import { defaultKeymap, indentWithTab, history, historyKeymap } from '@codemirror/commands'
import { indentOnInput, bracketMatching } from '@codemirror/language'
import { closeBrackets, closeBracketsKeymap } from '@codemirror/autocomplete'
import { autocompletion } from '@codemirror/autocomplete'
import type { CompletionContext, CompletionResult, Completion } from '@codemirror/autocomplete'
import { python } from '@codemirror/lang-python'
import type { ContextVariable } from '@/api/script-context-help'

export interface CreateEditorArgs {
  parent: HTMLElement
  initialDoc: string
  contextVariables: ContextVariable[]
  onChange: (doc: string) => void
}

export interface EditorHandle {
  insertAtCursor: (text: string) => void
  destroy: () => void
}

export function shouldPrefixNewline(currentLineText: string): boolean {
  return currentLineText.trim().length > 0
}

export function buildContextSuggestions(
  prefix: string,
  vars: ContextVariable[],
): Completion[] {
  const dotMatch = prefix.match(/([\w.]+)\.$/)
  if (dotMatch) {
    const varName = dotMatch[1]
    const variable = vars.find((v) => v.name === varName)
    if (!variable?.members) return []
    return variable.members.map((m) => ({
      label: m.name,
      type: m.signature ? 'method' : 'property',
      detail: m.signature,
      info: m.description,
    }))
  }
  return vars.map((v) => ({
    label: v.name,
    type: 'variable',
    info: v.summary,
  }))
}

function buildContextCompletions(vars: ContextVariable[]) {
  return (context: CompletionContext): CompletionResult | null => {
    const line = context.state.doc.lineAt(context.pos)
    const textBeforeCursor = line.text.slice(0, context.pos - line.from)

    const dotMatch = textBeforeCursor.match(/([\w.]+)\.(\w*)$/)
    if (dotMatch) {
      const suggestions = buildContextSuggestions(`${dotMatch[1]}.`, vars)
      if (suggestions.length === 0) return null
      return {
        from: context.pos - dotMatch[2].length,
        options: suggestions,
        validFor: /^\w*$/,
      }
    }

    const wordMatch = textBeforeCursor.match(/(\w+)$/)
    if (wordMatch) {
      return {
        from: context.pos - wordMatch[1].length,
        options: buildContextSuggestions('', vars),
        validFor: /^\w*$/,
      }
    }

    if (context.explicit) {
      return {
        from: context.pos,
        options: buildContextSuggestions('', vars),
        validFor: /^\w*$/,
      }
    }
    return null
  }
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
      autocompletion({ override: [buildContextCompletions(args.contextVariables)] }),
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

  return { insertAtCursor, destroy }
}
```

Cambios clave vs. v4:
- `buildContextSuggestions(prefix, vars)` — gana parámetro `vars`.
- `contextCompletions` pasa a ser `buildContextCompletions(vars)` que devuelve la función — permite cerrar sobre `vars` sin globales.
- Regex dotted `([\w.]+)\.` — soporta `self.api.`.
- Quitan los `TOP_LEVEL_COMPLETIONS`/`MEMBER_COMPLETIONS` globales (se construyen por llamada; para cada instancia el coste es despreciable y el wrapper queda sin estado global).
- Ya no importa `CONTEXT_VARIABLES` — solo el tipo `ContextVariable`.

- [ ] **Step 5: Actualizar el único consumer todavía existente — `ScriptStepForm.vue` — para pasar `contextVariables`**

Abrir `web/frontend/src/components/pipeline/forms/ScriptStepForm.vue`. Localizar el `onMounted` que hace `await import('./script-editor/editor')` y actualizar:

```ts
import { CONTEXT_VARIABLES, SNIPPETS } from '@/api/script-context-help'
// ... resto de imports

onMounted(async () => {
  if (!editorHost.value) return
  try {
    const { createEditor } = await import('@/components/code-editor/editor')
    if (cancelled || !editorHost.value) return
    const handle = await createEditor({
      parent: editorHost.value,
      initialDoc: props.modelValue.script,
      contextVariables: CONTEXT_VARIABLES,
      onChange: (doc) => patch({ script: doc }),
    })
    if (cancelled) {
      handle.destroy()
      return
    }
    editorHandle.value = handle
  } catch (err) {
    if (cancelled) return
    console.error('[ScriptStepForm] falló la carga del editor', err)
    editorError.value = 'No se pudo cargar el editor de código. Recarga la página o prueba de nuevo.'
  }
})
```

Cambios: `import(...)` apunta a `@/components/code-editor/editor`, y se pasa `contextVariables: CONTEXT_VARIABLES`.

- [ ] **Step 6: Actualizar el mock del test de ScriptStepForm**

Abrir `web/frontend/tests/ScriptStepForm.test.ts`. Localizar:

```ts
vi.mock('@/components/pipeline/forms/script-editor/editor', () => ({
```

Cambiar por:

```ts
vi.mock('@/components/code-editor/editor', () => ({
```

(la forma del mock interno se mantiene igual).

- [ ] **Step 7: Verificar que toda la suite pasa**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run
```

Expected: 74/74 PASS (73 anteriores + 1 nuevo test de prefijo multi-nivel en el wrapper).

- [ ] **Step 8: Commit**

```bash
git add web/frontend/src/components/code-editor/editor.ts \
        web/frontend/tests/code-editor/editor.test.ts \
        web/frontend/src/components/pipeline/forms/ScriptStepForm.vue \
        web/frontend/tests/ScriptStepForm.test.ts
git commit -m "refactor(web-frontend): desacoplar wrapper CodeMirror a code-editor/"
```

---

## Task 2: Crear `<CodeEditor>` componente

**Files:**
- Create: `web/frontend/src/components/CodeEditor.vue`
- Create: `web/frontend/tests/CodeEditor.test.ts`

- [ ] **Step 1: Escribir los tests del componente**

Crear `web/frontend/tests/CodeEditor.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import CodeEditor from '@/components/CodeEditor.vue'
import type { ContextVariable, Snippet } from '@/api/script-context-help'

const insertAtCursorMock = vi.fn()
const destroyMock = vi.fn()
const onChangeRef: { value: ((doc: string) => void) | null } = { value: null }
const createEditorMock = vi.fn()

vi.mock('@/components/code-editor/editor', () => ({
  createEditor: vi.fn(async (args: { onChange: (doc: string) => void }) => {
    onChangeRef.value = args.onChange
    createEditorMock(args)
    return {
      insertAtCursor: insertAtCursorMock,
      destroy: destroyMock,
    }
  }),
  shouldPrefixNewline: vi.fn(() => false),
  buildContextSuggestions: vi.fn(() => []),
}))

const SAMPLE_VARS: ContextVariable[] = [
  { name: 'app', summary: 'AppContext.' },
]

const SAMPLE_SNIPPETS: Snippet[] = [
  { id: 's1', label: 'Hola mundo', description: 'Ejemplo', code: 'log.info("hola")\n' },
  { id: 's2', label: 'Otro', description: 'Otro', code: 'pass\n' },
]

describe('CodeEditor', () => {
  beforeEach(() => {
    insertAtCursorMock.mockClear()
    destroyMock.mockClear()
    createEditorMock.mockClear()
    onChangeRef.value = null
    localStorage.clear()
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1280 })
  })

  it('sin snippets oculta el botón Insertar snippet', async () => {
    const wrapper = mount(CodeEditor, {
      props: { modelValue: 'x=1', contextVariables: SAMPLE_VARS },
    })
    await new Promise((r) => setTimeout(r, 0))
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-test="snippets-button"]').exists()).toBe(false)
  })

  it('cuando el editor dispara onChange, emite update:modelValue', async () => {
    const wrapper = mount(CodeEditor, {
      props: { modelValue: 'x=1', contextVariables: SAMPLE_VARS },
    })
    await new Promise((r) => setTimeout(r, 0))
    await wrapper.vm.$nextTick()

    expect(onChangeRef.value).toBeTypeOf('function')
    onChangeRef.value!('y=2')

    const events = wrapper.emitted('update:modelValue')!
    expect(events[events.length - 1][0]).toBe('y=2')
  })

  it('cambios posteriores a modelValue NO se propagan al editor', async () => {
    const wrapper = mount(CodeEditor, {
      props: { modelValue: 'x=1', contextVariables: SAMPLE_VARS },
    })
    await new Promise((r) => setTimeout(r, 0))
    await wrapper.vm.$nextTick()

    // Cambio externo de modelValue no debe llamar a createEditor una segunda vez
    await wrapper.setProps({ modelValue: 'y=2', contextVariables: SAMPLE_VARS })
    await wrapper.vm.$nextTick()
    expect(createEditorMock).toHaveBeenCalledTimes(1)
  })

  it('elegir un snippet llama a insertAtCursor con su code', async () => {
    const wrapper = mount(CodeEditor, {
      props: { modelValue: '', contextVariables: SAMPLE_VARS, snippets: SAMPLE_SNIPPETS },
    })
    await new Promise((r) => setTimeout(r, 0))
    await wrapper.vm.$nextTick()

    await wrapper.find('[data-test="snippets-button"]').trigger('click')
    const items = wrapper.findAll('[data-test="snippet-item"]')
    expect(items).toHaveLength(2)
    await items[0].trigger('click')

    expect(insertAtCursorMock).toHaveBeenCalledTimes(1)
    expect(insertAtCursorMock.mock.calls[0][0]).toBe('log.info("hola")\n')
  })

  it('colapsar el panel persiste en localStorage bajo la clave configurada', async () => {
    const wrapper = mount(CodeEditor, {
      props: {
        modelValue: '', contextVariables: SAMPLE_VARS,
        helpPanelStorageKey: 'customKey',
      },
    })
    await new Promise((r) => setTimeout(r, 0))
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[data-test="help-panel"]').exists()).toBe(true)
    await wrapper.find('[data-test="help-close"]').trigger('click')
    expect(wrapper.find('[data-test="help-panel"]').exists()).toBe(false)
    expect(localStorage.getItem('customKey')).toBe('false')
  })

  it('en unmount llama a destroy exactamente una vez', async () => {
    const wrapper = mount(CodeEditor, {
      props: { modelValue: 'x=1', contextVariables: SAMPLE_VARS },
    })
    await new Promise((r) => setTimeout(r, 0))
    await wrapper.vm.$nextTick()

    wrapper.unmount()
    await new Promise((r) => setTimeout(r, 0))
    expect(destroyMock).toHaveBeenCalledTimes(1)
  })
})
```

- [ ] **Step 2: Verificar que los tests fallan**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run tests/CodeEditor.test.ts
```

Expected: FAIL con "Cannot find module '@/components/CodeEditor.vue'".

- [ ] **Step 3: Crear el componente**

Crear `web/frontend/src/components/CodeEditor.vue`:

```vue
<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, shallowRef } from 'vue'
import type { EditorHandle } from './code-editor/editor'
import type { ContextVariable, Snippet } from '@/api/script-context-help'

const props = withDefaults(defineProps<{
  modelValue: string
  contextVariables: ContextVariable[]
  snippets?: Snippet[]
  minHeight?: number
  helpPanelStorageKey?: string
  disabled?: boolean
}>(), {
  snippets: () => [],
  minHeight: 420,
  helpPanelStorageKey: 'codeEditor.helpPanelOpen',
  disabled: false,
})

const emit = defineEmits<{ 'update:modelValue': [doc: string] }>()

const editorHost = ref<HTMLDivElement | null>(null)
const editorHandle = shallowRef<EditorHandle | null>(null)
const editorError = ref<string | null>(null)

const snippetsOpen = ref(false)

function resolveInitialPanelOpen(): boolean {
  const stored = localStorage.getItem(props.helpPanelStorageKey)
  if (stored === 'true' || stored === 'false') return stored === 'true'
  return window.innerWidth >= 768
}
const helpPanelOpen = ref(resolveInitialPanelOpen())

function toggleHelpPanel(): void {
  helpPanelOpen.value = !helpPanelOpen.value
  localStorage.setItem(props.helpPanelStorageKey, String(helpPanelOpen.value))
}

function toggleSnippets(): void {
  snippetsOpen.value = !snippetsOpen.value
}

function applySnippet(id: string): void {
  const snippet = props.snippets.find((s) => s.id === id)
  if (!snippet || !editorHandle.value) return
  editorHandle.value.insertAtCursor(snippet.code)
  snippetsOpen.value = false
}

function copyToClipboard(text: string): void {
  navigator.clipboard?.writeText(text).catch(() => {
    // silencioso: si falla, el usuario puede copiar manualmente
  })
}

let cancelled = false
onMounted(async () => {
  if (!editorHost.value) return
  try {
    const { createEditor } = await import('./code-editor/editor')
    if (cancelled || !editorHost.value) return
    const handle = await createEditor({
      parent: editorHost.value,
      initialDoc: props.modelValue,
      contextVariables: props.contextVariables,
      onChange: (doc) => emit('update:modelValue', doc),
    })
    if (cancelled) {
      handle.destroy()
      return
    }
    editorHandle.value = handle
  } catch (err) {
    if (cancelled) return
    console.error('[CodeEditor] falló la carga del editor', err)
    editorError.value = 'No se pudo cargar el editor de código. Recarga la página o prueba de nuevo.'
  }
})

onBeforeUnmount(() => {
  cancelled = true
  editorHandle.value?.destroy()
  editorHandle.value = null
})
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-1">
      <label class="block text-sm font-medium">Código Python</label>
      <div class="flex items-center gap-2">
        <button
          v-if="!helpPanelOpen"
          type="button"
          data-test="help-open"
          @click="toggleHelpPanel"
          class="text-xs text-subtext hover:text-text border border-surface-0 rounded px-2 py-1"
        >
          Ayuda →
        </button>
        <div v-if="snippets.length > 0" class="relative">
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
              v-for="snippet in snippets"
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
          :style="{ minHeight: `${minHeight}px`, height: `${minHeight}px` }"
        ></div>
      </div>

      <aside
        v-if="helpPanelOpen"
        data-test="help-panel"
        class="w-64 flex-shrink-0 border border-surface-0 rounded-md bg-surface-0/30 overflow-y-auto"
        :style="{ maxHeight: `${minHeight}px` }"
      >
        <div class="flex items-center justify-between px-3 py-2 border-b border-surface-0">
          <div class="text-xs font-medium uppercase tracking-wide text-subtext">Variables</div>
          <button
            type="button"
            data-test="help-close"
            @click="toggleHelpPanel"
            class="text-xs text-subtext hover:text-text"
          >
            ← Ocultar
          </button>
        </div>
        <ul class="p-2 space-y-2 text-xs">
          <li v-for="v in contextVariables" :key="v.name">
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
</template>
```

- [ ] **Step 4: Verificar que los 6 tests pasan**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run tests/CodeEditor.test.ts
```

Expected: 6/6 PASS.

- [ ] **Step 5: Ejecutar la suite completa**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run
```

Expected: 80/80 PASS (74 + 6 nuevos).

- [ ] **Step 6: Commit**

```bash
git add web/frontend/src/components/CodeEditor.vue web/frontend/tests/CodeEditor.test.ts
git commit -m "feat(web-frontend): componente CodeEditor genérico"
```

---

## Task 3: Refactorizar `ScriptStepForm.vue` para usar `<CodeEditor>`

**Files:**
- Modify: `web/frontend/src/components/pipeline/forms/ScriptStepForm.vue`
- Modify: `web/frontend/tests/ScriptStepForm.test.ts`

- [ ] **Step 1: Actualizar el mock del test de ScriptStepForm para interceptar `<CodeEditor>` en lugar del wrapper**

Abrir `web/frontend/tests/ScriptStepForm.test.ts`. Localizar el bloque `vi.mock(...)` (las primeras 15 líneas aprox.). Reemplazarlo por:

```ts
const insertAtCursorMock = vi.fn()

let latestUpdateModelValue: ((doc: string) => void) | null = null

vi.mock('@/components/CodeEditor.vue', () => ({
  default: {
    name: 'CodeEditor',
    props: ['modelValue', 'contextVariables', 'snippets', 'minHeight', 'helpPanelStorageKey', 'disabled'],
    emits: ['update:modelValue'],
    setup(props: { snippets?: { id: string; code: string }[] }, ctx: { emit: (name: string, ...args: unknown[]) => void; expose: (methods: Record<string, unknown>) => void }) {
      latestUpdateModelValue = (doc: string) => ctx.emit('update:modelValue', doc)
      ctx.expose({ insertAtCursor: insertAtCursorMock })
      return { snippets: props.snippets ?? [], _fire: latestUpdateModelValue }
    },
    template: `
      <div>
        <div data-test="stub-code-editor"></div>
        <div v-if="snippets.length > 0">
          <button data-test="snippets-button" @click="snippetsOpen = !snippetsOpen">snippets</button>
        </div>
      </div>
    `,
  },
}))
```

La intención del stub: expone `insertAtCursor` via `defineExpose` para que los tests de snippets puedan comprobar la llamada vía un ref; expone `latestUpdateModelValue` para simular cambios del editor; renderiza un `[data-test="stub-code-editor"]` que actúa como el host.

**Nota práctica**: el mock previo exponía `insertAtCursorMock` a través de `editorHandle.value.insertAtCursor`. Ahora lo expone el stub vía `defineExpose`. Algunos tests del form necesitarán adaptarse — pasarán a buscar la llamada a `insertAtCursor` en el mock directamente vía el ref expuesto del componente. **Ver Step 2 para los tests que hay que simplificar**.

- [ ] **Step 2: Simplificar los tests afectados por el cambio de mock**

En el mismo fichero, los tests que dependen de la implementación interna del editor (mount de CodeMirror) se simplifican porque el stub ya no interactúa con `createEditor`. Los tests quedan así (reemplazar el contenido desde el primer `describe`):

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ScriptStepForm from '@/components/pipeline/forms/ScriptStepForm.vue'
import type { ScriptStep } from '@/api/types-pipeline'
import { DEFAULT_SCRIPT_TEMPLATE, SNIPPETS } from '@/api/script-context-help'

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
    localStorage.clear()
    latestUpdateModelValue = null
  })

  it('renderiza Activo, Nombre y Función con los valores iniciales', () => {
    const step = makeStep({ label: 'mi-script', entry_point: 'process' })
    const wrapper = mount(ScriptStepForm, { props: { modelValue: step } })

    expect((wrapper.find('input[type="checkbox"]').element as HTMLInputElement).checked).toBe(true)
    expect((wrapper.find('[data-test="field-label"]').element as HTMLInputElement).value).toBe('mi-script')
    expect((wrapper.find('[data-test="field-entry-point"]').element as HTMLInputElement).value).toBe('process')
  })

  it('cambio de label emite update:modelValue con el nuevo label', async () => {
    const wrapper = mount(ScriptStepForm, { props: { modelValue: makeStep() } })
    await wrapper.find('[data-test="field-label"]').setValue('nuevo-nombre')
    const events = wrapper.emitted('update:modelValue')!
    expect((events[events.length - 1][0] as ScriptStep).label).toBe('nuevo-nombre')
  })

  it('cambio de entry_point emite con el nuevo valor', async () => {
    const wrapper = mount(ScriptStepForm, { props: { modelValue: makeStep() } })
    await wrapper.find('[data-test="field-entry-point"]').setValue('run')
    const events = wrapper.emitted('update:modelValue')!
    expect((events[events.length - 1][0] as ScriptStep).entry_point).toBe('run')
  })

  it('entry_point vacío tras blur se restaura a "process"', async () => {
    const wrapper = mount(ScriptStepForm, { props: { modelValue: makeStep({ entry_point: 'run' }) } })
    const entry = wrapper.find('[data-test="field-entry-point"]')
    await entry.setValue('')
    await entry.trigger('blur')
    const events = wrapper.emitted('update:modelValue')!
    expect((events[events.length - 1][0] as ScriptStep).entry_point).toBe('process')
  })

  it('toggle de enabled emite el booleano invertido', async () => {
    const wrapper = mount(ScriptStepForm, { props: { modelValue: makeStep({ enabled: true }) } })
    await wrapper.find('input[type="checkbox"]').setValue(false)
    const events = wrapper.emitted('update:modelValue')!
    expect((events[events.length - 1][0] as ScriptStep).enabled).toBe(false)
  })
})

describe('ScriptStepForm — editor CodeMirror', () => {
  beforeEach(() => {
    insertAtCursorMock.mockClear()
    latestUpdateModelValue = null
  })

  it('cuando CodeEditor emite update:modelValue, se propaga con patch({script})', async () => {
    const wrapper = mount(ScriptStepForm, {
      props: { modelValue: makeStep({ script: 'x = 1\n' }) },
    })
    await wrapper.vm.$nextTick()
    expect(latestUpdateModelValue).toBeTypeOf('function')
    latestUpdateModelValue!('y = 2\n')
    const events = wrapper.emitted('update:modelValue')!
    expect((events[events.length - 1][0] as ScriptStep).script).toBe('y = 2\n')
  })

  it('pasa CONTEXT_VARIABLES y SNIPPETS al CodeEditor', async () => {
    const wrapper = mount(ScriptStepForm, { props: { modelValue: makeStep() } })
    await wrapper.vm.$nextTick()
    const codeEditor = wrapper.findComponent({ name: 'CodeEditor' })
    expect(codeEditor.exists()).toBe(true)
    expect(codeEditor.props('snippets')).toEqual(SNIPPETS)
    expect(codeEditor.props('helpPanelStorageKey')).toBe('scriptEditor.helpPanelOpen')
  })
})
```

(Los 4 tests eliminados — dropdown de snippets, inserción, colapso panel — ahora son responsabilidad de `CodeEditor.test.ts`. No se pierde cobertura total; se mueve al componente correcto.)

- [ ] **Step 3: Verificar que los tests fallan (porque ScriptStepForm aún no usa CodeEditor)**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run tests/ScriptStepForm.test.ts
```

Expected: FAIL en "pasa CONTEXT_VARIABLES y SNIPPETS al CodeEditor" (findComponent no encuentra CodeEditor).

- [ ] **Step 4: Refactorizar el componente**

Reemplazar el contenido completo de `web/frontend/src/components/pipeline/forms/ScriptStepForm.vue` por:

```vue
<script setup lang="ts">
import type { ScriptStep } from '@/api/types-pipeline'
import { CONTEXT_VARIABLES, SNIPPETS } from '@/api/script-context-help'
import CodeEditor from '@/components/CodeEditor.vue'

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
    <div class="flex items-center gap-2">
      <input
        id="script_enabled"
        type="checkbox"
        :checked="modelValue.enabled"
        @change="(e) => patch({ enabled: (e.target as HTMLInputElement).checked })"
      />
      <label for="script_enabled" class="text-sm">Activo</label>
    </div>

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

    <CodeEditor
      :key="modelValue.id"
      :model-value="modelValue.script"
      :context-variables="CONTEXT_VARIABLES"
      :snippets="SNIPPETS"
      help-panel-storage-key="scriptEditor.helpPanelOpen"
      :min-height="420"
      @update:model-value="(doc) => patch({ script: doc })"
    />
  </div>
</template>
```

Cambios: elimina toda la lógica de editor/snippets/panel (ahora vive en `<CodeEditor>`). El componente baja de ~240 a ~70 líneas (más reducción de la estimada en spec).

- [ ] **Step 5: Verificar que los tests pasan**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run tests/ScriptStepForm.test.ts
```

Expected: 7/7 PASS (5 campos base + 2 integración CodeEditor).

- [ ] **Step 6: Ejecutar la suite completa**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run
```

Expected: 78/78 PASS (80 anteriores − 2 tests eliminados del ScriptStepForm = 78).

- [ ] **Step 7: Verificar build y chunk separado**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run build 2>&1 | grep -E "editor-|CodeEditor|ScriptStepForm"
```

Expected: chunk `editor-*.js` sigue separado (~131 KB gzipped); `CodeEditor` aparece probablemente inline en el bundle que lo consuma (PipelineEditorView); el chunk `ScriptStepForm` se mantiene pequeño.

- [ ] **Step 8: Commit**

```bash
git add web/frontend/src/components/pipeline/forms/ScriptStepForm.vue \
        web/frontend/tests/ScriptStepForm.test.ts
git commit -m "refactor(web-frontend): ScriptStepForm usa CodeEditor genérico"
```

---

## Task 4: Catálogo `events-catalog.ts`

**Files:**
- Create: `web/frontend/src/api/events-catalog.ts`
- Create: `web/frontend/tests/api/events-catalog.test.ts`

- [ ] **Step 1: Escribir los tests del catálogo**

Crear `web/frontend/tests/api/events-catalog.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { EVENT_DEFINITIONS } from '@/api/events-catalog'

const EXPECTED_NAMES = [
  'on_app_start',
  'on_app_end',
  'on_import',
  'on_scan_complete',
  'on_transfer_validate',
  'on_transfer_advanced',
  'on_transfer_page',
  'on_navigate_prev',
  'on_navigate_next',
  'on_navigate_script',
  'on_key_event',
  'init_global',
  'verification_panel',
]

describe('events-catalog', () => {
  it('EVENT_DEFINITIONS tiene 13 entradas con nombres únicos que coinciden con el desktop', () => {
    expect(EVENT_DEFINITIONS).toHaveLength(13)
    const names = EVENT_DEFINITIONS.map((e) => e.name)
    expect(new Set(names).size).toBe(13)
    for (const n of EXPECTED_NAMES) {
      expect(names).toContain(n)
    }
  })

  it('cada template empieza con la firma correcta (def o class)', () => {
    for (const event of EVENT_DEFINITIONS) {
      if (event.name === 'verification_panel') {
        expect(event.template.startsWith('class ')).toBe(true)
      } else {
        expect(event.template.startsWith(`def ${event.name}(`)).toBe(true)
      }
    }
  })

  it('verification_panel expone self.api con ≥9 miembros', () => {
    const vp = EVENT_DEFINITIONS.find((e) => e.name === 'verification_panel')!
    const selfApi = vp.contextVariables.find((v) => v.name === 'self.api')
    expect(selfApi).toBeDefined()
    expect(selfApi!.members?.length ?? 0).toBeGreaterThanOrEqual(9)
    const memberNames = selfApi!.members!.map((m) => m.name)
    expect(memberNames).toEqual(expect.arrayContaining([
      'get_page_image', 'get_page_barcodes', 'navigate_to', 'log',
    ]))
  })
})
```

- [ ] **Step 2: Verificar que los tests fallan**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run tests/api/events-catalog.test.ts
```

Expected: FAIL con "Cannot find module '@/api/events-catalog'".

- [ ] **Step 3: Crear el catálogo**

Crear `web/frontend/src/api/events-catalog.ts`:

```ts
import type { ContextVariable } from './script-context-help'

export interface EventDefinition {
  name: string
  description: string
  signature: string
  template: string
  contextVariables: ContextVariable[]
}

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

function tpl(name: string, args: string, docstring: string): string {
  return `def ${name}(${args}):
    """${docstring}"""
    pass
`
}

export const EVENT_DEFINITIONS: EventDefinition[] = [
  {
    name: 'on_app_start',
    description: 'Al abrir la aplicación.',
    signature: 'on_app_start(app, batch)',
    template: tpl('on_app_start', 'app, batch', 'Se ejecuta al abrir la aplicación en el Workbench.'),
    contextVariables: BASE_VARS,
  },
  {
    name: 'on_app_end',
    description: 'Al cerrar la aplicación.',
    signature: 'on_app_end(app, batch)',
    template: tpl('on_app_end', 'app, batch', 'Se ejecuta al cerrar la aplicación.'),
    contextVariables: BASE_VARS,
  },
  {
    name: 'on_import',
    description: 'Al pulsar Procesar. Reemplaza la carga estándar si está definido.',
    signature: 'on_import(app, batch)',
    template: tpl('on_import', 'app, batch', 'Reemplaza la lógica de importación estándar cuando está definido.'),
    contextVariables: BASE_VARS,
  },
  {
    name: 'on_scan_complete',
    description: 'Al terminar el pipeline sobre todas las páginas del lote.',
    signature: 'on_scan_complete(app, batch)',
    template: tpl('on_scan_complete', 'app, batch', 'Se ejecuta una vez al finalizar el pipeline para todas las páginas.'),
    contextVariables: BASE_VARS,
  },
  {
    name: 'on_transfer_validate',
    description: 'Antes de transferir; retornar False cancela.',
    signature: 'on_transfer_validate(app, batch) -> bool',
    template: `def on_transfer_validate(app, batch):
    """Se ejecuta antes de transferir. Devolver False cancela la transferencia."""
    return True
`,
    contextVariables: BASE_VARS,
  },
  {
    name: 'on_transfer_advanced',
    description: 'Transferencia scripteada (reemplaza la transferencia simple).',
    signature: 'on_transfer_advanced(app, batch, result)',
    template: tpl('on_transfer_advanced', 'app, batch, result', 'Reemplaza la transferencia simple con lógica personalizada.'),
    contextVariables: [...BASE_VARS, RESULT_VAR],
  },
  {
    name: 'on_transfer_page',
    description: 'Post-copia por página durante la transferencia simple.',
    signature: 'on_transfer_page(app, batch, page, result)',
    template: tpl('on_transfer_page', 'app, batch, page, result', 'Se ejecuta tras copiar cada página en la transferencia simple.'),
    contextVariables: [...BASE_VARS, PAGE_VAR, RESULT_VAR],
  },
  {
    name: 'on_navigate_prev',
    description: 'Navegación previa programable.',
    signature: 'on_navigate_prev(app, batch)',
    template: tpl('on_navigate_prev', 'app, batch', 'Handler personalizado de navegación anterior.'),
    contextVariables: BASE_VARS,
  },
  {
    name: 'on_navigate_next',
    description: 'Navegación siguiente programable.',
    signature: 'on_navigate_next(app, batch)',
    template: tpl('on_navigate_next', 'app, batch', 'Handler personalizado de navegación siguiente.'),
    contextVariables: BASE_VARS,
  },
  {
    name: 'on_navigate_script',
    description: 'Botón de navegación programable del visor.',
    signature: 'on_navigate_script(app, batch)',
    template: tpl('on_navigate_script', 'app, batch', 'Handler personalizado del botón de navegación del visor.'),
    contextVariables: BASE_VARS,
  },
  {
    name: 'on_key_event',
    description: 'Tecla personalizada.',
    signature: 'on_key_event(app, batch, key)',
    template: tpl('on_key_event', 'app, batch, key', 'Handler personalizado de eventos de teclado. key es un string con el nombre de la tecla.'),
    contextVariables: [...BASE_VARS, KEY_VAR],
  },
  {
    name: 'init_global',
    description: 'Al iniciar el programa (script global del launcher).',
    signature: 'init_global(app, batch)',
    template: tpl('init_global', 'app, batch', 'Se ejecuta al iniciar el programa (nivel launcher).'),
    contextVariables: BASE_VARS,
  },
  {
    name: 'verification_panel',
    description: 'Panel de verificación (clase VerificationPanel).',
    signature: 'class MyVerificationPanel(VerificationPanel)',
    template: `class MyVerificationPanel(VerificationPanel):
    """Panel de verificación personalizado.

    Métodos sobreescribibles: setup_ui(), on_page_changed(index),
    on_pipeline_completed(index), on_batch_loaded(),
    validate_page(index) -> (bool, str), validate() -> (bool, str), cleanup().
    """

    def setup_ui(self):
        pass
`,
    contextVariables: VERIFICATION_PANEL_VARS,
  },
]
```

- [ ] **Step 4: Verificar que los tests pasan**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run tests/api/events-catalog.test.ts
```

Expected: 3/3 PASS.

- [ ] **Step 5: Ejecutar la suite completa**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run
```

Expected: 81/81 PASS (78 + 3 nuevos).

- [ ] **Step 6: Commit**

```bash
git add web/frontend/src/api/events-catalog.ts web/frontend/tests/api/events-catalog.test.ts
git commit -m "feat(web-frontend): catálogo events-catalog con 13 EventDefinition"
```

---

## Task 5: Componente `<AppHeader>`

**Files:**
- Create: `web/frontend/src/components/AppHeader.vue`
- Create: `web/frontend/tests/components/AppHeader.test.ts`

- [ ] **Step 1: Escribir los tests del header**

Crear `web/frontend/tests/components/AppHeader.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import AppHeader from '@/components/AppHeader.vue'

function makeRouter(initialPath: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/applications', component: { template: '<div/>' } },
      { path: '/applications/:id', component: { template: '<div/>' } },
      { path: '/applications/:id/pipeline', component: { template: '<div/>' } },
      { path: '/applications/:id/events', component: { template: '<div/>' } },
    ],
  })
  router.push(initialPath)
  return router
}

describe('AppHeader', () => {
  it('renderiza las 3 tabs con la activa correcta según la ruta', async () => {
    const router = makeRouter('/applications/8/events')
    await router.isReady()
    const wrapper = mount(AppHeader, {
      props: { appId: 8, appName: 'Demo' },
      global: { plugins: [router] },
    })
    const tabs = wrapper.findAll('[data-test="app-tab"]')
    expect(tabs).toHaveLength(3)
    expect(tabs[0].text()).toBe('Resumen')
    expect(tabs[1].text()).toBe('Pipeline')
    expect(tabs[2].text()).toBe('Eventos')
    expect(tabs[2].classes().join(' ')).toContain('text-primary')
  })

  it('expone un slot "actions" para inyectar botones en la cabecera', async () => {
    const router = makeRouter('/applications/8')
    await router.isReady()
    const wrapper = mount(AppHeader, {
      props: { appId: 8, appName: 'Demo' },
      slots: { actions: '<button data-test="custom-action">Acción</button>' },
      global: { plugins: [router] },
    })
    expect(wrapper.find('[data-test="custom-action"]').exists()).toBe(true)
  })
})
```

- [ ] **Step 2: Verificar que los tests fallan**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run tests/components/AppHeader.test.ts
```

Expected: FAIL con "Cannot find module '@/components/AppHeader.vue'".

- [ ] **Step 3: Crear el componente**

Crear `web/frontend/src/components/AppHeader.vue`:

```vue
<script setup lang="ts">
import { useRouter } from 'vue-router'

const props = defineProps<{
  appId: number
  appName: string
  description?: string
}>()

const router = useRouter()
</script>

<template>
  <div class="mb-4">
    <div class="flex items-start justify-between gap-4">
      <div>
        <button
          @click="router.push('/applications')"
          class="text-xs text-subtext hover:text-text mb-2 inline-flex items-center gap-1 transition-colors"
        >
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" /></svg>
          Aplicaciones
        </button>
        <h1 class="text-2xl font-bold text-text">{{ appName }}</h1>
        <p v-if="description" class="text-xs text-subtext mt-1">{{ description }}</p>
      </div>
      <div class="flex gap-2 items-center">
        <slot name="actions" />
      </div>
    </div>

    <nav class="flex gap-1 border-b border-surface-0 mt-4" aria-label="Pestañas de configuración">
      <router-link
        data-test="app-tab"
        :to="`/applications/${appId}`"
        active-class="text-primary border-primary font-semibold"
        exact-active-class="text-primary border-primary font-semibold"
        class="px-4 py-2 text-[13px] border-b-2 border-transparent text-subtext hover:text-text transition-colors"
      >Resumen</router-link>
      <router-link
        data-test="app-tab"
        :to="`/applications/${appId}/pipeline`"
        active-class="text-primary border-primary font-semibold"
        class="px-4 py-2 text-[13px] border-b-2 border-transparent text-subtext hover:text-text transition-colors"
      >Pipeline</router-link>
      <router-link
        data-test="app-tab"
        :to="`/applications/${appId}/events`"
        active-class="text-primary border-primary font-semibold"
        class="px-4 py-2 text-[13px] border-b-2 border-transparent text-subtext hover:text-text transition-colors"
      >Eventos</router-link>
    </nav>
  </div>
</template>
```

- [ ] **Step 4: Verificar que los tests pasan**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run tests/components/AppHeader.test.ts
```

Expected: 2/2 PASS.

- [ ] **Step 5: Ejecutar la suite completa**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run
```

Expected: 83/83 PASS (81 + 2 nuevos).

- [ ] **Step 6: Commit**

```bash
git add web/frontend/src/components/AppHeader.vue web/frontend/tests/components/AppHeader.test.ts
git commit -m "feat(web-frontend): AppHeader con tabs Resumen/Pipeline/Eventos"
```

---

## Task 6: Integrar `<AppHeader>` en `ApplicationDetailView.vue`

**Files:**
- Modify: `web/frontend/src/views/applications/ApplicationDetailView.vue`

- [ ] **Step 1: Refactorizar la vista**

Abrir `web/frontend/src/views/applications/ApplicationDetailView.vue`. Reemplazar el `<template>` entero (y los imports/script si hace falta) por esta versión que usa `<AppHeader>` y elimina el botón "Editar pipeline" (ahora es tab):

```vue
<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useApplicationsStore } from '@/stores/applications'
import { useBatchesStore } from '@/stores/batches'
import AppHeader from '@/components/AppHeader.vue'

const route = useRoute()
const router = useRouter()
const appStore = useApplicationsStore()
const batchStore = useBatchesStore()

const appId = computed(() => Number(route.params.id))

onMounted(async () => {
  await appStore.fetchOne(appId.value)
  await batchStore.fetchAll(appId.value)
})

async function onDelete() {
  if (!confirm('¿Eliminar esta aplicación y todos sus lotes?')) return
  await appStore.remove(appId.value)
  router.push('/applications')
}

async function onCreateBatch() {
  const batch = await batchStore.create({ application_id: appId.value })
  router.push(`/batches/${batch.id}`)
}
</script>

<template>
  <div v-if="appStore.current">
    <AppHeader
      :app-id="appId"
      :app-name="appStore.current.name"
      :description="appStore.current.description || 'Sin descripción'"
    >
      <template #actions>
        <button
          @click="onCreateBatch"
          class="bg-primary text-white rounded-md px-4 py-2 text-[13px] font-semibold hover:bg-primary-hover transition-colors shadow-sm"
        >
          + Nuevo lote
        </button>
        <button
          @click="onDelete"
          class="text-danger border border-danger/40 bg-white rounded-md px-4 py-2 text-[13px] font-medium hover:bg-danger hover:text-white transition-colors"
        >
          Eliminar
        </button>
      </template>
    </AppHeader>

    <!-- Info -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
      <div class="bg-white rounded-lg border border-surface-0 p-4">
        <p class="text-[11px] text-subtext uppercase tracking-wide font-medium">Estado</p>
        <p class="text-sm font-semibold mt-1.5" :class="appStore.current.active ? 'text-success' : 'text-subtext'">
          {{ appStore.current.active ? 'Activa' : 'Inactiva' }}
        </p>
      </div>
      <div class="bg-white rounded-lg border border-surface-0 p-4">
        <p class="text-[11px] text-subtext uppercase tracking-wide font-medium">Formato salida</p>
        <p class="text-sm font-semibold text-text mt-1.5">{{ appStore.current.output_format || 'tiff' }}</p>
      </div>
      <div class="bg-white rounded-lg border border-surface-0 p-4">
        <p class="text-[11px] text-subtext uppercase tracking-wide font-medium">Auto-transferencia</p>
        <p class="text-sm font-semibold text-text mt-1.5">{{ appStore.current.auto_transfer ? 'Sí' : 'No' }}</p>
      </div>
      <div class="bg-white rounded-lg border border-surface-0 p-4">
        <p class="text-[11px] text-subtext uppercase tracking-wide font-medium">Lotes</p>
        <p class="text-sm font-semibold text-text mt-1.5">{{ batchStore.items.length }}</p>
      </div>
    </div>

    <!-- Lotes de esta aplicación -->
    <div class="bg-white rounded-lg border border-surface-0 overflow-hidden">
      <div class="px-5 py-3 border-b border-surface-0 bg-mantle">
        <h2 class="text-[13px] font-semibold text-text uppercase tracking-wide">Lotes</h2>
      </div>
      <div v-if="batchStore.items.length === 0" class="px-5 py-10 text-sm text-subtext text-center">
        Sin lotes. Crea uno para empezar a subir documentos.
      </div>
      <div v-else>
        <router-link
          v-for="batch in batchStore.items"
          :key="batch.id"
          :to="`/batches/${batch.id}`"
          class="flex items-center justify-between px-5 py-3 border-b border-surface-0 last:border-b-0 hover:bg-mantle transition-colors"
        >
          <div>
            <p class="text-[13px] font-medium text-text">Lote #{{ batch.id }}</p>
            <p class="text-xs text-subtext">{{ batch.page_count }} páginas — {{ new Date(batch.created_at).toLocaleDateString('es-ES') }}</p>
          </div>
          <span
            class="text-[11px] px-2 py-0.5 rounded-full font-medium border"
            :class="{
              'bg-warning-soft text-warning border-warning/30': batch.state === 'created',
              'bg-primary-soft text-primary border-primary/30': batch.state === 'read',
              'bg-danger-soft text-danger border-danger/30': batch.state.startsWith('error'),
            }"
          >
            {{ batch.state }}
          </span>
        </router-link>
      </div>
    </div>
  </div>
  <div v-else class="text-sm text-subtext">Cargando...</div>
</template>
```

Cambios: se importa `AppHeader`, se elimina la cabecera anterior con el botón "Editar pipeline" (ahora es tab), se delegan "+ Nuevo lote" y "Eliminar" al slot `actions`.

- [ ] **Step 2: Verificar que la suite sigue verde**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run
```

Expected: 83/83 PASS.

- [ ] **Step 3: Commit**

```bash
git add web/frontend/src/views/applications/ApplicationDetailView.vue
git commit -m "feat(web-frontend): ApplicationDetailView usa AppHeader con tabs"
```

---

## Task 7: Integrar `<AppHeader>` en `PipelineEditorView.vue`

**Files:**
- Modify: `web/frontend/src/views/applications/PipelineEditorView.vue`

- [ ] **Step 1: Inspeccionar la cabecera actual de PipelineEditorView**

```bash
grep -n "h1\|router\.push\|appStore\.current\.name\|appStore.current" web/frontend/src/views/applications/PipelineEditorView.vue | head -20
```

Localizar el bloque del template que contiene la cabecera (típicamente antes del editor del pipeline): un `<div>` con un `<h1>` y un back link. El resto (lista de steps, drawer, save pipeline) no se toca.

- [ ] **Step 2: Reemplazar la cabecera por `<AppHeader>`**

Abrir `web/frontend/src/views/applications/PipelineEditorView.vue`. Añadir el import:

```ts
import AppHeader from '@/components/AppHeader.vue'
```

En el template, sustituir el bloque de cabecera existente (h1 + back + botones del header si los hay) por:

```vue
<AppHeader
  v-if="appStore.current"
  :app-id="appId"
  :app-name="appStore.current.name"
  :description="appStore.current.description || undefined"
>
  <template #actions>
    <!-- Botones específicos del pipeline (Guardar pipeline, etc.); si no los había, el slot queda vacío -->
  </template>
</AppHeader>
```

Si el componente tiene botones específicos (p. ej. "Guardar pipeline"), se mueven al slot `actions`. El resto del template (lista de steps, drawer) permanece debajo.

**Criterio**: el usuario debe poder navegar de Pipeline a Resumen o Eventos vía tabs visibles en esta vista, y la cabecera (back link, título) ya no se duplica.

- [ ] **Step 3: Verificar que la suite sigue verde**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run
```

Expected: 83/83 PASS (posible regresión solo si había algún test sobre el DOM del header de PipelineEditorView — si falla, ajustar el test al nuevo header).

- [ ] **Step 4: Commit**

```bash
git add web/frontend/src/views/applications/PipelineEditorView.vue
git commit -m "feat(web-frontend): PipelineEditorView usa AppHeader con tabs"
```

---

## Task 8: Ruta `/applications/:id/events` + vista `EventsEditorView.vue`

**Files:**
- Create: `web/frontend/src/views/applications/EventsEditorView.vue`
- Create: `web/frontend/tests/views/EventsEditorView.test.ts`
- Modify: `web/frontend/src/router/index.ts`

- [ ] **Step 1: Escribir los tests de la vista**

Crear `web/frontend/tests/views/EventsEditorView.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createTestingPinia } from '@pinia/testing'
import EventsEditorView from '@/views/applications/EventsEditorView.vue'
import { useApplicationsStore } from '@/stores/applications'
import { EVENT_DEFINITIONS } from '@/api/events-catalog'

let latestUpdateModelValue: ((doc: string) => void) | null = null

vi.mock('@/components/CodeEditor.vue', () => ({
  default: {
    name: 'CodeEditor',
    props: ['modelValue', 'contextVariables', 'snippets', 'minHeight', 'helpPanelStorageKey', 'disabled'],
    emits: ['update:modelValue'],
    setup(_: unknown, ctx: { emit: (name: string, ...args: unknown[]) => void }) {
      latestUpdateModelValue = (doc: string) => ctx.emit('update:modelValue', doc)
      return {}
    },
    template: '<div data-test="stub-code-editor">{{ modelValue }}</div>',
  },
}))

vi.mock('@/components/AppHeader.vue', () => ({
  default: {
    name: 'AppHeader',
    props: ['appId', 'appName', 'description'],
    template: '<div data-test="stub-header"><slot name="actions" /></div>',
  },
}))

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/applications/:id/events', name: 'events', component: { template: '<div/>' } },
      { path: '/applications/:id', component: { template: '<div/>' } },
      { path: '/applications', component: { template: '<div/>' } },
    ],
  })
}

function mountView(eventsJson: string = '{}') {
  const router = makeRouter()
  router.push('/applications/8/events')

  const wrapper = mount(EventsEditorView, {
    global: {
      plugins: [
        router,
        createTestingPinia({ stubActions: false, createSpy: vi.fn }),
      ],
    },
  })

  const store = useApplicationsStore()
  store.current = {
    id: 8, name: 'Demo', description: '', active: true,
    pipeline_json: '[]', events_json: eventsJson, transfer_json: '{}',
    batch_fields_json: '[]', index_fields_json: '[]',
    auto_transfer: false, close_after_transfer: false,
    background_color: '', output_format: 'tiff', default_tab: 'lote',
    scanner_backend: '', image_config_json: '{}', ai_config_json: '{}',
    tenant_id: 1, created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
  }
  ;(store.fetchOne as unknown as { mockResolvedValue: (v: unknown) => void }).mockResolvedValue(undefined)
  return { wrapper, store, router }
}

describe('EventsEditorView', () => {
  beforeEach(() => {
    latestUpdateModelValue = null
    localStorage.clear()
  })

  it('fetch inicial carga events_json y selecciona on_app_start por defecto', async () => {
    const { wrapper, store } = mountView(JSON.stringify({
      on_app_end: 'log.info("bye")\n',
    }))
    await flushPromises()
    expect(store.fetchOne).toHaveBeenCalledWith(8)

    const items = wrapper.findAll('[data-test="event-item"]')
    expect(items).toHaveLength(13)
    expect(items[0].classes().join(' ')).toContain('text-primary')
    expect(items[0].text()).toContain('on_app_start')
  })

  it('sidebar marca con indicador los eventos con código', async () => {
    const { wrapper } = mountView(JSON.stringify({
      on_app_end: 'log.info("bye")\n',
      on_scan_complete: 'pass',
    }))
    await flushPromises()
    const active = wrapper.findAll('[data-test="event-indicator-active"]')
    const activeNames = active.map((a) => a.attributes('data-event'))
    expect(activeNames).toEqual(expect.arrayContaining(['on_app_end', 'on_scan_complete']))
  })

  it('click en otro evento cambia el modelValue pasado al CodeEditor', async () => {
    const { wrapper } = mountView(JSON.stringify({
      on_app_end: 'log.info("bye")\n',
    }))
    await flushPromises()

    const items = wrapper.findAll('[data-test="event-item"]')
    const onAppEnd = items.find((it) => it.text().includes('on_app_end'))!
    await onAppEnd.trigger('click')
    await wrapper.vm.$nextTick()

    const editor = wrapper.find('[data-test="stub-code-editor"]')
    expect(editor.text()).toContain('log.info("bye")')
  })

  it('seleccionar evento sin código muestra su template sin ensuciar hasChanges', async () => {
    const { wrapper } = mountView('{}')
    await flushPromises()

    const editor = wrapper.find('[data-test="stub-code-editor"]')
    expect(editor.text()).toContain('def on_app_start(app, batch):')

    const saveBtn = wrapper.find('[data-test="save-events"]')
    expect(saveBtn.attributes('disabled')).toBeDefined()
  })

  it('editar en el editor actualiza el estado y habilita Guardar', async () => {
    const { wrapper } = mountView('{}')
    await flushPromises()

    expect(latestUpdateModelValue).toBeTypeOf('function')
    latestUpdateModelValue!('log.info("hola")\n')
    await wrapper.vm.$nextTick()

    const saveBtn = wrapper.find('[data-test="save-events"]')
    expect(saveBtn.attributes('disabled')).toBeUndefined()
  })

  it('Guardar cambios llama a store.update con events_json stringified y resetea hasChanges', async () => {
    const { wrapper, store } = mountView('{}')
    await flushPromises()

    latestUpdateModelValue!('log.info("hola")\n')
    await wrapper.vm.$nextTick()

    ;(store.update as unknown as { mockResolvedValue: (v: unknown) => void }).mockResolvedValue(undefined)

    await wrapper.find('[data-test="save-events"]').trigger('click')
    await flushPromises()

    expect(store.update).toHaveBeenCalledWith(8, expect.objectContaining({
      events_json: expect.stringContaining('on_app_start'),
    }))

    const parsed = JSON.parse((store.update as unknown as { mock: { calls: unknown[][] } }).mock.calls[0][1] as string)
    // El JSON persistido debe tener on_app_start con el código editado (no el template).
    // Nota: el estado local se persiste tal cual; si coincide con template no se guardaría, pero el test escribe algo distinto.
    expect(wrapper.find('[data-test="save-events"]').attributes('disabled')).toBeDefined()
  })

  it('Deshacer restaura events al snapshot original', async () => {
    const { wrapper } = mountView(JSON.stringify({
      on_app_end: 'log.info("bye")\n',
    }))
    await flushPromises()

    latestUpdateModelValue!('log.info("modificado")\n')
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-test="save-events"]').attributes('disabled')).toBeUndefined()

    await wrapper.find('[data-test="undo-events"]').trigger('click')
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-test="save-events"]').attributes('disabled')).toBeDefined()
  })

  it('renderiza los 13 eventos en la sidebar', async () => {
    const { wrapper } = mountView('{}')
    await flushPromises()
    const items = wrapper.findAll('[data-test="event-item"]')
    expect(items).toHaveLength(13)
    expect(items[items.length - 1].text()).toContain('verification_panel')
    expect(items.map((i) => i.text()).join('\n')).toContain(EVENT_DEFINITIONS[0].name)
  })
})
```

- [ ] **Step 2: Verificar que los tests fallan**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run tests/views/EventsEditorView.test.ts
```

Expected: FAIL con "Cannot find module '@/views/applications/EventsEditorView.vue'".

- [ ] **Step 3: Crear la vista**

Crear `web/frontend/src/views/applications/EventsEditorView.vue`:

```vue
<script setup lang="ts">
import { computed, onMounted, ref, onBeforeUnmount } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router'
import { useApplicationsStore } from '@/stores/applications'
import { EVENT_DEFINITIONS } from '@/api/events-catalog'
import AppHeader from '@/components/AppHeader.vue'
import CodeEditor from '@/components/CodeEditor.vue'

const route = useRoute()
const router = useRouter()
const appStore = useApplicationsStore()

const appId = computed(() => Number(route.params.id))

const originalEvents = ref<Record<string, string>>({})
const events = ref<Record<string, string>>({})
const currentEventName = ref<string>(EVENT_DEFINITIONS[0].name)
const saving = ref(false)
const saveError = ref<string | null>(null)

const currentEvent = computed(() =>
  EVENT_DEFINITIONS.find((e) => e.name === currentEventName.value)!,
)

const currentEditorValue = computed(() => {
  const stored = events.value[currentEventName.value]
  return stored !== undefined ? stored : currentEvent.value.template
})

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

function parseEventsJson(raw: string): Record<string, string> {
  try {
    const parsed = JSON.parse(raw || '{}')
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return parsed as Record<string, string>
    }
    return {}
  } catch (err) {
    console.warn('[EventsEditorView] events_json inválido, usando {}', err)
    return {}
  }
}

function onEditorChange(doc: string): void {
  // Si el doc coincide exactamente con el template y no había código previamente,
  // no persistir (mantiene el evento como "sin código").
  if (doc === currentEvent.value.template && originalEvents.value[currentEventName.value] === undefined) {
    if (events.value[currentEventName.value] !== undefined) {
      const next = { ...events.value }
      delete next[currentEventName.value]
      events.value = next
    }
    return
  }
  // Si el código está vacío tras trim, eliminar la clave (match desktop).
  if (doc.trim() === '') {
    if (events.value[currentEventName.value] !== undefined) {
      const next = { ...events.value }
      delete next[currentEventName.value]
      events.value = next
    }
    return
  }
  events.value = { ...events.value, [currentEventName.value]: doc }
}

function selectEvent(name: string): void {
  currentEventName.value = name
}

function hasCode(name: string): boolean {
  return (events.value[name] ?? '').trim().length > 0
}

async function onSave(): Promise<void> {
  saving.value = true
  saveError.value = null
  try {
    await appStore.update(appId.value, {
      events_json: JSON.stringify(events.value),
    })
    originalEvents.value = { ...events.value }
  } catch (err) {
    saveError.value = (err as Error).message
  } finally {
    saving.value = false
  }
}

function onUndo(): void {
  events.value = { ...originalEvents.value }
}

function onBeforeUnload(ev: BeforeUnloadEvent): void {
  if (hasChanges.value) {
    ev.preventDefault()
    ev.returnValue = ''
  }
}

onMounted(async () => {
  await appStore.fetchOne(appId.value)
  const parsed = parseEventsJson(appStore.current?.events_json ?? '{}')
  originalEvents.value = parsed
  events.value = { ...parsed }
  window.addEventListener('beforeunload', onBeforeUnload)
})

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', onBeforeUnload)
})

onBeforeRouteLeave((_to, _from, next) => {
  if (!hasChanges.value) return next()
  if (confirm('Hay cambios sin guardar. ¿Salir igualmente?')) return next()
  next(false)
})
</script>

<template>
  <div v-if="appStore.current">
    <AppHeader
      :app-id="appId"
      :app-name="appStore.current.name"
      :description="appStore.current.description || undefined"
    >
      <template #actions>
        <span v-if="hasChanges" class="text-xs text-warning">● sin guardar</span>
        <button
          type="button"
          data-test="undo-events"
          :disabled="!hasChanges"
          @click="onUndo"
          class="text-[13px] text-subtext hover:text-text border border-surface-0 rounded px-3 py-2 disabled:opacity-50"
        >
          Deshacer
        </button>
        <button
          type="button"
          data-test="save-events"
          :disabled="!hasChanges || saving"
          @click="onSave"
          class="text-[13px] bg-primary text-white rounded-md px-4 py-2 font-semibold hover:bg-primary-hover disabled:opacity-50"
        >
          {{ saving ? 'Guardando...' : 'Guardar cambios' }}
        </button>
      </template>
    </AppHeader>

    <div v-if="saveError" class="mb-4 p-3 bg-red-50 border border-red-200 rounded text-sm text-danger">
      {{ saveError }}
    </div>

    <div class="flex gap-4">
      <!-- Sidebar -->
      <aside class="w-64 flex-shrink-0 bg-white rounded-md border border-surface-0 overflow-y-auto" style="max-height: 560px;">
        <div class="px-3 py-2 border-b border-surface-0 text-xs font-medium uppercase tracking-wide text-subtext">
          Eventos
        </div>
        <ul>
          <li
            v-for="ev in EVENT_DEFINITIONS"
            :key="ev.name"
            data-test="event-item"
            @click="selectEvent(ev.name)"
            :class="[
              'cursor-pointer px-3 py-2 border-b border-surface-0 last:border-b-0',
              currentEventName === ev.name ? 'bg-primary-soft text-primary font-semibold' : 'text-text hover:bg-surface-0',
            ]"
          >
            <div class="flex items-center gap-2">
              <span
                v-if="hasCode(ev.name)"
                data-test="event-indicator-active"
                :data-event="ev.name"
                class="w-2 h-2 rounded-full bg-success"
              ></span>
              <span v-else class="w-2 h-2 rounded-full bg-surface-0"></span>
              <span class="font-mono text-[13px]">{{ ev.name }}</span>
            </div>
            <div class="text-xs text-subtext mt-0.5 ml-4">{{ ev.description }}</div>
          </li>
        </ul>
      </aside>

      <!-- Editor -->
      <div class="flex-1 min-w-0">
        <CodeEditor
          :key="currentEventName"
          :model-value="currentEditorValue"
          :context-variables="currentEvent.contextVariables"
          help-panel-storage-key="eventsEditor.helpPanelOpen"
          :min-height="460"
          @update:model-value="onEditorChange"
        />
        <p class="text-xs text-subtext mt-2">
          <span class="font-semibold">Firma:</span>
          <code class="font-mono">{{ currentEvent.signature }}</code>
          — {{ currentEvent.description }}
        </p>
      </div>
    </div>
  </div>
  <div v-else class="text-sm text-subtext">Cargando...</div>
</template>
```

- [ ] **Step 4: Añadir la ruta**

Abrir `web/frontend/src/router/index.ts`. Localizar el bloque de rutas (array). Añadir antes del catch-all (si lo hay), junto a la ruta de `pipeline`:

```ts
{
  path: '/applications/:id/events',
  name: 'events',
  component: () => import('@/views/applications/EventsEditorView.vue'),
  meta: { requiresAuth: true },
},
```

- [ ] **Step 5: Verificar que los tests pasan**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run tests/views/EventsEditorView.test.ts
```

Expected: 8/8 PASS.

- [ ] **Step 6: Ejecutar la suite completa**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run
```

Expected: 91/91 PASS (83 + 8 nuevos).

- [ ] **Step 7: Verificar build**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run build 2>&1 | tail -15
```

Expected: build OK; chunk `editor-*.js` sigue aislado; nuevos chunks para EventsEditorView.

- [ ] **Step 8: Commit**

```bash
git add web/frontend/src/views/applications/EventsEditorView.vue \
        web/frontend/src/router/index.ts \
        web/frontend/tests/views/EventsEditorView.test.ts
git commit -m "feat(web-frontend): pestaña Eventos con sidebar + CodeEditor"
```

---

## Task 9: QA manual + push

**Sin commits hasta el push.**

- [ ] **Step 1: Arrancar el entorno local**

```bash
# Terminal 1
docker start docscan-pg

# Terminal 2
cd /media/nicolas/DATA/Tecnomedia/FlexiPy && source .venv/bin/activate
uvicorn web.api.main:create_app --factory --reload --port 8001

# Terminal 3
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run dev
```

- [ ] **Step 2: Login y navegación por tabs**

Abrir `http://localhost:5173`, login `demo2@demo.com / demo12345`, entrar en la aplicación id 8. Verificar:
- La cabecera muestra "Resumen | Pipeline | Eventos" como tabs.
- "Resumen" activo por defecto.
- Click en "Pipeline" → carga el editor de pipeline v4 sin regresiones.
- Click en "Eventos" → carga la nueva pestaña.

- [ ] **Step 3: Editar un evento sencillo**

En la pestaña Eventos:
- Seleccionar `on_app_start` en la sidebar.
- Ver plantilla `def on_app_start(app, batch): ...` pre-cargada.
- Escribir `log.info("hola")` dentro del cuerpo.
- El botón "Guardar cambios" se habilita y aparece "● sin guardar".
- Pulsar "Guardar cambios" → el indicador desaparece, el botón se deshabilita.

- [ ] **Step 4: Verificar persistencia**

- Recargar F5. Seleccionar `on_app_start`. Comprobar que el código editado persiste.
- En el sidebar, `on_app_start` tiene el dot verde.

- [ ] **Step 5: Autocompletado contextual**

- Seleccionar `on_key_event`. Escribir `ke` en el cuerpo. Comprobar que el autocompletado sugiere `key`.
- Seleccionar `on_transfer_page`. Escribir `pa` y comprobar que sugiere `page`.
- Seleccionar `verification_panel`. Verificar plantilla de clase. Escribir `self.api.` en el cuerpo del método `setup_ui` y comprobar que el autocompletado sugiere los métodos de `self.api`.

- [ ] **Step 6: Deshacer y navegación con cambios**

- Editar cualquier evento. Pulsar "Deshacer" → código vuelve al estado guardado, botón Guardar deshabilitado.
- Editar de nuevo. Intentar navegar a "Pipeline" o usar `window.location` → aparece `confirm` de abandono.

- [ ] **Step 7: Paridad con desktop**

- Abrir desktop (`python3.14 main.py`), abrir la aplicación id 8, pestaña Eventos. Verificar que el código editado desde web aparece en el diálogo desktop con el mismo contenido.

- [ ] **Step 8: Pipeline sigue sin regresiones**

- Volver a la pestaña Pipeline (web). Abrir un ScriptStep → editor CodeMirror sigue funcionando (autocompletado, snippets, panel de ayuda).
- Crear nuevo ScriptStep → plantilla `def process(...)` aparece. Escribir código. Guardar pipeline. Recargar F5. Verificar.

- [ ] **Step 9: Push al remote**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy && git push origin feature/web
```

Expected: push OK, rama `feature/web` actualizada con todos los commits del sub-proyecto.

- [ ] **Step 10: Cerrar entorno local**

- Ctrl+C en uvicorn y npm dev.
- `docker stop docscan-pg`.

---

## Cierre

- **~91 tests frontend pasando** (73 previos + 18 nuevos: 1 wrapper + 6 CodeEditor + 3 catálogo + 8 view + 2 AppHeader, menos 2 del ScriptStepForm que se movieron a CodeEditor.test.ts).
- **Cero cambios backend.**
- **Chunk CodeMirror** sigue aislado (~131 KB gzipped).
- Sub-navegación por tabs funcional en las 3 vistas de configuración.
- `<CodeEditor>` reutilizable — base para futuras pestañas que necesiten editor de código.

**Próximo paso:** actualizar `memory/project_web_session_next.md` marcando Eventos como completado y proponiendo el siguiente sub-proyecto (Imagen, Campos de lote, Transferencia o General).
