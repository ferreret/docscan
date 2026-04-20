import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import EnumField from '@/components/pipeline/fields/EnumField.vue'

const OPTIONS = [
  { value: 90, label: '90°' },
  { value: 180, label: '180°' },
  { value: 270, label: '270°' },
]

describe('EnumField', () => {
  it('emite update:modelValue con el value del option elegido', async () => {
    const wrapper = mount(EnumField, {
      props: { modelValue: 90, label: 'Grados', options: OPTIONS },
    })
    await wrapper.find('select').setValue('180')
    const events = wrapper.emitted('update:modelValue')
    expect(events![events!.length - 1]).toEqual([180])
  })

  it('conserva el tipo string para valores string', async () => {
    const wrapper = mount(EnumField, {
      props: {
        modelValue: 'HV',
        label: 'Dirección',
        options: [
          { value: 'H', label: 'Horizontal' },
          { value: 'V', label: 'Vertical' },
          { value: 'HV', label: 'Ambas' },
        ],
      },
    })
    await wrapper.find('select').setValue('V')
    const events = wrapper.emitted('update:modelValue')
    expect(events![events!.length - 1]).toEqual(['V'])
  })

  it('renderiza todas las opciones con su label', () => {
    const wrapper = mount(EnumField, {
      props: { modelValue: 90, label: 'Grados', options: OPTIONS },
    })
    expect(wrapper.findAll('option')).toHaveLength(3)
    expect(wrapper.text()).toContain('90°')
    expect(wrapper.text()).toContain('180°')
    expect(wrapper.text()).toContain('270°')
  })
})
