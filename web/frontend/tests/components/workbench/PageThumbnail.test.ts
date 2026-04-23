import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import PageThumbnail from '@/components/workbench/PageThumbnail.vue'
import type { PageResponse } from '@/api/types'

function makePage(overrides: Partial<PageResponse> = {}): PageResponse {
  return {
    id: 1, batch_id: 1, page_index: 0,
    needs_review: false, is_blank: false, pipeline_processed: false,
    created_at: '', image_path: '/img.png', ocr_text: '',
    index_fields_json: '{}', review_reason: '', is_excluded: false,
    processing_errors_json: '[]', script_errors_json: '[]',
    barcodes: [], updated_at: '',
    ...overrides,
  }
}

describe('PageThumbnail', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders the page index in the footer', () => {
    const wrapper = mount(PageThumbnail, {
      props: { page: makePage({ page_index: 4 }), batchId: 1, selected: false },
      global: { stubs: { AuthImage: true } },
    })
    expect(wrapper.text()).toContain('#5')
  })

  it('applies danger border when page is_excluded', () => {
    const wrapper = mount(PageThumbnail, {
      props: { page: makePage({ is_excluded: true }), batchId: 1, selected: false },
      global: { stubs: { AuthImage: true } },
    })
    expect(wrapper.find('button').classes()).toContain('border-danger')
  })

  it('applies primary border when page has fields', () => {
    const wrapper = mount(PageThumbnail, {
      props: { page: makePage({ index_fields_json: '{"a":1}' }), batchId: 1, selected: false },
      global: { stubs: { AuthImage: true } },
    })
    expect(wrapper.find('button').classes()).toContain('border-primary')
  })

  it('emits "select" on click', async () => {
    const wrapper = mount(PageThumbnail, {
      props: { page: makePage(), batchId: 1, selected: false },
      global: { stubs: { AuthImage: true } },
    })
    await wrapper.find('button').trigger('click')
    expect(wrapper.emitted('select')).toHaveLength(1)
  })

  it('emits "fit" on double click', async () => {
    const wrapper = mount(PageThumbnail, {
      props: { page: makePage(), batchId: 1, selected: false },
      global: { stubs: { AuthImage: true } },
    })
    await wrapper.find('button').trigger('dblclick')
    expect(wrapper.emitted('fit')).toHaveLength(1)
  })

  it('marks aria-pressed=true when selected', () => {
    const wrapper = mount(PageThumbnail, {
      props: { page: makePage(), batchId: 1, selected: true },
      global: { stubs: { AuthImage: true } },
    })
    expect(wrapper.find('button').attributes('aria-pressed')).toBe('true')
  })

  it('shows ✓ icon when pipeline_processed', () => {
    const wrapper = mount(PageThumbnail, {
      props: { page: makePage({ pipeline_processed: true }), batchId: 1, selected: false },
      global: { stubs: { AuthImage: true } },
    })
    expect(wrapper.text()).toContain('✓')
  })

  it('shows excluded badge when is_excluded=true', () => {
    const wrapper = mount(PageThumbnail, {
      props: { page: makePage({ is_excluded: true }), batchId: 1, selected: false },
      global: { stubs: { AuthImage: true } },
    })
    expect(wrapper.find('[data-testid="badge-excluded"]').exists()).toBe(true)
  })

  it('does NOT show excluded badge when is_excluded=false', () => {
    const wrapper = mount(PageThumbnail, {
      props: { page: makePage(), batchId: 1, selected: false },
      global: { stubs: { AuthImage: true } },
    })
    expect(wrapper.find('[data-testid="badge-excluded"]').exists()).toBe(false)
  })

  it('shows review badge when needs_review=true', () => {
    const wrapper = mount(PageThumbnail, {
      props: { page: makePage({ needs_review: true }), batchId: 1, selected: false },
      global: { stubs: { AuthImage: true } },
    })
    expect(wrapper.find('[data-testid="badge-review"]').exists()).toBe(true)
  })

  it('does NOT show review badge when needs_review=false', () => {
    const wrapper = mount(PageThumbnail, {
      props: { page: makePage(), batchId: 1, selected: false },
      global: { stubs: { AuthImage: true } },
    })
    expect(wrapper.find('[data-testid="badge-review"]').exists()).toBe(false)
  })

  it('shows both badges when both flags are true', () => {
    const wrapper = mount(PageThumbnail, {
      props: {
        page: makePage({ is_excluded: true, needs_review: true }),
        batchId: 1,
        selected: false,
      },
      global: { stubs: { AuthImage: true } },
    })
    expect(wrapper.find('[data-testid="badge-excluded"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="badge-review"]').exists()).toBe(true)
  })
})
