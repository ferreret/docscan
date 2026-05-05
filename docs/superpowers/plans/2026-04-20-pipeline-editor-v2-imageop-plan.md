# Editor de Pipeline v2 — ImageOpStep — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir crear, editar, reordenar y eliminar pasos de tipo `ImageOpStep` desde el editor web con paridad completa frente al desktop (24 operaciones soportadas) y UX tipado sin texto libre.

**Architecture:** Frontend puro — un catálogo TypeScript con las 24 operaciones + 5 widgets genéricos de campo + un form `ImageOpStepForm.vue` que ensambla dinámicamente los fields según la op elegida. Integración mínima en `AddStepMenu`, `PipelineStepDrawer`, `PipelineStepRow` y el store. Cero cambios en backend (la API `PUT /api/applications/{id}/pipeline` de v1 ya acepta `ImageOpStep`).

**Tech Stack:** Vue 3 + TypeScript + Pinia + Tailwind CSS + vitest + `@vue/test-utils` + `jsdom`.

**Spec:** `docs/superpowers/specs/2026-04-20-pipeline-editor-v2-imageop-design.md`

---

## Estructura de ficheros

### Nuevos

| Fichero | Responsabilidad |
| --- | --- |
| `web/frontend/src/api/image-op-catalog.ts` | 24 entradas con metadata (name, label, category, description, fields) + `CATEGORY_LABELS`. |
| `web/frontend/src/components/pipeline/fields/NumberField.vue` | Input numérico con clamp a min/max. |
| `web/frontend/src/components/pipeline/fields/EnumField.vue` | `<select>` simple con opciones tipadas. |
| `web/frontend/src/components/pipeline/fields/BooleanField.vue` | Checkbox con label a la derecha. |
| `web/frontend/src/components/pipeline/fields/PointField.vue` | 2 NumberField (X, Y) lado a lado; emite `{x, y}`. |
| `web/frontend/src/components/pipeline/fields/ColorField.vue` | 3 NumberField (R, G, B 0-255) + swatch de color; emite `[r,g,b]`. |
| `web/frontend/src/components/pipeline/WindowField.vue` | Toggle + 4 NumberField (X, Y, W, H); emite tupla o `null`. |
| `web/frontend/src/components/pipeline/forms/ImageOpStepForm.vue` | Form principal: selector agrupado + fields dinámicos + WindowField. |
| `web/frontend/tests/image-op-catalog.test.ts` | Paridad con IMAGE_OPS del backend + forma del catálogo. |
| `web/frontend/tests/fields/NumberField.test.ts` | Tests del widget NumberField. |
| `web/frontend/tests/fields/EnumField.test.ts` | Tests del widget EnumField. |
| `web/frontend/tests/fields/BooleanField.test.ts` | Tests del widget BooleanField. |
| `web/frontend/tests/fields/PointField.test.ts` | Tests del widget PointField. |
| `web/frontend/tests/fields/ColorField.test.ts` | Tests del widget ColorField. |
| `web/frontend/tests/fields/WindowField.test.ts` | Tests del widget WindowField. |
| `web/frontend/tests/ImageOpStepForm.test.ts` | Tests del form (carga, cambio de op, Resize modo, Rotate enum). |

### Modificados

| Fichero | Cambio |
| --- | --- |
| `web/frontend/src/api/types-pipeline.ts` | Añadir `ImageOpStep` al union `PipelineStep`. |
| `web/frontend/src/stores/pipeline.ts` | Rama `image_op` en `defaultsFor`. |
| `web/frontend/src/components/pipeline/AddStepMenu.vue` | Habilitar opción "Operación de imagen". |
| `web/frontend/src/components/pipeline/PipelineStepDrawer.vue` | Rama `image_op` en el switch del form. |
| `web/frontend/src/components/pipeline/PipelineStepRow.vue` | Resumen compacto para `image_op`. |
| `web/frontend/tests/stores/pipeline.store.test.ts` | Tests de `addStep('image_op')`. |

---

## Task 1: Tipo `ImageOpStep` en el dominio TypeScript

**Files:**
- Modify: `web/frontend/src/api/types-pipeline.ts`

- [ ] **Step 1: Abrir el fichero y añadir la interfaz `ImageOpStep`**

Añadir debajo de la interfaz `BarcodeStep` y antes de `GenericStep`:

```ts
export interface ImageOpStep extends BasePipelineStep {
  type: 'image_op'
  op: string
  params: Record<string, unknown>
  window: [number, number, number, number] | null
}
```

Actualizar el union `PipelineStep` para incluir el nuevo tipo:

```ts
export type PipelineStep = BarcodeStep | ImageOpStep | GenericStep
```

- [ ] **Step 2: Verificar que los tests actuales siguen pasando**

Run:
```bash
cd web/frontend && npm run test -- --run
```

Expected: todos los tests del store de pipeline siguen pasando (8/8).

- [ ] **Step 3: Commit**

```bash
git add web/frontend/src/api/types-pipeline.ts
git commit -m "feat(web-frontend): añadir tipo ImageOpStep al dominio TS"
```

---

## Task 2: Catálogo de operaciones

**Files:**
- Create: `web/frontend/src/api/image-op-catalog.ts`
- Create: `web/frontend/tests/image-op-catalog.test.ts`

- [ ] **Step 1: Escribir el test de paridad y forma**

Crear `web/frontend/tests/image-op-catalog.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import {
  IMAGE_OP_CATALOG,
  CATEGORY_LABELS,
  type Category,
} from '@/api/image-op-catalog'

// Lista esperada, sincronizada manualmente con app/services/image_pipeline.py::IMAGE_OPS.
// Si el backend añade/quita ops, actualizar esta lista y el catálogo a la vez.
const EXPECTED_OPS = [
  'AutoDeskew',
  'ConvertTo1Bpp',
  'Crop',
  'CropBlackBorders',
  'CropWhiteBorders',
  'FloodFill',
  'FxDespeckle',
  'FxDilate',
  'FxEqualizeIntensity',
  'FxErode',
  'FxGrayscale',
  'FxNegative',
  'KeepChannel',
  'RemoveChannel',
  'RemoveHolePunch',
  'RemoveLines',
  'Resize',
  'Rotate',
  'RotateAngle',
  'ScaleChannel',
  'SetBrightness',
  'SetContrast',
  'SetResolution',
  'SwapColor',
] as const

describe('IMAGE_OP_CATALOG', () => {
  it('contiene exactamente las 24 operaciones esperadas', () => {
    const names = IMAGE_OP_CATALOG.map((op) => op.name).sort()
    expect(names).toEqual([...EXPECTED_OPS].sort())
  })

  it('cada operación tiene label, description y category', () => {
    for (const op of IMAGE_OP_CATALOG) {
      expect(op.label).toBeTruthy()
      expect(op.description).toBeTruthy()
      expect(CATEGORY_LABELS[op.category]).toBeTruthy()
    }
  })

  it('cada field tiene default definido y los enums tienen opciones', () => {
    for (const op of IMAGE_OP_CATALOG) {
      for (const f of op.fields) {
        expect(f.default).toBeDefined()
        if (f.type === 'enum') {
          expect(f.options).toBeDefined()
          expect(f.options!.length).toBeGreaterThan(0)
        }
      }
    }
  })

  it('los fields numéricos con min y max cumplen min <= max', () => {
    for (const op of IMAGE_OP_CATALOG) {
      for (const f of op.fields) {
        if (
          (f.type === 'int' || f.type === 'float') &&
          f.min !== undefined &&
          f.max !== undefined
        ) {
          expect(f.min).toBeLessThanOrEqual(f.max)
        }
      }
    }
  })

  it('CATEGORY_LABELS cubre todas las categorías usadas', () => {
    const usedCategories = new Set(IMAGE_OP_CATALOG.map((op) => op.category))
    for (const cat of usedCategories) {
      expect(CATEGORY_LABELS[cat as Category]).toBeTruthy()
    }
  })
})
```

- [ ] **Step 2: Run test — debe fallar (módulo no existe)**

Run:
```bash
cd web/frontend && npm run test -- --run image-op-catalog
```

