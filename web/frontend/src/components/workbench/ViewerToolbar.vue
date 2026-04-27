<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'

const props = withDefaults(
  defineProps<{
    zoomPercent: number
    canRotate?: boolean
    canDelete?: boolean
    currentPageNumber?: number
    totalPages?: number
    canPrev?: boolean
    canNext?: boolean
  }>(),
  {
    canRotate: true,
    canDelete: true,
    currentPageNumber: 0,
    totalPages: 0,
    canPrev: false,
    canNext: false,
  },
)

const emit = defineEmits<{
  (e: 'zoom-in'): void
  (e: 'zoom-out'): void
  (e: 'reset'): void
  (e: 'fit'): void
  (e: 'fit-width'): void
  (e: 'rotate', turns: number): void
  (e: 'delete-page'): void
  (e: 'nav-first'): void
  (e: 'nav-prev'): void
  (e: 'nav-next'): void
  (e: 'nav-last'): void
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
  <div
    class="absolute bottom-4 left-1/2 -translate-x-1/2 z-10 inline-flex items-center bg-mantle/95 backdrop-blur-sm border border-surface-1 rounded-full shadow-lg overflow-hidden"
    role="toolbar"
    aria-label="Herramientas del visor"
  >
    <!-- Navegación: primera, anterior -->
    <button
      type="button"
      data-test="vt-nav-first"
      :disabled="!canPrev"
      title="Primera página"
      aria-label="Primera página"
      class="px-3 py-2 text-text hover:bg-crust transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
      @click="emit('nav-first')"
    >⏮</button>
    <button
      type="button"
      data-test="vt-nav-prev"
      :disabled="!canPrev"
      title="Página anterior (←)"
      aria-label="Página anterior"
      class="px-3 py-2 text-text hover:bg-crust transition-colors disabled:opacity-30 disabled:cursor-not-allowed border-l border-surface-1"
      @click="emit('nav-prev')"
    >◀</button>

    <!-- Indicador de página -->
    <span
      class="px-3 py-2 text-xs text-subtext border-l border-surface-1 min-w-[4.5rem] text-center font-mono tabular-nums"
      data-test="vt-page-indicator"
    >
      {{ currentPageNumber || '–' }} / {{ totalPages || '–' }}
    </span>

    <!-- Navegación: siguiente, última -->
    <button
      type="button"
      data-test="vt-nav-next"
      :disabled="!canNext"
      title="Página siguiente (→)"
      aria-label="Página siguiente"
      class="px-3 py-2 text-text hover:bg-crust transition-colors disabled:opacity-30 disabled:cursor-not-allowed border-l border-surface-1"
      @click="emit('nav-next')"
    >▶</button>
    <button
      type="button"
      data-test="vt-nav-last"
      :disabled="!canNext"
      title="Última página"
      aria-label="Última página"
      class="px-3 py-2 text-text hover:bg-crust transition-colors disabled:opacity-30 disabled:cursor-not-allowed border-l border-surface-1"
      @click="emit('nav-last')"
    >⏭</button>

    <!-- Separador visual entre navegación y zoom -->
    <span class="w-px h-6 bg-surface-1 mx-1" aria-hidden="true"></span>

    <!-- Zoom -->
    <button
      type="button"
      data-test="vt-zoom-out"
      title="Alejar"
      aria-label="Alejar"
      class="px-3 py-2 text-text hover:bg-crust transition-colors"
      @click="emit('zoom-out')"
    >−</button>
    <button
      type="button"
      data-test="vt-zoom-in"
      title="Acercar"
      aria-label="Acercar"
      class="px-3 py-2 text-text hover:bg-crust transition-colors border-l border-surface-1"
      @click="emit('zoom-in')"
    >+</button>
    <span
      class="px-3 py-2 text-xs text-subtext border-l border-surface-1 min-w-[3.5rem] text-center font-mono tabular-nums"
      data-test="vt-percent"
    >
      {{ zoomPercent }}%
    </span>
    <button
      type="button"
      data-test="vt-reset"
      title="Tamaño 100%"
      aria-label="Tamaño 100%"
      class="px-3 py-2 text-text hover:bg-crust transition-colors border-l border-surface-1 text-xs"
      @click="emit('reset')"
    >1:1</button>
    <button
      type="button"
      data-test="vt-fit"
      title="Ajustar a la página"
      aria-label="Ajustar a la página"
      class="px-3 py-2 text-text hover:bg-crust transition-colors border-l border-surface-1"
      @click="emit('fit')"
    >⛶</button>
    <button
      type="button"
      data-test="vt-fit-width"
      title="Ajustar al ancho"
      aria-label="Ajustar al ancho"
      class="px-3 py-2 text-text hover:bg-crust transition-colors border-l border-surface-1 text-xs"
      @click="emit('fit-width')"
    >↔</button>

    <span class="w-px h-6 bg-surface-1 mx-1" aria-hidden="true"></span>

    <!-- Rotate dropdown -->
    <div data-rotate-dropdown class="relative">
      <button
        type="button"
        data-testid="btn-rotate"
        :disabled="!canRotate"
        :title="canRotate ? 'Rotar página' : 'Rotación deshabilitada'"
        aria-label="Rotar página"
        class="px-3 py-2 text-text hover:bg-crust transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        @click="toggleRotate"
      >↻</button>
      <div
        v-if="rotateOpen"
        class="absolute bottom-full right-0 mb-1 bg-mantle border border-surface-1 rounded shadow-lg py-1 min-w-[140px] z-20"
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

    <!-- Eliminar página actual -->
    <button
      type="button"
      data-test="vt-delete-page"
      :disabled="!canDelete"
      title="Eliminar esta página (Supr)"
      aria-label="Eliminar esta página"
      class="px-3 py-2 text-danger hover:bg-danger/10 transition-colors border-l border-surface-1 disabled:opacity-30 disabled:cursor-not-allowed"
      @click="emit('delete-page')"
    >🗑</button>
  </div>
</template>
