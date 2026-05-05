<script setup lang="ts">
// Widget disponible para futuras ops con tipo 'point'. Actualmente ningún
// entry de IMAGE_OP_CATALOG lo usa — FloodFill modela x/y como dos campos
// 'int' separados. Para adoptarlo: añadir type: 'point' en el catálogo y
// una rama v-else-if en ImageOpStepForm.vue que expanda {x,y} a params.
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
