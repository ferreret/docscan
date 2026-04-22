import { ref, type Ref } from 'vue'

export interface LayoutSizes {
  columns: [number, number, number]
  rightVertical: [number, number]
}

const STORAGE_KEY = 'workbench.layout'
const DEFAULT_SIZES: LayoutSizes = {
  columns: [15, 55, 30],
  rightVertical: [50, 50],
}

function isValidSizes(value: unknown): value is LayoutSizes {
  if (!value || typeof value !== 'object') return false
  const v = value as Partial<LayoutSizes>
  return (
    Array.isArray(v.columns) && v.columns.length === 3 &&
    v.columns.every((n) => typeof n === 'number' && n > 0) &&
    Array.isArray(v.rightVertical) && v.rightVertical.length === 2 &&
    v.rightVertical.every((n) => typeof n === 'number' && n > 0)
  )
}

function readStored(): LayoutSizes {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return DEFAULT_SIZES
    const parsed = JSON.parse(raw)
    return isValidSizes(parsed) ? parsed : DEFAULT_SIZES
  } catch {
    return DEFAULT_SIZES
  }
}

const sizes = ref<LayoutSizes>(readStored())

function setSizes(next: LayoutSizes): void {
  sizes.value = next
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
  } catch {
    /* localStorage bloqueado */
  }
}

export function useWorkbenchLayout(): { sizes: Ref<LayoutSizes>; setSizes: (s: LayoutSizes) => void } {
  return { sizes, setSizes }
}

/** Solo para tests. */
export function _resetLayoutForTests(): void {
  sizes.value = readStored()
}
