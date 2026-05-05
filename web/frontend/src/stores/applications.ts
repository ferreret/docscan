import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api/client'
import type {
  ApplicationListItem,
  ApplicationResponse,
  ApplicationCreate,
  ApplicationUpdate,
  Paginated,
} from '@/api/types'

export const useApplicationsStore = defineStore('applications', () => {
  const items = ref<ApplicationListItem[]>([])
  const total = ref(0)
  const current = ref<ApplicationResponse | null>(null)
  const loading = ref(false)

  async function fetchAll() {
    loading.value = true
    try {
      const res = await api.get<Paginated<ApplicationListItem>>('/applications')
      items.value = res.items
      total.value = res.total
    } finally {
      loading.value = false
    }
  }

  async function fetchOne(id: number) {
    loading.value = true
    try {
      current.value = await api.get<ApplicationResponse>(`/applications/${id}`)
    } finally {
      loading.value = false
    }
  }

  async function create(data: ApplicationCreate) {
    const app = await api.post<ApplicationResponse>('/applications', data)
    await fetchAll()
    return app
  }

  async function update(id: number, data: ApplicationUpdate) {
    const app = await api.patch<ApplicationResponse>(`/applications/${id}`, data)
    current.value = app
    await fetchAll()
    return app
  }

  async function remove(id: number) {
    await api.delete(`/applications/${id}`)
    current.value = null
    await fetchAll()
  }

  return { items, total, current, loading, fetchAll, fetchOne, create, update, remove }
})
