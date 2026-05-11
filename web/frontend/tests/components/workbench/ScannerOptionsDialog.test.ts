import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
import ScannerOptionsDialog from '@/components/workbench/ScannerOptionsDialog.vue'
import type { DeviceOptionInfo } from '@/api/types'

// Mock del composable useScannerOptions: el dialog NO debería pegar a nadie
// directamente, sino consumirlo. El mock expone refs reactivos que el test
// puede manipular.
const mockOptions = ref<DeviceOptionInfo[]>([])
const mockLoading = ref(false)
const mockError = ref<string | null>(null)
const mockFetch = vi.fn(async () => {})

vi.mock('@/composables/useScannerOptions', () => ({
  useScannerOptions: () => ({
    options: mockOptions,
    loading: mockLoading,
    error: mockError,
    fetch: mockFetch,
  }),
  _resetScannerOptionsCache: vi.fn(),
}))

const SAMPLE_OPTIONS: DeviceOptionInfo[] = [
  {
    name: 'resolution',
    title: 'Resolución',
    description: 'DPI de captura',
    type: 'int',
    unit: 'dpi',
    constraint: [75, 150, 300, 600],
    value: 300,
    is_active: true,
    is_settable: true,
  },
  {
    name: 'mode',
    title: 'Modo',
    description: '',
    type: 'string',
    unit: '',
    constraint: ['Color', 'Gray', 'Lineart'],
    value: 'Color',
    is_active: true,
    is_settable: true,
  },
  {
    name: 'source',
    title: 'Fuente',
    description: '',
    type: 'string',
    unit: '',
    constraint: ['Flatbed', 'ADF Front', 'ADF Duplex'],
    value: 'Flatbed',
    is_active: true,
    is_settable: true,
  },
  {
    name: 'brightness',
    title: 'Brillo',
    description: '',
    type: 'int',
    unit: '',
    constraint: [-100, 100, 1],
    value: 0,
    is_active: true,
    is_settable: true,
  },
  {
    name: 'page-width',
    title: 'Ancho de página',
    description: '',
    type: 'fixed',
    unit: 'mm',
    constraint: [0, 297, 0.1],
    value: 215,
    is_active: true,
    is_settable: true,
  },
  {
    name: 'preview',
    title: 'Preview',
    description: '',
    type: 'bool',
    unit: '',
    constraint: null,
    value: false,
    is_active: true,
    is_settable: true,
  },
  {
    name: 'inactive-opt',
    title: 'Opción inactiva',
    description: '',
    type: 'int',
    unit: '',
    constraint: null,
    value: 0,
    is_active: false,
    is_settable: true,
  },
  {
    name: 'readonly-opt',
    title: 'Opción solo lectura',
    description: '',
    type: 'int',
    unit: '',
    constraint: null,
    value: 0,
    is_active: true,
    is_settable: false,
  },
]

function setOptions(opts: DeviceOptionInfo[] = SAMPLE_OPTIONS) {
  mockOptions.value = opts
  mockLoading.value = false
  mockError.value = null
}

function defaultProps(overrides: Record<string, unknown> = {}) {
  return {
    visible: true,
    scannerName: 'epson:fake',
    initialDefaults: {} as Record<string, unknown>,
    canSaveDefaults: false,
    ...overrides,
  }
}

