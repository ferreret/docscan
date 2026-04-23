import { ref, watch } from 'vue'

const STORAGE_KEY = 'workbench.overlays'

interface StoredToggles {
  barcodes: boolean
  fields: boolean
}

function readStored(): StoredToggles {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { barcodes: true, fields: true }
    const parsed = JSON.parse(raw)
    return {
      barcodes: typeof parsed.barcodes === 'boolean' ? parsed.barcodes : true,
      fields: typeof parsed.fields === 'boolean' ? parsed.fields : true,
    }
  } catch {
    return { barcodes: true, fields: true }
  }
}

export function useOverlayToggles() {
  const stored = readStored()
  const showBarcodes = ref(stored.barcodes)
  const showFields = ref(stored.fields)

  watch([showBarcodes, showFields], ([b, f]) => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ barcodes: b, fields: f }),
    )
  })

  return { showBarcodes, showFields }
}
