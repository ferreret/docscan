<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, onBeforeRouteLeave } from 'vue-router'
import { useApplicationsStore } from '@/stores/applications'
import AppHeader from '@/components/AppHeader.vue'

// --- Tipos ---

type FieldType = 'texto' | 'fecha' | 'lista' | 'numerico'

interface TextoConfig {
  // Sin configuración adicional
}

interface FechaConfig {
  format?: string
}

interface ListaConfig {
  values: string[]
}

interface NumericoConfig {
  min?: number
  max?: number
  step?: number
}

type FieldConfig = TextoConfig | FechaConfig | ListaConfig | NumericoConfig

interface BatchField {
  label: string
  type: FieldType
  required: boolean
  config: FieldConfig
}

const DATE_FORMATS = ['dd/MM/yyyy', 'yyyy-MM-dd', 'dd-MM-yyyy', 'MM/dd/yyyy'] as const

const FIELD_TYPES: { value: FieldType; label: string }[] = [
  { value: 'texto', label: 'Texto' },
  { value: 'fecha', label: 'Fecha' },
  { value: 'lista', label: 'Lista' },
  { value: 'numerico', label: 'Numérico' },
]

// --- Store y ruta ---

const route = useRoute()
const appStore = useApplicationsStore()

const appId = computed(() => Number(route.params.id))

// --- Estado ---

const original = ref<BatchField[]>([])
const fields = ref<BatchField[]>([])
const saving = ref(false)
const saveError = ref<string | null>(null)

// --- Parseo ---

function parseFieldsJson(raw: string): BatchField[] {
  try {
    const parsed = JSON.parse(raw || '[]')
    if (!Array.isArray(parsed)) return []
    return parsed as BatchField[]
  } catch (err) {
    console.warn('[BatchFieldsEditorView] batch_fields_json inválido, usando []', err)
    return []
  }
}

function deepClone(arr: BatchField[]): BatchField[] {
  return JSON.parse(JSON.stringify(arr)) as BatchField[]
}

// --- hasChanges ---

const hasChanges = computed(() => {
  return JSON.stringify(fields.value) !== JSON.stringify(original.value)
})

// --- Helpers de config por tipo ---

function defaultConfig(type: FieldType): FieldConfig {
  if (type === 'lista') return { values: [] }
  if (type === 'numerico') return { min: 0, max: 100, step: 1 }
  if (type === 'fecha') return { format: 'dd/MM/yyyy' }
  return {}
}

function listValuesString(field: BatchField): string {
  const cfg = field.config as ListaConfig
  return (cfg.values ?? []).join(', ')
}

function setListValues(field: BatchField, raw: string): void {
  const values = raw
    .split(',')
    .map((v) => v.trim())
    .filter((v) => v.length > 0)
  ;(field.config as ListaConfig).values = values
}

function numCfg(field: BatchField): NumericoConfig {
  return field.config as NumericoConfig
}

function fechaCfg(field: BatchField): FechaConfig {
  return field.config as FechaConfig
}

// --- Acciones ---

function addField(): void {
  fields.value.push({ label: '', type: 'texto', required: false, config: {} })
}

function removeField(index: number): void {
  fields.value.splice(index, 1)
}

function moveUp(index: number): void {
  if (index === 0) return
  const arr = fields.value
  ;[arr[index - 1], arr[index]] = [arr[index], arr[index - 1]]
}

function moveDown(index: number): void {
  if (index >= fields.value.length - 1) return
  const arr = fields.value
  ;[arr[index], arr[index + 1]] = [arr[index + 1], arr[index]]
}

function onTypeChange(field: BatchField, newType: FieldType): void {
  field.type = newType
  field.config = defaultConfig(newType)
}

// --- Validación ---

const validationError = computed(() => {
  const empty = fields.value.some((f) => !f.label.trim())
  if (empty) return 'Hay campos sin etiqueta. Rellena o elimina las filas incompletas antes de guardar.'
  return null
})

// --- Guardar ---

async function save(): Promise<void> {
  if (validationError.value) {
    saveError.value = validationError.value
    return
  }
  saving.value = true
  saveError.value = null
  try {
    await appStore.update(appId.value, {
      batch_fields_json: JSON.stringify(fields.value),
    })
    original.value = deepClone(fields.value)
  } catch (err) {
    saveError.value = (err as Error).message
  } finally {
    saving.value = false
  }
}

function onUndo(): void {
  fields.value = deepClone(original.value)
}

// --- Guards de navegación ---

