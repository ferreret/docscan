import { defineStore } from 'pinia'
import { ref } from 'vue'
import { pipelineApi } from '@/api/pipeline'
import type { PipelineStep, StepType, BarcodeStep } from '@/api/types-pipeline'

function defaultsFor(type: StepType): Partial<PipelineStep> {
  if (type === 'barcode') {
    const defaults: Omit<BarcodeStep, 'id'> = {
      type: 'barcode',
      enabled: true,
      engine: 'motor1',
      symbologies: [],
      regex: '',
      regex_include_symbology: false,
      orientations: ['horizontal', 'vertical'],
      quality_threshold: 0,
      window: null,
    }
    return defaults
  }
  // Otros tipos no son editables en v1; no se construyen nuevos.
  return { type, enabled: true }
}

export const usePipelineStore = defineStore('pipeline', () => {
  const steps = ref<PipelineStep[]>([])
  const loading = ref(false)
  const saving = ref(false)
  const error = ref<string | null>(null)

  async function fetch(appId: number): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const res = await pipelineApi.get(appId)
      steps.value = res.steps
    } catch (e) {
      error.value = (e as Error).message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function save(appId: number): Promise<void> {
    saving.value = true
    error.value = null
    try {
      const res = await pipelineApi.put(appId, steps.value)
      steps.value = res.steps
    } catch (e) {
      error.value = (e as Error).message
      throw e
    } finally {
      saving.value = false
    }
  }

  function addStep(
    type: StepType,
    overrides: Partial<PipelineStep> = {},
  ): PipelineStep {
    const base = defaultsFor(type)
    const step = {
      id: crypto.randomUUID(),
      ...base,
      ...overrides,
    } as PipelineStep
    steps.value = [...steps.value, step]
    return step
  }

  function updateStep(id: string, patch: Partial<PipelineStep>): void {
    const idx = steps.value.findIndex((s) => s.id === id)
    if (idx === -1) return
    steps.value = [
      ...steps.value.slice(0, idx),
      { ...steps.value[idx], ...patch } as PipelineStep,
      ...steps.value.slice(idx + 1),
    ]
  }

  function removeStep(id: string): void {
    steps.value = steps.value.filter((s) => s.id !== id)
  }

  function reorder(newOrder: PipelineStep[]): void {
    steps.value = newOrder
  }

  return {
    steps,
    loading,
    saving,
    error,
    fetch,
    save,
    addStep,
    updateStep,
    removeStep,
    reorder,
  }
})
