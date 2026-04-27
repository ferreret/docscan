<script setup lang="ts">
import { computed } from 'vue'
import AuthImage from '@/components/AuthImage.vue'
import { determinePageState, PAGE_STATE_BORDER_CLASS } from '@/composables/usePageState'
import { useBatchesStore } from '@/stores/batches'
import type { PageResponse } from '@/api/types'

const props = withDefaults(defineProps<{
  page: PageResponse
  batchId: number
  selected: boolean
  cacheTick?: number
  displayIndex?: number
}>(), { cacheTick: 0, displayIndex: 0 })

// Número visual del thumbnail: posición en la lista (1-indexed). Se prefiere
// sobre `page.page_index` porque éste no se reindexa al borrar páginas
// intermedias y dejaría huecos en la numeración.
const displayNumber = computed(() => props.displayIndex + 1)

const emit = defineEmits<{
  (e: 'select'): void
  (e: 'fit'): void
}>()

const store = useBatchesStore()

const borderClass = computed(() => PAGE_STATE_BORDER_CLASS[determinePageState(props.page)])
const imageUrl = computed(() => {
  const base = store.pageImageUrl(props.batchId, props.page.id)
  return props.cacheTick > 0 ? `${base}?v=${props.cacheTick}` : base
})
</script>

<template>
  <button
    type="button"
    :data-test="`page-thumbnail-${displayIndex}`"
    :aria-label="`Página ${displayNumber}`"
    :aria-pressed="selected"
    class="relative w-full text-left rounded overflow-hidden border-4 transition-colors"
    :class="[
      borderClass,
      selected ? 'ring-2 ring-primary ring-offset-2 ring-offset-base' : '',
    ]"
    @click="emit('select')"
    @dblclick="emit('fit')"
  >
    <AuthImage
      :src="imageUrl"
      :alt="`Página ${displayNumber}`"
      class="w-full aspect-[3/4] object-cover bg-crust"
    />
    <!-- Badges de estado (sobre la imagen, esquina inferior izquierda) -->
    <div class="absolute bottom-7 left-1 flex gap-0.5 pointer-events-none">
      <span
        v-if="page.is_excluded"
        data-testid="badge-excluded"
        class="bg-danger/90 text-base rounded px-1 text-xs leading-tight font-bold"
        title="Excluida"
      >⊘</span>
      <span
        v-if="page.needs_review"
        data-testid="badge-review"
        class="bg-warning/90 text-base rounded px-1 text-xs leading-tight font-bold"
        title="Revisión manual"
      >⚐</span>
    </div>
    <div class="absolute bottom-0 left-0 right-0 bg-crust/90 text-text text-[11px] px-2 py-1 flex justify-between items-center">
      <span class="font-semibold">#{{ displayNumber }}</span>
      <div class="flex gap-1">
        <span v-if="page.needs_review" class="text-warning" title="Requiere revisión">!</span>
        <span v-if="page.pipeline_processed" class="text-success" title="Procesada">✓</span>
        <span v-if="page.is_excluded" class="text-danger" title="Excluida">×</span>
      </div>
    </div>
  </button>
</template>
