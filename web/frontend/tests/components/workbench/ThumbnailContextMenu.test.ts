import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ThumbnailContextMenu from '@/components/workbench/ThumbnailContextMenu.vue'

describe('ThumbnailContextMenu', () => {
  const defaults = {
    visible: true, x: 100, y: 200,
    pageId: 7,
    isExcluded: false, needsReview: false,
    readOnly: false, isLastPage: false,
  }

  it('renders 4 actions when visible and not last page', () => {
    const wrapper = mount(ThumbnailContextMenu, { props: defaults, attachTo: document.body })
    expect(wrapper.find('[data-testid="action-exclude"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="action-review"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="action-delete"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="action-delete-after"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('hides delete-after when isLastPage=true', () => {
    const wrapper = mount(ThumbnailContextMenu, {
      props: { ...defaults, isLastPage: true },
      attachTo: document.body,
    })
    expect(wrapper.find('[data-testid="action-delete"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="action-delete-after"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('does not render when visible=false', () => {
    const wrapper = mount(ThumbnailContextMenu, {
      props: { ...defaults, visible: false },
    })
    expect(wrapper.find('[data-testid="action-exclude"]').exists()).toBe(false)
  })

  it('emits action toggle-excluded with pageId', async () => {
    const wrapper = mount(ThumbnailContextMenu, { props: defaults, attachTo: document.body })
    await wrapper.find('[data-testid="action-exclude"]').trigger('click')
    expect(wrapper.emitted('action')?.[0]).toEqual(['toggle-excluded', 7])
    wrapper.unmount()
  })

  it('emits action toggle-review', async () => {
    const wrapper = mount(ThumbnailContextMenu, { props: defaults, attachTo: document.body })
    await wrapper.find('[data-testid="action-review"]').trigger('click')
    expect(wrapper.emitted('action')?.[0]).toEqual(['toggle-review', 7])
    wrapper.unmount()
  })

  it('emits action delete-page', async () => {
    const wrapper = mount(ThumbnailContextMenu, { props: defaults, attachTo: document.body })
    await wrapper.find('[data-testid="action-delete"]').trigger('click')
    expect(wrapper.emitted('action')?.[0]).toEqual(['delete-page', 7])
    wrapper.unmount()
  })

  it('emits action delete-after', async () => {
    const wrapper = mount(ThumbnailContextMenu, { props: defaults, attachTo: document.body })
    await wrapper.find('[data-testid="action-delete-after"]').trigger('click')
    expect(wrapper.emitted('action')?.[0]).toEqual(['delete-after', 7])
    wrapper.unmount()
  })

  it('emits close on ESC keypress', async () => {
    const wrapper = mount(ThumbnailContextMenu, { props: defaults, attachTo: document.body })
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('close')).toBeTruthy()
    wrapper.unmount()
  })

  it('emits close on outside click', async () => {
    const wrapper = mount(ThumbnailContextMenu, { props: defaults, attachTo: document.body })
    // Click en el body, fuera del menú
    document.body.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('close')).toBeTruthy()
    wrapper.unmount()
  })

  it('does not emit close when clicking inside the menu', async () => {
    const wrapper = mount(ThumbnailContextMenu, { props: defaults, attachTo: document.body })
    const menu = wrapper.find('[data-thumb-ctx]').element as HTMLElement
    menu.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('close')).toBeFalsy()
    wrapper.unmount()
  })

  it('disables all items when readOnly=true', async () => {
    const wrapper = mount(ThumbnailContextMenu, {
      props: { ...defaults, readOnly: true },
      attachTo: document.body,
    })
    const items = wrapper.findAll('[role="menuitem"]')
    items.forEach(i => {
      expect(i.attributes('disabled')).toBeDefined()
    })
    // Clickar no emite action
    await wrapper.find('[data-testid="action-exclude"]').trigger('click')
    expect(wrapper.emitted('action')).toBeFalsy()
    wrapper.unmount()
  })

  it('shows "Incluir" label when isExcluded=true', () => {
    const wrapper = mount(ThumbnailContextMenu, {
      props: { ...defaults, isExcluded: true },
      attachTo: document.body,
    })
    expect(wrapper.find('[data-testid="action-exclude"]').text()).toContain('Incluir')
    wrapper.unmount()
  })

  it('shows "Quitar revisión" label when needsReview=true', () => {
    const wrapper = mount(ThumbnailContextMenu, {
      props: { ...defaults, needsReview: true },
      attachTo: document.body,
    })
    expect(wrapper.find('[data-testid="action-review"]').text()).toContain('Quitar')
    wrapper.unmount()
  })
})