Expected: FAIL con `Cannot find module '@/api/image-op-catalog'`.

- [ ] **Step 3: Crear el catálogo con las 24 operaciones**

Crear `web/frontend/src/api/image-op-catalog.ts`:

```ts
// Catálogo de operaciones de imagen (ImageOp). Fuente de verdad del frontend.
// Sincronizado manualmente con app/services/image_pipeline.py::IMAGE_OPS.

export type FieldType =
  | 'int' | 'float' | 'enum' | 'bool' | 'point' | 'color'

export type Category =
  | 'geometry' | 'color' | 'cleanup'
  | 'morphology' | 'channels' | 'effects'

export interface FieldSchema {
  key: string
  type: FieldType
  label: string
  default: unknown
  min?: number
  max?: number
  step?: number
  options?: { value: string | number; label: string }[]
  help?: string
}

export interface OpSchema {
  name: string
  label: string
  category: Category
  description: string
  fields: FieldSchema[]
}

export const CATEGORY_LABELS: Record<Category, string> = {
  geometry: 'Geometría',
  color: 'Color y tono',
  cleanup: 'Limpieza',
  morphology: 'Morfología',
  channels: 'Canales',
  effects: 'Efectos',
}

export const IMAGE_OP_CATALOG: OpSchema[] = [
  // --- Geometría ---
  {
    name: 'AutoDeskew',
    label: 'Corregir inclinación',
    category: 'geometry',
    description: 'Detecta y corrige la inclinación de la imagen automáticamente.',
    fields: [],
  },
  {
    name: 'Crop',
    label: 'Recortar región',
    category: 'geometry',
    description: 'Recorta una región rectangular definida por X, Y, ancho y alto.',
    fields: [
      { key: 'x', type: 'int', label: 'X', default: 0, min: 0 },
      { key: 'y', type: 'int', label: 'Y', default: 0, min: 0 },
      { key: 'w', type: 'int', label: 'Ancho', default: 100, min: 1 },
      { key: 'h', type: 'int', label: 'Alto', default: 100, min: 1 },
    ],
  },
  {
    name: 'Resize',
    label: 'Redimensionar',
    category: 'geometry',
    description: 'Cambia el tamaño por escala o a un tamaño absoluto.',
    fields: [
      { key: 'scale', type: 'float', label: 'Escala', default: 1.0, min: 0.01, max: 10, step: 0.1 },
      { key: 'width', type: 'int', label: 'Ancho (px)', default: 800, min: 1 },
      { key: 'height', type: 'int', label: 'Alto (px)', default: 600, min: 1 },
    ],
  },
  {
    name: 'Rotate',
    label: 'Rotar 90° / 180° / 270°',
    category: 'geometry',
    description: 'Rota la imagen en incrementos de 90 grados.',
    fields: [
      {
        key: 'degrees',
        type: 'enum',
        label: 'Grados',
        default: 90,
        options: [
          { value: 90, label: '90°' },
          { value: 180, label: '180°' },
          { value: 270, label: '270°' },
        ],
      },
    ],
  },
  {
    name: 'RotateAngle',
    label: 'Rotar ángulo libre',
    category: 'geometry',
    description: 'Rota un ángulo arbitrario en grados.',
    fields: [
      { key: 'angle', type: 'float', label: 'Ángulo (°)', default: 0, min: -360, max: 360, step: 0.1 },
    ],
  },

  // --- Color y tono ---
  {
    name: 'FxGrayscale',
    label: 'Convertir a escala de grises',
    category: 'color',
    description: 'Convierte la imagen a escala de grises.',
    fields: [],
  },
  {
    name: 'FxNegative',
    label: 'Invertir (negativo)',
    category: 'color',
    description: 'Invierte los colores de la imagen.',
    fields: [],
  },
  {
    name: 'FxEqualizeIntensity',
    label: 'Ecualizar intensidad',
    category: 'color',
    description: 'Ecualiza el histograma de intensidad.',
    fields: [],
  },
  {
    name: 'SetBrightness',
    label: 'Ajustar brillo',
    category: 'color',
    description: 'Suma un valor constante al brillo (-100 a 100).',
    fields: [
      { key: 'value', type: 'int', label: 'Valor', default: 0, min: -100, max: 100 },
    ],
  },
  {
    name: 'SetContrast',
    label: 'Ajustar contraste',
    category: 'color',
    description: 'Multiplica la intensidad por un factor.',
    fields: [
      { key: 'factor', type: 'float', label: 'Factor', default: 1.0, min: 0, max: 3, step: 0.1 },
    ],
  },

  // --- Limpieza ---
  {
    name: 'ConvertTo1Bpp',
    label: 'Convertir a 1 bit',
    category: 'cleanup',
    description: 'Binariza la imagen con un umbral configurable.',
    fields: [
      { key: 'threshold', type: 'int', label: 'Umbral', default: 128, min: 0, max: 255 },
    ],
  },
  {
    name: 'RemoveLines',
    label: 'Eliminar líneas',
    category: 'cleanup',
    description: 'Elimina líneas horizontales, verticales o ambas.',
    fields: [
      {
        key: 'direction',
        type: 'enum',
        label: 'Dirección',
        default: 'HV',
        options: [
          { value: 'H', label: 'Horizontales' },
          { value: 'V', label: 'Verticales' },
          { value: 'HV', label: 'Ambas' },
        ],
      },
    ],
  },
  {
    name: 'FxDespeckle',
    label: 'Despeckle (mediana)',
    category: 'cleanup',
    description: 'Elimina ruido con un filtro de mediana.',
    fields: [
      { key: 'kernel_size', type: 'int', label: 'Tamaño kernel (impar)', default: 3, min: 1, max: 21 },
    ],
  },
  {
    name: 'CropWhiteBorders',
    label: 'Recortar bordes blancos',
    category: 'cleanup',
    description: 'Elimina bordes blancos alrededor del contenido.',
    fields: [
      { key: 'margin', type: 'int', label: 'Margen (px)', default: 5, min: 0 },
    ],
  },
  {
    name: 'CropBlackBorders',
    label: 'Recortar bordes negros',
    category: 'cleanup',
    description: 'Elimina bordes negros alrededor del contenido.',
    fields: [
      { key: 'margin', type: 'int', label: 'Margen (px)', default: 5, min: 0 },
    ],
  },
  {
    name: 'RemoveHolePunch',
    label: 'Eliminar perforaciones',
    category: 'cleanup',
    description: 'Detecta y tapa marcas circulares de perforadora.',
    fields: [
      { key: 'min_radius', type: 'int', label: 'Radio mínimo (px)', default: 10, min: 1 },
      { key: 'max_radius', type: 'int', label: 'Radio máximo (px)', default: 30, min: 1 },
    ],
  },

  // --- Morfología ---
  {
    name: 'FxDilate',
    label: 'Dilatar',
    category: 'morphology',
    description: 'Dilatación morfológica (engrosa).',
    fields: [
      { key: 'kernel_size', type: 'int', label: 'Tamaño kernel', default: 3, min: 1, max: 15 },
      { key: 'iterations', type: 'int', label: 'Iteraciones', default: 1, min: 1, max: 10 },
    ],
  },
  {
    name: 'FxErode',
    label: 'Erosionar',
    category: 'morphology',
    description: 'Erosión morfológica (adelgaza).',
    fields: [
      { key: 'kernel_size', type: 'int', label: 'Tamaño kernel', default: 3, min: 1, max: 15 },
      { key: 'iterations', type: 'int', label: 'Iteraciones', default: 1, min: 1, max: 10 },
    ],
  },

  // --- Canales ---
  {
    name: 'KeepChannel',
    label: 'Mantener canal',
    category: 'channels',
    description: 'Extrae un canal individual (R, G o B).',
    fields: [
      {
        key: 'channel',
        type: 'enum',
        label: 'Canal',
        default: 'R',
        options: [
          { value: 'R', label: 'Rojo (R)' },
          { value: 'G', label: 'Verde (G)' },
          { value: 'B', label: 'Azul (B)' },
        ],
      },
    ],
  },
  {
    name: 'RemoveChannel',
    label: 'Eliminar canal',
    category: 'channels',
    description: 'Pone a cero un canal (R, G o B).',
    fields: [
      {
        key: 'channel',
        type: 'enum',
        label: 'Canal',
        default: 'R',
        options: [
          { value: 'R', label: 'Rojo (R)' },
          { value: 'G', label: 'Verde (G)' },
          { value: 'B', label: 'Azul (B)' },
        ],
      },
    ],
  },
  {
    name: 'ScaleChannel',
    label: 'Escalar canal',
    category: 'channels',
    description: 'Multiplica un canal por un factor.',
    fields: [
      {
        key: 'channel',
        type: 'enum',
        label: 'Canal',
        default: 'R',
        options: [
          { value: 'R', label: 'Rojo (R)' },
          { value: 'G', label: 'Verde (G)' },
          { value: 'B', label: 'Azul (B)' },
        ],
      },
      { key: 'factor', type: 'float', label: 'Factor', default: 1.0, min: 0, max: 2, step: 0.1 },
    ],
  },

  // --- Efectos ---
  {
    name: 'FloodFill',
    label: 'Rellenar desde punto',
    category: 'effects',
    description: 'Relleno por inundación desde un punto de origen.',
    fields: [
      { key: 'x', type: 'int', label: 'Origen X', default: 0, min: 0 },
      { key: 'y', type: 'int', label: 'Origen Y', default: 0, min: 0 },
      { key: 'color', type: 'color', label: 'Color', default: [255, 255, 255] },
    ],
  },
  {
    name: 'SwapColor',
    label: 'Intercambiar color',
    category: 'effects',
    description: 'Sustituye un color por otro con tolerancia.',
    fields: [
      { key: 'from', type: 'color', label: 'Color origen', default: [0, 0, 0] },
      { key: 'to', type: 'color', label: 'Color destino', default: [255, 255, 255] },
      { key: 'tolerance', type: 'int', label: 'Tolerancia', default: 10, min: 0, max: 50 },
    ],
  },
  {
    name: 'SetResolution',
    label: 'Fijar resolución (DPI)',
    category: 'effects',
    description: 'Marca la resolución para el guardado (no redimensiona).',
    fields: [],
  },
]
```

