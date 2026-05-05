<script setup lang="ts">
import type { PipelineStep, BarcodeStep, ImageOpStep, OcrStep, ScriptStep, StepType } from '@/api/types-pipeline'
import { IMAGE_OP_CATALOG } from '@/api/image-op-catalog'
import { computed } from 'vue'

const props = defineProps<{ step: PipelineStep; index: number }>()
defineEmits<{ edit: []; remove: [] }>()

const typeColors: Record<StepType, string> = {
  barcode: 'bg-sky-500',
  image_op: 'bg-emerald-500',
  ocr: 'bg-amber-500',
  script: 'bg-violet-500',
}

function formatParams(params: Record<string, unknown>): string {
  const keys = Object.keys(params)
  if (keys.length === 0) return ''
  const head = keys.slice(0, 2).map((k) => `${k}=${params[k]}`).join(', ')
  return keys.length > 2 ? `${head}…` : head
}

const summary = computed(() => {
  const s = props.step
  if (s.type === 'barcode') {
    const bc = s as BarcodeStep
    const region = bc.window ? 'región custom' : 'página completa'
    const symbols = bc.symbologies.length ? bc.symbologies.join(',') : 'todas'
    return `${bc.engine} · ${region} · ${symbols}`
  }
  if (s.type === 'image_op') {
    const io = s as ImageOpStep
    if (!io.op) return 'Operación de imagen (sin configurar)'
    const meta = IMAGE_OP_CATALOG.find((op) => op.name === io.op)
    const label = meta?.label ?? io.op
    const paramsTxt = formatParams(io.params)
    const windowTxt = io.window
      ? ` · región ${io.window.join(',')}`
      : ''
    return paramsTxt
      ? `${label} · ${paramsTxt}${windowTxt}`
      : `${label}${windowTxt}`
  }
  if (s.type === 'ocr') {
    const oc = s as OcrStep
    const langs = oc.languages.length ? oc.languages.join(',') : 'sin idiomas'
    const area = oc.full_page
      ? 'página completa'
      : oc.window
        ? `región ${oc.window.join(',')}`
        : 'sin región'
    return `OCR (${oc.engine}) · ${langs} · ${area}`
  }
  if (s.type === 'script') {
    const sc = s as ScriptStep
    const name = sc.label?.trim() || 'Script sin nombre'
    const entry = sc.entry_point?.trim() || 'process'
    const lines = (sc.script?.match(/\n/g)?.length ?? 0) + (sc.script ? 1 : 0)
    return `${name} · ${entry}() · ${lines} líneas`
  }
  return 'Editable desde configurador de escritorio'
})
</script>

<template>
  <div
    class="flex items-center gap-2 p-2 bg-base rounded-md border border-surface-0 hover:border-primary/40 transition-colors"
    :class="{ 'opacity-50': !step.enabled }"
  >
    <span class="cursor-grab text-subtext select-none" title="Reordenar">⋮⋮</span>
    <span
      class="text-white text-[11px] px-2 py-0.5 rounded font-medium"
      :class="typeColors[step.type] || 'bg-surface-2'"
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
