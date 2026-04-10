<script setup lang="ts">
import { onMounted } from 'vue'
import { useBatchesStore } from '@/stores/batches'

const store = useBatchesStore()

onMounted(() => store.fetchAll())
</script>

<template>
  <div>
    <h1 class="text-2xl font-bold text-gray-900 mb-6">Lotes</h1>

    <div v-if="store.loading" class="text-sm text-gray-500">Cargando...</div>
    <div v-else-if="store.items.length === 0" class="text-center py-12">
      <p class="text-gray-500">No hay lotes. Crea uno desde una aplicación.</p>
    </div>
    <div v-else class="bg-white rounded-xl border border-gray-200 divide-y divide-gray-100">
      <router-link
        v-for="batch in store.items"
        :key="batch.id"
        :to="`/batches/${batch.id}`"
        class="flex items-center justify-between px-6 py-4 hover:bg-gray-50 transition-colors"
      >
        <div>
          <p class="text-sm font-medium text-gray-900">Lote #{{ batch.id }}</p>
          <p class="text-xs text-gray-500">
            App #{{ batch.application_id }} — {{ batch.page_count }} páginas —
            {{ new Date(batch.created_at).toLocaleDateString('es-ES') }}
          </p>
        </div>
        <span
          class="text-xs px-2 py-1 rounded-full"
          :class="{
            'bg-yellow-100 text-yellow-700': batch.state === 'created',
            'bg-blue-100 text-blue-700': batch.state === 'read',
            'bg-red-100 text-red-700': batch.state.startsWith('error'),
          }"
        >
          {{ batch.state }}
        </span>
      </router-link>
    </div>
  </div>
</template>
