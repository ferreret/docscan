<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
</script>

<template>
  <div class="min-h-screen bg-base flex">
    <!-- Sidebar -->
    <aside class="w-64 bg-mantle border-r border-surface-1 flex flex-col">
      <div class="px-5 py-5 border-b border-surface-0">
        <h1 class="text-lg font-bold text-text tracking-tight">DocScan Studio</h1>
        <p class="text-xs text-subtext mt-0.5 truncate">{{ auth.user?.tenant_name }}</p>
      </div>

      <nav class="flex-1 p-3 space-y-0.5">
        <router-link
          to="/"
          class="flex items-center gap-2.5 px-3 py-2 rounded-md text-[13px] font-medium transition-colors"
          :class="$route.name === 'dashboard'
            ? 'bg-primary-soft text-primary border border-primary/30'
            : 'text-text hover:bg-crust'"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
          </svg>
          Inicio
        </router-link>

        <router-link
          to="/applications"
          class="flex items-center gap-2.5 px-3 py-2 rounded-md text-[13px] font-medium transition-colors"
          :class="$route.path.startsWith('/applications')
            ? 'bg-primary-soft text-primary border border-primary/30'
            : 'text-text hover:bg-crust'"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
          </svg>
          Aplicaciones
        </router-link>

        <router-link
          to="/batches"
          class="flex items-center gap-2.5 px-3 py-2 rounded-md text-[13px] font-medium transition-colors"
          :class="$route.path.startsWith('/batches')
            ? 'bg-primary-soft text-primary border border-primary/30'
            : 'text-text hover:bg-crust'"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          Lotes
        </router-link>

        <router-link
          v-if="auth.user?.role === 'company_admin'"
          to="/team"
          class="flex items-center gap-2.5 px-3 py-2 rounded-md text-[13px] font-medium transition-colors"
          :class="$route.path.startsWith('/team')
            ? 'bg-primary-soft text-primary border border-primary/30'
            : 'text-text hover:bg-crust'"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
          </svg>
          Equipo
        </router-link>
      </nav>

      <div class="p-3 border-t border-surface-0">
        <div class="flex items-center gap-2.5 px-2 py-1.5">
          <div class="w-8 h-8 rounded-full bg-primary-soft border border-primary/30 flex items-center justify-center text-primary font-semibold text-xs">
            {{ auth.user?.display_name?.charAt(0)?.toUpperCase() }}
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-[13px] font-medium text-text truncate">{{ auth.user?.display_name }}</p>
            <p class="text-[11px] text-subtext truncate">{{ auth.user?.email }}</p>
          </div>
          <button
            @click="auth.logout()"
            class="text-overlay-0 hover:text-danger p-1 rounded transition-colors"
            title="Cerrar sesión"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
          </button>
        </div>
      </div>
    </aside>

    <!-- Main content -->
    <main class="flex-1 overflow-auto bg-base">
      <div class="px-8 py-6 max-w-[1400px] mx-auto">
        <router-view />
      </div>
    </main>
  </div>
</template>
