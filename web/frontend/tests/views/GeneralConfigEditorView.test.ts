import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createTestingPinia } from '@pinia/testing'
import GeneralConfigEditorView from '@/views/applications/GeneralConfigEditorView.vue'
import { useApplicationsStore } from '@/stores/applications'

vi.mock('@/components/AppHeader.vue', () => ({
  default: {
    name: 'AppHeader',
    props: ['appId', 'appName', 'description'],
    template: '<div data-test="stub-header"><slot name="actions" /></div>',
  },
}))

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/applications/:id/general', name: 'general', component: { template: '<div/>' } },
      { path: '/applications/:id', component: { template: '<div/>' } },
      { path: '/applications', component: { template: '<div/>' } },
    ],
  })
}

function makeApp(overrides: Record<string, unknown> = {}) {
  return {
    id: 5,
    name: 'TestApp',
    description: 'Desc de prueba',
    active: true,
    scanner_backend: 'sane',
    auto_transfer: false,
    close_after_transfer: false,
    background_color: '#aabbcc',
    pipeline_json: '[]',
    events_json: '{}',
    transfer_json: '{}',
    batch_fields_json: '[]',
    index_fields_json: '[]',
    output_format: 'tiff',
    default_tab: 'lote',
    image_config_json: '{}',
    ai_config_json: '{}',
    tenant_id: 1,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  }
}

async function mountView(appOverrides: Record<string, unknown> = {}) {
  const router = makeRouter()
  await router.push('/applications/5/general')
  await router.isReady()

  const pinia = createTestingPinia({ stubActions: false, createSpy: vi.fn })
  const store = useApplicationsStore(pinia)
  store.current = makeApp(appOverrides)
  ;(store.fetchOne as unknown as { mockResolvedValue: (v: unknown) => void }).mockResolvedValue(undefined)

  const wrapper = mount(GeneralConfigEditorView, {
    global: { plugins: [router, pinia] },
  })

  return { wrapper, store, router }
}

