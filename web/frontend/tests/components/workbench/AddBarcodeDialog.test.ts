import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AddBarcodeDialog from '@/components/workbench/AddBarcodeDialog.vue'

describe('AddBarcodeDialog', () => {
  it('does not render when visible=false', () => {
    const wrapper = mount(AddBarcodeDialog, { props: { visible: false } })
    expect(wrapper.find('[data-testid="barcode-value"]').exists()).toBe(false)
  })

  it('renders input and select when visible', () => {
    const wrapper = mount(AddBarcodeDialog, { props: { visible: true } })
    expect(wrapper.find('[data-testid="barcode-value"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="barcode-symbology"]').exists()).toBe(true)
  })

  it('disables submit when value is empty', () => {
    const wrapper = mount(AddBarcodeDialog, { props: { visible: true } })
    expect(wrapper.find('[data-testid="submit"]').attributes('disabled')).toBeDefined()
  })

  it('disables submit when value is whitespace only', async () => {
    const wrapper = mount(AddBarcodeDialog, { props: { visible: true } })
    await wrapper.find('[data-testid="barcode-value"]').setValue('   ')
    expect(wrapper.find('[data-testid="submit"]').attributes('disabled')).toBeDefined()
  })

  it('enables submit when value is present', async () => {
    const wrapper = mount(AddBarcodeDialog, { props: { visible: true } })
    await wrapper.find('[data-testid="barcode-value"]').setValue('ABC')
    expect(wrapper.find('[data-testid="submit"]').attributes('disabled')).toBeUndefined()
  })

  it('emits submit with trimmed value and symbology', async () => {
    const wrapper = mount(AddBarcodeDialog, { props: { visible: true } })
    await wrapper.find('[data-testid="barcode-value"]').setValue('  ABC123  ')
    await wrapper.find('[data-testid="barcode-symbology"]').setValue('CODE128')
    await wrapper.find('[data-testid="submit"]').trigger('click')
    expect(wrapper.emitted('submit')?.[0]).toEqual([{ value: 'ABC123', symbology: 'CODE128' }])
  })

  it('emits close on cancel', async () => {
    const wrapper = mount(AddBarcodeDialog, { props: { visible: true } })
    await wrapper.find('[data-testid="cancel"]').trigger('click')
    expect(wrapper.emitted('close')).toBeTruthy()
  })

  it('resets fields when visible becomes true again', async () => {
    const wrapper = mount(AddBarcodeDialog, { props: { visible: true } })
    await wrapper.find('[data-testid="barcode-value"]').setValue('ABC')

    // Cerrar y reabrir
    await wrapper.setProps({ visible: false })
    await wrapper.setProps({ visible: true })

    const input = wrapper.find('[data-testid="barcode-value"]').element as HTMLInputElement
    expect(input.value).toBe('')
  })

  it('offers 8 symbologies', () => {
    const wrapper = mount(AddBarcodeDialog, { props: { visible: true } })
    const options = wrapper.findAll('[data-testid="barcode-symbology"] option')
    expect(options.length).toBe(8)
  })

  it('defaults symbology to MANUAL', () => {
    const wrapper = mount(AddBarcodeDialog, { props: { visible: true } })
    const select = wrapper.find('[data-testid="barcode-symbology"]').element as HTMLSelectElement
    expect(select.value).toBe('MANUAL')
  })

  it('expone role=dialog y aria-modal=true para que el filtro de useWorkbenchShortcuts lo detecte', () => {
    // Regresión: si faltan estos atributos, los atajos globales (R, Esc, etc.)
    // siguen activos con el dialog abierto y rotan/cierran lo que no toca.
    const wrapper = mount(AddBarcodeDialog, { props: { visible: true } })
    const dlg = wrapper.find('[role="dialog"]')
    expect(dlg.exists()).toBe(true)
    expect(dlg.attributes('aria-modal')).toBe('true')
    expect(dlg.attributes('aria-label')).toBe('Añadir barcode manual')
  })

  it('Escape cierra el dialog (mediante listener global) sin propagar al lote', async () => {
    // Regresión #28: Esc con dialog abierto cerraba el lote. El listener
    // global capture+stopPropagation lo evita y emite close.
    const wrapper = mount(AddBarcodeDialog, { props: { visible: true }, attachTo: document.body })
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    expect(wrapper.emitted('close')).toBeTruthy()
    wrapper.unmount()
  })
})
