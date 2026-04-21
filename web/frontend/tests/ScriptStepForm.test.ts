import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ScriptStepForm from '@/components/pipeline/forms/ScriptStepForm.vue'
import type { ScriptStep } from '@/api/types-pipeline'
import { DEFAULT_SCRIPT_TEMPLATE } from '@/api/script-context-help'

// Mock del wrapper del editor para no montar CodeMirror real.
const insertAtCursorMock = vi.fn()
const destroyMock = vi.fn()
const onChangeRef: { value: ((doc: string) => void) | null } = { value: null }

vi.mock('@/components/pipeline/forms/script-editor/editor', () => ({
  createEditor: vi.fn(async (args: { onChange: (doc: string) => void }) => {
    onChangeRef.value = args.onChange
    return {
      insertAtCursor: insertAtCursorMock,
      destroy: destroyMock,
    }
  }),
  // Los tests 3-4 no necesitan estos pero se exportan igualmente.
  shouldPrefixNewline: vi.fn(() => false),
  buildContextSuggestions: vi.fn(() => []),
}))

function makeStep(overrides: Partial<ScriptStep> = {}): ScriptStep {
  return {
    id: 'step-1',
    type: 'script',
    enabled: true,
    label: '',
    entry_point: 'process',
    script: DEFAULT_SCRIPT_TEMPLATE,
    ...overrides,
  }
}

describe('ScriptStepForm — campos base', () => {
  beforeEach(() => {
    insertAtCursorMock.mockClear()
    destroyMock.mockClear()
    onChangeRef.value = null
    localStorage.clear()
  })

  it('renderiza Activo, Nombre y Función con los valores iniciales', () => {
    const step = makeStep({ label: 'mi-script', entry_point: 'process' })
    const wrapper = mount(ScriptStepForm, { props: { modelValue: step } })

    const enabled = wrapper.find('input[type="checkbox"]')
    expect((enabled.element as HTMLInputElement).checked).toBe(true)

    const label = wrapper.find('[data-test="field-label"]')
    expect((label.element as HTMLInputElement).value).toBe('mi-script')

    const entry = wrapper.find('[data-test="field-entry-point"]')
    expect((entry.element as HTMLInputElement).value).toBe('process')
  })

  it('cambio de label emite update:modelValue con el nuevo label', async () => {
    const step = makeStep()
    const wrapper = mount(ScriptStepForm, { props: { modelValue: step } })
    const label = wrapper.find('[data-test="field-label"]')
    await label.setValue('nuevo-nombre')
    const events = wrapper.emitted('update:modelValue')!
    const last = events[events.length - 1][0] as ScriptStep
    expect(last.label).toBe('nuevo-nombre')
  })

  it('cambio de entry_point emite con el nuevo valor', async () => {
    const step = makeStep()
    const wrapper = mount(ScriptStepForm, { props: { modelValue: step } })
    const entry = wrapper.find('[data-test="field-entry-point"]')
    await entry.setValue('run')
    const events = wrapper.emitted('update:modelValue')!
    const last = events[events.length - 1][0] as ScriptStep
    expect(last.entry_point).toBe('run')
  })

  it('entry_point vacío tras blur se restaura a "process"', async () => {
    const step = makeStep({ entry_point: 'run' })
    const wrapper = mount(ScriptStepForm, { props: { modelValue: step } })
    const entry = wrapper.find('[data-test="field-entry-point"]')
    await entry.setValue('')
    await entry.trigger('blur')
    const events = wrapper.emitted('update:modelValue')!
    const last = events[events.length - 1][0] as ScriptStep
    expect(last.entry_point).toBe('process')
  })

  it('toggle de enabled emite el booleano invertido', async () => {
    const step = makeStep({ enabled: true })
    const wrapper = mount(ScriptStepForm, { props: { modelValue: step } })
    const enabled = wrapper.find('input[type="checkbox"]')
    await enabled.setValue(false)
    const events = wrapper.emitted('update:modelValue')!
    const last = events[events.length - 1][0] as ScriptStep
    expect(last.enabled).toBe(false)
  })
})

