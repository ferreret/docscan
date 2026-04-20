<script setup lang="ts">
import { ref } from 'vue'
import type { StepType } from '@/api/types-pipeline'

const emit = defineEmits<{ select: [type: StepType] }>()
const open = ref(false)

function pick(type: StepType) {
  open.value = false
  emit('select', type)
}
</script>

<template>
  <div class="relative">
    <button
      @click="open = !open"
      class="bg-primary text-white rounded-md px-4 py-2 text-[13px] font-semibold hover:bg-primary-hover transition-colors shadow-sm"
    >
      + Añadir step
    </button>

    <div
      v-if="open"
      class="absolute right-0 mt-1 w-64 bg-white rounded-md border border-surface-0 shadow-lg py-1 z-10"
    >
      <button
        @click="pick('barcode')"
        class="w-full text-left px-3 py-2 text-sm hover:bg-surface-0 flex items-center gap-2"
      >
        <span class="w-2 h-2 rounded-full bg-sky-500"></span>
        <span>Barcode</span>
        <span class="ml-auto text-xs text-subtext">v1</span>
      </button>
      <button
        @click="pick('image_op')"
        class="w-full text-left px-3 py-2 text-sm hover:bg-surface-0 flex items-center gap-2"
      >
        <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
        <span>Operación de imagen</span>
        <span class="ml-auto text-xs text-subtext">v2</span>
      </button>
      <div class="border-t border-surface-0 my-1"></div>
      <div class="px-3 py-1.5 text-[11px] text-subtext uppercase tracking-wide">
        Próximamente
      </div>
      <div
        v-for="type in ['ocr', 'script']"
        :key="type"
        class="w-full text-left px-3 py-2 text-sm text-subtext flex items-center gap-2 cursor-not-allowed"
      >
        <span class="w-2 h-2 rounded-full bg-gray-300"></span>
        <span>{{ type }}</span>
      </div>
    </div>
  </div>
</template>
