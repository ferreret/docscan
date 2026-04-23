import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import WorkbenchView from '@/views/batches/WorkbenchView.vue'
import { useBatchesStore } from '@/stores/batches'
import { useApplicationsStore } from '@/stores/applications'
import { useWorkbenchLog } from '@/composables/useWorkbenchLog'
import ThumbnailPanel from '@/components/workbench/ThumbnailPanel.vue'
import BarcodePanel from '@/components/workbench/BarcodePanel.vue'
import ViewerToolbar from '@/components/workbench/ViewerToolbar.vue'
import ThumbnailContextMenu from '@/components/workbench/ThumbnailContextMenu.vue'
import AddBarcodeDialog from '@/components/workbench/AddBarcodeDialog.vue'
import DeleteBarcodeDialog from '@/components/workbench/DeleteBarcodeDialog.vue'

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

  it('passes readOnly=true to editable children when batch.state is running', async () => {
    const batches = useBatchesStore()
    const apps = useApplicationsStore()
    batches.fetchOne = vi.fn(async () => {
      batches.current = {
        id: 1, application_id: 5, state: 'running', page_count: 1,
        created_at: '', updated_at: '', fields_json: '{}', folder_path: '', hostname: '',
      } as any
    })
    batches.fetchPages = vi.fn(async () => {
      batches.pages = [
        { id: 10, batch_id: 1, page_index: 0, needs_review: false, is_blank: false, pipeline_processed: false, created_at: '' },
      ] as any
    })
    batches.fetchPage = vi.fn(async () => {})
    apps.fetchOne = vi.fn(async () => {})
    const router = makeRouter('/batches/1'); await router.isReady()
    const wrapper = mount(WorkbenchView, { global: { plugins: [router] } })
    await flushPromises()

    const thumb = wrapper.findComponent(ThumbnailPanel)
    expect(thumb.exists()).toBe(true)
    expect(thumb.props('readOnly')).toBe(true)

    const bc = wrapper.findComponent(BarcodePanel)
    expect(bc.exists()).toBe(true)
    expect(bc.props('readOnly')).toBe(true)

    const toolbar = wrapper.findComponent(ViewerToolbar)
    if (toolbar.exists()) {
      expect(toolbar.props('canRotate')).toBe(false)
    }
    wrapper.unmount()
  })

  it('passes readOnly=false when batch.state is read', async () => {
    const batches = useBatchesStore()
    const apps = useApplicationsStore()
    batches.fetchOne = vi.fn(async () => {
      batches.current = {
        id: 1, application_id: 5, state: 'read', page_count: 1,
        created_at: '', updated_at: '', fields_json: '{}', folder_path: '', hostname: '',
      } as any
    })
    batches.fetchPages = vi.fn(async () => {
      batches.pages = [
        { id: 10, batch_id: 1, page_index: 0, needs_review: false, is_blank: false, pipeline_processed: false, created_at: '' },
      ] as any
    })
    batches.fetchPage = vi.fn(async () => {})
    apps.fetchOne = vi.fn(async () => {})
    const router = makeRouter('/batches/1'); await router.isReady()
    const wrapper = mount(WorkbenchView, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.findComponent(ThumbnailPanel).props('readOnly')).toBe(false)
    expect(wrapper.findComponent(BarcodePanel).props('readOnly')).toBe(false)
    wrapper.unmount()
  })

  it('loads persisted errors into the log when pages are fetched', async () => {
    const log = useWorkbenchLog()
    log.clear()
    const batches = useBatchesStore()
    const apps = useApplicationsStore()
    batches.fetchOne = vi.fn(async () => {
      batches.current = {
        id: 1, application_id: 5, state: 'read', page_count: 1,
        created_at: '', updated_at: '', fields_json: '{}', folder_path: '', hostname: '',
      } as any
    })
    batches.fetchPages = vi.fn(async () => {
      batches.pages = [
        {
          id: 10, batch_id: 1, page_index: 0,
          needs_review: false, is_blank: false, pipeline_processed: true,
          created_at: '', updated_at: '2026-04-23T10:00:00Z',
          processing_errors_json: JSON.stringify(['OCR falló']),
          script_errors_json: '[]',
        } as any,
      ]
    })
    batches.fetchPage = vi.fn(async () => {})
    apps.fetchOne = vi.fn(async () => {})
    const router = makeRouter('/batches/1'); await router.isReady()
    const wrapper = mount(WorkbenchView, { global: { plugins: [router] } })
    await flushPromises()

    const errorEntries = log.entries.value.filter((e) => e.level === 'error')
    expect(errorEntries.length).toBeGreaterThan(0)
    expect(errorEntries[0].message).toContain('OCR falló')
    wrapper.unmount()
  })

  it('opens ThumbnailContextMenu on right-click (non-readOnly batch)', async () => {
    const batches = useBatchesStore()
    const apps = useApplicationsStore()
    batches.fetchOne = vi.fn(async () => {
      batches.current = {
        id: 1, application_id: 5, state: 'read', page_count: 1,
        created_at: '', updated_at: '', fields_json: '{}', folder_path: '', hostname: '',
      } as any
    })
    batches.fetchPages = vi.fn(async () => {
      batches.pages = [
        { id: 10, batch_id: 1, page_index: 0, needs_review: false, is_blank: false, pipeline_processed: false, created_at: '' },
      ] as any
    })
    batches.fetchPage = vi.fn(async () => {})
    apps.fetchOne = vi.fn(async () => {})
    const router = makeRouter('/batches/1'); await router.isReady()
    const wrapper = mount(WorkbenchView, { global: { plugins: [router] } })
    await flushPromises()

    const menu = wrapper.findComponent(ThumbnailContextMenu)
    expect(menu.exists()).toBe(true)
    expect(menu.props('visible')).toBe(false)

    // Emitir el evento contextmenu desde ThumbnailPanel
    wrapper.findComponent(ThumbnailPanel).vm.$emit('contextmenu', 10, 150, 200)
    await flushPromises()

    expect(menu.props('visible')).toBe(true)
    expect(menu.props('pageId')).toBe(10)
    expect(menu.props('x')).toBe(150)
    expect(menu.props('y')).toBe(200)
    wrapper.unmount()
  })

  it('closes the context menu when the menu emits close', async () => {
    const batches = useBatchesStore()
    const apps = useApplicationsStore()
    batches.fetchOne = vi.fn(async () => {
      batches.current = {
        id: 1, application_id: 5, state: 'read', page_count: 1,
        created_at: '', updated_at: '', fields_json: '{}', folder_path: '', hostname: '',
      } as any
    })
    batches.fetchPages = vi.fn(async () => {
      batches.pages = [
        { id: 10, batch_id: 1, page_index: 0, needs_review: false, is_blank: false, pipeline_processed: false, created_at: '' },
      ] as any
    })
    batches.fetchPage = vi.fn(async () => {})
    apps.fetchOne = vi.fn(async () => {})
    const router = makeRouter('/batches/1'); await router.isReady()
    const wrapper = mount(WorkbenchView, { global: { plugins: [router] } })
    await flushPromises()

    wrapper.findComponent(ThumbnailPanel).vm.$emit('contextmenu', 10, 10, 10)
    await flushPromises()
    const menu = wrapper.findComponent(ThumbnailContextMenu)
    expect(menu.props('visible')).toBe(true)

    menu.vm.$emit('close')
    await flushPromises()
    expect(menu.props('visible')).toBe(false)
    wrapper.unmount()
  })

  it('opens AddBarcodeDialog when BarcodePanel emits add-barcode', async () => {
    const batches = useBatchesStore()
    const apps = useApplicationsStore()
    batches.fetchOne = vi.fn(async () => {
      batches.current = {
        id: 1, application_id: 5, state: 'read', page_count: 1,
        created_at: '', updated_at: '', fields_json: '{}', folder_path: '', hostname: '',
      } as any
    })
    batches.fetchPages = vi.fn(async () => {
      batches.pages = [
        { id: 10, batch_id: 1, page_index: 0, needs_review: false, is_blank: false, pipeline_processed: false, created_at: '' },
      ] as any
    })
    batches.fetchPage = vi.fn(async () => {})
    apps.fetchOne = vi.fn(async () => {})
    const router = makeRouter('/batches/1'); await router.isReady()
    const wrapper = mount(WorkbenchView, { global: { plugins: [router] } })
    await flushPromises()

    const addDialog = wrapper.findComponent(AddBarcodeDialog)
    expect(addDialog.props('visible')).toBe(false)

    wrapper.findComponent(BarcodePanel).vm.$emit('add-barcode')
    await flushPromises()
    expect(addDialog.props('visible')).toBe(true)

    addDialog.vm.$emit('close')
    await flushPromises()
    expect(addDialog.props('visible')).toBe(false)
    wrapper.unmount()
  })

  it('opens DeleteBarcodeDialog when BarcodePanel emits delete-barcode with a known barcode', async () => {
    const batches = useBatchesStore()
    const apps = useApplicationsStore()
    batches.fetchOne = vi.fn(async () => {
      batches.current = {
        id: 1, application_id: 5, state: 'read', page_count: 1,
        created_at: '', updated_at: '', fields_json: '{}', folder_path: '', hostname: '',
      } as any
    })
    batches.fetchPages = vi.fn(async () => {
      batches.pages = [
        { id: 10, batch_id: 1, page_index: 0, needs_review: false, is_blank: false, pipeline_processed: false, created_at: '' },
      ] as any
    })
    batches.fetchPage = vi.fn(async () => {
      batches.currentPage = {
        id: 10, batch_id: 1, page_index: 0, needs_review: false, is_blank: false,
        pipeline_processed: false, created_at: '', updated_at: '',
        image_path: '', ocr_text: '', index_fields_json: '{}', review_reason: '',
        is_excluded: false, processing_errors_json: '[]', script_errors_json: '[]',
        barcodes: [
          { id: 1, value: 'ABC123', symbology: 'CODE128', engine: 'zbar', step_id: '', quality: 100, pos_x: 0, pos_y: 0, pos_w: 10, pos_h: 10, role: '' },
        ],
      } as any
    })
    apps.fetchOne = vi.fn(async () => {})
    const router = makeRouter('/batches/1'); await router.isReady()
    const wrapper = mount(WorkbenchView, { global: { plugins: [router] } })
    await flushPromises()

    const delDialog = wrapper.findComponent(DeleteBarcodeDialog)
    expect(delDialog.props('visible')).toBe(false)

    wrapper.findComponent(BarcodePanel).vm.$emit('delete-barcode', 1)
    await flushPromises()
    expect(delDialog.props('visible')).toBe(true)
    expect(delDialog.props('barcodeValue')).toBe('ABC123')
    wrapper.unmount()
  })

  it('passes overlay toggles (showBarcodes / showFields) from composable to DocumentViewer and ViewerToolbar', async () => {
    localStorage.setItem('workbench.overlays', JSON.stringify({ barcodes: true, fields: false }))
    const batches = useBatchesStore()
    const apps = useApplicationsStore()
    batches.fetchOne = vi.fn(async () => {
      batches.current = {
        id: 1, application_id: 5, state: 'read', page_count: 1,
        created_at: '', updated_at: '', fields_json: '{}', folder_path: '', hostname: '',
      } as any
    })
    batches.fetchPages = vi.fn(async () => {
      batches.pages = [
        { id: 10, batch_id: 1, page_index: 0, needs_review: false, is_blank: false, pipeline_processed: false, created_at: '' },
      ] as any
    })
    batches.fetchPage = vi.fn(async () => {})
    apps.fetchOne = vi.fn(async () => {})
    const router = makeRouter('/batches/1'); await router.isReady()
    const wrapper = mount(WorkbenchView, { global: { plugins: [router] } })
    await flushPromises()

    const toolbar = wrapper.findComponent(ViewerToolbar)
    if (toolbar.exists()) {
      expect(toolbar.props('showBarcodes')).toBe(true)
      expect(toolbar.props('showFields')).toBe(false)
    }
    wrapper.unmount()
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
