import { describe, it, expect, beforeEach } from 'vitest'
import { useWorkbenchLog } from '@/composables/useWorkbenchLog'

describe('useWorkbenchLog', () => {
  let log: ReturnType<typeof useWorkbenchLog>

  beforeEach(() => {
    log = useWorkbenchLog()
    log.clear()
    log.filterLevel.value = 'debug'
  })

  it('starts empty after clear', () => {
    expect(log.entries.value).toEqual([])
  })

  it('append adds a local entry', () => {
    log.append('info', 'user', 'Rotada página 3')
    expect(log.entries.value).toHaveLength(1)
    expect(log.entries.value[0].level).toBe('info')
    expect(log.entries.value[0].source).toBe('user')
    expect(log.entries.value[0].message).toContain('Rotada')
  })

  it('appendFromEvent pipeline_started → info with page_count', () => {
    log.appendFromEvent({ type: 'pipeline_started', page_count: 5 })
    expect(log.entries.value).toHaveLength(1)
    const e = log.entries.value[0]
    expect(e.level).toBe('info')
    expect(e.source).toBe('pipeline')
    expect(e.message).toContain('5')
  })

  it('appendFromEvent page_processed → debug', () => {
    log.appendFromEvent({ type: 'page_processed', page_index: 1, page_count: 3 })
    expect(log.entries.value[0].level).toBe('debug')
    expect(log.entries.value[0].message).toContain('2/3')
  })

  it('appendFromEvent page_error → error with message', () => {
    log.appendFromEvent({ type: 'page_error', page_index: 0, error: 'boom' })
    const e = log.entries.value[0]
    expect(e.level).toBe('error')
    expect(e.message).toContain('boom')
  })

  it('appendFromEvent pipeline_completed → info', () => {
    log.appendFromEvent({ type: 'pipeline_completed' })
    expect(log.entries.value[0].level).toBe('info')
  })

  it('appendFromEvent transfer_* events', () => {
    log.appendFromEvent({ type: 'transfer_started' })
    log.appendFromEvent({ type: 'transfer_completed' })
    log.appendFromEvent({ type: 'transfer_aborted' })
    log.appendFromEvent({ type: 'transfer_error', error: 'fail' })
    const levels = log.entries.value.map(e => e.level)
    expect(levels).toEqual(['info', 'info', 'warn', 'error'])
    log.entries.value.forEach(e => expect(e.source).toBe('transfer'))
  })

  it('appendFromEvent page_updated → debug editor', () => {
    log.appendFromEvent({ type: 'page_updated', page_id: 7, action: 'rotated' })
    const e = log.entries.value[0]
    expect(e.level).toBe('debug')
    expect(e.source).toBe('editor')
    expect(e.message).toContain('7')
    expect(e.message).toContain('rotated')
  })

  it('appendFromEvent ignores unknown types', () => {
    log.appendFromEvent({ type: 'unknown_event_xyz', foo: 'bar' })
    expect(log.entries.value).toHaveLength(0)
  })

  it('loadPersistedErrors populates from pages', () => {
    log.loadPersistedErrors([
      {
        id: 1, page_index: 0,
        processing_errors_json: JSON.stringify(['err1', 'err2']),
        script_errors_json: '[]',
        updated_at: '2026-04-23T10:00:00',
      },
      {
        id: 2, page_index: 1,
        processing_errors_json: '[]',
        script_errors_json: JSON.stringify([{ step_id: 's1', error: 'fail' }]),
        updated_at: '2026-04-23T10:01:00',
      },
    ] as any)
    expect(log.entries.value).toHaveLength(3)
    expect(log.entries.value.filter(e => e.level === 'error')).toHaveLength(2)
    expect(log.entries.value.filter(e => e.level === 'warn')).toHaveLength(1)
  })

  it('loadPersistedErrors handles malformed JSON gracefully', () => {
    log.loadPersistedErrors([
      {
        id: 1, page_index: 0,
        processing_errors_json: 'not json',
        script_errors_json: '[invalid',
        updated_at: '2026-04-23T10:00:00',
      },
    ] as any)
    expect(log.entries.value).toHaveLength(0)
  })

  it('filterLevel restricts filteredEntries', () => {
    log.append('info', 'pipeline', 'info msg')
    log.append('error', 'pipeline', 'error msg')
    log.append('warn', 'script', 'warn msg')
    log.filterLevel.value = 'error'
    expect(log.filteredEntries.value).toHaveLength(1)
    expect(log.filteredEntries.value[0].level).toBe('error')
  })

  it('clear empties entries', () => {
    log.append('info', 'user', 'x')
    log.clear()
    expect(log.entries.value).toEqual([])
  })

  it('is a singleton: returns same refs across calls', () => {
    const a = useWorkbenchLog()
    a.clear()
    a.append('info', 'user', 'from a')
    const b = useWorkbenchLog()
    expect(b.entries.value).toHaveLength(1)
    expect(b.entries.value[0].message).toBe('from a')
  })
})
