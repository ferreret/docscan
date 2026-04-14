<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { api, ApiError } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import type { TeamUser, Invitation, Paginated } from '@/api/types'

const auth = useAuthStore()

const users = ref<TeamUser[]>([])
const invitations = ref<Invitation[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

const showInvite = ref(false)
const inviteEmail = ref('')
const inviteRole = ref('operator')
const inviteError = ref<string | null>(null)
const creating = ref(false)

const lastToken = ref<string | null>(null)
const copied = ref(false)

const isAdmin = computed(() => auth.user?.role === 'company_admin')

async function loadAll() {
  loading.value = true
  error.value = null
  try {
    const [u, i] = await Promise.all([
      api.get<Paginated<TeamUser>>('/users'),
      api.get<Paginated<Invitation>>('/invitations'),
    ])
    users.value = u.items
    invitations.value = i.items
  } catch (e) {
    error.value = e instanceof ApiError ? e.detail : 'Error cargando equipo'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (isAdmin.value) loadAll()
})

watch(isAdmin, (v) => {
  if (v) loadAll()
})

async function onCreateInvitation() {
  inviteError.value = null
  creating.value = true
  try {
    const inv = await api.post<Invitation>('/invitations', {
      email: inviteEmail.value,
      role: inviteRole.value,
    })
    invitations.value.unshift(inv)
    lastToken.value = inv.token
    inviteEmail.value = ''
  } catch (e) {
    inviteError.value = e instanceof ApiError ? e.detail : 'Error al invitar'
  } finally {
    creating.value = false
  }
}

async function onRevoke(id: number) {
  if (!confirm('¿Revocar esta invitación?')) return
  await api.delete(`/invitations/${id}`)
  invitations.value = invitations.value.filter((i) => i.id !== id)
}

async function onToggleActive(u: TeamUser) {
  if (u.id === auth.user?.id) return
  const updated = await api.patch<TeamUser>(`/users/${u.id}`, { active: !u.active })
  Object.assign(u, updated)
}

async function onChangeRole(u: TeamUser, role: string) {
  if (role === u.role) return
  try {
    const updated = await api.patch<TeamUser>(`/users/${u.id}`, { role })
    Object.assign(u, updated)
  } catch (e) {
    error.value = e instanceof ApiError ? e.detail : 'Error cambiando rol'
  }
}

async function onDeleteUser(u: TeamUser) {
  if (u.id === auth.user?.id) return
  if (!confirm(`¿Eliminar a ${u.email}? Esta acción es permanente.`)) return
  await api.delete(`/users/${u.id}`)
  users.value = users.value.filter((x) => x.id !== u.id)
}

function invitationUrl(token: string) {
  return `${window.location.origin}/accept-invitation/${token}`
}

async function copyToken(token: string) {
  try {
    await navigator.clipboard.writeText(invitationUrl(token))
    copied.value = true
    setTimeout(() => (copied.value = false), 2000)
  } catch {
    /* ignore */
  }
}

function closeInvite() {
  showInvite.value = false
  lastToken.value = null
  inviteError.value = null
}
</script>

<template>
  <div v-if="!isAdmin" class="bg-white rounded-lg border border-surface-0 p-10 text-center">
    <p class="text-sm text-subtext">
      Solo los administradores pueden gestionar el equipo.
    </p>
  </div>

  <div v-else>
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-text">Equipo</h1>
        <p class="text-xs text-subtext mt-1">Usuarios e invitaciones de {{ auth.user?.tenant_name }}</p>
      </div>
      <button
        @click="showInvite = true"
        class="bg-primary text-white rounded-md px-4 py-2 text-[13px] font-semibold hover:bg-primary-hover transition-colors shadow-sm"
      >
        + Invitar usuario
      </button>
    </div>

    <div v-if="error" class="text-xs text-danger bg-danger-soft border border-danger/30 rounded-md px-3 py-2 mb-4">{{ error }}</div>
    <div v-if="loading" class="text-sm text-subtext">Cargando...</div>

    <!-- Invitaciones pendientes -->
    <div v-if="invitations.length" class="bg-white rounded-lg border border-surface-0 overflow-hidden mb-6">
      <div class="px-5 py-3 border-b border-surface-0 bg-mantle">
        <h2 class="text-[13px] font-semibold text-text uppercase tracking-wide">
          Invitaciones pendientes ({{ invitations.length }})
        </h2>
      </div>
      <div>
        <div
          v-for="inv in invitations"
          :key="inv.id"
          class="flex items-center justify-between px-5 py-3 border-b border-surface-0 last:border-b-0"
        >
          <div class="min-w-0">
            <p class="text-[13px] font-medium text-text truncate">{{ inv.email }}</p>
            <p class="text-xs text-subtext">
              {{ inv.role }} · expira {{ new Date(inv.expires_at).toLocaleDateString('es-ES') }}
            </p>
          </div>
          <div class="flex gap-2 ml-4 shrink-0">
            <button
              @click="copyToken(inv.token)"
              class="text-xs px-2.5 py-1 bg-primary-soft text-primary border border-primary/30 rounded hover:bg-primary hover:text-white transition-colors font-medium"
            >
              Copiar enlace
            </button>
            <button
              @click="onRevoke(inv.id)"
              class="text-xs text-danger border border-danger/40 bg-white px-2.5 py-1 rounded hover:bg-danger hover:text-white transition-colors"
            >
              Revocar
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Usuarios -->
    <div class="bg-white rounded-lg border border-surface-0 overflow-hidden">
      <div class="px-5 py-3 border-b border-surface-0 bg-mantle">
        <h2 class="text-[13px] font-semibold text-text uppercase tracking-wide">
          Usuarios ({{ users.length }})
        </h2>
      </div>
      <div>
        <div
          v-for="u in users"
          :key="u.id"
          class="flex items-center justify-between px-5 py-3 border-b border-surface-0 last:border-b-0"
        >
          <div class="flex items-center gap-3 min-w-0">
            <div class="w-9 h-9 rounded-full bg-primary-soft border border-primary/30 flex items-center justify-center text-primary font-semibold text-xs shrink-0">
              {{ u.display_name?.charAt(0)?.toUpperCase() || u.email.charAt(0).toUpperCase() }}
            </div>
            <div class="min-w-0">
              <p class="text-[13px] font-medium text-text truncate">
                {{ u.display_name || u.email }}
                <span v-if="u.id === auth.user?.id" class="text-[10px] text-subtext ml-1">(tú)</span>
              </p>
              <p class="text-xs text-subtext truncate">{{ u.email }}</p>
            </div>
          </div>
          <div class="flex items-center gap-2 shrink-0 ml-4">
            <select
              :value="u.role"
              @change="(e) => onChangeRole(u, (e.target as HTMLSelectElement).value)"
              :disabled="u.id === auth.user?.id"
              class="text-xs border border-surface-1 rounded px-2 py-1 bg-white text-text disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <option value="operator">operator</option>
              <option value="company_admin">company_admin</option>
            </select>
            <button
              @click="onToggleActive(u)"
              :disabled="u.id === auth.user?.id"
              class="text-[11px] px-2 py-1 rounded-full font-medium border disabled:opacity-50 disabled:cursor-not-allowed"
              :class="u.active
                ? 'bg-success-soft text-success border-success/30 hover:bg-success hover:text-white'
                : 'bg-crust text-subtext border-surface-0 hover:bg-subtext hover:text-white'"
            >
              {{ u.active ? 'Activo' : 'Inactivo' }}
            </button>
            <button
              @click="onDeleteUser(u)"
              :disabled="u.id === auth.user?.id"
              class="text-overlay-0 hover:text-danger p-1 rounded transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
              title="Eliminar usuario"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Modal invitar -->
    <div v-if="showInvite" class="fixed inset-0 bg-text/40 backdrop-blur-sm flex items-center justify-center z-50 px-4" @click.self="closeInvite">
      <form
        v-if="!lastToken"
        @submit.prevent="onCreateInvitation"
        class="bg-white rounded-lg shadow-xl border border-surface-0 p-6 w-full max-w-md space-y-4"
      >
        <h2 class="text-base font-semibold text-text">Invitar usuario</h2>
        <div v-if="inviteError" class="text-xs text-danger bg-danger-soft border border-danger/30 rounded-md px-3 py-2">{{ inviteError }}</div>
        <div>
          <label class="block text-xs font-medium text-subtext mb-1">Email</label>
          <input
            v-model="inviteEmail"
            type="email"
            required
            placeholder="usuario@empresa.com"
            class="w-full rounded-md border border-surface-1 bg-white px-3 py-2 text-[13px] text-text focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
          />
        </div>
        <div>
          <label class="block text-xs font-medium text-subtext mb-1">Rol</label>
          <select
            v-model="inviteRole"
            class="w-full rounded-md border border-surface-1 bg-white px-3 py-2 text-[13px] text-text focus:outline-none focus:border-primary"
          >
            <option value="operator">operator</option>
            <option value="company_admin">company_admin</option>
          </select>
        </div>
        <div class="flex justify-end gap-2 pt-2">
          <button type="button" @click="closeInvite" class="px-4 py-2 text-[13px] font-medium text-text bg-crust hover:bg-surface-0 border border-surface-1 rounded-md transition-colors">Cancelar</button>
          <button
            type="submit"
            :disabled="creating"
            class="bg-primary text-white px-4 py-2 text-[13px] font-semibold rounded-md hover:bg-primary-hover disabled:opacity-50 transition-colors"
          >
            {{ creating ? 'Creando…' : 'Crear invitación' }}
          </button>
        </div>
      </form>

      <div
        v-else
        class="bg-white rounded-lg shadow-xl border border-surface-0 p-6 w-full max-w-md space-y-4"
      >
        <h2 class="text-base font-semibold text-text">Invitación creada</h2>
        <p class="text-xs text-subtext">
          Copia este enlace y envíaselo al usuario. Expira en 7 días.
        </p>
        <div class="bg-mantle border border-surface-0 rounded-md p-3 break-all text-xs font-mono text-text">
          {{ invitationUrl(lastToken) }}
        </div>
        <div class="flex justify-end gap-2 pt-2">
          <button
            @click="copyToken(lastToken!)"
            class="bg-primary text-white px-4 py-2 text-[13px] font-semibold rounded-md hover:bg-primary-hover transition-colors"
          >
            {{ copied ? '¡Copiado!' : 'Copiar enlace' }}
          </button>
          <button @click="closeInvite" class="px-4 py-2 text-[13px] font-medium text-text bg-crust hover:bg-surface-0 border border-surface-1 rounded-md transition-colors">Cerrar</button>
        </div>
      </div>
    </div>
  </div>
</template>
