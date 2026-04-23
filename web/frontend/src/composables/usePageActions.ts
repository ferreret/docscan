// Composable que centraliza las mutaciones HTTP del Workbench.
// Cada método es un wrapper fino sobre api.*; el rollback optimista se
// gestiona en el componente consumidor (WorkbenchView).
import { api } from '@/api/client'

export function usePageActions() {
  return {
    toggleExcluded: (pageId: number, value: boolean) =>
      api.patch(`/pages/${pageId}`, { is_excluded: value }),

    toggleReview: (pageId: number, value: boolean, reason = '') =>
      api.patch(`/pages/${pageId}`, {
        needs_review: value,
        review_reason: reason,
      }),

    rotatePage: (pageId: number, turns: number) =>
      api.post(`/pages/${pageId}/rotate`, { turns }),

    deletePage: (pageId: number) =>
      api.delete(`/pages/${pageId}`),

    deleteFromPage: (batchId: number, pageId: number) =>
      api.delete(`/batches/${batchId}/pages/after/${pageId}`),

    reorderPages: (batchId: number, pageIds: number[]) =>
      api.post(`/batches/${batchId}/reorder`, { page_ids: pageIds }),

    addBarcode: (pageId: number, value: string, symbology: string) =>
      api.post(`/pages/${pageId}/barcodes`, { value, symbology }),

    deleteBarcode: (pageId: number, barcodeId: number) =>
      api.delete(`/pages/${pageId}/barcodes/${barcodeId}`),
  }
}
