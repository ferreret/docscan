<script setup lang="ts">
import { onMounted, onBeforeUnmount } from 'vue'

const props = defineProps<{
  visible: boolean
  x: number
  y: number
  pageId: number
  isExcluded: boolean
  needsReview: boolean
  readOnly: boolean
  isLastPage: boolean
}>()

const emit = defineEmits<{
  (e: 'action', type: 'toggle-excluded' | 'toggle-review' | 'delete-page' | 'delete-after', pageId: number): void
  (e: 'close'): void
}>()

const handleKeydown = (ev: KeyboardEvent) => {
  if (ev.key === 'Escape' && props.visible) emit('close')
}

const handleMouseDown = (ev: MouseEvent) => {
  if (!props.visible) return
  const target = ev.target as HTMLElement | null
  if (!target || !target.closest('[data-thumb-ctx]')) emit('close')
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
  document.addEventListener('mousedown', handleMouseDown)
})
onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleKeydown)
  document.removeEventListener('mousedown', handleMouseDown)
})

const trigger = (type: 'toggle-excluded' | 'toggle-review' | 'delete-page' | 'delete-after') => {
  if (props.readOnly) return
  emit('action', type, props.pageId)
  emit('close')
}
</script>

<template>
  <div
    v-if="visible"
    data-thumb-ctx
    role="menu"
    :style="{
      position: 'fixed',
      left: x + 'px',
      top: y + 'px',
      zIndex: 1000,
    }"
    class="bg-mantle border border-surface-1 rounded shadow-lg py-1 min-w-[200px]"
  >
    <button
      data-testid="action-exclude"
      role="menuitem"
      type="button"
      :disabled="readOnly"
      class="w-full text-left px-3 py-1.5 text-sm hover:bg-crust disabled:opacity-50 disabled:cursor-not-allowed text-text"
      @click="trigger('toggle-excluded')"
    >
      {{ isExcluded ? '✓ Incluir' : '⊘ Marcar excluida' }}
    </button>
    <button
      data-testid="action-review"
      role="menuitem"
      type="button"
      :disabled="readOnly"
      class="w-full text-left px-3 py-1.5 text-sm hover:bg-crust disabled:opacity-50 disabled:cursor-not-allowed text-text"
      @click="trigger('toggle-review')"
    >
      {{ needsReview ? '✓ Quitar revisión' : '⚐ Marcar revisión' }}
    </button>
    <hr class="my-1 border-surface-0" />
    <button
      data-testid="action-delete"
      role="menuitem"
      type="button"
      :disabled="readOnly"
      class="w-full text-left px-3 py-1.5 text-sm hover:bg-crust disabled:opacity-50 disabled:cursor-not-allowed text-danger"
      @click="trigger('delete-page')"
    >
      🗑 Eliminar página
    </button>
    <button
      v-if="!isLastPage"
      data-testid="action-delete-after"
      role="menuitem"
      type="button"
      :disabled="readOnly"
      class="w-full text-left px-3 py-1.5 text-sm hover:bg-crust disabled:opacity-50 disabled:cursor-not-allowed text-danger"
      @click="trigger('delete-after')"
    >
      🗑 Eliminar desde aquí
    </button>
  </div>
</template>
