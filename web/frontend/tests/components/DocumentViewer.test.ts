import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import DocumentViewer from '@/components/DocumentViewer.vue'

describe('DocumentViewer — fields overlays', () => {
  const mockBarcode = {
    id: 1,
    value: 'X',
    symbology: 'EAN',
    engine: 'zxing',
    step_id: 's',
    quality: 0.9,
    pos_x: 0,
    pos_y: 0,
    pos_w: 50,
    pos_h: 20,
    role: '',
  }

  it('renders field overlay when value has x/y/w/h', () => {
    const wrapper = mount(DocumentViewer, {
      props: {
        imageUrl: '/test.png',
        barcodes: [],
        fields: {
          cliente: { x: 10, y: 20, w: 100, h: 30, value: 'Acme Inc' },
          fecha: 'no coords', // no debe pintarse
        },
        showBarcodes: false,
        showFields: true,
      },
    })
    const overlays = wrapper.findAll('[data-field-overlay]')
    expect(overlays).toHaveLength(1)
    expect(overlays[0].text()).toContain('cliente')
    expect(overlays[0].text()).toContain('Acme Inc')
  })

  it('hides barcode overlays when showBarcodes=false', () => {
    const wrapper = mount(DocumentViewer, {
      props: {
        imageUrl: '/test.png',
        barcodes: [mockBarcode],
        fields: {},
        showBarcodes: false,
        showFields: true,
      },
    })
    expect(wrapper.findAll('[data-barcode-overlay]')).toHaveLength(0)
  })

  it('shows barcode overlays when showBarcodes=true (default)', () => {
    const wrapper = mount(DocumentViewer, {
      props: {
        imageUrl: '/test.png',
        barcodes: [mockBarcode],
        fields: {},
      },
    })
    expect(wrapper.findAll('[data-barcode-overlay]')).toHaveLength(1)
  })

  it('hides field overlays when showFields=false', () => {
    const wrapper = mount(DocumentViewer, {
      props: {
        imageUrl: '/test.png',
        barcodes: [],
        fields: {
          cliente: { x: 10, y: 20, w: 100, h: 30, value: 'X' },
        },
        showBarcodes: true,
        showFields: false,
      },
    })
    expect(wrapper.findAll('[data-field-overlay]')).toHaveLength(0)
  })

  it('ignores fields without valid coords', () => {
    const wrapper = mount(DocumentViewer, {
      props: {
        imageUrl: '/test.png',
        barcodes: [],
        fields: {
          a: 'plain string',
          b: 123,
          c: { value: 'no coords' },
          d: { x: 0, y: 0, w: 0, h: 0, value: 'zero' }, // w/h=0 descarta
          e: { x: 10, y: 20, w: 50, h: 30, value: 'Válido' },
        },
        showFields: true,
      },
    })
    const overlays = wrapper.findAll('[data-field-overlay]')
    expect(overlays).toHaveLength(1)
    expect(overlays[0].text()).toContain('Válido')
  })

  it('shows field name only when value is empty', () => {
    const wrapper = mount(DocumentViewer, {
      props: {
        imageUrl: '/test.png',
        barcodes: [],
        fields: {
          sin_valor: { x: 1, y: 1, w: 10, h: 10, value: '' },
        },
        showFields: true,
      },
    })
    const overlay = wrapper.find('[data-field-overlay]')
    expect(overlay.text()).toContain('sin_valor')
  })
})
