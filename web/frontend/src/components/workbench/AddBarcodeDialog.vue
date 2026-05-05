<script setup lang="ts">
import { ref, watch, computed, nextTick, useTemplateRef, onBeforeUnmount } from 'vue'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{
  (e: 'submit', data: { value: string; symbology: string }): void
  (e: 'close'): void
}>()

const SYMBOLOGIES = [
  'MANUAL', 'CODE128', 'CODE39',
  'EAN13', 'EAN8',
  'QR', 'DATAMATRIX', 'PDF417',
]

const value = ref('')
const symbology = ref('MANUAL')
const valueInputRef = useTemplateRef<HTMLInputElement>('valueInputRef')

function onDocEsc(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.stopPropagation()
    emit('close')
  }
}

watch(() => props.visible, (v) => {
  if (v) {
    value.value = ''
    symbology.value = 'MANUAL'
    nextTick(() => valueInputRef.value?.focus())
    document.addEventListener('keydown', onDocEsc, true)
  } else {
    document.removeEventListener('keydown', onDocEsc, true)
  }
}, { immediate: true })

onBeforeUnmount(() => document.removeEventListener('keydown', onDocEsc, true))

const canSubmit = computed(() => value.value.trim().length > 0)

const onSubmit = () => {
  if (!canSubmit.value) return
  emit('submit', {
    value: value.value.trim(),
    symbology: symbology.value,
  })
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.stopPropagation()
    emit('close')
  }
}
</script>

<template>
  <div
    v-if="visible"
    class="fixed inset-0 bg-text/40 backdrop-blur-sm flex items-center justify-center z-50 px-4"
    @click.self="emit('close')"
  >
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Añadir barcode manual"
      tabindex="-1"
      class="bg-base rounded-lg shadow-xl border border-surface-0 p-6 w-full max-w-md space-y-4"
      @keydown="onKeydown"
    >
      <h2 class="text-base font-semibold text-text">Añadir barcode manual</h2>

      <div>
        <label class="block text-xs font-medium text-subtext mb-1">Valor</label>
        <input
          ref="valueInputRef"
          data-testid="barcode-value"
          v-model="value"
          type="text"
          class="w-full rounded-md border border-surface-1 bg-base px-3 py-2 text-[13px] text-text focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
          @keyup.enter="onSubmit"
        />
      </div>

      <div>
        <label class="block text-xs font-medium text-subtext mb-1">Symbology</label>
        <select
          data-testid="barcode-symbology"
          v-model="symbology"
          class="w-full rounded-md border border-surface-1 bg-base px-3 py-2 text-[13px] text-text focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
        >
          <option v-for="s in SYMBOLOGIES" :key="s" :value="s">{{ s }}</option>
        </select>
      </div>

      <div class="flex justify-end gap-2 pt-2">
        <button
          data-testid="cancel"
          type="button"
          class="px-4 py-2 text-[13px] font-medium text-text bg-crust hover:bg-surface-0 border border-surface-1 rounded-md transition-colors"
          @click="emit('close')"
        >Cancelar</button>
        <button
          data-testid="submit"
          type="button"
          class="bg-primary text-base px-4 py-2 text-[13px] font-semibold rounded-md hover:bg-primary-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="!canSubmit"
          @click="onSubmit"
        >Añadir</button>
      </div>
    </div>
  </div>
</template>
