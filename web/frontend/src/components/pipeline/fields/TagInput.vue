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
