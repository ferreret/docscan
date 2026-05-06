import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api/client'
import type {
  Paginated,
  TenantListItem,
  TenantDetail,
  TenantCreateRequest,
  TenantUpdateRequest,
  AdminUserListItem,
  AdminUserCreateRequest,
  AdminUserUpdateRequest,
} from '@/api/types'

interface PageParams {
  limit?: number
  offset?: number
}

interface UserListParams extends PageParams {
  tenantId?: number
}

const DEFAULT_LIMIT = 50

export const useAdminStore = defineStore('admin', () => {
  const tenants = ref<TenantListItem[]>([])
  const totalTenants = ref(0)
  const currentTenant = ref<TenantDetail | null>(null)

  const users = ref<AdminUserListItem[]>([])
  const totalUsers = ref(0)

  const loading = ref(false)

  async function fetchTenants(params: PageParams = {}) {
    const limit = params.limit ?? DEFAULT_LIMIT
    const offset = params.offset ?? 0
    loading.value = true
    try {
      const res = await api.get<Paginated<TenantListItem>>(
        `/admin/tenants?limit=${limit}&offset=${offset}`,
      )
      tenants.value = res.items
      totalTenants.value = res.total
    } finally {
      loading.value = false
    }
  }

  async function fetchTenant(id: number) {
    loading.value = true
    try {
      currentTenant.value = await api.get<TenantDetail>(`/admin/tenants/${id}`)
    } finally {
      loading.value = false
    }
  }

  async function createTenant(data: TenantCreateRequest) {
    const tenant = await api.post<TenantDetail>('/admin/tenants', data)
    await fetchTenants()
    return tenant
  }

  async function updateTenant(id: number, data: TenantUpdateRequest) {
    const tenant = await api.patch<TenantListItem>(`/admin/tenants/${id}`, data)
    if (currentTenant.value?.id === id) {
      await fetchTenant(id)
    }
    await fetchTenants()
    return tenant
  }

  async function deleteTenant(id: number) {
    await api.delete(`/admin/tenants/${id}`)
    if (currentTenant.value?.id === id) {
      currentTenant.value = null
    }
    await fetchTenants()
  }

  async function fetchUsers(params: UserListParams = {}) {
    const limit = params.limit ?? DEFAULT_LIMIT
    const offset = params.offset ?? 0
    let path = `/admin/users?limit=${limit}&offset=${offset}`
    if (params.tenantId !== undefined) {
      path += `&tenant_id=${params.tenantId}`
    }
    loading.value = true
    try {
      const res = await api.get<Paginated<AdminUserListItem>>(path)
      users.value = res.items
      totalUsers.value = res.total
    } finally {
      loading.value = false
    }
  }

  async function createUser(data: AdminUserCreateRequest) {
    const user = await api.post<AdminUserListItem>('/admin/users', data)
    if (currentTenant.value?.id === data.tenant_id) {
      await fetchTenant(data.tenant_id)
    }
    return user
  }

  async function updateUser(id: number, data: AdminUserUpdateRequest) {
    const user = await api.patch<AdminUserListItem>(`/admin/users/${id}`, data)
    if (currentTenant.value && user.tenant_id === currentTenant.value.id) {
      await fetchTenant(currentTenant.value.id)
    }
    return user
  }

  async function deleteUser(id: number, opts: { tenantId?: number } = {}) {
    await api.delete(`/admin/users/${id}`)
    if (opts.tenantId !== undefined && currentTenant.value?.id === opts.tenantId) {
      await fetchTenant(opts.tenantId)
    }
  }

  return {
    tenants,
    totalTenants,
    currentTenant,
    users,
    totalUsers,
    loading,
    fetchTenants,
    fetchTenant,
    createTenant,
    updateTenant,
    deleteTenant,
    fetchUsers,
    createUser,
    updateUser,
    deleteUser,
  }
})