describe('ScannerOptionsDialog', () => {
  beforeEach(() => {
    mockOptions.value = []
    mockLoading.value = false
    mockError.value = null
    mockFetch.mockClear()
  })

  it('no renderiza con visible=false', () => {
    const wrapper = mount(ScannerOptionsDialog, { props: defaultProps({ visible: false }) })
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    expect(mockFetch).not.toHaveBeenCalled()
  })

  it('al abrir dispara fetch del composable con scannerName', async () => {
    mount(ScannerOptionsDialog, { props: defaultProps() })
    await flushPromises()
    expect(mockFetch).toHaveBeenCalledWith('epson:fake')
  })

  it('al cambiar visible de false→true vuelve a fetch', async () => {
    const wrapper = mount(ScannerOptionsDialog, { props: defaultProps({ visible: false }) })
    expect(mockFetch).not.toHaveBeenCalled()
    await wrapper.setProps({ visible: true })
    await flushPromises()
    expect(mockFetch).toHaveBeenCalledTimes(1)
  })

  it('expone role=dialog y aria-modal=true', () => {
    setOptions()
    const wrapper = mount(ScannerOptionsDialog, { props: defaultProps() })
    const dlg = wrapper.find('[role="dialog"]')
    expect(dlg.exists()).toBe(true)
    expect(dlg.attributes('aria-modal')).toBe('true')
    expect(dlg.attributes('aria-label')).toContain('Opciones')
  })

  it('muestra skeleton mientras loading=true', async () => {
    mockLoading.value = true
    const wrapper = mount(ScannerOptionsDialog, { props: defaultProps() })
    await flushPromises()
    expect(wrapper.find('[data-testid="loading"]').exists()).toBe(true)
  })

  it('muestra error con botón reintentar cuando error≠null', async () => {
    mockError.value = 'agente caído'
    const wrapper = mount(ScannerOptionsDialog, { props: defaultProps() })
    await flushPromises()
    const err = wrapper.find('[data-testid="error"]')
    expect(err.exists()).toBe(true)
    expect(err.text()).toContain('agente caído')

    mockFetch.mockClear()
    await wrapper.find('[data-testid="retry"]').trigger('click')
    expect(mockFetch).toHaveBeenCalledWith('epson:fake', { refresh: true })
  })

  it('renderiza select para constraint=lista (resolution, mode, source)', async () => {
    setOptions()
    const wrapper = mount(ScannerOptionsDialog, { props: defaultProps() })
    await flushPromises()

    const resSel = wrapper.find('[data-testid="opt-resolution"] select')
    expect(resSel.exists()).toBe(true)
    const opts = resSel.findAll('option')
    expect(opts).toHaveLength(4)
    expect(opts[0].attributes('value')).toBe('75')

    const modeSel = wrapper.find('[data-testid="opt-mode"] select')
    expect(modeSel.exists()).toBe(true)
    expect((modeSel.element as HTMLSelectElement).value).toBe('Color')
  })

  it('renderiza number+range para constraint=tupla (brightness)', async () => {
    setOptions()
    const wrapper = mount(ScannerOptionsDialog, { props: defaultProps() })
    await flushPromises()
    const numInput = wrapper.find('[data-testid="opt-brightness"] input[type="number"]')
    const rangeInput = wrapper.find('[data-testid="opt-brightness"] input[type="range"]')
    expect(numInput.exists()).toBe(true)
    expect(rangeInput.exists()).toBe(true)
    expect(numInput.attributes('min')).toBe('-100')
    expect(numInput.attributes('max')).toBe('100')
    expect(numInput.attributes('step')).toBe('1')
  })

  it('renderiza checkbox para type=bool (en avanzadas)', async () => {
    setOptions()
    const wrapper = mount(ScannerOptionsDialog, { props: defaultProps() })
    await flushPromises()
    // 'preview' es avanzada — hay que expandir primero.
    await wrapper.find('[data-testid="advanced-toggle"]').trigger('click')
    const cb = wrapper.find('[data-testid="opt-preview"] input[type="checkbox"]')
    expect(cb.exists()).toBe(true)
  })

  it('omite opciones is_settable=false e is_active=false', async () => {
    setOptions()
    const wrapper = mount(ScannerOptionsDialog, { props: defaultProps() })
    await flushPromises()
    expect(wrapper.find('[data-testid="opt-inactive-opt"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="opt-readonly-opt"]').exists()).toBe(false)
  })

  it('separa secciones Esenciales y Avanzadas', async () => {
    setOptions()
    const wrapper = mount(ScannerOptionsDialog, { props: defaultProps() })
    await flushPromises()
    const essentials = wrapper.find('[data-testid="essentials"]')
    const advanced = wrapper.find('[data-testid="advanced"]')
    expect(essentials.exists()).toBe(true)
    expect(advanced.exists()).toBe(true)
    // Esenciales: resolution, mode, source, brightness (las que matchean
    // la lista hardcodeada y existen en options).
    expect(essentials.find('[data-testid="opt-resolution"]').exists()).toBe(true)
    expect(essentials.find('[data-testid="opt-mode"]').exists()).toBe(true)
    expect(essentials.find('[data-testid="opt-brightness"]').exists()).toBe(true)
    // Avanzadas: el resto (page-width, preview). Hay que expandir para verlas.
    await wrapper.find('[data-testid="advanced-toggle"]').trigger('click')
    expect(advanced.find('[data-testid="opt-page-width"]').exists()).toBe(true)
    expect(advanced.find('[data-testid="opt-preview"]').exists()).toBe(true)
  })

  it('Avanzadas arranca colapsado y se puede expandir', async () => {
    setOptions()
    const wrapper = mount(ScannerOptionsDialog, { props: defaultProps() })
    await flushPromises()
    const advanced = wrapper.find('[data-testid="advanced"]')
    // Al inicio el contenido no es visible (los inputs no se ven aunque
    // estén en el DOM si usamos un v-show). Comprobamos vía un
    // data-testid del bloque colapsable.
    expect(advanced.find('[data-testid="advanced-body"]').exists()).toBe(false)

    await advanced.find('[data-testid="advanced-toggle"]').trigger('click')
    expect(advanced.find('[data-testid="advanced-body"]').exists()).toBe(true)
  })

  it('initialDefaults precarga valores en el form', async () => {
    setOptions()
    const wrapper = mount(ScannerOptionsDialog, {
      props: defaultProps({
        initialDefaults: { resolution: 600, mode: 'Gray', preview: true },
      }),
    })
    await flushPromises()
    const resSel = wrapper.find('[data-testid="opt-resolution"] select').element as HTMLSelectElement
    expect(resSel.value).toBe('600')
    const modeSel = wrapper.find('[data-testid="opt-mode"] select').element as HTMLSelectElement
    expect(modeSel.value).toBe('Gray')
    // Para checkbox hay que expandir primero (preview es avanzada).
    await wrapper.find('[data-testid="advanced-toggle"]').trigger('click')
    const cb = wrapper.find('[data-testid="opt-preview"] input[type="checkbox"]').element as HTMLInputElement
    expect(cb.checked).toBe(true)
  })

  it('submit emite los valores del form (overrides) y cierra', async () => {
    setOptions()
    const wrapper = mount(ScannerOptionsDialog, { props: defaultProps() })
    await flushPromises()

    await wrapper.find('[data-testid="opt-resolution"] select').setValue('600')
    await wrapper.find('[data-testid="opt-mode"] select').setValue('Gray')
    await wrapper.find('[data-testid="submit"]').trigger('click')

    const submits = wrapper.emitted('submit')
    expect(submits).toBeTruthy()
    const payload = submits![0][0] as Record<string, unknown>
    expect(payload.resolution).toBe(600)
    expect(payload.mode).toBe('Gray')
    // Valores no tocados también vienen (el backend filtra noops).
    expect(payload.source).toBe('Flatbed')
    expect(payload.brightness).toBe(0)
    // Inactivas/readonly no aparecen.
    expect(payload).not.toHaveProperty('inactive-opt')
    expect(payload).not.toHaveProperty('readonly-opt')
  })

  it('cancel emite close sin submit', async () => {
    setOptions()
    const wrapper = mount(ScannerOptionsDialog, { props: defaultProps() })
    await flushPromises()
    await wrapper.find('[data-testid="cancel"]').trigger('click')
    expect(wrapper.emitted('close')).toBeTruthy()
    expect(wrapper.emitted('submit')).toBeFalsy()
  })

  it('Escape cierra el dialog (listener global)', async () => {
    setOptions()
    const wrapper = mount(ScannerOptionsDialog, { props: defaultProps(), attachTo: document.body })
    await flushPromises()
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    expect(wrapper.emitted('close')).toBeTruthy()
    wrapper.unmount()
  })

  it('botón "Recordar para esta app" oculto si canSaveDefaults=false', async () => {
    setOptions()
    const wrapper = mount(ScannerOptionsDialog, { props: defaultProps({ canSaveDefaults: false }) })
    await flushPromises()
    expect(wrapper.find('[data-testid="save-defaults"]').exists()).toBe(false)
  })

  it('botón "Recordar para esta app" emite save-defaults con los valores actuales', async () => {
    setOptions()
    const wrapper = mount(ScannerOptionsDialog, { props: defaultProps({ canSaveDefaults: true }) })
    await flushPromises()
    await wrapper.find('[data-testid="opt-resolution"] select').setValue('150')
    await wrapper.find('[data-testid="save-defaults"]').trigger('click')
    const evts = wrapper.emitted('save-defaults')
    expect(evts).toBeTruthy()
    const payload = evts![0][0] as Record<string, unknown>
    expect(payload.resolution).toBe(150)
  })
})
