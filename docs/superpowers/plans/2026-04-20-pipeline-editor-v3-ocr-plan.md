# Editor de Pipeline v3 — OcrStep — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir crear, editar, reordenar y eliminar pasos de tipo `OcrStep` desde el editor web con paridad completa frente al desktop (motor, idiomas, full_page, window).

**Architecture:** Frontend puro — un widget `TagInput` para chips de idiomas + un form `OcrStepForm.vue` que ensambla los 4 campos del dataclass reutilizando los widgets genéricos de v2 (`EnumField`, `BooleanField`, `WindowField`). Integración mínima en `AddStepMenu`, `PipelineStepDrawer`, `PipelineStepRow` y el store. Cero cambios en backend.

**Tech Stack:** Vue 3 + TypeScript + Pinia + Tailwind CSS + vitest + `@vue/test-utils` + `jsdom`.

**Spec:** `docs/superpowers/specs/2026-04-20-pipeline-editor-v3-ocr-design.md`

---

## Estructura de ficheros

### Nuevos

| Fichero | Responsabilidad |
| --- | --- |
| `web/frontend/src/components/pipeline/fields/TagInput.vue` | Input de chips: Enter/coma añade, ✕ elimina, duplicados ignorados. |
| `web/frontend/src/components/pipeline/forms/OcrStepForm.vue` | Form principal con Engine (EnumField), idiomas (TagInput), full_page (BooleanField), WindowField. |
| `web/frontend/tests/fields/TagInput.test.ts` | Tests del widget (5). |
| `web/frontend/tests/OcrStepForm.test.ts` | Tests del form (4). |

### Modificados

| Fichero | Cambio |
| --- | --- |
| `web/frontend/src/api/types-pipeline.ts` | Añadir `OcrStep` al union `PipelineStep`. |
| `web/frontend/src/stores/pipeline.ts` | Rama `ocr` en `defaultsFor`. |
| `web/frontend/src/components/pipeline/AddStepMenu.vue` | Promover `ocr` a opción activa con badge v3. |
| `web/frontend/src/components/pipeline/PipelineStepDrawer.vue` | Rama `ocr` en el switch, extender `isEditable` y `canSave`. |
| `web/frontend/src/components/pipeline/PipelineStepRow.vue` | Summary para `ocr`. |
| `web/frontend/tests/stores/pipeline.store.test.ts` | 1 test nuevo para `addStep('ocr')`. |

---

## Task 1: Tipo `OcrStep` en el dominio TypeScript

**Files:**
- Modify: `web/frontend/src/api/types-pipeline.ts`

- [ ] **Step 1: Añadir la interfaz `OcrStep`**

Abrir el fichero y añadir debajo de la interfaz `ImageOpStep` (tras la línea `window: [number, number, number, number] | null }`) y antes de `GenericStep`:

```ts
export interface OcrStep extends BasePipelineStep {
  type: 'ocr'
  engine: 'rapidocr' | 'easyocr' | 'tesseract'
  languages: string[]
  full_page: boolean
  window: [number, number, number, number] | null
}
```

- [ ] **Step 2: Actualizar el union `PipelineStep`**

Cambiar:
```ts
export type PipelineStep = BarcodeStep | ImageOpStep | GenericStep
```

Por:
```ts
export type PipelineStep = BarcodeStep | ImageOpStep | OcrStep | GenericStep
```

- [ ] **Step 3: Verificar tests existentes**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run
```

Expected: 44/44 PASS (sin cambios respecto a v2).

- [ ] **Step 4: Commit**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy
git add web/frontend/src/api/types-pipeline.ts
git commit -m "feat(web-frontend): añadir tipo OcrStep al dominio TS"
```

---

## Task 2: Widget `TagInput`

**Files:**
- Create: `web/frontend/src/components/pipeline/fields/TagInput.vue`
- Create: `web/frontend/tests/fields/TagInput.test.ts`

- [ ] **Step 1: Escribir el test**

Crear `web/frontend/tests/fields/TagInput.test.ts` con este EXACTO contenido:

```ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import TagInput from '@/components/pipeline/fields/TagInput.vue'

describe('TagInput', () => {
  it('añade un chip al pulsar Enter', async () => {
    const wrapper = mount(TagInput, {
      props: { modelValue: [], label: 'Idiomas' },
    })
    const input = wrapper.find('input')
    await input.setValue('es')
    await input.trigger('keydown', { key: 'Enter' })
    const events = wrapper.emitted('update:modelValue')
    expect(events![events!.length - 1]).toEqual([['es']])
  })

  it('añade un chip al escribir coma', async () => {
    const wrapper = mount(TagInput, {
      props: { modelValue: ['es'], label: 'Idiomas' },
    })
    const input = wrapper.find('input')
    await input.setValue('en,')
    // El componente detecta la coma en el valor y dispara el add
    const events = wrapper.emitted('update:modelValue')
    expect(events![events!.length - 1]).toEqual([['es', 'en']])
  })

  it('elimina un chip al pulsar su botón ✕', async () => {
    const wrapper = mount(TagInput, {
      props: { modelValue: ['es', 'en'], label: 'Idiomas' },
    })
    const removeButtons = wrapper.findAll('button[aria-label^="Eliminar"]')
    expect(removeButtons.length).toBe(2)
    await removeButtons[0].trigger('click')
    const events = wrapper.emitted('update:modelValue')
    expect(events![events!.length - 1]).toEqual([['en']])
  })

  it('ignora duplicados', async () => {
    const wrapper = mount(TagInput, {
      props: { modelValue: ['es'], label: 'Idiomas' },
    })
    const input = wrapper.find('input')
    await input.setValue('es')
    await input.trigger('keydown', { key: 'Enter' })
    const events = wrapper.emitted('update:modelValue')
    // No debe emitir porque es duplicado
    expect(events).toBeFalsy()
  })

  it('ignora texto vacío tras trim', async () => {
    const wrapper = mount(TagInput, {
      props: { modelValue: [], label: 'Idiomas' },
    })
    const input = wrapper.find('input')
    await input.setValue('   ')
    await input.trigger('keydown', { key: 'Enter' })
    const events = wrapper.emitted('update:modelValue')
    expect(events).toBeFalsy()
  })

  it('renderiza el label', () => {
    const wrapper = mount(TagInput, {
      props: { modelValue: [], label: 'Idiomas soportados' },
    })
    expect(wrapper.text()).toContain('Idiomas soportados')
  })
})
```

- [ ] **Step 2: Run test — MUST fail**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run TagInput
```

Expected: FAIL con `Cannot find module '@/components/pipeline/fields/TagInput.vue'`.

- [ ] **Step 3: Crear el componente**

Crear `web/frontend/src/components/pipeline/fields/TagInput.vue` con este EXACTO contenido:

```vue
<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  modelValue: string[]
  label: string
  placeholder?: string
  help?: string
  disabled?: boolean
}>()

const emit = defineEmits<{ 'update:modelValue': [value: string[]] }>()

const draft = ref('')

function addTag(raw: string) {
  const tag = raw.trim()
  if (!tag) return
  if (props.modelValue.includes(tag)) return
  emit('update:modelValue', [...props.modelValue, tag])
}

function onKeydown(e: KeyboardEvent) {
  if (e.key !== 'Enter') return
  e.preventDefault()
  addTag(draft.value)
  draft.value = ''
}

// Detectar coma en el input y dividir
watch(draft, (val) => {
  if (!val.includes(',')) return
  const parts = val.split(',')
  const complete = parts.slice(0, -1)
  for (const p of complete) addTag(p)
  draft.value = parts[parts.length - 1]
})

function removeTag(idx: number) {
  const next = props.modelValue.slice()
  next.splice(idx, 1)
  emit('update:modelValue', next)
}
</script>

<template>
  <div>
    <label class="block text-[11px] uppercase tracking-wide text-subtext font-medium mb-1">
      {{ label }}
      <span v-if="help" class="normal-case text-subtext">· {{ help }}</span>
    </label>
    <input
      v-model="draft"
      type="text"
      :placeholder="placeholder"
      :disabled="disabled"
      @keydown="onKeydown"
      class="w-full border rounded-md px-2 py-1.5 text-sm"
    />
    <div v-if="modelValue.length" class="flex flex-wrap gap-1.5 mt-2">
      <span
        v-for="(tag, idx) in modelValue"
        :key="tag"
        class="inline-flex items-center gap-1 px-2 py-0.5 bg-surface-0 border border-surface-0 rounded-full text-xs"
      >
        {{ tag }}
        <button
          type="button"
          :aria-label="`Eliminar ${tag}`"
          class="hover:text-danger text-subtext"
          @click="removeTag(idx)"
        >
          ✕
        </button>
      </span>
    </div>
  </div>
</template>
```

- [ ] **Step 4: Run test — must pass (6/6)**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run TagInput
```

