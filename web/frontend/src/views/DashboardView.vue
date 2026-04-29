<script setup lang="ts">
import { onMounted } from 'vue'
import { useApplicationsStore } from '@/stores/applications'
import { useBatchesStore } from '@/stores/batches'
import BatchStateBadge from '@/components/batches/BatchStateBadge.vue'

const apps = useApplicationsStore()
const batches = useBatchesStore()

onMounted(() => {
  apps.fetchAll()
  batches.fetchAll()
})
</script>

<template>
  <div>
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-text">Panel de control</h1>
      <p class="text-xs text-subtext mt-1">Resumen de aplicaciones y lotes</p>
    </div>

    <!-- Stats -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
      <div class="bg-base rounded-lg border border-surface-0 p-5">
        <p class="text-xs font-medium text-subtext uppercase tracking-wide">Aplicaciones</p>
        <p class="text-3xl font-bold text-text mt-2">{{ apps.items.length }}</p>
      </div>
      <div class="bg-base rounded-lg border border-surface-0 p-5">
        <p class="text-xs font-medium text-subtext uppercase tracking-wide">Lotes</p>
        <p class="text-3xl font-bold text-text mt-2">{{ batches.items.length }}</p>
      </div>
      <div class="bg-base rounded-lg border border-surface-0 p-5">
        <p class="text-xs font-medium text-subtext uppercase tracking-wide">Páginas totales</p>
        <p class="text-3xl font-bold text-text mt-2">
          {{ batches.items.reduce((sum, b) => sum + b.page_count, 0) }}
        </p>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <!-- Aplicaciones recientes -->
      <div class="bg-base rounded-lg border border-surface-0 overflow-hidden">
        <div class="px-5 py-3 border-b border-surface-0 bg-mantle flex items-center justify-between">
          <h2 class="text-[13px] font-semibold text-text uppercase tracking-wide">Aplicaciones</h2>
          <router-link to="/applications" class="text-xs text-primary hover:text-primary-hover font-medium">Ver todas →</router-link>
        </div>
        <div v-if="apps.items.length === 0" class="px-5 py-8 text-sm text-subtext text-center">
          Sin aplicaciones. Crea una para empezar.
        </div>
        <div v-else>
          <router-link
            v-for="app in apps.items.slice(0, 5)"
            :key="app.id"
            :to="`/applications/${app.id}`"
            class="flex items-center justify-between px-5 py-3 border-b border-surface-0 last:border-b-0 hover:bg-mantle transition-colors"
          >
            <div class="min-w-0">
              <p class="text-[13px] font-medium text-text truncate">{{ app.name }}</p>
              <p class="text-xs text-subtext truncate">{{ app.description || 'Sin descripción' }}</p>
            </div>
            <span
              class="text-[11px] px-2 py-0.5 rounded-full font-medium shrink-0 ml-3 border"
              :class="app.active
                ? 'bg-success-soft text-success border-success/30'
                : 'bg-crust text-subtext border-surface-0'"
            >
              {{ app.active ? 'Activa' : 'Inactiva' }}
            </span>
          </router-link>
        </div>
      </div>

      <!-- Lotes recientes -->
      <div class="bg-base rounded-lg border border-surface-0 overflow-hidden">
        <div class="px-5 py-3 border-b border-surface-0 bg-mantle flex items-center justify-between">
          <h2 class="text-[13px] font-semibold text-text uppercase tracking-wide">Lotes recientes</h2>
          <router-link to="/batches" class="text-xs text-primary hover:text-primary-hover font-medium">Ver todos →</router-link>
        </div>
        <div v-if="batches.items.length === 0" class="px-5 py-8 text-sm text-subtext text-center">
          Sin lotes todavía.
        </div>
        <div v-else>
          <router-link
            v-for="batch in batches.items.slice(0, 5)"
            :key="batch.id"
            :to="`/batches/${batch.id}`"
            class="flex items-center justify-between px-5 py-3 border-b border-surface-0 last:border-b-0 hover:bg-mantle transition-colors"
          >
            <div>
              <p class="text-[13px] font-medium text-text">Lote #{{ batch.id }}</p>
              <p class="text-xs text-subtext">{{ batch.page_count }} páginas</p>
            </div>
            <BatchStateBadge :state="batch.state" />
          </router-link>
        </div>
      </div>
    </div>
  </div>
</template>
