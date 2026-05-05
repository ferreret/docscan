import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory, type Router } from 'vue-router'
import TenantDetailView from '@/views/admin/TenantDetailView.vue'
import { useAdminStore } from '@/stores/admin'
import { useAuthStore } from '@/stores/auth'
import { ApiError } from '@/api/client'
import type { TenantDetail } from '@/api/types'

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

const tenantDetail: TenantDetail = {
  id: 7,
  name: 'Acme',
  slug: 'acme',
  plan: 'free',
  active: true,
  created_at: '2026-05-01T10:00:00Z',
  stats: { n_users: 2, n_applications: 1, n_batches: 3 },
  users: [
    {
      id: 100,
      email: 'admin@acme.test',
      display_name: 'Admin Acme',
      role: 'company_admin',
      active: true,
      created_at: '2026-05-01T10:00:00Z',
    },
    {
      id: 101,
      email: 'op@acme.test',
      display_name: 'Operador Acme',
      role: 'operator',
      active: false,
      created_at: '2026-05-02T10:00:00Z',
    },
  ],
}

async function makeRouter(): Promise<Router> {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/admin/tenants', name: 'admin-tenants', component: { template: '<div/>' } },
      {
        path: '/admin/tenants/:id',
        name: 'admin-tenant-detail',
        component: { template: '<div/>' },
      },
    ],
  })
  router.push('/admin/tenants/7')
  await router.isReady()
  return router
}

async function mountView(props: { id: string } = { id: '7' }) {
  const router = await makeRouter()
  const wrapper = mount(TenantDetailView, {
    props,
    global: { plugins: [router] },
  })
  return { wrapper, router }
}

function seedSuperadmin() {
  const auth = useAuthStore()
  auth.user = {
    id: 1,
    email: 'super@tecnomedia.test',
    display_name: 'Super',
    role: 'superadmin',
    tenant_id: 1,
    tenant_name: 'TecnoMedia',
  }
}

describe('TenantDetailView — carga', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    seedSuperadmin()
  })

  it('al montar dispara fetchTenant(id) y muestra cabecera + usuarios', async () => {
    const store = useAdminStore()
    store.fetchTenant = vi.fn(async () => {
      store.currentTenant = { ...tenantDetail }
    })

    const { wrapper } = await mountView()
    await flushPromises()

    expect(store.fetchTenant).toHaveBeenCalledWith(7)
    expect(wrapper.text()).toContain('Acme')
    expect(wrapper.text()).toContain('acme')
    const rows = wrapper.findAll('[data-test="user-row"]')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('admin@acme.test')
    expect(rows[1].text()).toContain('op@acme.test')
  })

  it('mientras carga muestra mensaje y no rompe si currentTenant null', async () => {
    const store = useAdminStore()
    store.fetchTenant = vi.fn(async () => {
      // no hidratamos currentTenant: simulamos pendiente
    })

    const { wrapper } = await mountView()
    expect(wrapper.text().toLowerCase()).toContain('cargando')
  })
})

describe('TenantDetailView — editar tenant', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    seedSuperadmin()
  })

  it('guarda cambios solo cuando el formulario de tenant difiere', async () => {
    const store = useAdminStore()
    store.fetchTenant = vi.fn(async () => {
      store.currentTenant = { ...tenantDetail }
    })
    store.updateTenant = vi.fn().mockResolvedValue({
      ...tenantDetail,
      plan: 'enterprise',
    })

    const { wrapper } = await mountView()
    await flushPromises()

    await wrapper.find('[data-test="tenant-name-input"]').setValue('Acme')
    await wrapper.find('[data-test="tenant-plan-select"]').setValue('enterprise')
    await wrapper.find('[data-test="save-tenant"]').trigger('click')
    await flushPromises()

    expect(store.updateTenant).toHaveBeenCalledWith(7, { plan: 'enterprise' })
  })

  it('toggle active en cabecera llama updateTenant con active', async () => {
    const store = useAdminStore()
    store.fetchTenant = vi.fn(async () => {
      store.currentTenant = { ...tenantDetail }
    })
    store.updateTenant = vi.fn().mockResolvedValue({ ...tenantDetail, active: false })

    const { wrapper } = await mountView()
    await flushPromises()

    await wrapper.find('[data-test="tenant-active-toggle"]').trigger('click')
    expect(store.updateTenant).toHaveBeenCalledWith(7, { active: false })
  })
})

