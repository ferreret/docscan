import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createTestingPinia } from '@pinia/testing'
import ImageConfigEditorView from '@/views/applications/ImageConfigEditorView.vue'
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
        path: '/applications/:id/image',
        name: 'image-config',
        component: { template: '<div/>' },
      },
      { path: '/applications/:id', component: { template: '<div/>' } },
      { path: '/applications', component: { template: '<div/>' } },
    ],
  })
}

const BASE_APP = {
  id: 7,
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
  ai_config_json: '{}',
  tenant_id: 1,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
}

async function mountView(imageConfigJson: string = '{}') {
  const router = makeRouter()
  await router.push('/applications/7/image')
  await router.isReady()

  const pinia = createTestingPinia({ stubActions: false, createSpy: vi.fn })
  const store = useApplicationsStore(pinia)

  store.current = { ...BASE_APP, image_config_json: imageConfigJson }
  ;(store.fetchOne as unknown as { mockResolvedValue: (v: unknown) => void }).mockResolvedValue(undefined)

  const wrapper = mount(ImageConfigEditorView, {
    global: { plugins: [router, pinia] },
  })

  return { wrapper, store, router }
}

describe('ImageConfigEditorView', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  // 1. Renderiza con valores por defecto si image_config_json está vacío
  it('renderiza con valores por defecto si image_config_json es {}', async () => {
    const { wrapper } = await mountView('{}')
    await flushPromises()

    const formatSelect = wrapper.find('[data-test="select-format"]')
    expect((formatSelect.element as HTMLSelectElement).value).toBe('tiff')

    const colorSelect = wrapper.find('[data-test="select-color-mode"]')
    expect((colorSelect.element as HTMLSelectElement).value).toBe('color')

    // Botón guardar deshabilitado (sin cambios)
    expect(wrapper.find('[data-test="save-image-config"]').attributes('disabled')).toBeDefined()
  })

  // 2. Carga valores existentes desde image_config_json
  it('carga valores existentes desde image_config_json', async () => {
    const config = JSON.stringify({
      format: 'jpg',
      color_mode: 'grayscale',
      jpeg_quality: 70,
    })
    const { wrapper } = await mountView(config)
    await flushPromises()

    expect((wrapper.find('[data-test="select-format"]').element as HTMLSelectElement).value).toBe('jpg')
    expect((wrapper.find('[data-test="select-color-mode"]').element as HTMLSelectElement).value).toBe('grayscale')
    expect((wrapper.find('[data-test="slider-jpeg-quality"]').element as HTMLInputElement).value).toBe('70')
  })

  // 3. Calidad JPEG visible cuando format=jpg, oculta cuando format=tiff
  it('muestra Calidad JPEG cuando format=jpg y la oculta cuando format=tiff', async () => {
    const { wrapper } = await mountView(JSON.stringify({ format: 'jpg' }))
    await flushPromises()

    expect(wrapper.find('[data-test="section-jpeg-quality"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="section-tiff-compression"]').exists()).toBe(false)

    await wrapper.find('[data-test="select-format"]').setValue('tiff')
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[data-test="section-jpeg-quality"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="section-tiff-compression"]').exists()).toBe(true)
  })

  // 4. Compresión TIFF visible cuando format=tiff, oculta cuando format=jpg
  it('muestra Compresión TIFF cuando format=tiff y la oculta cuando format=jpg', async () => {
    const { wrapper } = await mountView(JSON.stringify({ format: 'tiff' }))
    await flushPromises()

    expect(wrapper.find('[data-test="section-tiff-compression"]').exists()).toBe(true)

    await wrapper.find('[data-test="select-format"]').setValue('jpg')
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[data-test="section-tiff-compression"]').exists()).toBe(false)
  })

  // 5. Compresión PNG visible cuando format=png, oculta cuando format=tiff
  it('muestra Compresión PNG cuando format=png y la oculta cuando format=tiff', async () => {
    const { wrapper } = await mountView(JSON.stringify({ format: 'png' }))
    await flushPromises()

    expect(wrapper.find('[data-test="section-png-compression"]').exists()).toBe(true)

    await wrapper.find('[data-test="select-format"]').setValue('tiff')
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[data-test="section-png-compression"]').exists()).toBe(false)
  })

  // 6. Umbral B/N visible cuando color_mode=bw, oculto cuando color_mode=color
  it('muestra Umbral B/N cuando color_mode=bw y lo oculta cuando color_mode=color', async () => {
    const { wrapper } = await mountView(JSON.stringify({ color_mode: 'bw' }))
    await flushPromises()

    expect(wrapper.find('[data-test="section-bw-threshold"]').exists()).toBe(true)

    await wrapper.find('[data-test="select-color-mode"]').setValue('color')
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[data-test="section-bw-threshold"]').exists()).toBe(false)
  })

  // 7. hasChanges empieza false, se vuelve true al cambiar un campo
  it('hasChanges empieza false y se vuelve true al cambiar format', async () => {
    const { wrapper } = await mountView('{}')
    await flushPromises()

    expect(wrapper.find('[data-test="save-image-config"]').attributes('disabled')).toBeDefined()

    await wrapper.find('[data-test="select-format"]').setValue('jpg')
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[data-test="save-image-config"]').attributes('disabled')).toBeUndefined()
  })

  // 8. Al guardar, llama store.update con image_config_json serializado
  it('al guardar llama store.update con image_config_json serializado correctamente', async () => {
    const { wrapper, store } = await mountView('{}')
    await flushPromises()

    ;(store.update as unknown as { mockResolvedValue: (v: unknown) => void }).mockResolvedValue(undefined)

    await wrapper.find('[data-test="select-format"]').setValue('png')
    await wrapper.vm.$nextTick()

    await wrapper.find('[data-test="save-image-config"]').trigger('click')
    await flushPromises()

    expect(store.update).toHaveBeenCalledWith(
      7,
      expect.objectContaining({
        image_config_json: expect.stringContaining('"format":"png"'),
      }),
    )
  })

  // 9. Tras guardar, hasChanges vuelve a false
  it('tras guardar correctamente, hasChanges vuelve a false', async () => {
    const { wrapper, store } = await mountView('{}')
    await flushPromises()

    ;(store.update as unknown as { mockResolvedValue: (v: unknown) => void }).mockResolvedValue(undefined)

    await wrapper.find('[data-test="select-format"]').setValue('jpg')
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-test="save-image-config"]').attributes('disabled')).toBeUndefined()

    await wrapper.find('[data-test="save-image-config"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-test="save-image-config"]').attributes('disabled')).toBeDefined()
  })

  // 10. JSON malformado no rompe — usa defaults
  it('image_config_json malformado no rompe el componente y usa defaults', async () => {
    const { wrapper } = await mountView('NOT_VALID_JSON{{{')
    await flushPromises()

    expect(wrapper.find('[data-test="select-format"]').exists()).toBe(true)
    expect((wrapper.find('[data-test="select-format"]').element as HTMLSelectElement).value).toBe('tiff')
    expect((wrapper.find('[data-test="select-color-mode"]').element as HTMLSelectElement).value).toBe('color')
  })
})
