<script setup lang="ts">
defineProps<{ zoomPercent: number }>()

const emit = defineEmits<{
  (e: 'zoom-in'): void
  (e: 'zoom-out'): void
  (e: 'reset'): void
  (e: 'fit'): void
}>()
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
    <span class="px-2 py-1 text-xs text-subtext border-l border-surface-1 min-w-[3.5rem] text-right" data-test="vt-percent">
      {{ zoomPercent }}%
    </span>
  </div>
</template>
