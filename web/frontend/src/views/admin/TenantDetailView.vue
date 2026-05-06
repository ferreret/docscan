<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ApiError } from '@/api/client'
import { useAdminStore } from '@/stores/admin'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import type { TenantUserItem, TenantUpdateRequest } from '@/api/types'

const props = defineProps<{ id: string }>()

const router = useRouter()
const store = useAdminStore()
const auth = useAuthStore()
const toast = useToast()

const tenantId = computed(() => Number(props.id))
const tenant = computed(() => store.currentTenant)

const formName = ref('')
const formPlan = ref('free')
const savingTenant = ref(false)
const tenantError = ref<string | null>(null)
const usersError = ref<string | null>(null)

const showCreateUser = ref(false)
const newEmail = ref('')
const newDisplayName = ref('')
const newPassword = ref('')
const newRole = ref('operator')
const creatingUser = ref(false)
const createUserError = ref<string | null>(null)

watch(
  tenant,
  (t) => {
    if (t) {
      formName.value = t.name
      formPlan.value = t.plan
    }
  },
  { immediate: true },
)

onMounted(async () => {
  try {
    await store.fetchTenant(tenantId.value)
  } catch (e) {
    tenantError.value = e instanceof ApiError ? e.detail : 'Error cargando tenant'
  }
})

const tenantDirty = computed(() => {
  if (!tenant.value) return false
  return formName.value !== tenant.value.name || formPlan.value !== tenant.value.plan
})

async function onSaveTenant() {
  if (!tenant.value || !tenantDirty.value) return
  const patch: TenantUpdateRequest = {}
  if (formName.value !== tenant.value.name) patch.name = formName.value
  if (formPlan.value !== tenant.value.plan) patch.plan = formPlan.value

  savingTenant.value = true
  tenantError.value = null
  try {
    await store.updateTenant(tenantId.value, patch)
    toast.success('Tenant actualizado')
  } catch (e) {
    tenantError.value = e instanceof ApiError ? e.detail : 'Error actualizando tenant'
  } finally {
    savingTenant.value = false
  }
}

async function onToggleTenantActive() {
  if (!tenant.value) return
  tenantError.value = null
  try {
    await store.updateTenant(tenantId.value, { active: !tenant.value.active })
    toast.success(tenant.value.active ? 'Tenant suspendido' : 'Tenant activado')
  } catch (e) {
    tenantError.value = e instanceof ApiError ? e.detail : 'Error actualizando tenant'
  }
}

async function onChangeUserRole(u: TenantUserItem, role: string) {
  if (role === u.role) return
  usersError.value = null
  try {
    await store.updateUser(u.id, { role })
    toast.success(`Rol de ${u.email} actualizado`)
  } catch (e) {
    usersError.value = e instanceof ApiError ? e.detail : 'Error cambiando rol'
  }
}

async function onToggleUserActive(u: TenantUserItem) {
  usersError.value = null
  try {
    await store.updateUser(u.id, { active: !u.active })
  } catch (e) {
    usersError.value = e instanceof ApiError ? e.detail : 'Error actualizando usuario'
  }
}

async function onDeleteUser(u: TenantUserItem) {
  if (!window.confirm(`¿Eliminar a ${u.email}? Esta acción es permanente.`)) {
    return
  }
  usersError.value = null
  try {
    await store.deleteUser(u.id, { tenantId: tenantId.value })
    toast.success(`${u.email} eliminado`)
  } catch (e) {
    usersError.value = e instanceof ApiError ? e.detail : 'Error eliminando usuario'
  }
}

function openCreateUser() {
  newEmail.value = ''
  newDisplayName.value = ''
  newPassword.value = ''
  newRole.value = 'operator'
  createUserError.value = null
  showCreateUser.value = true
}

function closeCreateUser() {
  showCreateUser.value = false
}

async function onCreateUser() {
  createUserError.value = null
  if (newPassword.value.length < 8) {
    createUserError.value = 'La contraseña debe tener al menos 8 caracteres.'
    return
  }
  creatingUser.value = true
  try {
    await store.createUser({
      tenant_id: tenantId.value,
      email: newEmail.value,
      password: newPassword.value,
      display_name: newDisplayName.value,
      role: newRole.value,
    })
    toast.success(`Usuario ${newEmail.value} creado`)
    showCreateUser.value = false
  } catch (e) {
    createUserError.value = e instanceof ApiError ? e.detail : 'Error creando usuario'
  } finally {
    creatingUser.value = false
  }
}

function backToList() {
  router.push('/admin/tenants')
}

function isSelf(u: TenantUserItem): boolean {
  return auth.user?.id === u.id
}

function fmtDate(s: string): string {
  return new Date(s).toLocaleDateString('es-ES')
}
</script>

