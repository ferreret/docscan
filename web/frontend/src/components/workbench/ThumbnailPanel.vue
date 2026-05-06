<script setup lang="ts">
import { ref, watch } from 'vue'
import { VueDraggable } from 'vue-draggable-plus'
import PageThumbnail from '@/components/workbench/PageThumbnail.vue'
import type { PageResponse } from '@/api/types'

const props = withDefaults(
  defineProps<{
    pages: PageResponse[]
    batchId: number
    currentIndex: number
    readOnly?: boolean
    cacheTick?: number
  }>(),
  { readOnly: false, cacheTick: 0 },
)

const emit = defineEmits<{
  (e: 'select', index: number): void
  (e: 'fit'): void
  (e: 'reorder', newOrder: number[]): void
  (e: 'contextmenu', pageId: number, x: number, y: number): void
}>()

// Lista local mutable para que VueDraggable la reordene vía v-model.
const list = ref<PageResponse[]>([...props.pages])

watch(
  () => props.pages,
  (v) => {
    list.value = [...v]
  },
  { deep: true },
)

const onDragEnd = () => {
  if (props.readOnly) return
  // Comprobar si realmente cambió el orden comparando con props.pages.
  const current = list.value.map((p) => p.id)
  const original = props.pages.map((p) => p.id)
  const sameOrder =
    current.length === original.length && current.every((id, i) => id === original[i])
  if (sameOrder) return
  emit('reorder', current)
}

const onContextMenu = (ev: MouseEvent, page: PageResponse) => {
  ev.preventDefault()
  emit('contextmenu', page.id, ev.clientX, ev.clientY)
}

// Exponer para que los tests puedan simular drag-end mutando la lista.
defineExpose({ list, onDragEnd })
</script>

<template>
  <aside class="h-full overflow-y-auto bg-mantle border-r border-surface-0 p-2">
    <div v-if="list.length === 0" class="text-center text-subtext text-xs py-6">
      Sin páginas
      <p class="text-overlay-0 mt-1">Usa «Subir ficheros» en la barra superior</p>
    </div>
    <template v-else>
      <p class="text-[10px] text-overlay-0 px-1 pb-2 leading-snug">
        Botón derecho en una página para más opciones (excluir, marcar revisión, eliminar...).
      </p>
      <VueDraggable
        v-model="list"
        :disabled="readOnly"
        :animation="150"
        handle=".thumb-handle"
        ghost-class="opacity-40"
        class="space-y-2"
        :on-end="onDragEnd"
      >
        <div
          v-for="(page, idx) in list"
          :key="page.id"
          :data-testid="`thumb-${idx}`"
          class="thumb-handle cursor-context-menu"
          title="Botón derecho para más opciones"
          @contextmenu="onContextMenu($event, page)"
          @click="emit('select', idx)"
        >
          <PageThumbnail
            :page="page"
            :batchId="batchId"
            :selected="idx === currentIndex"
            :cacheTick="cacheTick"
            :displayIndex="idx"
            @select="emit('select', idx)"
            @fit="emit('fit')"
          />
        </div>
      </VueDraggable>
    </template>
  </aside>
</template>
