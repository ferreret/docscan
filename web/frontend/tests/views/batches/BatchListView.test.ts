import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import BatchListView from '@/views/batches/BatchListView.vue'
import { useBatchesStore } from '@/stores/batches'
import { useApplicationsStore } from '@/stores/applications'
import { useAuthStore } from '@/stores/auth'

function makeRouter() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: BatchListView },
      { path: '/batches/:id', component: { template: '<div/>' } },
    ],
  })
  router.push('/')
  return router
}

function seedAuth() {
  const auth = useAuthStore()
  auth.user = {
    id: 1,
    tenant_id: 1,
    tenant_name: 'AcmeCo',
    email: 'a@a.com',
    role: 'company_admin',
    display_name: 'A',
    active: true,
  }
}

function seedApps() {
  const apps = useApplicationsStore()
  apps.fetchAll = vi.fn(async () => {
    apps.items = [
      { id: 10, name: 'AppX', description: '', position: 0 },
      { id: 11, name: 'AppY', description: '', position: 1 },
    ] as any
  })
  return apps
}

function seedBatches(total = 0, items: any[] = []) {
  const store = useBatchesStore()
  store.fetchAll = vi.fn(async (params: any = {}) => {
    store.items = items
    store.total = total
    store.limit = params?.limit ?? 50
    store.offset = params?.offset ?? 0
  }) as any
  return store
}

describe('BatchListView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('on mount fetches applications + batches with offset 0', async () => {
    seedAuth()
    const apps = seedApps()
    const store = seedBatches(0, [])
    const router = makeRouter()
    await router.isReady()
    mount(BatchListView, { global: { plugins: [router] } })
    await flushPromises()
    expect(apps.fetchAll).toHaveBeenCalled()
    expect(store.fetchAll).toHaveBeenCalledWith(
      expect.objectContaining({ applicationId: null, state: null, offset: 0 }),
    )
  })

  it('changing application filter triggers refetch with applicationId and resets offset', async () => {
    seedAuth()
    seedApps()
    const store = seedBatches(0, [])
    const router = makeRouter()
    await router.isReady()
    const wrapper = mount(BatchListView, { global: { plugins: [router] } })
    await flushPromises()
    ;(store.fetchAll as any).mockClear()
    const select = wrapper.find('[data-testid="filter-application"]')
    await select.setValue('10')
    await flushPromises()
    expect(store.fetchAll).toHaveBeenCalledWith(
      expect.objectContaining({ applicationId: 10, offset: 0 }),
    )
  })

  it('changing state filter triggers refetch with state', async () => {
    seedAuth()
    seedApps()
    const store = seedBatches(0, [])
    const router = makeRouter()
    await router.isReady()
    const wrapper = mount(BatchListView, { global: { plugins: [router] } })
    await flushPromises()
    ;(store.fetchAll as any).mockClear()
    await wrapper.find('[data-testid="filter-state"]').setValue('running')
    await flushPromises()
    expect(store.fetchAll).toHaveBeenCalledWith(
      expect.objectContaining({ state: 'running', offset: 0 }),
    )
  })

  it('paginates with Siguiente when total > PAGE_SIZE', async () => {
    seedAuth()
    seedApps()
    const items = Array.from({ length: 50 }, (_, i) => ({
      id: i + 1,
      tenant_id: 1,
      application_id: 10,
      state: 'read',
      page_count: 0,
      created_at: '2026-04-01',
    }))
    const store = seedBatches(120, items)
    const router = makeRouter()
    await router.isReady()
    const wrapper = mount(BatchListView, { global: { plugins: [router] } })
    await flushPromises()
    ;(store.fetchAll as any).mockClear()
    await wrapper.find('[data-testid="page-next"]').trigger('click')
    await flushPromises()
    expect(store.fetchAll).toHaveBeenCalledWith(
      expect.objectContaining({ offset: 50 }),
    )
  })

  it('hides pagination controls when total <= PAGE_SIZE', async () => {
    seedAuth()
    seedApps()
    const store = seedBatches(20, [])
    const router = makeRouter()
    await router.isReady()
    const wrapper = mount(BatchListView, { global: { plugins: [router] } })
    await flushPromises()
    expect(wrapper.find('[data-testid="page-next"]').exists()).toBe(false)
    expect(store.fetchAll).toHaveBeenCalled()
  })

  it('Anterior is disabled in first page', async () => {
    seedAuth()
    seedApps()
    const store = seedBatches(120, Array.from({ length: 50 }, (_, i) => ({
      id: i,
      tenant_id: 1,
      application_id: 10,
      state: 'read',
      page_count: 0,
      created_at: '2026-04-01',
    })))
    const router = makeRouter()
    await router.isReady()
    const wrapper = mount(BatchListView, { global: { plugins: [router] } })
    await flushPromises()
    const prev = wrapper.find('[data-testid="page-prev"]')
    expect(prev.attributes('disabled')).toBeDefined()
    expect(store.fetchAll).toHaveBeenCalled()
  })

  it('shows filtered empty-state message when filters active', async () => {
    seedAuth()
    seedApps()
    seedBatches(0, [])
    const router = makeRouter()
    await router.isReady()
    const wrapper = mount(BatchListView, { global: { plugins: [router] } })
    await flushPromises()
    await wrapper.find('[data-testid="filter-state"]').setValue('error_read')
    await flushPromises()
    expect(wrapper.text()).toContain('No hay lotes que coincidan con los filtros.')
  })
})
