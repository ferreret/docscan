<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useBatchesStore } from '@/stores/batches'
import { ApiError } from '@/api/client'
import AuthImage from '@/components/AuthImage.vue'

const route = useRoute()
const router = useRouter()
const store = useBatchesStore()

const batchId = computed(() => Number(route.params.id))
const uploading = ref(false)
const running = ref(false)
const error = ref<string | null>(null)
const selectedPage = ref<number | null>(null)

onMounted(async () => {
  await store.fetchOne(batchId.value)
  await store.fetchPages(batchId.value)
})

async function onUpload(event: Event) {
  const input = event.target as HTMLInputElement
  if (!input.files?.length) return
  uploading.value = true
  error.value = null
  try {
    await store.uploadFiles(batchId.value, Array.from(input.files))
    await store.fetchOne(batchId.value)
  } catch (e) {
    error.value = e instanceof ApiError ? e.detail : 'Error al subir ficheros'
  } finally {
    uploading.value = false
    input.value = ''
  }
}

async function onRunPipeline() {
  running.value = true
  error.value = null
  try {
    await store.runPipeline(batchId.value)
    // Polling simple para actualizar estado
    setTimeout(async () => {
      await store.fetchOne(batchId.value)
      await store.fetchPages(batchId.value)
      running.value = false
    }, 3000)
  } catch (e) {
    error.value = e instanceof ApiError ? e.detail : 'Error al ejecutar pipeline'
    running.value = false
  }
}

async function onDeletePage(pageId: number) {
  await store.deletePage(batchId.value, pageId)
  await store.fetchOne(batchId.value)
  if (selectedPage.value === pageId) selectedPage.value = null
}

async function onDelete() {
  if (!confirm('¿Eliminar este lote y todas sus páginas?')) return
  await store.remove(batchId.value)
  router.push('/batches')
}

function selectPage(pageId: number) {
  selectedPage.value = selectedPage.value === pageId ? null : pageId
  if (selectedPage.value) {
    store.fetchPage(batchId.value, pageId)
  }
}
</script>

