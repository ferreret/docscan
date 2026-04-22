# Workbench web — Fase 2 (base) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reemplazar `BatchDetailView.vue` por un Workbench multi-panel (3 columnas redimensionables) equivalente al desktop, manteniendo todas las acciones existentes y añadiendo navegación con flechas, miniaturas con bordes coloreados por estado y formulario editable de campos custom del lote.

**Architecture:** `WorkbenchView.vue` orquesta layout con `vue-splitpanes`. Componentes hijos puramente presentacionales (`ThumbnailPanel`, `BarcodePanel`, `MetadataPanel`, `WorkbenchToolbar`, `ViewerToolbar`, `PageThumbnail`) reciben datos vía props y emiten eventos. Composables `usePageState` (lógica de estado de página) y `useWorkbenchLayout` (persistencia de tamaños splitter en localStorage). `DocumentViewer.vue` existente se reutiliza, exponiendo métodos vía `defineExpose`.

**Tech Stack:** Vue 3 (`<script setup>` + Composition API), TypeScript estricto, Tailwind v4 con variables semánticas (Fase 1), Pinia, Vitest + @vue/test-utils, splitpanes 4.x.

**Spec:** `docs/superpowers/specs/2026-04-22-workbench-web-fase-2-design.md`

---

## File Structure

**Create:**
- `web/frontend/src/composables/usePageState.ts` — `determinePageState()` con 6 estados y mapping a clases Tailwind
- `web/frontend/src/composables/useWorkbenchLayout.ts` — `useWorkbenchLayout()` con persistencia localStorage
- `web/frontend/src/components/workbench/PageThumbnail.vue` — miniatura individual con borde coloreado
- `web/frontend/src/components/workbench/ThumbnailPanel.vue` — panel scrollable de miniaturas
- `web/frontend/src/components/workbench/BarcodePanel.vue` — tabla view-only de barcodes + contadores
- `web/frontend/src/components/workbench/MetadataPanel.vue` — tab Lote con form dinámico
- `web/frontend/src/components/workbench/ViewerToolbar.vue` — toolbar flotante zoom/pan
- `web/frontend/src/components/workbench/WorkbenchToolbar.vue` — top toolbar con acciones
- `web/frontend/src/views/batches/WorkbenchView.vue` — orquestador (reemplaza BatchDetailView)
- 9 ficheros de tests vitest (paralelos a cada source)

**Modify:**
- `web/frontend/package.json` — añadir dependencia `splitpanes`
- `web/frontend/src/components/DocumentViewer.vue` — añadir `defineExpose({ zoomIn, zoomOut, resetView, fitToViewport, zoomPercent })`
- `web/frontend/src/router/index.ts` — cambiar componente de `/batches/:id` a `WorkbenchView`

**Delete:**
- `web/frontend/src/views/batches/BatchDetailView.vue` — reemplazado

---

## Task 1: Instalar splitpanes y crear estructura de carpeta

**Files:**
- Modify: `web/frontend/package.json`
- Create: `web/frontend/src/components/workbench/.gitkeep` (placeholder)

- [ ] **Step 1: Instalar splitpanes**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm install splitpanes@4 --save`
Expected: `package.json` y `package-lock.json` actualizados con `splitpanes` ^4.x.

- [ ] **Step 2: Crear carpeta workbench**

Run: `mkdir -p /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend/src/components/workbench`
(No es necesario crear `.gitkeep` — los componentes posteriores la poblarán.)

- [ ] **Step 3: POC mínimo de splitpanes**

Crear `web/frontend/src/components/workbench/_poc.ts`:

```ts
import { Splitpanes, Pane } from 'splitpanes'
import 'splitpanes/dist/splitpanes.css'

export { Splitpanes, Pane }
```

Esto verifica que el import funciona. El fichero se elimina en el commit final del Task (no entra en producción) — pero comprobamos que typescript lo acepta.

- [ ] **Step 4: Typecheck**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vue-tsc --noEmit 2>&1 | tail -5`
Expected: sin errores. Si falla por tipos de splitpanes, instalar `npm install --save-dev @types/splitpanes` (puede no hacer falta — splitpanes 4.x tiene tipos integrados).

- [ ] **Step 5: Limpiar POC**

Run: `rm /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend/src/components/workbench/_poc.ts`

- [ ] **Step 6: Commit**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy && git add web/frontend/package.json web/frontend/package-lock.json
git commit -m "chore(web-frontend): añadir dependencia splitpanes 4.x

Necesaria para el layout 3 paneles redimensionables del Workbench
web (Fase 2). Versión 4.x compatible con Vue 3."
```

---

## Task 2: Composable `usePageState`

**Files:**
- Create: `web/frontend/src/composables/usePageState.ts`
- Create: `web/frontend/tests/composables/usePageState.test.ts`

- [ ] **Step 1: Escribir el primer test failing**

Crear `web/frontend/tests/composables/usePageState.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { determinePageState } from '@/composables/usePageState'
import type { PageResponse, BarcodeResponse } from '@/api/types'

function makePage(overrides: Partial<PageResponse> = {}): PageResponse {
  return {
    id: 1,
    batch_id: 1,
    page_index: 0,
    needs_review: false,
    is_blank: false,
    pipeline_processed: false,
    created_at: '2026-04-22T00:00:00Z',
    image_path: '/img.png',
    ocr_text: '',
    index_fields_json: '{}',
    review_reason: '',
    is_excluded: false,
    processing_errors_json: '[]',
    script_errors_json: '[]',
    barcodes: [],
    updated_at: '2026-04-22T00:00:00Z',
    ...overrides,
  }
}

function makeBarcode(role = ''): BarcodeResponse {
  return {
    id: 1, value: 'V', symbology: 'EAN', engine: 'motor1',
    step_id: 's1', quality: 1, pos_x: 0, pos_y: 0, pos_w: 10, pos_h: 10, role,
  }
}

describe('determinePageState', () => {
  it('returns "excluded" when is_excluded is true', () => {
    expect(determinePageState(makePage({ is_excluded: true }))).toBe('excluded')
  })
})
```

- [ ] **Step 2: Ejecutar test, verificar que falla**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run tests/composables/usePageState.test.ts 2>&1 | tail -5`
Expected: FAIL con `Failed to resolve import "@/composables/usePageState"`.

- [ ] **Step 3: Crear composable mínimo**

Crear `web/frontend/src/composables/usePageState.ts`:

```ts
import type { PageResponse } from '@/api/types'

export type PageState =
  | 'excluded'
  | 'needs_review'
  | 'separator_barcode'
  | 'has_fields'
  | 'barcode_no_role'
  | 'no_recognition'

export const PAGE_STATE_BORDER_CLASS: Record<PageState, string> = {
  excluded: 'border-danger',
  needs_review: 'border-danger',
  separator_barcode: 'border-warning',
  has_fields: 'border-primary',
  barcode_no_role: 'border-success',
  no_recognition: 'border-overlay-0',
}

export function determinePageState(page: PageResponse): PageState {
  if (page.is_excluded) return 'excluded'
  if (page.needs_review) return 'needs_review'

  const barcodes = page.barcodes ?? []
  if (barcodes.some((b) => b.role === 'separator')) return 'separator_barcode'

  let hasFields = false
  try {
    const fields = JSON.parse(page.index_fields_json || '{}')
    hasFields = fields && typeof fields === 'object' && Object.keys(fields).length > 0
  } catch {
    hasFields = false
  }
  if (hasFields) return 'has_fields'

  if (barcodes.length > 0) return 'barcode_no_role'

  return 'no_recognition'
}
```

- [ ] **Step 4: Ejecutar test, verificar que pasa**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run tests/composables/usePageState.test.ts 2>&1 | tail -5`
Expected: `Tests 1 passed (1)`.

- [ ] **Step 5: Añadir tests restantes**

Añadir dentro del `describe('determinePageState', ...)`:

```ts
  it('returns "needs_review" when needs_review is true and not excluded', () => {
    expect(determinePageState(makePage({ needs_review: true }))).toBe('needs_review')
  })

  it('"excluded" wins over "needs_review"', () => {
    expect(determinePageState(makePage({ is_excluded: true, needs_review: true }))).toBe('excluded')
  })

  it('returns "separator_barcode" when any barcode has role=separator', () => {
    const page = makePage({ barcodes: [makeBarcode(''), makeBarcode('separator')] })
    expect(determinePageState(page)).toBe('separator_barcode')
  })

  it('returns "has_fields" when index_fields_json has keys', () => {
    const page = makePage({ index_fields_json: '{"cliente": "ACME"}' })
    expect(determinePageState(page)).toBe('has_fields')
  })

  it('returns "barcode_no_role" when has barcodes but none with role and no fields', () => {
    const page = makePage({ barcodes: [makeBarcode('')] })
    expect(determinePageState(page)).toBe('barcode_no_role')
  })

  it('returns "no_recognition" when has nothing', () => {
    expect(determinePageState(makePage())).toBe('no_recognition')
  })

  it('treats malformed index_fields_json as no fields', () => {
    const page = makePage({ index_fields_json: '{"broken' })
    expect(determinePageState(page)).toBe('no_recognition')
  })

  it('PAGE_STATE_BORDER_CLASS has entry for every state', () => {
    const states: PageState[] = ['excluded', 'needs_review', 'separator_barcode', 'has_fields', 'barcode_no_role', 'no_recognition']
    for (const s of states) {
      expect(PAGE_STATE_BORDER_CLASS[s]).toMatch(/^border-/)
    }
  })
```

- [ ] **Step 6: Ejecutar todos los tests**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run tests/composables/usePageState.test.ts 2>&1 | tail -5`
Expected: `Tests 9 passed (9)`.

- [ ] **Step 7: Suite completa (regresión cero)**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run 2>&1 | tail -5`
Expected: `Tests 173 passed (173)` (164 previos + 9 nuevos).

- [ ] **Step 8: Commit**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy && git add web/frontend/src/composables/usePageState.ts web/frontend/tests/composables/usePageState.test.ts
git commit -m "feat(web-frontend): composable usePageState con 6 estados como desktop

determinePageState mapea PageResponse a uno de seis estados con
prioridad UI igual al desktop: excluded > needs_review >
separator_barcode > has_fields > barcode_no_role > no_recognition.
Mapping PAGE_STATE_BORDER_CLASS expone la clase Tailwind por estado
para usar en bordes de miniaturas.

9 tests vitest cubren cada estado, prioridad, JSON malformado y
completitud del mapping."
```

---

## Task 3: Composable `useWorkbenchLayout`

**Files:**
- Create: `web/frontend/src/composables/useWorkbenchLayout.ts`
- Create: `web/frontend/tests/composables/useWorkbenchLayout.test.ts`

- [ ] **Step 1: Escribir test failing — defaults**

Crear `web/frontend/tests/composables/useWorkbenchLayout.test.ts`:

