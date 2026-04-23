<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { ApplicationResponse, BatchResponse } from '@/api/types'
import LogPanel from './LogPanel.vue'
import { useWorkbenchLog } from '@/composables/useWorkbenchLog'

interface BatchField {
  label: string
  type: 'texto' | 'fecha' | 'lista' | 'numerico'
  required: boolean
  config: Record<string, unknown>
}

const props = defineProps<{
  app: ApplicationResponse | null
  batch: BatchResponse | null
  saving: boolean
}>()

const emit = defineEmits<{
  (e: 'save', fields: Record<string, unknown>): void
}>()

const activeTab = ref<'lote' | 'log'>('lote')

const log = useWorkbenchLog()
const warnErrorCount = computed(() =>
  log.entries.value.filter((e) => e.level === 'warn' || e.level === 'error').length,
)

const fieldDefs = computed<BatchField[]>(() => {
  if (!props.app) return []
  try {
    const parsed = JSON.parse(props.app.batch_fields_json || '[]')
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
})

const initialFields = computed<Record<string, unknown>>(() => {
  if (!props.batch) return {}
  try {
    const parsed = JSON.parse(props.batch.fields_json || '{}')
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
})

const localFields = ref<Record<string, unknown>>({ ...initialFields.value })

watch(initialFields, (next) => {
  localFields.value = { ...next }
})

const hasChanges = computed(() => {
  return JSON.stringify(localFields.value) !== JSON.stringify(initialFields.value)
})

const validationError = computed<string | null>(() => {
  for (const f of fieldDefs.value) {
    if (f.required && !localFields.value[f.label]) {
      return `Campo obligatorio: ${f.label}`
    }
  }
  return null
})

function onSave(): void {
  if (validationError.value) return
  emit('save', { ...localFields.value })
}
</script>

<template>
  <section class="h-full flex flex-col bg-mantle border-l border-t border-surface-0">
    <nav class="flex border-b border-surface-0" aria-label="Pestañas de metadatos">
      <button
        data-testid="tab-lote"
        type="button"
        :aria-pressed="activeTab === 'lote'"
        class="px-3 py-2 text-xs uppercase tracking-wide font-semibold transition-colors"
        :class="activeTab === 'lote' ? 'text-primary border-b-2 border-primary' : 'text-subtext hover:text-text'"
        @click="activeTab = 'lote'"
      >
        <span data-testid="tab-lote-label">Lote</span>
      </button>
      <button
        data-testid="tab-log"
        type="button"
        :aria-pressed="activeTab === 'log'"
        class="px-3 py-2 text-xs uppercase tracking-wide font-semibold transition-colors"
        :class="activeTab === 'log' ? 'text-primary border-b-2 border-primary' : 'text-subtext hover:text-text'"
        @click="activeTab = 'log'"
      >
        <span data-testid="tab-log-label">
          Log<span v-if="warnErrorCount > 0" class="text-warning"> ({{ warnErrorCount }})</span>
        </span>
      </button>
    </nav>

    <div v-if="activeTab === 'lote'" class="flex-1 overflow-auto p-3">
      <p v-if="fieldDefs.length === 0" class="text-center text-subtext text-xs py-6">
        Sin campos definidos
        <span class="block text-overlay-0 mt-1">Configura batch_fields en la aplicación</span>
      </p>

      <form v-else class="space-y-3" @submit.prevent="onSave">
        <div v-for="field in fieldDefs" :key="field.label" class="space-y-1">
          <label class="block text-xs font-medium text-text">
            {{ field.label }}<span v-if="field.required" class="text-danger">*</span>
          </label>
          <input
            v-if="field.type === 'texto'"
            type="text"
            :value="localFields[field.label] ?? ''"
            class="w-full px-2 py-1 text-xs bg-base border border-surface-1 rounded text-text"
            @input="localFields[field.label] = ($event.target as HTMLInputElement).value"
          />
          <input
            v-else-if="field.type === 'fecha'"
            type="date"
            :value="localFields[field.label] ?? ''"
            class="w-full px-2 py-1 text-xs bg-base border border-surface-1 rounded text-text"
            @input="localFields[field.label] = ($event.target as HTMLInputElement).value"
          />
          <input
            v-else-if="field.type === 'numerico'"
            type="number"
            :value="localFields[field.label] ?? ''"
            class="w-full px-2 py-1 text-xs bg-base border border-surface-1 rounded text-text"
            @input="localFields[field.label] = Number(($event.target as HTMLInputElement).value)"
          />
          <select
            v-else-if="field.type === 'lista'"
            :value="localFields[field.label] ?? ''"
            class="w-full px-2 py-1 text-xs bg-base border border-surface-1 rounded text-text"
            @change="localFields[field.label] = ($event.target as HTMLSelectElement).value"
          >
            <option value="">—</option>
            <option v-for="opt in (field.config?.values as string[] | undefined) ?? []" :key="opt" :value="opt">{{ opt }}</option>
          </select>
        </div>

        <p v-if="validationError" class="text-xs text-danger">{{ validationError }}</p>

        <button
          type="submit"
          :disabled="!hasChanges || saving || !!validationError || !batch"
          class="w-full bg-primary text-base font-semibold text-xs px-3 py-1.5 rounded hover:bg-primary-hover disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {{ saving ? 'Guardando…' : 'Guardar' }}
        </button>
      </form>
    </div>

    <div v-else-if="activeTab === 'log'" class="flex-1 min-h-0">
      <LogPanel />
    </div>
  </section>
</template>
