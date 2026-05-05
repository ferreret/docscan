import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BooleanField from '@/components/pipeline/fields/BooleanField.vue'

describe('BooleanField', () => {
  it('emite true cuando se marca', async () => {
    const wrapper = mount(BooleanField, {
      props: { modelValue: false, label: 'Activo' },
    })
    await wrapper.find('input[type=checkbox]').setValue(true)
    const events = wrapper.emitted('update:modelValue')
    expect(events![events!.length - 1]).toEqual([true])
  })

  it('emite false cuando se desmarca', async () => {
    const wrapper = mount(BooleanField, {
      props: { modelValue: true, label: 'Activo' },
    })
    await wrapper.find('input[type=checkbox]').setValue(false)
    const events = wrapper.emitted('update:modelValue')
    expect(events![events!.length - 1]).toEqual([false])
  })

  it('renderiza el label', () => {
    const wrapper = mount(BooleanField, {
      props: { modelValue: false, label: 'Deskew automático' },
    })
    expect(wrapper.text()).toContain('Deskew automático')
  })
})