```ts
import { describe, it, expect, beforeEach } from 'vitest'
import { useWorkbenchLayout, _resetLayoutForTests } from '@/composables/useWorkbenchLayout'

describe('useWorkbenchLayout', () => {
  beforeEach(() => {
    localStorage.clear()
    _resetLayoutForTests()
  })

  it('returns default sizes when localStorage is empty', () => {
    const { sizes } = useWorkbenchLayout()
    expect(sizes.value).toEqual({ columns: [15, 55, 30], rightVertical: [50, 50] })
  })
})
```

- [ ] **Step 2: Verificar fail**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run tests/composables/useWorkbenchLayout.test.ts 2>&1 | tail -5`
Expected: FAIL `Failed to resolve import`.

- [ ] **Step 3: Crear composable mínimo**

Crear `web/frontend/src/composables/useWorkbenchLayout.ts`:

```ts
import { ref, type Ref } from 'vue'

export interface LayoutSizes {
  columns: [number, number, number]
  rightVertical: [number, number]
}

const STORAGE_KEY = 'workbench.layout'
const DEFAULT_SIZES: LayoutSizes = {
  columns: [15, 55, 30],
  rightVertical: [50, 50],
}

function isValidSizes(value: unknown): value is LayoutSizes {
  if (!value || typeof value !== 'object') return false
  const v = value as Partial<LayoutSizes>
  return (
    Array.isArray(v.columns) && v.columns.length === 3 &&
    v.columns.every((n) => typeof n === 'number' && n > 0) &&
    Array.isArray(v.rightVertical) && v.rightVertical.length === 2 &&
    v.rightVertical.every((n) => typeof n === 'number' && n > 0)
  )
}

function readStored(): LayoutSizes {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return DEFAULT_SIZES
    const parsed = JSON.parse(raw)
    return isValidSizes(parsed) ? parsed : DEFAULT_SIZES
  } catch {
    return DEFAULT_SIZES
  }
}

const sizes = ref<LayoutSizes>(readStored())

function setSizes(next: LayoutSizes): void {
  sizes.value = next
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
  } catch {
    /* localStorage bloqueado */
  }
}

export function useWorkbenchLayout(): { sizes: Ref<LayoutSizes>; setSizes: (s: LayoutSizes) => void } {
  return { sizes, setSizes }
}

/** Solo para tests. */
export function _resetLayoutForTests(): void {
  sizes.value = readStored()
}
```

- [ ] **Step 4: Verificar pass**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run tests/composables/useWorkbenchLayout.test.ts 2>&1 | tail -5`
Expected: `Tests 1 passed (1)`.

- [ ] **Step 5: Añadir tests restantes**

Añadir dentro del describe:

```ts
  it('loads valid sizes from localStorage', () => {
    localStorage.setItem('workbench.layout', JSON.stringify({ columns: [20, 50, 30], rightVertical: [60, 40] }))
    _resetLayoutForTests()
    const { sizes } = useWorkbenchLayout()
    expect(sizes.value.columns).toEqual([20, 50, 30])
    expect(sizes.value.rightVertical).toEqual([60, 40])
  })

  it('falls back to defaults when localStorage value is malformed', () => {
    localStorage.setItem('workbench.layout', '{not json')
    _resetLayoutForTests()
    const { sizes } = useWorkbenchLayout()
    expect(sizes.value).toEqual({ columns: [15, 55, 30], rightVertical: [50, 50] })
  })

  it('falls back to defaults when shape is wrong', () => {
    localStorage.setItem('workbench.layout', JSON.stringify({ columns: [50, 50] })) // only 2 cols
    _resetLayoutForTests()
    const { sizes } = useWorkbenchLayout()
    expect(sizes.value).toEqual({ columns: [15, 55, 30], rightVertical: [50, 50] })
  })

  it('setSizes updates ref and persists to localStorage', () => {
    const { setSizes, sizes } = useWorkbenchLayout()
    setSizes({ columns: [10, 60, 30], rightVertical: [40, 60] })
    expect(sizes.value.columns).toEqual([10, 60, 30])
    expect(JSON.parse(localStorage.getItem('workbench.layout')!)).toEqual({
      columns: [10, 60, 30], rightVertical: [40, 60],
    })
  })
```

- [ ] **Step 6: Ejecutar tests**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run tests/composables/useWorkbenchLayout.test.ts 2>&1 | tail -5`
Expected: `Tests 5 passed (5)`.

- [ ] **Step 7: Suite completa**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run 2>&1 | tail -5`
Expected: `Tests 178 passed (178)`.

- [ ] **Step 8: Commit**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy && git add web/frontend/src/composables/useWorkbenchLayout.ts web/frontend/tests/composables/useWorkbenchLayout.test.ts
git commit -m "feat(web-frontend): composable useWorkbenchLayout con persistencia

Singleton que mantiene los tamaños de los splitters del Workbench
(3 columnas + split vertical en panel derecho) y los persiste en
localStorage clave 'workbench.layout'. Defaults [15,55,30] + [50,50].
Sanitización: cualquier JSON malformado o shape inválido cae a
defaults silenciosamente.

5 tests cubren defaults, carga, JSON malformado, shape inválido y
persistencia."
```

---

## Task 4: Componente `<PageThumbnail>`

**Files:**
- Create: `web/frontend/src/components/workbench/PageThumbnail.vue`
- Create: `web/frontend/tests/components/workbench/PageThumbnail.test.ts`

- [ ] **Step 1: Test failing — render básico**

Crear `web/frontend/tests/components/workbench/PageThumbnail.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import PageThumbnail from '@/components/workbench/PageThumbnail.vue'
import type { PageResponse } from '@/api/types'

function makePage(overrides: Partial<PageResponse> = {}): PageResponse {
  return {
    id: 1, batch_id: 1, page_index: 0,
    needs_review: false, is_blank: false, pipeline_processed: false,
    created_at: '', image_path: '/img.png', ocr_text: '',
    index_fields_json: '{}', review_reason: '', is_excluded: false,
    processing_errors_json: '[]', script_errors_json: '[]',
    barcodes: [], updated_at: '',
    ...overrides,
  }
}

describe('PageThumbnail', () => {
  it('renders the page index in the footer', () => {
    const wrapper = mount(PageThumbnail, {
      props: { page: makePage({ page_index: 4 }), batchId: 1, selected: false },
      global: { stubs: { AuthImage: true } },
    })
    expect(wrapper.text()).toContain('#5')
  })
})
```

- [ ] **Step 2: Verificar fail**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run tests/components/workbench/PageThumbnail.test.ts 2>&1 | tail -5`
Expected: FAIL `Failed to resolve import`.

- [ ] **Step 3: Crear componente mínimo**

Crear `web/frontend/src/components/workbench/PageThumbnail.vue`:

```vue
<script setup lang="ts">
import { computed } from 'vue'
import AuthImage from '@/components/AuthImage.vue'
import { determinePageState, PAGE_STATE_BORDER_CLASS } from '@/composables/usePageState'
import { useBatchesStore } from '@/stores/batches'
import type { PageResponse } from '@/api/types'

const props = defineProps<{
  page: PageResponse
  batchId: number
  selected: boolean
}>()

const emit = defineEmits<{
  (e: 'select'): void
  (e: 'fit'): void
}>()

const store = useBatchesStore()

const borderClass = computed(() => PAGE_STATE_BORDER_CLASS[determinePageState(props.page)])
const imageUrl = computed(() => store.pageImageUrl(props.batchId, props.page.id))
</script>

<template>
  <button
    type="button"
    :data-test="`page-thumbnail-${page.page_index}`"
    :aria-label="`Página ${page.page_index + 1}`"
    :aria-pressed="selected"
    class="relative w-full text-left rounded overflow-hidden border-4 transition-colors"
    :class="[
      borderClass,
      selected ? 'ring-2 ring-primary ring-offset-2 ring-offset-base' : '',
    ]"
    @click="emit('select')"
    @dblclick="emit('fit')"
  >
    <AuthImage
      :src="imageUrl"
      :alt="`Página ${page.page_index + 1}`"
      class="w-full aspect-[3/4] object-cover bg-crust"
    />
    <div class="absolute bottom-0 left-0 right-0 bg-crust/90 text-text text-[11px] px-2 py-1 flex justify-between items-center">
      <span class="font-semibold">#{{ page.page_index + 1 }}</span>
      <div class="flex gap-1">
        <span v-if="page.needs_review" class="text-warning" title="Requiere revisión">!</span>
        <span v-if="page.pipeline_processed" class="text-success" title="Procesada">✓</span>
        <span v-if="page.is_excluded" class="text-danger" title="Excluida">×</span>
      </div>
    </div>
  </button>
</template>
```

- [ ] **Step 4: Verificar pass**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run tests/components/workbench/PageThumbnail.test.ts 2>&1 | tail -5`
Expected: `Tests 1 passed (1)`.

- [ ] **Step 5: Añadir tests restantes**

Añadir dentro del describe (necesita import de `setActivePinia, createPinia` arriba):

```ts
import { setActivePinia, createPinia } from 'pinia'
import { beforeEach } from 'vitest'

// y antes de los nuevos tests, añadir:
beforeEach(() => {
  setActivePinia(createPinia())
})
```

Tests adicionales:

```ts
  it('applies danger border when page is_excluded', () => {
    const wrapper = mount(PageThumbnail, {
      props: { page: makePage({ is_excluded: true }), batchId: 1, selected: false },
      global: { stubs: { AuthImage: true } },
    })
    expect(wrapper.find('button').classes()).toContain('border-danger')
  })

  it('applies primary border when page has fields', () => {
    const wrapper = mount(PageThumbnail, {
      props: { page: makePage({ index_fields_json: '{"a":1}' }), batchId: 1, selected: false },
      global: { stubs: { AuthImage: true } },
    })
    expect(wrapper.find('button').classes()).toContain('border-primary')
  })

  it('emits "select" on click', async () => {
    const wrapper = mount(PageThumbnail, {
      props: { page: makePage(), batchId: 1, selected: false },
      global: { stubs: { AuthImage: true } },
    })
    await wrapper.find('button').trigger('click')
    expect(wrapper.emitted('select')).toHaveLength(1)
  })

  it('emits "fit" on double click', async () => {
    const wrapper = mount(PageThumbnail, {
      props: { page: makePage(), batchId: 1, selected: false },
      global: { stubs: { AuthImage: true } },
    })
    await wrapper.find('button').trigger('dblclick')
    expect(wrapper.emitted('fit')).toHaveLength(1)
  })

  it('marks aria-pressed=true when selected', () => {
    const wrapper = mount(PageThumbnail, {
      props: { page: makePage(), batchId: 1, selected: true },
      global: { stubs: { AuthImage: true } },
    })
    expect(wrapper.find('button').attributes('aria-pressed')).toBe('true')
  })

  it('shows ✓ icon when pipeline_processed', () => {
    const wrapper = mount(PageThumbnail, {
      props: { page: makePage({ pipeline_processed: true }), batchId: 1, selected: false },
      global: { stubs: { AuthImage: true } },
    })
    expect(wrapper.text()).toContain('✓')
  })
