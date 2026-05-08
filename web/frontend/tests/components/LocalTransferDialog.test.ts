import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import LocalTransferDialog from '@/components/workbench/LocalTransferDialog.vue'

vi.mock('@/api/agent', () => ({
  transferBatchToLocal: vi.fn(),
}))

import { transferBatchToLocal } from '@/api/agent'

beforeEach(() => {
  vi.clearAllMocks()
})

describe('LocalTransferDialog', () => {
  it('no se renderiza si visible=false', () => {
    const wrapper = mount(LocalTransferDialog, {
      props: { visible: false, batchId: 42 },
    })
    expect(wrapper.find('[data-testid="local-transfer-dialog"]').exists()).toBe(
      false,
    )
  })

  it('botón Descargar deshabilitado si destination está vacío', async () => {
    const wrapper = mount(LocalTransferDialog, {
      props: { visible: true, batchId: 42 },
    })
    await flushPromises()

    expect(
      wrapper.find('[data-testid="confirm-button"]').attributes('disabled'),
    ).toBeDefined()
  })

  it('happy path: destination + mode default → llama al helper y emite success+close', async () => {
    vi.mocked(transferBatchToLocal).mockResolvedValueOnce({
      batch_id: 42,
      mode: 'extracted',
      path: '/home/ana/out/batch_42',
      files_count: 5,
      bytes: 12345,
    })

    const wrapper = mount(LocalTransferDialog, {
      props: { visible: true, batchId: 42 },
    })
    await flushPromises()

    await wrapper
      .find('[data-testid="destination-input"]')
      .setValue('/home/ana/out')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(transferBatchToLocal).toHaveBeenCalledWith({
      batch_id: 42,
      destination: '/home/ana/out',
      mode: 'extracted',
    })
    expect(wrapper.emitted('success')?.[0][0]).toEqual({
      path: '/home/ana/out/batch_42',
      files_count: 5,
    })
    expect(wrapper.emitted('close')).toBeTruthy()
  })

  it('mode zip: el helper recibe mode=zip', async () => {
    vi.mocked(transferBatchToLocal).mockResolvedValueOnce({
      batch_id: 42,
      mode: 'zip',
      path: '/tmp/batch_42.zip',
      files_count: 1,
      bytes: 4096,
    })

    const wrapper = mount(LocalTransferDialog, {
      props: { visible: true, batchId: 42 },
    })
    await flushPromises()

    await wrapper.find('[data-testid="destination-input"]').setValue('/tmp')
    await wrapper.find('[data-testid="mode-zip"]').setValue(true)
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    const call = vi.mocked(transferBatchToLocal).mock.calls[0][0]
    expect(call.mode).toBe('zip')
  })

  it('error del agente: emite error con detail y NO emite success/close', async () => {
    vi.mocked(transferBatchToLocal).mockRejectedValueOnce(
      new Error('La ruta destino apunta a un fichero existente: /tmp/x.txt'),
    )

    const wrapper = mount(LocalTransferDialog, {
      props: { visible: true, batchId: 42 },
    })
    await flushPromises()

    await wrapper
      .find('[data-testid="destination-input"]')
      .setValue('/tmp/x.txt')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.emitted('error')?.[0][0]).toMatch(/fichero existente/i)
    expect(wrapper.emitted('success')).toBeFalsy()
    expect(wrapper.emitted('close')).toBeFalsy()
  })

  it('botón Cancelar emite close', async () => {
    const wrapper = mount(LocalTransferDialog, {
      props: { visible: true, batchId: 42 },
    })
    await flushPromises()

    await wrapper.find('[data-testid="cancel-button"]').trigger('click')
    expect(wrapper.emitted('close')).toBeTruthy()
  })

  it('reset entre aperturas: destination y mode vuelven a default', async () => {
    const wrapper = mount(LocalTransferDialog, {
      props: { visible: true, batchId: 42 },
    })
    await flushPromises()

    await wrapper.find('[data-testid="destination-input"]').setValue('/tmp')
    await wrapper.find('[data-testid="mode-zip"]').setValue(true)

    // Cierre y reapertura del dialog para otro lote.
    await wrapper.setProps({ visible: false })
    await wrapper.setProps({ visible: true, batchId: 99 })
    await flushPromises()

    const input = wrapper.find('[data-testid="destination-input"]')
      .element as HTMLInputElement
    expect(input.value).toBe('')
    const radio = wrapper.find('[data-testid="mode-extracted"]')
      .element as HTMLInputElement
    expect(radio.checked).toBe(true)
  })
})
