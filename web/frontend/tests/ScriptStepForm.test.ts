import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ScriptStepForm from '@/components/pipeline/forms/ScriptStepForm.vue'
import type { ScriptStep } from '@/api/types-pipeline'
import { DEFAULT_SCRIPT_TEMPLATE, SNIPPETS } from '@/api/script-context-help'

let latestUpdateModelValue: ((doc: string) => void) | null = null

vi.mock('@/components/CodeEditor.vue', () => ({
  default: {
    name: 'CodeEditor',
    props: ['modelValue', 'contextVariables', 'snippets', 'minHeight', 'helpPanelStorageKey'],
    emits: ['update:modelValue'],
    setup(_props: unknown, ctx: { emit: (name: string, ...args: unknown[]) => void }) {
      latestUpdateModelValue = (doc: string) => ctx.emit('update:modelValue', doc)
      return {}
    },
    template: '<div data-test="stub-code-editor"></div>',
  },
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
    localStorage.clear()
    latestUpdateModelValue = null
  })

  it('renderiza Activo, Nombre y Función con los valores iniciales', () => {
    const step = makeStep({ label: 'mi-script', entry_point: 'process' })
    const wrapper = mount(ScriptStepForm, { props: { modelValue: step } })

    expect((wrapper.find('input[type="checkbox"]').element as HTMLInputElement).checked).toBe(true)
    expect((wrapper.find('[data-test="field-label"]').element as HTMLInputElement).value).toBe('mi-script')
    expect((wrapper.find('[data-test="field-entry-point"]').element as HTMLInputElement).value).toBe('process')
  })

  it('cambio de label emite update:modelValue con el nuevo label', async () => {
    const wrapper = mount(ScriptStepForm, { props: { modelValue: makeStep() } })
    await wrapper.find('[data-test="field-label"]').setValue('nuevo-nombre')
    const events = wrapper.emitted('update:modelValue')!
    expect((events[events.length - 1][0] as ScriptStep).label).toBe('nuevo-nombre')
  })

  it('cambio de entry_point emite con el nuevo valor', async () => {
    const wrapper = mount(ScriptStepForm, { props: { modelValue: makeStep() } })
    await wrapper.find('[data-test="field-entry-point"]').setValue('run')
    const events = wrapper.emitted('update:modelValue')!
    expect((events[events.length - 1][0] as ScriptStep).entry_point).toBe('run')
  })

  it('entry_point vacío tras blur se restaura a "process"', async () => {
    const wrapper = mount(ScriptStepForm, { props: { modelValue: makeStep({ entry_point: 'run' }) } })
    const entry = wrapper.find('[data-test="field-entry-point"]')
    await entry.setValue('')
    await entry.trigger('blur')
    const events = wrapper.emitted('update:modelValue')!
    expect((events[events.length - 1][0] as ScriptStep).entry_point).toBe('process')
  })

  it('toggle de enabled emite el booleano invertido', async () => {
    const wrapper = mount(ScriptStepForm, { props: { modelValue: makeStep({ enabled: true }) } })
    await wrapper.find('input[type="checkbox"]').setValue(false)
    const events = wrapper.emitted('update:modelValue')!
    expect((events[events.length - 1][0] as ScriptStep).enabled).toBe(false)
  })
})

describe('ScriptStepForm — integración CodeEditor', () => {
  beforeEach(() => {
    latestUpdateModelValue = null
  })

  it('cuando CodeEditor emite update:modelValue, se propaga con patch({script})', async () => {
    const wrapper = mount(ScriptStepForm, {
      props: { modelValue: makeStep({ script: 'x = 1\n' }) },
    })
    await wrapper.vm.$nextTick()
    expect(latestUpdateModelValue).toBeTypeOf('function')
    latestUpdateModelValue!('y = 2\n')
    const events = wrapper.emitted('update:modelValue')!
    expect((events[events.length - 1][0] as ScriptStep).script).toBe('y = 2\n')
  })

  it('pasa CONTEXT_VARIABLES y SNIPPETS al CodeEditor', async () => {
    const wrapper = mount(ScriptStepForm, { props: { modelValue: makeStep() } })
    await wrapper.vm.$nextTick()
    const codeEditor = wrapper.findComponent({ name: 'CodeEditor' })
    expect(codeEditor.exists()).toBe(true)
    expect(codeEditor.props('snippets')).toEqual(SNIPPETS)
    expect(codeEditor.props('helpPanelStorageKey')).toBe('scriptEditor.helpPanelOpen')
  })
})
