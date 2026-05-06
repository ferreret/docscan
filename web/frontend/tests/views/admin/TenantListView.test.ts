import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory, type Router } from 'vue-router'
import TenantListView from '@/views/admin/TenantListView.vue'
import { useAdminStore } from '@/stores/admin'
import type { TenantListItem } from '@/api/types'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
  ApiError: class extends Error {
    status: number
    detail: string
    constructor(status: number, detail: string) {
      super(detail)
      this.status = status
      this.detail = detail
    }
  },
}))

const tenantA: TenantListItem = {
  id: 1,
  name: 'Acme',
  slug: 'acme',
  plan: 'free',
  active: true,
  created_at: '2026-05-01T10:00:00Z',
  stats: { n_users: 3, n_applications: 2, n_batches: 5 },
}
const tenantB: TenantListItem = {
  id: 2,
  name: 'Globex',
  slug: 'globex',
  plan: 'enterprise',
  active: false,
  created_at: '2026-04-15T08:00:00Z',
  stats: { n_users: 12, n_applications: 5, n_batches: 100 },
}

async function makeRouter(): Promise<Router> {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/admin/tenants', name: 'admin-tenants', component: { template: '<div/>' } },
      { path: '/admin/tenants/new', name: 'admin-tenant-new', component: { template: '<div/>' } },
      {
        path: '/admin/tenants/:id',
        name: 'admin-tenant-detail',
        component: { template: '<div/>' },
      },
    ],
  })
  router.push('/admin/tenants')
  await router.isReady()
  return router
}

async function mountView() {
  const router = await makeRouter()
  return mount(TenantListView, { global: { plugins: [router] } })
}

describe('TenantListView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('al montar dispara fetchTenants y muestra la tabla', async () => {
    const store = useAdminStore()
    store.fetchTenants = vi.fn(async () => {
      store.tenants = [tenantA, tenantB]
      store.totalTenants = 2
    })

    const wrapper = await mountView()
    await flushPromises()

    expect(store.fetchTenants).toHaveBeenCalledOnce()
    const rows = wrapper.findAll('[data-test="tenant-row"]')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('Acme')
    expect(rows[0].text()).toContain('free')
    expect(rows[0].text()).toContain('3') // n_users
    expect(rows[1].text()).toContain('Globex')
    expect(rows[1].text()).toContain('enterprise')
  })

  it('marca visualmente los tenants inactivos', async () => {
    const store = useAdminStore()
    store.fetchTenants = vi.fn(async () => {
      store.tenants = [tenantB]
      store.totalTenants = 1
    })

    const wrapper = await mountView()
    await flushPromises()

    const row = wrapper.find('[data-test="tenant-row"]')
    expect(row.classes().join(' ')).toContain('opacity-50')
  })

  it('botón Suspender llama updateTenant con active=false', async () => {
    const store = useAdminStore()
    store.fetchTenants = vi.fn(async () => {
      store.tenants = [tenantA]
      store.totalTenants = 1
    })
    store.updateTenant = vi.fn().mockResolvedValue({ ...tenantA, active: false })

    const wrapper = await mountView()
    await flushPromises()

    await wrapper.find('[data-test="toggle-active"]').trigger('click')
    expect(store.updateTenant).toHaveBeenCalledWith(1, { active: false })
  })

  it('botón Activar llama updateTenant con active=true en tenant inactivo', async () => {
    const store = useAdminStore()
    store.fetchTenants = vi.fn(async () => {
      store.tenants = [tenantB]
      store.totalTenants = 1
    })
    store.updateTenant = vi.fn().mockResolvedValue({ ...tenantB, active: true })

    const wrapper = await mountView()
    await flushPromises()

    await wrapper.find('[data-test="toggle-active"]').trigger('click')
    expect(store.updateTenant).toHaveBeenCalledWith(2, { active: true })
  })

  it('eliminar pide confirmación con el nombre exacto', async () => {
    const store = useAdminStore()
    store.fetchTenants = vi.fn(async () => {
      store.tenants = [tenantA]
      store.totalTenants = 1
    })
    store.deleteTenant = vi.fn().mockResolvedValue(undefined)
    const promptSpy = vi
      .spyOn(window, 'prompt')
      .mockReturnValueOnce('xxx') // confirmación errónea
      .mockReturnValueOnce('Acme') // confirmación correcta

    const wrapper = await mountView()
    await flushPromises()

    await wrapper.find('[data-test="delete-tenant"]').trigger('click')
    expect(store.deleteTenant).not.toHaveBeenCalled()

    await wrapper.find('[data-test="delete-tenant"]').trigger('click')
    expect(store.deleteTenant).toHaveBeenCalledWith(1)

    promptSpy.mockRestore()
  })

  it('lista vacía muestra empty state con CTA a /admin/tenants/new', async () => {
    const store = useAdminStore()
    store.fetchTenants = vi.fn(async () => {
      store.tenants = []
      store.totalTenants = 0
    })

    const wrapper = await mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('No hay tenants')
    expect(wrapper.find('[data-test="empty-cta"]').attributes('href')).toBe(
      '/admin/tenants/new',
    )
  })

  it('cabecera tiene CTA "Nuevo tenant" enlazando a /admin/tenants/new', async () => {
    const store = useAdminStore()
    store.fetchTenants = vi.fn(async () => {
      store.tenants = [tenantA]
      store.totalTenants = 1
    })

    const wrapper = await mountView()
    await flushPromises()

    const link = wrapper.find('[data-test="new-tenant-cta"]')
    expect(link.exists()).toBe(true)
    expect(link.attributes('href')).toBe('/admin/tenants/new')
  })
})
