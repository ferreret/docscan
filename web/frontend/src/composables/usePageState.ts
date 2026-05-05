import type { PageResponse } from '@/api/types'

export type PageState =
  | 'excluded'
  | 'needs_review'
  | 'separator_barcode'
  | 'has_fields'
  | 'barcode_no_role'
  | 'no_recognition'

export const PAGE_STATE_BORDER_CLASS: Record<PageState, string> = {
  excluded: 'border-danger',
  needs_review: 'border-warning',
  separator_barcode: 'border-primary',
  has_fields: 'border-primary',
  barcode_no_role: 'border-success',
  no_recognition: 'border-overlay-0',
}

export function determinePageState(page: PageResponse): PageState {
  if (page.is_excluded) return 'excluded'
  if (page.needs_review) return 'needs_review'

  const barcodes = page.barcodes ?? []
  if (barcodes.some((b) => b.role === 'separator')) return 'separator_barcode'

  let hasFields = false
  try {
    const fields = JSON.parse(page.index_fields_json || '{}')
    hasFields = fields && typeof fields === 'object' && Object.keys(fields).length > 0
  } catch {
    hasFields = false
  }
  if (hasFields) return 'has_fields'

  if (barcodes.length > 0) return 'barcode_no_role'

  return 'no_recognition'
}
