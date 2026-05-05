import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import DeleteBarcodeDialog from '@/components/workbench/DeleteBarcodeDialog.vue'

describe('DeleteBarcodeDialog', () => {
  it('does not render when visible=false', () => {
    const wrapper = mount(DeleteBarcodeDialog, {
      props: { visible: false, barcodeValue: 'X' },
    })
    expect(wrapper.find('[data-testid="confirm"]').exists()).toBe(false)
  })

  it('shows barcode value in message', () => {
    const wrapper = mount(DeleteBarcodeDialog, {
      props: { visible: true, barcodeValue: 'ABC123' },
    })
    expect(wrapper.text()).toContain('ABC123')
  })

  it('emits confirm on click', async () => {
    const wrapper = mount(DeleteBarcodeDialog, {
      props: { visible: true, barcodeValue: 'X' },
    })
    await wrapper.find('[data-testid="confirm"]').trigger('click')
    expect(wrapper.emitted('confirm')).toBeTruthy()
  })

  it('emits close on cancel click', async () => {
    const wrapper = mount(DeleteBarcodeDialog, {
      props: { visible: true, barcodeValue: 'X' },
    })
    await wrapper.find('[data-testid="cancel"]').trigger('click')
    expect(wrapper.emitted('close')).toBeTruthy()
  })

  it('emits close on outside click (overlay self)', async () => {
    const wrapper = mount(DeleteBarcodeDialog, {
      props: { visible: true, barcodeValue: 'X' },
    })
    // @click.self se dispara cuando target === currentTarget (el overlay)
    await wrapper.find('[data-testid="overlay"]').trigger('click')
    expect(wrapper.emitted('close')).toBeTruthy()
  })
})
