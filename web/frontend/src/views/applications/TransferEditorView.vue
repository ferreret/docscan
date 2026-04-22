<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, onBeforeRouteLeave } from 'vue-router'
import { useApplicationsStore } from '@/stores/applications'
import AppHeader from '@/components/AppHeader.vue'

// ---- tipos ----

type TransferMode = 'folder' | 'pdf' | 'pdfa' | 'csv'

interface TransferConfig {
  standard_enabled: boolean
  mode: TransferMode
  destination: string
  filename_pattern: string
  create_subdirs: boolean
  collision_policy: 'suffix' | 'overwrite' | 'merge'
  pdf_dpi: number
  csv_separator: string
  csv_fields: string[]
  include_metadata: boolean
  output_format: string
  output_dpi: number
  output_color_mode: string
  output_jpeg_quality: number
  output_tiff_compression: string
  output_png_compression: number
  output_bw_threshold: number
  pdf_jpeg_quality: number
}

const DEFAULTS: TransferConfig = {
  standard_enabled: true,
  mode: 'folder',
  destination: '',
  filename_pattern: '{batch_id}_{page_index:04d}',
  create_subdirs: true,
  collision_policy: 'suffix',
  pdf_dpi: 200,
  csv_separator: ';',
  csv_fields: [],
  include_metadata: false,
  output_format: '',
  output_dpi: 0,
  output_color_mode: '',
  output_jpeg_quality: 85,
  output_tiff_compression: 'lzw',
  output_png_compression: 6,
  output_bw_threshold: 128,
  pdf_jpeg_quality: 85,
}

// ---- estado ----

const route = useRoute()
const appStore = useApplicationsStore()

const appId = computed(() => Number(route.params.id))

const original = ref<TransferConfig>({ ...DEFAULTS, csv_fields: [] })
const current = ref<TransferConfig>({ ...DEFAULTS, csv_fields: [] })
const saving = ref(false)
const saveError = ref<string | null>(null)
const newCsvField = ref('')

// ---- visibilidad condicional ----

const isFolder = computed(() => current.value.mode === 'folder')
const isPdf = computed(() => current.value.mode === 'pdf' || current.value.mode === 'pdfa')
const isCsv = computed(() => current.value.mode === 'csv')
const showJpegQuality = computed(() => isFolder.value && current.value.output_format === 'jpg')

// ---- validación ----

const destinationError = computed(() =>
  current.value.destination.trim() === '' ? 'El destino es obligatorio.' : null,
)

// ---- hasChanges ----

const hasChanges = computed(() => {
  const keys = Object.keys(DEFAULTS) as (keyof TransferConfig)[]
  return keys.some((k) => {
    if (k === 'csv_fields') {
      const a = JSON.stringify(original.value.csv_fields)
      const b = JSON.stringify(current.value.csv_fields)
      return a !== b
    }
    return (original.value[k] as unknown) !== (current.value[k] as unknown)
  })
})

// ---- parseo ----

function parseTransferJson(raw: string): TransferConfig {
  try {
    const parsed = JSON.parse(raw || '{}')
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return {
        ...DEFAULTS,
        ...(parsed as Partial<TransferConfig>),
        csv_fields: Array.isArray(parsed.csv_fields) ? [...parsed.csv_fields] : [],
      }
    }
    return { ...DEFAULTS, csv_fields: [] }
  } catch (err) {
    console.warn('[TransferEditorView] transfer_json inválido, usando defaults', err)
    return { ...DEFAULTS, csv_fields: [] }
  }
}

// ---- carga ----

