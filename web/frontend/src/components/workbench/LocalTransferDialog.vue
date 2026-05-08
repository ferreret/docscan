<script setup lang="ts">
// Dialog de transferencia local — sprint cliente local web, hito 11.
//
// El operario elige una ruta destino del PC y un modo (carpeta extraída
// o ZIP suelto). Al confirmar, llamamos a transferBatchToLocal que
// reusa el endpoint /api/batches/{id}/export del SaaS y escribe el
// resultado en disco vía el agente local.

import { ref, computed, watch, nextTick } from 'vue'
import {
  transferBatchToLocal,
  type TransferLocalMode,
} from '@/api/agent'

const props = defineProps<{
  visible: boolean
  batchId: number
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'success', payload: { path: string; files_count: number }): void
  (e: 'error', message: string): void
}>()

const destination = ref('')
const mode = ref<TransferLocalMode>('extracted')
const sending = ref(false)

const dialogRef = ref<HTMLDivElement | null>(null)
const inputRef = ref<HTMLInputElement | null>(null)

const canSubmit = computed(
  () => !sending.value && destination.value.trim().length > 0,
)

watch(
  () => props.visible,
  (v) => {
    if (v) {
      // Reset por si el dialog se reusa entre lotes.
      destination.value = ''
      mode.value = 'extracted'
      sending.value = false
      nextTick(() => {
        inputRef.value?.focus()
      })
    }
  },
  { immediate: true },
)

async function onSubmit() {
  const dest = destination.value.trim()
  if (!dest) return
  sending.value = true
  try {
    const result = await transferBatchToLocal({
      batch_id: props.batchId,
      destination: dest,
      mode: mode.value,
    })
    emit('success', { path: result.path, files_count: result.files_count })
    emit('close')
  } catch (e) {
    emit('error', e instanceof Error ? e.message : 'Error transfiriendo el lote')
  } finally {
    sending.value = false
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && !sending.value) {
    e.stopPropagation()
    emit('close')
  }
}
</script>

<template>
  <div
    v-if="visible"
    ref="dialogRef"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
    role="dialog"
    aria-modal="true"
    data-testid="local-transfer-dialog"
    @keydown="onKeydown"
  >
    <div
      class="bg-mantle border border-surface-1 rounded-lg p-6 w-full max-w-md shadow-xl"
      @click.stop
    >
      <h2 class="text-lg font-semibold text-text mb-1">Descargar a este equipo</h2>
      <p class="text-sm text-subtext mb-4">
        El agente local descargará el lote del SaaS y lo escribirá aquí.
      </p>

      <form @submit.prevent="onSubmit" class="space-y-4">
        <div>
          <label class="block text-xs font-medium text-text mb-1">
            Carpeta destino
          </label>
          <input
            ref="inputRef"
            v-model="destination"
            type="text"
            placeholder="Ej.: /home/usuario/Documents/DocScan o C:\Users\…\DocScan"
            class="w-full px-3 py-2 text-sm rounded-md border border-surface-1 bg-base text-text font-mono focus:border-primary focus:outline-none"
            :disabled="sending"
            data-testid="destination-input"
          />
          <p class="text-xs text-subtext mt-1">
            Se crea si no existe. Usa una ruta absoluta del PC donde corre el agente.
          </p>
        </div>

        <fieldset class="space-y-2">
          <legend class="block text-xs font-medium text-text mb-1">Formato</legend>
          <label class="flex items-start gap-2 text-sm cursor-pointer">
            <input
              type="radio"
              v-model="mode"
              value="extracted"
              :disabled="sending"
              class="mt-0.5"
              data-testid="mode-extracted"
            />
            <span class="text-text">
              Carpeta extraída
              <span class="block text-xs text-subtext">
                Páginas + manifest.json sueltos en
                <code>{destino}/batch_{id}/</code>
              </span>
            </span>
          </label>
          <label class="flex items-start gap-2 text-sm cursor-pointer">
            <input
              type="radio"
              v-model="mode"
              value="zip"
              :disabled="sending"
              class="mt-0.5"
              data-testid="mode-zip"
            />
            <span class="text-text">
              ZIP comprimido
              <span class="block text-xs text-subtext">
                Un único fichero
                <code>{destino}/batch_{id}.zip</code>
              </span>
            </span>
          </label>
        </fieldset>

        <div class="flex justify-end gap-2 pt-2">
          <button
            type="button"
            class="text-sm px-3 py-1.5 rounded border border-surface-1 text-text hover:bg-crust"
            :disabled="sending"
            data-testid="cancel-button"
            @click="emit('close')"
          >
            Cancelar
          </button>
          <button
            type="submit"
            class="text-sm px-3 py-1.5 rounded bg-primary text-base font-medium hover:opacity-90 disabled:opacity-50 inline-flex items-center gap-1.5"
            :disabled="!canSubmit"
            data-testid="confirm-button"
          >
            <span
              v-if="sending"
              class="inline-block w-3 h-3 border-2 border-base border-t-transparent rounded-full animate-spin"
            ></span>
            <span>{{ sending ? 'Descargando…' : 'Descargar' }}</span>
          </button>
        </div>
      </form>
    </div>
  </div>
</template>
