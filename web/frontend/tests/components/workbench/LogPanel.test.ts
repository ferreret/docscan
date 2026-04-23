import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import LogPanel from '@/components/workbench/LogPanel.vue'
import { useWorkbenchLog } from '@/composables/useWorkbenchLog'

describe('LogPanel', () => {
  beforeEach(() => {
    const log = useWorkbenchLog()
    log.clear()
    log.filterLevel.value = 'debug'
  })

  it('shows empty state when no entries', () => {
    const wrapper = mount(LogPanel)
    expect(wrapper.text()).toMatch(/sin eventos/i)
  })

  it('renders log entries', () => {
    const log = useWorkbenchLog()
    log.append('info', 'pipeline', 'Pipeline iniciado')
    log.append('error', 'pipeline', 'Algo falló')
    const wrapper = mount(LogPanel)
    const rows = wrapper.findAll('[data-testid="log-entry"]')
    expect(rows).toHaveLength(2)
  })

  it('shows level color class on entries', () => {
    const log = useWorkbenchLog()
    log.append('error', 'pipeline', 'boom')
    const wrapper = mount(LogPanel)
    const entry = wrapper.find('[data-testid="log-entry"]')
    expect(entry.attributes('data-level')).toBe('error')
  })

  it('filter select restricts shown entries', async () => {
    const log = useWorkbenchLog()
    log.append('info', 'pipeline', 'info msg')
    log.append('error', 'pipeline', 'error msg')
    const wrapper = mount(LogPanel)
    const select = wrapper.find('[data-testid="filter-level"]')
    await select.setValue('error')
    const rows = wrapper.findAll('[data-testid="log-entry"]')
    expect(rows).toHaveLength(1)
    expect(rows[0].attributes('data-level')).toBe('error')
  })

  it('clear button empties entries', async () => {
    const log = useWorkbenchLog()
    log.append('info', 'pipeline', 'msg')
    const wrapper = mount(LogPanel)
    await wrapper.find('[data-testid="btn-clear"]').trigger('click')
    expect(wrapper.findAll('[data-testid="log-entry"]')).toHaveLength(0)
  })

  it('shows entries count', () => {
    const log = useWorkbenchLog()
    log.append('info', 'pipeline', 'a')
    log.append('info', 'pipeline', 'b')
    const wrapper = mount(LogPanel)
    expect(wrapper.find('[data-testid="entries-count"]').text()).toContain('2')
  })

  it('entries show source and message', () => {
    const log = useWorkbenchLog()
    log.append('info', 'script', 'error en paso X')
    const wrapper = mount(LogPanel)
    const entry = wrapper.find('[data-testid="log-entry"]')
    expect(entry.text()).toContain('script')
    expect(entry.text()).toContain('error en paso X')
  })
})
