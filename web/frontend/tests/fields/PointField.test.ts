import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import PointField from '@/components/pipeline/fields/PointField.vue'

describe('PointField', () => {
  it('emite {x, y} al cambiar X', async () => {
    const wrapper = mount(PointField, {
      props: { modelValue: { x: 10, y: 20 }, label: 'Origen' },
    })
    const inputs = wrapper.findAll('input[type=number]')
    await inputs[0].setValue('50')
    const events = wrapper.emitted('update:modelValue')
    expect(events![events!.length - 1]).toEqual([{ x: 50, y: 20 }])
  })

  it('emite {x, y} al cambiar Y', async () => {
    const wrapper = mount(PointField, {
      props: { modelValue: { x: 10, y: 20 }, label: 'Origen' },
    })
    const inputs = wrapper.findAll('input[type=number]')
    await inputs[1].setValue('99')
    const events = wrapper.emitted('update:modelValue')
    expect(events![events!.length - 1]).toEqual([{ x: 10, y: 99 }])
  })

  it('renderiza el label principal', () => {
    const wrapper = mount(PointField, {
      props: { modelValue: { x: 0, y: 0 }, label: 'Origen del relleno' },
    })
    expect(wrapper.text()).toContain('Origen del relleno')
  })
})
