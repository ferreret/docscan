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
        <button @click="router.push('/applications')" class="text-xs text-subtext hover:text-text mb-2 inline-flex items-center gap-1 transition-colors">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" /></svg>
          Aplicaciones
        </button>
        <h1 class="text-2xl font-bold text-text">{{ appStore.current.name }}</h1>
        <p class="text-xs text-subtext mt-1">{{ appStore.current.description || 'Sin descripción' }}</p>
      </div>
      <div class="flex gap-2">
        <button
          @click="router.push(`/applications/${appId}/pipeline`)"
          class="bg-white text-primary border border-primary/40 rounded-md px-4 py-2 text-[13px] font-medium hover:bg-primary hover:text-white transition-colors"
        >
          Editar pipeline
        </button>
        <button
          @click="onCreateBatch"
          class="bg-primary text-white rounded-md px-4 py-2 text-[13px] font-semibold hover:bg-primary-hover transition-colors shadow-sm"
        >
          + Nuevo lote
        </button>
        <button
          @click="onDelete"
          class="text-danger border border-danger/40 bg-white rounded-md px-4 py-2 text-[13px] font-medium hover:bg-danger hover:text-white transition-colors"
        >
          Eliminar
        </button>
      </div>
    </div>

    <!-- Info -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
      <div class="bg-white rounded-lg border border-surface-0 p-4">
        <p class="text-[11px] text-subtext uppercase tracking-wide font-medium">Estado</p>
        <p class="text-sm font-semibold mt-1.5" :class="appStore.current.active ? 'text-success' : 'text-subtext'">
          {{ appStore.current.active ? 'Activa' : 'Inactiva' }}
        </p>
      </div>
      <div class="bg-white rounded-lg border border-surface-0 p-4">
        <p class="text-[11px] text-subtext uppercase tracking-wide font-medium">Formato salida</p>
        <p class="text-sm font-semibold text-text mt-1.5">{{ appStore.current.output_format || 'tiff' }}</p>
      </div>
      <div class="bg-white rounded-lg border border-surface-0 p-4">
        <p class="text-[11px] text-subtext uppercase tracking-wide font-medium">Auto-transferencia</p>
        <p class="text-sm font-semibold text-text mt-1.5">{{ appStore.current.auto_transfer ? 'Sí' : 'No' }}</p>
      </div>
      <div class="bg-white rounded-lg border border-surface-0 p-4">
        <p class="text-[11px] text-subtext uppercase tracking-wide font-medium">Lotes</p>
        <p class="text-sm font-semibold text-text mt-1.5">{{ batchStore.items.length }}</p>
      </div>
    </div>

    <!-- Lotes de esta aplicación -->
    <div class="bg-white rounded-lg border border-surface-0 overflow-hidden">
      <div class="px-5 py-3 border-b border-surface-0 bg-mantle">
        <h2 class="text-[13px] font-semibold text-text uppercase tracking-wide">Lotes</h2>
      </div>
      <div v-if="batchStore.items.length === 0" class="px-5 py-10 text-sm text-subtext text-center">
        Sin lotes. Crea uno para empezar a subir documentos.
      </div>
      <div v-else>
        <router-link
          v-for="batch in batchStore.items"
          :key="batch.id"
          :to="`/batches/${batch.id}`"
          class="flex items-center justify-between px-5 py-3 border-b border-surface-0 last:border-b-0 hover:bg-mantle transition-colors"
        >
          <div>
            <p class="text-[13px] font-medium text-text">Lote #{{ batch.id }}</p>
            <p class="text-xs text-subtext">{{ batch.page_count }} páginas — {{ new Date(batch.created_at).toLocaleDateString('es-ES') }}</p>
          </div>
          <span
            class="text-[11px] px-2 py-0.5 rounded-full font-medium border"
            :class="{
              'bg-warning-soft text-warning border-warning/30': batch.state === 'created',
              'bg-primary-soft text-primary border-primary/30': batch.state === 'read',
              'bg-danger-soft text-danger border-danger/30': batch.state.startsWith('error'),
            }"
          >
            {{ batch.state }}
          </span>
        </router-link>
      </div>
    </div>
  </div>
  <div v-else class="text-sm text-subtext">Cargando...</div>
</template>
