import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory, type Router } from 'vue-router'
import CreateTenantView from '@/views/admin/CreateTenantView.vue'
import { useAdminStore } from '@/stores/admin'
import { ApiError } from '@/api/client'

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
  router.push('/admin/tenants/new')
  await router.isReady()
  return router
}

async function mountView() {
  const router = await makeRouter()
  const wrapper = mount(CreateTenantView, { global: { plugins: [router] } })
  return { wrapper, router }
}

describe('CreateTenantView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('submit envía payload completo y redirige al detalle del tenant creado', async () => {
    const store = useAdminStore()
    store.createTenant = vi.fn().mockResolvedValue({
      id: 42,
      name: 'NuevoCo',
      slug: 'nuevoco',
      plan: 'basic',
      active: true,
      created_at: '2026-05-05T10:00:00Z',
      stats: { n_users: 1, n_applications: 0, n_batches: 0 },
      users: [],
    })

    const { wrapper, router } = await mountView()
    await wrapper.find('[data-test="tenant-name"]').setValue('NuevoCo')
    await wrapper.find('[data-test="plan-select"]').setValue('basic')
    await wrapper.find('[data-test="admin-email"]').setValue('root@nuevoco.test')
    await wrapper.find('[data-test="admin-password"]').setValue('secret123')
    await wrapper.find('[data-test="admin-display-name"]').setValue('Root Nuevo')

    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(store.createTenant).toHaveBeenCalledWith({
      tenant_name: 'NuevoCo',
      plan: 'basic',
      admin_email: 'root@nuevoco.test',
      admin_password: 'secret123',
      admin_display_name: 'Root Nuevo',
    })
    expect(router.currentRoute.value.path).toBe('/admin/tenants/42')
  })

  it('botón Cancelar vuelve al listado', async () => {
    const { wrapper, router } = await mountView()
    await wrapper.find('[data-test="cancel"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/admin/tenants')
  })

  it('error de la API se muestra al usuario y no redirige', async () => {
    const store = useAdminStore()
    store.createTenant = vi.fn().mockRejectedValue(new ApiError(409, 'email ya en uso'))

    const { wrapper, router } = await mountView()
    await wrapper.find('[data-test="tenant-name"]').setValue('NuevoCo')
    await wrapper.find('[data-test="admin-email"]').setValue('dup@nuevoco.test')
    await wrapper.find('[data-test="admin-password"]').setValue('secret123')
    await wrapper.find('[data-test="admin-display-name"]').setValue('Root')

    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.text()).toContain('email ya en uso')
    expect(router.currentRoute.value.path).toBe('/admin/tenants/new')
  })

  it('contraseña corta muestra error de validación local antes de pegarle al backend', async () => {
    const store = useAdminStore()
    store.createTenant = vi.fn()

    const { wrapper } = await mountView()
    await wrapper.find('[data-test="tenant-name"]').setValue('NuevoCo')
    await wrapper.find('[data-test="admin-email"]').setValue('root@nuevoco.test')
    await wrapper.find('[data-test="admin-password"]').setValue('short')
    await wrapper.find('[data-test="admin-display-name"]').setValue('Root')

    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.text()).toContain('al menos 8 caracteres')
    expect(store.createTenant).not.toHaveBeenCalled()
  })
})
