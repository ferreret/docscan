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

  it('appendFromEvent pipeline_started → info con total_pages', () => {
    log.appendFromEvent({ type: 'pipeline_started', total_pages: 5 })
    expect(log.entries.value).toHaveLength(1)
    const e = log.entries.value[0]
    expect(e.level).toBe('info')
    expect(e.source).toBe('pipeline')
    expect(e.message).toContain('5')
    expect(e.message).not.toContain('?')
  })

  it('appendFromEvent page_processed → debug usa total', () => {
    log.appendFromEvent({ type: 'page_processed', page_index: 1, total: 3 })
    expect(log.entries.value[0].level).toBe('debug')
    expect(log.entries.value[0].message).toContain('2/3')
  })

  it('appendFromEvent page_processed con ok=false → error con mensaje', () => {
    // El backend emite los errores de página en page_processed con ok=false
    // (no existe un evento page_error). Antes el log tenía una rama muerta
    // para page_error que nunca se disparaba.
    log.appendFromEvent({
      type: 'page_processed',
      page_index: 0,
      total: 3,
      ok: false,
      error: 'boom',
    })
    const e = log.entries.value[0]
    expect(e.level).toBe('error')
    expect(e.message).toContain('boom')
    expect(e.message).toContain('1/3')
  })

  it('appendFromEvent pipeline_completed sin errores → info', () => {
    log.appendFromEvent({ type: 'pipeline_completed', any_error: false })
    const e = log.entries.value[0]
    expect(e.level).toBe('info')
    expect(e.message).toBe('Pipeline completado')
  })

  it('appendFromEvent pipeline_completed con any_error → warn', () => {
    log.appendFromEvent({ type: 'pipeline_completed', any_error: true })
    const e = log.entries.value[0]
    expect(e.level).toBe('warn')
    expect(e.message).toContain('errores')
  })

  it('appendFromEvent pipeline_error → error con detalle', () => {
    log.appendFromEvent({ type: 'pipeline_error', error: 'batch_not_found' })
    const e = log.entries.value[0]
    expect(e.level).toBe('error')
    expect(e.source).toBe('pipeline')
    expect(e.message).toContain('batch_not_found')
  })

  it('appendFromEvent transfer_started incluye total_pages y mode', () => {
    log.appendFromEvent({ type: 'transfer_started', total_pages: 4, mode: 'pdf' })
    const e = log.entries.value[0]
    expect(e.level).toBe('info')
    expect(e.message).toContain('4')
    expect(e.message).toContain('pdf')
  })

  it('appendFromEvent transfer_aborted incluye reason', () => {
    log.appendFromEvent({ type: 'transfer_aborted', reason: 'not_configured' })
    const e = log.entries.value[0]
    expect(e.level).toBe('warn')
    expect(e.message).toContain('not_configured')
  })

  it('appendFromEvent transfer_completed con files_transferred', () => {
    log.appendFromEvent({
      type: 'transfer_completed',
      success: true,
      files_transferred: 3,
    })
    const e = log.entries.value[0]
    expect(e.level).toBe('info')
    expect(e.message).toContain('3')
  })

  it('appendFromEvent transfer_completed con success=false → error', () => {
    log.appendFromEvent({
      type: 'transfer_completed',
      success: false,
      files_transferred: 0,
    })
    const e = log.entries.value[0]
    expect(e.level).toBe('error')
  })

  it('appendFromEvent transfer_error usa el campo error', () => {
    log.appendFromEvent({ type: 'transfer_error', error: 'fail' })
    const e = log.entries.value[0]
    expect(e.level).toBe('error')
    expect(e.source).toBe('transfer')
    expect(e.message).toContain('fail')
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
