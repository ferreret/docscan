import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import WindowField from '@/components/pipeline/WindowField.vue'

describe('WindowField', () => {
  it('con modelValue=null muestra solo el toggle', () => {
    const wrapper = mount(WindowField, { props: { modelValue: null } })
    expect(wrapper.find('input[type=checkbox]').exists()).toBe(true)
    expect(wrapper.findAll('input[type=number]')).toHaveLength(0)
  })

  it('al activar el toggle emite [0, 0, 100, 100]', async () => {
    const wrapper = mount(WindowField, { props: { modelValue: null } })
    await wrapper.find('input[type=checkbox]').setValue(true)
    const events = wrapper.emitted('update:modelValue')
    expect(events![events!.length - 1]).toEqual([[0, 0, 100, 100]])
  })

  it('al desactivar el toggle emite null', async () => {
    const wrapper = mount(WindowField, {
      props: { modelValue: [5, 10, 50, 50] },
    })
    await wrapper.find('input[type=checkbox]').setValue(false)
    const events = wrapper.emitted('update:modelValue')
    expect(events![events!.length - 1]).toEqual([null])
  })

  it('con modelValue no-null renderiza 4 inputs numéricos', () => {
    const wrapper = mount(WindowField, {
      props: { modelValue: [5, 10, 50, 50] },
    })
    expect(wrapper.findAll('input[type=number]')).toHaveLength(4)
  })

  it('emite tupla actualizada al cambiar un campo', async () => {
    const wrapper = mount(WindowField, {
      props: { modelValue: [5, 10, 50, 50] },
    })
    const inputs = wrapper.findAll('input[type=number]')
    await inputs[2].setValue('200')
    const events = wrapper.emitted('update:modelValue')
    expect(events![events!.length - 1]).toEqual([[5, 10, 200, 50]])
  })
})
