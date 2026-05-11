<script setup lang="ts">
// Botones "Escanear" desde el agente local, dentro del WorkbenchToolbar.
//
// Sprint cliente local web, hito 10. Si el agente no está detectado o
// no está vinculado, este componente se renderiza vacío (oculto del
// todo). El operario tiene la entrada "Mi estación" en el sidebar para
// arreglarlo, no contaminamos el toolbar con un botón "vincular".
//
// Sprint D, hito 13. Estrategia de UX según el escáner y la app:
// - Si scanner.supports_native_ui (TWAIN/WIA en Windows) → manda
//   show_ui=true y el driver pinta su propio diálogo. Sin dialog dinámico.
// - Si !native_ui y app.scan_show_dialog → abre ScannerOptionsDialog
//   construido desde GET /scanners/{name}/options. Al submit, dispara el
//   /scan-* con `options` como overrides.
// - Si !native_ui y !app.scan_show_dialog → escanea directo (sin dialog,
//   sin overrides; el driver SANE/TWAIN usa su última configuración).
// - Sin app prop (back-compat): comportamiento previo sin dialog.

import { onMounted, ref, computed, watch } from 'vue'
import { useAgentStore } from '@/stores/agent'
import { useApplicationsStore } from '@/stores/applications'
import { useToast } from '@/composables/useToast'
import { scanFlatbed, scanAdf } from '@/api/agent'
import ScannerOptionsDialog from '@/components/workbench/ScannerOptionsDialog.vue'
import type { ApplicationResponse } from '@/api/types'

const props = defineProps<{
  batchId: number
  disabled?: boolean
  application?: ApplicationResponse | null
}>()

const emit = defineEmits<{
  (e: 'uploaded'): void
  (e: 'adf-progress', payload: { current: number; total: number | null }): void
  (e: 'adf-finished'): void
  (e: 'error', message: string): void
}>()

const agent = useAgentStore()
const apps = useApplicationsStore()
const toast = useToast()

const selectedScanner = ref<string>('')
const scanning = ref(false)
const adfActive = ref(false)

// Estado del dialog dinámico (hito 13).
const dialogOpen = ref(false)
const pendingMode = ref<'flatbed' | 'adf' | null>(null)

const ready = computed(
  () => agent.available && agent.paired && agent.scanners.length > 0,
)

const busy = computed(() => scanning.value || adfActive.value)

// Defaults parseados de la app — null si no hay app, {} si JSON inválido.
const parsedDefaults = computed<Record<string, unknown>>(() => {
  if (!props.application?.scan_defaults_json) return {}
  try {
    const parsed = JSON.parse(props.application.scan_defaults_json)
    return typeof parsed === 'object' && parsed !== null ? parsed : {}
  } catch {
    return {}
  }
})

const selectedScannerInfo = computed(() =>
  agent.findScanner(selectedScanner.value),
)

onMounted(async () => {
  if (!agent.available) {
    await agent.detect()
  }
  if (agent.paired && agent.scanners.length === 0) {
    await agent.loadScanners()
  }
  if (!selectedScanner.value && agent.scanners.length > 0) {
    selectedScanner.value = agent.scanners[0].name
  }
})

watch(
  () => agent.scanners,
  (list) => {
    const names = list.map((s) => s.name)
    if (!selectedScanner.value || !names.includes(selectedScanner.value)) {
      selectedScanner.value = names[0] ?? ''
    }
  },
)

// Decide qué hacer al pulsar Flatbed/ADF según el escáner y la app.
type Strategy = 'native' | 'dialog' | 'direct'
function decideStrategy(): Strategy {
  if (selectedScannerInfo.value?.supports_native_ui) return 'native'
  // Sin app prop: comportamiento legacy (sin dialog, sin overrides).
  if (!props.application) return 'direct'
  if (props.application.scan_show_dialog) return 'dialog'
  return 'direct'
}

async function runFlatbed(extra: { options?: Record<string, unknown>; show_ui?: boolean }): Promise<void> {
  scanning.value = true
  try {
    await scanFlatbed({
      scanner_name: selectedScanner.value,
      batch_id: props.batchId,
      ...extra,
    })
    emit('uploaded')
  } catch (e) {
    emit('error', e instanceof Error ? e.message : 'Error escaneando flatbed')
  } finally {
    scanning.value = false
  }
}

async function runAdf(extra: { options?: Record<string, unknown>; show_ui?: boolean }): Promise<void> {
  adfActive.value = true
  let count = 0
  let hadError = false
  try {
    for await (const ev of scanAdf({
      scanner_name: selectedScanner.value,
      batch_id: props.batchId,
      ...extra,
    })) {
      if (ev.event === 'page_uploaded') {
        count++
        emit('adf-progress', { current: count, total: null })
      } else if (ev.event === 'error') {
        hadError = true
        emit('error', ev.detail || `Error en el ADF (${ev.code ?? 'desconocido'})`)
      }
    }
  } catch (e) {
    hadError = true
    emit('error', e instanceof Error ? e.message : 'Error escaneando ADF')
  } finally {
    adfActive.value = false
    emit('adf-finished')
    if (count > 0 || !hadError) {
      emit('uploaded')
    }
  }
}

async function onFlatbed(): Promise<void> {
  if (!selectedScanner.value) return
  const strategy = decideStrategy()
  if (strategy === 'dialog') {
    pendingMode.value = 'flatbed'
    dialogOpen.value = true
    return
  }
  await runFlatbed(strategy === 'native' ? { show_ui: true } : {})
}

async function onAdf(): Promise<void> {
  if (!selectedScanner.value) return
  const strategy = decideStrategy()
  if (strategy === 'dialog') {
    pendingMode.value = 'adf'
    dialogOpen.value = true
    return
  }
  await runAdf(strategy === 'native' ? { show_ui: true } : {})
}

async function onDialogSubmit(overrides: Record<string, unknown>): Promise<void> {
  const mode = pendingMode.value
  dialogOpen.value = false
  pendingMode.value = null
  if (mode === 'flatbed') {
    await runFlatbed({ options: overrides })
  } else if (mode === 'adf') {
    await runAdf({ options: overrides })
  }
}

function onDialogClose(): void {
  dialogOpen.value = false
  pendingMode.value = null
}

async function onSaveDefaults(defaults: Record<string, unknown>): Promise<void> {
  if (!props.application) return
  try {
    await apps.update(props.application.id, {
      scan_defaults_json: JSON.stringify(defaults),
    })
    toast.success('Defaults de escaneo guardados')
  } catch (e) {
    toast.error(e instanceof Error ? e.message : 'No se pudieron guardar los defaults')
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
      <option v-for="s in agent.scanners" :key="s.name" :value="s.name">
        {{ s.name }}
      </option>
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

    <ScannerOptionsDialog
      :visible="dialogOpen"
      :scannerName="selectedScanner"
      :initialDefaults="parsedDefaults"
      :canSaveDefaults="!!application"
      @submit="onDialogSubmit"
      @save-defaults="onSaveDefaults"
      @close="onDialogClose"
    />
  </div>
</template>
