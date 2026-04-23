<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'

const props = withDefaults(
  defineProps<{
    zoomPercent: number
    canRotate?: boolean
    showBarcodes?: boolean
    showFields?: boolean
  }>(),
  {
    canRotate: true,
    showBarcodes: true,
    showFields: true,
  },
)

const emit = defineEmits<{
  (e: 'zoom-in'): void
  (e: 'zoom-out'): void
  (e: 'reset'): void
  (e: 'fit'): void
  (e: 'rotate', turns: number): void
  (e: 'toggle-barcodes'): void
  (e: 'toggle-fields'): void
}>()

const rotateOpen = ref(false)

const toggleRotate = () => {
  if (!props.canRotate) return
  rotateOpen.value = !rotateOpen.value
}

const onRotate = (turns: number) => {
  emit('rotate', turns)
  rotateOpen.value = false
}

const handleClickOutside = (ev: MouseEvent) => {
  const target = ev.target as HTMLElement | null
  if (!target) return
  if (!target.closest('[data-rotate-dropdown]')) {
    rotateOpen.value = false
  }
}

onMounted(() => document.addEventListener('mousedown', handleClickOutside))
onBeforeUnmount(() => document.removeEventListener('mousedown', handleClickOutside))
</script>

<template>
  <div class="absolute top-2 right-2 z-10 inline-flex items-center bg-mantle border border-surface-1 rounded shadow-sm">
    <button
      type="button"
      data-test="vt-zoom-in"
      title="Acercar"
      aria-label="Acercar"
      class="px-2 py-1 text-text hover:bg-crust transition-colors"
      @click="emit('zoom-in')"
    >+</button>
    <button
      type="button"
      data-test="vt-zoom-out"
      title="Alejar"
      aria-label="Alejar"
      class="px-2 py-1 text-text hover:bg-crust transition-colors border-l border-surface-1"
      @click="emit('zoom-out')"
    >−</button>
    <button
      type="button"
      data-test="vt-reset"
      title="Tamaño 100%"
      aria-label="Tamaño 100%"
      class="px-2 py-1 text-text hover:bg-crust transition-colors border-l border-surface-1 text-xs"
      @click="emit('reset')"
    >1:1</button>
    <button
      type="button"
      data-test="vt-fit"
      title="Ajustar a la vista"
      aria-label="Ajustar a la vista"
      class="px-2 py-1 text-text hover:bg-crust transition-colors border-l border-surface-1"
      @click="emit('fit')"
    >⛶</button>
    <span
      class="px-2 py-1 text-xs text-subtext border-l border-surface-1 min-w-[3.5rem] text-right"
      data-test="vt-percent"
    >
      {{ zoomPercent }}%
    </span>

    <!-- Rotate dropdown -->
    <div data-rotate-dropdown class="relative border-l border-surface-1">
      <button
        type="button"
        data-testid="btn-rotate"
        :disabled="!canRotate"
        :title="canRotate ? 'Rotar página' : 'Rotación deshabilitada'"
        aria-label="Rotar página"
        class="px-2 py-1 text-text hover:bg-crust transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        @click="toggleRotate"
      >↻</button>
      <div
        v-if="rotateOpen"
        class="absolute top-full right-0 mt-1 bg-mantle border border-surface-1 rounded shadow-lg py-1 min-w-[140px] z-20"
      >
        <button
          type="button"
          data-testid="rotate-90"
          class="w-full text-left px-3 py-1.5 text-sm text-text hover:bg-crust transition-colors"
          @click="onRotate(1)"
        >90° ↻</button>
        <button
          type="button"
          data-testid="rotate-180"
          class="w-full text-left px-3 py-1.5 text-sm text-text hover:bg-crust transition-colors"
          @click="onRotate(2)"
        >180° ↻</button>
        <button
          type="button"
          data-testid="rotate-270"
          class="w-full text-left px-3 py-1.5 text-sm text-text hover:bg-crust transition-colors"
          @click="onRotate(3)"
        >270° ↺</button>
      </div>
    </div>

    <!-- Overlay toggles -->
    <button
      type="button"
      data-testid="btn-toggle-barcodes"
      :aria-pressed="showBarcodes ? 'true' : 'false'"
      :title="showBarcodes ? 'Ocultar barcodes' : 'Mostrar barcodes'"
      aria-label="Alternar overlay de barcodes"
      class="px-2 py-1 text-xs border-l border-surface-1 transition-colors"
      :class="showBarcodes ? 'bg-blue text-base' : 'text-subtext hover:bg-crust'"
      @click="emit('toggle-barcodes')"
    >▮▮</button>
    <button
      type="button"
      data-testid="btn-toggle-fields"
      :aria-pressed="showFields ? 'true' : 'false'"
      :title="showFields ? 'Ocultar campos' : 'Mostrar campos'"
      aria-label="Alternar overlay de campos"
      class="px-2 py-1 text-xs border-l border-surface-1 transition-colors"
      :class="showFields ? 'bg-blue text-base' : 'text-subtext hover:bg-crust'"
      @click="emit('toggle-fields')"
    >ABC</button>
  </div>
</template>