- [ ] **Step 4: Run test — debe pasar**

Run:
```bash
cd web/frontend && npm run test -- --run image-op-catalog
```

Expected: PASS (5 tests del catálogo).

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/api/image-op-catalog.ts web/frontend/tests/image-op-catalog.test.ts
git commit -m "feat(web-frontend): catálogo TS con las 24 operaciones de imagen"
```

---

## Task 3: `NumberField` widget

**Files:**
- Create: `web/frontend/src/components/pipeline/fields/NumberField.vue`
- Create: `web/frontend/tests/fields/NumberField.test.ts`

- [ ] **Step 1: Escribir el test**

Crear `web/frontend/tests/fields/NumberField.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import NumberField from '@/components/pipeline/fields/NumberField.vue'

describe('NumberField', () => {
  it('emite update:modelValue con el número al cambiar el input', async () => {
    const wrapper = mount(NumberField, {
      props: { modelValue: 5, label: 'Cantidad' },
    })
    await wrapper.find('input').setValue('12')
    const events = wrapper.emitted('update:modelValue')
    expect(events).toBeTruthy()
    expect(events![events!.length - 1]).toEqual([12])
  })

  it('clampa al máximo cuando se excede', async () => {
    const wrapper = mount(NumberField, {
      props: { modelValue: 50, label: 'X', max: 100 },
    })
    await wrapper.find('input').setValue('999')
    const events = wrapper.emitted('update:modelValue')
    expect(events![events!.length - 1]).toEqual([100])
  })

  it('clampa al mínimo cuando se baja de él', async () => {
    const wrapper = mount(NumberField, {
      props: { modelValue: 0, label: 'X', min: 0 },
    })
    await wrapper.find('input').setValue('-5')
    const events = wrapper.emitted('update:modelValue')
    expect(events![events!.length - 1]).toEqual([0])
  })

  it('convierte a entero cuando integer=true', async () => {
    const wrapper = mount(NumberField, {
      props: { modelValue: 0, label: 'X', integer: true },
    })
    await wrapper.find('input').setValue('3.7')
    const events = wrapper.emitted('update:modelValue')
    expect(events![events!.length - 1]).toEqual([3])
  })

  it('renderiza el label', () => {
    const wrapper = mount(NumberField, {
      props: { modelValue: 0, label: 'Brillo' },
    })
    expect(wrapper.text()).toContain('Brillo')
  })
})
```

- [ ] **Step 2: Run test — debe fallar**

Run:
```bash
cd web/frontend && npm run test -- --run NumberField
```

Expected: FAIL por módulo no encontrado.

- [ ] **Step 3: Implementar el componente**

Crear `web/frontend/src/components/pipeline/fields/NumberField.vue`:

```vue
<script setup lang="ts">
const props = defineProps<{
  modelValue: number
  label: string
  help?: string
  disabled?: boolean
  min?: number
  max?: number
  step?: number
  integer?: boolean
}>()

const emit = defineEmits<{ 'update:modelValue': [value: number] }>()

function onInput(e: Event) {
  const raw = (e.target as HTMLInputElement).value
  if (raw === '') return
  let n = props.integer ? parseInt(raw, 10) : Number(raw)
  if (Number.isNaN(n)) return
  if (props.min !== undefined && n < props.min) n = props.min
  if (props.max !== undefined && n > props.max) n = props.max
  emit('update:modelValue', n)
}
</script>

<template>
  <div>
    <label class="block text-[11px] uppercase tracking-wide text-subtext font-medium mb-1">
      {{ label }}
      <span v-if="help" class="normal-case text-subtext">· {{ help }}</span>
    </label>
    <input
      type="number"
      :value="modelValue"
      :min="min"
      :max="max"
      :step="step ?? (integer ? 1 : undefined)"
      :disabled="disabled"
      @input="onInput"
      class="w-full border rounded-md px-2 py-1.5 text-sm"
    />
  </div>
</template>
```

- [ ] **Step 4: Run test — debe pasar**

Run:
```bash
cd web/frontend && npm run test -- --run NumberField
```

Expected: PASS (5/5).

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/components/pipeline/fields/NumberField.vue web/frontend/tests/fields/NumberField.test.ts
git commit -m "feat(web-frontend): widget NumberField con clamp y modo entero"
```

---

## Task 4: `EnumField` widget

**Files:**
- Create: `web/frontend/src/components/pipeline/fields/EnumField.vue`
- Create: `web/frontend/tests/fields/EnumField.test.ts`

- [ ] **Step 1: Escribir el test**

Crear `web/frontend/tests/fields/EnumField.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import EnumField from '@/components/pipeline/fields/EnumField.vue'

const OPTIONS = [
  { value: 90, label: '90°' },
  { value: 180, label: '180°' },
  { value: 270, label: '270°' },
]

describe('EnumField', () => {
  it('emite update:modelValue con el value del option elegido', async () => {
    const wrapper = mount(EnumField, {
      props: { modelValue: 90, label: 'Grados', options: OPTIONS },
    })
    await wrapper.find('select').setValue('180')
    const events = wrapper.emitted('update:modelValue')
    expect(events![events!.length - 1]).toEqual([180])
  })

  it('conserva el tipo string para valores string', async () => {
    const wrapper = mount(EnumField, {
      props: {
        modelValue: 'HV',
        label: 'Dirección',
        options: [
          { value: 'H', label: 'Horizontal' },
          { value: 'V', label: 'Vertical' },
          { value: 'HV', label: 'Ambas' },
        ],
      },
    })
    await wrapper.find('select').setValue('V')
    const events = wrapper.emitted('update:modelValue')
    expect(events![events!.length - 1]).toEqual(['V'])
  })

  it('renderiza todas las opciones con su label', () => {
    const wrapper = mount(EnumField, {
      props: { modelValue: 90, label: 'Grados', options: OPTIONS },
    })
    expect(wrapper.findAll('option')).toHaveLength(3)
    expect(wrapper.text()).toContain('90°')
    expect(wrapper.text()).toContain('180°')
    expect(wrapper.text()).toContain('270°')
  })
})
```

