import { describe, it, expect } from 'vitest'
import { EVENT_DEFINITIONS } from '@/api/events-catalog'

describe('events-catalog', () => {
  it('EVENT_DEFINITIONS contiene exactamente on_scan_complete', () => {
    expect(EVENT_DEFINITIONS).toHaveLength(1)
    expect(EVENT_DEFINITIONS[0].name).toBe('on_scan_complete')
  })

  it('on_scan_complete template empieza con def on_scan_complete(', () => {
    const event = EVENT_DEFINITIONS[0]
    expect(event.template.startsWith('def on_scan_complete(')).toBe(true)
  })

  it('on_scan_complete contextVariables incluye app, batch, log, http', () => {
    const event = EVENT_DEFINITIONS[0]
    const names = event.contextVariables.map((v) => v.name)
    expect(names).toEqual(expect.arrayContaining(['app', 'batch', 'log', 'http']))
  })
})
