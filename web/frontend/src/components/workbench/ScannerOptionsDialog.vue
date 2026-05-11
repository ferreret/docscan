<script setup lang="ts">
// Diálogo dinámico de opciones de escaneo (sprint D, hito 13).
//
// Se monta cuando el escáner NO tiene UI nativa (típico SANE en Linux) y
// la aplicación tiene scan_show_dialog=true. Render dinámico desde
// GET /scanners/{name}/options vía useScannerOptions.
//
// Componente presentacional puro: no escribe en el SaaS. Emite los
// overrides al hacer submit, y emite los defaults al pulsar "Recordar
// para esta app". Es la integración (ScanFromAgentMenu / MiEstacionView)
// quien llama POST /scan-* y quien hace PATCH /api/applications/{id}.

import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { useScannerOptions } from '@/composables/useScannerOptions'
import type { DeviceOptionInfo } from '@/api/types'

const props = defineProps<{
  visible: boolean
  scannerName: string
  initialDefaults: Record<string, unknown>
  canSaveDefaults: boolean
}>()

const emit = defineEmits<{
  (e: 'submit', overrides: Record<string, unknown>): void
  (e: 'save-defaults', defaults: Record<string, unknown>): void
  (e: 'close'): void
}>()

// Lista de opciones que consideramos "esenciales" — el resto va a Avanzadas.
// Se filtra por intersección con las options reales del driver, así que si
// una de ellas no existe simplemente no aparece.
const ESSENTIAL_NAMES = ['resolution', 'mode', 'source', 'brightness', 'contrast']

const { options, loading, error, fetch: fetchOptions } = useScannerOptions()

// Valores actuales del form, indexados por option.name.
const values = ref<Record<string, unknown>>({})
const advancedExpanded = ref(false)

// Opciones renderizables: descarta inactivas y readonly.
const renderable = computed(() =>
  options.value.filter((o) => o.is_active && o.is_settable),
)

const essentialOptions = computed(() =>
  ESSENTIAL_NAMES.map((n) => renderable.value.find((o) => o.name === n)).filter(
    (o): o is DeviceOptionInfo => o !== undefined,
  ),
)

const advancedOptions = computed(() =>
  renderable.value.filter((o) => !ESSENTIAL_NAMES.includes(o.name)),
)

function isTupleConstraint(c: DeviceOptionInfo['constraint']): c is [number, number, number] {
  // Tupla (min, max, step): exactamente 3 números.
  return Array.isArray(c) && c.length === 3 && c.every((v) => typeof v === 'number')
}

function isListConstraint(c: DeviceOptionInfo['constraint']): c is string[] | number[] {
  // Cualquier array que no sea una tupla numérica (incluye listas de
  // 3 strings como ["Color","Gray","Lineart"], que NO son rangos).
  return Array.isArray(c) && !isTupleConstraint(c)
}

function inputKind(opt: DeviceOptionInfo): 'select' | 'range' | 'checkbox' | 'number' | 'text' {
  if (isTupleConstraint(opt.constraint)) return 'range'
  if (isListConstraint(opt.constraint)) return 'select'
  if (opt.type === 'bool') return 'checkbox'
  if (opt.type === 'int' || opt.type === 'fixed') return 'number'
  return 'text'
}

function initValues() {
  const next: Record<string, unknown> = {}
  for (const opt of renderable.value) {
    if (opt.name in props.initialDefaults) {
      next[opt.name] = props.initialDefaults[opt.name]
    } else {
      next[opt.name] = opt.value
    }
  }
  values.value = next
}

// Re-fetch al abrir y al cambiar de scanner.
watch(
  () => [props.visible, props.scannerName] as const,
  async ([vis, name], _old) => {
    if (vis && name) {
      await fetchOptions(name)
      initValues()
    }
  },
  { immediate: true },
)

// Reinicia valores cuando llegan options nuevas (carga inicial o refresh).
watch(renderable, () => {
  if (props.visible) initValues()
})

// Listener global de Escape (patrón de AddBarcodeDialog para que el filtro
// de useWorkbenchShortcuts no dispare atajos sobre la página de fondo).
function onDocEsc(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.stopPropagation()
    emit('close')
  }
}
watch(
  () => props.visible,
  (v) => {
    if (v) document.addEventListener('keydown', onDocEsc, true)
    else document.removeEventListener('keydown', onDocEsc, true)
  },
  { immediate: true },
)
onBeforeUnmount(() => document.removeEventListener('keydown', onDocEsc, true))