function onBeforeUnload(ev: BeforeUnloadEvent): void {
  if (hasChanges.value) {
    ev.preventDefault()
    ev.returnValue = ''
  }
}

onMounted(() => {
  window.addEventListener('beforeunload', onBeforeUnload)
})

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', onBeforeUnload)
})

onBeforeRouteLeave((_to, _from, next) => {
  if (!hasChanges.value) return next()
  if (confirm('Hay cambios sin guardar. ¿Salir igualmente?')) return next()
  next(false)
})

// --- Carga ---

async function loadFromStore(id: number): Promise<void> {
  await appStore.fetchOne(id)
  const parsed = parseFieldsJson(appStore.current?.batch_fields_json ?? '[]')
  original.value = deepClone(parsed)
  fields.value = deepClone(parsed)
}

watch(
  appId,
  async (id) => {
    if (typeof id === 'number' && !Number.isNaN(id)) {
      await loadFromStore(id)
    }
  },
  { immediate: true },
)
</script>

<template>
  <div v-if="appStore.current">
    <AppHeader
      :app-id="appId"
      :app-name="appStore.current.name"
      :description="appStore.current.description || undefined"
    >
      <template #actions>
        <span v-if="hasChanges" class="text-xs text-warning">● sin guardar</span>
        <button
          type="button"
          data-test="add-field"
          @click="addField"
          class="text-[13px] text-subtext hover:text-text border border-surface-0 rounded px-3 py-2"
        >
          + Añadir campo
        </button>
        <button
          type="button"
          data-test="undo-fields"
          :disabled="!hasChanges"
          @click="onUndo"
          class="text-[13px] text-subtext hover:text-text border border-surface-0 rounded px-3 py-2 disabled:opacity-50"
        >
          Deshacer
        </button>
        <button
          type="button"
          data-test="save-fields"
          :disabled="!hasChanges || saving"
          @click="save"
          class="text-[13px] bg-primary text-white rounded-md px-4 py-2 font-semibold hover:bg-primary-hover disabled:opacity-50"
        >
          {{ saving ? 'Guardando...' : 'Guardar cambios' }}
        </button>
      </template>
    </AppHeader>

    <!-- Error de validación o de API -->
    <div
      v-if="saveError"
      data-test="save-error"
      class="mb-4 p-3 bg-red-50 border border-red-200 rounded text-sm text-danger"
    >
      {{ saveError }}
    </div>

    <!-- Tabla de campos -->
    <div v-if="fields.length > 0" class="bg-white rounded-md border border-surface-0 overflow-hidden">
      <table class="w-full text-[13px]">
        <thead>
          <tr class="bg-surface-0 border-b border-surface-0">
            <th class="text-left px-3 py-2 font-medium text-subtext w-1/4">Etiqueta</th>
            <th class="text-left px-3 py-2 font-medium text-subtext w-28">Tipo</th>
            <th class="text-left px-3 py-2 font-medium text-subtext">Configuración</th>
            <th class="text-center px-3 py-2 font-medium text-subtext w-24">Obligatorio</th>
            <th class="text-center px-3 py-2 font-medium text-subtext w-28">Acciones</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(field, index) in fields"
            :key="index"
            data-test="field-row"
            class="border-b border-surface-0 last:border-b-0 hover:bg-surface-0/40"
          >
            <!-- Etiqueta -->
            <td class="px-3 py-2">
              <input
                v-model="field.label"
                type="text"
                data-test="field-label"
                placeholder="Nombre del campo..."
                aria-label="Etiqueta del campo"
                class="w-full rounded border border-surface-0 px-2 py-1 text-[13px] text-text focus:outline-none focus:border-primary"
              />
            </td>

            <!-- Tipo -->
            <td class="px-3 py-2">
              <select
                :value="field.type"
                data-test="field-type"
                aria-label="Tipo de campo"
                class="w-full rounded border border-surface-0 px-2 py-1 text-[13px] text-text focus:outline-none focus:border-primary bg-white"
                @change="onTypeChange(field, ($event.target as HTMLSelectElement).value as FieldType)"
              >
                <option
                  v-for="ft in FIELD_TYPES"
                  :key="ft.value"
                  :value="ft.value"
                >{{ ft.label }}</option>
              </select>
            </td>

            <!-- Configuración (varía por tipo) -->
            <td class="px-3 py-2">
              <!-- Texto: sin config -->
              <span
                v-if="field.type === 'texto'"
                class="text-subtext italic"
              >Sin configuración adicional</span>

              <!-- Fecha: selector de formato -->
              <div v-else-if="field.type === 'fecha'" class="flex items-center gap-2">
                <label class="text-subtext whitespace-nowrap">Formato:</label>
                <select
                  v-model="(fechaCfg(field)).format"
                  data-test="field-date-format"
                  aria-label="Formato de fecha"
                  class="rounded border border-surface-0 px-2 py-1 text-[13px] text-text focus:outline-none focus:border-primary bg-white"
                >
                  <option v-for="fmt in DATE_FORMATS" :key="fmt" :value="fmt">{{ fmt }}</option>
                </select>
              </div>

              <!-- Lista: valores separados por coma -->
              <div v-else-if="field.type === 'lista'" class="flex items-center gap-2">
                <label class="text-subtext whitespace-nowrap">Valores:</label>
                <input
                  type="text"
                  data-test="field-list-values"
                  :value="listValuesString(field)"
                  placeholder="valor1, valor2, valor3..."
                  aria-label="Valores de la lista separados por coma"
                  class="flex-1 rounded border border-surface-0 px-2 py-1 text-[13px] text-text focus:outline-none focus:border-primary"
                  @input="setListValues(field, ($event.target as HTMLInputElement).value)"
                />
              </div>

              <!-- Numérico: min, max, step -->
              <div v-else-if="field.type === 'numerico'" class="flex items-center gap-2 flex-wrap">
                <label class="text-subtext">Mín:</label>
                <input
                  v-model.number="(numCfg(field)).min"
                  type="number"
                  data-test="field-num-min"
                  aria-label="Valor mínimo"
                  class="w-16 rounded border border-surface-0 px-2 py-1 text-[13px] text-text focus:outline-none focus:border-primary"
                />
                <label class="text-subtext">Máx:</label>
                <input
                  v-model.number="(numCfg(field)).max"
                  type="number"
                  data-test="field-num-max"
                  aria-label="Valor máximo"
                  class="w-16 rounded border border-surface-0 px-2 py-1 text-[13px] text-text focus:outline-none focus:border-primary"
                />
                <label class="text-subtext">Paso:</label>
                <input
                  v-model.number="(numCfg(field)).step"
                  type="number"
                  data-test="field-num-step"
                  min="1"
                  aria-label="Paso"
                  class="w-14 rounded border border-surface-0 px-2 py-1 text-[13px] text-text focus:outline-none focus:border-primary"
                />
              </div>
            </td>

            <!-- Obligatorio -->
            <td class="px-3 py-2 text-center">
              <input
                v-model="field.required"
                type="checkbox"
                data-test="field-required"
                aria-label="Campo obligatorio"
                class="w-4 h-4 rounded accent-primary cursor-pointer"
              />
            </td>

            <!-- Acciones -->
            <td class="px-3 py-2">
              <div class="flex items-center justify-center gap-1">
                <button
                  type="button"
                  data-test="move-up"
                  :disabled="index === 0"
                  :aria-label="`Subir campo ${field.label || index + 1}`"
                  @click="moveUp(index)"
                  class="w-7 h-7 flex items-center justify-center rounded border border-surface-0 text-subtext hover:text-text hover:bg-surface-0 disabled:opacity-30 disabled:cursor-not-allowed"
                >↑</button>
                <button
                  type="button"
                  data-test="move-down"
                  :disabled="index === fields.length - 1"
                  :aria-label="`Bajar campo ${field.label || index + 1}`"
                  @click="moveDown(index)"
                  class="w-7 h-7 flex items-center justify-center rounded border border-surface-0 text-subtext hover:text-text hover:bg-surface-0 disabled:opacity-30 disabled:cursor-not-allowed"
                >↓</button>
                <button
                  type="button"
                  data-test="remove-field"
                  :aria-label="`Eliminar campo ${field.label || index + 1}`"
                  @click="removeField(index)"
                  class="w-7 h-7 flex items-center justify-center rounded border border-surface-0 text-danger hover:bg-red-50 hover:border-red-200"
                >✕</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Empty state -->
    <div
      v-else
      data-test="empty-state"
      class="flex flex-col items-center justify-center py-16 text-subtext bg-white rounded-md border border-surface-0 border-dashed"
    >
      <svg class="w-12 h-12 mb-3 text-surface-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
      </svg>
      <p class="text-sm font-medium">Sin campos de lote</p>
      <p class="text-xs mt-1">Pulsa «+ Añadir campo» para definir el primer campo.</p>
    </div>
  </div>

  <div v-else class="text-sm text-subtext">Cargando...</div>
</template>
