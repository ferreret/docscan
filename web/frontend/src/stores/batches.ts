import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api/client'
import type {
  BatchListItem,
  BatchResponse,
  BatchCreate,
  PageListItem,
  PageResponse,
  PageUploadResponse,
  Paginated,
} from '@/api/types'

export const useBatchesStore = defineStore('batches', () => {
  const items = ref<BatchListItem[]>([])
  const total = ref(0)
  const limit = ref(50)
  const offset = ref(0)
  const current = ref<BatchResponse | null>(null)
  const pages = ref<PageListItem[]>([])
  const currentPage = ref<PageResponse | null>(null)
  const loading = ref(false)

  async function fetchAll(
    applicationIdOrParams?:
      | number
      | {
          applicationId?: number | null
          state?: string | null
          limit?: number
          offset?: number
          silent?: boolean
        },
    opts: { silent?: boolean } = {},
  ) {
    // Compat: el polling existente llama fetchAll(undefined, {silent:true})
    // y el resto fetchAll(appId). Si el primer argumento es un objeto se
    // toma como bag de parámetros (incluye silent).
    const params =
      typeof applicationIdOrParams === 'object' && applicationIdOrParams !== null
        ? applicationIdOrParams
        : { applicationId: applicationIdOrParams ?? null, ...opts }
    const silent = params.silent ?? false
    if (!silent) loading.value = true
    try {
      const qs = new URLSearchParams()
      if (params.applicationId != null) qs.set('application_id', String(params.applicationId))
      if (params.state) qs.set('state', params.state)
      if (params.limit != null) qs.set('limit', String(params.limit))
      if (params.offset != null) qs.set('offset', String(params.offset))
      const query = qs.toString() ? `?${qs.toString()}` : ''
      const res = await api.get<Paginated<BatchListItem>>(`/batches${query}`)
      items.value = res.items
      total.value = res.total
      limit.value = res.limit
      offset.value = res.offset
    } finally {
      if (!silent) loading.value = false
    }
  }

  async function fetchOne(id: number) {
    loading.value = true
    try {
      current.value = await api.get<BatchResponse>(`/batches/${id}`)
    } finally {
      loading.value = false
    }
  }

  async function create(data: BatchCreate) {
    const batch = await api.post<BatchResponse>('/batches', data)
    return batch
  }

  async function remove(id: number) {
    await api.delete(`/batches/${id}`)
    current.value = null
  }

  async function runPipeline(id: number) {
    return api.post<BatchResponse>(`/batches/${id}/run`)
  }

  // --- Pages ---

  async function fetchPages(batchId: number) {
    pages.value = await api.get<PageListItem[]>(`/batches/${batchId}/pages`)
  }

  async function fetchPage(batchId: number, pageId: number) {
    currentPage.value = await api.get<PageResponse>(
      `/batches/${batchId}/pages/${pageId}`,
    )
  }

  async function uploadFiles(batchId: number, files: File[]) {
    const res = await api.uploadFiles<PageUploadResponse>(
      `/batches/${batchId}/pages`,
      files,
    )
    await fetchPages(batchId)
    return res
  }

  async function deletePage(batchId: number, pageId: number) {
    await api.delete(`/batches/${batchId}/pages/${pageId}`)
    await fetchPages(batchId)
  }

  function pageImageUrl(batchId: number, pageId: number): string {
    return `/api/batches/${batchId}/pages/${pageId}/image`
  }

  return {
    items, total, limit, offset, current, pages, currentPage, loading,
    fetchAll, fetchOne, create, remove, runPipeline,
    fetchPages, fetchPage, uploadFiles, deletePage, pageImageUrl,
  }
})
