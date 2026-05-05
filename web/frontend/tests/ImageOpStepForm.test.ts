import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ImageOpStepForm from '@/components/pipeline/forms/ImageOpStepForm.vue'
import type { ImageOpStep } from '@/api/types-pipeline'

function emptyStep(): ImageOpStep {
  return {
    id: 'test-1',
    type: 'image_op',
    enabled: true,
    op: '',
    params: {},
    window: null,
  }
}

describe('ImageOpStepForm', () => {
  it('con op vacío solo renderiza el selector y no los fields', () => {
    const wrapper = mount(ImageOpStepForm, {
      props: { modelValue: emptyStep() },
    })
    const selects = wrapper.findAll('select')
    // Solo el selector de operación, no hay fields dinámicos
    expect(selects.length).toBeGreaterThanOrEqual(1)
    // No hay WindowField tampoco cuando op === ''
    expect(wrapper.find('label[for="window_enabled"]').exists()).toBe(false)
  })

  it('al elegir una op, emite step con params por defecto del schema', async () => {
    const wrapper = mount(ImageOpStepForm, {
      props: { modelValue: emptyStep() },
    })
    // El primer select es el de operación
    await wrapper.find('select').setValue('ConvertTo1Bpp')
    const events = wrapper.emitted('update:modelValue')
    expect(events).toBeTruthy()
    const last = events![events!.length - 1][0] as ImageOpStep
    expect(last.op).toBe('ConvertTo1Bpp')
    expect(last.params).toEqual({ threshold: 128 })
  })

  it('op sin fields (FxGrayscale) no renderiza field dinámico', async () => {
    const step: ImageOpStep = {
      ...emptyStep(),
      op: 'FxGrayscale',
      params: {},
    }
    const wrapper = mount(ImageOpStepForm, { props: { modelValue: step } })
    // Solo hay 1 select: el selector de op (FxGrayscale no tiene enum field)
    const selects = wrapper.findAll('select')
    expect(selects).toHaveLength(1)
  })

  it('op con enum (Rotate degrees) renderiza select con 3 opciones', async () => {
    const step: ImageOpStep = {
      ...emptyStep(),
      op: 'Rotate',
      params: { degrees: 90 },
    }
    const wrapper = mount(ImageOpStepForm, { props: { modelValue: step } })
    const selects = wrapper.findAll('select')
    // [0]: selector de op, [1]: degrees
    expect(selects.length).toBeGreaterThanOrEqual(2)
    const degreesSelect = selects[1]
    expect(degreesSelect.findAll('option')).toHaveLength(3)
  })

  it('al cambiar de op, reemplaza params y conserva window', async () => {
    const step: ImageOpStep = {
      ...emptyStep(),
      op: 'ConvertTo1Bpp',
      params: { threshold: 200 },
      window: [10, 20, 100, 100],
    }
    const wrapper = mount(ImageOpStepForm, { props: { modelValue: step } })
    await wrapper.find('select').setValue('RotateAngle')
    const events = wrapper.emitted('update:modelValue')
    const last = events![events!.length - 1][0] as ImageOpStep
    expect(last.op).toBe('RotateAngle')
    expect(last.params).toEqual({ angle: 0 })
    expect(last.window).toEqual([10, 20, 100, 100])
  })

  it('Resize infiere modo scale y muestra solo el campo scale', () => {
    const step: ImageOpStep = {
      ...emptyStep(),
      op: 'Resize',
      params: { scale: 0.5 },
    }
    const wrapper = mount(ImageOpStepForm, { props: { modelValue: step } })
    const numberInputs = wrapper.findAll('input[type=number]')
    // [scale] + 4 de window si activado — aquí window es null, así que solo scale
    // El selector "modo" es un <select>, no input number.
    expect(numberInputs.length).toBe(1)
  })

  it('Resize al cambiar a modo size emite params con width y height', async () => {
    const step: ImageOpStep = {
      ...emptyStep(),
      op: 'Resize',
      params: { scale: 1.0 },
    }
    const wrapper = mount(ImageOpStepForm, { props: { modelValue: step } })
    // Buscar el select del modo (es el segundo select: op + modo)
    const selects = wrapper.findAll('select')
    const modeSelect = selects[1]
    await modeSelect.setValue('size')
    const events = wrapper.emitted('update:modelValue')
    const last = events![events!.length - 1][0] as ImageOpStep
    expect(last.params).toEqual({ width: 800, height: 600 })
  })
})
