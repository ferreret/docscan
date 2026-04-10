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
} from '@/api/types'

export const useBatchesStore = defineStore('batches', () => {
  const items = ref<BatchListItem[]>([])
  const current = ref<BatchResponse | null>(null)
  const pages = ref<PageListItem[]>([])
  const currentPage = ref<PageResponse | null>(null)
  const loading = ref(false)

  async function fetchAll(applicationId?: number) {
    loading.value = true
    try {
      const query = applicationId ? `?application_id=${applicationId}` : ''
      items.value = await api.get<BatchListItem[]>(`/batches${query}`)
    } finally {
      loading.value = false
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
    items, current, pages, currentPage, loading,
    fetchAll, fetchOne, create, remove, runPipeline,
    fetchPages, fetchPage, uploadFiles, deletePage, pageImageUrl,
  }
})
