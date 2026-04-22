import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import ThumbnailPanel from '@/components/workbench/ThumbnailPanel.vue'
import type { PageResponse } from '@/api/types'

function makePage(idx: number): PageResponse {
  return {
    id: idx + 1, batch_id: 1, page_index: idx,
    needs_review: false, is_blank: false, pipeline_processed: false,
    created_at: '', image_path: `/p${idx}.png`, ocr_text: '',
    index_fields_json: '{}', review_reason: '', is_excluded: false,
    processing_errors_json: '[]', script_errors_json: '[]',
    barcodes: [], updated_at: '',
  }
}

describe('ThumbnailPanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('shows empty state when pages list is empty', () => {
    const wrapper = mount(ThumbnailPanel, {
      props: { pages: [], batchId: 1, selectedIndex: 0 },
      global: { stubs: { PageThumbnail: true, AuthImage: true } },
    })
    expect(wrapper.text()).toContain('Sin páginas')
  })

  it('renders one PageThumbnail per page', () => {
    const wrapper = mount(ThumbnailPanel, {
      props: { pages: [makePage(0), makePage(1), makePage(2)], batchId: 1, selectedIndex: 0 },
      global: { stubs: { PageThumbnail: true, AuthImage: true } },
    })
    expect(wrapper.findAllComponents({ name: 'PageThumbnail' })).toHaveLength(3)
  })

  it('emits "select" with index when child PageThumbnail emits select', async () => {
    const wrapper = mount(ThumbnailPanel, {
      props: { pages: [makePage(0), makePage(1)], batchId: 1, selectedIndex: 0 },
    })
    const thumbs = wrapper.findAllComponents({ name: 'PageThumbnail' })
    thumbs[1].vm.$emit('select')
    expect(wrapper.emitted('select')).toEqual([[1]])
  })

  it('emits "fit" when child PageThumbnail emits fit', () => {
    const wrapper = mount(ThumbnailPanel, {
      props: { pages: [makePage(0)], batchId: 1, selectedIndex: 0 },
    })
    wrapper.findComponent({ name: 'PageThumbnail' }).vm.$emit('fit')
    expect(wrapper.emitted('fit')).toHaveLength(1)
  })
})