<template>
  <div v-if="store.current">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <button @click="router.back()" class="text-sm text-gray-500 hover:text-gray-700 mb-2 inline-flex items-center gap-1">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" /></svg>
          Volver
        </button>
        <h1 class="text-2xl font-bold text-gray-900">Lote #{{ store.current.id }}</h1>
      </div>
      <div class="flex gap-3">
        <label class="bg-white border border-gray-300 text-gray-700 rounded-lg px-4 py-2 text-sm font-medium hover:bg-gray-50 cursor-pointer transition-colors">
          {{ uploading ? 'Subiendo...' : 'Subir ficheros' }}
          <input type="file" multiple accept=".jpg,.jpeg,.png,.bmp,.tif,.tiff,.pdf" class="hidden" @change="onUpload" :disabled="uploading" />
        </label>
        <button
          @click="onRunPipeline"
          :disabled="running || store.current.page_count === 0"
          class="bg-green-600 text-white rounded-lg px-4 py-2 text-sm font-medium hover:bg-green-700 disabled:opacity-50 transition-colors"
        >
          {{ running ? 'Procesando...' : 'Ejecutar pipeline' }}
        </button>
        <button @click="onDelete" class="text-red-600 hover:text-red-700 rounded-lg px-4 py-2 text-sm font-medium hover:bg-red-50 transition-colors">
          Eliminar
        </button>
      </div>
    </div>

    <div v-if="error" class="text-sm text-red-600 bg-red-50 rounded-lg px-4 py-2 mb-4">{{ error }}</div>

    <!-- Info -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <div class="bg-white rounded-xl border border-gray-200 p-4">
        <p class="text-xs text-gray-500">Estado</p>
        <p class="text-sm font-medium mt-1" :class="{
          'text-yellow-600': store.current.state === 'created',
          'text-blue-600': store.current.state === 'read',
          'text-red-600': store.current.state.startsWith('error'),
        }">{{ store.current.state }}</p>
      </div>
      <div class="bg-white rounded-xl border border-gray-200 p-4">
        <p class="text-xs text-gray-500">Páginas</p>
        <p class="text-sm font-medium mt-1">{{ store.current.page_count }}</p>
      </div>
      <div class="bg-white rounded-xl border border-gray-200 p-4">
        <p class="text-xs text-gray-500">Aplicación</p>
        <p class="text-sm font-medium mt-1">#{{ store.current.application_id }}</p>
      </div>
      <div class="bg-white rounded-xl border border-gray-200 p-4">
        <p class="text-xs text-gray-500">Creado</p>
        <p class="text-sm font-medium mt-1">{{ new Date(store.current.created_at).toLocaleString('es-ES') }}</p>
      </div>
    </div>

    <!-- Thumbnails + Detail -->
    <div class="flex gap-6">
      <!-- Thumbnails grid -->
      <div class="flex-1">
        <div v-if="store.pages.length === 0" class="bg-white rounded-xl border border-gray-200 p-12 text-center">
          <p class="text-gray-500">Sin páginas. Sube imágenes o PDFs para empezar.</p>
        </div>
        <div v-else class="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
          <div
            v-for="page in store.pages"
            :key="page.id"
            @click="selectPage(page.id)"
            class="relative bg-white rounded-lg border-2 overflow-hidden cursor-pointer transition-all hover:shadow-md"
            :class="selectedPage === page.id ? 'border-blue-500 shadow-md' : 'border-gray-200'"
          >
            <AuthImage
              :url="store.pageImageUrl(batchId, page.id)"
              :alt="`Página ${page.page_index + 1}`"
              class="w-full aspect-[3/4] object-cover"
            />
            <div class="absolute bottom-0 left-0 right-0 bg-black/60 text-white text-xs px-2 py-1 flex justify-between">
              <span>{{ page.page_index + 1 }}</span>
              <div class="flex gap-1">
                <span v-if="page.needs_review" class="text-yellow-300" title="Requiere revisión">!</span>
                <span v-if="page.pipeline_processed" class="text-green-300" title="Procesada">&#10003;</span>
              </div>
            </div>
            <button
              @click.stop="onDeletePage(page.id)"
              class="absolute top-1 right-1 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs opacity-0 hover:opacity-100 transition-opacity"
              title="Eliminar"
            >
              &times;
            </button>
          </div>
        </div>
      </div>

      <!-- Detail panel -->
      <div v-if="selectedPage && store.currentPage" class="w-80 shrink-0">
        <div class="bg-white rounded-xl border border-gray-200 p-4 space-y-4 sticky top-8">
          <h3 class="font-semibold text-gray-900">Página {{ store.currentPage.page_index + 1 }}</h3>

          <div v-if="store.currentPage.ocr_text" class="space-y-1">
            <p class="text-xs font-medium text-gray-500">OCR</p>
            <p class="text-sm text-gray-700 bg-gray-50 rounded-lg p-3 max-h-40 overflow-auto whitespace-pre-wrap">{{ store.currentPage.ocr_text }}</p>
          </div>

          <div v-if="store.currentPage.index_fields_json && store.currentPage.index_fields_json !== '{}'" class="space-y-1">
            <p class="text-xs font-medium text-gray-500">Campos</p>
            <pre class="text-xs text-gray-700 bg-gray-50 rounded-lg p-3 max-h-40 overflow-auto">{{ JSON.stringify(JSON.parse(store.currentPage.index_fields_json), null, 2) }}</pre>
          </div>

          <div class="space-y-1">
            <p class="text-xs font-medium text-gray-500">Estado</p>
            <div class="flex flex-wrap gap-1">
              <span v-if="store.currentPage.pipeline_processed" class="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">Procesada</span>
              <span v-if="store.currentPage.needs_review" class="text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded">{{ store.currentPage.review_reason || 'Revisión' }}</span>
              <span v-if="store.currentPage.is_blank" class="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded">En blanco</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
  <div v-else class="text-sm text-gray-500">Cargando...</div>
</template>
