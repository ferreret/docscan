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
