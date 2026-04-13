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
        <button @click="router.back()" class="text-xs text-subtext hover:text-text mb-2 inline-flex items-center gap-1 transition-colors">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" /></svg>
          Volver
        </button>
        <h1 class="text-2xl font-bold text-text">Lote #{{ store.current.id }}</h1>
      </div>
      <div class="flex gap-2">
        <label class="bg-white border border-surface-1 text-text rounded-md px-4 py-2 text-[13px] font-medium hover:bg-crust cursor-pointer transition-colors">
          {{ uploading ? 'Subiendo...' : '↑ Subir ficheros' }}
          <input type="file" multiple accept=".jpg,.jpeg,.png,.bmp,.tif,.tiff,.pdf" class="hidden" @change="onUpload" :disabled="uploading" />
        </label>
        <button
          @click="onRunPipeline"
          :disabled="running || store.current.page_count === 0"
          class="bg-primary text-white rounded-md px-4 py-2 text-[13px] font-semibold hover:bg-primary-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm"
        >
          {{ running ? 'Procesando…' : '▶ Ejecutar pipeline' }}
        </button>
        <button @click="onDelete" class="text-danger border border-danger/40 bg-white rounded-md px-4 py-2 text-[13px] font-medium hover:bg-danger hover:text-white transition-colors">
          Eliminar
        </button>
      </div>
    </div>

    <div v-if="error" class="text-xs text-danger bg-danger-soft border border-danger/30 rounded-md px-3 py-2 mb-4">{{ error }}</div>

    <!-- Info -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
      <div class="bg-white rounded-lg border border-surface-0 p-4">
        <p class="text-[11px] text-subtext uppercase tracking-wide font-medium">Estado</p>
        <p class="text-sm font-semibold mt-1.5" :class="{
          'text-warning': store.current.state === 'created',
          'text-primary': store.current.state === 'read',
          'text-danger': store.current.state.startsWith('error'),
        }">{{ store.current.state }}</p>
      </div>
      <div class="bg-white rounded-lg border border-surface-0 p-4">
        <p class="text-[11px] text-subtext uppercase tracking-wide font-medium">Páginas</p>
        <p class="text-sm font-semibold text-text mt-1.5">{{ store.current.page_count }}</p>
      </div>
      <div class="bg-white rounded-lg border border-surface-0 p-4">
        <p class="text-[11px] text-subtext uppercase tracking-wide font-medium">Aplicación</p>
        <p class="text-sm font-semibold text-text mt-1.5">#{{ store.current.application_id }}</p>
      </div>
      <div class="bg-white rounded-lg border border-surface-0 p-4">
        <p class="text-[11px] text-subtext uppercase tracking-wide font-medium">Creado</p>
        <p class="text-sm font-semibold text-text mt-1.5">{{ new Date(store.current.created_at).toLocaleString('es-ES') }}</p>
      </div>
    </div>

    <!-- Thumbnails + Detail -->
    <div class="flex gap-4">
      <!-- Thumbnails grid -->
      <div class="flex-1 min-w-0">
        <div class="bg-white rounded-lg border border-surface-0 overflow-hidden">
          <div class="px-5 py-3 border-b border-surface-0 bg-mantle">
            <h2 class="text-[13px] font-semibold text-text uppercase tracking-wide">Páginas</h2>
          </div>
          <div v-if="store.pages.length === 0" class="px-5 py-16 text-center">
            <p class="text-sm text-subtext">Sin páginas. Sube imágenes o PDFs para empezar.</p>
          </div>
          <div v-else class="p-4 grid grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
            <div
              v-for="page in store.pages"
              :key="page.id"
              @click="selectPage(page.id)"
              class="group relative bg-white rounded-md border-2 overflow-hidden cursor-pointer transition-all hover:shadow-md"
              :class="selectedPage === page.id ? 'border-primary shadow-md' : 'border-surface-0 hover:border-surface-1'"
            >
              <AuthImage
                :url="store.pageImageUrl(batchId, page.id)"
                :alt="`Página ${page.page_index + 1}`"
                class="w-full aspect-[3/4] object-cover bg-crust"
              />
              <div class="absolute bottom-0 left-0 right-0 bg-text/80 text-white text-[11px] px-2 py-1 flex justify-between items-center">
                <span class="font-semibold">#{{ page.page_index + 1 }}</span>
                <div class="flex gap-1">
                  <span v-if="page.needs_review" class="text-warning" title="Requiere revisión">!</span>
                  <span v-if="page.pipeline_processed" class="text-success" title="Procesada">✓</span>
                </div>
              </div>
              <button
                @click.stop="onDeletePage(page.id)"
                class="absolute top-1.5 right-1.5 bg-danger text-white rounded-full w-5 h-5 flex items-center justify-center text-xs opacity-0 group-hover:opacity-100 transition-opacity shadow-sm"
                title="Eliminar"
              >
                ×
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Detail panel -->
      <div v-if="selectedPage && store.currentPage" class="w-80 shrink-0">
        <div class="bg-white rounded-lg border border-surface-0 overflow-hidden sticky top-6">
          <div class="px-5 py-3 border-b border-surface-0 bg-mantle">
            <h3 class="text-[13px] font-semibold text-text uppercase tracking-wide">Página {{ store.currentPage.page_index + 1 }}</h3>
          </div>
          <div class="p-4 space-y-4">
            <div v-if="store.currentPage.ocr_text" class="space-y-1.5">
              <p class="text-[11px] font-medium text-subtext uppercase tracking-wide">OCR</p>
              <p class="text-xs text-text bg-mantle border border-surface-0 rounded-md p-3 max-h-40 overflow-auto whitespace-pre-wrap">{{ store.currentPage.ocr_text }}</p>
            </div>

            <div v-if="store.currentPage.index_fields_json && store.currentPage.index_fields_json !== '{}'" class="space-y-1.5">
              <p class="text-[11px] font-medium text-subtext uppercase tracking-wide">Campos</p>
              <pre class="text-xs text-text bg-mantle border border-surface-0 rounded-md p-3 max-h-40 overflow-auto font-mono">{{ JSON.stringify(JSON.parse(store.currentPage.index_fields_json), null, 2) }}</pre>
            </div>

            <div class="space-y-1.5">
              <p class="text-[11px] font-medium text-subtext uppercase tracking-wide">Estado</p>
              <div class="flex flex-wrap gap-1.5">
                <span v-if="store.currentPage.pipeline_processed" class="text-[11px] bg-success-soft text-success border border-success/30 px-2 py-0.5 rounded-full font-medium">Procesada</span>
                <span v-if="store.currentPage.needs_review" class="text-[11px] bg-warning-soft text-warning border border-warning/30 px-2 py-0.5 rounded-full font-medium">{{ store.currentPage.review_reason || 'Revisión' }}</span>
                <span v-if="store.currentPage.is_blank" class="text-[11px] bg-crust text-subtext border border-surface-0 px-2 py-0.5 rounded-full font-medium">En blanco</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
  <div v-else class="text-sm text-subtext">Cargando...</div>
</template>
