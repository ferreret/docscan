<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import type { PipelineStep, BarcodeStep, ImageOpStep, OcrStep } from '@/api/types-pipeline'
import BarcodeStepForm from './forms/BarcodeStepForm.vue'
import ImageOpStepForm from './forms/ImageOpStepForm.vue'
import OcrStepForm from './forms/OcrStepForm.vue'

const props = defineProps<{
  open: boolean
  step: PipelineStep | null
  isNew: boolean
}>()

const emit = defineEmits<{
  save: [step: PipelineStep]
  cancel: []
}>()

const draft = ref<PipelineStep | null>(null)
const dirty = ref(false)
const valid = ref(true)

watch(
  () => [props.open, props.step],
  () => {
    draft.value = props.step ? { ...props.step } : null
    dirty.value = false
    valid.value = true
  },
  { immediate: true },
)

function onDraftUpdate(next: PipelineStep) {
  draft.value = next
  dirty.value = true
}

function onCancel() {
  if (dirty.value && !confirm('¿Descartar cambios?')) return
  emit('cancel')
}

function onSave() {
  if (!draft.value || !valid.value) return
  emit('save', draft.value)
}

const isEditable = computed(
  () =>
    props.step?.type === 'barcode' ||
    props.step?.type === 'image_op' ||
    props.step?.type === 'ocr',
)

const canSave = computed(() => {
  if (!draft.value) return false
  if (!valid.value) return false
  if (draft.value.type === 'image_op') {
    return (draft.value as ImageOpStep).op !== ''
  }
  return true
})
</script>

<template>
  <div v-if="open" class="fixed inset-0 z-40">
    <!-- Backdrop -->
    <div class="absolute inset-0 bg-black/30" @click="onCancel"></div>

    <!-- Drawer -->
    <div
      class="absolute top-0 right-0 bottom-0 w-full max-w-lg bg-white shadow-2xl flex flex-col"
    >
      <div class="p-4 border-b border-surface-0 flex items-center justify-between">
        <h2 class="text-lg font-semibold text-text">
          {{ isNew ? 'Añadir step' : 'Editar step' }}
          <span v-if="step" class="text-xs text-subtext ml-2">{{ step.type }}</span>
        </h2>
        <button @click="onCancel" class="text-subtext hover:text-text text-xl">×</button>
      </div>

      <div class="flex-1 overflow-y-auto p-4">
        <BarcodeStepForm
          v-if="draft?.type === 'barcode'"
          :model-value="draft as BarcodeStep"
          @update:model-value="onDraftUpdate"
          @validity-change="(v) => (valid = v)"
        />
        <ImageOpStepForm
          v-else-if="draft?.type === 'image_op'"
          :model-value="draft as ImageOpStep"
          @update:model-value="onDraftUpdate"
        />
        <OcrStepForm
          v-else-if="draft?.type === 'ocr'"
          :model-value="draft as OcrStep"
          @update:model-value="onDraftUpdate"
        />
        <div v-else class="text-sm text-subtext bg-amber-50 border border-amber-200 rounded p-3">
          Este tipo de step (<code>{{ step?.type }}</code>) se edita desde el
          configurador de escritorio. Próximamente disponible aquí.
        </div>
      </div>

      <div class="p-4 border-t border-surface-0 flex justify-end gap-2">
        <button
          @click="onCancel"
          class="px-4 py-2 text-[13px] text-text hover:bg-surface-0 rounded-md transition-colors"
        >
          Cancelar
        </button>
        <button
          v-if="isEditable"
          @click="onSave"
          :disabled="!canSave"
          class="px-4 py-2 text-[13px] bg-primary text-white rounded-md font-semibold hover:bg-primary-hover transition-colors disabled:opacity-50"
        >
          Guardar step
        </button>
      </div>
    </div>
  </div>
</template>
