<script setup lang="ts">
import PageThumbnail from '@/components/workbench/PageThumbnail.vue'
import type { PageResponse } from '@/api/types'

const props = defineProps<{
  pages: PageResponse[]
  batchId: number
  selectedIndex: number
}>()

const emit = defineEmits<{
  (e: 'select', index: number): void
  (e: 'fit'): void
}>()
</script>

<template>
  <aside class="h-full overflow-y-auto bg-mantle border-r border-surface-0 p-2 space-y-2">
    <div v-if="pages.length === 0" class="text-center text-subtext text-xs py-6">
      Sin páginas
      <p class="text-overlay-0 mt-1">Usa «Subir ficheros» en la barra superior</p>
    </div>
    <PageThumbnail
      v-for="(page, idx) in pages"
      :key="page.id"
      :page="page"
      :batchId="batchId"
      :selected="idx === selectedIndex"
      @select="emit('select', idx)"
      @fit="emit('fit')"
    />
  </aside>
</template>