describe('ScriptStepForm — editor CodeMirror', () => {
  beforeEach(() => {
    insertAtCursorMock.mockClear()
    destroyMock.mockClear()
    onChangeRef.value = null
    localStorage.clear()
  })

  it('monta el wrapper y emite update:modelValue cuando el editor cambia', async () => {
    const step = makeStep({ script: 'x = 1\n' })
    const wrapper = mount(ScriptStepForm, { props: { modelValue: step } })

    // Esperar a que onMounted haga el import dinámico y llame createEditor.
    await new Promise((r) => setTimeout(r, 0))
    await wrapper.vm.$nextTick()

    expect(onChangeRef.value).toBeTypeOf('function')
    onChangeRef.value!('y = 2\n')

    const events = wrapper.emitted('update:modelValue')!
    const last = events[events.length - 1][0] as ScriptStep
    expect(last.script).toBe('y = 2\n')
  })
})

describe('ScriptStepForm — snippets', () => {
  beforeEach(() => {
    insertAtCursorMock.mockClear()
    destroyMock.mockClear()
    onChangeRef.value = null
    localStorage.clear()
  })

  it('el dropdown lista los 4 snippets disponibles', async () => {
    const wrapper = mount(ScriptStepForm, { props: { modelValue: makeStep() } })
    await new Promise((r) => setTimeout(r, 0))
    await wrapper.vm.$nextTick()

    const button = wrapper.find('[data-test="snippets-button"]')
    await button.trigger('click')
    const items = wrapper.findAll('[data-test="snippet-item"]')
    expect(items).toHaveLength(4)
    const labels = items.map((it) => it.text())
    expect(labels.some((l) => l.includes('Asignar primer barcode'))).toBe(true)
  })

  it('elegir un snippet invoca insertAtCursor con su code', async () => {
    const wrapper = mount(ScriptStepForm, { props: { modelValue: makeStep() } })
    await new Promise((r) => setTimeout(r, 0))
    await wrapper.vm.$nextTick()

    await wrapper.find('[data-test="snippets-button"]').trigger('click')
    const items = wrapper.findAll('[data-test="snippet-item"]')
    await items[0].trigger('click')

    expect(insertAtCursorMock).toHaveBeenCalledTimes(1)
    const arg = insertAtCursorMock.mock.calls[0][0] as string
    expect(arg).toContain('page.barcodes')
    expect(arg).toContain('page.fields["documento"]')
  })
})

describe('ScriptStepForm — panel de ayuda', () => {
  beforeEach(() => {
    insertAtCursorMock.mockClear()
    destroyMock.mockClear()
    onChangeRef.value = null
    localStorage.clear()
    // Simular viewport md+ (≥768 px).
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1280 })
  })

  it('colapsar el panel persiste helpPanelOpen=false en localStorage', async () => {
    const wrapper = mount(ScriptStepForm, { props: { modelValue: makeStep() } })
    await new Promise((r) => setTimeout(r, 0))
    await wrapper.vm.$nextTick()

    // Por defecto en viewport ≥md el panel está abierto.
    expect(wrapper.find('[data-test="help-panel"]').exists()).toBe(true)

    await wrapper.find('[data-test="help-close"]').trigger('click')

    expect(wrapper.find('[data-test="help-panel"]').exists()).toBe(false)
    expect(localStorage.getItem('scriptEditor.helpPanelOpen')).toBe('false')

    // Re-montar y comprobar que persiste cerrado.
    wrapper.unmount()
    const wrapper2 = mount(ScriptStepForm, { props: { modelValue: makeStep() } })
    await new Promise((r) => setTimeout(r, 0))
    await wrapper2.vm.$nextTick()
    expect(wrapper2.find('[data-test="help-panel"]').exists()).toBe(false)
  })
})
