import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAdminStore } from '@/stores/admin'
import type {
  TenantListItem,
  TenantDetail,
  AdminUserListItem,
  TenantCreateRequest,
  AdminUserCreateRequest,
} from '@/api/types'

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
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

import { api } from '@/api/client'

const tenantStub: TenantListItem = {
  id: 1,
  name: 'Acme',
  slug: 'acme',
  plan: 'free',
  active: true,
  created_at: '2026-05-01T10:00:00Z',
  stats: { n_users: 3, n_applications: 2, n_batches: 5 },
}

const tenantDetailStub: TenantDetail = {
  ...tenantStub,
  users: [
    {
      id: 10,
      email: 'admin@acme.test',
      display_name: 'Admin Acme',
      role: 'company_admin',
      active: true,
      created_at: '2026-05-01T10:00:00Z',
    },
  ],
}

const userStub: AdminUserListItem = {
  id: 10,
  email: 'admin@acme.test',
  display_name: 'Admin Acme',
  role: 'company_admin',
  active: true,
  created_at: '2026-05-01T10:00:00Z',
  tenant_id: 1,
  tenant_name: 'Acme',
}

describe('useAdminStore — tenants', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('fetchTenants popula items y total', async () => {
    vi.mocked(api.get).mockResolvedValue({
      items: [tenantStub],
      total: 1,
      limit: 50,
      offset: 0,
    })
    const store = useAdminStore()

    await store.fetchTenants()

    expect(api.get).toHaveBeenCalledWith('/admin/tenants?limit=50&offset=0')
    expect(store.tenants).toHaveLength(1)
    expect(store.tenants[0].name).toBe('Acme')
    expect(store.totalTenants).toBe(1)
  })

  it('fetchTenants pasa params limit/offset cuando se proporcionan', async () => {
    vi.mocked(api.get).mockResolvedValue({
      items: [],
      total: 0,
      limit: 25,
      offset: 25,
    })
    const store = useAdminStore()

    await store.fetchTenants({ limit: 25, offset: 25 })

    expect(api.get).toHaveBeenCalledWith('/admin/tenants?limit=25&offset=25')
  })

  it('fetchTenant carga un tenant en current', async () => {
    vi.mocked(api.get).mockResolvedValue(tenantDetailStub)
    const store = useAdminStore()

    await store.fetchTenant(1)

    expect(api.get).toHaveBeenCalledWith('/admin/tenants/1')
    expect(store.currentTenant?.id).toBe(1)
    expect(store.currentTenant?.users).toHaveLength(1)
  })

  it('createTenant POSTea y refresca la lista', async () => {
    const payload: TenantCreateRequest = {
      tenant_name: 'NuevoTenant',
      plan: 'basic',
      admin_email: 'root@nuevo.test',
      admin_password: 'secret123',
      admin_display_name: 'Root Nuevo',
    }
    vi.mocked(api.post).mockResolvedValue(tenantDetailStub)
    vi.mocked(api.get).mockResolvedValue({
      items: [tenantStub],
      total: 1,
      limit: 50,
      offset: 0,
    })
    const store = useAdminStore()

    const created = await store.createTenant(payload)

    expect(api.post).toHaveBeenCalledWith('/admin/tenants', payload)
    expect(created.id).toBe(1)
    expect(api.get).toHaveBeenCalledWith('/admin/tenants?limit=50&offset=0')
  })

  it('updateTenant PATCH y refresca currentTenant si coincide id', async () => {
    // Backend PATCH /admin/tenants/:id devuelve TenantListItem (sin users[]).
    // El store debe refrescar con fetchTenant para conservar el detalle completo.
    vi.mocked(api.patch).mockResolvedValue({
      ...tenantStub,
      plan: 'enterprise',
    })
    vi.mocked(api.get).mockImplementation((path: string) => {
      if (path === '/admin/tenants/1') {
        return Promise.resolve({
          ...tenantDetailStub,
          plan: 'enterprise',
        })
      }
      return Promise.resolve({ items: [], total: 0, limit: 50, offset: 0 })
    })
    const store = useAdminStore()
    store.currentTenant = tenantDetailStub

    const updated = await store.updateTenant(1, { plan: 'enterprise' })

    expect(api.patch).toHaveBeenCalledWith('/admin/tenants/1', {
      plan: 'enterprise',
    })
    expect(updated.plan).toBe('enterprise')
    expect(store.currentTenant?.plan).toBe('enterprise')
    // Regresión: el PATCH del backend no devuelve users, pero el store
    // debe refrescar con fetchTenant para que la vista no crashee.
    expect(store.currentTenant?.users).toBeDefined()
    expect(store.currentTenant?.users.length).toBe(1)
    expect(api.get).toHaveBeenCalledWith('/admin/tenants/1')
  })

  it('updateTenant no refresca currentTenant si el id no coincide', async () => {
    vi.mocked(api.patch).mockResolvedValue({ ...tenantStub, id: 99 })
    vi.mocked(api.get).mockResolvedValue({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    })
    const store = useAdminStore()
    store.currentTenant = tenantDetailStub  // id=1

    await store.updateTenant(99, { plan: 'enterprise' })

    // Sólo se llamó al endpoint de listado, no al detalle de id=99.
    expect(api.get).not.toHaveBeenCalledWith('/admin/tenants/99')
  })

  it('deleteTenant DELETE y limpia current si coincide', async () => {
    vi.mocked(api.delete).mockResolvedValue(undefined)
    vi.mocked(api.get).mockResolvedValue({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    })
    const store = useAdminStore()
    store.currentTenant = tenantDetailStub

    await store.deleteTenant(1)

    expect(api.delete).toHaveBeenCalledWith('/admin/tenants/1')
    expect(store.currentTenant).toBeNull()
  })

  it('deleteTenant no toca current si id distinto', async () => {
    vi.mocked(api.delete).mockResolvedValue(undefined)
    vi.mocked(api.get).mockResolvedValue({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    })
    const store = useAdminStore()
    store.currentTenant = tenantDetailStub

    await store.deleteTenant(99)

    expect(store.currentTenant?.id).toBe(1)
  })
})

