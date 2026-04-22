import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import WorkbenchView from '@/views/batches/WorkbenchView.vue'
import { useBatchesStore } from '@/stores/batches'
import { useApplicationsStore } from '@/stores/applications'

function makeRouter(initial = '/batches/1') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/batches', component: { template: '<div/>' } },
      { path: '/batches/:id', component: WorkbenchView, props: true },
    ],
  })
  router.push(initial)
  return router
}

describe('WorkbenchView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('mounts and calls store.fetchOne + fetchPages on the route batchId', async () => {
    const batches = useBatchesStore()
    const apps = useApplicationsStore()
    batches.fetchOne = vi.fn(async () => {
      batches.current = {
        id: 1, application_id: 5, state: 'read', page_count: 0,
        created_at: '', updated_at: '', fields_json: '{}', folder_path: '', hostname: '',
      }
    })
    batches.fetchPages = vi.fn(async () => { batches.pages = [] })
    apps.fetchOne = vi.fn(async () => {})
    const router = makeRouter('/batches/1')
    await router.isReady()
    mount(WorkbenchView, { global: { plugins: [router] } })
    await flushPromises()
    expect(batches.fetchOne).toHaveBeenCalledWith(1)
    expect(batches.fetchPages).toHaveBeenCalledWith(1)
  })

  it('navigates pages with ArrowRight / ArrowLeft', async () => {
    const batches = useBatchesStore()
    const apps = useApplicationsStore()
    batches.fetchOne = vi.fn(async () => {
      batches.current = {
        id: 1, application_id: 5, state: 'read', page_count: 3,
        created_at: '', updated_at: '', fields_json: '{}', folder_path: '', hostname: '',
      }
    })
    batches.fetchPages = vi.fn(async () => {
      batches.pages = [
        { id: 10, batch_id: 1, page_index: 0, needs_review: false, is_blank: false, pipeline_processed: false, created_at: '' },
        { id: 11, batch_id: 1, page_index: 1, needs_review: false, is_blank: false, pipeline_processed: false, created_at: '' },
        { id: 12, batch_id: 1, page_index: 2, needs_review: false, is_blank: false, pipeline_processed: false, created_at: '' },
      ]
    })
    batches.fetchPage = vi.fn(async () => {})
    apps.fetchOne = vi.fn(async () => {})
    const router = makeRouter('/batches/1'); await router.isReady()
    const wrapper = mount(WorkbenchView, { global: { plugins: [router] }, attachTo: document.body })
    await flushPromises()
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight' }))
    await flushPromises()
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight' }))
    await flushPromises()
    expect(batches.fetchPage).toHaveBeenCalledWith(1, 11)
    expect(batches.fetchPage).toHaveBeenCalledWith(1, 12)
    wrapper.unmount()
  })

  it('removes keydown listener on unmount', async () => {
    const batches = useBatchesStore()
    const apps = useApplicationsStore()
    batches.fetchOne = vi.fn(async () => { batches.current = { id: 1, application_id: 5, state: 'read', page_count: 0, created_at: '', updated_at: '', fields_json: '{}', folder_path: '', hostname: '' } })
    batches.fetchPages = vi.fn(async () => { batches.pages = [] })
    apps.fetchOne = vi.fn(async () => {})
    const router = makeRouter('/batches/1'); await router.isReady()
    const removeSpy = vi.spyOn(window, 'removeEventListener')
    const wrapper = mount(WorkbenchView, { global: { plugins: [router] } })
    await flushPromises()
    wrapper.unmount()
    expect(removeSpy).toHaveBeenCalledWith('keydown', expect.any(Function))
    removeSpy.mockRestore()
  })

  it('persists splitter sizes via setSizes when columns are resized', async () => {
    const batches = useBatchesStore()
    const apps = useApplicationsStore()
    batches.fetchOne = vi.fn(async () => { batches.current = { id: 1, application_id: 5, state: 'read', page_count: 0, created_at: '', updated_at: '', fields_json: '{}', folder_path: '', hostname: '' } })
    batches.fetchPages = vi.fn(async () => { batches.pages = [] })
    apps.fetchOne = vi.fn(async () => {})
    const router = makeRouter('/batches/1'); await router.isReady()
    const wrapper = mount(WorkbenchView, { global: { plugins: [router] } })
    await flushPromises()
    // Simulate splitpanes "resized" event on the outer Splitpanes
    const outerSplit = wrapper.findAllComponents({ name: 'splitpanes' })[0]
    outerSplit.vm.$emit('resized', [{ size: 20 }, { size: 50 }, { size: 30 }])
    await flushPromises()
    const stored = JSON.parse(localStorage.getItem('workbench.layout')!)
    expect(stored.columns).toEqual([20, 50, 30])
    wrapper.unmount()
  })
})