<template>
  <div>
    <div class="flex items-center gap-3 mb-2 text-xs text-subtext">
      <button
        @click="backToList"
        class="hover:text-primary transition-colors"
      >
        ← Tenants
      </button>
    </div>

    <div v-if="tenantError" class="text-xs text-danger bg-danger-soft border border-danger/30 rounded-md px-3 py-2 mb-4">
      {{ tenantError }}
    </div>

    <div v-if="!tenant" class="text-sm text-subtext">Cargando…</div>

    <template v-else>
      <!-- Cabecera tenant -->
      <div class="flex items-center justify-between mb-6">
        <div>
          <div class="flex items-center gap-3">
            <h1 class="text-2xl font-bold text-text">{{ tenant.name }}</h1>
            <span
              class="text-[11px] px-2 py-0.5 rounded-full font-medium border"
              :class="tenant.active
                ? 'bg-success-soft text-success border-success/30'
                : 'bg-crust text-subtext border-surface-0'"
            >
              {{ tenant.active ? 'Activo' : 'Suspendido' }}
            </span>
          </div>
          <p class="text-xs text-subtext mt-1 font-mono">{{ tenant.slug }}</p>
        </div>
        <button
          data-test="tenant-active-toggle"
          @click="onToggleTenantActive"
          class="text-[13px] px-3 py-2 rounded-md font-semibold border transition-colors"
          :class="tenant.active
            ? 'bg-base text-warning border-warning/40 hover:bg-warning hover:text-base'
            : 'bg-base text-success border-success/40 hover:bg-success hover:text-base'"
        >
          {{ tenant.active ? 'Suspender' : 'Activar' }}
        </button>
      </div>

      <!-- Stats rápidas -->
      <div class="grid grid-cols-3 gap-3 mb-6">
        <div class="bg-base rounded-lg border border-surface-0 px-4 py-3">
          <p class="text-[11px] uppercase tracking-wide text-subtext">Usuarios</p>
          <p class="text-2xl font-bold text-text tabular-nums">{{ tenant.stats.n_users }}</p>
        </div>
        <div class="bg-base rounded-lg border border-surface-0 px-4 py-3">
          <p class="text-[11px] uppercase tracking-wide text-subtext">Aplicaciones</p>
          <p class="text-2xl font-bold text-text tabular-nums">{{ tenant.stats.n_applications }}</p>
        </div>
        <div class="bg-base rounded-lg border border-surface-0 px-4 py-3">
          <p class="text-[11px] uppercase tracking-wide text-subtext">Lotes</p>
          <p class="text-2xl font-bold text-text tabular-nums">{{ tenant.stats.n_batches }}</p>
        </div>
      </div>

      <!-- Datos del tenant -->
      <div class="bg-base rounded-lg border border-surface-0 overflow-hidden mb-6">
        <div class="px-5 py-3 border-b border-surface-0 bg-mantle">
          <h2 class="text-[13px] font-semibold text-text uppercase tracking-wide">
            Datos del tenant
          </h2>
        </div>
        <div class="p-5 space-y-4">
          <div>
            <label class="block text-xs font-medium text-subtext mb-1">Nombre</label>
            <input
              v-model="formName"
              data-test="tenant-name-input"
              type="text"
              maxlength="200"
              class="w-full max-w-md rounded-md border border-surface-1 bg-base px-3 py-2 text-[13px] text-text focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
            />
          </div>
          <div>
            <label class="block text-xs font-medium text-subtext mb-1">Plan</label>
            <select
              v-model="formPlan"
              data-test="tenant-plan-select"
              class="w-full max-w-xs rounded-md border border-surface-1 bg-base px-3 py-2 text-[13px] text-text focus:outline-none focus:border-primary"
            >
              <option value="free">free</option>
              <option value="basic">basic</option>
              <option value="enterprise">enterprise</option>
            </select>
          </div>
          <div>
            <p class="text-xs text-subtext">
              Creado el {{ fmtDate(tenant.created_at) }}
            </p>
          </div>
          <div class="pt-2 border-t border-surface-0">
            <button
              data-test="save-tenant"
              :disabled="!tenantDirty || savingTenant"
              @click="onSaveTenant"
              class="bg-primary text-base px-4 py-2 text-[13px] font-semibold rounded-md hover:bg-primary-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {{ savingTenant ? 'Guardando…' : 'Guardar cambios' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Usuarios del tenant -->
      <div class="bg-base rounded-lg border border-surface-0 overflow-hidden">
        <div class="px-5 py-3 border-b border-surface-0 bg-mantle flex items-center justify-between">
          <h2 class="text-[13px] font-semibold text-text uppercase tracking-wide">
            Usuarios ({{ tenant.users.length }})
          </h2>
          <button
            data-test="open-create-user"
            @click="openCreateUser"
            class="text-xs px-2.5 py-1 bg-primary-soft text-primary border border-primary/30 rounded hover:bg-primary hover:text-base transition-colors font-medium"
          >
            + Crear usuario
          </button>
        </div>

        <div
          v-if="usersError"
          class="text-xs text-danger bg-danger-soft border-b border-danger/30 px-5 py-2"
        >
          {{ usersError }}
        </div>

        <div v-if="!tenant.users.length" class="px-5 py-8 text-center text-sm text-subtext">
          Este tenant no tiene usuarios todavía.
        </div>

        <div v-else>
          <div
            v-for="u in tenant.users"
            :key="u.id"
            data-test="user-row"
            class="flex items-center justify-between px-5 py-3 border-b border-surface-0 last:border-b-0"
          >
            <div class="flex items-center gap-3 min-w-0" :class="{ 'opacity-50': !u.active }">
              <div class="w-9 h-9 rounded-full bg-primary-soft border border-primary/30 flex items-center justify-center text-primary font-semibold text-xs shrink-0">
                {{ u.display_name?.charAt(0)?.toUpperCase() || u.email.charAt(0).toUpperCase() }}
              </div>
              <div class="min-w-0">
                <p class="text-[13px] font-medium text-text truncate">
                  {{ u.display_name || u.email }}
                  <span v-if="isSelf(u)" class="text-[10px] text-subtext ml-1">(tú)</span>
                </p>
                <p class="text-xs text-subtext truncate">{{ u.email }}</p>
              </div>
            </div>
            <div class="flex items-center gap-2 shrink-0 ml-4">
              <select
                data-test="user-role-select"
                :value="u.role"
                @change="(e) => onChangeUserRole(u, (e.target as HTMLSelectElement).value)"
                :disabled="isSelf(u)"
                class="text-xs border border-surface-1 rounded px-2 py-1 bg-base text-text disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <option value="operator">operator</option>
                <option value="company_admin">company_admin</option>
                <option value="superadmin">superadmin</option>
              </select>
              <button
                data-test="user-active-toggle"
                @click="onToggleUserActive(u)"
                :disabled="isSelf(u)"
                class="text-[11px] px-2 py-1 rounded-full font-medium border disabled:opacity-50 disabled:cursor-not-allowed"
                :class="u.active
                  ? 'bg-success-soft text-success border-success/30 hover:bg-success hover:text-base'
                  : 'bg-crust text-subtext border-surface-0 hover:bg-subtext hover:text-base'"
              >
                {{ u.active ? 'Activo' : 'Inactivo' }}
              </button>
              <button
                data-test="user-delete"
                @click="onDeleteUser(u)"
                :disabled="isSelf(u)"
                class="text-overlay-0 hover:text-danger p-1 rounded transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                title="Eliminar usuario"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Modal crear usuario -->
      <div
        v-if="showCreateUser"
        data-test="create-user-modal"
        class="fixed inset-0 bg-text/40 backdrop-blur-sm flex items-center justify-center z-50 px-4"
        @click.self="closeCreateUser"
        role="dialog"
        aria-modal="true"
      >
        <form
          @submit.prevent="onCreateUser"
          class="bg-base rounded-lg shadow-xl border border-surface-0 p-6 w-full max-w-md space-y-4"
        >
          <h2 class="text-base font-semibold text-text">
            Crear usuario en {{ tenant.name }}
          </h2>

          <div
            v-if="createUserError"
            class="text-xs text-danger bg-danger-soft border border-danger/30 rounded-md px-3 py-2"
          >
            {{ createUserError }}
          </div>

          <div>
            <label class="block text-xs font-medium text-subtext mb-1">Email</label>
            <input
              v-model="newEmail"
              data-test="new-user-email"
              type="email"
              required
              placeholder="usuario@empresa.com"
              class="w-full rounded-md border border-surface-1 bg-base px-3 py-2 text-[13px] text-text focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
            />
          </div>

          <div>
            <label class="block text-xs font-medium text-subtext mb-1">Nombre visible</label>
            <input
              v-model="newDisplayName"
              data-test="new-user-display-name"
              type="text"
              required
              maxlength="200"
              class="w-full rounded-md border border-surface-1 bg-base px-3 py-2 text-[13px] text-text focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
            />
          </div>

          <div>
            <label class="block text-xs font-medium text-subtext mb-1">
              Contraseña
              <span class="text-subtext font-normal">· mín. 8 caracteres</span>
            </label>
            <input
              v-model="newPassword"
              data-test="new-user-password"
              type="password"
              required
              minlength="8"
              class="w-full rounded-md border border-surface-1 bg-base px-3 py-2 text-[13px] text-text focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
            />
          </div>

          <div>
            <label class="block text-xs font-medium text-subtext mb-1">Rol</label>
            <select
              v-model="newRole"
              data-test="new-user-role"
              class="w-full rounded-md border border-surface-1 bg-base px-3 py-2 text-[13px] text-text focus:outline-none focus:border-primary"
            >
              <option value="operator">operator</option>
              <option value="company_admin">company_admin</option>
              <option value="superadmin">superadmin</option>
            </select>
          </div>

          <div class="flex justify-end gap-2 pt-2">
            <button
              type="button"
              @click="closeCreateUser"
              class="px-4 py-2 text-[13px] font-medium text-text bg-crust hover:bg-surface-0 border border-surface-1 rounded-md transition-colors"
            >
              Cancelar
            </button>
            <button
              type="submit"
              data-test="submit-create-user"
              :disabled="creatingUser"
              class="bg-primary text-base px-4 py-2 text-[13px] font-semibold rounded-md hover:bg-primary-hover disabled:opacity-50 transition-colors"
            >
              {{ creatingUser ? 'Creando…' : 'Crear usuario' }}
            </button>
          </div>
        </form>
      </div>
    </template>
  </div>
</template>
