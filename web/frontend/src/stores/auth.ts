import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api, ApiError } from '@/api/client'
import type { LoginRequest, TokenResponse, UserResponse } from '@/api/types'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<UserResponse | null>(null)
  const token = ref<string | null>(localStorage.getItem('access_token'))
  const loading = ref(false)
  const error = ref<string | null>(null)

  const isAuthenticated = computed(() => !!token.value)

  async function login(data: LoginRequest) {
    loading.value = true
    error.value = null
    try {
      const res = await api.post<TokenResponse>('/auth/login', data)
      token.value = res.access_token
      localStorage.setItem('access_token', res.access_token)
      await fetchUser()
    } catch (e) {
      error.value = e instanceof ApiError ? e.detail : 'Error de conexión'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchUser() {
    if (!token.value) return
    try {
      user.value = await api.get<UserResponse>('/auth/me')
    } catch {
      logout()
    }
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('access_token')
    window.location.href = '/login'
  }

  return { user, token, loading, error, isAuthenticated, login, fetchUser, logout }
})