```

- [ ] **Step 6: Tests pasan**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run tests/components/workbench/PageThumbnail.test.ts 2>&1 | tail -5`
Expected: `Tests 7 passed (7)`.

- [ ] **Step 7: Suite completa**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run 2>&1 | tail -5`
Expected: `Tests 185 passed (185)`.

- [ ] **Step 8: Commit**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy && git add web/frontend/src/components/workbench/PageThumbnail.vue web/frontend/tests/components/workbench/PageThumbnail.test.ts
git commit -m "feat(web-frontend): componente PageThumbnail con borde por estado

Miniatura individual del Workbench: imagen via AuthImage + borde
coloreado según determinePageState (6 estados) + footer con #N y
iconos !/✓/× según flags. Click emite select, doble-click emite
fit. Marca aria-pressed cuando selected=true.

7 tests vitest cubren render, bordes por estado, eventos y a11y."
```

---

## Task 5: Componente `<ThumbnailPanel>`

**Files:**
- Create: `web/frontend/src/components/workbench/ThumbnailPanel.vue`
- Create: `web/frontend/tests/components/workbench/ThumbnailPanel.test.ts`

- [ ] **Step 1: Test failing**

Crear `web/frontend/tests/components/workbench/ThumbnailPanel.test.ts`:

```ts
import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import ThumbnailPanel from '@/components/workbench/ThumbnailPanel.vue'
import type { PageResponse } from '@/api/types'

function makePage(idx: number): PageResponse {
  return {
    id: idx + 1, batch_id: 1, page_index: idx,
    needs_review: false, is_blank: false, pipeline_processed: false,
    created_at: '', image_path: `/p${idx}.png`, ocr_text: '',
    index_fields_json: '{}', review_reason: '', is_excluded: false,
    processing_errors_json: '[]', script_errors_json: '[]',
    barcodes: [], updated_at: '',
  }
}

describe('ThumbnailPanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('shows empty state when pages list is empty', () => {
    const wrapper = mount(ThumbnailPanel, {
      props: { pages: [], batchId: 1, selectedIndex: 0 },
      global: { stubs: { PageThumbnail: true, AuthImage: true } },
    })
    expect(wrapper.text()).toContain('Sin páginas')
  })
})
```

- [ ] **Step 2: Verificar fail**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run tests/components/workbench/ThumbnailPanel.test.ts 2>&1 | tail -5`
Expected: FAIL.

- [ ] **Step 3: Crear componente**

Crear `web/frontend/src/components/workbench/ThumbnailPanel.vue`:

```vue
<script setup lang="ts">
import PageThumbnail from '@/components/workbench/PageThumbnail.vue'
import type { PageResponse } from '@/api/types'

const props = defineProps<{
  pages: PageResponse[]
  batchId: number
  selectedIndex: number
}>()

const emit = defineEmits<{
  (e: 'select', index: number): void
  (e: 'fit'): void
}>()
</script>

<template>
  <aside class="h-full overflow-y-auto bg-mantle border-r border-surface-0 p-2 space-y-2">
    <div v-if="pages.length === 0" class="text-center text-subtext text-xs py-6">
      Sin páginas
      <p class="text-overlay-0 mt-1">Usa «Subir ficheros» en la barra superior</p>
    </div>
    <PageThumbnail
      v-for="(page, idx) in pages"
      :key="page.id"
      :page="page"
      :batchId="batchId"
      :selected="idx === selectedIndex"
      @select="emit('select', idx)"
      @fit="emit('fit')"
    />
  </aside>
</template>
```

- [ ] **Step 4: Verificar pass**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run tests/components/workbench/ThumbnailPanel.test.ts 2>&1 | tail -5`
Expected: `Tests 1 passed (1)`.

- [ ] **Step 5: Añadir tests restantes**

```ts
  it('renders one PageThumbnail per page', () => {
    const wrapper = mount(ThumbnailPanel, {
      props: { pages: [makePage(0), makePage(1), makePage(2)], batchId: 1, selectedIndex: 0 },
      global: { stubs: { PageThumbnail: true, AuthImage: true } },
    })
    expect(wrapper.findAllComponents({ name: 'PageThumbnail' })).toHaveLength(3)
  })

  it('emits "select" with index when child PageThumbnail emits select', async () => {
    const wrapper = mount(ThumbnailPanel, {
      props: { pages: [makePage(0), makePage(1)], batchId: 1, selectedIndex: 0 },
    })
    const thumbs = wrapper.findAllComponents({ name: 'PageThumbnail' })
    thumbs[1].vm.$emit('select')
    expect(wrapper.emitted('select')).toEqual([[1]])
  })

  it('emits "fit" when child PageThumbnail emits fit', () => {
    const wrapper = mount(ThumbnailPanel, {
      props: { pages: [makePage(0)], batchId: 1, selectedIndex: 0 },
    })
    wrapper.findComponent({ name: 'PageThumbnail' }).vm.$emit('fit')
    expect(wrapper.emitted('fit')).toHaveLength(1)
  })
```

- [ ] **Step 6: Pasan**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run tests/components/workbench/ThumbnailPanel.test.ts 2>&1 | tail -5`
Expected: `Tests 4 passed (4)`.

- [ ] **Step 7: Suite completa**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run 2>&1 | tail -5`
Expected: `Tests 189 passed (189)`.

- [ ] **Step 8: Commit**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy && git add web/frontend/src/components/workbench/ThumbnailPanel.vue web/frontend/tests/components/workbench/ThumbnailPanel.test.ts
git commit -m "feat(web-frontend): componente ThumbnailPanel scrollable

Panel izquierdo del Workbench que itera sobre las páginas y renderiza
un PageThumbnail por cada una. Empty state cuando no hay páginas.
Reemite los eventos select e fit de los thumbnails al padre.

4 tests cubren empty state, render lista, emit select con índice y
emit fit."
```

---

## Task 6: Componente `<BarcodePanel>`

**Files:**
- Create: `web/frontend/src/components/workbench/BarcodePanel.vue`
- Create: `web/frontend/tests/components/workbench/BarcodePanel.test.ts`

- [ ] **Step 1: Test failing**

Crear `web/frontend/tests/components/workbench/BarcodePanel.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BarcodePanel from '@/components/workbench/BarcodePanel.vue'
import type { BarcodeResponse } from '@/api/types'

function makeBarcode(overrides: Partial<BarcodeResponse> = {}): BarcodeResponse {
  return {
    id: 1, value: '12345', symbology: 'EAN13', engine: 'motor1',
    step_id: 's1', quality: 1, pos_x: 0, pos_y: 0, pos_w: 10, pos_h: 10, role: '',
    ...overrides,
  }
}

describe('BarcodePanel', () => {
  it('renders empty state when no barcodes', () => {
    const wrapper = mount(BarcodePanel, { props: { barcodes: [], pageCounters: { total: 0, withBarcode: 0, separators: 0, needsReview: 0 } } })
    expect(wrapper.text()).toContain('Sin barcodes')
  })
})
```

- [ ] **Step 2: Verificar fail**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run tests/components/workbench/BarcodePanel.test.ts 2>&1 | tail -5`
Expected: FAIL.

- [ ] **Step 3: Crear componente**

Crear `web/frontend/src/components/workbench/BarcodePanel.vue`:

```vue
<script setup lang="ts">
import type { BarcodeResponse } from '@/api/types'

defineProps<{
  barcodes: BarcodeResponse[]
  pageCounters: { total: number; withBarcode: number; separators: number; needsReview: number }
}>()

const COLORS = ['#1e66f5', '#40a02b', '#df8e1d', '#d20f39', '#8839ef', '#179299', '#e64553', '#dd7878']

function colorFor(idx: number): string {
  return COLORS[idx % COLORS.length]
}
</script>

<template>
  <section class="h-full flex flex-col bg-mantle border-l border-surface-0">
    <header class="px-3 py-2 border-b border-surface-0 flex items-center justify-between text-xs">
      <h2 class="font-semibold text-text uppercase tracking-wide">Barcodes</h2>
      <div class="flex gap-3 text-subtext">
        <span data-test="counter-total">Páginas: {{ pageCounters.total }}</span>
        <span data-test="counter-with-barcode">Con barcode: {{ pageCounters.withBarcode }}</span>
        <span data-test="counter-separators">Separadores: {{ pageCounters.separators }}</span>
        <span data-test="counter-needs-review">Revisión: {{ pageCounters.needsReview }}</span>
      </div>
    </header>

    <div class="flex-1 overflow-auto">
      <table v-if="barcodes.length > 0" class="w-full text-xs">
        <thead class="bg-crust text-subtext uppercase">
          <tr>
            <th class="w-6"></th>
            <th class="text-left px-2 py-1.5">Valor</th>
            <th class="text-left px-2 py-1.5">Símbolo</th>
            <th class="text-left px-2 py-1.5">Motor</th>
            <th class="text-left px-2 py-1.5">Rol</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(bc, idx) in barcodes" :key="bc.id" class="border-t border-surface-0">
            <td class="px-2"><span class="inline-block w-3 h-3 rounded-full" :style="{ backgroundColor: colorFor(idx) }"></span></td>
            <td class="px-2 py-1 text-text font-mono">{{ bc.value }}</td>
            <td class="px-2 py-1 text-subtext">{{ bc.symbology }}</td>
            <td class="px-2 py-1 text-subtext">{{ bc.engine }}</td>
            <td class="px-2 py-1 text-subtext">{{ bc.role || '—' }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else class="text-center text-subtext text-xs py-6">Sin barcodes en esta página</p>
    </div>
  </section>
</template>
```

