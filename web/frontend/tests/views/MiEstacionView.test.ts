import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import MiEstacionView from '@/views/MiEstacionView.vue'
import { useAgentStore } from '@/stores/agent'
import type { AgentStatus } from '@/api/types'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
  ApiError: class extends Error {
    status: number
    detail: string
    constructor(status: number, detail: string) {
      super(detail)
      this.status = status
      this.detail = detail
    }
  },
}))

vi.mock('@/composables/useToast', () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  }),
}))

const STATUS_UNPAIRED: AgentStatus = {
  name: 'docscan-local-agent',
  version: '0.1.0',
  paired: false,
  device_name: null,
  user_email: null,
  tenant_name: null,
}

const STATUS_PAIRED: AgentStatus = {
  name: 'docscan-local-agent',
  version: '0.1.0',
  paired: true,
  device_name: 'Portátil Ana',
  user_email: 'ana@example.com',
  tenant_name: 'TecnoMedia',
}

function mockFetchSequence(...responses: { payload: unknown; ok?: boolean; status?: number }[]) {
  const fetchMock = vi.fn()
  for (const r of responses) {
    fetchMock.mockResolvedValueOnce({
      ok: r.ok ?? true,
      status: r.status ?? 200,
      json: async () => r.payload,
      text: async () => JSON.stringify(r.payload),
    })
  }
  globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch
  return fetchMock
}

describe('MiEstacionView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('estado 1: muestra placeholder cuando el agente no está disponible', async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch

    const wrapper = mount(MiEstacionView)
    await flushPromises()

    expect(wrapper.find('[data-testid="state-not-detected"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="state-unpaired"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="state-paired"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('No detectamos el agente local')
  })

  it('estado 2: muestra formulario de pairing si el agente está detectado sin vincular', async () => {
    mockFetchSequence({ payload: STATUS_UNPAIRED })

    const wrapper = mount(MiEstacionView)
    await flushPromises()

    expect(wrapper.find('[data-testid="state-unpaired"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="state-not-detected"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="state-paired"]').exists()).toBe(false)

    const input = wrapper.find('[data-testid="device-name-input"]')
    expect(input.exists()).toBe(true)
    // Botón disabled mientras no haya nombre.
    const button = wrapper.find('[data-testid="pair-button"]')
    expect(button.attributes('disabled')).toBeDefined()
  })

  it('estado 3: vinculado muestra metadata + lista escáneres + carga al mount', async () => {
    // Mount: detect → STATUS_PAIRED, después loadScanners → 2 escáneres.
    mockFetchSequence(
      { payload: STATUS_PAIRED },
      { payload: ['dev:001', 'epson:fake'] },
    )

    const wrapper = mount(MiEstacionView)
    await flushPromises()

    expect(wrapper.find('[data-testid="state-paired"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Portátil Ana')
    expect(wrapper.text()).toContain('ana@example.com')
    expect(wrapper.text()).toContain('TecnoMedia')

    const list = wrapper.find('[data-testid="scanner-list"]')
    expect(list.exists()).toBe(true)
    expect(list.text()).toContain('dev:001')
    expect(list.text()).toContain('epson:fake')
  })

  it('estado 3: si no hay escáneres muestra el mensaje "no se ha detectado"', async () => {
    mockFetchSequence(
      { payload: STATUS_PAIRED },
      { payload: [] },
    )

    const wrapper = mount(MiEstacionView)
    await flushPromises()

    expect(wrapper.find('[data-testid="no-scanners"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="scanner-list"]').exists()).toBe(false)
  })

  it('botón "Comprobar de nuevo" re-ejecuta detect()', async () => {
    mockFetchSequence({ payload: STATUS_UNPAIRED })

    const wrapper = mount(MiEstacionView)
    await flushPromises()

    const store = useAgentStore()
    const detectSpy = vi.spyOn(store, 'detect')

    await wrapper.find('[data-testid="refresh-button"]').trigger('click')
    expect(detectSpy).toHaveBeenCalled()
  })
})
