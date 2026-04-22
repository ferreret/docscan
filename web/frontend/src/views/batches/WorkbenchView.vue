<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, useTemplateRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Splitpanes, Pane } from 'splitpanes'
import 'splitpanes/dist/splitpanes.css'

import { ApiError } from '@/api/client'
import DocumentViewer from '@/components/DocumentViewer.vue'
import ThumbnailPanel from '@/components/workbench/ThumbnailPanel.vue'
import BarcodePanel from '@/components/workbench/BarcodePanel.vue'
import MetadataPanel from '@/components/workbench/MetadataPanel.vue'
import ViewerToolbar from '@/components/workbench/ViewerToolbar.vue'
import WorkbenchToolbar from '@/components/workbench/WorkbenchToolbar.vue'
import { useBatchesStore } from '@/stores/batches'
import { useApplicationsStore } from '@/stores/applications'
import { useToast } from '@/composables/useToast'
import { useWorkbenchLayout } from '@/composables/useWorkbenchLayout'

const route = useRoute()
const router = useRouter()
const store = useBatchesStore()
const appStore = useApplicationsStore()
const toast = useToast()
const { sizes, setSizes } = useWorkbenchLayout()

const batchId = computed(() => Number(route.params.id))
const selectedPageIndex = ref(0)
const uploading = ref(false)
const running = ref(false)
const transferring = ref(false)
const transferStatus = ref<'idle' | 'running' | 'completed' | 'error' | 'aborted'>('idle')
const transferMessage = ref<string | null>(null)
const transferProgress = ref<{ page_index: number; total: number } | null>(null)
const progress = ref<{ processed: number; total: number } | null>(null)
const error = ref<string | null>(null)
const savingMetadata = ref(false)

const viewerRef = useTemplateRef<InstanceType<typeof DocumentViewer>>('viewerRef')

const sortedPages = computed(() => [...(store.pages ?? [])].sort((a, b) => a.page_index - b.page_index))
const currentPageListItem = computed(() => sortedPages.value[selectedPageIndex.value])

const currentPage = computed(() => store.currentPage)
const currentImageUrl = computed(() =>
  currentPageListItem.value ? store.pageImageUrl(batchId.value, currentPageListItem.value.id) : '',
)

const counters = computed(() => {
  let withBarcode = 0
  let separators = 0
  let needsReview = 0
  for (const p of sortedPages.value) {
    if (p.needs_review) needsReview++
  }
  if (currentPage.value?.barcodes?.length) {
    withBarcode = sortedPages.value.length // approximation: per-page barcode count needs lazy fetch
  }
  if (currentPage.value?.barcodes?.some((b) => b.role === 'separator')) {
    separators = 1
  }
  return { total: sortedPages.value.length, withBarcode, separators, needsReview }
})

watch(
  () => currentPageListItem.value?.id,
  async (id) => {
    if (id) await store.fetchPage(batchId.value, id)
  },
)

onMounted(async () => {
  await store.fetchOne(batchId.value)
  await store.fetchPages(batchId.value)
  if (store.current?.application_id) await appStore.fetchOne(store.current.application_id)
  if (sortedPages.value.length > 0) {
    await store.fetchPage(batchId.value, sortedPages.value[0].id)
  }
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
})

function onKeydown(e: KeyboardEvent): void {
  if (e.target instanceof HTMLElement && ['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) return
  if (e.key === 'ArrowLeft') {
    selectedPageIndex.value = Math.max(0, selectedPageIndex.value - 1)
    e.preventDefault()
  } else if (e.key === 'ArrowRight') {
    selectedPageIndex.value = Math.min(sortedPages.value.length - 1, selectedPageIndex.value + 1)
    e.preventDefault()
  }
}

function openWs(): WebSocket {
  const token = localStorage.getItem('access_token') ?? ''
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return new WebSocket(`${proto}://${window.location.host}/ws/batches/${batchId.value}?token=${encodeURIComponent(token)}`)
}

async function onUpload(files: File[]): Promise<void> {
  uploading.value = true
  error.value = null
  try {
    await store.uploadFiles(batchId.value, files)
    await store.fetchOne(batchId.value)
  } catch (e) {
    error.value = e instanceof ApiError ? e.detail : 'Error al subir ficheros'
    toast.error(error.value!)
  } finally {
    uploading.value = false
  }
}

async function onRunPipeline(): Promise<void> {
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
      await Promise.all([store.fetchOne(batchId.value), store.fetchPages(batchId.value)])
      if (currentPageListItem.value) await store.fetchPage(batchId.value, currentPageListItem.value.id)
      running.value = false
      progress.value = null
      ws.close()
      toast[event.any_error ? 'error' : 'success'](
        event.any_error ? 'Pipeline con errores' : 'Pipeline completado',
      )
      if (appStore.current?.auto_transfer && store.current?.state === 'read') {
        await onTransfer()
      }
    } else if (event.type === 'pipeline_error') {
      error.value = `Error pipeline: ${event.error}`
      running.value = false
      progress.value = null
      ws.close()
      toast.error(error.value)
    }
  }
  ws.onerror = () => { error.value = 'Error de conexión'; running.value = false }
  try {
    await new Promise<void>((resolve, reject) => {
      ws.onopen = () => resolve()
      ws.addEventListener('error', () => reject(new Error('ws')), { once: true })
    })
    await store.runPipeline(batchId.value)
  } catch (e) {
    error.value = e instanceof ApiError ? e.detail : 'Error al ejecutar pipeline'
    running.value = false
    ws.close()
  }
}