describe('GeneralConfigEditorView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('1. carga los campos existentes en el formulario', async () => {
    const { wrapper } = await mountView()
    await flushPromises()

    const name = wrapper.find<HTMLInputElement>('[data-test="field-name"]')
    const description = wrapper.find<HTMLTextAreaElement>('[data-test="field-description"]')
    const active = wrapper.find<HTMLInputElement>('[data-test="field-active"]')
    const scannerBackend = wrapper.find<HTMLSelectElement>('[data-test="field-scanner-backend"]')
    const bgColor = wrapper.find<HTMLInputElement>('[data-test="field-background-color"]')

    expect(name.element.value).toBe('TestApp')
    expect(description.element.value).toBe('Desc de prueba')
    expect(active.element.checked).toBe(true)
    expect(scannerBackend.element.value).toBe('sane')
    expect(bgColor.element.value).toBe('#aabbcc')
  })

  it('2. cambiar nombre activa hasChanges y habilita el botón guardar', async () => {
    const { wrapper } = await mountView()
    await flushPromises()

    const saveBtn = wrapper.find('[data-test="save-general"]')
    expect(saveBtn.attributes('disabled')).toBeDefined()

    const name = wrapper.find<HTMLInputElement>('[data-test="field-name"]')
    await name.setValue('NuevoNombre')
    await wrapper.vm.$nextTick()

    expect(saveBtn.attributes('disabled')).toBeUndefined()
  })

  it('3. cambiar el checkbox active activa hasChanges', async () => {
    const { wrapper } = await mountView()
    await flushPromises()

    const saveBtn = wrapper.find('[data-test="save-general"]')
    expect(saveBtn.attributes('disabled')).toBeDefined()

    const active = wrapper.find('[data-test="field-active"]')
    await active.setValue(false)
    await wrapper.vm.$nextTick()

    expect(saveBtn.attributes('disabled')).toBeUndefined()
  })

  it('4. cambiar scanner_backend activa hasChanges y muestra el texto informativo', async () => {
    const { wrapper } = await mountView({ scanner_backend: '' })
    await flushPromises()

    const select = wrapper.find('[data-test="field-scanner-backend"]')
    await select.setValue('twain')
    await wrapper.vm.$nextTick()

    const saveBtn = wrapper.find('[data-test="save-general"]')
    expect(saveBtn.attributes('disabled')).toBeUndefined()

    const note = wrapper.find('[data-test="scanner-backend-note"]')
    expect(note.exists()).toBe(true)
    expect(note.text()).toContain('agente local')
  })

  it('5. cambiar background_color activa hasChanges', async () => {
    const { wrapper } = await mountView()
    await flushPromises()

    const saveBtn = wrapper.find('[data-test="save-general"]')
    expect(saveBtn.attributes('disabled')).toBeDefined()

    const colorInput = wrapper.find('[data-test="field-background-color"]')
    await colorInput.setValue('#ff0000')
    await wrapper.vm.$nextTick()

    expect(saveBtn.attributes('disabled')).toBeUndefined()
  })

  it('6. save deshabilitado si nombre está vacío y muestra mensaje de error', async () => {
    const { wrapper } = await mountView()
    await flushPromises()

    const nameInput = wrapper.find('[data-test="field-name"]')
    await nameInput.setValue('')
    await wrapper.vm.$nextTick()

    const saveBtn = wrapper.find('[data-test="save-general"]')
    expect(saveBtn.attributes('disabled')).toBeDefined()

    const errorMsg = wrapper.find('[data-test="name-error"]')
    expect(errorMsg.exists()).toBe(true)
    expect(errorMsg.text()).toContain('obligatorio')
  })

  it('7. save llama a appStore.update con los 7 campos', async () => {
    const { wrapper, store } = await mountView()
    await flushPromises()

    ;(store.update as unknown as { mockResolvedValue: (v: unknown) => void }).mockResolvedValue(undefined)

    const nameInput = wrapper.find('[data-test="field-name"]')
    await nameInput.setValue('NombreActualizado')
    await wrapper.vm.$nextTick()

    await wrapper.find('[data-test="save-general"]').trigger('click')
    await flushPromises()

    expect(store.update).toHaveBeenCalledWith(
      5,
      expect.objectContaining({
        name: 'NombreActualizado',
        description: expect.any(String),
        active: expect.any(Boolean),
        scanner_backend: expect.any(String),
        auto_transfer: expect.any(Boolean),
        close_after_transfer: expect.any(Boolean),
        background_color: expect.any(String),
      }),
    )
  })

  it('8. tras guardar, hasChanges vuelve a false y el botón queda deshabilitado', async () => {
    const { wrapper, store } = await mountView()
    await flushPromises()

    ;(store.update as unknown as { mockResolvedValue: (v: unknown) => void }).mockResolvedValue(undefined)

    const nameInput = wrapper.find('[data-test="field-name"]')
    await nameInput.setValue('OtroNombre')
    await wrapper.vm.$nextTick()

    const saveBtn = wrapper.find('[data-test="save-general"]')
    expect(saveBtn.attributes('disabled')).toBeUndefined()

    await saveBtn.trigger('click')
    await flushPromises()

    expect(saveBtn.attributes('disabled')).toBeDefined()
  })

  it('9. beforeunload con cambios sin guardar llama preventDefault', async () => {
    const { wrapper } = await mountView()
    await flushPromises()

    const nameInput = wrapper.find('[data-test="field-name"]')
    await nameInput.setValue('CambioSinGuardar')
    await wrapper.vm.$nextTick()

    // Simular el evento beforeunload del navegador
    const event = new Event('beforeunload') as BeforeUnloadEvent & { returnValue: string }
    const preventDefaultSpy = vi.spyOn(event, 'preventDefault')
    window.dispatchEvent(event)

    expect(preventDefaultSpy).toHaveBeenCalled()

    wrapper.unmount()
  })

  it('10. combo scanner_backend muestra las 4 opciones esperadas', async () => {
    const { wrapper } = await mountView()
    await flushPromises()

    const options = wrapper.findAll('option[data-test^="scanner-option"]')
    expect(options).toHaveLength(4)

    const values = options.map((o) => (o.element as HTMLOptionElement).value)
    expect(values).toContain('')
    expect(values).toContain('sane')
    expect(values).toContain('twain')
    expect(values).toContain('wia')

    const labels = options.map((o) => o.text())
    expect(labels).toContain('Sin escáner')
    expect(labels).toContain('SANE (Linux)')
    expect(labels).toContain('TWAIN (Windows)')
    expect(labels).toContain('WIA (Windows)')
  })
})
