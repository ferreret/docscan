import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import WorkbenchToolbar from '@/components/workbench/WorkbenchToolbar.vue'
import type { BatchResponse } from '@/api/types'

// Hito 10: WorkbenchToolbar incluye ScanFromAgentMenu, que usa el
// agent store. Sin Pinia, el mount lanza "no active Pinia".
beforeEach(() => {
  setActivePinia(createPinia())
})

function makeBatch(overrides: Partial<BatchResponse> = {}): BatchResponse {
  return {
    id: 1, application_id: 1, state: 'pending', page_count: 0,
    created_at: '', updated_at: '', fields_json: '{}', folder_path: '', hostname: '',
    ...overrides,
  }
}

function makeRouter() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/batches', component: { template: '<div/>' } }],
  })
  router.push('/batches')
  return router
}

describe('WorkbenchToolbar', () => {
  it('renders 5 action buttons and the title', async () => {
    const router = makeRouter(); await router.isReady()
    const wrapper = mount(WorkbenchToolbar, {
      props: { batch: makeBatch(), running: false, transferring: false, uploading: false },
      global: { plugins: [router] },
    })
    expect(wrapper.text()).toContain('Lote #1')
    // 4 buttons + back button + 1 file label (not a button)
    expect(wrapper.findAll('button').length).toBeGreaterThanOrEqual(4)
  })

  it('disables Pipeline when page_count is 0', async () => {
    const router = makeRouter(); await router.isReady()
    const wrapper = mount(WorkbenchToolbar, {
      props: { batch: makeBatch({ page_count: 0 }), running: false, transferring: false, uploading: false },
      global: { plugins: [router] },
    })
    const pipelineBtn = wrapper.findAll('button').find((b) => b.text().includes('Pipeline'))!
    expect((pipelineBtn.element as HTMLButtonElement).disabled).toBe(true)
  })

  it('disables Transferir unless batch.state === "read"', async () => {
    const router = makeRouter(); await router.isReady()
    const wrapper = mount(WorkbenchToolbar, {
      props: { batch: makeBatch({ state: 'pending' }), running: false, transferring: false, uploading: false },
      global: { plugins: [router] },
    })
    const transferBtn = wrapper.findAll('button').find((b) => b.text().includes('Transferir'))!
    expect((transferBtn.element as HTMLButtonElement).disabled).toBe(true)
  })

  it('emits "run-pipeline" when Pipeline clicked', async () => {
    const router = makeRouter(); await router.isReady()
    const wrapper = mount(WorkbenchToolbar, {
      props: { batch: makeBatch({ page_count: 3 }), running: false, transferring: false, uploading: false },
      global: { plugins: [router] },
    })
    const pipelineBtn = wrapper.findAll('button').find((b) => b.text().includes('Pipeline'))!
    await pipelineBtn.trigger('click')
    expect(wrapper.emitted('run-pipeline')).toHaveLength(1)
  })

  it('ZIP en estado idle muestra "↓ ZIP" y está habilitado', async () => {
    const router = makeRouter(); await router.isReady()
    const wrapper = mount(WorkbenchToolbar, {
      props: { batch: makeBatch(), running: false, transferring: false, uploading: false },
      global: { plugins: [router] },
    })
    const zipBtn = wrapper.find('[data-testid="btn-zip"]')
    expect(zipBtn.text()).toContain('↓ ZIP')
    expect((zipBtn.element as HTMLButtonElement).disabled).toBe(false)
  })

  it('ZIP exporting=true muestra "Generando…" con spinner y está deshabilitado', async () => {
    // Regresión: el export es síncrono y tarda. Antes el botón no
    // daba feedback visual y el usuario pulsaba dos veces o se
    // preguntaba si había pasado algo.
    const router = makeRouter(); await router.isReady()
    const wrapper = mount(WorkbenchToolbar, {
      props: {
        batch: makeBatch(),
        running: false,
        transferring: false,
        uploading: false,
        exporting: true,
      },
      global: { plugins: [router] },
    })
    const zipBtn = wrapper.find('[data-testid="btn-zip"]')
    expect(zipBtn.text()).toContain('Generando')
    expect((zipBtn.element as HTMLButtonElement).disabled).toBe(true)
    expect(zipBtn.find('.animate-spin').exists()).toBe(true)
  })
})