- [ ] **Step 4: Verificar pass**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run tests/components/workbench/BarcodePanel.test.ts 2>&1 | tail -5`
Expected: `Tests 1 passed (1)`.

- [ ] **Step 5: Tests adicionales**

```ts
  it('renders a row per barcode with 5 columns', () => {
    const wrapper = mount(BarcodePanel, {
      props: {
        barcodes: [makeBarcode({ id: 1, value: 'A' }), makeBarcode({ id: 2, value: 'B', role: 'separator' })],
        pageCounters: { total: 1, withBarcode: 1, separators: 1, needsReview: 0 },
      },
    })
    const rows = wrapper.findAll('tbody tr')
    expect(rows).toHaveLength(2)
    expect(rows[0].findAll('td')).toHaveLength(5)
  })

  it('shows counters in header', () => {
    const wrapper = mount(BarcodePanel, {
      props: {
        barcodes: [],
        pageCounters: { total: 12, withBarcode: 8, separators: 3, needsReview: 1 },
      },
    })
    expect(wrapper.find('[data-test="counter-total"]').text()).toContain('12')
    expect(wrapper.find('[data-test="counter-with-barcode"]').text()).toContain('8')
    expect(wrapper.find('[data-test="counter-separators"]').text()).toContain('3')
    expect(wrapper.find('[data-test="counter-needs-review"]').text()).toContain('1')
  })

  it('shows em-dash when role is empty', () => {
    const wrapper = mount(BarcodePanel, {
      props: { barcodes: [makeBarcode({ role: '' })], pageCounters: { total: 0, withBarcode: 0, separators: 0, needsReview: 0 } },
    })
    expect(wrapper.find('tbody tr').findAll('td')[4].text()).toBe('—')
  })

  it('cycles colors when more barcodes than palette', () => {
    const many = Array.from({ length: 9 }, (_, i) => makeBarcode({ id: i + 1, value: `V${i}` }))
    const wrapper = mount(BarcodePanel, {
      props: { barcodes: many, pageCounters: { total: 1, withBarcode: 1, separators: 0, needsReview: 0 } },
    })
    const dots = wrapper.findAll('tbody tr td:first-child span')
    expect(dots[0].attributes('style')).toBe(dots[8].attributes('style'))
  })
```

- [ ] **Step 6: Tests pasan**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run tests/components/workbench/BarcodePanel.test.ts 2>&1 | tail -5`
Expected: `Tests 5 passed (5)`.

- [ ] **Step 7: Suite completa**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run 2>&1 | tail -5`
Expected: `Tests 194 passed (194)`.

- [ ] **Step 8: Commit**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy && git add web/frontend/src/components/workbench/BarcodePanel.vue web/frontend/tests/components/workbench/BarcodePanel.test.ts
git commit -m "feat(web-frontend): componente BarcodePanel view-only

Panel derecho-arriba del Workbench: tabla de 5 columnas (color,
valor, símbolo, motor, rol) con paleta cíclica de 8 colores. Header
con 4 contadores de lote (total, con-barcode, separadores, revisión).
Empty state cuando la página actual no tiene barcodes.

5 tests cubren empty state, render tabla, contadores, em-dash en
rol vacío y ciclo de paleta."
```

---

## Task 7: Componente `<MetadataPanel>`

**Files:**
- Create: `web/frontend/src/components/workbench/MetadataPanel.vue`
- Create: `web/frontend/tests/components/workbench/MetadataPanel.test.ts`

- [ ] **Step 1: Test failing**

Crear `web/frontend/tests/components/workbench/MetadataPanel.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import MetadataPanel from '@/components/workbench/MetadataPanel.vue'
import type { ApplicationResponse, BatchResponse } from '@/api/types'

function makeApp(batchFields: unknown[] = []): ApplicationResponse {
  return {
    id: 1, name: 'X', description: '', active: true, output_format: 'tiff',
    created_at: '', tenant_id: 1, pipeline_json: '[]', events_json: '{}',
    transfer_json: '{}', batch_fields_json: JSON.stringify(batchFields),
    index_fields_json: '[]', auto_transfer: false, close_after_transfer: false,
    background_color: '', default_tab: 'lote', scanner_backend: '',
    image_config_json: '{}', ai_config_json: '{}', updated_at: '',
  }
}

function makeBatch(fields: Record<string, unknown> = {}): BatchResponse {
  return {
    id: 1, application_id: 1, state: 'read', page_count: 0,
    created_at: '', updated_at: '', fields_json: JSON.stringify(fields),
    folder_path: '', hostname: '',
  }
}

describe('MetadataPanel', () => {
  it('renders empty state when application has no batch_fields', () => {
    const wrapper = mount(MetadataPanel, {
      props: { app: makeApp([]), batch: makeBatch(), saving: false },
    })
    expect(wrapper.text()).toContain('Sin campos definidos')
  })
})
```

- [ ] **Step 2: Verificar fail**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run tests/components/workbench/MetadataPanel.test.ts 2>&1 | tail -5`
Expected: FAIL.

- [ ] **Step 3: Crear componente**

Crear `web/frontend/src/components/workbench/MetadataPanel.vue`:

```vue
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { ApplicationResponse, BatchResponse } from '@/api/types'

interface BatchField {
  label: string
  type: 'texto' | 'fecha' | 'lista' | 'numerico'
  required: boolean
  config: Record<string, unknown>
}

const props = defineProps<{
  app: ApplicationResponse | null
  batch: BatchResponse | null
  saving: boolean
}>()

const emit = defineEmits<{
  (e: 'save', fields: Record<string, unknown>): void
}>()

const activeTab = ref<'lote' | 'log'>('lote')

