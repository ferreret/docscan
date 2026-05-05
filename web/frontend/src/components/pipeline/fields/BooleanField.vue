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
