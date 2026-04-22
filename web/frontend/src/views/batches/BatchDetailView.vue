<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useBatchesStore } from '@/stores/batches'
import { useApplicationsStore } from '@/stores/applications'
import { ApiError } from '@/api/client'
import AuthImage from '@/components/AuthImage.vue'
import DocumentViewer from '@/components/DocumentViewer.vue'
import { useToast } from '@/composables/useToast'

const toast = useToast()

const route = useRoute()
const router = useRouter()
const store = useBatchesStore()
const appStore = useApplicationsStore()

const batchId = computed(() => Number(route.params.id))
const uploading = ref(false)
const running = ref(false)
const error = ref<string | null>(null)
const selectedPage = ref<number | null>(null)
const progress = ref<{ processed: number; total: number } | null>(null)

// ---- Transfer state ----
const transferring = ref(false)
const transferProgress = ref<{ page_index: number; total: number } | null>(null)
const transferStatus = ref<'idle' | 'running' | 'completed' | 'error' | 'aborted'>('idle')
const transferMessage = ref<string | null>(null)

const canTransfer = computed(
  () => store.current?.state === 'read' && !transferring.value && !running.value,
)

onMounted(async () => {
  await store.fetchOne(batchId.value)
  await store.fetchPages(batchId.value)
  // Load application to know auto_transfer setting
  if (store.current?.application_id) {
    await appStore.fetchOne(store.current.application_id)
  }
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
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

function openWs(): WebSocket {
  const token = localStorage.getItem('access_token') ?? ''
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return new WebSocket(
    `${proto}://${window.location.host}/ws/batches/${batchId.value}?token=${encodeURIComponent(token)}`,
  )
}

async function onRunPipeline() {
  running.value = true
  error.value = null
  progress.value = null

  const ws = openWs()

  ws.onmessage = async (msg) => {
    const event = JSON.parse(msg.data)
    if (event.type === 'pipeline_started') {
      progress.value = { processed: 0, total: event.total_pages }
    } else if (event.type === 'page_processed') {
      progress.value = { processed: event.processed, total: event.total }
    } else if (event.type === 'pipeline_completed') {
      await Promise.all([
        store.fetchOne(batchId.value),
        store.fetchPages(batchId.value),
        selectedPage.value ? store.fetchPage(batchId.value, selectedPage.value) : null,
      ])
      running.value = false
      progress.value = null
      ws.close()
      if (event.any_error) {
        toast.error('Pipeline completado con errores — revisa las páginas marcadas')
      } else {
        toast.success('Pipeline completado correctamente')
      }
      // Auto-transfer if configured and batch is now 'read'
      if (
        appStore.current?.auto_transfer &&
        store.current?.state === 'read'
      ) {
        await startTransfer()
      }
    } else if (event.type === 'pipeline_error') {
      error.value = `Error en pipeline: ${event.error}`
      running.value = false
      progress.value = null
      ws.close()
      toast.error(`Error en pipeline: ${event.error}`)
    }
  }

  ws.onerror = () => {
    error.value = 'Error de conexión con el servidor'
    running.value = false
    progress.value = null
  }

  try {
    await new Promise<void>((resolve, reject) => {
      ws.onopen = () => resolve()
      ws.addEventListener('error', () => reject(new Error('ws connect failed')), { once: true })
    })
    await store.runPipeline(batchId.value)
  } catch (e) {
    error.value = e instanceof ApiError ? e.detail : 'Error al ejecutar pipeline'
    running.value = false
    progress.value = null
    ws.close()
  }
}

async function startTransfer() {
  if (transferring.value) return
  transferring.value = true
  transferStatus.value = 'running'
  transferMessage.value = null
  transferProgress.value = null

  const ws = openWs()

  ws.onmessage = async (msg) => {
    const event = JSON.parse(msg.data)
    if (event.type === 'transfer_started') {
      transferProgress.value = { page_index: 0, total: event.total_pages }
    } else if (event.type === 'transfer_page') {
      if (transferProgress.value) {
        transferProgress.value = {
          page_index: event.page_index + 1,
          total: transferProgress.value.total,
        }
      }
    } else if (event.type === 'transfer_completed') {
      transferring.value = false
      ws.close()
      if (event.success) {
        transferStatus.value = 'completed'
        transferMessage.value = event.output_path
          ? `Transferencia completada → ${event.output_path}`
          : 'Transferencia completada correctamente.'
        toast.success(transferMessage.value)
      } else {
        transferStatus.value = 'error'
        transferMessage.value = event.errors?.join('; ') || 'Error desconocido en la transferencia.'
        toast.error(transferMessage.value)
      }
      transferProgress.value = null
      await store.fetchOne(batchId.value)
    } else if (event.type === 'transfer_error') {
      transferring.value = false
      transferStatus.value = 'error'
      transferMessage.value = `Error: ${event.error}`
      transferProgress.value = null
      ws.close()
      toast.error(transferMessage.value)
    } else if (event.type === 'transfer_aborted') {
      transferring.value = false
      transferStatus.value = 'aborted'
      transferMessage.value = `Transferencia abortada: ${event.reason}`
      transferProgress.value = null
      ws.close()
      toast.error(transferMessage.value)
    }
  }

  ws.onerror = () => {
    transferring.value = false
    transferStatus.value = 'error'
    transferMessage.value = 'Error de conexión durante la transferencia'
    transferProgress.value = null
  }

  try {
    await new Promise<void>((resolve, reject) => {
      ws.onopen = () => resolve()
      ws.addEventListener('error', () => reject(new Error('ws transfer connect failed')), { once: true })
    })
    const token = localStorage.getItem('access_token') ?? ''
    const res = await fetch(`/api/batches/${batchId.value}/transfer`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(body.detail || `Error ${res.status}`)
    }
  } catch (e) {
    transferring.value = false
    transferStatus.value = 'error'
    transferMessage.value = e instanceof Error ? e.message : 'Error al iniciar la transferencia'
    transferProgress.value = null
    ws.close()
    toast.error(transferMessage.value!)
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

const downloading = ref(false)

async function onDownload() {
  downloading.value = true
  error.value = null
  try {
    const token = localStorage.getItem('access_token') ?? ''
    const res = await fetch(`/api/batches/${batchId.value}/export`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!res.ok) {
      error.value = `Error ${res.status} al descargar`
      return
    }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `batch_${batchId.value}.zip`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  } catch {
    error.value = 'Error de conexión al descargar'
  } finally {
    downloading.value = false
  }
}

function openViewer(pageId: number) {
  selectedPage.value = pageId
}

function closeViewer() {
  selectedPage.value = null
}

const selectedIndex = computed(() =>
  store.pages.findIndex((p) => p.id === selectedPage.value),
)

function navigate(delta: number) {
  if (selectedIndex.value < 0) return
  const next = selectedIndex.value + delta
  if (next < 0 || next >= store.pages.length) return
  selectedPage.value = store.pages[next].id
}

function onKeydown(e: KeyboardEvent) {
  if (selectedPage.value === null) return
  if (e.key === 'Escape') closeViewer()
  else if (e.key === 'ArrowLeft') navigate(-1)
  else if (e.key === 'ArrowRight') navigate(1)
}

watch(selectedPage, (id) => {
  if (id) store.fetchPage(batchId.value, id)
})

const fieldsParsed = computed(() => {
  const raw = store.currentPage?.index_fields_json
  if (!raw || raw === '{}') return null
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
})
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
        <label class="bg-base border border-surface-1 text-text rounded-md px-4 py-2 text-[13px] font-medium hover:bg-crust cursor-pointer transition-colors">
          {{ uploading ? 'Subiendo...' : '↑ Subir ficheros' }}
          <input type="file" multiple accept=".jpg,.jpeg,.png,.bmp,.tif,.tiff,.pdf" class="hidden" @change="onUpload" :disabled="uploading" />
        </label>
        <button
          @click="onRunPipeline"
          :disabled="running || store.current.page_count === 0"
          class="bg-primary text-base rounded-md px-4 py-2 text-[13px] font-semibold hover:bg-primary-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm min-w-[170px]"
        >
          <span v-if="progress">Procesando {{ progress.processed }}/{{ progress.total }}…</span>
          <span v-else-if="running">Iniciando…</span>
          <span v-else>▶ Ejecutar pipeline</span>
        </button>

        <!-- Botón Transferir ahora: solo visible si state==='read' -->
        <button
          v-if="store.current.state === 'read'"
          data-test="btn-transfer"
          @click="startTransfer"
          :disabled="!canTransfer"
          class="bg-base border border-surface-1 text-text rounded-md px-4 py-2 text-[13px] font-medium hover:bg-crust disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <span v-if="transferProgress">
            Transfiriendo {{ transferProgress.page_index }}/{{ transferProgress.total }}…
          </span>
          <span v-else-if="transferring">Iniciando…</span>
          <span v-else>↗ Transferir ahora</span>
        </button>

        <button
          @click="onDownload"
          :disabled="downloading || store.current.page_count === 0"
          class="bg-base border border-surface-1 text-text rounded-md px-4 py-2 text-[13px] font-medium hover:bg-crust disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {{ downloading ? 'Descargando…' : '↓ Descargar ZIP' }}
        </button>
        <button @click="onDelete" class="text-danger border border-danger/40 bg-base rounded-md px-4 py-2 text-[13px] font-medium hover:bg-danger hover:text-base transition-colors">
          Eliminar
        </button>
      </div>
    </div>

    <div v-if="error" class="text-xs text-danger bg-danger-soft border border-danger/30 rounded-md px-3 py-2 mb-4">{{ error }}</div>

    <!-- Transfer status banner -->
    <div
      v-if="transferStatus !== 'idle' && transferMessage"
      data-test="transfer-status-banner"
      class="rounded-md px-3 py-2 mb-4 text-xs"
      :class="{
        'bg-success-soft border border-success/30 text-success': transferStatus === 'completed',
        'bg-danger-soft border border-danger/30 text-danger': transferStatus === 'error',
        'bg-warning-soft border border-warning/30 text-warning': transferStatus === 'aborted',
        'bg-primary-soft border border-primary/30 text-primary': transferStatus === 'running',
      }"
    >
      {{ transferMessage }}
    </div>

    <!-- Info -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
      <div class="bg-base rounded-lg border border-surface-0 p-4">
        <p class="text-[11px] text-subtext uppercase tracking-wide font-medium">Estado</p>
        <p class="text-sm font-semibold mt-1.5" :class="{
          'text-warning': store.current.state === 'created',
          'text-primary': store.current.state === 'read',
          'text-danger': store.current.state.startsWith('error'),
        }">{{ store.current.state }}</p>
      </div>
      <div class="bg-base rounded-lg border border-surface-0 p-4">
        <p class="text-[11px] text-subtext uppercase tracking-wide font-medium">Páginas</p>
        <p class="text-sm font-semibold text-text mt-1.5">{{ store.current.page_count }}</p>
      </div>
      <div class="bg-base rounded-lg border border-surface-0 p-4">
        <p class="text-[11px] text-subtext uppercase tracking-wide font-medium">Aplicación</p>
        <p class="text-sm font-semibold text-text mt-1.5">#{{ store.current.application_id }}</p>
      </div>
      <div class="bg-base rounded-lg border border-surface-0 p-4">
        <p class="text-[11px] text-subtext uppercase tracking-wide font-medium">Creado</p>
        <p class="text-sm font-semibold text-text mt-1.5">{{ new Date(store.current.created_at).toLocaleString('es-ES') }}</p>
      </div>
    </div>

    <!-- Thumbnails grid -->
    <div class="bg-base rounded-lg border border-surface-0 overflow-hidden">
      <div class="px-5 py-3 border-b border-surface-0 bg-mantle">
        <h2 class="text-[13px] font-semibold text-text uppercase tracking-wide">Páginas</h2>
      </div>
      <div v-if="store.pages.length === 0" class="px-5 py-16 text-center">
        <p class="text-sm text-subtext">Sin páginas. Sube imágenes o PDFs para empezar.</p>
      </div>
      <div v-else class="p-4 grid grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-3">
        <div
          v-for="page in store.pages"
          :key="page.id"
          @click="openViewer(page.id)"
          class="group relative bg-base rounded-md border-2 overflow-hidden cursor-pointer transition-all hover:shadow-md border-surface-0 hover:border-surface-1"
        >
          <AuthImage
            :url="store.pageImageUrl(batchId, page.id)"
            :alt="`Página ${page.page_index + 1}`"
            class="w-full aspect-[3/4] object-cover bg-crust"
          />
          <div class="absolute bottom-0 left-0 right-0 bg-crust/90 text-text text-[11px] px-2 py-1 flex justify-between items-center">
            <span class="font-semibold">#{{ page.page_index + 1 }}</span>
            <div class="flex gap-1">
              <span v-if="page.needs_review" class="text-warning" title="Requiere revisión">!</span>
              <span v-if="page.pipeline_processed" class="text-success" title="Procesada">✓</span>
            </div>
          </div>
          <button
            @click.stop="onDeletePage(page.id)"
            class="absolute top-1.5 right-1.5 bg-danger text-base rounded-full w-5 h-5 flex items-center justify-center text-xs opacity-0 group-hover:opacity-100 transition-opacity shadow-sm"
            title="Eliminar"
          >
            ×
          </button>
        </div>
      </div>
    </div>

    <!-- Modal Visor -->
    <div
      v-if="selectedPage && store.currentPage"
      class="fixed inset-0 bg-crust/90 backdrop-blur-sm z-50 flex flex-col"
      @click.self="closeViewer"
    >
      <!-- Toolbar superior -->
      <div class="flex items-center justify-between px-6 py-3 bg-mantle border-b border-surface-1 shrink-0">
        <div class="flex items-center gap-3">
          <button
            @click="closeViewer"
            class="text-subtext hover:text-text p-1.5 rounded transition-colors"
            title="Cerrar (Esc)"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
          <h3 class="text-[13px] font-semibold text-text uppercase tracking-wide">
            Página {{ store.currentPage.page_index + 1 }} de {{ store.pages.length }}
          </h3>
        </div>
        <div class="flex items-center gap-2">
          <button
            @click="navigate(-1)"
            :disabled="selectedIndex <= 0"
            class="px-3 h-8 flex items-center gap-1 rounded-md text-[13px] font-medium text-text bg-base border border-surface-1 hover:bg-crust disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            title="Anterior (←)"
          >
            ← Anterior
          </button>
          <button
            @click="navigate(1)"
            :disabled="selectedIndex >= store.pages.length - 1"
            class="px-3 h-8 flex items-center gap-1 rounded-md text-[13px] font-medium text-text bg-base border border-surface-1 hover:bg-crust disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            title="Siguiente (→)"
          >
            Siguiente →
          </button>
          <div class="w-px h-6 bg-surface-1 mx-1"></div>
          <button
            @click="onDeletePage(selectedPage)"
            class="px-3 h-8 flex items-center text-[13px] font-medium text-danger border border-danger/40 bg-base hover:bg-danger hover:text-base rounded-md transition-colors"
          >
            Eliminar página
          </button>
        </div>
      </div>

      <!-- Cuerpo: visor + sidebar metadata -->
      <div class="flex-1 flex min-h-0">
        <div class="flex-1 min-w-0">
          <DocumentViewer
            :image-url="store.pageImageUrl(batchId, selectedPage)"
            :barcodes="store.currentPage.barcodes"
          />
        </div>

        <aside class="w-80 shrink-0 bg-mantle border-l border-surface-1 overflow-auto">
          <div class="p-4 space-y-4">
            <!-- Estado -->
            <div class="space-y-1.5">
              <p class="text-[11px] font-medium text-subtext uppercase tracking-wide">Estado</p>
              <div class="flex flex-wrap gap-1.5">
                <span v-if="store.currentPage.pipeline_processed" class="text-[11px] bg-success-soft text-success border border-success/30 px-2 py-0.5 rounded-full font-medium">Procesada</span>
                <span v-if="store.currentPage.needs_review" class="text-[11px] bg-warning-soft text-warning border border-warning/30 px-2 py-0.5 rounded-full font-medium">{{ store.currentPage.review_reason || 'Revisión' }}</span>
                <span v-if="store.currentPage.is_blank" class="text-[11px] bg-crust text-subtext border border-surface-0 px-2 py-0.5 rounded-full font-medium">En blanco</span>
                <span v-if="!store.currentPage.pipeline_processed && !store.currentPage.needs_review" class="text-[11px] bg-crust text-subtext border border-surface-0 px-2 py-0.5 rounded-full font-medium">Sin procesar</span>
              </div>
            </div>

            <!-- Barcodes -->
            <div v-if="store.currentPage.barcodes?.length" class="space-y-1.5">
              <p class="text-[11px] font-medium text-subtext uppercase tracking-wide">
                Barcodes ({{ store.currentPage.barcodes.length }})
              </p>
              <div class="space-y-1.5">
                <div
                  v-for="bc in store.currentPage.barcodes"
                  :key="bc.id"
                  class="bg-base border border-surface-0 rounded-md p-2.5"
                >
                  <div class="flex items-center justify-between gap-2">
                    <span class="text-[10px] font-semibold text-subtext uppercase">{{ bc.symbology }}</span>
                    <span v-if="bc.role" class="text-[10px] bg-primary-soft text-primary px-1.5 py-0.5 rounded font-medium">{{ bc.role }}</span>
                  </div>
                  <p class="text-xs font-mono text-text mt-1 break-all">{{ bc.value }}</p>
                </div>
              </div>
            </div>

            <!-- Campos -->
            <div v-if="fieldsParsed" class="space-y-1.5">
              <p class="text-[11px] font-medium text-subtext uppercase tracking-wide">Campos</p>
              <div class="bg-base border border-surface-0 rounded-md divide-y divide-surface-0">
                <div
                  v-for="(value, key) in fieldsParsed"
                  :key="key"
                  class="px-2.5 py-1.5 flex justify-between gap-2 text-xs"
                >
                  <span class="text-subtext font-medium">{{ key }}</span>
                  <span class="text-text font-mono break-all text-right">{{ value }}</span>
                </div>
              </div>
            </div>

            <!-- OCR -->
            <div v-if="store.currentPage.ocr_text" class="space-y-1.5">
              <p class="text-[11px] font-medium text-subtext uppercase tracking-wide">OCR</p>
              <p class="text-xs text-text bg-base border border-surface-0 rounded-md p-3 max-h-60 overflow-auto whitespace-pre-wrap">{{ store.currentPage.ocr_text }}</p>
            </div>

            <!-- Errores -->
            <div
              v-if="store.currentPage.processing_errors_json && store.currentPage.processing_errors_json !== '[]'"
              class="space-y-1.5"
            >
              <p class="text-[11px] font-medium text-danger uppercase tracking-wide">Errores</p>
              <pre class="text-xs text-danger bg-danger-soft border border-danger/30 rounded-md p-3 max-h-40 overflow-auto whitespace-pre-wrap">{{ store.currentPage.processing_errors_json }}</pre>
            </div>
          </div>
        </aside>
      </div>
    </div>
  </div>
  <div v-else class="text-sm text-subtext">Cargando...</div>
</template>