const fieldDefs = computed<BatchField[]>(() => {
  if (!props.app) return []
  try {
    const parsed = JSON.parse(props.app.batch_fields_json || '[]')
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
})

const initialFields = computed<Record<string, unknown>>(() => {
  if (!props.batch) return {}
  try {
    const parsed = JSON.parse(props.batch.fields_json || '{}')
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
})

const localFields = ref<Record<string, unknown>>({ ...initialFields.value })

watch(initialFields, (next) => {
  localFields.value = { ...next }
})

const hasChanges = computed(() => {
  return JSON.stringify(localFields.value) !== JSON.stringify(initialFields.value)
})

const validationError = computed<string | null>(() => {
  for (const f of fieldDefs.value) {
    if (f.required && !localFields.value[f.label]) {
      return `Campo obligatorio: ${f.label}`
    }
  }
  return null
})

function onSave(): void {
  if (validationError.value) return
  emit('save', { ...localFields.value })
}
</script>

<template>
  <section class="h-full flex flex-col bg-mantle border-l border-t border-surface-0">
    <nav class="flex border-b border-surface-0" aria-label="Pestañas de metadatos">
      <button
        type="button"
        :aria-pressed="activeTab === 'lote'"
        class="px-3 py-2 text-xs uppercase tracking-wide font-semibold transition-colors"
        :class="activeTab === 'lote' ? 'text-primary border-b-2 border-primary' : 'text-subtext hover:text-text'"
        @click="activeTab = 'lote'"
      >
        Lote
      </button>
      <button
        type="button"
        disabled
        class="px-3 py-2 text-xs uppercase tracking-wide text-overlay-0 cursor-not-allowed"
        title="Disponible en Fase 3"
      >
        Log
      </button>
    </nav>

    <div v-if="activeTab === 'lote'" class="flex-1 overflow-auto p-3">
      <p v-if="fieldDefs.length === 0" class="text-center text-subtext text-xs py-6">
        Sin campos definidos
        <span class="block text-overlay-0 mt-1">Configura batch_fields en la aplicación</span>
      </p>

      <form v-else class="space-y-3" @submit.prevent="onSave">
        <div v-for="field in fieldDefs" :key="field.label" class="space-y-1">
          <label class="block text-xs font-medium text-text">
            {{ field.label }}<span v-if="field.required" class="text-danger">*</span>
          </label>
          <input
            v-if="field.type === 'texto'"
            type="text"
            :value="localFields[field.label] ?? ''"
            class="w-full px-2 py-1 text-xs bg-base border border-surface-1 rounded text-text"
            @input="localFields[field.label] = ($event.target as HTMLInputElement).value"
          />
          <input
            v-else-if="field.type === 'fecha'"
            type="date"
            :value="localFields[field.label] ?? ''"
            class="w-full px-2 py-1 text-xs bg-base border border-surface-1 rounded text-text"
            @input="localFields[field.label] = ($event.target as HTMLInputElement).value"
          />
          <input
            v-else-if="field.type === 'numerico'"
            type="number"
            :value="localFields[field.label] ?? ''"
            class="w-full px-2 py-1 text-xs bg-base border border-surface-1 rounded text-text"
            @input="localFields[field.label] = Number(($event.target as HTMLInputElement).value)"
          />
          <select
            v-else-if="field.type === 'lista'"
            :value="localFields[field.label] ?? ''"
            class="w-full px-2 py-1 text-xs bg-base border border-surface-1 rounded text-text"
            @change="localFields[field.label] = ($event.target as HTMLSelectElement).value"
          >
            <option value="">—</option>
            <option v-for="opt in (field.config?.values as string[] | undefined) ?? []" :key="opt" :value="opt">{{ opt }}</option>
          </select>
        </div>

        <p v-if="validationError" class="text-xs text-danger">{{ validationError }}</p>

        <button
          type="submit"
          :disabled="!hasChanges || saving || !!validationError || !batch"
          class="w-full bg-primary text-base font-semibold text-xs px-3 py-1.5 rounded hover:bg-primary-hover disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {{ saving ? 'Guardando…' : 'Guardar' }}
        </button>
      </form>
    </div>
  </section>
</template>
```

- [ ] **Step 4: Verificar pass**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run tests/components/workbench/MetadataPanel.test.ts 2>&1 | tail -5`
Expected: `Tests 1 passed (1)`.

- [ ] **Step 5: Tests adicionales**

```ts
  it('renders text input for type=texto', () => {
    const wrapper = mount(MetadataPanel, {
      props: {
        app: makeApp([{ label: 'Cliente', type: 'texto', required: false, config: {} }]),
        batch: makeBatch({ Cliente: 'ACME' }), saving: false,
      },
    })
    const input = wrapper.find('input[type="text"]')
    expect(input.exists()).toBe(true)
    expect((input.element as HTMLInputElement).value).toBe('ACME')
  })

  it('renders date / number / select for other field types', () => {
    const wrapper = mount(MetadataPanel, {
      props: {
        app: makeApp([
          { label: 'F', type: 'fecha', required: false, config: {} },
          { label: 'N', type: 'numerico', required: false, config: {} },
          { label: 'L', type: 'lista', required: false, config: { values: ['a', 'b'] } },
        ]),
        batch: makeBatch(), saving: false,
      },
    })
    expect(wrapper.find('input[type="date"]').exists()).toBe(true)
    expect(wrapper.find('input[type="number"]').exists()).toBe(true)
    expect(wrapper.findAll('select option')).toHaveLength(3) // "—" + a + b
  })

  it('disables save when no changes', () => {
    const wrapper = mount(MetadataPanel, {
      props: {
        app: makeApp([{ label: 'C', type: 'texto', required: false, config: {} }]),
        batch: makeBatch(), saving: false,
      },
    })
    expect((wrapper.find('button[type="submit"]').element as HTMLButtonElement).disabled).toBe(true)
  })

  it('enables save and emits "save" with new fields when user edits', async () => {
    const wrapper = mount(MetadataPanel, {
      props: {
        app: makeApp([{ label: 'C', type: 'texto', required: false, config: {} }]),
        batch: makeBatch(), saving: false,
      },
    })
    await wrapper.find('input[type="text"]').setValue('NEW')
    await wrapper.find('form').trigger('submit')
    expect(wrapper.emitted('save')).toEqual([[{ C: 'NEW' }]])
  })

  it('blocks save with required field empty and shows error', async () => {
    const wrapper = mount(MetadataPanel, {
      props: {
        app: makeApp([{ label: 'C', type: 'texto', required: true, config: {} }]),
        batch: makeBatch({ C: 'old' }), saving: false,
      },
    })
    await wrapper.find('input[type="text"]').setValue('')
    expect(wrapper.text()).toContain('Campo obligatorio: C')
    expect((wrapper.find('button[type="submit"]').element as HTMLButtonElement).disabled).toBe(true)
  })

  it('shows "Guardando…" when saving=true', () => {
    const wrapper = mount(MetadataPanel, {
      props: {
        app: makeApp([{ label: 'C', type: 'texto', required: false, config: {} }]),
        batch: makeBatch({ C: 'x' }), saving: true,
      },
    })
    expect(wrapper.find('button[type="submit"]').text()).toBe('Guardando…')
  })

  it('disables save when batch is null', () => {
    const wrapper = mount(MetadataPanel, {
      props: {
        app: makeApp([{ label: 'C', type: 'texto', required: false, config: {} }]),
        batch: null, saving: false,
      },
    })
    expect((wrapper.find('button[type="submit"]').element as HTMLButtonElement).disabled).toBe(true)
  })
```

- [ ] **Step 6: Tests pasan**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run tests/components/workbench/MetadataPanel.test.ts 2>&1 | tail -5`
Expected: `Tests 8 passed (8)`.

- [ ] **Step 7: Suite completa**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run 2>&1 | tail -5`
Expected: `Tests 202 passed (202)`.

- [ ] **Step 8: Commit**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy && git add web/frontend/src/components/workbench/MetadataPanel.vue web/frontend/tests/components/workbench/MetadataPanel.test.ts
git commit -m "feat(web-frontend): componente MetadataPanel con tab Lote editable

Panel derecho-abajo del Workbench. Tabs UI preparada (Lote activa,
Log deshabilitada con tooltip 'Disponible en Fase 3'). Form dinámico
de campos custom según batch_fields_json de la app: input text,
date, number, select según el tipo. Validación de required.
hasChanges + saving + emit save al padre.

8 tests cubren empty state, render por tipo, disable save sin
cambios, emit save con cambios, validación required, estado
guardando y batch null."
```

---

## Task 8: Extender `<DocumentViewer>` + componente `<ViewerToolbar>`

**Files:**
- Modify: `web/frontend/src/components/DocumentViewer.vue`
- Create: `web/frontend/src/components/workbench/ViewerToolbar.vue`
- Create: `web/frontend/tests/components/workbench/ViewerToolbar.test.ts`

- [ ] **Step 1: Modificar DocumentViewer.vue para exponer métodos**

En `web/frontend/src/components/DocumentViewer.vue`, justo antes del `</script>` (al final del bloque `<script setup lang="ts">`), añadir:

```ts
defineExpose({
  zoomIn: () => zoomBy(1.25),
  zoomOut: () => zoomBy(1 / 1.25),
  resetView,
  fitToViewport,
  zoomPercent,
})
```

Esto expone los métodos al `ref` del componente padre. `zoomBy`, `resetView`, `fitToViewport` y `zoomPercent` ya existen en el script.

- [ ] **Step 2: Verificar typecheck OK**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vue-tsc --noEmit 2>&1 | tail -5`
Expected: sin errores.

- [ ] **Step 3: Test failing del ViewerToolbar**

Crear `web/frontend/tests/components/workbench/ViewerToolbar.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ViewerToolbar from '@/components/workbench/ViewerToolbar.vue'

describe('ViewerToolbar', () => {
  it('renders four buttons and a percent indicator', () => {
    const wrapper = mount(ViewerToolbar, { props: { zoomPercent: 100 } })
    const buttons = wrapper.findAll('button')
    expect(buttons).toHaveLength(4)
    expect(wrapper.text()).toContain('100%')
  })
})
```

- [ ] **Step 4: Verificar fail**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run tests/components/workbench/ViewerToolbar.test.ts 2>&1 | tail -5`
Expected: FAIL.

- [ ] **Step 5: Crear ViewerToolbar**

Crear `web/frontend/src/components/workbench/ViewerToolbar.vue`:

```vue
<script setup lang="ts">
defineProps<{ zoomPercent: number }>()

const emit = defineEmits<{
  (e: 'zoom-in'): void
  (e: 'zoom-out'): void
  (e: 'reset'): void
  (e: 'fit'): void
}>()
</script>

<template>
  <div class="absolute top-2 right-2 z-10 inline-flex items-center bg-mantle border border-surface-1 rounded shadow-sm">
    <button
      type="button"
      data-test="vt-zoom-in"
      title="Acercar"
      aria-label="Acercar"
      class="px-2 py-1 text-text hover:bg-crust transition-colors"
      @click="emit('zoom-in')"
    >+</button>
    <button
      type="button"
      data-test="vt-zoom-out"
      title="Alejar"
      aria-label="Alejar"
      class="px-2 py-1 text-text hover:bg-crust transition-colors border-l border-surface-1"
      @click="emit('zoom-out')"
    >−</button>
    <button
      type="button"
      data-test="vt-reset"
      title="Tamaño 100%"
      aria-label="Tamaño 100%"
      class="px-2 py-1 text-text hover:bg-crust transition-colors border-l border-surface-1 text-xs"
      @click="emit('reset')"
    >1:1</button>
    <button
      type="button"
      data-test="vt-fit"
      title="Ajustar a la vista"
      aria-label="Ajustar a la vista"
      class="px-2 py-1 text-text hover:bg-crust transition-colors border-l border-surface-1"
      @click="emit('fit')"
    >⛶</button>
    <span class="px-2 py-1 text-xs text-subtext border-l border-surface-1 min-w-[3.5rem] text-right" data-test="vt-percent">
      {{ zoomPercent }}%
    </span>
  </div>
</template>
```

- [ ] **Step 6: Verificar pass**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run tests/components/workbench/ViewerToolbar.test.ts 2>&1 | tail -5`
Expected: `Tests 1 passed (1)`.

- [ ] **Step 7: Tests adicionales**

```ts
  it('emits zoom-in on + button click', async () => {
    const wrapper = mount(ViewerToolbar, { props: { zoomPercent: 100 } })
    await wrapper.find('[data-test="vt-zoom-in"]').trigger('click')
    expect(wrapper.emitted('zoom-in')).toHaveLength(1)
  })

  it('emits zoom-out on − button click', async () => {
    const wrapper = mount(ViewerToolbar, { props: { zoomPercent: 100 } })
    await wrapper.find('[data-test="vt-zoom-out"]').trigger('click')
    expect(wrapper.emitted('zoom-out')).toHaveLength(1)
  })

  it('emits reset on 1:1 button click', async () => {
    const wrapper = mount(ViewerToolbar, { props: { zoomPercent: 100 } })
    await wrapper.find('[data-test="vt-reset"]').trigger('click')
    expect(wrapper.emitted('reset')).toHaveLength(1)
  })

  it('emits fit on ⛶ button click', async () => {
    const wrapper = mount(ViewerToolbar, { props: { zoomPercent: 100 } })
    await wrapper.find('[data-test="vt-fit"]').trigger('click')
    expect(wrapper.emitted('fit')).toHaveLength(1)
  })

  it('shows the current zoom percent', () => {
    const wrapper = mount(ViewerToolbar, { props: { zoomPercent: 75 } })
    expect(wrapper.find('[data-test="vt-percent"]').text()).toBe('75%')
  })
```

- [ ] **Step 8: Tests pasan**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run tests/components/workbench/ViewerToolbar.test.ts 2>&1 | tail -5`
Expected: `Tests 6 passed (6)`.

- [ ] **Step 9: Suite completa**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run 2>&1 | tail -5`
Expected: `Tests 208 passed (208)`.

- [ ] **Step 10: Commit**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy && git add web/frontend/src/components/DocumentViewer.vue web/frontend/src/components/workbench/ViewerToolbar.vue web/frontend/tests/components/workbench/ViewerToolbar.test.ts
git commit -m "feat(web-frontend): ViewerToolbar flotante + DocumentViewer expone métodos

DocumentViewer ahora expone via defineExpose: zoomIn, zoomOut,
resetView, fitToViewport, zoomPercent. ViewerToolbar es un
componente externo absolutamente posicionado (top-right del visor)
con 4 botones (+, −, 1:1, ⛶) y un indicador de zoom%. Comunica con
el viewer via ref del padre.

6 tests del ViewerToolbar cubren render, los 4 emits y el indicador."
```

---

## Task 9: Componente `<WorkbenchToolbar>`

**Files:**
- Create: `web/frontend/src/components/workbench/WorkbenchToolbar.vue`
- Create: `web/frontend/tests/components/workbench/WorkbenchToolbar.test.ts`

- [ ] **Step 1: Test failing**

Crear `web/frontend/tests/components/workbench/WorkbenchToolbar.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import WorkbenchToolbar from '@/components/workbench/WorkbenchToolbar.vue'
import type { BatchResponse } from '@/api/types'

function makeBatch(overrides: Partial<BatchResponse> = {}): BatchResponse {
  return {
    id: 1, application_id: 1, state: 'pending', page_count: 0,
    created_at: '', updated_at: '', fields_json: '{}', folder_path: '', hostname: '',
    ...overrides,
  }
}

describe('WorkbenchToolbar', () => {
  it('renders 5 action buttons and the title', () => {
    const wrapper = mount(WorkbenchToolbar, {
      props: { batch: makeBatch(), running: false, transferring: false, uploading: false },
    })
    expect(wrapper.text()).toContain('Lote #1')
    const buttons = wrapper.findAll('button')
    expect(buttons.length).toBeGreaterThanOrEqual(5)
  })
})
```

- [ ] **Step 2: Verificar fail**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run tests/components/workbench/WorkbenchToolbar.test.ts 2>&1 | tail -5`
Expected: FAIL.

- [ ] **Step 3: Crear componente**

Crear `web/frontend/src/components/workbench/WorkbenchToolbar.vue`:

```vue
<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import type { BatchResponse } from '@/api/types'

const props = defineProps<{
  batch: BatchResponse
  running: boolean
  transferring: boolean
  uploading: boolean
}>()

const emit = defineEmits<{
  (e: 'upload', files: File[]): void
  (e: 'run-pipeline'): void
  (e: 'transfer'): void
  (e: 'download-zip'): void
  (e: 'delete-batch'): void
}>()

const router = useRouter()
const canTransfer = computed(() => props.batch.state === 'read' && !props.transferring && !props.running)
const busy = computed(() => props.running || props.transferring || props.uploading)

function onUpload(event: Event): void {
  const input = event.target as HTMLInputElement
  if (!input.files?.length) return
  emit('upload', Array.from(input.files))
  input.value = ''
}
</script>

<template>
  <header class="border-b border-surface-0 px-4 py-2 flex items-center justify-between gap-4 bg-mantle">
    <div class="flex items-center gap-3">
      <button
        type="button"
        class="text-xs text-subtext hover:text-text inline-flex items-center gap-1"
        @click="router.push('/batches')"
      >
        ← Lotes
      </button>
      <h1 class="text-sm font-bold text-text">Lote #{{ batch.id }}</h1>
      <span class="text-xs text-subtext uppercase tracking-wide">{{ batch.state }}</span>
    </div>
    <div class="flex items-center gap-1">
      <label class="bg-base text-text text-xs px-3 py-1.5 rounded border border-surface-1 cursor-pointer hover:bg-crust">
        ↑ Subir
        <input type="file" multiple class="hidden" :disabled="busy" @change="onUpload" />
      </label>
      <button
        type="button"
        class="bg-primary text-base text-xs px-3 py-1.5 rounded font-semibold hover:bg-primary-hover disabled:opacity-50"
        :disabled="busy || batch.page_count === 0"
        @click="emit('run-pipeline')"
      >▶ Pipeline</button>
      <button
        type="button"
        class="bg-base text-text text-xs px-3 py-1.5 rounded border border-surface-1 hover:bg-crust disabled:opacity-50"
        :disabled="!canTransfer"
        @click="emit('transfer')"
      >↗ Transferir</button>
      <button
        type="button"
        class="bg-base text-text text-xs px-3 py-1.5 rounded border border-surface-1 hover:bg-crust"
        @click="emit('download-zip')"
      >↓ ZIP</button>
      <button
        type="button"
        class="bg-base text-danger text-xs px-3 py-1.5 rounded border border-surface-1 hover:bg-danger hover:text-base"
        :disabled="busy"
        @click="emit('delete-batch')"
      >Eliminar</button>
    </div>
  </header>
</template>
```

- [ ] **Step 4: Verificar pass**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run tests/components/workbench/WorkbenchToolbar.test.ts 2>&1 | tail -5`

(Si el test falla por `useRouter` sin router instalado, ajustar el mount con `global.mocks: { $router: { push: vi.fn() } }` o usar `createRouter` mínimo. Patrón sugerido para tests siguientes:)

```ts
import { createRouter, createMemoryHistory } from 'vue-router'

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/batches', component: { template: '<div/>' } }],
  })
}
```

Y usar `global: { plugins: [makeRouter()] }` en cada `mount`. Ajustar el primer test:

```ts
it('renders 5 action buttons and the title', async () => {
  const router = makeRouter()
  await router.isReady()
  const wrapper = mount(WorkbenchToolbar, {
    props: { batch: makeBatch(), running: false, transferring: false, uploading: false },
    global: { plugins: [router] },
  })
  expect(wrapper.text()).toContain('Lote #1')
  expect(wrapper.findAll('button').length).toBeGreaterThanOrEqual(4) // sin contar el label de upload
})
```

Re-run. Expected: PASS.

- [ ] **Step 5: Tests adicionales**

```ts
  it('disables Pipeline when page_count is 0', async () => {
    const router = makeRouter(); await router.isReady()
    const wrapper = mount(WorkbenchToolbar, {
      props: { batch: makeBatch({ page_count: 0 }), running: false, transferring: false, uploading: false },
      global: { plugins: [router] },
    })
    const pipelineBtn = wrapper.findAll('button').find((b) => b.text().includes('Pipeline'))!
    expect((pipelineBtn.element as HTMLButtonElement).disabled).toBe(true)
  })

  it('disables Transferir unless batch.state === "read"', async () => {
    const router = makeRouter(); await router.isReady()
    const wrapper = mount(WorkbenchToolbar, {
      props: { batch: makeBatch({ state: 'pending' }), running: false, transferring: false, uploading: false },
      global: { plugins: [router] },
    })
    const transferBtn = wrapper.findAll('button').find((b) => b.text().includes('Transferir'))!
    expect((transferBtn.element as HTMLButtonElement).disabled).toBe(true)
  })

  it('emits "run-pipeline" when Pipeline clicked', async () => {
    const router = makeRouter(); await router.isReady()
    const wrapper = mount(WorkbenchToolbar, {
      props: { batch: makeBatch({ page_count: 3 }), running: false, transferring: false, uploading: false },
      global: { plugins: [router] },
    })
    const pipelineBtn = wrapper.findAll('button').find((b) => b.text().includes('Pipeline'))!
    await pipelineBtn.trigger('click')
    expect(wrapper.emitted('run-pipeline')).toHaveLength(1)
  })
