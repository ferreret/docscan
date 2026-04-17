<script setup lang="ts">
import type { PipelineStep, BarcodeStep } from '@/api/types-pipeline'
import { computed } from 'vue'

const props = defineProps<{ step: PipelineStep; index: number }>()
defineEmits<{ edit: []; remove: [] }>()

const typeColors: Record<string, string> = {
  barcode: 'bg-sky-500',
  image_op: 'bg-emerald-500',
  ocr: 'bg-amber-500',
  script: 'bg-violet-500',
}

const summary = computed(() => {
  const s = props.step
  if (s.type === 'barcode') {
    const bc = s as BarcodeStep
    const region = bc.window ? 'región custom' : 'página completa'
    const symbols = bc.symbologies.length ? bc.symbologies.join(',') : 'todas'
    return `${bc.engine} · ${region} · ${symbols}`
  }
  return 'Editable desde configurador de escritorio'
})
</script>

<template>
  <div
    class="flex items-center gap-2 p-2 bg-white rounded-md border border-surface-0 hover:border-primary/40 transition-colors"
    :class="{ 'opacity-50': !step.enabled }"
  >
    <span class="cursor-grab text-subtext select-none" title="Reordenar">⋮⋮</span>
    <span
      class="text-white text-[11px] px-2 py-0.5 rounded font-medium"
      :class="typeColors[step.type] || 'bg-gray-500'"
    >
      {{ step.type }}
    </span>
    <span class="flex-1 text-sm text-text truncate">{{ summary }}</span>
    <button
      @click="$emit('edit')"
      class="text-subtext hover:text-primary text-sm"
      title="Editar"
    >
      ✎
    </button>
    <button
      @click="$emit('remove')"
      class="text-subtext hover:text-danger text-sm"
      title="Eliminar"
    >
      🗑
    </button>
  </div>
</template>
