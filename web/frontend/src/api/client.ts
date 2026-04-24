// Cliente HTTP centralizado para la API REST.

import type { EventFireIn, EventResult } from './types'

const BASE_URL = '/api'

class ApiError extends Error {
  status: number
  detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

function getToken(): string | null {
  return localStorage.getItem('access_token')
}

type PydanticError = { loc?: (string | number)[]; msg?: string }

function formatDetail(detail: unknown): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((e: PydanticError) => {
        const field = e.loc?.filter((p) => p !== 'body').join('.') || ''
        const msg = e.msg || 'error de validación'
        return field ? `${field}: ${msg}` : msg
      })
      .join(' · ')
  }
  return 'Error desconocido'
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  // No poner Content-Type si es FormData (el browser lo gestiona con boundary)
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  })

  if (res.status === 401 && token) {
    localStorage.removeItem('access_token')
    window.location.href = '/login'
    throw new ApiError(401, 'No autenticado')
  }

  if (res.status === 204) {
    return undefined as T
  }

  const body = await res.json()

  if (!res.ok) {
    throw new ApiError(res.status, formatDetail(body.detail))
  }

  return body as T
}

export const api = {
  get: <T>(path: string) => request<T>(path),

  post: <T>(path: string, data?: unknown) =>
    request<T>(path, {
      method: 'POST',
      body: data instanceof FormData ? data : JSON.stringify(data),
    }),

  patch: <T>(path: string, data: unknown) =>
    request<T>(path, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  put: <T>(path: string, data: unknown) =>
    request<T>(path, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  delete: (path: string) =>
    request<void>(path, { method: 'DELETE' }),

  uploadFiles: <T>(path: string, files: File[]) => {
    const form = new FormData()
    files.forEach((f) => form.append('files', f))
    return request<T>(path, { method: 'POST', body: form })
  },
}

export async function fireEvent(
  batchId: number,
  eventName: string,
  payload: EventFireIn = {},
): Promise<EventResult> {
  return api.post<EventResult>(`/batches/${batchId}/events/${eventName}`, payload)
}

export { ApiError }
