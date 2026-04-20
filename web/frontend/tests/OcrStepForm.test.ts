import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import OcrStepForm from '@/components/pipeline/forms/OcrStepForm.vue'
import type { OcrStep } from '@/api/types-pipeline'

function defaultStep(): OcrStep {
  return {
    id: 'test-1',
    type: 'ocr',
    enabled: true,
    engine: 'rapidocr',
    languages: ['es'],
    full_page: true,
    window: null,
  }
}

describe('OcrStepForm', () => {
  it('renderiza el selector de motor con 3 opciones', () => {
    const wrapper = mount(OcrStepForm, {
      props: { modelValue: defaultStep() },
    })
    const selects = wrapper.findAll('select')
    // Primer (y único) select es el engine
    expect(selects.length).toBeGreaterThanOrEqual(1)
    const engineSelect = selects[0]
    expect(engineSelect.findAll('option')).toHaveLength(3)
  })

  it('al cambiar el motor emite el step con nuevo engine', async () => {
    const wrapper = mount(OcrStepForm, {
      props: { modelValue: defaultStep() },
    })
    await wrapper.find('select').setValue('tesseract')
    const events = wrapper.emitted('update:modelValue')
    const last = events![events!.length - 1][0] as OcrStep
    expect(last.engine).toBe('tesseract')
  })

  it('al añadir un idioma emite el step con lista actualizada', async () => {
    const wrapper = mount(OcrStepForm, {
      props: { modelValue: defaultStep() },
    })
    const input = wrapper.find('input[type=text]')
    await input.setValue('en')
    await input.trigger('keydown', { key: 'Enter' })
    const events = wrapper.emitted('update:modelValue')
    const last = events![events!.length - 1][0] as OcrStep
    expect(last.languages).toEqual(['es', 'en'])
  })

  it('toggle full_page invierte el booleano emitido', async () => {
    const wrapper = mount(OcrStepForm, {
      props: { modelValue: defaultStep() },
    })
    const checkboxes = wrapper.findAll('input[type=checkbox]')
    // [0]: activo, [1]: página completa (ambos true por default)
    await checkboxes[1].setValue(false)
    const events = wrapper.emitted('update:modelValue')
    const last = events![events!.length - 1][0] as OcrStep
    expect(last.full_page).toBe(false)
  })
})