- [ ] **Step 2: Run test — debe fallar**

Run:
```bash
cd web/frontend && npm run test -- --run EnumField
```

Expected: FAIL.

- [ ] **Step 3: Implementar el componente**

Crear `web/frontend/src/components/pipeline/fields/EnumField.vue`:

```vue
<script setup lang="ts">
interface Option {
  value: string | number
  label: string
}

const props = defineProps<{
  modelValue: string | number
  label: string
  options: Option[]
  help?: string
  disabled?: boolean
}>()

const emit = defineEmits<{ 'update:modelValue': [value: string | number] }>()

function onChange(e: Event) {
  const raw = (e.target as HTMLSelectElement).value
  // Detectar si el option original era number y coercer
  const original = props.options.find((o) => String(o.value) === raw)
  emit('update:modelValue', original ? original.value : raw)
}
</script>

<template>
  <div>
    <label class="block text-[11px] uppercase tracking-wide text-subtext font-medium mb-1">
      {{ label }}
      <span v-if="help" class="normal-case text-subtext">· {{ help }}</span>
    </label>
    <select
      :value="modelValue"
      :disabled="disabled"
      @change="onChange"
      class="w-full border rounded-md px-2 py-1.5 text-sm"
    >
      <option v-for="opt in options" :key="opt.value" :value="opt.value">
        {{ opt.label }}
      </option>
    </select>
  </div>
</template>
```

- [ ] **Step 4: Run test — debe pasar**

Run:
```bash
cd web/frontend && npm run test -- --run EnumField
```

Expected: PASS (3/3).

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/components/pipeline/fields/EnumField.vue web/frontend/tests/fields/EnumField.test.ts
git commit -m "feat(web-frontend): widget EnumField con preservación de tipo"
```

---

## Task 5: `BooleanField` widget

**Files:**
- Create: `web/frontend/src/components/pipeline/fields/BooleanField.vue`
- Create: `web/frontend/tests/fields/BooleanField.test.ts`

- [ ] **Step 1: Escribir el test**

Crear `web/frontend/tests/fields/BooleanField.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BooleanField from '@/components/pipeline/fields/BooleanField.vue'

describe('BooleanField', () => {
  it('emite true cuando se marca', async () => {
    const wrapper = mount(BooleanField, {
      props: { modelValue: false, label: 'Activo' },
    })
    await wrapper.find('input[type=checkbox]').setValue(true)
    const events = wrapper.emitted('update:modelValue')
    expect(events![events!.length - 1]).toEqual([true])
  })

  it('emite false cuando se desmarca', async () => {
    const wrapper = mount(BooleanField, {
      props: { modelValue: true, label: 'Activo' },
    })
    await wrapper.find('input[type=checkbox]').setValue(false)
    const events = wrapper.emitted('update:modelValue')
    expect(events![events!.length - 1]).toEqual([false])
  })

  it('renderiza el label', () => {
    const wrapper = mount(BooleanField, {
      props: { modelValue: false, label: 'Deskew automático' },
    })
    expect(wrapper.text()).toContain('Deskew automático')
  })
})
```

- [ ] **Step 2: Run test — debe fallar**

Run:
```bash
cd web/frontend && npm run test -- --run BooleanField
```

Expected: FAIL.

- [ ] **Step 3: Implementar el componente**

Crear `web/frontend/src/components/pipeline/fields/BooleanField.vue`:

```vue
<script setup lang="ts">
defineProps<{
  modelValue: boolean
  label: string
  help?: string
  disabled?: boolean
}>()

const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()

function onChange(e: Event) {
  emit('update:modelValue', (e.target as HTMLInputElement).checked)
}
</script>

<template>
  <div class="flex items-center gap-2">
    <input
      type="checkbox"
      :checked="modelValue"
      :disabled="disabled"
      @change="onChange"
    />
    <label class="text-sm">
      {{ label }}
      <span v-if="help" class="text-subtext text-xs">· {{ help }}</span>
    </label>
  </div>
</template>
```

- [ ] **Step 4: Run test — debe pasar**

Run:
```bash
cd web/frontend && npm run test -- --run BooleanField
```

Expected: PASS (3/3).

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/components/pipeline/fields/BooleanField.vue web/frontend/tests/fields/BooleanField.test.ts
git commit -m "feat(web-frontend): widget BooleanField"
```

---

## Task 6: `PointField` widget

**Files:**
- Create: `web/frontend/src/components/pipeline/fields/PointField.vue`
- Create: `web/frontend/tests/fields/PointField.test.ts`

- [ ] **Step 1: Escribir el test**

Crear `web/frontend/tests/fields/PointField.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import PointField from '@/components/pipeline/fields/PointField.vue'

describe('PointField', () => {
  it('emite {x, y} al cambiar X', async () => {
    const wrapper = mount(PointField, {
      props: { modelValue: { x: 10, y: 20 }, label: 'Origen' },
    })
    const inputs = wrapper.findAll('input[type=number]')
    await inputs[0].setValue('50')
    const events = wrapper.emitted('update:modelValue')
    expect(events![events!.length - 1]).toEqual([{ x: 50, y: 20 }])
  })

  it('emite {x, y} al cambiar Y', async () => {
    const wrapper = mount(PointField, {
      props: { modelValue: { x: 10, y: 20 }, label: 'Origen' },
    })
    const inputs = wrapper.findAll('input[type=number]')
    await inputs[1].setValue('99')
    const events = wrapper.emitted('update:modelValue')
    expect(events![events!.length - 1]).toEqual([{ x: 10, y: 99 }])
  })

  it('renderiza el label principal', () => {
    const wrapper = mount(PointField, {
      props: { modelValue: { x: 0, y: 0 }, label: 'Origen del relleno' },
    })
    expect(wrapper.text()).toContain('Origen del relleno')
  })
})
```

- [ ] **Step 2: Run test — debe fallar**

Run:
```bash
cd web/frontend && npm run test -- --run PointField
```

Expected: FAIL.

- [ ] **Step 3: Implementar el componente**

Crear `web/frontend/src/components/pipeline/fields/PointField.vue`:

```vue
<script setup lang="ts">
import NumberField from './NumberField.vue'

const props = defineProps<{
  modelValue: { x: number; y: number }
  label: string
  help?: string
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: { x: number; y: number }]
}>()

function setX(x: number) {
  emit('update:modelValue', { x, y: props.modelValue.y })
}
function setY(y: number) {
  emit('update:modelValue', { x: props.modelValue.x, y })
}
</script>

<template>
  <div>
    <label class="block text-[11px] uppercase tracking-wide text-subtext font-medium mb-1">
      {{ label }}
      <span v-if="help" class="normal-case text-subtext">· {{ help }}</span>
    </label>
    <div class="grid grid-cols-2 gap-2">
      <NumberField
        :model-value="modelValue.x"
        label="X"
        :disabled="disabled"
        :min="0"
        integer
        @update:model-value="setX"
      />
      <NumberField
        :model-value="modelValue.y"
        label="Y"
        :disabled="disabled"
        :min="0"
        integer
        @update:model-value="setY"
      />
    </div>
  </div>
</template>
```

- [ ] **Step 4: Run test — debe pasar**

Run:
```bash
cd web/frontend && npm run test -- --run PointField
```

Expected: PASS (3/3).

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/components/pipeline/fields/PointField.vue web/frontend/tests/fields/PointField.test.ts
git commit -m "feat(web-frontend): widget PointField (X, Y)"
```

---

## Task 7: `ColorField` widget

**Files:**
- Create: `web/frontend/src/components/pipeline/fields/ColorField.vue`
- Create: `web/frontend/tests/fields/ColorField.test.ts`

- [ ] **Step 1: Escribir el test**

Crear `web/frontend/tests/fields/ColorField.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ColorField from '@/components/pipeline/fields/ColorField.vue'

