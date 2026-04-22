import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createTestingPinia } from '@pinia/testing'
import BatchFieldsEditorView from '@/views/applications/BatchFieldsEditorView.vue'
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
        path: '/applications/:id/batch-fields',
        name: 'batch-fields',
        component: { template: '<div/>' },
      },
      { path: '/applications/:id', component: { template: '<div/>' } },
      { path: '/applications', component: { template: '<div/>' } },
    ],
  })
}

function makeApp(batchFieldsJson = '[]') {
  return {
    id: 5,
    name: 'Test App',
    description: '',
    active: true,
    pipeline_json: '[]',
    events_json: '{}',
    transfer_json: '{}',
    batch_fields_json: batchFieldsJson,
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
}

async function mountView(batchFieldsJson = '[]') {
  const router = makeRouter()
  await router.push('/applications/5/batch-fields')
  await router.isReady()

  const pinia = createTestingPinia({ stubActions: false, createSpy: vi.fn })
  const store = useApplicationsStore(pinia)
  store.current = makeApp(batchFieldsJson)
  ;(store.fetchOne as unknown as { mockResolvedValue: (v: unknown) => void }).mockResolvedValue(
    undefined,
  )

  const wrapper = mount(BatchFieldsEditorView, {
    global: { plugins: [router, pinia] },
  })

  return { wrapper, store, router }
}

describe('BatchFieldsEditorView', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  // 1. Renderiza empty state si batch_fields_json está vacío
  it('renderiza empty state si batch_fields_json es []', async () => {
    const { wrapper } = await mountView('[]')
    await flushPromises()
    expect(wrapper.find('[data-test="empty-state"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="field-row"]').exists()).toBe(false)
  })

  // 2. Carga campos existentes y los renderiza en tabla
  it('carga campos existentes y los renderiza en tabla', async () => {
    const fields = [
      { label: 'Referencia', type: 'texto', required: false, config: {} },
      { label: 'Fecha entrada', type: 'fecha', required: true, config: { format: 'dd/MM/yyyy' } },
    ]
    const { wrapper } = await mountView(JSON.stringify(fields))
    await flushPromises()
    const rows = wrapper.findAll('[data-test="field-row"]')
    expect(rows).toHaveLength(2)
    expect(wrapper.find('[data-test="empty-state"]').exists()).toBe(false)
    const labels = wrapper.findAll('[data-test="field-label"]')
    expect((labels[0].element as HTMLInputElement).value).toBe('Referencia')
    expect((labels[1].element as HTMLInputElement).value).toBe('Fecha entrada')
  })

  // 3. "+ Añadir campo" agrega fila nueva con tipo=texto por defecto
  it('añadir campo agrega una fila con tipo texto por defecto', async () => {
    const { wrapper } = await mountView('[]')
    await flushPromises()
    await wrapper.find('[data-test="add-field"]').trigger('click')
    await wrapper.vm.$nextTick()
    const rows = wrapper.findAll('[data-test="field-row"]')
    expect(rows).toHaveLength(1)
    const typeSelect = wrapper.find('[data-test="field-type"]')
    expect((typeSelect.element as HTMLSelectElement).value).toBe('texto')
    expect(wrapper.find('[data-test="empty-state"]').exists()).toBe(false)
  })

  // 4. Botón ↑ mueve campo arriba; botón ↓ lo mueve abajo
  it('botón ↑ mueve el campo arriba', async () => {
    const fields = [
      { label: 'Primero', type: 'texto', required: false, config: {} },
      { label: 'Segundo', type: 'texto', required: false, config: {} },
    ]
    const { wrapper } = await mountView(JSON.stringify(fields))
    await flushPromises()
    // Clic en ↑ de la segunda fila (índice 1)
    const upBtns = wrapper.findAll('[data-test="move-up"]')
    await upBtns[1].trigger('click')
    await wrapper.vm.$nextTick()
    const labels = wrapper.findAll('[data-test="field-label"]')
    expect((labels[0].element as HTMLInputElement).value).toBe('Segundo')
    expect((labels[1].element as HTMLInputElement).value).toBe('Primero')
  })

  it('botón ↓ mueve el campo abajo', async () => {
    const fields = [
      { label: 'Primero', type: 'texto', required: false, config: {} },
      { label: 'Segundo', type: 'texto', required: false, config: {} },
    ]
    const { wrapper } = await mountView(JSON.stringify(fields))
    await flushPromises()
    // Clic en ↓ de la primera fila (índice 0)
    const downBtns = wrapper.findAll('[data-test="move-down"]')
    await downBtns[0].trigger('click')
    await wrapper.vm.$nextTick()
    const labels = wrapper.findAll('[data-test="field-label"]')
    expect((labels[0].element as HTMLInputElement).value).toBe('Segundo')
    expect((labels[1].element as HTMLInputElement).value).toBe('Primero')
  })

  // 5. Botón ↑ deshabilitado en primera fila; ↓ deshabilitado en última
  it('botón ↑ deshabilitado en primera fila y ↓ deshabilitado en última', async () => {
    const fields = [
      { label: 'A', type: 'texto', required: false, config: {} },
      { label: 'B', type: 'texto', required: false, config: {} },
    ]
    const { wrapper } = await mountView(JSON.stringify(fields))
    await flushPromises()
    const upBtns = wrapper.findAll('[data-test="move-up"]')
    const downBtns = wrapper.findAll('[data-test="move-down"]')
    expect(upBtns[0].attributes('disabled')).toBeDefined()
    expect(upBtns[1].attributes('disabled')).toBeUndefined()
    expect(downBtns[0].attributes('disabled')).toBeUndefined()
    expect(downBtns[1].attributes('disabled')).toBeDefined()
  })

  // 6. Botón ✕ elimina el campo
  it('botón ✕ elimina el campo', async () => {
    const fields = [
      { label: 'Campo A', type: 'texto', required: false, config: {} },
      { label: 'Campo B', type: 'texto', required: false, config: {} },
    ]
    const { wrapper } = await mountView(JSON.stringify(fields))
    await flushPromises()
    const removeBtns = wrapper.findAll('[data-test="remove-field"]')
    await removeBtns[0].trigger('click')
    await wrapper.vm.$nextTick()
    const rows = wrapper.findAll('[data-test="field-row"]')
    expect(rows).toHaveLength(1)
    const label = wrapper.find('[data-test="field-label"]')
    expect((label.element as HTMLInputElement).value).toBe('Campo B')
  })

  // 7. Cambiar tipo a "lista" muestra input para valores; "numerico" muestra min/max/step
  it('cambiar tipo a lista muestra input de valores', async () => {
    const { wrapper } = await mountView('[]')
    await flushPromises()
    await wrapper.find('[data-test="add-field"]').trigger('click')
    await wrapper.vm.$nextTick()
    const typeSelect = wrapper.find('[data-test="field-type"]')
    await typeSelect.setValue('lista')
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-test="field-list-values"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="field-num-min"]').exists()).toBe(false)
  })

  it('cambiar tipo a numerico muestra inputs min/max/step', async () => {
    const { wrapper } = await mountView('[]')
    await flushPromises()
    await wrapper.find('[data-test="add-field"]').trigger('click')
    await wrapper.vm.$nextTick()
    const typeSelect = wrapper.find('[data-test="field-type"]')
    await typeSelect.setValue('numerico')
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-test="field-num-min"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="field-num-max"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="field-num-step"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="field-list-values"]').exists()).toBe(false)
  })

  // 8. hasChanges empieza false, true al modificar/añadir/borrar/reordenar
  it('hasChanges empieza false y se activa al añadir un campo', async () => {
    const { wrapper } = await mountView('[]')
    await flushPromises()
    expect(wrapper.find('[data-test="save-fields"]').attributes('disabled')).toBeDefined()
    await wrapper.find('[data-test="add-field"]').trigger('click')
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-test="save-fields"]').attributes('disabled')).toBeUndefined()
  })

  it('hasChanges se activa al modificar la etiqueta de un campo', async () => {
    const fields = [{ label: 'Original', type: 'texto', required: false, config: {} }]
    const { wrapper } = await mountView(JSON.stringify(fields))
    await flushPromises()
    expect(wrapper.find('[data-test="save-fields"]').attributes('disabled')).toBeDefined()
    const labelInput = wrapper.find('[data-test="field-label"]')
    await labelInput.setValue('Modificado')
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-test="save-fields"]').attributes('disabled')).toBeUndefined()
  })

  it('hasChanges se activa al eliminar un campo', async () => {
    const fields = [{ label: 'A', type: 'texto', required: false, config: {} }]
    const { wrapper } = await mountView(JSON.stringify(fields))
    await flushPromises()
    expect(wrapper.find('[data-test="save-fields"]').attributes('disabled')).toBeDefined()
    await wrapper.find('[data-test="remove-field"]').trigger('click')
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-test="save-fields"]').attributes('disabled')).toBeUndefined()
  })

  it('hasChanges se activa al reordenar campos', async () => {
    const fields = [
      { label: 'A', type: 'texto', required: false, config: {} },
      { label: 'B', type: 'texto', required: false, config: {} },
    ]
    const { wrapper } = await mountView(JSON.stringify(fields))
    await flushPromises()
    expect(wrapper.find('[data-test="save-fields"]').attributes('disabled')).toBeDefined()
    const downBtns = wrapper.findAll('[data-test="move-down"]')
    await downBtns[0].trigger('click')
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-test="save-fields"]').attributes('disabled')).toBeUndefined()
  })

  // 9. Save bloqueado si hay un label vacío (con mensaje de error visible)
  it('save muestra error si hay un campo sin etiqueta', async () => {
    const { wrapper } = await mountView('[]')
    await flushPromises()
    await wrapper.find('[data-test="add-field"]').trigger('click')
    await wrapper.vm.$nextTick()
    // label está vacío por defecto → save habilitado por hasChanges pero debe mostrar error
    await wrapper.find('[data-test="save-fields"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-test="save-error"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="save-error"]').text()).toContain('etiqueta')
  })

  // 10. Save serializa correctamente y llama appStore.update
  it('save serializa y llama appStore.update con batch_fields_json', async () => {
    const { wrapper, store } = await mountView('[]')
    await flushPromises()
    await wrapper.find('[data-test="add-field"]').trigger('click')
    await wrapper.vm.$nextTick()
    const labelInput = wrapper.find('[data-test="field-label"]')
    await labelInput.setValue('Mi campo')
    await wrapper.vm.$nextTick()
    ;(store.update as unknown as { mockResolvedValue: (v: unknown) => void }).mockResolvedValue(
      undefined,
    )
    await wrapper.find('[data-test="save-fields"]').trigger('click')
    await flushPromises()
    expect(store.update).toHaveBeenCalledWith(
      5,
      expect.objectContaining({
        batch_fields_json: expect.stringContaining('Mi campo'),
      }),
    )
  })

  // 11. Tras guardar, hasChanges vuelve a false
  it('tras guardar, hasChanges vuelve a false', async () => {
    const { wrapper, store } = await mountView('[]')
    await flushPromises()
    await wrapper.find('[data-test="add-field"]').trigger('click')
    await wrapper.vm.$nextTick()
    const labelInput = wrapper.find('[data-test="field-label"]')
    await labelInput.setValue('Campo guardado')
    await wrapper.vm.$nextTick()
    store.current = makeApp(
      JSON.stringify([{ label: 'Campo guardado', type: 'texto', required: false, config: {} }]),
    )
    ;(store.update as unknown as { mockResolvedValue: (v: unknown) => void }).mockResolvedValue(
      undefined,
    )
    await wrapper.find('[data-test="save-fields"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-test="save-fields"]').attributes('disabled')).toBeDefined()
  })

  // 12. JSON malformado no rompe — usa []
  it('JSON malformado en batch_fields_json no rompe y usa []', async () => {
    const { wrapper } = await mountView('INVALID_JSON{{{')
    await flushPromises()
    expect(wrapper.find('[data-test="empty-state"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="field-row"]').exists()).toBe(false)
  })

  // Fetch inicial llama a store.fetchOne
  it('fetch inicial llama a store.fetchOne con el id correcto', async () => {
    const { store } = await mountView('[]')
    await flushPromises()
    expect(store.fetchOne).toHaveBeenCalledWith(5)
  })

  // Deshacer restaura al snapshot original
  it('deshacer restaura el estado original', async () => {
    const fields = [{ label: 'Original', type: 'texto', required: false, config: {} }]
    const { wrapper } = await mountView(JSON.stringify(fields))
    await flushPromises()
    const labelInput = wrapper.find('[data-test="field-label"]')
    await labelInput.setValue('Modificado')
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-test="save-fields"]').attributes('disabled')).toBeUndefined()
    await wrapper.find('[data-test="undo-fields"]').trigger('click')
    await wrapper.vm.$nextTick()
    expect((wrapper.find('[data-test="field-label"]').element as HTMLInputElement).value).toBe(
      'Original',
    )
    expect(wrapper.find('[data-test="save-fields"]').attributes('disabled')).toBeDefined()
  })
})
