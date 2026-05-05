import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createTestingPinia } from '@pinia/testing'
import TransferEditorView from '@/views/applications/TransferEditorView.vue'
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
      {
        path: '/applications/:id/transfer',
        name: 'transfer',
        component: { template: '<div/>' },
      },
      { path: '/applications/:id', component: { template: '<div/>' } },
      { path: '/applications', component: { template: '<div/>' } },
    ],
  })
}

const BASE_APP = {
  id: 9,
  name: 'TestApp',
  description: '',
  active: true,
  pipeline_json: '[]',
  events_json: '{}',
  transfer_json: '{}',
  batch_fields_json: '[]',
  index_fields_json: '[]',
  auto_transfer: false,
  close_after_transfer: false,
  background_color: '',
  output_format: 'tiff',
  default_tab: 'lote',
  scanner_backend: '',
  image_config_json: '{}',
  ai_config_json: '{}',
  tenant_id: 1,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
}

async function mountView(transferJson: string = '{}') {
  const router = makeRouter()
  await router.push('/applications/9/transfer')
  await router.isReady()

  const pinia = createTestingPinia({ stubActions: false, createSpy: vi.fn })
  const store = useApplicationsStore(pinia)

  store.current = { ...BASE_APP, transfer_json: transferJson }
  ;(store.fetchOne as unknown as { mockResolvedValue: (v: unknown) => void }).mockResolvedValue(undefined)

  const wrapper = mount(TransferEditorView, {
    global: { plugins: [router, pinia] },
  })

  return { wrapper, store, router }
}

