import { ref } from 'vue'

export type ToastKind = 'success' | 'error' | 'info'

export interface Toast {
  id: number
  kind: ToastKind
  message: string
}

const toasts = ref<Toast[]>([])
const timers = new Map<number, number>()
let nextId = 1

function dismiss(id: number) {
  const handle = timers.get(id)
  if (handle !== undefined) {
    window.clearTimeout(handle)
    timers.delete(id)
  }
  toasts.value = toasts.value.filter((t) => t.id !== id)
}

function push(kind: ToastKind, message: string, timeoutMs: number): number {
  const id = nextId++
  toasts.value.push({ id, kind, message })
  if (timeoutMs > 0) {
    timers.set(id, window.setTimeout(() => dismiss(id), timeoutMs))
  }
  return id
}

export function useToast() {
  return {
    toasts,
    dismiss,
    success: (message: string, timeoutMs = 4000) => push('success', message, timeoutMs),
    error: (message: string, timeoutMs = 6000) => push('error', message, timeoutMs),
    info: (message: string, timeoutMs = 4000) => push('info', message, timeoutMs),
  }
}
