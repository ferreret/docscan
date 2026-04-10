<script setup lang="ts">
import { onMounted } from 'vue'
import { useApplicationsStore } from '@/stores/applications'
import { useBatchesStore } from '@/stores/batches'

const apps = useApplicationsStore()
const batches = useBatchesStore()

onMounted(() => {
  apps.fetchAll()
  batches.fetchAll()
})
</script>

<template>
  <div>
    <h1 class="text-2xl font-bold text-gray-900 mb-6">Panel de control</h1>

    <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
      <div class="bg-white rounded-xl border border-gray-200 p-6">
        <p class="text-sm font-medium text-gray-500">Aplicaciones</p>
        <p class="text-3xl font-bold text-gray-900 mt-2">{{ apps.items.length }}</p>
      </div>
      <div class="bg-white rounded-xl border border-gray-200 p-6">
        <p class="text-sm font-medium text-gray-500">Lotes</p>
        <p class="text-3xl font-bold text-gray-900 mt-2">{{ batches.items.length }}</p>
      </div>
      <div class="bg-white rounded-xl border border-gray-200 p-6">
        <p class="text-sm font-medium text-gray-500">Páginas totales</p>
        <p class="text-3xl font-bold text-gray-900 mt-2">
          {{ batches.items.reduce((sum, b) => sum + b.page_count, 0) }}
        </p>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- Aplicaciones recientes -->
      <div class="bg-white rounded-xl border border-gray-200">
        <div class="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <h2 class="font-semibold text-gray-900">Aplicaciones</h2>
          <router-link to="/applications" class="text-sm text-blue-600 hover:text-blue-700">Ver todas</router-link>
        </div>
        <div v-if="apps.items.length === 0" class="p-6 text-sm text-gray-500 text-center">
          Sin aplicaciones. Crea una para empezar.
        </div>
        <div v-else class="divide-y divide-gray-100">
          <router-link
            v-for="app in apps.items.slice(0, 5)"
            :key="app.id"
            :to="`/applications/${app.id}`"
            class="flex items-center justify-between px-6 py-3 hover:bg-gray-50 transition-colors"
          >
            <div>
              <p class="text-sm font-medium text-gray-900">{{ app.name }}</p>
              <p class="text-xs text-gray-500">{{ app.description || 'Sin descripción' }}</p>
            </div>
            <span
              class="text-xs px-2 py-1 rounded-full"
              :class="app.active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'"
            >
              {{ app.active ? 'Activa' : 'Inactiva' }}
            </span>
          </router-link>
        </div>
      </div>

      <!-- Lotes recientes -->
      <div class="bg-white rounded-xl border border-gray-200">
        <div class="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <h2 class="font-semibold text-gray-900">Lotes recientes</h2>
          <router-link to="/batches" class="text-sm text-blue-600 hover:text-blue-700">Ver todos</router-link>
        </div>
        <div v-if="batches.items.length === 0" class="p-6 text-sm text-gray-500 text-center">
          Sin lotes todavía.
        </div>
        <div v-else class="divide-y divide-gray-100">
          <router-link
            v-for="batch in batches.items.slice(0, 5)"
            :key="batch.id"
            :to="`/batches/${batch.id}`"
            class="flex items-center justify-between px-6 py-3 hover:bg-gray-50 transition-colors"
          >
            <div>
              <p class="text-sm font-medium text-gray-900">Lote #{{ batch.id }}</p>
              <p class="text-xs text-gray-500">{{ batch.page_count }} páginas</p>
            </div>
            <span
              class="text-xs px-2 py-1 rounded-full"
              :class="{
                'bg-yellow-100 text-yellow-700': batch.state === 'created',
                'bg-blue-100 text-blue-700': batch.state === 'read',
                'bg-red-100 text-red-700': batch.state === 'error_read',
              }"
            >
              {{ batch.state }}
            </span>
          </router-link>
        </div>
      </div>
    </div>
  </div>
</template>