describe('ColorField', () => {
  it('emite [r, g, b] al cambiar un canal', async () => {
    const wrapper = mount(ColorField, {
      props: { modelValue: [10, 20, 30], label: 'Color' },
    })
    const inputs = wrapper.findAll('input[type=number]')
    await inputs[0].setValue('200')
    const events = wrapper.emitted('update:modelValue')
    expect(events![events!.length - 1]).toEqual([[200, 20, 30]])
  })

  it('clampa cada canal a 255', async () => {
    const wrapper = mount(ColorField, {
      props: { modelValue: [0, 0, 0], label: 'Color' },
    })
    const inputs = wrapper.findAll('input[type=number]')
    await inputs[2].setValue('999')
    const events = wrapper.emitted('update:modelValue')
    expect(events![events!.length - 1]).toEqual([[0, 0, 255]])
  })

  it('clampa cada canal a 0 si es negativo', async () => {
    const wrapper = mount(ColorField, {
      props: { modelValue: [100, 100, 100], label: 'Color' },
    })
    const inputs = wrapper.findAll('input[type=number]')
    await inputs[1].setValue('-50')
    const events = wrapper.emitted('update:modelValue')
    expect(events![events!.length - 1]).toEqual([[100, 0, 100]])
  })

  it('renderiza el label', () => {
    const wrapper = mount(ColorField, {
      props: { modelValue: [0, 0, 0], label: 'Color origen' },
    })
    expect(wrapper.text()).toContain('Color origen')
  })
})
```

- [ ] **Step 2: Run test — debe fallar**

Run:
```bash
cd web/frontend && npm run test -- --run ColorField
```

Expected: FAIL.

- [ ] **Step 3: Implementar el componente**

Crear `web/frontend/src/components/pipeline/fields/ColorField.vue`:

```vue
<script setup lang="ts">
import { computed } from 'vue'
import NumberField from './NumberField.vue'

const props = defineProps<{
  modelValue: [number, number, number]
  label: string
  help?: string
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: [number, number, number]]
}>()

function setChannel(idx: 0 | 1 | 2, v: number) {
  const next: [number, number, number] = [...props.modelValue] as [number, number, number]
  next[idx] = v
  emit('update:modelValue', next)
}

const swatch = computed(
  () => `rgb(${props.modelValue[0]}, ${props.modelValue[1]}, ${props.modelValue[2]})`,
)
</script>

<template>
  <div>
    <label class="block text-[11px] uppercase tracking-wide text-subtext font-medium mb-1">
      {{ label }}
      <span v-if="help" class="normal-case text-subtext">· {{ help }}</span>
    </label>
    <div class="flex items-end gap-2">
      <div class="grid grid-cols-3 gap-2 flex-1">
        <NumberField
          :model-value="modelValue[0]"
          label="R"
          :min="0"
          :max="255"
          integer
          :disabled="disabled"
          @update:model-value="(v) => setChannel(0, v)"
        />
        <NumberField
          :model-value="modelValue[1]"
          label="G"
          :min="0"
          :max="255"
          integer
          :disabled="disabled"
          @update:model-value="(v) => setChannel(1, v)"
        />
        <NumberField
          :model-value="modelValue[2]"
          label="B"
          :min="0"
          :max="255"
          integer
          :disabled="disabled"
          @update:model-value="(v) => setChannel(2, v)"
        />
      </div>
      <div
        class="w-10 h-10 rounded border border-surface-0 shrink-0"
        :style="{ background: swatch }"
        aria-label="Muestra del color"
      ></div>
    </div>
  </div>
</template>
```

- [ ] **Step 4: Run test — debe pasar**

Run:
```bash
cd web/frontend && npm run test -- --run ColorField
```

Expected: PASS (4/4).

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/components/pipeline/fields/ColorField.vue web/frontend/tests/fields/ColorField.test.ts
git commit -m "feat(web-frontend): widget ColorField con swatch RGB"
```

---

## Task 8: `WindowField` widget

**Files:**
- Create: `web/frontend/src/components/pipeline/WindowField.vue`
- Create: `web/frontend/tests/fields/WindowField.test.ts`

- [ ] **Step 1: Escribir el test**

Crear `web/frontend/tests/fields/WindowField.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import WindowField from '@/components/pipeline/WindowField.vue'

describe('WindowField', () => {
  it('con modelValue=null muestra solo el toggle', () => {
    const wrapper = mount(WindowField, { props: { modelValue: null } })
    expect(wrapper.find('input[type=checkbox]').exists()).toBe(true)
    expect(wrapper.findAll('input[type=number]')).toHaveLength(0)
  })

  it('al activar el toggle emite [0, 0, 100, 100]', async () => {
    const wrapper = mount(WindowField, { props: { modelValue: null } })
    await wrapper.find('input[type=checkbox]').setValue(true)
    const events = wrapper.emitted('update:modelValue')
    expect(events![events!.length - 1]).toEqual([[0, 0, 100, 100]])
  })

  it('al desactivar el toggle emite null', async () => {
    const wrapper = mount(WindowField, {
      props: { modelValue: [5, 10, 50, 50] },
    })
    await wrapper.find('input[type=checkbox]').setValue(false)
    const events = wrapper.emitted('update:modelValue')
    expect(events![events!.length - 1]).toEqual([null])
  })

  it('con modelValue no-null renderiza 4 inputs numéricos', () => {
    const wrapper = mount(WindowField, {
      props: { modelValue: [5, 10, 50, 50] },
    })
    expect(wrapper.findAll('input[type=number]')).toHaveLength(4)
  })

  it('emite tupla actualizada al cambiar un campo', async () => {
    const wrapper = mount(WindowField, {
      props: { modelValue: [5, 10, 50, 50] },
    })
    const inputs = wrapper.findAll('input[type=number]')
    await inputs[2].setValue('200')
    const events = wrapper.emitted('update:modelValue')
    expect(events![events!.length - 1]).toEqual([[5, 10, 200, 50]])
  })
})
```

- [ ] **Step 2: Run test — debe fallar**

Run:
```bash
cd web/frontend && npm run test -- --run WindowField
```

Expected: FAIL.

- [ ] **Step 3: Implementar el componente**

Crear `web/frontend/src/components/pipeline/WindowField.vue`:

```vue
<script setup lang="ts">
import NumberField from './fields/NumberField.vue'

type Window = [number, number, number, number]

const props = defineProps<{
  modelValue: Window | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: Window | null]
}>()

function onToggle(e: Event) {
  const checked = (e.target as HTMLInputElement).checked
  emit('update:modelValue', checked ? [0, 0, 100, 100] : null)
}

function updateAt(idx: 0 | 1 | 2 | 3, v: number) {
  if (!props.modelValue) return
  const next: Window = [...props.modelValue] as Window
  next[idx] = v
  emit('update:modelValue', next)
}
</script>

<template>
  <div>
    <div class="flex items-center gap-2 mb-2">
      <input
        id="window_enabled"
        type="checkbox"
        :checked="modelValue !== null"
        @change="onToggle"
      />
      <label for="window_enabled" class="text-sm">
        Aplicar solo a una región
      </label>
    </div>
    <div v-if="modelValue" class="grid grid-cols-2 gap-2">
      <NumberField
        :model-value="modelValue[0]"
        label="X"
        :min="0"
        integer
        @update:model-value="(v) => updateAt(0, v)"
      />
      <NumberField
        :model-value="modelValue[1]"
        label="Y"
        :min="0"
        integer
        @update:model-value="(v) => updateAt(1, v)"
      />
      <NumberField
        :model-value="modelValue[2]"
        label="Ancho"
        :min="1"
        integer
        @update:model-value="(v) => updateAt(2, v)"
      />
      <NumberField
        :model-value="modelValue[3]"
        label="Alto"
        :min="1"
        integer
        @update:model-value="(v) => updateAt(3, v)"
      />
    </div>
  </div>
</template>
```

- [ ] **Step 4: Run test — debe pasar**

Run:
```bash
cd web/frontend && npm run test -- --run WindowField
```

