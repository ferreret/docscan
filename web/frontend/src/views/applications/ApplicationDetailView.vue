<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useApplicationsStore } from '@/stores/applications'
import { useBatchesStore } from '@/stores/batches'

const route = useRoute()
const router = useRouter()
const appStore = useApplicationsStore()
const batchStore = useBatchesStore()

const appId = computed(() => Number(route.params.id))

onMounted(async () => {
  await appStore.fetchOne(appId.value)
  await batchStore.fetchAll(appId.value)
})

async function onDelete() {
  if (!confirm('¿Eliminar esta aplicación y todos sus lotes?')) return
  await appStore.remove(appId.value)
  router.push('/applications')
}

async function onCreateBatch() {
  const batch = await batchStore.create({ application_id: appId.value })
  router.push(`/batches/${batch.id}`)
}
</script>

<template>
  <div v-if="appStore.current">
    <div class="flex items-center justify-between mb-6">
      <div>
        <button @click="router.push('/applications')" class="text-sm text-gray-500 hover:text-gray-700 mb-2 inline-flex items-center gap-1">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" /></svg>
          Aplicaciones
        </button>
        <h1 class="text-2xl font-bold text-gray-900">{{ appStore.current.name }}</h1>
        <p class="text-sm text-gray-500 mt-1">{{ appStore.current.description || 'Sin descripción' }}</p>
      </div>
      <div class="flex gap-3">
        <button
          @click="onCreateBatch"
          class="bg-blue-600 text-white rounded-lg px-4 py-2 text-sm font-medium hover:bg-blue-700 transition-colors"
        >
          Nuevo lote
        </button>
        <button
          @click="onDelete"
          class="text-red-600 hover:text-red-700 rounded-lg px-4 py-2 text-sm font-medium hover:bg-red-50 transition-colors"
        >
          Eliminar
        </button>
      </div>
    </div>

    <!-- Info -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <div class="bg-white rounded-xl border border-gray-200 p-4">
        <p class="text-xs text-gray-500">Estado</p>
        <p class="text-sm font-medium mt-1" :class="appStore.current.active ? 'text-green-600' : 'text-gray-500'">
          {{ appStore.current.active ? 'Activa' : 'Inactiva' }}
        </p>
      </div>
      <div class="bg-white rounded-xl border border-gray-200 p-4">
        <p class="text-xs text-gray-500">Formato salida</p>
        <p class="text-sm font-medium mt-1">{{ appStore.current.output_format || 'tiff' }}</p>
      </div>
      <div class="bg-white rounded-xl border border-gray-200 p-4">
        <p class="text-xs text-gray-500">Auto-transferencia</p>
        <p class="text-sm font-medium mt-1">{{ appStore.current.auto_transfer ? 'Sí' : 'No' }}</p>
      </div>
      <div class="bg-white rounded-xl border border-gray-200 p-4">
        <p class="text-xs text-gray-500">Lotes</p>
        <p class="text-sm font-medium mt-1">{{ batchStore.items.length }}</p>
      </div>
    </div>

    <!-- Lotes de esta aplicación -->
    <div class="bg-white rounded-xl border border-gray-200">
      <div class="px-6 py-4 border-b border-gray-200">
        <h2 class="font-semibold text-gray-900">Lotes</h2>
      </div>
      <div v-if="batchStore.items.length === 0" class="p-6 text-sm text-gray-500 text-center">
        Sin lotes. Crea uno para empezar a subir documentos.
      </div>
      <div v-else class="divide-y divide-gray-100">
        <router-link
          v-for="batch in batchStore.items"
          :key="batch.id"
          :to="`/batches/${batch.id}`"
          class="flex items-center justify-between px-6 py-3 hover:bg-gray-50 transition-colors"
        >
          <div>
            <p class="text-sm font-medium text-gray-900">Lote #{{ batch.id }}</p>
            <p class="text-xs text-gray-500">{{ batch.page_count }} páginas — {{ new Date(batch.created_at).toLocaleDateString('es-ES') }}</p>
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
  </div>
  <div v-else class="text-sm text-gray-500">Cargando...</div>
</template>
