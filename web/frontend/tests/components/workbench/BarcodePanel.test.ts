import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BarcodePanel from '@/components/workbench/BarcodePanel.vue'
import type { BarcodeResponse } from '@/api/types'

function makeBarcode(overrides: Partial<BarcodeResponse> = {}): BarcodeResponse {
  return {
    id: 1, value: '12345', symbology: 'EAN13', engine: 'motor1',
    step_id: 's1', quality: 1, pos_x: 0, pos_y: 0, pos_w: 10, pos_h: 10, role: '',
    ...overrides,
  }
}

describe('BarcodePanel', () => {
  it('renders empty state when no barcodes', () => {
    const wrapper = mount(BarcodePanel, { props: { barcodes: [], pageCounters: { total: 0, withBarcode: 0, separators: 0, needsReview: 0 } } })
    expect(wrapper.text()).toContain('Sin barcodes')
  })

  it('renders a row per barcode with 5 columns', () => {
    const wrapper = mount(BarcodePanel, {
      props: {
        barcodes: [makeBarcode({ id: 1, value: 'A' }), makeBarcode({ id: 2, value: 'B', role: 'separator' })],
        pageCounters: { total: 1, withBarcode: 1, separators: 1, needsReview: 0 },
      },
    })
    const rows = wrapper.findAll('tbody tr')
    expect(rows).toHaveLength(2)
    expect(rows[0].findAll('td')).toHaveLength(5)
  })

  it('shows counters in header', () => {
    const wrapper = mount(BarcodePanel, {
      props: {
        barcodes: [],
        pageCounters: { total: 12, withBarcode: 8, separators: 3, needsReview: 1 },
      },
    })
    expect(wrapper.find('[data-test="counter-total"]').text()).toContain('12')
    expect(wrapper.find('[data-test="counter-with-barcode"]').text()).toContain('8')
    expect(wrapper.find('[data-test="counter-separators"]').text()).toContain('3')
    expect(wrapper.find('[data-test="counter-needs-review"]').text()).toContain('1')
  })

  it('shows em-dash when role is empty', () => {
    const wrapper = mount(BarcodePanel, {
      props: { barcodes: [makeBarcode({ role: '' })], pageCounters: { total: 0, withBarcode: 0, separators: 0, needsReview: 0 } },
    })
    expect(wrapper.find('tbody tr').findAll('td')[4].text()).toBe('—')
  })

  it('cycles colors when more barcodes than palette', () => {
    const many = Array.from({ length: 9 }, (_, i) => makeBarcode({ id: i + 1, value: `V${i}` }))
    const wrapper = mount(BarcodePanel, {
      props: { barcodes: many, pageCounters: { total: 1, withBarcode: 1, separators: 0, needsReview: 0 } },
    })
    const dots = wrapper.findAll('tbody tr td:first-child span')
    expect(dots[0].attributes('style')).toBe(dots[8].attributes('style'))
  })
})