Expected: PASS 6/6.

- [ ] **Step 5: Commit**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy
git add web/frontend/src/components/pipeline/fields/TagInput.vue web/frontend/tests/fields/TagInput.test.ts
git commit -m "feat(web-frontend): widget TagInput con chips add/remove"
```

---

## Task 3: `defaultsFor('ocr')` en el store

**Files:**
- Modify: `web/frontend/src/stores/pipeline.ts`
- Modify: `web/frontend/tests/stores/pipeline.store.test.ts`

- [ ] **Step 1: Añadir el test**

Abrir `web/frontend/tests/stores/pipeline.store.test.ts` y añadir al final del bloque `describe('usePipelineStore', ...)`, antes de su `})`:

```ts
  it('addStep ocr devuelve un step con defaults correctos', () => {
    const store = usePipelineStore()
    const step = store.addStep('ocr')

    expect(step.type).toBe('ocr')
    expect(step.enabled).toBe(true)
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const s = step as any
    expect(s.engine).toBe('rapidocr')
    expect(s.languages).toEqual(['es'])
    expect(s.full_page).toBe(true)
    expect(s.window).toBeNull()
    expect(step.id).toBeTruthy()
  })
```

- [ ] **Step 2: Run test — MUST fail**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run pipeline.store
```

Expected: FAIL porque `engine` es undefined en el step devuelto.

- [ ] **Step 3: Modificar el store**

Editar `web/frontend/src/stores/pipeline.ts`.

Cambiar el import:

```ts
import type { PipelineStep, StepType, BarcodeStep, ImageOpStep, OcrStep } from '@/api/types-pipeline'
```

Añadir la rama `ocr` en `defaultsFor` después de la rama `image_op` y antes del `return { type, enabled: true }`:

```ts
  if (type === 'ocr') {
    const defaults: Omit<OcrStep, 'id'> = {
      type: 'ocr',
      enabled: true,
      engine: 'rapidocr',
      languages: ['es'],
      full_page: true,
      window: null,
    }
    return defaults
  }
```

- [ ] **Step 4: Run test — must pass**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run pipeline.store
```

Expected: PASS (10/10 — los 9 anteriores + el nuevo).

- [ ] **Step 5: Commit**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy
git add web/frontend/src/stores/pipeline.ts web/frontend/tests/stores/pipeline.store.test.ts
git commit -m "feat(web-frontend): defaultsFor ocr en el store"
```

---

## Task 4: `OcrStepForm.vue`

**Files:**
- Create: `web/frontend/src/components/pipeline/forms/OcrStepForm.vue`
- Create: `web/frontend/tests/OcrStepForm.test.ts`

- [ ] **Step 1: Escribir el test**

Crear `web/frontend/tests/OcrStepForm.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import OcrStepForm from '@/components/pipeline/forms/OcrStepForm.vue'
import type { OcrStep } from '@/api/types-pipeline'

function defaultStep(): OcrStep {
  return {
    id: 'test-1',
    type: 'ocr',
    enabled: true,
    engine: 'rapidocr',
    languages: ['es'],
    full_page: true,
    window: null,
  }
}

describe('OcrStepForm', () => {
  it('renderiza el selector de motor con 3 opciones', () => {
    const wrapper = mount(OcrStepForm, {
      props: { modelValue: defaultStep() },
    })
    const selects = wrapper.findAll('select')
    // Primer (y único) select es el engine
    expect(selects.length).toBeGreaterThanOrEqual(1)
    const engineSelect = selects[0]
    expect(engineSelect.findAll('option')).toHaveLength(3)
  })

  it('al cambiar el motor emite el step con nuevo engine', async () => {
    const wrapper = mount(OcrStepForm, {
      props: { modelValue: defaultStep() },
    })
    await wrapper.find('select').setValue('tesseract')
    const events = wrapper.emitted('update:modelValue')
    const last = events![events!.length - 1][0] as OcrStep
    expect(last.engine).toBe('tesseract')
  })

  it('al añadir un idioma emite el step con lista actualizada', async () => {
    const wrapper = mount(OcrStepForm, {
      props: { modelValue: defaultStep() },
    })
    const input = wrapper.find('input[type=text]')
    await input.setValue('en')
    await input.trigger('keydown', { key: 'Enter' })
    const events = wrapper.emitted('update:modelValue')
    const last = events![events!.length - 1][0] as OcrStep
    expect(last.languages).toEqual(['es', 'en'])
  })

  it('toggle full_page invierte el booleano emitido', async () => {
    const wrapper = mount(OcrStepForm, {
      props: { modelValue: defaultStep() },
    })
    const checkboxes = wrapper.findAll('input[type=checkbox]')
    // [0]: activo, [1]: página completa (ambos true por default)
    await checkboxes[1].setValue(false)
    const events = wrapper.emitted('update:modelValue')
    const last = events![events!.length - 1][0] as OcrStep
    expect(last.full_page).toBe(false)
  })
})
```

