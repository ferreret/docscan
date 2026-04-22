<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, onBeforeRouteLeave } from 'vue-router'
import { useApplicationsStore } from '@/stores/applications'
import AppHeader from '@/components/AppHeader.vue'

// ---- tipos ----

type ImageFormat = 'tiff' | 'png' | 'jpg' | 'pdf'
type ColorMode = 'color' | 'grayscale' | 'bw'
type TiffCompression = 'none' | 'lzw' | 'zip' | 'group4'

interface ImageConfig {
  format: ImageFormat
  color_mode: ColorMode
  jpeg_quality: number
  tiff_compression: TiffCompression
  png_compression: number
  bw_threshold: number
}

const DEFAULTS: ImageConfig = {
  format: 'tiff',
  color_mode: 'color',
  jpeg_quality: 85,
  tiff_compression: 'lzw',
  png_compression: 6,
  bw_threshold: 128,
}

// ---- estado ----

const route = useRoute()
const appStore = useApplicationsStore()

const appId = computed(() => Number(route.params.id))

const original = ref<ImageConfig>({ ...DEFAULTS })
const current = ref<ImageConfig>({ ...DEFAULTS })
const saving = ref(false)
const saveError = ref<string | null>(null)

// ---- visibilidad condicional ----

const showJpegQuality = computed(() => current.value.format === 'jpg')
const showTiffCompression = computed(() => current.value.format === 'tiff')
const showPngCompression = computed(() => current.value.format === 'png')
const showBwThreshold = computed(() => current.value.color_mode === 'bw')

// ---- hasChanges ----

const hasChanges = computed(() => {
  const keys = Object.keys(DEFAULTS) as (keyof ImageConfig)[]
  return keys.some((k) => (original.value[k] as unknown) !== (current.value[k] as unknown))
})

// ---- parseo ----

function parseImageConfigJson(raw: string): ImageConfig {
  try {
    const parsed = JSON.parse(raw || '{}')
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return { ...DEFAULTS, ...(parsed as Partial<ImageConfig>) }
    }
    return { ...DEFAULTS }
  } catch (err) {
    console.warn('[ImageConfigEditorView] image_config_json inválido, usando defaults', err)
    return { ...DEFAULTS }
  }
}

// ---- carga ----

async function loadFromStore(id: number): Promise<void> {
  await appStore.fetchOne(id)
  const parsed = parseImageConfigJson(appStore.current?.image_config_json ?? '{}')
  original.value = { ...parsed }
  current.value = { ...parsed }
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
  saving.value = true
  saveError.value = null
  try {
    await appStore.update(appId.value, {
      image_config_json: JSON.stringify(current.value),
    })
    original.value = { ...current.value }
  } catch (err) {
    saveError.value = (err as Error).message
  } finally {
    saving.value = false
  }
}

// ---- deshacer ----