describe('TenantDetailView — usuarios', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    seedSuperadmin()
  })

  it('cambiar rol de un usuario llama updateUser', async () => {
    const store = useAdminStore()
    store.fetchTenant = vi.fn(async () => {
      store.currentTenant = { ...tenantDetail }
    })
    store.updateUser = vi.fn().mockResolvedValue({
      id: 101,
      email: 'op@acme.test',
      display_name: 'Operador Acme',
      role: 'company_admin',
      active: false,
      created_at: '2026-05-02T10:00:00Z',
      tenant_id: 7,
      tenant_name: 'Acme',
    })

    const { wrapper } = await mountView()
    await flushPromises()

    const select = wrapper.findAll('[data-test="user-role-select"]')[1]
    await select.setValue('company_admin')
    await flushPromises()

    expect(store.updateUser).toHaveBeenCalledWith(101, { role: 'company_admin' })
  })

  it('toggle activo de un usuario llama updateUser', async () => {
    const store = useAdminStore()
    store.fetchTenant = vi.fn(async () => {
      store.currentTenant = { ...tenantDetail }
    })
    store.updateUser = vi.fn().mockResolvedValue({
      id: 101,
      email: 'op@acme.test',
      display_name: 'Operador Acme',
      role: 'operator',
      active: true,
      created_at: '2026-05-02T10:00:00Z',
      tenant_id: 7,
      tenant_name: 'Acme',
    })

    const { wrapper } = await mountView()
    await flushPromises()

    const toggles = wrapper.findAll('[data-test="user-active-toggle"]')
    await toggles[1].trigger('click')
    expect(store.updateUser).toHaveBeenCalledWith(101, { active: true })
  })

  it('borrar usuario pide confirm y llama deleteUser con tenantId', async () => {
    const store = useAdminStore()
    store.fetchTenant = vi.fn(async () => {
      store.currentTenant = { ...tenantDetail }
    })
    store.deleteUser = vi.fn().mockResolvedValue(undefined)
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)

    const { wrapper } = await mountView()
    await flushPromises()

    await wrapper.findAll('[data-test="user-delete"]')[0].trigger('click')
    expect(store.deleteUser).toHaveBeenCalledWith(100, { tenantId: 7 })

    confirmSpy.mockRestore()
  })

  it('borrar usuario cancelado en confirm no llama al store', async () => {
    const store = useAdminStore()
    store.fetchTenant = vi.fn(async () => {
      store.currentTenant = { ...tenantDetail }
    })
    store.deleteUser = vi.fn()
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)

    const { wrapper } = await mountView()
    await flushPromises()

    await wrapper.findAll('[data-test="user-delete"]')[0].trigger('click')
    expect(store.deleteUser).not.toHaveBeenCalled()
    confirmSpy.mockRestore()
  })

  it('error 409 del backend (último admin) se enseña como toast/inline', async () => {
    const store = useAdminStore()
    store.fetchTenant = vi.fn(async () => {
      store.currentTenant = { ...tenantDetail }
    })
    store.updateUser = vi
      .fn()
      .mockRejectedValue(new ApiError(409, 'El tenant debe mantener al menos un company_admin activo'))

    const { wrapper } = await mountView()
    await flushPromises()

    const toggles = wrapper.findAll('[data-test="user-active-toggle"]')
    await toggles[0].trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('al menos un company_admin')
  })
})

describe('TenantDetailView — crear usuario', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    seedSuperadmin()
  })

  it('modal crear envía payload con tenant_id correcto', async () => {
    const store = useAdminStore()
    store.fetchTenant = vi.fn(async () => {
      store.currentTenant = { ...tenantDetail }
    })
    store.createUser = vi.fn().mockResolvedValue({
      id: 200,
      email: 'nuevo@acme.test',
      display_name: 'Nuevo',
      role: 'operator',
      active: true,
      created_at: '2026-05-05T10:00:00Z',
      tenant_id: 7,
      tenant_name: 'Acme',
    })

    const { wrapper } = await mountView()
    await flushPromises()

    await wrapper.find('[data-test="open-create-user"]').trigger('click')
    await wrapper.find('[data-test="new-user-email"]').setValue('nuevo@acme.test')
    await wrapper.find('[data-test="new-user-display-name"]').setValue('Nuevo')
    await wrapper.find('[data-test="new-user-password"]').setValue('secret123')
    await wrapper.find('[data-test="new-user-role"]').setValue('operator')
    await wrapper.find('[data-test="create-user-modal"] form').trigger('submit.prevent')
    await flushPromises()

    expect(store.createUser).toHaveBeenCalledWith({
      tenant_id: 7,
      email: 'nuevo@acme.test',
      password: 'secret123',
      display_name: 'Nuevo',
      role: 'operator',
    })
  })

  it('error API en creación se muestra dentro del modal y no cierra', async () => {
    const store = useAdminStore()
    store.fetchTenant = vi.fn(async () => {
      store.currentTenant = { ...tenantDetail }
    })
    store.createUser = vi.fn().mockRejectedValue(new ApiError(409, 'email ya en uso'))

    const { wrapper } = await mountView()
    await flushPromises()

    await wrapper.find('[data-test="open-create-user"]').trigger('click')
    await wrapper.find('[data-test="new-user-email"]').setValue('dup@acme.test')
    await wrapper.find('[data-test="new-user-display-name"]').setValue('Dup')
    await wrapper.find('[data-test="new-user-password"]').setValue('secret123')
    await wrapper.find('[data-test="create-user-modal"] form').trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.text()).toContain('email ya en uso')
    expect(wrapper.find('[data-test="create-user-modal"]').exists()).toBe(true)
  })

  it('contraseña corta bloquea submit antes del backend', async () => {
    const store = useAdminStore()
    store.fetchTenant = vi.fn(async () => {
      store.currentTenant = { ...tenantDetail }
    })
    store.createUser = vi.fn()

    const { wrapper } = await mountView()
    await flushPromises()

    await wrapper.find('[data-test="open-create-user"]').trigger('click')
    await wrapper.find('[data-test="new-user-email"]').setValue('a@a.test')
    await wrapper.find('[data-test="new-user-display-name"]').setValue('X')
    await wrapper.find('[data-test="new-user-password"]').setValue('123')
    await wrapper.find('[data-test="create-user-modal"] form').trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.text()).toContain('al menos 8 caracteres')
    expect(store.createUser).not.toHaveBeenCalled()
  })
})
