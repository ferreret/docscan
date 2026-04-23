import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ViewerToolbar from '@/components/workbench/ViewerToolbar.vue'

describe('ViewerToolbar', () => {
  it('renders zoom buttons and a percent indicator', () => {
    const wrapper = mount(ViewerToolbar, { props: { zoomPercent: 100 } })
    expect(wrapper.find('[data-test="vt-zoom-in"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="vt-zoom-out"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="vt-reset"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="vt-fit"]').exists()).toBe(true)
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

describe('ViewerToolbar — rotate + overlay toggles', () => {
  const defaults = {
    zoomPercent: 100,
    canRotate: true,
    showBarcodes: true,
    showFields: true,
  }

  it('emits rotate with turns=1 when clicking 90°', async () => {
    const wrapper = mount(ViewerToolbar, { props: defaults, attachTo: document.body })
    await wrapper.find('[data-testid="btn-rotate"]').trigger('click')
    await wrapper.find('[data-testid="rotate-90"]').trigger('click')
    expect(wrapper.emitted('rotate')?.[0]).toEqual([1])
    wrapper.unmount()
  })

  it('emits rotate with turns=2 when clicking 180°', async () => {
    const wrapper = mount(ViewerToolbar, { props: defaults, attachTo: document.body })
    await wrapper.find('[data-testid="btn-rotate"]').trigger('click')
    await wrapper.find('[data-testid="rotate-180"]').trigger('click')
    expect(wrapper.emitted('rotate')?.[0]).toEqual([2])
    wrapper.unmount()
  })

  it('emits rotate with turns=3 when clicking 270°', async () => {
    const wrapper = mount(ViewerToolbar, { props: defaults, attachTo: document.body })
    await wrapper.find('[data-testid="btn-rotate"]').trigger('click')
    await wrapper.find('[data-testid="rotate-270"]').trigger('click')
    expect(wrapper.emitted('rotate')?.[0]).toEqual([3])
    wrapper.unmount()
  })

  it('disables rotate when canRotate=false', () => {
    const wrapper = mount(ViewerToolbar, {
      props: { ...defaults, canRotate: false },
    })
    const btn = wrapper.find('[data-testid="btn-rotate"]')
    expect(btn.attributes('disabled')).toBeDefined()
  })

  it('emits toggle-barcodes on click', async () => {
    const wrapper = mount(ViewerToolbar, { props: defaults })
    await wrapper.find('[data-testid="btn-toggle-barcodes"]').trigger('click')
    expect(wrapper.emitted('toggle-barcodes')).toBeTruthy()
  })

  it('emits toggle-fields on click', async () => {
    const wrapper = mount(ViewerToolbar, { props: defaults })
    await wrapper.find('[data-testid="btn-toggle-fields"]').trigger('click')
    expect(wrapper.emitted('toggle-fields')).toBeTruthy()
  })

  it('toggle buttons reflect state (ON vs OFF)', () => {
    const wrapperOn = mount(ViewerToolbar, {
      props: { ...defaults, showBarcodes: true },
    })
    const wrapperOff = mount(ViewerToolbar, {
      props: { ...defaults, showBarcodes: false },
    })
    expect(wrapperOn.find('[data-testid="btn-toggle-barcodes"]').attributes('aria-pressed')).toBe('true')
    expect(wrapperOff.find('[data-testid="btn-toggle-barcodes"]').attributes('aria-pressed')).toBe('false')
  })
})