function onUndo(): void {
  current.value = { ...original.value }
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
          data-test="undo-image-config"
          :disabled="!hasChanges"
          @click="onUndo"
          class="text-[13px] text-subtext hover:text-text border border-surface-0 rounded px-3 py-2 disabled:opacity-50"
        >
          Deshacer
        </button>
        <button
          type="button"
          data-test="save-image-config"
          :disabled="!hasChanges || saving"
          @click="onSave"
          class="text-[13px] bg-primary text-base rounded-md px-4 py-2 font-semibold hover:bg-primary-hover disabled:opacity-50"
        >
          {{ saving ? 'Guardando...' : 'Guardar cambios' }}
        </button>
      </template>
    </AppHeader>

    <div v-if="saveError" class="mb-4 p-3 bg-danger-soft border border-danger/30 rounded text-sm text-danger">
      {{ saveError }}
    </div>

    <div class="bg-base rounded-md border border-surface-0 p-6 max-w-lg">
      <h2 class="text-sm font-semibold uppercase tracking-wide text-subtext mb-4">Configuración de imagen</h2>

      <div class="space-y-5">

        <!-- Formato -->
        <div>
          <label for="img-format" class="block text-sm font-medium text-text mb-1">Formato</label>
          <select
            id="img-format"
            v-model="current.format"
            data-test="select-format"
            class="w-full rounded border border-surface-0 bg-base px-3 py-2 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary"
          >
            <option value="tiff">TIFF</option>
            <option value="png">PNG</option>
            <option value="jpg">JPEG</option>
            <option value="pdf">PDF</option>
          </select>
        </div>

        <!-- Modo de color -->
        <div>
          <label for="img-color-mode" class="block text-sm font-medium text-text mb-1">Modo de color</label>
          <select
            id="img-color-mode"
            v-model="current.color_mode"
            data-test="select-color-mode"
            class="w-full rounded border border-surface-0 bg-base px-3 py-2 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary"
          >
            <option value="color">Color</option>
            <option value="grayscale">Escala de grises</option>
            <option value="bw">Blanco y negro</option>
          </select>
        </div>

        <!-- Calidad JPEG (solo si format=jpg) -->
        <div v-if="showJpegQuality" data-test="section-jpeg-quality">
          <label for="img-jpeg-quality" class="block text-sm font-medium text-text mb-1">
            Calidad JPEG
            <span class="ml-1 font-mono text-primary">{{ current.jpeg_quality }}</span>
          </label>
          <input
            id="img-jpeg-quality"
            v-model.number="current.jpeg_quality"
            data-test="slider-jpeg-quality"
            type="range"
            min="1"
            max="100"
            class="w-full accent-primary"
          />
          <div class="flex justify-between text-xs text-subtext mt-0.5">
            <span>1</span><span>100</span>
          </div>
        </div>

        <!-- Compresión TIFF (solo si format=tiff) -->
        <div v-if="showTiffCompression" data-test="section-tiff-compression">
          <label for="img-tiff-compression" class="block text-sm font-medium text-text mb-1">Compresión TIFF</label>
          <select
            id="img-tiff-compression"
            v-model="current.tiff_compression"
            data-test="select-tiff-compression"
            class="w-full rounded border border-surface-0 bg-base px-3 py-2 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary"
          >
            <option value="none">Sin compresión</option>
            <option value="lzw">LZW</option>
            <option value="zip">ZIP / Deflate</option>
            <option value="group4">Group 4 (fax)</option>
          </select>
        </div>

        <!-- Compresión PNG (solo si format=png) -->
        <div v-if="showPngCompression" data-test="section-png-compression">
          <label for="img-png-compression" class="block text-sm font-medium text-text mb-1">
            Compresión PNG
            <span class="ml-1 font-mono text-primary">{{ current.png_compression }}</span>
          </label>
          <input
            id="img-png-compression"
            v-model.number="current.png_compression"
            data-test="slider-png-compression"
            type="range"
            min="0"
            max="9"
            class="w-full accent-primary"
          />
          <div class="flex justify-between text-xs text-subtext mt-0.5">
            <span>0</span><span>9</span>
          </div>
        </div>

        <!-- Umbral B/N (solo si color_mode=bw) -->
        <div v-if="showBwThreshold" data-test="section-bw-threshold">
          <label for="img-bw-threshold" class="block text-sm font-medium text-text mb-1">
            Umbral B/N
            <span class="ml-1 font-mono text-primary">{{ current.bw_threshold }}</span>
          </label>
          <input
            id="img-bw-threshold"
            v-model.number="current.bw_threshold"
            data-test="slider-bw-threshold"
            type="range"
            min="0"
            max="255"
            class="w-full accent-primary"
          />
          <div class="flex justify-between text-xs text-subtext mt-0.5">
            <span>0</span><span>255</span>
          </div>
        </div>

      </div>
    </div>
  </div>
  <div v-else class="text-sm text-subtext">Cargando...</div>
</template>
