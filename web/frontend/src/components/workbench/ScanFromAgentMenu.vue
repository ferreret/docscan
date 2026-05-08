<script setup lang="ts">
// Botones "Escanear" desde el agente local, dentro del WorkbenchToolbar.
//
// Sprint cliente local web, hito 10. Si el agente no está detectado o
// no está vinculado, este componente se renderiza vacío (oculto del
// todo). El operario tiene la entrada "Mi estación" en el sidebar para
// arreglarlo, no contaminamos el toolbar con un botón "vincular".
//
// Cuando hay agente y al menos un escáner:
// - Si solo hay 1 escáner, los botones lo escogen automáticamente.
// - Si hay >1, un selector compacto permite elegir.
// - Botón "🖨 Flatbed" → POST /scan-and-upload (hito 7), una página.
// - Botón "🖨 ADF" → stream NDJSON de /scan-adf-and-upload (hito 8),
//   emite progreso por página al padre.

import { onMounted, ref, computed, watch } from 'vue'
import { useAgentStore } from '@/stores/agent'
import { scanFlatbed, scanAdf } from '@/api/agent'

const props = defineProps<{
  batchId: number
  disabled?: boolean
}>()

const emit = defineEmits<{
  (e: 'uploaded'): void
  (e: 'adf-progress', payload: { current: number; total: number | null }): void
  (e: 'adf-finished'): void
  (e: 'error', message: string): void
}>()

const agent = useAgentStore()

const selectedScanner = ref<string>('')
const scanning = ref(false)
const adfActive = ref(false)

const ready = computed(
  () => agent.available && agent.paired && agent.scanners.length > 0,
)

const busy = computed(() => scanning.value || adfActive.value)

onMounted(async () => {
  if (!agent.available) {
    await agent.detect()
  }
  if (agent.paired && agent.scanners.length === 0) {
    await agent.loadScanners()
  }
  // Por defecto, primer escáner.
  if (!selectedScanner.value && agent.scanners.length > 0) {
    selectedScanner.value = agent.scanners[0]
  }
})

watch(
  () => agent.scanners,
  (list) => {
    if (!selectedScanner.value || !list.includes(selectedScanner.value)) {
      selectedScanner.value = list[0] ?? ''
    }
  },
)

async function onFlatbed(): Promise<void> {
  if (!selectedScanner.value) return
  scanning.value = true
  try {
    await scanFlatbed({
      scanner_name: selectedScanner.value,
      batch_id: props.batchId,
    })
    emit('uploaded')
  } catch (e) {
    emit('error', e instanceof Error ? e.message : 'Error escaneando flatbed')
  } finally {
    scanning.value = false
  }
}

async function onAdf(): Promise<void> {
  if (!selectedScanner.value) return
  adfActive.value = true
  let count = 0
  let hadError = false
  try {
    for await (const ev of scanAdf({
      scanner_name: selectedScanner.value,
      batch_id: props.batchId,
    })) {
      if (ev.event === 'page_uploaded') {
        count++
        emit('adf-progress', { current: count, total: null })
      } else if (ev.event === 'error') {
        hadError = true
        emit(
          'error',
          ev.detail || `Error en el ADF (${ev.code ?? 'desconocido'})`,
        )
      }
      // started / completed: nada que hacer aquí, el progreso lo lleva count.
    }
  } catch (e) {
    hadError = true
    emit('error', e instanceof Error ? e.message : 'Error escaneando ADF')
  } finally {
    adfActive.value = false
    emit('adf-finished')
    // Refrescamos el lote aunque haya habido error: las páginas anteriores
    // al fallo ya están en el SaaS y el operario tiene que verlas.
    if (count > 0 || !hadError) {
      emit('uploaded')
    }
  }
}
</script>

<template>
  <div
    v-if="ready"
    class="flex items-center gap-1"
    data-testid="scan-from-agent-menu"
  >
    <select
      v-if="agent.scanners.length > 1"
      v-model="selectedScanner"
      :disabled="busy || disabled"
      class="bg-base text-text text-xs px-2 py-1.5 rounded border border-surface-1 max-w-[180px] truncate"
      data-testid="scanner-select"
    >
      <option v-for="s in agent.scanners" :key="s" :value="s">{{ s }}</option>
    </select>
    <span
      v-else
      class="text-xs text-subtext px-2 py-1.5 truncate max-w-[180px] hidden xl:inline"
      :title="selectedScanner"
    >
      {{ selectedScanner }}
    </span>
    <button
      type="button"
      class="bg-base text-text text-xs px-3 py-1.5 rounded border border-surface-1 hover:bg-crust disabled:opacity-50 inline-flex items-center gap-1.5"
      :disabled="busy || disabled || !selectedScanner"
      data-testid="btn-flatbed"
      @click="onFlatbed"
    >
      <span
        v-if="scanning"
        class="inline-block w-3 h-3 border-2 border-text border-t-transparent rounded-full animate-spin"
      ></span>
      <span>{{ scanning ? 'Escaneando…' : '🖨 Flatbed' }}</span>
    </button>
    <button
      type="button"
      class="bg-base text-text text-xs px-3 py-1.5 rounded border border-surface-1 hover:bg-crust disabled:opacity-50 inline-flex items-center gap-1.5"
      :disabled="busy || disabled || !selectedScanner"
      data-testid="btn-adf"
      @click="onAdf"
    >
      <span
        v-if="adfActive"
        class="inline-block w-3 h-3 border-2 border-text border-t-transparent rounded-full animate-spin"
      ></span>
      <span>{{ adfActive ? 'Escaneando ADF…' : '🖨 ADF' }}</span>
    </button>
  </div>
</template>
