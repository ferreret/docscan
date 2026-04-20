<script setup lang="ts">
import type { OcrStep } from '@/api/types-pipeline'

import EnumField from '../fields/EnumField.vue'
import BooleanField from '../fields/BooleanField.vue'
import TagInput from '../fields/TagInput.vue'
import WindowField from '../WindowField.vue'

const props = defineProps<{ modelValue: OcrStep }>()
const emit = defineEmits<{ 'update:modelValue': [step: OcrStep] }>()

function patch(update: Partial<OcrStep>) {
  emit('update:modelValue', { ...props.modelValue, ...update })
}

const ENGINE_OPTIONS = [
  { value: 'rapidocr', label: 'rapidocr (rápido, offline)' },
  { value: 'easyocr', label: 'easyocr (alta precisión, PyTorch)' },
  { value: 'tesseract', label: 'tesseract (ligero, ISO 639-3)' },
]
</script>

<template>
  <div class="space-y-4">
    <!-- Activo -->
    <div class="flex items-center gap-2">
      <input
        id="ocr_enabled"
        type="checkbox"
        :checked="modelValue.enabled"
        @change="(e) => patch({ enabled: (e.target as HTMLInputElement).checked })"
      />
      <label for="ocr_enabled" class="text-sm">Activo</label>
    </div>

    <!-- Motor -->
    <EnumField
      label="Motor"
      :model-value="modelValue.engine"
      :options="ENGINE_OPTIONS"
      help="rapidocr/easyocr usan ISO 639-1 (es, en). tesseract usa ISO 639-3 (spa, eng)."
      @update:model-value="(v) => patch({ engine: v as OcrStep['engine'] })"
    />

    <!-- Idiomas -->
    <TagInput
      label="Idiomas"
      placeholder="es, en, fr"
      help="Los códigos varían según el motor."
      :model-value="modelValue.languages"
      @update:model-value="(v) => patch({ languages: v })"
    />

    <!-- Full page -->
    <BooleanField
      label="Procesar página completa"
      help="Si se desactiva, se usará la región indicada abajo."
      :model-value="modelValue.full_page"
      @update:model-value="(v) => patch({ full_page: v })"
    />

    <!-- Window (ROI) -->
    <WindowField
      :model-value="modelValue.window"
      @update:model-value="(v) => patch({ window: v })"
    />
  </div>
</template>
