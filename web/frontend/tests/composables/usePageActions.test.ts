import { describe, it, expect, vi, beforeEach } from 'vitest'
import { usePageActions } from '@/composables/usePageActions'
import { api } from '@/api/client'

vi.mock('@/api/client', () => ({
  api: {
    patch: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('usePageActions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(api.patch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({ data: {} })
    ;(api.post as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({ data: {} })
    ;(api.delete as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({ data: {} })
  })

  it('toggleExcluded calls PATCH /pages/:id', async () => {
    const actions = usePageActions()
    await actions.toggleExcluded(42, true)
    expect(api.patch).toHaveBeenCalledWith('/pages/42', { is_excluded: true })
  })

  it('toggleReview calls PATCH with needs_review + reason', async () => {
    const actions = usePageActions()
    await actions.toggleReview(42, true, 'check it')
    expect(api.patch).toHaveBeenCalledWith('/pages/42', {
      needs_review: true,
      review_reason: 'check it',
    })
  })

  it('toggleReview defaults reason to empty string', async () => {
    const actions = usePageActions()
    await actions.toggleReview(42, false)
    expect(api.patch).toHaveBeenCalledWith('/pages/42', {
      needs_review: false,
      review_reason: '',
    })
  })

  it('rotatePage calls POST /pages/:id/rotate', async () => {
    const actions = usePageActions()
    await actions.rotatePage(42, 2)
    expect(api.post).toHaveBeenCalledWith('/pages/42/rotate', { turns: 2 })
  })

  it('deletePage calls DELETE /batches/:bid/pages/:pid', async () => {
    const actions = usePageActions()
    await actions.deletePage(5, 42)
    expect(api.delete).toHaveBeenCalledWith('/batches/5/pages/42')
  })

  it('deleteFromPage calls DELETE /batches/:batch/pages/after/:page', async () => {
    const actions = usePageActions()
    await actions.deleteFromPage(5, 42)
    expect(api.delete).toHaveBeenCalledWith('/batches/5/pages/after/42')
  })

  it('reorderPages calls POST /batches/:id/reorder', async () => {
    const actions = usePageActions()
    await actions.reorderPages(5, [10, 20, 30])
    expect(api.post).toHaveBeenCalledWith('/batches/5/reorder', {
      page_ids: [10, 20, 30],
    })
  })

  it('addBarcode calls POST /pages/:id/barcodes', async () => {
    const actions = usePageActions()
    await actions.addBarcode(42, 'ABC', 'MANUAL')
    expect(api.post).toHaveBeenCalledWith('/pages/42/barcodes', {
      value: 'ABC',
      symbology: 'MANUAL',
    })
  })

  it('deleteBarcode calls DELETE', async () => {
    const actions = usePageActions()
    await actions.deleteBarcode(42, 7)
    expect(api.delete).toHaveBeenCalledWith('/pages/42/barcodes/7')
  })

  it('returns the underlying promise (so callers can await data)', async () => {
    ;(api.patch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { id: 1, is_excluded: true },
    })
    const actions = usePageActions()
    const res = await actions.toggleExcluded(1, true)
    expect((res as { data: { is_excluded: boolean } }).data.is_excluded).toBe(true)
  })

  it('reprocessPage llama POST /pages/:id/reprocess', async () => {
    const actions = usePageActions()
    await actions.reprocessPage(42)
    expect(api.post).toHaveBeenCalledWith('/pages/42/reprocess', {})
  })
})
