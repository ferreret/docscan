import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { usePipelineStore } from '@/stores/pipeline'
import type { BarcodeStep } from '@/api/types-pipeline'

vi.mock('@/api/pipeline', () => ({
  pipelineApi: {
    get: vi.fn(),
    put: vi.fn(),
  },
}))

import { pipelineApi } from '@/api/pipeline'

const barcodeDefaults: BarcodeStep = {
  id: 'bc-1',
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

describe('usePipelineStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('fetch popula steps y resetea error', async () => {
    vi.mocked(pipelineApi.get).mockResolvedValue({ steps: [barcodeDefaults] })
    const store = usePipelineStore()

    await store.fetch(42)

    expect(store.steps).toHaveLength(1)
    expect(store.steps[0].id).toBe('bc-1')
    expect(store.error).toBeNull()
  })

  it('addStep añade al final con id generado', () => {
    const store = usePipelineStore()
    const step = store.addStep('barcode', { engine: 'motor2' })

    expect(store.steps).toHaveLength(1)
    expect(step.id).toBeTruthy()
    expect(step.type).toBe('barcode')
    expect((step as BarcodeStep).engine).toBe('motor2')
  })

  it('updateStep modifica por id', () => {
    const store = usePipelineStore()
    store.steps = [{ ...barcodeDefaults }]

    store.updateStep('bc-1', { enabled: false, regex: 'XYZ' })

    expect(store.steps[0].enabled).toBe(false)
    expect((store.steps[0] as BarcodeStep).regex).toBe('XYZ')
  })

  it('updateStep con id inexistente no hace nada', () => {
    const store = usePipelineStore()
    store.steps = [{ ...barcodeDefaults }]

    store.updateStep('no-existe', { enabled: false })

    expect(store.steps[0].enabled).toBe(true)
  })

  it('removeStep elimina por id', () => {
    const store = usePipelineStore()
    store.steps = [
      { ...barcodeDefaults, id: 'a' },
      { ...barcodeDefaults, id: 'b' },
    ]

    store.removeStep('a')

    expect(store.steps).toHaveLength(1)
    expect(store.steps[0].id).toBe('b')
  })

  it('reorder sustituye la lista', () => {
    const store = usePipelineStore()
    const a = { ...barcodeDefaults, id: 'a' }
    const b = { ...barcodeDefaults, id: 'b' }
    store.steps = [a, b]

    store.reorder([b, a])

    expect(store.steps[0].id).toBe('b')
    expect(store.steps[1].id).toBe('a')
  })

  it('save envía los steps actuales al endpoint', async () => {
    vi.mocked(pipelineApi.put).mockResolvedValue({ steps: [barcodeDefaults] })
    const store = usePipelineStore()
    store.steps = [{ ...barcodeDefaults }]

    await store.save(42)

    expect(pipelineApi.put).toHaveBeenCalledWith(42, [barcodeDefaults])
    expect(store.saving).toBe(false)
    expect(store.error).toBeNull()
  })

  it('save guarda error si falla', async () => {
    vi.mocked(pipelineApi.put).mockRejectedValue(
      new Error('Pipeline inválido: foo')
    )
    const store = usePipelineStore()
    store.steps = [{ ...barcodeDefaults }]

    await expect(store.save(42)).rejects.toThrow('Pipeline inválido')
    expect(store.error).toContain('Pipeline inválido')
    expect(store.saving).toBe(false)
  })

  it('addStep image_op devuelve un step con defaults correctos', () => {
    const store = usePipelineStore()
    const step = store.addStep('image_op')

    expect(step.type).toBe('image_op')
    expect(step.enabled).toBe(true)
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const s = step as any
    expect(s.op).toBe('')
    expect(s.params).toEqual({})
    expect(s.window).toBeNull()
    expect(step.id).toBeTruthy()
  })
})
