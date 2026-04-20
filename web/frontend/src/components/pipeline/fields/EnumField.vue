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
