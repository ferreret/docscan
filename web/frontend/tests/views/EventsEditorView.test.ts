import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createTestingPinia } from '@pinia/testing'
import EventsEditorView from '@/views/applications/EventsEditorView.vue'
import { useApplicationsStore } from '@/stores/applications'
import { EVENT_DEFINITIONS } from '@/api/events-catalog'

let latestUpdateModelValue: ((doc: string) => void) | null = null

vi.mock('@/components/CodeEditor.vue', () => ({
  default: {
    name: 'CodeEditor',
    props: ['modelValue', 'contextVariables', 'snippets', 'minHeight', 'helpPanelStorageKey'],
    emits: ['update:modelValue'],
    setup(_: unknown, ctx: { emit: (name: string, ...args: unknown[]) => void }) {
      latestUpdateModelValue = (doc: string) => ctx.emit('update:modelValue', doc)
      return {}
    },
    template: '<div data-test="stub-code-editor">{{ modelValue }}</div>',
  },
}))

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
      { path: '/applications/:id/events', name: 'events', component: { template: '<div/>' } },
      { path: '/applications/:id', component: { template: '<div/>' } },
      { path: '/applications', component: { template: '<div/>' } },
    ],
  })
}

async function mountView(eventsJson: string = '{}') {
  const router = makeRouter()
  await router.push('/applications/8/events')
  await router.isReady()

  const pinia = createTestingPinia({ stubActions: false, createSpy: vi.fn })

  const store = useApplicationsStore(pinia)
  store.current = {
    id: 8, name: 'Demo', description: '', active: true,
    pipeline_json: '[]', events_json: eventsJson, transfer_json: '{}',
    batch_fields_json: '[]', index_fields_json: '[]',
    auto_transfer: false, close_after_transfer: false,
    background_color: '', output_format: 'tiff', default_tab: 'lote',
    scanner_backend: '', image_config_json: '{}', ai_config_json: '{}',
    tenant_id: 1, created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
  }
  ;(store.fetchOne as unknown as { mockResolvedValue: (v: unknown) => void }).mockResolvedValue(undefined)

  const wrapper = mount(EventsEditorView, {
    global: {
      plugins: [router, pinia],
    },
  })

  return { wrapper, store, router }
}

describe('EventsEditorView', () => {
  beforeEach(() => {
    latestUpdateModelValue = null
    localStorage.clear()
  })

  it('fetch inicial carga events_json y selecciona on_scan_complete por defecto', async () => {
    const { wrapper, store } = await mountView(JSON.stringify({
      on_scan_complete: 'log.info("done")\n',
    }))
    await flushPromises()
    expect(store.fetchOne).toHaveBeenCalledWith(8)

    const items = wrapper.findAll('[data-test="event-item"]')
    expect(items).toHaveLength(1)
    expect(items[0].classes().join(' ')).toContain('text-primary')
    expect(items[0].text()).toContain('on_scan_complete')
  })

  it('sidebar marca con indicador los eventos con código', async () => {
    const { wrapper } = await mountView(JSON.stringify({
      on_scan_complete: 'log.info("done")\n',
    }))
    await flushPromises()
    const active = wrapper.findAll('[data-test="event-indicator-active"]')
    const activeNames = active.map((a) => a.attributes('data-event'))
    expect(activeNames).toEqual(['on_scan_complete'])
  })

  it('el único evento seleccionado muestra su código en el editor', async () => {
    const { wrapper } = await mountView(JSON.stringify({
      on_scan_complete: 'log.info("done")\n',
    }))
    await flushPromises()

    const editor = wrapper.find('[data-test="stub-code-editor"]')
    expect(editor.text()).toContain('log.info("done")')
  })

  it('seleccionar evento sin código muestra su template sin ensuciar hasChanges', async () => {
    const { wrapper } = await mountView('{}')
    await flushPromises()

    const editor = wrapper.find('[data-test="stub-code-editor"]')
    expect(editor.text()).toContain('def on_scan_complete(app, batch):')

    const saveBtn = wrapper.find('[data-test="save-events"]')
    expect(saveBtn.attributes('disabled')).toBeDefined()
  })

  it('editar en el editor actualiza el estado y habilita Guardar', async () => {
    const { wrapper } = await mountView('{}')
    await flushPromises()

    expect(latestUpdateModelValue).toBeTypeOf('function')
    latestUpdateModelValue!('log.info("hola")\n')
    await wrapper.vm.$nextTick()

    const saveBtn = wrapper.find('[data-test="save-events"]')
    expect(saveBtn.attributes('disabled')).toBeUndefined()
  })

  it('Guardar cambios llama a store.update con events_json stringified y resetea hasChanges', async () => {
    const { wrapper, store } = await mountView('{}')
    await flushPromises()

    latestUpdateModelValue!('log.info("hola")\n')
    await wrapper.vm.$nextTick()

    ;(store.update as unknown as { mockResolvedValue: (v: unknown) => void }).mockResolvedValue(undefined)

    await wrapper.find('[data-test="save-events"]').trigger('click')
    await flushPromises()

    expect(store.update).toHaveBeenCalledWith(8, expect.objectContaining({
      events_json: expect.stringContaining('on_scan_complete'),
    }))

    expect(wrapper.find('[data-test="save-events"]').attributes('disabled')).toBeDefined()
  })

  it('Deshacer restaura events al snapshot original', async () => {
    const { wrapper } = await mountView(JSON.stringify({
      on_scan_complete: 'log.info("done")\n',
    }))
    await flushPromises()

    latestUpdateModelValue!('log.info("modificado")\n')
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-test="save-events"]').attributes('disabled')).toBeUndefined()

    await wrapper.find('[data-test="undo-events"]').trigger('click')
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-test="save-events"]').attributes('disabled')).toBeDefined()
  })

  it('la sidebar lista el único evento del catálogo', async () => {
    const { wrapper } = await mountView('{}')
    await flushPromises()
    const items = wrapper.findAll('[data-test="event-item"]')
    expect(items).toHaveLength(1)
    expect(items[0].text()).toContain(EVENT_DEFINITIONS[0].name)
  })
})
