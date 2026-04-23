import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import ThumbnailPanel from '@/components/workbench/ThumbnailPanel.vue'
import type { PageResponse } from '@/api/types'

function makePage(idx: number): PageResponse {
  return {
    id: idx + 1,
    batch_id: 1,
    page_index: idx,
    image_path: `/p${idx}.png`,
    ocr_text: '',
    index_fields_json: '{}',
    needs_review: false,
    review_reason: '',
    is_blank: false,
    is_excluded: false,
    pipeline_processed: false,
    processing_errors_json: '[]',
    script_errors_json: '[]',
    barcodes: [],
    created_at: '2026-04-23',
    updated_at: '2026-04-23',
  }
}

const mockPages = [makePage(0), makePage(1), makePage(2)]

describe('ThumbnailPanel — drag + contextmenu', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders a thumbnail per page', () => {
    const wrapper = mount(ThumbnailPanel, {
      props: { pages: mockPages, batchId: 1, currentIndex: 0, readOnly: false },
      global: { stubs: { AuthImage: true } },
    })
    expect(wrapper.findAllComponents({ name: 'PageThumbnail' })).toHaveLength(3)
  })

  it('emits select when a thumbnail is clicked', async () => {
    const wrapper = mount(ThumbnailPanel, {
      props: { pages: mockPages, batchId: 1, currentIndex: 0, readOnly: false },
      global: { stubs: { AuthImage: true } },
    })
    await wrapper.findAll('[data-testid^="thumb-"]')[1].trigger('click')
    expect(wrapper.emitted('select')?.[0]).toEqual([1])
  })

  it('emits fit when a thumbnail is double-clicked', async () => {
    const wrapper = mount(ThumbnailPanel, {
      props: { pages: mockPages, batchId: 1, currentIndex: 0, readOnly: false },
      global: { stubs: { AuthImage: true } },
    })
    const thumbs = wrapper.findAllComponents({ name: 'PageThumbnail' })
    thumbs[0].vm.$emit('fit')
    expect(wrapper.emitted('fit')).toHaveLength(1)
  })

  it('emits contextmenu with pageId and coords on right-click', async () => {
    const wrapper = mount(ThumbnailPanel, {
      props: { pages: mockPages, batchId: 1, currentIndex: 0, readOnly: false },
      global: { stubs: { AuthImage: true } },
    })
    const thumb = wrapper.findAll('[data-testid^="thumb-"]')[1]
    await thumb.trigger('contextmenu', { clientX: 123, clientY: 456 })
    expect(wrapper.emitted('contextmenu')?.[0]).toEqual([2, 123, 456])
  })

  it('emits reorder with new page-id order after drag-end', async () => {
    const wrapper = mount(ThumbnailPanel, {
      props: { pages: mockPages, batchId: 1, currentIndex: 0, readOnly: false },
      global: { stubs: { AuthImage: true } },
    })
    // Simular reorden mutando directamente la lista local expuesta y llamando onDragEnd
    ;(wrapper.vm as any).list = [mockPages[2], mockPages[0], mockPages[1]]
    ;(wrapper.vm as any).onDragEnd()
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('reorder')?.[0]).toEqual([[3, 1, 2]])
  })

  it('renders VueDraggable with disabled=true when readOnly', () => {
    const wrapper = mount(ThumbnailPanel, {
      props: { pages: mockPages, batchId: 1, currentIndex: 0, readOnly: true },
      global: { stubs: { AuthImage: true } },
    })
    const draggable = wrapper.findComponent({ name: 'VueDraggable' })
    expect(draggable.exists()).toBe(true)
    expect(draggable.props('disabled')).toBe(true)
  })

  it('reorder event not emitted when readOnly', async () => {
    const wrapper = mount(ThumbnailPanel, {
      props: { pages: mockPages, batchId: 1, currentIndex: 0, readOnly: true },
      global: { stubs: { AuthImage: true } },
    })
    ;(wrapper.vm as any).list = [mockPages[2], mockPages[0], mockPages[1]]
    ;(wrapper.vm as any).onDragEnd()
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('reorder')).toBeFalsy()
  })

  it('empty state when no pages', () => {
    const wrapper = mount(ThumbnailPanel, {
      props: { pages: [], batchId: 1, currentIndex: 0, readOnly: false },
      global: { stubs: { AuthImage: true } },
    })
    expect(wrapper.text()).toContain('Sin páginas')
  })

  it('syncs local list when parent updates pages prop', async () => {
    const wrapper = mount(ThumbnailPanel, {
      props: { pages: mockPages, batchId: 1, currentIndex: 0, readOnly: false },
      global: { stubs: { AuthImage: true } },
    })
    const newPages = [makePage(0), makePage(1)]
    await wrapper.setProps({ pages: newPages })
    expect((wrapper.vm as any).list).toHaveLength(2)
  })
})
