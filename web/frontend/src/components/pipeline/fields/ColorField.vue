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
