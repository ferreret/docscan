<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useApplicationsStore } from '@/stores/applications'
import { ApiError } from '@/api/client'

const store = useApplicationsStore()
const showCreate = ref(false)
const newName = ref('')
const newDescription = ref('')
const createError = ref<string | null>(null)

onMounted(() => store.fetchAll())

async function onCreate() {
  createError.value = null
  try {
    await store.create({ name: newName.value, description: newDescription.value })
    showCreate.value = false
    newName.value = ''
    newDescription.value = ''
  } catch (e) {
    createError.value = e instanceof ApiError ? e.detail : 'Error al crear'
  }
}

async function onDelete(id: number) {
  if (!confirm('¿Eliminar esta aplicación y todos sus lotes?')) return
  await store.remove(id)
}
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-text">Aplicaciones</h1>
        <p class="text-xs text-subtext mt-1">Perfiles de captura y procesamiento</p>
      </div>
      <button
        @click="showCreate = true"
        class="bg-primary text-white rounded-md px-4 py-2 text-[13px] font-semibold hover:bg-primary-hover transition-colors shadow-sm"
      >
        + Nueva aplicación
      </button>
    </div>

    <!-- Modal crear -->
    <div v-if="showCreate" class="fixed inset-0 bg-text/40 backdrop-blur-sm flex items-center justify-center z-50 px-4">
      <form @submit.prevent="onCreate" class="bg-white rounded-lg shadow-xl border border-surface-0 p-6 w-full max-w-md space-y-4">
        <h2 class="text-base font-semibold text-text">Nueva aplicación</h2>
        <div v-if="createError" class="text-xs text-danger bg-danger-soft border border-danger/30 rounded-md px-3 py-2">{{ createError }}</div>
        <div>
          <label class="block text-xs font-medium text-subtext mb-1">Nombre</label>
          <input v-model="newName" required class="w-full rounded-md border border-surface-1 bg-white px-3 py-2 text-[13px] text-text focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20" />
        </div>
        <div>
          <label class="block text-xs font-medium text-subtext mb-1">Descripción</label>
          <textarea v-model="newDescription" rows="2" class="w-full rounded-md border border-surface-1 bg-white px-3 py-2 text-[13px] text-text focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"></textarea>
        </div>
        <div class="flex justify-end gap-2 pt-2">
          <button type="button" @click="showCreate = false" class="px-4 py-2 text-[13px] font-medium text-text bg-crust hover:bg-surface-0 border border-surface-1 rounded-md transition-colors">Cancelar</button>
          <button type="submit" class="bg-primary text-white px-4 py-2 text-[13px] font-semibold rounded-md hover:bg-primary-hover transition-colors">Crear</button>
        </div>
      </form>
    </div>

    <!-- Lista -->
    <div v-if="store.loading" class="text-sm text-subtext">Cargando...</div>
    <div v-else-if="store.items.length === 0" class="bg-white rounded-lg border border-surface-0 py-16 text-center">
      <p class="text-sm text-subtext">No hay aplicaciones todavía.</p>
      <button @click="showCreate = true" class="mt-3 text-primary hover:text-primary-hover text-[13px] font-medium">Crear la primera</button>
    </div>
    <div v-else class="bg-white rounded-lg border border-surface-0 overflow-hidden">
      <div
        v-for="app in store.items"
        :key="app.id"
        class="flex items-center justify-between px-5 py-4 border-b border-surface-0 last:border-b-0 hover:bg-mantle transition-colors"
      >
        <router-link :to="`/applications/${app.id}`" class="flex-1 min-w-0">
          <p class="text-[13px] font-medium text-text">{{ app.name }}</p>
          <p class="text-xs text-subtext truncate mt-0.5">{{ app.description || 'Sin descripción' }}</p>
        </router-link>
        <div class="flex items-center gap-3 ml-4">
          <span
            class="text-[11px] px-2 py-0.5 rounded-full font-medium border"
            :class="app.active
              ? 'bg-success-soft text-success border-success/30'
              : 'bg-crust text-subtext border-surface-0'"
          >
            {{ app.active ? 'Activa' : 'Inactiva' }}
          </span>
          <button @click="onDelete(app.id)" class="text-overlay-0 hover:text-danger p-1 rounded transition-colors" title="Eliminar">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
