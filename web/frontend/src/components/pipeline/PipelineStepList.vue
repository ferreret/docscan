<script setup lang="ts">
import { VueDraggable } from 'vue-draggable-plus'
import { computed } from 'vue'
import PipelineStepRow from './PipelineStepRow.vue'
import type { PipelineStep } from '@/api/types-pipeline'

const props = defineProps<{ modelValue: PipelineStep[] }>()
const emit = defineEmits<{
  'update:modelValue': [steps: PipelineStep[]]
  'edit-step': [step: PipelineStep]
  'remove-step': [step: PipelineStep]
}>()

const list = computed({
  get: () => props.modelValue,
  set: (v: PipelineStep[]) => emit('update:modelValue', v),
})
</script>

<template>
  <div v-if="list.length === 0" class="text-center py-12 text-subtext">
    <p class="text-sm">Todavía no hay ningún step en el pipeline.</p>
    <p class="text-xs mt-1">
      Pulsa «+ Añadir step» para empezar.
    </p>
  </div>

  <VueDraggable
    v-else
    v-model="list"
    handle=".cursor-grab"
    :animation="150"
    class="flex flex-col gap-1.5"
  >
    <PipelineStepRow
      v-for="(step, idx) in list"
      :key="step.id"
      :step="step"
      :index="idx"
      @edit="emit('edit-step', step)"
      @remove="emit('remove-step', step)"
    />
  </VueDraggable>
</template>