- [ ] **Step 2: Run test — MUST fail**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run OcrStepForm
```

Expected: FAIL por módulo no encontrado.

- [ ] **Step 3: Crear el componente**

Crear `web/frontend/src/components/pipeline/forms/OcrStepForm.vue`:

```vue
<script setup lang="ts">
import type { OcrStep } from '@/api/types-pipeline'

import EnumField from '../fields/EnumField.vue'
import BooleanField from '../fields/BooleanField.vue'
import TagInput from '../fields/TagInput.vue'
import WindowField from '../WindowField.vue'

const props = defineProps<{ modelValue: OcrStep }>()
const emit = defineEmits<{ 'update:modelValue': [step: OcrStep] }>()

function patch(update: Partial<OcrStep>) {
  emit('update:modelValue', { ...props.modelValue, ...update })
}

const ENGINE_OPTIONS = [
  { value: 'rapidocr', label: 'rapidocr (rápido, offline)' },
  { value: 'easyocr', label: 'easyocr (alta precisión, PyTorch)' },
  { value: 'tesseract', label: 'tesseract (ligero, ISO 639-3)' },
]
</script>

<template>
  <div class="space-y-4">
    <!-- Activo -->
    <div class="flex items-center gap-2">
      <input
        id="ocr_enabled"
        type="checkbox"
        :checked="modelValue.enabled"
        @change="(e) => patch({ enabled: (e.target as HTMLInputElement).checked })"
      />
      <label for="ocr_enabled" class="text-sm">Activo</label>
    </div>

    <!-- Motor -->
    <EnumField
      label="Motor"
      :model-value="modelValue.engine"
      :options="ENGINE_OPTIONS"
      help="rapidocr/easyocr usan ISO 639-1 (es, en). tesseract usa ISO 639-3 (spa, eng)."
      @update:model-value="(v) => patch({ engine: v as OcrStep['engine'] })"
    />

    <!-- Idiomas -->
    <TagInput
      label="Idiomas"
      placeholder="es, en, fr"
      help="Los códigos varían según el motor."
      :model-value="modelValue.languages"
      @update:model-value="(v) => patch({ languages: v })"
    />

    <!-- Full page -->
    <BooleanField
      label="Procesar página completa"
      help="Si se desactiva, se usará la región indicada abajo."
      :model-value="modelValue.full_page"
      @update:model-value="(v) => patch({ full_page: v })"
    />

    <!-- Window (ROI) -->
    <WindowField
      :model-value="modelValue.window"
      @update:model-value="(v) => patch({ window: v })"
    />
  </div>
</template>
```

- [ ] **Step 4: Run test — must pass (4/4)**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run OcrStepForm
```

Expected: PASS 4/4.

También ejecutar la suite completa:

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run
```

Expected: ~55/55 PASS (44 anteriores + 10 nuevos hasta aquí + los 4 del form).

- [ ] **Step 5: Commit**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy
git add web/frontend/src/components/pipeline/forms/OcrStepForm.vue web/frontend/tests/OcrStepForm.test.ts
git commit -m "feat(web-frontend): OcrStepForm con motor, idiomas, full_page y ROI"
```

---

## Task 5: Habilitar `ocr` en `AddStepMenu` e integrar en el drawer

**Files:**
- Modify: `web/frontend/src/components/pipeline/AddStepMenu.vue`
- Modify: `web/frontend/src/components/pipeline/PipelineStepDrawer.vue`

- [ ] **Step 1: Editar `AddStepMenu.vue`**

Localizar el bloque actual (lines 45-55 aprox), que debe contener la lista "Próximamente" con `['ocr', 'script']`. Reemplazar:

```vue
      <div
        v-for="type in ['ocr', 'script']"
        :key="type"
        class="w-full text-left px-3 py-2 text-sm text-subtext flex items-center gap-2 cursor-not-allowed"
      >
        <span class="w-2 h-2 rounded-full bg-gray-300"></span>
        <span>{{ type }}</span>
      </div>
```

Por:

```vue
      <button
        @click="pick('ocr')"
        class="w-full text-left px-3 py-2 text-sm hover:bg-surface-0 flex items-center gap-2"
      >
        <span class="w-2 h-2 rounded-full bg-amber-500"></span>
        <span>OCR</span>
        <span class="ml-auto text-xs text-subtext">v3</span>
      </button>
      <div
        class="w-full text-left px-3 py-2 text-sm text-subtext flex items-center gap-2 cursor-not-allowed"
      >
        <span class="w-2 h-2 rounded-full bg-gray-300"></span>
        <span>script</span>
      </div>
```

Dejar el bloque del `border-t` y `Próximamente` tal cual (sigue siendo correcto porque aún falta `script`).

- [ ] **Step 2: Editar `PipelineStepDrawer.vue`**

Abrir `web/frontend/src/components/pipeline/PipelineStepDrawer.vue`.

Actualizar el import:

```ts
import type { PipelineStep, BarcodeStep, ImageOpStep, OcrStep } from '@/api/types-pipeline'
import BarcodeStepForm from './forms/BarcodeStepForm.vue'
import ImageOpStepForm from './forms/ImageOpStepForm.vue'
import OcrStepForm from './forms/OcrStepForm.vue'
```

Actualizar `isEditable`:

```ts
const isEditable = computed(
  () =>
    props.step?.type === 'barcode' ||
    props.step?.type === 'image_op' ||
    props.step?.type === 'ocr',
)
```

Nota: `canSave` ya contempla todos los tipos (devuelve `true` por defecto); no hay campo bloqueante específico para `ocr`, por lo que no hay que modificar `canSave`.

En el template, añadir la rama `ocr` en el switch. Localizar:

```vue
        <ImageOpStepForm
          v-else-if="draft?.type === 'image_op'"
          :model-value="draft as ImageOpStep"
          @update:model-value="onDraftUpdate"
        />
        <div v-else class="text-sm text-subtext bg-amber-50 border border-amber-200 rounded p-3">
```

Insertar ANTES del `<div v-else>`:

```vue
        <OcrStepForm
          v-else-if="draft?.type === 'ocr'"
          :model-value="draft as OcrStep"
          @update:model-value="onDraftUpdate"
        />
```

- [ ] **Step 3: Verificar suite completa**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run
```

Expected: Todos los tests siguen pasando.

- [ ] **Step 4: Verificar typecheck**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npx vue-tsc --noEmit 2>&1 | tail -10
```

Expected: 0 errores relacionados con estos ficheros.

- [ ] **Step 5: Commit**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy
git add web/frontend/src/components/pipeline/AddStepMenu.vue web/frontend/src/components/pipeline/PipelineStepDrawer.vue
git commit -m "feat(web-frontend): habilitar ocr en menú y drawer"
```

---

## Task 6: Resumen `ocr` en `PipelineStepRow`

**Files:**
- Modify: `web/frontend/src/components/pipeline/PipelineStepRow.vue`

- [ ] **Step 1: Extender el `<script setup>`**

Abrir `web/frontend/src/components/pipeline/PipelineStepRow.vue`.

Actualizar el import:

```ts
import type { PipelineStep, BarcodeStep, ImageOpStep, OcrStep } from '@/api/types-pipeline'
```

En el computed `summary`, añadir la rama `ocr` antes del último `return 'Editable desde configurador de escritorio'`:

```ts
  if (s.type === 'ocr') {
    const oc = s as OcrStep
    const langs = oc.languages.length ? oc.languages.join(',') : 'sin idiomas'
    const area = oc.full_page
      ? 'página completa'
      : oc.window
        ? `región ${oc.window.join(',')}`
        : 'sin región'
    return `OCR (${oc.engine}) · ${langs} · ${area}`
  }