describe('useAdminStore — users cross-tenant', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('fetchUsers sin filtro devuelve la lista global', async () => {
    vi.mocked(api.get).mockResolvedValue({
      items: [userStub],
      total: 1,
      limit: 50,
      offset: 0,
    })
    const store = useAdminStore()

    await store.fetchUsers()

    expect(api.get).toHaveBeenCalledWith('/admin/users?limit=50&offset=0')
    expect(store.users).toHaveLength(1)
    expect(store.totalUsers).toBe(1)
  })

  it('fetchUsers con tenantId añade el query param', async () => {
    vi.mocked(api.get).mockResolvedValue({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    })
    const store = useAdminStore()

    await store.fetchUsers({ tenantId: 7 })

    expect(api.get).toHaveBeenCalledWith(
      '/admin/users?limit=50&offset=0&tenant_id=7',
    )
  })

  it('createUser POSTea con tenant_id en payload', async () => {
    const payload: AdminUserCreateRequest = {
      tenant_id: 1,
      email: 'op@acme.test',
      password: 'secret123',
      display_name: 'Operador',
      role: 'operator',
    }
    vi.mocked(api.post).mockResolvedValue(userStub)
    const store = useAdminStore()

    const created = await store.createUser(payload)

    expect(api.post).toHaveBeenCalledWith('/admin/users', payload)
    expect(created.email).toBe('admin@acme.test')
  })

  it('updateUser PATCH y refresca currentTenant si coincide', async () => {
    vi.mocked(api.patch).mockResolvedValue({ ...userStub, role: 'operator' })
    vi.mocked(api.get).mockResolvedValue(tenantDetailStub)
    const store = useAdminStore()
    store.currentTenant = tenantDetailStub

    await store.updateUser(10, { role: 'operator' })

    expect(api.patch).toHaveBeenCalledWith('/admin/users/10', {
      role: 'operator',
    })
    expect(api.get).toHaveBeenCalledWith('/admin/tenants/1')
  })

  it('updateUser sin currentTenant no recarga tenant', async () => {
    vi.mocked(api.patch).mockResolvedValue({ ...userStub, active: false })
    const store = useAdminStore()

    await store.updateUser(10, { active: false })

    expect(api.get).not.toHaveBeenCalledWith('/admin/tenants/1')
  })

  it('deleteUser DELETE y refresca currentTenant si lo está mostrando', async () => {
    vi.mocked(api.delete).mockResolvedValue(undefined)
    vi.mocked(api.get).mockResolvedValue(tenantDetailStub)
    const store = useAdminStore()
    store.currentTenant = tenantDetailStub

    await store.deleteUser(10, { tenantId: 1 })

    expect(api.delete).toHaveBeenCalledWith('/admin/users/10')
    expect(api.get).toHaveBeenCalledWith('/admin/tenants/1')
  })

  it('deleteUser sin tenantId no recarga', async () => {
    vi.mocked(api.delete).mockResolvedValue(undefined)
    const store = useAdminStore()

    await store.deleteUser(10)

    expect(api.get).not.toHaveBeenCalled()
  })
})

describe('useAdminStore — error handling', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('fetchTenants propaga error y deja loading=false', async () => {
    vi.mocked(api.get).mockRejectedValue(new Error('boom'))
    const store = useAdminStore()

    await expect(store.fetchTenants()).rejects.toThrow('boom')
    expect(store.loading).toBe(false)
  })
})