Expected: PASS (5/5).

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/components/pipeline/WindowField.vue web/frontend/tests/fields/WindowField.test.ts
git commit -m "feat(web-frontend): widget WindowField (ROI rectangular)"
```

---

## Task 9: `defaultsFor('image_op')` en el store

**Files:**
- Modify: `web/frontend/src/stores/pipeline.ts`
- Modify: `web/frontend/tests/stores/pipeline.store.test.ts`

- [ ] **Step 1: Añadir el test al fichero del store**

Abrir `web/frontend/tests/stores/pipeline.store.test.ts` y añadir al final (antes del cierre del describe):

```ts
  it('addStep image_op devuelve un step con defaults correctos', () => {
    const store = usePipelineStore()
    const step = store.addStep('image_op')

    expect(step.type).toBe('image_op')
    expect(step.enabled).toBe(true)
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const s = step as any
    expect(s.op).toBe('')
    expect(s.params).toEqual({})
    expect(s.window).toBeNull()
    expect(step.id).toBeTruthy()
  })
```

- [ ] **Step 2: Run test — debe fallar**

Run:
```bash
cd web/frontend && npm run test -- --run pipeline.store
```

Expected: FAIL con `expect(step.type).toBe('image_op')` recibiendo posiblemente `image_op` pero `s.op` siendo `undefined`.

- [ ] **Step 3: Implementar la rama en `defaultsFor`**

Editar `web/frontend/src/stores/pipeline.ts`:

Cambiar el import:

```ts
import type { PipelineStep, StepType, BarcodeStep, ImageOpStep } from '@/api/types-pipeline'
```

Y `defaultsFor`:

```ts
function defaultsFor(type: StepType): Partial<PipelineStep> {
  if (type === 'barcode') {
    const defaults: Omit<BarcodeStep, 'id'> = {
      type: 'barcode',
      enabled: true,
      engine: 'motor1',
      symbologies: [],
      regex: '',
      regex_include_symbology: false,
      orientations: ['horizontal', 'vertical'],
      quality_threshold: 0,
      window: null,
    }
    return defaults
  }
  if (type === 'image_op') {
    const defaults: Omit<ImageOpStep, 'id'> = {
      type: 'image_op',
      enabled: true,
      op: '',
      params: {},
      window: null,
    }
    return defaults
  }
  // Otros tipos no son editables aún; no se construyen nuevos.
  return { type, enabled: true }
}
```

- [ ] **Step 4: Run test — debe pasar**

Run:
```bash
cd web/frontend && npm run test -- --run pipeline.store
```

Expected: PASS (9/9 — los 8 anteriores + el nuevo).

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/stores/pipeline.ts web/frontend/tests/stores/pipeline.store.test.ts
git commit -m "feat(web-frontend): defaultsFor image_op en el store"
```

---

## Task 10: `ImageOpStepForm.vue`

**Files:**
- Create: `web/frontend/src/components/pipeline/forms/ImageOpStepForm.vue`
- Create: `web/frontend/tests/ImageOpStepForm.test.ts`

- [ ] **Step 1: Escribir el test**

Crear `web/frontend/tests/ImageOpStepForm.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ImageOpStepForm from '@/components/pipeline/forms/ImageOpStepForm.vue'
import type { ImageOpStep } from '@/api/types-pipeline'

function emptyStep(): ImageOpStep {
  return {
    id: 'test-1',
    type: 'image_op',
    enabled: true,
    op: '',
    params: {},
    window: null,
  }
}

describe('ImageOpStepForm', () => {
  it('con op vacío solo renderiza el selector y no los fields', () => {
    const wrapper = mount(ImageOpStepForm, {
      props: { modelValue: emptyStep() },
    })
    const selects = wrapper.findAll('select')
    // Solo el selector de operación, no hay fields dinámicos
    expect(selects.length).toBeGreaterThanOrEqual(1)
    // No hay WindowField tampoco cuando op === ''
    expect(wrapper.find('label[for="window_enabled"]').exists()).toBe(false)
  })

  it('al elegir una op, emite step con params por defecto del schema', async () => {
    const wrapper = mount(ImageOpStepForm, {
      props: { modelValue: emptyStep() },
    })
    // El primer select es el de operación
    await wrapper.find('select').setValue('ConvertTo1Bpp')
    const events = wrapper.emitted('update:modelValue')
    expect(events).toBeTruthy()
    const last = events![events!.length - 1][0] as ImageOpStep
    expect(last.op).toBe('ConvertTo1Bpp')
    expect(last.params).toEqual({ threshold: 128 })
  })

  it('op sin fields (FxGrayscale) no renderiza field dinámico', async () => {
    const step: ImageOpStep = {
      ...emptyStep(),
      op: 'FxGrayscale',
      params: {},
    }
    const wrapper = mount(ImageOpStepForm, { props: { modelValue: step } })
    // Solo hay 1 select: el selector de op (FxGrayscale no tiene enum field)
    const selects = wrapper.findAll('select')
    expect(selects).toHaveLength(1)
  })

  it('op con enum (Rotate degrees) renderiza select con 3 opciones', async () => {
    const step: ImageOpStep = {
      ...emptyStep(),
      op: 'Rotate',
      params: { degrees: 90 },
    }
    const wrapper = mount(ImageOpStepForm, { props: { modelValue: step } })
    const selects = wrapper.findAll('select')
    // [0]: selector de op, [1]: degrees
    expect(selects.length).toBeGreaterThanOrEqual(2)
    const degreesSelect = selects[1]
    expect(degreesSelect.findAll('option')).toHaveLength(3)
  })

  it('al cambiar de op, reemplaza params y conserva window', async () => {
    const step: ImageOpStep = {
      ...emptyStep(),
      op: 'ConvertTo1Bpp',
      params: { threshold: 200 },
      window: [10, 20, 100, 100],
    }
    const wrapper = mount(ImageOpStepForm, { props: { modelValue: step } })
    await wrapper.find('select').setValue('RotateAngle')
    const events = wrapper.emitted('update:modelValue')
    const last = events![events!.length - 1][0] as ImageOpStep
    expect(last.op).toBe('RotateAngle')
    expect(last.params).toEqual({ angle: 0 })
    expect(last.window).toEqual([10, 20, 100, 100])
  })

  it('Resize infiere modo scale y muestra solo el campo scale', () => {
    const step: ImageOpStep = {
      ...emptyStep(),
      op: 'Resize',
      params: { scale: 0.5 },
    }
    const wrapper = mount(ImageOpStepForm, { props: { modelValue: step } })
    const numberInputs = wrapper.findAll('input[type=number]')
    // [scale] + 4 de window si activado — aquí window es null, así que solo scale
    // El selector "modo" es un <select>, no input number.
    expect(numberInputs.length).toBe(1)
  })

  it('Resize al cambiar a modo size emite params con width y height', async () => {
    const step: ImageOpStep = {
      ...emptyStep(),
      op: 'Resize',
      params: { scale: 1.0 },
    }
    const wrapper = mount(ImageOpStepForm, { props: { modelValue: step } })
    // Buscar el select del modo (es el segundo select: op + modo)
    const selects = wrapper.findAll('select')
    const modeSelect = selects[1]
    await modeSelect.setValue('size')
    const events = wrapper.emitted('update:modelValue')
    const last = events![events!.length - 1][0] as ImageOpStep
    expect(last.params).toEqual({ width: 800, height: 600 })
  })
})
```

- [ ] **Step 2: Run test — debe fallar**

Run:
```bash
cd web/frontend && npm run test -- --run ImageOpStepForm
```

Expected: FAIL por módulo no encontrado.

- [ ] **Step 3: Implementar el componente**

Crear `web/frontend/src/components/pipeline/forms/ImageOpStepForm.vue`:

```vue
<script setup lang="ts">
import { computed } from 'vue'
import type { ImageOpStep } from '@/api/types-pipeline'
import {
  IMAGE_OP_CATALOG,
  CATEGORY_LABELS,
  type OpSchema,
  type FieldSchema,
  type Category,
} from '@/api/image-op-catalog'

import NumberField from '../fields/NumberField.vue'
import EnumField from '../fields/EnumField.vue'
import BooleanField from '../fields/BooleanField.vue'
import PointField from '../fields/PointField.vue'
import ColorField from '../fields/ColorField.vue'
import WindowField from '../WindowField.vue'

const props = defineProps<{ modelValue: ImageOpStep }>()
const emit = defineEmits<{ 'update:modelValue': [step: ImageOpStep] }>()

function patch(update: Partial<ImageOpStep>) {
  emit('update:modelValue', { ...props.modelValue, ...update })
}

// Agrupación para <optgroup>
const grouped = computed(() => {
  const groups = new Map<Category, OpSchema[]>()
  for (const op of IMAGE_OP_CATALOG) {
    const arr = groups.get(op.category) ?? []
    arr.push(op)
    groups.set(op.category, arr)
  }
  return Array.from(groups.entries()).map(([cat, ops]) => ({
    category: cat,
    label: CATEGORY_LABELS[cat],
    ops: ops.slice().sort((a, b) => a.label.localeCompare(b.label, 'es')),
  }))
})

const selectedOp = computed<OpSchema | null>(
  () => IMAGE_OP_CATALOG.find((o) => o.name === props.modelValue.op) ?? null,
)

// --- Caso especial Resize: modo inferido desde params ---
const RESIZE_MODES = [
  { value: 'scale', label: 'Escala' },
  { value: 'size', label: 'Tamaño (px)' },
]

const resizeMode = computed<'scale' | 'size'>(() => {
  const p = props.modelValue.params
  if ('width' in p && 'height' in p) return 'size'
  return 'scale'
})

function isResize(): boolean {
  return selectedOp.value?.name === 'Resize'
}

// Qué fields del schema mostrar según el modo (solo aplica a Resize).
function visibleFields(op: OpSchema): FieldSchema[] {
  if (op.name !== 'Resize') return op.fields
  if (resizeMode.value === 'scale') {
    return op.fields.filter((f) => f.key === 'scale')
  }
  return op.fields.filter((f) => f.key === 'width' || f.key === 'height')
}

function changeOp(newName: string) {
  const op = IMAGE_OP_CATALOG.find((o) => o.name === newName)
  if (!op) return
  const params: Record<string, unknown> = {}
  if (op.name === 'Resize') {
    // Modo por defecto al crear: scale
    params['scale'] = 1.0
  } else {
    for (const f of op.fields) {
      params[f.key] = f.default
    }
  }
  patch({ op: newName, params })
}

function changeResizeMode(mode: 'scale' | 'size') {
  if (mode === 'scale') {
    patch({ params: { scale: 1.0 } })
  } else {
    patch({ params: { width: 800, height: 600 } })
  }
}

function updateFieldValue(key: string, value: unknown) {
  patch({ params: { ...props.modelValue.params, [key]: value } })
}

function fieldValue(key: string, fallback: unknown): unknown {
  return props.modelValue.params[key] ?? fallback
}
</script>

<template>
  <div class="space-y-4">
    <!-- Enabled -->
    <div class="flex items-center gap-2">
      <input
        id="imop_enabled"
        type="checkbox"
        :checked="modelValue.enabled"
        @change="(e) => patch({ enabled: (e.target as HTMLInputElement).checked })"
      />
      <label for="imop_enabled" class="text-sm">Activo</label>
    </div>

    <!-- Selector de operación -->
    <div>
      <label class="block text-[11px] uppercase tracking-wide text-subtext font-medium mb-1">
        Operación
      </label>
      <select
        :value="modelValue.op"
        @change="(e) => changeOp((e.target as HTMLSelectElement).value)"
        class="w-full border rounded-md px-2 py-1.5 text-sm"
      >
        <option value="" disabled>Elige una operación…</option>
        <optgroup
          v-for="g in grouped"
          :key="g.category"
          :label="g.label"
        >
          <option v-for="op in g.ops" :key="op.name" :value="op.name">
            {{ op.label }}
          </option>
        </optgroup>
      </select>
      <p v-if="selectedOp" class="text-xs text-subtext mt-1">
        {{ selectedOp.description }}
      </p>
    </div>

    <!-- Selector de modo para Resize -->
    <div v-if="selectedOp && isResize()">
      <EnumField
        label="Modo"
        :model-value="resizeMode"
        :options="RESIZE_MODES"
        @update:model-value="(v) => changeResizeMode(v as 'scale' | 'size')"
      />
    </div>

    <!-- Fields dinámicos del schema -->
    <template v-if="selectedOp">
      <div v-for="f in visibleFields(selectedOp)" :key="f.key">
        <NumberField
          v-if="f.type === 'int' || f.type === 'float'"
          :model-value="fieldValue(f.key, f.default) as number"
          :label="f.label"
          :min="f.min"
          :max="f.max"
          :step="f.step"
          :integer="f.type === 'int'"
          :help="f.help"
          @update:model-value="(v) => updateFieldValue(f.key, v)"
        />
        <EnumField
          v-else-if="f.type === 'enum'"
          :model-value="fieldValue(f.key, f.default) as string | number"
          :label="f.label"
          :options="f.options!"
          :help="f.help"
          @update:model-value="(v) => updateFieldValue(f.key, v)"
        />
        <BooleanField
          v-else-if="f.type === 'bool'"
          :model-value="fieldValue(f.key, f.default) as boolean"
          :label="f.label"
          :help="f.help"
          @update:model-value="(v) => updateFieldValue(f.key, v)"
        />
        <ColorField
          v-else-if="f.type === 'color'"
          :model-value="fieldValue(f.key, f.default) as [number, number, number]"
          :label="f.label"
          :help="f.help"
          @update:model-value="(v) => updateFieldValue(f.key, v)"
        />
      </div>
    </template>

    <!-- WindowField (ROI) — solo cuando hay op elegida -->
    <div v-if="selectedOp">
      <WindowField
        :model-value="modelValue.window"
        @update:model-value="(v) => patch({ window: v })"
      />
    </div>
  </div>
</template>
```

- [ ] **Step 4: Run test — debe pasar**

Run:
```bash
cd web/frontend && npm run test -- --run ImageOpStepForm
```

Expected: PASS (7/7).

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/components/pipeline/forms/ImageOpStepForm.vue web/frontend/tests/ImageOpStepForm.test.ts
git commit -m "feat(web-frontend): ImageOpStepForm con selector agrupado y fields dinámicos"
```

---

## Task 11: Habilitar `image_op` en `AddStepMenu` e integrar en el drawer

**Files:**
- Modify: `web/frontend/src/components/pipeline/AddStepMenu.vue`
- Modify: `web/frontend/src/components/pipeline/PipelineStepDrawer.vue`

- [ ] **Step 1: Editar `AddStepMenu.vue` — habilitar la opción image_op**

Reemplazar el bloque "Próximamente" del componente para que solo `ocr` y `script` queden deshabilitados. Localizar y reemplazar:

```vue
      <div
        v-for="type in ['image_op', 'ocr', 'script']"
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
        @click="pick('image_op')"
        class="w-full text-left px-3 py-2 text-sm hover:bg-surface-0 flex items-center gap-2"
      >
        <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
        <span>Operación de imagen</span>
        <span class="ml-auto text-xs text-subtext">v2</span>
      </button>
      <div class="border-t border-surface-0 my-1"></div>
      <div class="px-3 py-1.5 text-[11px] text-subtext uppercase tracking-wide">
        Próximamente
      </div>
      <div
        v-for="type in ['ocr', 'script']"
        :key="type"
        class="w-full text-left px-3 py-2 text-sm text-subtext flex items-center gap-2 cursor-not-allowed"
      >
        <span class="w-2 h-2 rounded-full bg-gray-300"></span>
        <span>{{ type }}</span>
      </div>