```

El bloque `summary` completo resultante debe ser:

```ts
const summary = computed(() => {
  const s = props.step
  if (s.type === 'barcode') {
    const bc = s as BarcodeStep
    const region = bc.window ? 'región custom' : 'página completa'
    const symbols = bc.symbologies.length ? bc.symbologies.join(',') : 'todas'
    return `${bc.engine} · ${region} · ${symbols}`
  }
  if (s.type === 'image_op') {
    const io = s as ImageOpStep
    if (!io.op) return 'Operación de imagen (sin configurar)'
    const meta = IMAGE_OP_CATALOG.find((op) => op.name === io.op)
    const label = meta?.label ?? io.op
    const paramsTxt = formatParams(io.params)
    const windowTxt = io.window
      ? ` · región ${io.window.join(',')}`
      : ''
    return paramsTxt
      ? `${label} · ${paramsTxt}${windowTxt}`
      : `${label}${windowTxt}`
  }
  if (s.type === 'ocr') {
    const oc = s as OcrStep
    const langs = oc.languages.length ? oc.languages.join(',') : 'sin idiomas'
    const area = oc.full_page
      ? 'página completa'
      : oc.window
        ? `región ${oc.window.join(',')}`
        : 'sin región'
    return `OCR (${oc.engine}) · ${langs} · ${area}`
  }
  return 'Editable desde configurador de escritorio'
})
```

- [ ] **Step 2: Ejecutar tests**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run
```

Expected: Todos siguen pasando.

- [ ] **Step 3: Commit**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy
git add web/frontend/src/components/pipeline/PipelineStepRow.vue
git commit -m "feat(web-frontend): resumen compacto para ocr en la fila"
```

---

## Task 7: Verificación manual end-to-end

**Objetivo:** probar el flujo completo contra backend real, incluyendo persistencia y round-trip.

- [ ] **Step 1: Arrancar el stack local**

```bash
# Terminal 1
docker start docscan-pg

# Terminal 2
source .venv/bin/activate
uvicorn web.api.main:create_app --factory --reload --port 8001

# Terminal 3
cd web/frontend && npm run dev
```

Recuerda: el dev server puede arrancar en 5173 o 5174 si ese puerto está ocupado.

- [ ] **Step 2: Login**

Abrir el navegador en la URL del dev server. Login con `demo2@demo.com` / `demo12345`.

- [ ] **Step 3: Abrir la app Pipeline Test v1 (id 8)**

Navegar → Aplicaciones → Pipeline Test v1 → Editar pipeline.

- [ ] **Step 4: Añadir un OCR paso con engine=tesseract, idiomas=[spa, eng], full_page=false**

1. Pulsar "+ Añadir step" → "OCR" (badge v3).
2. Cambiar Motor a "tesseract".
3. En Idiomas, escribir `spa` → Enter; luego `eng` → Enter. Verificar que aparecen 2 chips.
4. Probar añadir `spa` de nuevo — no debe aparecer duplicado.
5. Probar eliminar `eng` con ✕ — debe desaparecer. Volver a añadirlo.
6. Desactivar "Procesar página completa".
7. Activar "Aplicar solo a una región" en WindowField, valores por defecto (0,0,100,100).
8. Guardar.

Verificar que la fila muestra algo como: `OCR (tesseract) · spa,eng · región 0,0,100,100`.

- [ ] **Step 5: Añadir otro OCR paso con defaults (rapidocr + es + full_page)**

Añadir otro step, sin cambiar nada salvo guardar. La fila debe mostrar: `OCR (rapidocr) · es · página completa`.

- [ ] **Step 6: Verificar persistencia en BD**

```bash
docker exec docscan-pg psql -U docscan -d docscan -c \
  "SELECT id, name, LEFT(pipeline_json::text, 400) FROM applications WHERE id = 8;"
```

Buscar en el JSON devuelto las entradas `"type":"ocr"` con los `engine`, `languages`, `full_page` y `window` correctos.

- [ ] **Step 7: Verificar round-trip**

Recargar la página (`F5`). Los pasos deben volver a aparecer con sus resúmenes correctos. Editar el primer OCR; debe mostrar los chips (spa, eng), el motor tesseract y el toggle desactivado.

- [ ] **Step 8: Parar los servicios**

Ctrl+C en las 2 terminales de uvicorn y npm.

---

## Verificación final y push

- [ ] **Step 1: Suite completa**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy/web/frontend && npm run test -- --run
```

Expected: ~55 tests PASS (44 previos + 6 TagInput + 1 store + 4 OcrStepForm = 55). Cero fallos.

- [ ] **Step 2: Push al remote**

```bash
cd /media/nicolas/DATA/Tecnomedia/FlexiPy
git push origin feature/web
```

- [ ] **Step 3: Informe del día**

Crear `docs/progreso_2026-04-20_v3.md` (o añadir una sección al informe del día si ya se ha creado uno para esta fecha), siguiendo el patrón del skill `progreso-doc`.

---

## Fuera de scope (recordatorio)

- Validación de códigos de idioma por motor.
- Preview del resultado OCR.
- Editor de `ScriptStep` — sub-proyecto 4 con CodeMirror.
