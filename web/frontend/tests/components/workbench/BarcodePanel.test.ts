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

const emptyCounters = { total: 0, withBarcode: 0, separators: 0, needsReview: 0 }

describe('BarcodePanel', () => {
  it('renders empty state when no barcodes', () => {
    const wrapper = mount(BarcodePanel, { props: { barcodes: [], pageCounters: emptyCounters } })
    expect(wrapper.text()).toContain('Sin barcodes')
  })

  it('renders a row per barcode with 6 columns (incl. acciones) when !readOnly', () => {
    const wrapper = mount(BarcodePanel, {
      props: {
        barcodes: [makeBarcode({ id: 1, value: 'A' }), makeBarcode({ id: 2, value: 'B', role: 'separator' })],
        pageCounters: { total: 1, withBarcode: 1, separators: 1, needsReview: 0 },
      },
    })
    const rows = wrapper.findAll('tbody tr')
    expect(rows).toHaveLength(2)
    expect(rows[0].findAll('td')).toHaveLength(6)
  })

  it('renders a row per barcode with 5 columns when readOnly', () => {
    const wrapper = mount(BarcodePanel, {
      props: {
        barcodes: [makeBarcode({ id: 1, value: 'A' })],
        pageCounters: emptyCounters,
        readOnly: true,
      },
    })
    const rows = wrapper.findAll('tbody tr')
    expect(rows).toHaveLength(1)
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
      props: { barcodes: [makeBarcode({ role: '' })], pageCounters: emptyCounters },
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

describe('BarcodePanel — editable', () => {
  it('shows + Añadir button when !readOnly', () => {
    const wrapper = mount(BarcodePanel, {
      props: { barcodes: [], pageCounters: emptyCounters },
    })
    expect(wrapper.find('[data-testid="btn-add-barcode"]').exists()).toBe(true)
  })

  it('hides + Añadir button when readOnly', () => {
    const wrapper = mount(BarcodePanel, {
      props: { barcodes: [], pageCounters: emptyCounters, readOnly: true },
    })
    expect(wrapper.find('[data-testid="btn-add-barcode"]').exists()).toBe(false)
  })

  it('emits add-barcode on + click', async () => {
    const wrapper = mount(BarcodePanel, {
      props: { barcodes: [], pageCounters: emptyCounters },
    })
    await wrapper.find('[data-testid="btn-add-barcode"]').trigger('click')
    expect(wrapper.emitted('add-barcode')).toBeTruthy()
  })

  it('shows × button per row when !readOnly', () => {
    const wrapper = mount(BarcodePanel, {
      props: {
        barcodes: [makeBarcode({ id: 1, value: 'A' }), makeBarcode({ id: 2, value: 'B' })],
        pageCounters: emptyCounters,
      },
    })
    expect(wrapper.find('[data-testid="btn-delete-bc-1"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="btn-delete-bc-2"]').exists()).toBe(true)
  })

  it('hides × buttons when readOnly', () => {
    const wrapper = mount(BarcodePanel, {
      props: {
        barcodes: [makeBarcode({ id: 1, value: 'A' })],
        pageCounters: emptyCounters,
        readOnly: true,
      },
    })
    expect(wrapper.find('[data-testid="btn-delete-bc-1"]').exists()).toBe(false)
  })

  it('emits delete-barcode with id on × click', async () => {
    const wrapper = mount(BarcodePanel, {
      props: {
        barcodes: [makeBarcode({ id: 42, value: 'X' })],
        pageCounters: emptyCounters,
      },
    })
    await wrapper.find('[data-testid="btn-delete-bc-42"]').trigger('click')
    expect(wrapper.emitted('delete-barcode')?.[0]).toEqual([42])
  })

  it('renders barcode rows', () => {
    const wrapper = mount(BarcodePanel, {
      props: {
        barcodes: [makeBarcode({ id: 1, value: 'ABC' }), makeBarcode({ id: 2, value: 'DEF' })],
        pageCounters: emptyCounters,
      },
    })
    expect(wrapper.text()).toContain('ABC')
    expect(wrapper.text()).toContain('DEF')
  })
})
