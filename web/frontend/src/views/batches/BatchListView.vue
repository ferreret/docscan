<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useBatchesStore } from '@/stores/batches'
import { useApplicationsStore } from '@/stores/applications'
import { useBatchesPolling } from '@/composables/useBatchesPolling'
import { useAuthStore } from '@/stores/auth'
import { storeToRefs } from 'pinia'
import BatchStateBadge from '@/components/batches/BatchStateBadge.vue'

const store = useBatchesStore()
const auth = useAuthStore()
const apps = useApplicationsStore()
const { items, total, limit, offset } = storeToRefs(store)

// Estados disponibles para el filtro. ""=todos. Mantengo los nombres
// internos del backend para que el query param vaya literal.
const STATE_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'Todos los estados' },
  { value: 'created', label: 'Creado' },
  { value: 'running', label: 'Procesando' },
  { value: 'read', label: 'Procesado' },
  { value: 'transferring', label: 'Transfiriendo' },
  { value: 'transferred', label: 'Transferido' },
  { value: 'error_read', label: 'Error' },
]

const filterAppId = ref<number | null>(null)
const filterState = ref<string>('')
const currentOffset = ref(0)
const PAGE_SIZE = 50

const totalPages = computed(() =>
  total.value === 0 ? 1 : Math.ceil(total.value / PAGE_SIZE),
)
const currentPageNum = computed(() => Math.floor(currentOffset.value / PAGE_SIZE) + 1)

const rangeStart = computed(() => (total.value === 0 ? 0 : currentOffset.value + 1))
const rangeEnd = computed(() => Math.min(currentOffset.value + PAGE_SIZE, total.value))

async function load(silent = false): Promise<void> {
  await store.fetchAll({
    applicationId: filterAppId.value,
    state: filterState.value || null,
    limit: PAGE_SIZE,
    offset: currentOffset.value,
    silent,
  })
}

function onFiltersChanged(): void {
  // Reset a primera página al cambiar filtros para no quedar fuera de rango.
  currentOffset.value = 0
  load()
}

function goPrev(): void {
  if (currentOffset.value === 0) return
  currentOffset.value = Math.max(0, currentOffset.value - PAGE_SIZE)
  load()
}

function goNext(): void {
  if (currentOffset.value + PAGE_SIZE >= total.value) return
  currentOffset.value += PAGE_SIZE
  load()
}

watch([filterAppId, filterState], onFiltersChanged)

onMounted(async () => {
  // Cargar la lista de aplicaciones del tenant para el dropdown.
  await apps.fetchAll()
  await load()
})

// Auto-refresh: respeta los filtros activos para no descartar lo que
// el usuario está mirando.
useBatchesPolling(items, () => load(true))
</script>

<template>
  <div>
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-text">Lotes</h1>
      <p class="text-xs text-subtext mt-1">Todos los lotes de {{ auth.user?.tenant_name }}</p>
    </div>

    <!-- Barra de filtros -->
    <div class="bg-base rounded-lg border border-surface-0 px-4 py-3 mb-3 flex flex-wrap items-center gap-3">
      <label class="flex items-center gap-2 text-xs text-subtext">
        Aplicación
        <select
          v-model="filterAppId"
          data-testid="filter-application"
          class="text-xs border border-surface-1 rounded px-2 py-1 bg-base text-text min-w-[140px]"
        >
          <option :value="null">Todas</option>
          <option v-for="a in apps.items" :key="a.id" :value="a.id">{{ a.name }}</option>
        </select>
      </label>
      <label class="flex items-center gap-2 text-xs text-subtext">
        Estado
        <select
          v-model="filterState"
          data-testid="filter-state"
          class="text-xs border border-surface-1 rounded px-2 py-1 bg-base text-text min-w-[140px]"
        >
          <option v-for="opt in STATE_OPTIONS" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
      </label>
      <div class="ml-auto text-xs text-overlay-0">
        <span v-if="total > 0">{{ rangeStart }}–{{ rangeEnd }} de {{ total }}</span>
        <span v-else>Sin resultados</span>
      </div>
    </div>

    <div v-if="store.loading" class="text-sm text-subtext">Cargando...</div>
    <div
      v-else-if="store.items.length === 0"
      class="bg-base rounded-lg border border-surface-0 py-16 text-center"
    >
      <p class="text-sm text-subtext">
        <span v-if="filterAppId !== null || filterState">No hay lotes que coincidan con los filtros.</span>
        <span v-else>No hay lotes. Crea uno desde una aplicación.</span>
      </p>
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

    <!-- Paginación -->
    <div
      v-if="total > PAGE_SIZE"
      class="flex items-center justify-between mt-3 px-1 text-xs text-subtext"
    >
      <span>Página {{ currentPageNum }} de {{ totalPages }}</span>
      <div class="flex gap-2">
        <button
          type="button"
          data-testid="page-prev"
          :disabled="currentOffset === 0 || store.loading"
          class="px-3 py-1 rounded border border-surface-1 bg-base text-text hover:bg-mantle disabled:opacity-40 disabled:cursor-not-allowed"
          @click="goPrev"
        >
          ‹ Anterior
        </button>
        <button
          type="button"
          data-testid="page-next"
          :disabled="currentOffset + PAGE_SIZE >= total || store.loading"
          class="px-3 py-1 rounded border border-surface-1 bg-base text-text hover:bg-mantle disabled:opacity-40 disabled:cursor-not-allowed"
          @click="goNext"
        >
          Siguiente ›
        </button>
      </div>
    </div>
  </div>
</template>
