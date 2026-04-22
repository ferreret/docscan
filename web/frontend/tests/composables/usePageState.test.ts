import { describe, it, expect } from 'vitest'
import { determinePageState, PAGE_STATE_BORDER_CLASS, type PageState } from '@/composables/usePageState'
import type { PageResponse, BarcodeResponse } from '@/api/types'

function makePage(overrides: Partial<PageResponse> = {}): PageResponse {
  return {
    id: 1,
    batch_id: 1,
    page_index: 0,
    needs_review: false,
    is_blank: false,
    pipeline_processed: false,
    created_at: '2026-04-22T00:00:00Z',
    image_path: '/img.png',
    ocr_text: '',
    index_fields_json: '{}',
    review_reason: '',
    is_excluded: false,
    processing_errors_json: '[]',
    script_errors_json: '[]',
    barcodes: [],
    updated_at: '2026-04-22T00:00:00Z',
    ...overrides,
  }
}

function makeBarcode(role = ''): BarcodeResponse {
  return {
    id: 1, value: 'V', symbology: 'EAN', engine: 'motor1',
    step_id: 's1', quality: 1, pos_x: 0, pos_y: 0, pos_w: 10, pos_h: 10, role,
  }
}

describe('determinePageState', () => {
  it('returns "excluded" when is_excluded is true', () => {
    expect(determinePageState(makePage({ is_excluded: true }))).toBe('excluded')
  })

  it('returns "needs_review" when needs_review is true and not excluded', () => {
    expect(determinePageState(makePage({ needs_review: true }))).toBe('needs_review')
  })

  it('"excluded" wins over "needs_review"', () => {
    expect(determinePageState(makePage({ is_excluded: true, needs_review: true }))).toBe('excluded')
  })

  it('returns "separator_barcode" when any barcode has role=separator', () => {
    const page = makePage({ barcodes: [makeBarcode(''), makeBarcode('separator')] })
    expect(determinePageState(page)).toBe('separator_barcode')
  })

  it('returns "has_fields" when index_fields_json has keys', () => {
    const page = makePage({ index_fields_json: '{"cliente": "ACME"}' })
    expect(determinePageState(page)).toBe('has_fields')
  })

  it('returns "barcode_no_role" when has barcodes but none with role and no fields', () => {
    const page = makePage({ barcodes: [makeBarcode('')] })
    expect(determinePageState(page)).toBe('barcode_no_role')
  })

  it('returns "no_recognition" when has nothing', () => {
    expect(determinePageState(makePage())).toBe('no_recognition')
  })

  it('treats malformed index_fields_json as no fields', () => {
    const page = makePage({ index_fields_json: '{"broken' })
    expect(determinePageState(page)).toBe('no_recognition')
  })

  it('PAGE_STATE_BORDER_CLASS has entry for every state', () => {
    const states: PageState[] = ['excluded', 'needs_review', 'separator_barcode', 'has_fields', 'barcode_no_role', 'no_recognition']
    for (const s of states) {
      expect(PAGE_STATE_BORDER_CLASS[s]).toMatch(/^border-/)
    }
  })
})