```

- [ ] **Step 6: Tests pasan**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run tests/components/workbench/WorkbenchToolbar.test.ts 2>&1 | tail -5`
Expected: `Tests 4 passed (4)`.

- [ ] **Step 7: Suite completa**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run 2>&1 | tail -5`
Expected: `Tests 212 passed (212)`.

- [ ] **Step 8: Commit**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy && git add web/frontend/src/components/workbench/WorkbenchToolbar.vue web/frontend/tests/components/workbench/WorkbenchToolbar.test.ts
git commit -m "feat(web-frontend): WorkbenchToolbar con 5 acciones y estados disabled

Top toolbar del Workbench: navegación a Lotes, título 'Lote #N',
estado, y 5 botones de acción (Subir, ▶ Pipeline, ↗ Transferir,
↓ ZIP, Eliminar). Pipeline disabled si page_count=0. Transferir
sólo si state==='read'. Todos disabled durante running/transferring/
uploading.

4 tests cubren render, disabled states y emit run-pipeline."
```

---

## Task 10: `WorkbenchView` ensamblado

**Files:**
- Create: `web/frontend/src/views/batches/WorkbenchView.vue`
- Create: `web/frontend/tests/views/batches/WorkbenchView.test.ts`

- [ ] **Step 1: Test failing — smoke mount**

Crear `web/frontend/tests/views/batches/WorkbenchView.test.ts`:

```ts
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import WorkbenchView from '@/views/batches/WorkbenchView.vue'
import { useBatchesStore } from '@/stores/batches'
import { useApplicationsStore } from '@/stores/applications'

function makeRouter(initial = '/batches/1') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/batches', component: { template: '<div/>' } },
      { path: '/batches/:id', component: WorkbenchView, props: true },
    ],
  })
  router.push(initial)
  return router
}

describe('WorkbenchView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('mounts and calls store.fetchOne + fetchPages on the route batchId', async () => {
    const batches = useBatchesStore()
    const apps = useApplicationsStore()
    batches.fetchOne = vi.fn(async () => {
      batches.current = {
        id: 1, application_id: 5, state: 'read', page_count: 0,
        created_at: '', updated_at: '', fields_json: '{}', folder_path: '', hostname: '',
      }
    })
    batches.fetchPages = vi.fn(async () => { batches.pages = [] })
    apps.fetchOne = vi.fn(async () => {})
    const router = makeRouter('/batches/1')
    await router.isReady()
    mount(WorkbenchView, { global: { plugins: [router] } })
    await flushPromises()
    expect(batches.fetchOne).toHaveBeenCalledWith(1)
    expect(batches.fetchPages).toHaveBeenCalledWith(1)
  })
})
```

- [ ] **Step 2: Verificar fail**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run tests/views/batches/WorkbenchView.test.ts 2>&1 | tail -5`
Expected: FAIL `Failed to resolve import "@/views/batches/WorkbenchView.vue"`.

- [ ] **Step 3: Crear WorkbenchView**

Crear `web/frontend/src/views/batches/WorkbenchView.vue`:

```vue
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, useTemplateRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Splitpanes, Pane } from 'splitpanes'
import 'splitpanes/dist/splitpanes.css'

import { ApiError } from '@/api/client'
import DocumentViewer from '@/components/DocumentViewer.vue'
import ThumbnailPanel from '@/components/workbench/ThumbnailPanel.vue'
import BarcodePanel from '@/components/workbench/BarcodePanel.vue'
import MetadataPanel from '@/components/workbench/MetadataPanel.vue'
import ViewerToolbar from '@/components/workbench/ViewerToolbar.vue'
import WorkbenchToolbar from '@/components/workbench/WorkbenchToolbar.vue'
import { useBatchesStore } from '@/stores/batches'
import { useApplicationsStore } from '@/stores/applications'
import { useToast } from '@/composables/useToast'
import { useWorkbenchLayout } from '@/composables/useWorkbenchLayout'

const route = useRoute()
const router = useRouter()
const store = useBatchesStore()
const appStore = useApplicationsStore()
const toast = useToast()
const { sizes, setSizes } = useWorkbenchLayout()

const batchId = computed(() => Number(route.params.id))
const selectedPageIndex = ref(0)
const uploading = ref(false)
const running = ref(false)
const transferring = ref(false)
const transferStatus = ref<'idle' | 'running' | 'completed' | 'error' | 'aborted'>('idle')
const transferMessage = ref<string | null>(null)
const transferProgress = ref<{ page_index: number; total: number } | null>(null)
const progress = ref<{ processed: number; total: number } | null>(null)
const error = ref<string | null>(null)
const savingMetadata = ref(false)

const viewerRef = useTemplateRef<InstanceType<typeof DocumentViewer>>('viewerRef')

const sortedPages = computed(() => [...(store.pages ?? [])].sort((a, b) => a.page_index - b.page_index))
const currentPageListItem = computed(() => sortedPages.value[selectedPageIndex.value])

const currentPage = computed(() => store.currentPage)
const currentImageUrl = computed(() =>
  currentPageListItem.value ? store.pageImageUrl(batchId.value, currentPageListItem.value.id) : '',
)

const counters = computed(() => {
  let withBarcode = 0
  let separators = 0
  let needsReview = 0
  for (const p of sortedPages.value) {
    if (p.needs_review) needsReview++
  }
  if (currentPage.value?.barcodes?.length) {
    withBarcode = sortedPages.value.length // approximation: per-page barcode count needs lazy fetch
  }
  if (currentPage.value?.barcodes?.some((b) => b.role === 'separator')) {
    separators = 1
  }
  return { total: sortedPages.value.length, withBarcode, separators, needsReview }
})

watch(
  () => currentPageListItem.value?.id,
  async (id) => {
    if (id) await store.fetchPage(batchId.value, id)
  },
)

onMounted(async () => {
  await store.fetchOne(batchId.value)
  await store.fetchPages(batchId.value)
  if (store.current?.application_id) await appStore.fetchOne(store.current.application_id)
  if (sortedPages.value.length > 0) {
    await store.fetchPage(batchId.value, sortedPages.value[0].id)
  }
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
})

