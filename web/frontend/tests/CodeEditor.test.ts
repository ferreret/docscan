import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import CodeEditor from '@/components/CodeEditor.vue'
import type { ContextVariable, Snippet } from '@/api/script-context-help'

const insertAtCursorMock = vi.fn()
const destroyMock = vi.fn()
const onChangeRef: { value: ((doc: string) => void) | null } = { value: null }
const createEditorMock = vi.fn()

vi.mock('@/components/code-editor/editor', () => ({
  createEditor: vi.fn(async (args: { onChange: (doc: string) => void }) => {
    onChangeRef.value = args.onChange
    createEditorMock(args)
    return {
      insertAtCursor: insertAtCursorMock,
      destroy: destroyMock,
    }
  }),
  shouldPrefixNewline: vi.fn(() => false),
  buildContextSuggestions: vi.fn(() => []),
}))

const SAMPLE_VARS: ContextVariable[] = [
  { name: 'app', summary: 'AppContext.' },
]

const SAMPLE_SNIPPETS: Snippet[] = [
  { id: 's1', label: 'Hola mundo', description: 'Ejemplo', code: 'log.info("hola")\n' },
  { id: 's2', label: 'Otro', description: 'Otro', code: 'pass\n' },
]

describe('CodeEditor', () => {
  beforeEach(() => {
    insertAtCursorMock.mockClear()
    destroyMock.mockClear()
    createEditorMock.mockClear()
    onChangeRef.value = null
    localStorage.clear()
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1280 })
  })

  it('sin snippets oculta el botón Insertar snippet', async () => {
    const wrapper = mount(CodeEditor, {
      props: { modelValue: 'x=1', contextVariables: SAMPLE_VARS },
    })
    await new Promise((r) => setTimeout(r, 0))
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-test="snippets-button"]').exists()).toBe(false)
  })

  it('cuando el editor dispara onChange, emite update:modelValue', async () => {
    const wrapper = mount(CodeEditor, {
      props: { modelValue: 'x=1', contextVariables: SAMPLE_VARS },
    })
    await new Promise((r) => setTimeout(r, 0))
    await wrapper.vm.$nextTick()

    expect(onChangeRef.value).toBeTypeOf('function')
    onChangeRef.value!('y=2')

    const events = wrapper.emitted('update:modelValue')!
    expect(events[events.length - 1][0]).toBe('y=2')
  })

  it('cambios posteriores a modelValue NO se propagan al editor', async () => {
    const wrapper = mount(CodeEditor, {
      props: { modelValue: 'x=1', contextVariables: SAMPLE_VARS },
    })
    await new Promise((r) => setTimeout(r, 0))
    await wrapper.vm.$nextTick()

    // Cambio externo de modelValue no debe llamar a createEditor una segunda vez
    await wrapper.setProps({ modelValue: 'y=2', contextVariables: SAMPLE_VARS })
    await wrapper.vm.$nextTick()
    expect(createEditorMock).toHaveBeenCalledTimes(1)
  })

  it('elegir un snippet llama a insertAtCursor con su code', async () => {
    const wrapper = mount(CodeEditor, {
      props: { modelValue: '', contextVariables: SAMPLE_VARS, snippets: SAMPLE_SNIPPETS },
    })
    await new Promise((r) => setTimeout(r, 0))
    await wrapper.vm.$nextTick()

    await wrapper.find('[data-test="snippets-button"]').trigger('click')
    const items = wrapper.findAll('[data-test="snippet-item"]')
    expect(items).toHaveLength(2)
    await items[0].trigger('click')

    expect(insertAtCursorMock).toHaveBeenCalledTimes(1)
    expect(insertAtCursorMock.mock.calls[0][0]).toBe('log.info("hola")\n')
  })

  it('colapsar el panel persiste en localStorage bajo la clave configurada', async () => {
    const wrapper = mount(CodeEditor, {
      props: {
        modelValue: '', contextVariables: SAMPLE_VARS,
        helpPanelStorageKey: 'customKey',
      },
    })
    await new Promise((r) => setTimeout(r, 0))
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[data-test="help-panel"]').exists()).toBe(true)
    await wrapper.find('[data-test="help-close"]').trigger('click')
    expect(wrapper.find('[data-test="help-panel"]').exists()).toBe(false)
    expect(localStorage.getItem('customKey')).toBe('false')
  })

  it('en unmount llama a destroy exactamente una vez', async () => {
    const wrapper = mount(CodeEditor, {
      props: { modelValue: 'x=1', contextVariables: SAMPLE_VARS },
    })
    await new Promise((r) => setTimeout(r, 0))
    await wrapper.vm.$nextTick()

    wrapper.unmount()
    await new Promise((r) => setTimeout(r, 0))
    expect(destroyMock).toHaveBeenCalledTimes(1)
  })
})
