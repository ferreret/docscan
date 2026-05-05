import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import NumberField from '@/components/pipeline/fields/NumberField.vue'

describe('NumberField', () => {
  it('emite update:modelValue con el número al cambiar el input', async () => {
    const wrapper = mount(NumberField, {
      props: { modelValue: 5, label: 'Cantidad' },
    })
    await wrapper.find('input').setValue('12')
    const events = wrapper.emitted('update:modelValue')
    expect(events).toBeTruthy()
    expect(events![events!.length - 1]).toEqual([12])
  })

  it('clampa al máximo cuando se excede', async () => {
    const wrapper = mount(NumberField, {
      props: { modelValue: 50, label: 'X', max: 100 },
    })
    await wrapper.find('input').setValue('999')
    const events = wrapper.emitted('update:modelValue')
    expect(events![events!.length - 1]).toEqual([100])
  })

  it('clampa al mínimo cuando se baja de él', async () => {
    const wrapper = mount(NumberField, {
      props: { modelValue: 0, label: 'X', min: 0 },
    })
    await wrapper.find('input').setValue('-5')
    const events = wrapper.emitted('update:modelValue')
    expect(events![events!.length - 1]).toEqual([0])
  })

  it('convierte a entero cuando integer=true', async () => {
    const wrapper = mount(NumberField, {
      props: { modelValue: 0, label: 'X', integer: true },
    })
    await wrapper.find('input').setValue('3.7')
    const events = wrapper.emitted('update:modelValue')
    expect(events![events!.length - 1]).toEqual([3])
  })

  it('renderiza el label', () => {
    const wrapper = mount(NumberField, {
      props: { modelValue: 0, label: 'Brillo' },
    })
    expect(wrapper.text()).toContain('Brillo')
  })
})