// Coerce string→number cuando el option es numérico (los <select> y <input>
// devuelven siempre string).
function setValue(opt: DeviceOptionInfo, raw: unknown) {
  if (opt.type === 'int' || opt.type === 'fixed') {
    values.value[opt.name] = raw === '' || raw === null ? null : Number(raw)
  } else if (opt.type === 'bool') {
    values.value[opt.name] = Boolean(raw)
  } else {
    values.value[opt.name] = raw
  }
}

function onRetry() {
  fetchOptions(props.scannerName, { refresh: true })
}

function onSubmit() {
  emit('submit', { ...values.value })
}

function onSaveDefaults() {
  emit('save-defaults', { ...values.value })
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
      aria-label="Opciones de escaneo"
      tabindex="-1"
      class="bg-base rounded-lg shadow-xl border border-surface-0 w-full max-w-2xl max-h-[85vh] flex flex-col"
    >
      <header class="px-6 py-4 border-b border-surface-0">
        <h2 class="text-base font-semibold text-text">Opciones de escaneo</h2>
        <p class="text-xs text-subtext mt-1 truncate">{{ scannerName }}</p>
      </header>

      <div class="flex-1 overflow-y-auto px-6 py-4 space-y-6">
        <!-- Loading -->
        <div
          v-if="loading"
          data-testid="loading"
          class="flex items-center justify-center py-12 text-sm text-subtext"
        >
          <span class="animate-pulse">Cargando opciones del driver…</span>
        </div>

        <!-- Error -->
        <div
          v-else-if="error"
          data-testid="error"
          class="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 flex items-start justify-between gap-4"
        >
          <div>
            <p class="font-medium">No se pudieron cargar las opciones</p>
            <p class="mt-1 text-xs">{{ error }}</p>
          </div>
          <button
            data-testid="retry"
            type="button"
            class="px-3 py-1.5 text-xs font-medium bg-base border border-red-300 rounded-md hover:bg-red-100 transition-colors shrink-0"
            @click="onRetry"
          >Reintentar</button>
        </div>

        <!-- Esenciales -->
        <section v-else data-testid="essentials" class="space-y-4">
          <h3 class="text-xs font-semibold uppercase tracking-wide text-subtext">Esenciales</h3>
          <div v-if="essentialOptions.length === 0" class="text-xs text-subtext italic">
            El driver no expone ninguna opción esencial conocida.
          </div>
          <div
            v-for="opt in essentialOptions"
            :key="opt.name"
            :data-testid="`opt-${opt.name}`"
            class="grid grid-cols-1 md:grid-cols-[200px_1fr] gap-2 md:items-center"
          >
            <label class="text-sm text-text" :title="opt.description">
              {{ opt.title || opt.name }}
              <span v-if="opt.unit" class="text-xs text-subtext">({{ opt.unit }})</span>
            </label>
            <div>
              <!-- select -->
              <select
                v-if="inputKind(opt) === 'select'"
                :value="values[opt.name]"
                class="w-full rounded-md border border-surface-1 bg-base px-3 py-2 text-[13px] text-text focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                @change="setValue(opt, ($event.target as HTMLSelectElement).value)"
              >
                <option v-for="v in (opt.constraint as (string | number)[])" :key="String(v)" :value="v">
                  {{ v }}
                </option>
              </select>
              <!-- range + number -->
              <div v-else-if="inputKind(opt) === 'range'" class="flex items-center gap-3">
                <input
                  type="range"
                  :min="(opt.constraint as [number, number, number])[0]"
                  :max="(opt.constraint as [number, number, number])[1]"
                  :step="(opt.constraint as [number, number, number])[2]"
                  :value="values[opt.name]"
                  class="flex-1"
                  @input="setValue(opt, ($event.target as HTMLInputElement).value)"
                />
                <input
                  type="number"
                  :min="(opt.constraint as [number, number, number])[0]"
                  :max="(opt.constraint as [number, number, number])[1]"
                  :step="(opt.constraint as [number, number, number])[2]"
                  :value="values[opt.name]"
                  class="w-24 rounded-md border border-surface-1 bg-base px-2 py-1.5 text-[13px] text-text focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                  @input="setValue(opt, ($event.target as HTMLInputElement).value)"
                />
              </div>
              <!-- checkbox -->
              <input
                v-else-if="inputKind(opt) === 'checkbox'"
                type="checkbox"
                :checked="Boolean(values[opt.name])"
                class="h-4 w-4 rounded border-surface-1 text-primary focus:ring-primary/20"
                @change="setValue(opt, ($event.target as HTMLInputElement).checked)"
              />
              <!-- number suelto -->
              <input
                v-else-if="inputKind(opt) === 'number'"
                type="number"
                :value="values[opt.name]"
                class="w-full rounded-md border border-surface-1 bg-base px-3 py-2 text-[13px] text-text focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                @input="setValue(opt, ($event.target as HTMLInputElement).value)"
              />
              <!-- text -->
              <input
                v-else
                type="text"
                :value="values[opt.name]"
                class="w-full rounded-md border border-surface-1 bg-base px-3 py-2 text-[13px] text-text focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                @input="setValue(opt, ($event.target as HTMLInputElement).value)"
              />
            </div>
          </div>
        </section>

        <!-- Avanzadas (colapsable) -->
        <section
          v-if="!loading && !error && advancedOptions.length > 0"
          data-testid="advanced"
          class="space-y-3 border-t border-surface-0 pt-4"
        >
          <button
            data-testid="advanced-toggle"
            type="button"
            class="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-subtext hover:text-text transition-colors"
            @click="advancedExpanded = !advancedExpanded"
          >
            <span>{{ advancedExpanded ? '▾' : '▸' }}</span>
            <span>Avanzadas ({{ advancedOptions.length }})</span>
          </button>
          <div v-if="advancedExpanded" data-testid="advanced-body" class="space-y-4">
            <div
              v-for="opt in advancedOptions"
              :key="opt.name"
              :data-testid="`opt-${opt.name}`"
              class="grid grid-cols-1 md:grid-cols-[200px_1fr] gap-2 md:items-center"
            >
              <label class="text-sm text-text" :title="opt.description">
                {{ opt.title || opt.name }}
                <span v-if="opt.unit" class="text-xs text-subtext">({{ opt.unit }})</span>
              </label>
              <div>
                <select
                  v-if="inputKind(opt) === 'select'"
                  :value="values[opt.name]"
                  class="w-full rounded-md border border-surface-1 bg-base px-3 py-2 text-[13px] text-text focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                  @change="setValue(opt, ($event.target as HTMLSelectElement).value)"
                >
                  <option v-for="v in (opt.constraint as (string | number)[])" :key="String(v)" :value="v">
                    {{ v }}
                  </option>
                </select>
                <div v-else-if="inputKind(opt) === 'range'" class="flex items-center gap-3">
                  <input
                    type="range"
                    :min="(opt.constraint as [number, number, number])[0]"
                    :max="(opt.constraint as [number, number, number])[1]"
                    :step="(opt.constraint as [number, number, number])[2]"
                    :value="values[opt.name]"
                    class="flex-1"
                    @input="setValue(opt, ($event.target as HTMLInputElement).value)"
                  />
                  <input
                    type="number"
                    :min="(opt.constraint as [number, number, number])[0]"
                    :max="(opt.constraint as [number, number, number])[1]"
                    :step="(opt.constraint as [number, number, number])[2]"
                    :value="values[opt.name]"
                    class="w-24 rounded-md border border-surface-1 bg-base px-2 py-1.5 text-[13px] text-text focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                    @input="setValue(opt, ($event.target as HTMLInputElement).value)"
                  />
                </div>
                <input
                  v-else-if="inputKind(opt) === 'checkbox'"
                  type="checkbox"
                  :checked="Boolean(values[opt.name])"
                  class="h-4 w-4 rounded border-surface-1 text-primary focus:ring-primary/20"
                  @change="setValue(opt, ($event.target as HTMLInputElement).checked)"
                />
                <input
                  v-else-if="inputKind(opt) === 'number'"
                  type="number"
                  :value="values[opt.name]"
                  class="w-full rounded-md border border-surface-1 bg-base px-3 py-2 text-[13px] text-text focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                  @input="setValue(opt, ($event.target as HTMLInputElement).value)"
                />
                <input
                  v-else
                  type="text"
                  :value="values[opt.name]"
                  class="w-full rounded-md border border-surface-1 bg-base px-3 py-2 text-[13px] text-text focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                  @input="setValue(opt, ($event.target as HTMLInputElement).value)"
                />
              </div>
            </div>
          </div>
        </section>
      </div>

      <footer class="px-6 py-4 border-t border-surface-0 flex items-center justify-between gap-2">
        <button
          v-if="canSaveDefaults"
          data-testid="save-defaults"
          type="button"
          class="px-3 py-2 text-[13px] font-medium text-subtext hover:text-text border border-surface-1 rounded-md hover:bg-surface-0 transition-colors"
          :disabled="loading || !!error"
          @click="onSaveDefaults"
        >Recordar para esta aplicación</button>
        <span v-else></span>
        <div class="flex gap-2">
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
            :disabled="loading || !!error"
            @click="onSubmit"
          >Escanear</button>
        </div>
      </footer>
    </div>
  </div>
</template>
