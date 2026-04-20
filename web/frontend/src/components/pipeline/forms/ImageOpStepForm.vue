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

const isResize = computed(() => selectedOp.value?.name === 'Resize')

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
    <div v-if="selectedOp && isResize">
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
