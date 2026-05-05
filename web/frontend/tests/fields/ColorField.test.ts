import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ColorField from '@/components/pipeline/fields/ColorField.vue'

describe('ColorField', () => {
  it('emite [r, g, b] al cambiar un canal', async () => {
    const wrapper = mount(ColorField, {
      props: { modelValue: [10, 20, 30], label: 'Color' },
    })
    const inputs = wrapper.findAll('input[type=number]')
    await inputs[0].setValue('200')
    const events = wrapper.emitted('update:modelValue')
    expect(events![events!.length - 1]).toEqual([[200, 20, 30]])
  })

  it('clampa cada canal a 255', async () => {
    const wrapper = mount(ColorField, {
      props: { modelValue: [0, 0, 0], label: 'Color' },
    })
    const inputs = wrapper.findAll('input[type=number]')
    await inputs[2].setValue('999')
    const events = wrapper.emitted('update:modelValue')
    expect(events![events!.length - 1]).toEqual([[0, 0, 255]])
  })

  it('clampa cada canal a 0 si es negativo', async () => {
    const wrapper = mount(ColorField, {
      props: { modelValue: [100, 100, 100], label: 'Color' },
    })
    const inputs = wrapper.findAll('input[type=number]')
    await inputs[1].setValue('-50')
    const events = wrapper.emitted('update:modelValue')
    expect(events![events!.length - 1]).toEqual([[100, 0, 100]])
  })

  it('renderiza el label', () => {
    const wrapper = mount(ColorField, {
      props: { modelValue: [0, 0, 0], label: 'Color origen' },
    })
    expect(wrapper.text()).toContain('Color origen')
  })
})
