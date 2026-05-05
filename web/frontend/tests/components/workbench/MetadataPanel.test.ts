import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import MetadataPanel from '@/components/workbench/MetadataPanel.vue'
import { useWorkbenchLog } from '@/composables/useWorkbenchLog'
import type { ApplicationResponse, BatchResponse } from '@/api/types'

function makeApp(batchFields: unknown[] = []): ApplicationResponse {
  return {
    id: 1, name: 'X', description: '', active: true, output_format: 'tiff',
    created_at: '', tenant_id: 1, pipeline_json: '[]', events_json: '{}',
    transfer_json: '{}', batch_fields_json: JSON.stringify(batchFields),
    index_fields_json: '[]', auto_transfer: false, close_after_transfer: false,
    background_color: '', default_tab: 'lote', scanner_backend: '',
    image_config_json: '{}', ai_config_json: '{}', updated_at: '',
  }
}

function makeBatch(fields: Record<string, unknown> = {}): BatchResponse {
  return {
    id: 1, application_id: 1, state: 'read', page_count: 0,
    created_at: '', updated_at: '', fields_json: JSON.stringify(fields),
    folder_path: '', hostname: '',
  }
}

describe('MetadataPanel', () => {
  beforeEach(() => {
    const log = useWorkbenchLog()
    log.clear()
    log.filterLevel.value = 'debug'
  })

  it('renders empty state when application has no batch_fields', () => {
    const wrapper = mount(MetadataPanel, {
      props: { app: makeApp([]), batch: makeBatch(), saving: false },
    })
    expect(wrapper.text()).toContain('Sin campos definidos')
  })

  it('renders text input for type=texto', () => {
    const wrapper = mount(MetadataPanel, {
      props: {
        app: makeApp([{ label: 'Cliente', type: 'texto', required: false, config: {} }]),
        batch: makeBatch({ Cliente: 'ACME' }), saving: false,
      },
    })
    const input = wrapper.find('input[type="text"]')
    expect(input.exists()).toBe(true)
    expect((input.element as HTMLInputElement).value).toBe('ACME')
  })

  it('renders date / number / select for other field types', () => {
    const wrapper = mount(MetadataPanel, {
      props: {
        app: makeApp([
          { label: 'F', type: 'fecha', required: false, config: {} },
          { label: 'N', type: 'numerico', required: false, config: {} },
          { label: 'L', type: 'lista', required: false, config: { values: ['a', 'b'] } },
        ]),
        batch: makeBatch(), saving: false,
      },
    })
    expect(wrapper.find('input[type="date"]').exists()).toBe(true)
    expect(wrapper.find('input[type="number"]').exists()).toBe(true)
    expect(wrapper.findAll('select option')).toHaveLength(3) // "—" + a + b
  })

  it('disables save when no changes', () => {
    const wrapper = mount(MetadataPanel, {
      props: {
        app: makeApp([{ label: 'C', type: 'texto', required: false, config: {} }]),
        batch: makeBatch(), saving: false,
      },
    })
    expect((wrapper.find('button[type="submit"]').element as HTMLButtonElement).disabled).toBe(true)
  })

  it('enables save and emits "save" with new fields when user edits', async () => {
    const wrapper = mount(MetadataPanel, {
      props: {
        app: makeApp([{ label: 'C', type: 'texto', required: false, config: {} }]),
        batch: makeBatch(), saving: false,
      },
    })
    await wrapper.find('input[type="text"]').setValue('NEW')
    await wrapper.find('form').trigger('submit')
    expect(wrapper.emitted('save')).toEqual([[{ C: 'NEW' }]])
  })

  it('blocks save with required field empty and shows error', async () => {
    const wrapper = mount(MetadataPanel, {
      props: {
        app: makeApp([{ label: 'C', type: 'texto', required: true, config: {} }]),
        batch: makeBatch({ C: 'old' }), saving: false,
      },
    })
    await wrapper.find('input[type="text"]').setValue('')
    expect(wrapper.text()).toContain('Campo obligatorio: C')
    expect((wrapper.find('button[type="submit"]').element as HTMLButtonElement).disabled).toBe(true)
  })

  it('shows "Guardando…" when saving=true', () => {
    const wrapper = mount(MetadataPanel, {
      props: {
        app: makeApp([{ label: 'C', type: 'texto', required: false, config: {} }]),
        batch: makeBatch({ C: 'x' }), saving: true,
      },
    })
    expect(wrapper.find('button[type="submit"]').text()).toBe('Guardando…')
  })

  it('disables save when batch is null', () => {
    const wrapper = mount(MetadataPanel, {
      props: {
        app: makeApp([{ label: 'C', type: 'texto', required: false, config: {} }]),
        batch: null, saving: false,
      },
    })
    expect((wrapper.find('button[type="submit"]').element as HTMLButtonElement).disabled).toBe(true)
  })
})

describe('MetadataPanel — Log tab', () => {
  beforeEach(() => {
    const log = useWorkbenchLog()
    log.clear()
    log.filterLevel.value = 'debug'
  })

  const defaultProps = {
    app: makeApp([]),
    batch: makeBatch(),
    saving: false,
  }

  it('renders "Log" tab (not disabled)', () => {
    const wrapper = mount(MetadataPanel, { props: defaultProps })
    const tab = wrapper.find('[data-testid="tab-log"]')
    expect(tab.exists()).toBe(true)
    expect(tab.attributes('disabled')).toBeUndefined()
  })

  it('shows Log tab label without count when no warns/errors', () => {
    const wrapper = mount(MetadataPanel, { props: defaultProps })
    const label = wrapper.find('[data-testid="tab-log-label"]')
    expect(label.text().trim()).toBe('Log')
  })

  it('shows count in Log tab label when warns/errors present', () => {
    const log = useWorkbenchLog()
    log.append('error', 'pipeline', 'boom')
    log.append('warn', 'script', 'oops')
    log.append('info', 'pipeline', 'ok') // no cuenta
    const wrapper = mount(MetadataPanel, { props: defaultProps })
    const label = wrapper.find('[data-testid="tab-log-label"]')
    expect(label.text()).toContain('2')
  })

  it('renders LogPanel when Log tab is active', async () => {
    const wrapper = mount(MetadataPanel, { props: defaultProps })
    await wrapper.find('[data-testid="tab-log"]').trigger('click')
    expect(wrapper.findComponent({ name: 'LogPanel' }).exists()).toBe(true)
  })

  it('Lote tab remains default active', () => {
    const wrapper = mount(MetadataPanel, { props: defaultProps })
    // Por defecto "Lote" activa: no se renderiza LogPanel
    expect(wrapper.findComponent({ name: 'LogPanel' }).exists()).toBe(false)
  })
})
