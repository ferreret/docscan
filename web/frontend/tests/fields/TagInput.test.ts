import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import TagInput from '@/components/pipeline/fields/TagInput.vue'

describe('TagInput', () => {
  it('añade un chip al pulsar Enter', async () => {
    const wrapper = mount(TagInput, {
      props: { modelValue: [], label: 'Idiomas' },
    })
    const input = wrapper.find('input')
    await input.setValue('es')
    await input.trigger('keydown', { key: 'Enter' })
    const events = wrapper.emitted('update:modelValue')
    expect(events![events!.length - 1]).toEqual([['es']])
  })

  it('añade un chip al escribir coma', async () => {
    const wrapper = mount(TagInput, {
      props: { modelValue: ['es'], label: 'Idiomas' },
    })
    const input = wrapper.find('input')
    await input.setValue('en,')
    // El componente detecta la coma en el valor y dispara el add
    const events = wrapper.emitted('update:modelValue')
    expect(events![events!.length - 1]).toEqual([['es', 'en']])
  })

  it('elimina un chip al pulsar su botón ✕', async () => {
    const wrapper = mount(TagInput, {
      props: { modelValue: ['es', 'en'], label: 'Idiomas' },
    })
    const removeButtons = wrapper.findAll('button[aria-label^="Eliminar"]')
    expect(removeButtons.length).toBe(2)
    await removeButtons[0].trigger('click')
    const events = wrapper.emitted('update:modelValue')
    expect(events![events!.length - 1]).toEqual([['en']])
  })

  it('ignora duplicados', async () => {
    const wrapper = mount(TagInput, {
      props: { modelValue: ['es'], label: 'Idiomas' },
    })
    const input = wrapper.find('input')
    await input.setValue('es')
    await input.trigger('keydown', { key: 'Enter' })
    const events = wrapper.emitted('update:modelValue')
    // No debe emitir porque es duplicado
    expect(events).toBeFalsy()
  })

  it('ignora texto vacío tras trim', async () => {
    const wrapper = mount(TagInput, {
      props: { modelValue: [], label: 'Idiomas' },
    })
    const input = wrapper.find('input')
    await input.setValue('   ')
    await input.trigger('keydown', { key: 'Enter' })
    const events = wrapper.emitted('update:modelValue')
    expect(events).toBeFalsy()
  })

  it('renderiza el label', () => {
    const wrapper = mount(TagInput, {
      props: { modelValue: [], label: 'Idiomas soportados' },
    })
    expect(wrapper.text()).toContain('Idiomas soportados')
  })
})
