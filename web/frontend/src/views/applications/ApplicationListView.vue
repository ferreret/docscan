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
      <h1 class="text-2xl font-bold text-gray-900">Aplicaciones</h1>
      <button
        @click="showCreate = true"
        class="bg-blue-600 text-white rounded-lg px-4 py-2 text-sm font-medium hover:bg-blue-700 transition-colors"
      >
        Nueva aplicación
      </button>
    </div>

    <!-- Modal crear -->
    <div v-if="showCreate" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <form @submit.prevent="onCreate" class="bg-white rounded-xl shadow-xl p-6 w-full max-w-md space-y-4">
        <h2 class="text-lg font-semibold text-gray-900">Nueva aplicación</h2>
        <div v-if="createError" class="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{{ createError }}</div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Nombre</label>
          <input v-model="newName" required class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Descripción</label>
          <textarea v-model="newDescription" rows="2" class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"></textarea>
        </div>
        <div class="flex justify-end gap-3">
          <button type="button" @click="showCreate = false" class="px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded-lg">Cancelar</button>
          <button type="submit" class="bg-blue-600 text-white px-4 py-2 text-sm font-medium rounded-lg hover:bg-blue-700">Crear</button>
        </div>
      </form>
    </div>

    <!-- Lista -->
    <div v-if="store.loading" class="text-sm text-gray-500">Cargando...</div>
    <div v-else-if="store.items.length === 0" class="text-center py-12">
      <p class="text-gray-500">No hay aplicaciones todavía.</p>
      <button @click="showCreate = true" class="mt-4 text-blue-600 hover:text-blue-700 text-sm font-medium">Crear la primera</button>
    </div>
    <div v-else class="bg-white rounded-xl border border-gray-200 divide-y divide-gray-100">
      <div
        v-for="app in store.items"
        :key="app.id"
        class="flex items-center justify-between px-6 py-4"
      >
        <router-link :to="`/applications/${app.id}`" class="flex-1 min-w-0">
          <p class="text-sm font-medium text-gray-900">{{ app.name }}</p>
          <p class="text-xs text-gray-500 truncate">{{ app.description || 'Sin descripción' }}</p>
        </router-link>
        <div class="flex items-center gap-3 ml-4">
          <span
            class="text-xs px-2 py-1 rounded-full"
            :class="app.active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'"
          >
            {{ app.active ? 'Activa' : 'Inactiva' }}
          </span>
          <button @click="onDelete(app.id)" class="text-gray-400 hover:text-red-600" title="Eliminar">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
