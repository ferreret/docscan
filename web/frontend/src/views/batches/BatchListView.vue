<script setup lang="ts">
import { onMounted } from 'vue'
import { useBatchesStore } from '@/stores/batches'

const store = useBatchesStore()

onMounted(() => store.fetchAll())
</script>

<template>
  <div>
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-text">Lotes</h1>
      <p class="text-xs text-subtext mt-1">Todos los lotes del inquilino</p>
    </div>

    <div v-if="store.loading" class="text-sm text-subtext">Cargando...</div>
    <div v-else-if="store.items.length === 0" class="bg-white rounded-lg border border-surface-0 py-16 text-center">
      <p class="text-sm text-subtext">No hay lotes. Crea uno desde una aplicación.</p>
    </div>
    <div v-else class="bg-white rounded-lg border border-surface-0 overflow-hidden">
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
</template>
