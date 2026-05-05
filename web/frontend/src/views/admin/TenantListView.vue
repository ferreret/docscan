<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { ApiError } from '@/api/client'
import { useAdminStore } from '@/stores/admin'
import { useToast } from '@/composables/useToast'
import type { TenantListItem } from '@/api/types'

const store = useAdminStore()
const toast = useToast()

const tenants = computed(() => store.tenants)
const loading = computed(() => store.loading)

onMounted(() => {
  store.fetchTenants().catch((e) => {
    toast.error(e instanceof ApiError ? e.detail : 'Error cargando tenants')
  })
})

async function onToggleActive(t: TenantListItem) {
  try {
    await store.updateTenant(t.id, { active: !t.active })
    toast.success(t.active ? `${t.name} suspendido` : `${t.name} activado`)
  } catch (e) {
    toast.error(e instanceof ApiError ? e.detail : 'Error actualizando tenant')
  }
}

async function onDelete(t: TenantListItem) {
  const typed = window.prompt(
    `Vas a eliminar "${t.name}" y todos sus datos (usuarios, aplicaciones, lotes, archivos).\n\n` +
      `Esta acción es IRREVERSIBLE.\n\n` +
      `Escribe el nombre exacto del tenant para confirmar:`,
  )
  if (typed !== t.name) {
    if (typed !== null) toast.info('Confirmación cancelada')
    return
  }
  try {
    await store.deleteTenant(t.id)
    toast.success(`${t.name} eliminado`)
  } catch (e) {
    toast.error(e instanceof ApiError ? e.detail : 'Error eliminando tenant')
  }
}

function planClass(plan: string): string {
  if (plan === 'enterprise') return 'bg-primary-soft text-primary border-primary/30'
  if (plan === 'basic') return 'bg-warning-soft text-warning border-warning/30'
  return 'bg-crust text-subtext border-surface-1'
}

function fmtDate(s: string): string {
  return new Date(s).toLocaleDateString('es-ES')
}
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-text">Tenants</h1>
        <p class="text-xs text-subtext mt-1">
          Administración global de la plataforma
        </p>
      </div>
      <router-link
        to="/admin/tenants/new"
        data-test="new-tenant-cta"
        class="bg-primary text-base rounded-md px-4 py-2 text-[13px] font-semibold hover:bg-primary-hover transition-colors shadow-sm"
      >
        + Nuevo tenant
      </router-link>
    </div>

    <div v-if="loading && !tenants.length" class="text-sm text-subtext">Cargando…</div>

    <div
      v-else-if="!tenants.length"
      class="bg-base rounded-lg border border-surface-0 p-10 text-center"
    >
      <p class="text-sm text-subtext mb-4">No hay tenants registrados.</p>
      <router-link
        to="/admin/tenants/new"
        data-test="empty-cta"
        class="inline-block bg-primary text-base rounded-md px-4 py-2 text-[13px] font-semibold hover:bg-primary-hover transition-colors"
      >
        Crear el primero
      </router-link>
    </div>

    <div v-else class="bg-base rounded-lg border border-surface-0 overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-mantle border-b border-surface-0">
          <tr class="text-left text-[11px] uppercase tracking-wide text-subtext">
            <th class="px-5 py-3 font-semibold">Nombre</th>
            <th class="px-3 py-3 font-semibold">Plan</th>
            <th class="px-3 py-3 font-semibold text-right">Usuarios</th>
            <th class="px-3 py-3 font-semibold text-right">Apps</th>
            <th class="px-3 py-3 font-semibold text-right">Lotes</th>
            <th class="px-3 py-3 font-semibold">Creado</th>
            <th class="px-3 py-3 font-semibold text-right">Acciones</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="t in tenants"
            :key="t.id"
            data-test="tenant-row"
            class="border-b border-surface-0 last:border-b-0 hover:bg-mantle/40 transition-colors"
            :class="{ 'opacity-50': !t.active }"
          >
            <td class="px-5 py-3">
              <router-link
                :to="`/admin/tenants/${t.id}`"
                class="text-[13px] font-medium text-text hover:text-primary"
              >
                {{ t.name }}
              </router-link>
              <p class="text-[11px] text-subtext font-mono">{{ t.slug }}</p>
            </td>
            <td class="px-3 py-3">
              <span
                class="text-[11px] px-2 py-0.5 rounded-full font-medium border"
                :class="planClass(t.plan)"
              >
                {{ t.plan }}
              </span>
            </td>
            <td class="px-3 py-3 text-right text-[13px] text-text tabular-nums">
              {{ t.stats.n_users }}
            </td>
            <td class="px-3 py-3 text-right text-[13px] text-text tabular-nums">
              {{ t.stats.n_applications }}
            </td>
            <td class="px-3 py-3 text-right text-[13px] text-text tabular-nums">
              {{ t.stats.n_batches }}
            </td>
            <td class="px-3 py-3 text-[12px] text-subtext">{{ fmtDate(t.created_at) }}</td>
            <td class="px-3 py-3">
              <div class="flex items-center justify-end gap-2">
                <button
                  data-test="toggle-active"
                  @click="onToggleActive(t)"
                  class="text-[11px] px-2 py-1 rounded-full font-medium border"
                  :class="t.active
                    ? 'bg-success-soft text-success border-success/30 hover:bg-success hover:text-base'
                    : 'bg-crust text-subtext border-surface-0 hover:bg-subtext hover:text-base'"
                >
                  {{ t.active ? 'Activo' : 'Inactivo' }}
                </button>
                <button
                  data-test="delete-tenant"
                  @click="onDelete(t)"
                  class="text-overlay-0 hover:text-danger p-1 rounded transition-colors"
                  title="Eliminar tenant"
                >
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                      d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
