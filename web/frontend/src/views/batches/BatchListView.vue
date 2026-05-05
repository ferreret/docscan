<script setup lang="ts">
import { onMounted } from 'vue'
import { useBatchesStore } from '@/stores/batches'
import { useBatchesPolling } from '@/composables/useBatchesPolling'
import { storeToRefs } from 'pinia'
import BatchStateBadge from '@/components/batches/BatchStateBadge.vue'

const store = useBatchesStore()
const { items } = storeToRefs(store)

onMounted(() => store.fetchAll())

// Auto-refresh del listado mientras haya lotes en running/transferring.
// Polling silencioso (no toca store.loading → no parpadea "Cargando...").
useBatchesPolling(items, () => store.fetchAll(undefined, { silent: true }))
</script>

<template>
  <div>
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-text">Lotes</h1>
      <p class="text-xs text-subtext mt-1">Todos los lotes del inquilino</p>
    </div>

    <div v-if="store.loading" class="text-sm text-subtext">Cargando...</div>
    <div v-else-if="store.items.length === 0" class="bg-base rounded-lg border border-surface-0 py-16 text-center">
      <p class="text-sm text-subtext">No hay lotes. Crea uno desde una aplicación.</p>
    </div>
    <div v-else class="bg-base rounded-lg border border-surface-0 overflow-hidden">
      <router-link
        v-for="batch in store.items"
        :key="batch.id"
        :to="`/batches/${batch.id}`"
        class="flex items-center justify-between px-5 py-4 border-b border-surface-0 last:border-b-0 hover:bg-mantle transition-colors"
      >
        <div>
          <p class="text-[13px] font-medium text-text">Lote #{{ batch.id }}</p>
          <p class="text-xs text-subtext mt-0.5">
            App #{{ batch.application_id }} · {{ batch.page_count }} páginas ·
            {{ new Date(batch.created_at).toLocaleDateString('es-ES') }}
          </p>
        </div>
        <BatchStateBadge :state="batch.state" />
      </router-link>
    </div>
  </div>
</template>
