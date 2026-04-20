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
