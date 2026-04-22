import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ViewerToolbar from '@/components/workbench/ViewerToolbar.vue'

describe('ViewerToolbar', () => {
  it('renders four buttons and a percent indicator', () => {
    const wrapper = mount(ViewerToolbar, { props: { zoomPercent: 100 } })
    const buttons = wrapper.findAll('button')
    expect(buttons).toHaveLength(4)
    expect(wrapper.text()).toContain('100%')
  })

  it('emits zoom-in on + button click', async () => {
    const wrapper = mount(ViewerToolbar, { props: { zoomPercent: 100 } })
    await wrapper.find('[data-test="vt-zoom-in"]').trigger('click')
    expect(wrapper.emitted('zoom-in')).toHaveLength(1)
  })

  it('emits zoom-out on − button click', async () => {
    const wrapper = mount(ViewerToolbar, { props: { zoomPercent: 100 } })
    await wrapper.find('[data-test="vt-zoom-out"]').trigger('click')
    expect(wrapper.emitted('zoom-out')).toHaveLength(1)
  })

  it('emits reset on 1:1 button click', async () => {
    const wrapper = mount(ViewerToolbar, { props: { zoomPercent: 100 } })
    await wrapper.find('[data-test="vt-reset"]').trigger('click')
    expect(wrapper.emitted('reset')).toHaveLength(1)
  })

  it('emits fit on ⛶ button click', async () => {
    const wrapper = mount(ViewerToolbar, { props: { zoomPercent: 100 } })
    await wrapper.find('[data-test="vt-fit"]').trigger('click')
    expect(wrapper.emitted('fit')).toHaveLength(1)
  })

  it('shows the current zoom percent', () => {
    const wrapper = mount(ViewerToolbar, { props: { zoomPercent: 75 } })
    expect(wrapper.find('[data-test="vt-percent"]').text()).toBe('75%')
  })
})