async function loadFromStore(id: number): Promise<void> {
  await appStore.fetchOne(id)
  const parsed = parseTransferJson(appStore.current?.transfer_json ?? '{}')
  original.value = { ...parsed, csv_fields: [...parsed.csv_fields] }
  current.value = { ...parsed, csv_fields: [...parsed.csv_fields] }
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

// ---- guardar ----

async function onSave(): Promise<void> {
  if (destinationError.value) return
  saving.value = true
  saveError.value = null
  try {
    await appStore.update(appId.value, {
      transfer_json: JSON.stringify(current.value),
    })
    original.value = { ...current.value, csv_fields: [...current.value.csv_fields] }
  } catch (err) {
    saveError.value = (err as Error).message
  } finally {
    saving.value = false
  }
}

// ---- deshacer ----

function onUndo(): void {
  current.value = { ...original.value, csv_fields: [...original.value.csv_fields] }
}

// ---- csv_fields lista ----

function addCsvField(): void {
  const trimmed = newCsvField.value.trim()
  if (!trimmed || current.value.csv_fields.includes(trimmed)) return
  current.value = { ...current.value, csv_fields: [...current.value.csv_fields, trimmed] }
  newCsvField.value = ''
}

function removeCsvField(index: number): void {
  const fields = [...current.value.csv_fields]
  fields.splice(index, 1)
  current.value = { ...current.value, csv_fields: fields }
}

// ---- guards ----

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
          data-test="undo-transfer"
          :disabled="!hasChanges"
          @click="onUndo"
          class="text-[13px] text-subtext hover:text-text border border-surface-0 rounded px-3 py-2 disabled:opacity-50"
        >
          Deshacer
        </button>
        <button
          type="button"
          data-test="save-transfer"
          :disabled="!hasChanges || !!destinationError || saving"
          @click="onSave"
          class="text-[13px] bg-primary text-white rounded-md px-4 py-2 font-semibold hover:bg-primary-hover disabled:opacity-50"
        >
          {{ saving ? 'Guardando...' : 'Guardar cambios' }}
        </button>
      </template>
    </AppHeader>

    <div v-if="saveError" class="mb-4 p-3 bg-red-50 border border-red-200 rounded text-sm text-danger">
      {{ saveError }}
    </div>

    <div
      class="bg-white rounded-md border border-surface-0 p-6 max-w-2xl space-y-6"
      :class="{ 'opacity-100': true }"
    >
      <h2 class="text-sm font-semibold uppercase tracking-wide text-subtext">Configuración de transferencia</h2>

      <!-- standard_enabled: siempre visible y prominente -->
      <div
        class="flex items-start gap-3 p-3 rounded-md border"
        :class="current.standard_enabled ? 'border-success/40 bg-success-soft' : 'border-surface-0 bg-crust'"
      >
        <input
          id="field-standard-enabled"
          v-model="current.standard_enabled"
          type="checkbox"
          data-test="field-standard-enabled"
          class="mt-0.5 h-4 w-4 rounded border-surface-0 text-primary focus:ring-primary"
          aria-label="Transferencia estándar habilitada"
        />
        <div>
          <label for="field-standard-enabled" class="text-sm font-semibold text-text cursor-pointer">
            Transferencia estándar habilitada
          </label>
          <p class="text-xs text-subtext mt-0.5">
            Si está desactivada, solo se ejecuta <code class="font-mono">on_transfer_advanced</code>.
          </p>
        </div>
      </div>

      <!-- Sección dinámica: atenuada visualmente si standard_enabled=false -->
      <div
        data-test="transfer-form-body"
        :class="{ 'opacity-50 pointer-events-none': !current.standard_enabled }"
        class="space-y-5 transition-opacity"
        :aria-disabled="!current.standard_enabled"
      >

        <!-- Modo -->
        <div>
          <label for="field-mode" class="block text-sm font-medium text-text mb-1">Modo de transferencia</label>
          <select
            id="field-mode"
            v-model="current.mode"
            data-test="field-mode"
            class="w-full rounded border border-surface-0 bg-white px-3 py-2 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary"
          >
            <option value="folder">Carpeta (imágenes)</option>
            <option value="pdf">PDF</option>
            <option value="pdfa">PDF/A</option>
            <option value="csv">CSV</option>
          </select>
        </div>

        <!-- Destino: siempre visible -->
        <div>
          <label for="field-destination" class="block text-sm font-medium text-text mb-1">
            Destino <span class="text-danger" aria-hidden="true">*</span>
          </label>
          <input
            id="field-destination"
            v-model="current.destination"
            type="text"
            data-test="field-destination"
            placeholder="/ruta/absoluta/destino"
            class="w-full rounded border px-3 py-2 text-sm text-text placeholder:text-subtext focus:outline-none focus:ring-2 focus:ring-primary"
            :class="destinationError ? 'border-danger focus:ring-danger' : 'border-surface-0'"
            aria-required="true"
            :aria-invalid="destinationError ? 'true' : undefined"
            :aria-describedby="destinationError ? 'destination-error' : undefined"
          />
          <p
            v-if="destinationError"
            id="destination-error"
            data-test="destination-error"
            class="mt-1 text-xs text-danger"
            role="alert"
          >
            {{ destinationError }}
          </p>
        </div>

        <!-- Patrón de nombre de fichero: folder, pdf, pdfa, csv -->
        <div data-test="section-filename-pattern">
          <label for="field-filename-pattern" class="block text-sm font-medium text-text mb-1">
            Patrón de nombre de fichero
          </label>
          <input
            id="field-filename-pattern"
            v-model="current.filename_pattern"
            type="text"
            data-test="field-filename-pattern"
            placeholder="{batch_id}_{page_index:04d}"
            class="w-full rounded border border-surface-0 px-3 py-2 text-sm font-mono text-text placeholder:text-subtext focus:outline-none focus:ring-2 focus:ring-primary"
          />
          <p class="mt-1 text-xs text-subtext">Variables: <code class="font-mono">{batch_id}</code>, <code class="font-mono">{page_index}</code>, <code class="font-mono">{first_barcode}</code></p>
        </div>

        <!-- Política de colisión: folder, pdf, pdfa, csv -->
        <div data-test="section-collision-policy">
          <label for="field-collision-policy" class="block text-sm font-medium text-text mb-1">Política de colisión</label>
          <select
            id="field-collision-policy"
            v-model="current.collision_policy"
            data-test="field-collision-policy"
            class="w-full rounded border border-surface-0 bg-white px-3 py-2 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary"
          >
            <option value="suffix">Añadir sufijo numérico</option>
            <option value="overwrite">Sobreescribir</option>
            <option value="merge">Fusionar (multi-página)</option>
          </select>
        </div>

        <!-- ---- Campos solo modo FOLDER ---- -->
        <template v-if="isFolder">

          <!-- Formato de salida -->
          <div data-test="section-output-format">
            <label for="field-output-format" class="block text-sm font-medium text-text mb-1">Formato de salida</label>
            <select
              id="field-output-format"
              v-model="current.output_format"
              data-test="field-output-format"
              class="w-full rounded border border-surface-0 bg-white px-3 py-2 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="">Original (sin convertir)</option>
              <option value="tiff">TIFF</option>
              <option value="png">PNG</option>
              <option value="jpg">JPEG</option>
              <option value="pdf">PDF</option>
            </select>
          </div>

          <!-- DPI de salida -->
          <div data-test="section-output-dpi">
            <label for="field-output-dpi" class="block text-sm font-medium text-text mb-1">
              DPI de salida
              <span class="ml-1 font-mono text-primary text-xs">{{ current.output_dpi === 0 ? 'original' : current.output_dpi }}</span>
            </label>
            <input
              id="field-output-dpi"
              v-model.number="current.output_dpi"
              type="number"
              data-test="field-output-dpi"
              min="0"
              max="1200"
              step="50"
              class="w-full rounded border border-surface-0 px-3 py-2 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary"
            />
            <p class="mt-1 text-xs text-subtext">0 = mantener DPI original</p>
          </div>

          <!-- Modo de color de salida -->
          <div data-test="section-output-color-mode">
            <label for="field-output-color-mode" class="block text-sm font-medium text-text mb-1">Modo de color de salida</label>
            <select
              id="field-output-color-mode"
              v-model="current.output_color_mode"
              data-test="field-output-color-mode"
              class="w-full rounded border border-surface-0 bg-white px-3 py-2 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="">Original (sin convertir)</option>
              <option value="color">Color</option>
              <option value="grayscale">Escala de grises</option>
              <option value="bw">Blanco y negro</option>
            </select>
          </div>

          <!-- Calidad JPEG (solo si output_format=jpg) -->
          <div v-if="showJpegQuality" data-test="section-jpeg-quality">
            <label for="field-output-jpeg-quality" class="block text-sm font-medium text-text mb-1">
              Calidad JPEG
              <span class="ml-1 font-mono text-primary">{{ current.output_jpeg_quality }}</span>
            </label>
            <input
              id="field-output-jpeg-quality"
              v-model.number="current.output_jpeg_quality"
              type="range"
              data-test="slider-jpeg-quality"
              min="1"
              max="100"
              class="w-full accent-primary"
            />
            <div class="flex justify-between text-xs text-subtext mt-0.5">
              <span>1</span><span>100</span>
            </div>
          </div>

          <!-- Crear subdirectorios -->
          <div class="flex items-center gap-3" data-test="section-create-subdirs">
            <input
              id="field-create-subdirs"
              v-model="current.create_subdirs"
              type="checkbox"
              data-test="field-create-subdirs"
              class="h-4 w-4 rounded border-surface-0 text-primary focus:ring-primary"
              aria-label="Crear subdirectorio batch_<id>"
            />
            <label for="field-create-subdirs" class="text-sm font-medium text-text cursor-pointer">
              Crear subdirectorio <code class="font-mono text-xs">batch_&lt;id&gt;/</code>
            </label>
          </div>

          <!-- Incluir metadatos -->
          <div class="flex items-center gap-3" data-test="section-include-metadata">
            <input
              id="field-include-metadata"
              v-model="current.include_metadata"
              type="checkbox"
              data-test="field-include-metadata"
              class="h-4 w-4 rounded border-surface-0 text-primary focus:ring-primary"
              aria-label="Incluir fichero .json de metadatos"
            />
            <label for="field-include-metadata" class="text-sm font-medium text-text cursor-pointer">
              Generar sidecar <code class="font-mono text-xs">.json</code> de metadatos
            </label>
          </div>

        </template>

        <!-- ---- Campos solo modo PDF / PDF/A ---- -->
        <template v-if="isPdf">

          <!-- DPI PDF -->
          <div data-test="section-pdf-dpi">
            <label for="field-pdf-dpi" class="block text-sm font-medium text-text mb-1">
              DPI del PDF
              <span class="ml-1 font-mono text-primary text-xs">{{ current.pdf_dpi }}</span>
            </label>
            <input
              id="field-pdf-dpi"
              v-model.number="current.pdf_dpi"
              type="range"
              data-test="slider-pdf-dpi"
              min="72"
              max="600"
              step="10"
              class="w-full accent-primary"
            />
            <div class="flex justify-between text-xs text-subtext mt-0.5">
              <span>72</span><span>600</span>
            </div>
          </div>

          <!-- Modo de color (PDF) -->
          <div data-test="section-pdf-color-mode">
            <label for="field-pdf-color-mode" class="block text-sm font-medium text-text mb-1">Modo de color de salida</label>
            <select
              id="field-pdf-color-mode"
              v-model="current.output_color_mode"
              data-test="field-pdf-color-mode"
              class="w-full rounded border border-surface-0 bg-white px-3 py-2 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="">Original (sin convertir)</option>
              <option value="color">Color</option>
              <option value="grayscale">Escala de grises</option>
              <option value="bw">Blanco y negro</option>
            </select>
          </div>

        </template>

        <!-- ---- Campos solo modo CSV ---- -->
        <template v-if="isCsv">

          <!-- Separador CSV -->
          <div data-test="section-csv-separator">
            <label for="field-csv-separator" class="block text-sm font-medium text-text mb-1">Separador CSV</label>
            <input
              id="field-csv-separator"
              v-model="current.csv_separator"
              type="text"
              data-test="field-csv-separator"
              maxlength="3"
              class="w-24 rounded border border-surface-0 px-3 py-2 text-sm font-mono text-text focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>

          <!-- Campos a exportar -->
          <div data-test="section-csv-fields">
            <p class="block text-sm font-medium text-text mb-2">Campos a exportar</p>
            <div class="space-y-1.5 mb-2">
              <div
                v-for="(field, index) in current.csv_fields"
                :key="index"
                class="flex items-center gap-2 bg-crust border border-surface-0 rounded px-2 py-1"
              >
                <span class="flex-1 text-sm font-mono text-text">{{ field }}</span>
                <button
                  type="button"
                  :data-test="`csv-field-remove-${index}`"
                  @click="removeCsvField(index)"
                  class="text-danger hover:text-danger/80 text-xs font-semibold px-1"
                  :aria-label="`Eliminar campo ${field}`"
                >
                  ×
                </button>
              </div>
              <div v-if="current.csv_fields.length === 0" class="text-xs text-subtext italic">
                Sin campos definidos — se auto-detectan desde los metadatos de cada página.
              </div>
            </div>
            <div class="flex gap-2">
              <input
                v-model="newCsvField"
                type="text"
                data-test="csv-field-input"
                placeholder="nombre_campo"
                class="flex-1 rounded border border-surface-0 px-3 py-1.5 text-sm font-mono text-text placeholder:text-subtext focus:outline-none focus:ring-2 focus:ring-primary"
                @keydown.enter.prevent="addCsvField"
              />
              <button
                type="button"
                data-test="csv-field-add"
                @click="addCsvField"
                class="text-[13px] bg-primary text-white rounded px-3 py-1.5 font-medium hover:bg-primary-hover"
              >
                Añadir
              </button>
            </div>
          </div>

        </template>

      </div>
    </div>
  </div>
  <div v-else class="text-sm text-subtext">Cargando...</div>
</template>