async function onTransfer(): Promise<void> {
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
    } else if (event.type === 'transfer_page' && transferProgress.value) {
      transferProgress.value = { page_index: event.page_index + 1, total: transferProgress.value.total }
    } else if (event.type === 'transfer_completed') {
      transferring.value = false
      ws.close()
      transferStatus.value = event.success ? 'completed' : 'error'
      transferMessage.value = event.success
        ? (event.output_path ? `Transferencia → ${event.output_path}` : 'Transferencia completada')
        : (event.errors?.join('; ') || 'Error en transferencia')
      toast[event.success ? 'success' : 'error'](transferMessage.value!)
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
  ws.onerror = () => { transferring.value = false; transferStatus.value = 'error'; transferMessage.value = 'Error de conexión durante la transferencia' }
  try {
    await new Promise<void>((resolve, reject) => {
      ws.onopen = () => resolve()
      ws.addEventListener('error', () => reject(new Error('ws transfer')), { once: true })
    })
    const token = localStorage.getItem('access_token') ?? ''
    const res = await fetch(`/api/batches/${batchId.value}/transfer`, {
      method: 'POST', headers: { Authorization: `Bearer ${token}` },
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(body.detail || `Error ${res.status}`)
    }
  } catch (e) {
    transferring.value = false
    transferStatus.value = 'error'
    transferMessage.value = e instanceof Error ? e.message : 'Error al iniciar transferencia'
    ws.close()
    toast.error(transferMessage.value!)
  }
}

async function onDownloadZip(): Promise<void> {
  const token = localStorage.getItem('access_token') ?? ''
  const res = await fetch(`/api/batches/${batchId.value}/export`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) { toast.error('Error al descargar ZIP'); return }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = `batch_${batchId.value}.zip`; a.click()
  URL.revokeObjectURL(url)
}

async function onDeleteBatch(): Promise<void> {
  if (!confirm('¿Eliminar este lote? Esta acción no se puede deshacer.')) return
  await store.remove(batchId.value)
  router.push('/batches')
}

async function onSaveMetadata(fields: Record<string, unknown>): Promise<void> {
  if (!store.current) return
  savingMetadata.value = true
  try {
    await fetch(`/api/batches/${batchId.value}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${localStorage.getItem('access_token') ?? ''}`,
      },
      body: JSON.stringify({ fields_json: JSON.stringify(fields) }),
    })
    await store.fetchOne(batchId.value)
    toast.success('Lote guardado')
  } catch (e) {
    toast.error(e instanceof Error ? e.message : 'Error al guardar')
  } finally {
    savingMetadata.value = false
  }
}

function onColumnsResize(panes: Array<{ size: number }>): void {
  setSizes({ columns: panes.map((p) => p.size) as [number, number, number], rightVertical: sizes.value.rightVertical })
}

function onRightResize(panes: Array<{ size: number }>): void {
  setSizes({ columns: sizes.value.columns, rightVertical: panes.map((p) => p.size) as [number, number] })
}
</script>

<template>
  <div class="h-screen flex flex-col bg-base text-text">
    <WorkbenchToolbar
      v-if="store.current"
      :batch="store.current"
      :running="running"
      :transferring="transferring"
      :uploading="uploading"
      @upload="onUpload"
      @run-pipeline="onRunPipeline"
      @transfer="onTransfer"
      @download-zip="onDownloadZip"
      @delete-batch="onDeleteBatch"
    />
    <div v-if="error" class="bg-danger-soft text-danger text-xs px-4 py-1">{{ error }}</div>
    <div v-if="progress" class="bg-primary-soft text-primary text-xs px-4 py-1">Procesando {{ progress.processed }}/{{ progress.total }}…</div>
    <div v-if="transferProgress" class="bg-warning-soft text-warning text-xs px-4 py-1">Transfiriendo {{ transferProgress.page_index }}/{{ transferProgress.total }}…</div>

    <Splitpanes class="flex-1" @resized="onColumnsResize">
      <Pane :size="sizes.columns[0]" :min-size="8">
        <ThumbnailPanel
          :pages="sortedPages"
          :batchId="batchId"
          :selectedIndex="selectedPageIndex"
          @select="(i) => (selectedPageIndex = i)"
          @fit="viewerRef?.fitToViewport()"
        />
      </Pane>
      <Pane :size="sizes.columns[1]" :min-size="20">
        <div class="relative h-full">
          <DocumentViewer ref="viewerRef" :imageUrl="currentImageUrl" :barcodes="currentPage?.barcodes" />
          <ViewerToolbar
            v-if="viewerRef"
            :zoom-percent="viewerRef.zoomPercent ?? 100"
            @zoom-in="viewerRef.zoomIn()"
            @zoom-out="viewerRef.zoomOut()"
            @reset="viewerRef.resetView()"
            @fit="viewerRef.fitToViewport()"
          />
        </div>
      </Pane>
      <Pane :size="sizes.columns[2]" :min-size="20">
        <Splitpanes horizontal @resized="onRightResize">
          <Pane :size="sizes.rightVertical[0]" :min-size="20">
            <BarcodePanel :barcodes="currentPage?.barcodes ?? []" :pageCounters="counters" />
          </Pane>
          <Pane :size="sizes.rightVertical[1]" :min-size="20">
            <MetadataPanel :app="appStore.current" :batch="store.current" :saving="savingMetadata" @save="onSaveMetadata" />
          </Pane>
        </Splitpanes>
      </Pane>
    </Splitpanes>
  </div>
</template>

<style>
.splitpanes--vertical > .splitpanes__splitter {
  min-width: 4px;
  background-color: var(--color-surface-0);
}
.splitpanes--horizontal > .splitpanes__splitter {
  min-height: 4px;
  background-color: var(--color-surface-0);
}
.splitpanes__splitter:hover {
  background-color: var(--color-surface-1);
}
</style>
