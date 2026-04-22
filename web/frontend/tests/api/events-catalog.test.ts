import { describe, it, expect } from 'vitest'
import { EVENT_DEFINITIONS } from '@/api/events-catalog'

describe('events-catalog', () => {
  it('EVENT_DEFINITIONS contiene on_scan_complete y los 3 eventos de transferencia', () => {
    expect(EVENT_DEFINITIONS).toHaveLength(4)
    const names = EVENT_DEFINITIONS.map((e) => e.name)
    expect(names).toContain('on_scan_complete')
    expect(names).toContain('on_transfer_validate')
    expect(names).toContain('on_transfer_advanced')
    expect(names).toContain('on_transfer_page')
  })

  it('on_scan_complete template empieza con def on_scan_complete(', () => {
    const event = EVENT_DEFINITIONS.find((e) => e.name === 'on_scan_complete')!
    expect(event.template.startsWith('def on_scan_complete(')).toBe(true)
  })

  it('on_scan_complete contextVariables incluye app, batch, log, http', () => {
    const event = EVENT_DEFINITIONS.find((e) => e.name === 'on_scan_complete')!
    const names = event.contextVariables.map((v) => v.name)
    expect(names).toEqual(expect.arrayContaining(['app', 'batch', 'log', 'http']))
  })

  it('on_transfer_validate incluye result en contextVariables', () => {
    const event = EVENT_DEFINITIONS.find((e) => e.name === 'on_transfer_validate')!
    const names = event.contextVariables.map((v) => v.name)
    expect(names).toContain('result')
    expect(names).toContain('app')
    expect(names).toContain('batch')
  })

  it('on_transfer_validate template contiene return True', () => {
    const event = EVENT_DEFINITIONS.find((e) => e.name === 'on_transfer_validate')!
    expect(event.template).toContain('return True')
  })

  it('on_transfer_page incluye page y result en contextVariables', () => {
    const event = EVENT_DEFINITIONS.find((e) => e.name === 'on_transfer_page')!
    const names = event.contextVariables.map((v) => v.name)
    expect(names).toContain('page')
    expect(names).toContain('result')
  })

  it('on_transfer_advanced template empieza con def on_transfer_advanced(', () => {
    const event = EVENT_DEFINITIONS.find((e) => e.name === 'on_transfer_advanced')!
    expect(event.template.startsWith('def on_transfer_advanced(')).toBe(true)
  })
})