```

- [ ] **Step 2: Editar `PipelineStepDrawer.vue` — añadir rama `image_op`**

En el `<script setup>`, añadir import:

```ts
import type { PipelineStep, BarcodeStep, ImageOpStep } from '@/api/types-pipeline'
import BarcodeStepForm from './forms/BarcodeStepForm.vue'
import ImageOpStepForm from './forms/ImageOpStepForm.vue'
```

Reemplazar `isEditable`:

```ts
const isEditable = computed(
  () => props.step?.type === 'barcode' || props.step?.type === 'image_op',
)
```

Y en el `<template>`, reemplazar el bloque del form por uno con `v-if` específico para cada tipo:

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
        <div v-else class="text-sm text-subtext bg-amber-50 border border-amber-200 rounded p-3">
          Este tipo de step (<code>{{ step?.type }}</code>) se edita desde el
          configurador de escritorio. Próximamente disponible aquí.
        </div>
      </div>
```

Cambiar la condición del botón "Guardar" para también requerir `op !== ''` en `image_op`:

```vue
        <button
          v-if="isEditable"
          @click="onSave"
          :disabled="!valid || !canSave"
          class="px-4 py-2 text-[13px] bg-primary text-white rounded-md font-semibold hover:bg-primary-hover transition-colors disabled:opacity-50"
        >
          Guardar step
        </button>
```

Añadir en el `<script setup>`:

```ts
const canSave = computed(() => {
  if (!draft.value) return false
  if (draft.value.type === 'image_op') {
    return (draft.value as ImageOpStep).op !== ''
  }
  return true
})
```

- [ ] **Step 3: Verificar que no rompe tests existentes**

Run:
```bash
cd web/frontend && npm run test -- --run
```

Expected: todos los tests siguen pasando (los nuevos + los de v1).

- [ ] **Step 4: Comprobación manual del lint/tipos**

Run:
```bash
cd web/frontend && npm run typecheck 2>&1 | tail -20
```

Expected: 0 errores de tipos. Si no existe ese script, probar:
```bash
cd web/frontend && npx vue-tsc --noEmit 2>&1 | tail -20
```

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/components/pipeline/AddStepMenu.vue web/frontend/src/components/pipeline/PipelineStepDrawer.vue
git commit -m "feat(web-frontend): habilitar image_op en menú y drawer"
```

---

## Task 12: Resumen compacto en `PipelineStepRow`

**Files:**
- Modify: `web/frontend/src/components/pipeline/PipelineStepRow.vue`

- [ ] **Step 1: Editar `PipelineStepRow.vue`**

Cambiar el `<script setup>` para importar el catálogo y añadir la rama `image_op` al `summary` computed.

Reemplazar el bloque de imports + computed:

```ts
import type { PipelineStep, BarcodeStep, ImageOpStep } from '@/api/types-pipeline'
import { IMAGE_OP_CATALOG } from '@/api/image-op-catalog'
import { computed } from 'vue'

const props = defineProps<{ step: PipelineStep; index: number }>()
defineEmits<{ edit: []; remove: [] }>()

const typeColors: Record<string, string> = {
  barcode: 'bg-sky-500',
  image_op: 'bg-emerald-500',
  ocr: 'bg-amber-500',
  script: 'bg-violet-500',
}

function formatParams(params: Record<string, unknown>): string {
  const keys = Object.keys(params)
  if (keys.length === 0) return ''
  const head = keys.slice(0, 2).map((k) => `${k}=${params[k]}`).join(', ')
  return keys.length > 2 ? `${head}…` : head
}

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
  return 'Editable desde configurador de escritorio'
})
```

- [ ] **Step 2: Verificar tests**

Run:
```bash
cd web/frontend && npm run test -- --run
```

Expected: todos los tests siguen pasando.

- [ ] **Step 3: Commit**

```bash
git add web/frontend/src/components/pipeline/PipelineStepRow.vue
git commit -m "feat(web-frontend): resumen compacto para image_op en la fila"
```

---

## Task 13: Verificación manual end-to-end

**Objetivo:** comprobar que el flujo completo funciona contra el backend real, incluyendo que un pipeline creado desde web se ejecuta correctamente.

- [ ] **Step 1: Arrancar el stack local**

En 3 terminales separadas:

```bash
# Terminal 1 — Postgres
docker start docscan-pg

# Terminal 2 — API
source .venv/bin/activate
uvicorn web.api.main:create_app --factory --reload --port 8001

# Terminal 3 — Frontend
cd web/frontend && npm run dev
```

- [ ] **Step 2: Login con usuario de prueba**

Abrir `http://localhost:5173` y loguear con `demo2@demo.com` / `demo12345` (company_admin de "Demo Org" — ver memoria web).

- [ ] **Step 3: Abrir la app de prueba "Pipeline Test v1" (id 8)**

Navegar a la pestaña de pipeline. Debe verse el BarcodeStep existente.

- [ ] **Step 4: Añadir un ImageOpStep**

Pulsar "Añadir step" → "Operación de imagen". Se abre el drawer con el selector y el botón "Guardar" deshabilitado (porque `op === ''`).

- [ ] **Step 5: Probar 3 operaciones de categorías distintas**

Para cada una, elegir la op, ajustar 1 parámetro, pulsar "Guardar step" y comprobar que la fila aparece con resumen correcto:

- **AutoDeskew** (geometría, sin params): resumen debe mostrar `"Corregir inclinación"`.
- **ConvertTo1Bpp** (limpieza): cambiar `threshold` a 180; resumen debe mostrar `"Convertir a 1 bit · threshold=180"`.
- **Resize** (geometría, caso especial): elegir modo "Tamaño (px)", ajustar width=1200 / height=800; resumen debe mostrar `"Redimensionar · width=1200, height=800"`.

- [ ] **Step 6: Activar "Aplicar solo a una región" en una op**

Reabrir ConvertTo1Bpp, activar el toggle de región, dejar valores por defecto, guardar. Resumen debe incluir `· región 0,0,100,100`.

- [ ] **Step 7: Reordenar con drag & drop**

Arrastrar los ImageOpSteps entre sí y con el BarcodeStep. Confirmar que persiste al recargar la página.

- [ ] **Step 8: Guardar el pipeline completo**

Pulsar "Guardar pipeline" (o comprobar que el auto-save del v1 ya persistió). Debe mostrar toast verde.

- [ ] **Step 9: Verificar persistencia en BD**

En una terminal (ajusta puerto/usuario si hace falta — ver `.env` del proyecto):

```bash
psql "postgresql://docscan:docscan@localhost:5433/docscan" \
  -c "SELECT id, name, LEFT(pipeline_json::text, 200) FROM applications WHERE id = 8;"
```

Debe devolver una fila cuyo `pipeline_json` contiene los `image_op` que se
acaban de crear (busca los `"type":"image_op"` y las `"op"` que elegiste).

- [ ] **Step 10: Ejecutar el pipeline con un lote de prueba**

Subir una imagen escaneada desde la interfaz web de batches, asignarla a la app id 8 y ejecutar el pipeline. Verificar en los logs del servidor que las ops se aplican sin `KeyError`.

- [ ] **Step 11: Si todo pasa, último commit de documentación**

```bash
# Añadir nota al bitácora del editor de pipeline v2 si existe, o crearla.
# Documentar: fecha, tareas completadas, tests añadidos, QA manual pasado.
```

---

## Verificación final y push

- [ ] **Step 1: Run full test suite (backend + frontend)**

```bash
# Backend
source .venv/bin/activate
pytest -q

# Frontend
cd web/frontend && npm run test -- --run
```

Expected: 960 backend (sin cambios, sigue igual) + ~33 frontend (8 originales + ~25 nuevos). Cero fallos.

Nota: si la cifra frontend difiere de la esperada, revisar si algún test se duplicó o si tests existentes se rompieron por los cambios en los tipos.

- [ ] **Step 2: Push al remote**

```bash
git push origin feature/web
```

- [ ] **Step 3: Crear informe del día**

Crear `docs/progreso_2026-04-20.md` siguiendo el formato estándar del proyecto (skill `progreso-doc`). Debe resumir: sub-proyecto 2 completado, 24 ops, ~25 tests frontend nuevos, QA manual passed.

---

## Fuera de scope (recordatorio)

- Preview del resultado de la op (sub-proyecto independiente si se pide).
- Selector visual de ROI.
- Cambios en backend (`IMAGE_OPS`, `serializer.py`, endpoint `GET /api/image-ops/schema`).