describe('TransferEditorView', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  // 1. Renderiza form con defaults si transfer_json vacío
  it('1. renderiza con valores por defecto si transfer_json es {}', async () => {
    const { wrapper } = await mountView('{}')
    await flushPromises()

    const modeSelect = wrapper.find<HTMLSelectElement>('[data-test="field-mode"]')
    expect(modeSelect.element.value).toBe('folder')

    const standardEnabled = wrapper.find<HTMLInputElement>('[data-test="field-standard-enabled"]')
    expect(standardEnabled.element.checked).toBe(true)

    const destination = wrapper.find<HTMLInputElement>('[data-test="field-destination"]')
    expect(destination.element.value).toBe('')

    // Botón guardar deshabilitado: destination vacío bloquea
    expect(wrapper.find('[data-test="save-transfer"]').attributes('disabled')).toBeDefined()
  })

  // 2. Carga config existente desde transfer_json
  it('2. carga config existente desde transfer_json', async () => {
    const config = JSON.stringify({
      mode: 'pdf',
      destination: '/tmp/salida',
      filename_pattern: '{batch_id}',
      standard_enabled: false,
      pdf_dpi: 300,
    })
    const { wrapper } = await mountView(config)
    await flushPromises()

    const modeSelect = wrapper.find<HTMLSelectElement>('[data-test="field-mode"]')
    expect(modeSelect.element.value).toBe('pdf')

    const dest = wrapper.find<HTMLInputElement>('[data-test="field-destination"]')
    expect(dest.element.value).toBe('/tmp/salida')

    const stdEnabled = wrapper.find<HTMLInputElement>('[data-test="field-standard-enabled"]')
    expect(stdEnabled.element.checked).toBe(false)
  })

  // 3. Mostrar campos folder cuando mode=folder
  it('3. muestra campos folder cuando mode=folder', async () => {
    const { wrapper } = await mountView(JSON.stringify({ mode: 'folder', destination: '/tmp' }))
    await flushPromises()

    expect(wrapper.find('[data-test="section-output-format"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="section-output-dpi"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="section-create-subdirs"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="section-include-metadata"]').exists()).toBe(true)

    // NO debe mostrar campos de PDF ni CSV
    expect(wrapper.find('[data-test="section-pdf-dpi"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="section-csv-separator"]').exists()).toBe(false)
  })

  // 4. Mostrar campos pdf cuando mode=pdf, ocultar folder-specific
  it('4. muestra campos pdf cuando mode=pdf y oculta folder-específicos', async () => {
    const { wrapper } = await mountView(JSON.stringify({ mode: 'pdf', destination: '/tmp' }))
    await flushPromises()

    expect(wrapper.find('[data-test="section-pdf-dpi"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="section-pdf-color-mode"]').exists()).toBe(true)

    // Campos solo de folder no visibles
    expect(wrapper.find('[data-test="section-output-format"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="section-create-subdirs"]').exists()).toBe(false)

    // CSV tampoco
    expect(wrapper.find('[data-test="section-csv-separator"]').exists()).toBe(false)
  })

  // 5. Mostrar campos csv cuando mode=csv
  it('5. muestra campos csv cuando mode=csv (separator + lista de fields)', async () => {
    const { wrapper } = await mountView(JSON.stringify({ mode: 'csv', destination: '/tmp' }))
    await flushPromises()

    expect(wrapper.find('[data-test="section-csv-separator"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="section-csv-fields"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="csv-field-input"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="csv-field-add"]').exists()).toBe(true)

    // Campos solo de folder o pdf no visibles
    expect(wrapper.find('[data-test="section-output-format"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="section-pdf-dpi"]').exists()).toBe(false)
  })

  // 6. JPEG quality solo visible si mode=folder Y output_format=jpg
  it('6. JPEG quality visible solo si mode=folder y output_format=jpg', async () => {
    const { wrapper } = await mountView(JSON.stringify({ mode: 'folder', destination: '/tmp', output_format: 'tiff' }))
    await flushPromises()

    // Con tiff: sin calidad JPEG
    expect(wrapper.find('[data-test="section-jpeg-quality"]').exists()).toBe(false)

    // Cambiar a jpg
    await wrapper.find('[data-test="field-output-format"]').setValue('jpg')
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[data-test="section-jpeg-quality"]').exists()).toBe(true)
  })

  // 7. Checkbox standard_enabled atenúa el form cuando false
  it('7. checkbox standard_enabled atenúa el form-body cuando está desactivado', async () => {
    const { wrapper } = await mountView('{}')
    await flushPromises()

    const body = wrapper.find('[data-test="transfer-form-body"]')
    expect(body.classes()).not.toContain('opacity-50')

    const checkbox = wrapper.find('[data-test="field-standard-enabled"]')
    await checkbox.setValue(false)
    await wrapper.vm.$nextTick()

    expect(body.classes()).toContain('opacity-50')
  })

  // 8. csv_fields: añadir y eliminar elementos de la lista
  it('8. csv_fields: añadir y eliminar campos de la lista', async () => {
    const { wrapper } = await mountView(JSON.stringify({ mode: 'csv', destination: '/tmp' }))
    await flushPromises()

    const input = wrapper.find('[data-test="csv-field-input"]')
    const addBtn = wrapper.find('[data-test="csv-field-add"]')

    // Añadir campo "nif"
    await input.setValue('nif')
    await addBtn.trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[data-test="csv-field-remove-0"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('nif')

    // Añadir campo "nombre"
    await input.setValue('nombre')
    await addBtn.trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[data-test="csv-field-remove-1"]').exists()).toBe(true)

    // Eliminar primer campo
    await wrapper.find('[data-test="csv-field-remove-0"]').trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[data-test="csv-field-remove-0"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('nombre')
    // nif ya no está como primer elemento
    expect(wrapper.find('[data-test="csv-field-remove-1"]').exists()).toBe(false)
  })

  // 9. hasChanges empieza false, se vuelve true al cambiar cualquier campo
  it('9. hasChanges empieza false (save deshabilitado) y se vuelve true al cambiar un campo', async () => {
    const { wrapper } = await mountView(JSON.stringify({ mode: 'folder', destination: '/tmp/salida' }))
    await flushPromises()

    const saveBtn = wrapper.find('[data-test="save-transfer"]')
    // Sin cambios → save deshabilitado aunque destination sea válida
    expect(saveBtn.attributes('disabled')).toBeDefined()

    // Cambiar mode → hasChanges=true → save habilitado (destination válida)
    await wrapper.find('[data-test="field-mode"]').setValue('pdf')
    await wrapper.vm.$nextTick()

    expect(saveBtn.attributes('disabled')).toBeUndefined()

    // Indicador "sin guardar" aparece
    expect(wrapper.find('span.text-warning').exists()).toBe(true)
  })

  // Verificar que hasChanges funciona correctamente con estado inicial
  it('9b. hasChanges=false al arrancar sin modificaciones', async () => {
    const { wrapper } = await mountView('{}')
    await flushPromises()

    // Sin destination → save bloqueado por validación, no por hasChanges
    const saveBtn = wrapper.find('[data-test="save-transfer"]')
    // Comprobamos que el indicador "sin guardar" NO aparece
    expect(wrapper.find('span.text-warning').exists()).toBe(false)
  })

  // 10. Save serializa correctamente y llama appStore.update
  it('10. save serializa correctamente y llama appStore.update con transfer_json', async () => {
    const { wrapper, store } = await mountView(JSON.stringify({ mode: 'folder', destination: '/tmp' }))
    await flushPromises()

    ;(store.update as unknown as { mockResolvedValue: (v: unknown) => void }).mockResolvedValue(undefined)

    // Cambiar pdf_dpi-related: cambiar modo a pdf para forzar hasChanges
    await wrapper.find('[data-test="field-mode"]').setValue('pdf')
    await wrapper.vm.$nextTick()

    await wrapper.find('[data-test="save-transfer"]').trigger('click')
    await flushPromises()

    expect(store.update).toHaveBeenCalledWith(
      9,
      expect.objectContaining({
        transfer_json: expect.stringContaining('"mode":"pdf"'),
      }),
    )

    const callArg = (store.update as ReturnType<typeof vi.fn>).mock.calls[0][1]
    const parsed = JSON.parse(callArg.transfer_json)
    expect(parsed).toMatchObject({ mode: 'pdf', destination: '/tmp' })
  })

  // 11. Tras guardar, hasChanges vuelve a false
  it('11. tras guardar, hasChanges vuelve a false', async () => {
    const { wrapper, store } = await mountView(JSON.stringify({ mode: 'folder', destination: '/tmp' }))
    await flushPromises()

    ;(store.update as unknown as { mockResolvedValue: (v: unknown) => void }).mockResolvedValue(undefined)

    await wrapper.find('[data-test="field-mode"]').setValue('csv')
    await wrapper.vm.$nextTick()

    expect(wrapper.find('span.text-warning').exists()).toBe(true)

    await wrapper.find('[data-test="save-transfer"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('span.text-warning').exists()).toBe(false)
  })

  // 12. JSON malformado no rompe — usa defaults
  it('12. JSON malformado en transfer_json no rompe y usa defaults', async () => {
    const { wrapper } = await mountView('NOT_VALID_JSON{{{')
    await flushPromises()

    // El componente debe renderizarse con defaults
    const modeSelect = wrapper.find('[data-test="field-mode"]')
    expect(modeSelect.exists()).toBe(true)
    expect(modeSelect.element.value).toBe('folder')

    const stdEnabled = wrapper.find<HTMLInputElement>('[data-test="field-standard-enabled"]')
    expect(stdEnabled.element.checked).toBe(true)
  })

  // 13. Validación: destination vacío bloquea save y muestra mensaje
  it('13. destination vacío bloquea save y muestra mensaje de error', async () => {
    const { wrapper } = await mountView('{}')
    await flushPromises()

    const destInput = wrapper.find('[data-test="field-destination"]')
    expect(destInput.element.value).toBe('')

    const saveBtn = wrapper.find('[data-test="save-transfer"]')
    expect(saveBtn.attributes('disabled')).toBeDefined()

    const errorMsg = wrapper.find('[data-test="destination-error"]')
    expect(errorMsg.exists()).toBe(true)
    expect(errorMsg.text()).toContain('obligatorio')
  })

  // 14. Botón deshacer restaura estado original
  it('14. deshacer restaura el estado original de la config', async () => {
    const { wrapper } = await mountView(JSON.stringify({ mode: 'folder', destination: '/tmp/original' }))
    await flushPromises()

    // Cambiar modo
    await wrapper.find('[data-test="field-mode"]').setValue('csv')
    await wrapper.vm.$nextTick()

    expect(wrapper.find<HTMLSelectElement>('[data-test="field-mode"]').element.value).toBe('csv')

    // Deshacer
    await wrapper.find('[data-test="undo-transfer"]').trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.find<HTMLSelectElement>('[data-test="field-mode"]').element.value).toBe('folder')
  })

  // 15. csv_fields cargados desde JSON se muestran en la lista
  it('15. csv_fields cargados desde transfer_json aparecen en la lista', async () => {
    const config = JSON.stringify({
      mode: 'csv',
      destination: '/tmp',
      csv_fields: ['nif', 'nombre', 'fecha'],
    })
    const { wrapper } = await mountView(config)
    await flushPromises()

    expect(wrapper.find('[data-test="csv-field-remove-0"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="csv-field-remove-1"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="csv-field-remove-2"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('nif')
    expect(wrapper.text()).toContain('nombre')
    expect(wrapper.text()).toContain('fecha')
  })

  // 16. Añadir csv_field duplicado no lo inserta de nuevo
  it('16. añadir campo csv duplicado no lo inserta', async () => {
    const config = JSON.stringify({ mode: 'csv', destination: '/tmp', csv_fields: ['nif'] })
    const { wrapper } = await mountView(config)
    await flushPromises()

    const input = wrapper.find('[data-test="csv-field-input"]')
    await input.setValue('nif')
    await wrapper.find('[data-test="csv-field-add"]').trigger('click')
    await wrapper.vm.$nextTick()

    // Solo debe aparecer 1 campo "nif"
    expect(wrapper.find('[data-test="csv-field-remove-1"]').exists()).toBe(false)
  })
})
