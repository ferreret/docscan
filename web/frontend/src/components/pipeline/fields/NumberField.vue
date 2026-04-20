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