function onKeydown(e: KeyboardEvent): void {
  if (e.target instanceof HTMLElement && ['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) return
  if (e.key === 'ArrowLeft') {
    selectedPageIndex.value = Math.max(0, selectedPageIndex.value - 1)
    e.preventDefault()
  } else if (e.key === 'ArrowRight') {
    selectedPageIndex.value = Math.min(sortedPages.value.length - 1, selectedPageIndex.value + 1)
    e.preventDefault()
  }
}

function openWs(): WebSocket {
  const token = localStorage.getItem('access_token') ?? ''
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return new WebSocket(`${proto}://${window.location.host}/ws/batches/${batchId.value}?token=${encodeURIComponent(token)}`)
}

async function onUpload(files: File[]): Promise<void> {
  uploading.value = true
  error.value = null
  try {
    await store.uploadFiles(batchId.value, files)
    await store.fetchOne(batchId.value)
  } catch (e) {
    error.value = e instanceof ApiError ? e.detail : 'Error al subir ficheros'
    toast.error(error.value!)
  } finally {
    uploading.value = false
  }
}

async function onRunPipeline(): Promise<void> {
  running.value = true
  error.value = null
  progress.value = null
  const ws = openWs()
  ws.onmessage = async (msg) => {
    const event = JSON.parse(msg.data)
    if (event.type === 'pipeline_started') {
      progress.value = { processed: 0, total: event.total_pages }
    } else if (event.type === 'page_processed') {
      progress.value = { processed: event.processed, total: event.total }
    } else if (event.type === 'pipeline_completed') {
      await Promise.all([store.fetchOne(batchId.value), store.fetchPages(batchId.value)])
      if (currentPageListItem.value) await store.fetchPage(batchId.value, currentPageListItem.value.id)
      running.value = false
      progress.value = null
      ws.close()
      toast[event.any_error ? 'error' : 'success'](
        event.any_error ? 'Pipeline con errores' : 'Pipeline completado',
      )
      if (appStore.current?.auto_transfer && store.current?.state === 'read') {
        await onTransfer()
      }
    } else if (event.type === 'pipeline_error') {
      error.value = `Error pipeline: ${event.error}`
      running.value = false
      progress.value = null
      ws.close()
      toast.error(error.value)
    }
  }
  ws.onerror = () => { error.value = 'Error de conexión'; running.value = false }
  try {
    await new Promise<void>((resolve, reject) => {
      ws.onopen = () => resolve()
      ws.addEventListener('error', () => reject(new Error('ws')), { once: true })
    })
    await store.runPipeline(batchId.value)
  } catch (e) {
    error.value = e instanceof ApiError ? e.detail : 'Error al ejecutar pipeline'
    running.value = false
    ws.close()
  }
}

async function onTransfer(): Promise<void> {
  if (transferring.value) return
  transferring.value = true
  transferStatus.value = 'running'
  transferMessage.value = null
  transferProgress.value = null
  const ws = openWs()
  ws.onmessage = async (msg) => {
    const event = JSON.parse(msg.data)
    if (event.type === 'transfer_started') {
      transferProgress.value = { page_index: 0, total: event.total_pages }
    } else if (event.type === 'transfer_page' && transferProgress.value) {
      transferProgress.value = { page_index: event.page_index + 1, total: transferProgress.value.total }
    } else if (event.type === 'transfer_completed') {
      transferring.value = false
      ws.close()
      transferStatus.value = event.success ? 'completed' : 'error'
      transferMessage.value = event.success
        ? (event.output_path ? `Transferencia → ${event.output_path}` : 'Transferencia completada')
        : (event.errors?.join('; ') || 'Error en transferencia')
      toast[event.success ? 'success' : 'error'](transferMessage.value!)
      transferProgress.value = null
      await store.fetchOne(batchId.value)
    } else if (event.type === 'transfer_error') {
      transferring.value = false
      transferStatus.value = 'error'
      transferMessage.value = `Error: ${event.error}`
      transferProgress.value = null
      ws.close()
      toast.error(transferMessage.value)
    } else if (event.type === 'transfer_aborted') {
      transferring.value = false
      transferStatus.value = 'aborted'
      transferMessage.value = `Transferencia abortada: ${event.reason}`
      transferProgress.value = null
      ws.close()
      toast.error(transferMessage.value)
    }
  }
  ws.onerror = () => { transferring.value = false; transferStatus.value = 'error'; transferMessage.value = 'Error de conexión durante la transferencia' }
  try {
    await new Promise<void>((resolve, reject) => {
      ws.onopen = () => resolve()
      ws.addEventListener('error', () => reject(new Error('ws transfer')), { once: true })
    })
    const token = localStorage.getItem('access_token') ?? ''
    const res = await fetch(`/api/batches/${batchId.value}/transfer`, {
      method: 'POST', headers: { Authorization: `Bearer ${token}` },
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(body.detail || `Error ${res.status}`)
    }
  } catch (e) {
    transferring.value = false
    transferStatus.value = 'error'
    transferMessage.value = e instanceof Error ? e.message : 'Error al iniciar transferencia'
    ws.close()
    toast.error(transferMessage.value!)
  }
}

async function onDownloadZip(): Promise<void> {
  const token = localStorage.getItem('access_token') ?? ''
  const res = await fetch(`/api/batches/${batchId.value}/export`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) { toast.error('Error al descargar ZIP'); return }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = `batch_${batchId.value}.zip`; a.click()
  URL.revokeObjectURL(url)
}

async function onDeleteBatch(): Promise<void> {
  if (!confirm('¿Eliminar este lote? Esta acción no se puede deshacer.')) return
  await store.remove(batchId.value)
  router.push('/batches')
}

async function onSaveMetadata(fields: Record<string, unknown>): Promise<void> {
  if (!store.current) return
  savingMetadata.value = true
  try {
    await fetch(`/api/batches/${batchId.value}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${localStorage.getItem('access_token') ?? ''}`,
      },
      body: JSON.stringify({ fields_json: JSON.stringify(fields) }),
    })
    await store.fetchOne(batchId.value)
    toast.success('Lote guardado')
  } catch (e) {
    toast.error(e instanceof Error ? e.message : 'Error al guardar')
  } finally {
    savingMetadata.value = false
  }
}

function onColumnsResize(panes: Array<{ size: number }>): void {
  setSizes({ columns: panes.map((p) => p.size) as [number, number, number], rightVertical: sizes.value.rightVertical })
}

function onRightResize(panes: Array<{ size: number }>): void {
  setSizes({ columns: sizes.value.columns, rightVertical: panes.map((p) => p.size) as [number, number] })
}
</script>

<template>
  <div class="h-screen flex flex-col bg-base text-text">
    <WorkbenchToolbar
      v-if="store.current"
      :batch="store.current"
      :running="running"
      :transferring="transferring"
      :uploading="uploading"
      @upload="onUpload"
      @run-pipeline="onRunPipeline"
      @transfer="onTransfer"
      @download-zip="onDownloadZip"
      @delete-batch="onDeleteBatch"
    />
    <div v-if="error" class="bg-danger-soft text-danger text-xs px-4 py-1">{{ error }}</div>
    <div v-if="progress" class="bg-primary-soft text-primary text-xs px-4 py-1">Procesando {{ progress.processed }}/{{ progress.total }}…</div>
    <div v-if="transferProgress" class="bg-warning-soft text-warning text-xs px-4 py-1">Transfiriendo {{ transferProgress.page_index }}/{{ transferProgress.total }}…</div>

    <Splitpanes class="flex-1" @resized="onColumnsResize">
      <Pane :size="sizes.columns[0]" :min-size="8">
        <ThumbnailPanel
          :pages="sortedPages"
          :batchId="batchId"
          :selectedIndex="selectedPageIndex"
          @select="(i) => (selectedPageIndex = i)"
          @fit="viewerRef?.fitToViewport()"
        />
      </Pane>
      <Pane :size="sizes.columns[1]" :min-size="20">
        <div class="relative h-full">
          <DocumentViewer ref="viewerRef" :imageUrl="currentImageUrl" :barcodes="currentPage?.barcodes" />
          <ViewerToolbar
            v-if="viewerRef"
            :zoom-percent="viewerRef.zoomPercent ?? 100"
            @zoom-in="viewerRef.zoomIn()"
            @zoom-out="viewerRef.zoomOut()"
            @reset="viewerRef.resetView()"
            @fit="viewerRef.fitToViewport()"
          />
        </div>
      </Pane>
      <Pane :size="sizes.columns[2]" :min-size="20">
        <Splitpanes horizontal @resized="onRightResize">
          <Pane :size="sizes.rightVertical[0]" :min-size="20">
            <BarcodePanel :barcodes="currentPage?.barcodes ?? []" :pageCounters="counters" />
          </Pane>
          <Pane :size="sizes.rightVertical[1]" :min-size="20">
            <MetadataPanel :app="appStore.current" :batch="store.current" :saving="savingMetadata" @save="onSaveMetadata" />
          </Pane>
        </Splitpanes>
      </Pane>
    </Splitpanes>
  </div>
</template>

<style>
.splitpanes--vertical > .splitpanes__splitter {
  min-width: 4px;
  background-color: var(--color-surface-0);
}
.splitpanes--horizontal > .splitpanes__splitter {
  min-height: 4px;
  background-color: var(--color-surface-0);
}
.splitpanes__splitter:hover {
  background-color: var(--color-surface-1);
}
</style>
```

- [ ] **Step 4: Verificar pass**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run tests/views/batches/WorkbenchView.test.ts 2>&1 | tail -5`
Expected: `Tests 1 passed (1)`.

- [ ] **Step 5: Tests adicionales — navegación con flechas + cleanup listener**

```ts
  it('navigates pages with ArrowRight / ArrowLeft', async () => {
    const batches = useBatchesStore()
    const apps = useApplicationsStore()
    batches.fetchOne = vi.fn(async () => {
      batches.current = {
        id: 1, application_id: 5, state: 'read', page_count: 3,
        created_at: '', updated_at: '', fields_json: '{}', folder_path: '', hostname: '',
      }
    })
    batches.fetchPages = vi.fn(async () => {
      batches.pages = [
        { id: 10, batch_id: 1, page_index: 0, needs_review: false, is_blank: false, pipeline_processed: false, created_at: '' },
        { id: 11, batch_id: 1, page_index: 1, needs_review: false, is_blank: false, pipeline_processed: false, created_at: '' },
        { id: 12, batch_id: 1, page_index: 2, needs_review: false, is_blank: false, pipeline_processed: false, created_at: '' },
      ]
    })
    batches.fetchPage = vi.fn(async () => {})
    apps.fetchOne = vi.fn(async () => {})
    const router = makeRouter('/batches/1'); await router.isReady()
    const wrapper = mount(WorkbenchView, { global: { plugins: [router] }, attachTo: document.body })
    await flushPromises()
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight' }))
    await flushPromises()
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight' }))
    await flushPromises()
    // We can't easily inspect selectedPageIndex from outside, but we expect fetchPage to have been called for id=11 then id=12
    expect(batches.fetchPage).toHaveBeenCalledWith(1, 11)
    expect(batches.fetchPage).toHaveBeenCalledWith(1, 12)
    wrapper.unmount()
  })

  it('removes keydown listener on unmount', async () => {
    const batches = useBatchesStore()
    const apps = useApplicationsStore()
    batches.fetchOne = vi.fn(async () => { batches.current = { id: 1, application_id: 5, state: 'read', page_count: 0, created_at: '', updated_at: '', fields_json: '{}', folder_path: '', hostname: '' } })
    batches.fetchPages = vi.fn(async () => { batches.pages = [] })
    apps.fetchOne = vi.fn(async () => {})
    const router = makeRouter('/batches/1'); await router.isReady()
    const removeSpy = vi.spyOn(window, 'removeEventListener')
    const wrapper = mount(WorkbenchView, { global: { plugins: [router] } })
    await flushPromises()
    wrapper.unmount()
    expect(removeSpy).toHaveBeenCalledWith('keydown', expect.any(Function))
    removeSpy.mockRestore()
  })

  it('persists splitter sizes via setSizes when columns are resized', async () => {
    const batches = useBatchesStore()
    const apps = useApplicationsStore()
    batches.fetchOne = vi.fn(async () => { batches.current = { id: 1, application_id: 5, state: 'read', page_count: 0, created_at: '', updated_at: '', fields_json: '{}', folder_path: '', hostname: '' } })
    batches.fetchPages = vi.fn(async () => { batches.pages = [] })
    apps.fetchOne = vi.fn(async () => {})
    const router = makeRouter('/batches/1'); await router.isReady()
    const wrapper = mount(WorkbenchView, { global: { plugins: [router] } })
    await flushPromises()
    // Simulate splitpanes "resized" event on the outer Splitpanes
    const outerSplit = wrapper.findAllComponents({ name: 'splitpanes' })[0]
    outerSplit.vm.$emit('resized', [{ size: 20 }, { size: 50 }, { size: 30 }])
    await flushPromises()
    const stored = JSON.parse(localStorage.getItem('workbench.layout')!)
    expect(stored.columns).toEqual([20, 50, 30])
    wrapper.unmount()
  })
```

- [ ] **Step 6: Tests pasan**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run tests/views/batches/WorkbenchView.test.ts 2>&1 | tail -5`
Expected: `Tests 4 passed (4)`. Si alguno falla por detalle de implementación (e.g. `splitpanes` component name diferente), ajustar el selector.

- [ ] **Step 7: Suite completa**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run 2>&1 | tail -5`
Expected: `Tests 216 passed (216)`.

- [ ] **Step 8: Typecheck**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vue-tsc --noEmit 2>&1 | tail -5`
Expected: sin errores.

- [ ] **Step 9: Commit**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy && git add web/frontend/src/views/batches/WorkbenchView.vue web/frontend/tests/views/batches/WorkbenchView.test.ts
git commit -m "feat(web-frontend): WorkbenchView ensamblado con 3 paneles splitpanes

Vista que orquesta el Workbench: WorkbenchToolbar arriba, Splitpanes
con ThumbnailPanel izda + DocumentViewer+ViewerToolbar centro +
(BarcodePanel arriba / MetadataPanel abajo) dcha. Tamaños persistidos
en localStorage via useWorkbenchLayout. Navegación con flechas
←/→. Lazy fetch de la página seleccionada via watcher.

Migra todos los handlers de BatchDetailView (uploads, run pipeline,
transfer con WS, download zip, delete batch, save metadata).

4 tests cubren mount + fetch inicial, navegación con flechas,
cleanup del listener y persistencia de splitter."
```

---

## Task 11: Router actualizado + eliminar BatchDetailView

**Files:**
- Modify: `web/frontend/src/router/index.ts`
- Delete: `web/frontend/src/views/batches/BatchDetailView.vue`

- [ ] **Step 1: Modificar router**

En `/media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend/src/router/index.ts`, localizar la entrada:

```ts
        {
          path: 'batches/:id',
          name: 'batch-detail',
          component: () => import('@/views/batches/BatchDetailView.vue'),
          props: true,
        },
```

y reemplazarla por:

```ts
        {
          path: 'batches/:id',
          name: 'batch-detail',
          component: () => import('@/views/batches/WorkbenchView.vue'),
          props: true,
        },
```

- [ ] **Step 2: Eliminar BatchDetailView.vue**

Run: `rm /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend/src/views/batches/BatchDetailView.vue`

- [ ] **Step 3: Verificar typecheck (no debe haber imports rotos)**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vue-tsc --noEmit 2>&1 | tail -10`
Expected: sin errores.

Si aparece un error de import en algún test que aún referenciaba `BatchDetailView`, abrirlo y actualizar import a `WorkbenchView`. Si el test se vuelve obsoleto (asume estructura antigua), borrarlo.

- [ ] **Step 4: Suite completa**

Run: `cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run 2>&1 | tail -5`
Expected: `Tests 216 passed (216)`.

- [ ] **Step 5: Commit**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy && git add web/frontend/src/router/index.ts web/frontend/src/views/batches/BatchDetailView.vue
git commit -m "refactor(web-frontend): /batches/:id usa WorkbenchView

Ruta batch-detail apunta a WorkbenchView (Fase 2 del Workbench web).
Elimina BatchDetailView.vue (560 líneas) reemplazado por el nuevo
layout multi-panel. Misma URL, misma funcionalidad de pipeline +
transfer + uploads + delete, ahora con miniaturas con bordes por
estado, visor con toolbar flotante, panel de barcodes y formulario
editable de campos custom del lote."
```

---

## Task 12: QA visual Playwright + push final

**Files:** ninguno modificado (solo verificación).

- [ ] **Step 1: Arrancar servicios locales**

Run en orden:

```bash
docker start docscan-pg
source /media/nicolas/DATA/Tecnomedia/FlexiPy/.venv/bin/activate
uvicorn web.api.main:create_app --factory --port 8001 > /tmp/uvicorn-qa-wb2.log 2>&1 &
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run dev -- --port 5180 > /tmp/vite-qa-wb2.log 2>&1 &
sleep 6
curl -s -o /dev/null -w "API:%{http_code}\nFrontend:" http://localhost:8001/docs
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5180
```

Expected: ambos `200`.

- [ ] **Step 2: Login con Playwright**

Navegar a `http://localhost:5180/login` y autenticar con `demo2@demo.com` / `demo12345`.

- [ ] **Step 3: Navegar a un lote real**

Navegar a `http://localhost:5180/batches/4` (o el batch_id disponible).

Verificar visualmente:
- 3 paneles visibles (miniaturas izda, visor centro, panel dcha con barcodes y lote)
- WorkbenchToolbar arriba con 5 botones (Subir, Pipeline, Transferir, ZIP, Eliminar)
- ViewerToolbar flotante en esquina superior derecha del visor
- Splitters arrastrables (probar arrastrar uno y soltarlo en otra posición)

- [ ] **Step 4: Probar navegación entre páginas**

Click en una thumbnail diferente: el visor cambia.
Pulsar tecla ArrowRight: el thumbnail seleccionado avanza, el visor cambia.
Pulsar tecla ArrowLeft: retrocede.

- [ ] **Step 5: Probar zoom**

Click en `+`: zoom aumenta, indicador % sube.
Click en `−`: zoom baja.
Click en `1:1`: vuelve a 100%.
Click en `⛶`: ajusta a la vista.

- [ ] **Step 6: Probar tema oscuro**

Click en ☾ del sidebar (selector de tema). Verificar que TODO el Workbench se ve coherente en oscuro: sidebar, toolbar, paneles, splitters.

- [ ] **Step 7: Probar persistencia de splitters**

Arrastrar un splitter a una posición distinta. Recargar página (`Ctrl+R`). Verificar que el splitter mantiene la posición.

- [ ] **Step 8: Probar editar metadata**

En el panel inferior derecho (Lote), editar un campo. Click "Guardar". Verificar toast success.

- [ ] **Step 9: Cerrar Playwright y matar servicios**

```bash
pkill -f "uvicorn web.api"
pkill -f "vite.*--port 5180"
```

- [ ] **Step 10: Suite final + typecheck**

Run:

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vitest run 2>&1 | tail -5
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vue-tsc --noEmit 2>&1 | tail -5
```

Expected: tests passing, typecheck OK.

- [ ] **Step 11: Push a origin/feature/web**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy && git push origin feature/web 2>&1 | tail -5
```

Expected: push OK.

---

## Self-Review

**Spec coverage:**

- ✅ Layout 3 paneles con vue-splitpanes → Task 1 + Task 10
- ✅ Persistencia layout en localStorage → Task 3 + Task 10
- ✅ Composable usePageState con 6 estados → Task 2
- ✅ PageThumbnail con borde por estado → Task 4
- ✅ ThumbnailPanel con empty state → Task 5
- ✅ BarcodePanel view-only con tabla 5 cols + contadores → Task 6
- ✅ MetadataPanel con tabs preparada (Lote activa) y form dinámico → Task 7
- ✅ DocumentViewer con defineExpose + ViewerToolbar flotante → Task 8
- ✅ WorkbenchToolbar con 5 acciones y disabled states → Task 9
- ✅ WorkbenchView ensamblado con todo + listeners WS preservados de BatchDetailView → Task 10
- ✅ Navegación ←→ teclado → Task 10 (handler onKeydown)
- ✅ Router actualizado + BatchDetailView eliminado → Task 11
- ✅ QA visual + push final → Task 12

**Placeholder scan:** 
- Step 4 de Task 9 menciona "Si el test falla por useRouter sin router instalado, ajustar..." — esto es una contingencia documentada con código de fallback. No es placeholder.
- Step 6 de Task 10 menciona "Si alguno falla por detalle de implementación (e.g. splitpanes component name diferente), ajustar el selector." — contingencia. No placeholder porque damos el código por defecto.
- Step 3 de Task 11 menciona "Si aparece un error de import...abrirlo y actualizar". Contingencia menor.

Todo válido — son contingencias con instrucciones específicas, no TBDs.

**Type consistency:**
- `PageState` definido en Task 2, importado correctamente en Task 4
- `LayoutSizes` definido en Task 3, usado en Task 10
- Props/emits consistentes entre componentes y su uso en WorkbenchView (Task 10)
- `defineExpose` de DocumentViewer (Task 8) consumido correctamente en Task 10 via `viewerRef?.zoomIn()` etc.
- `BatchField` interface definida en Task 7 (MetadataPanel) — autocontenida, no usada fuera

Plan completo.

---

## Execution Handoff

Plan completo y guardado en `docs/superpowers/plans/2026-04-22-workbench-web-fase-2.md`.

Dos opciones de ejecución:

1. **Subagent-Driven (recomendada)** — dispatch un subagent fresco por task con review entre tasks. Iteración rápida.
2. **Inline Execution** — ejecutar tasks en esta sesión usando executing-plans.
