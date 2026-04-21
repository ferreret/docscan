<script setup lang="ts">
import { useRouter } from 'vue-router'

defineProps<{
  appId: number
  appName: string
  description?: string
}>()

const router = useRouter()
</script>

<template>
  <div class="mb-4">
    <div class="flex items-start justify-between gap-4">
      <div>
        <button
          @click="router.push('/applications')"
          class="text-xs text-subtext hover:text-text mb-2 inline-flex items-center gap-1 transition-colors"
        >
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" /></svg>
          Aplicaciones
        </button>
        <h1 class="text-2xl font-bold text-text">{{ appName }}</h1>
        <p v-if="description" class="text-xs text-subtext mt-1">{{ description }}</p>
      </div>
      <div class="flex gap-2 items-center">
        <slot name="actions" />
      </div>
    </div>

    <nav class="flex gap-1 border-b border-surface-0 mt-4" aria-label="Pestañas de configuración">
      <router-link
        data-test="app-tab"
        :to="`/applications/${appId}`"
        active-class="text-primary border-primary font-semibold"
        exact-active-class="text-primary border-primary font-semibold"
        class="px-4 py-2 text-[13px] border-b-2 border-transparent text-subtext hover:text-text transition-colors"
      >Resumen</router-link>
      <router-link
        data-test="app-tab"
        :to="`/applications/${appId}/pipeline`"
        active-class="text-primary border-primary font-semibold"
        class="px-4 py-2 text-[13px] border-b-2 border-transparent text-subtext hover:text-text transition-colors"
      >Pipeline</router-link>
      <router-link
        data-test="app-tab"
        :to="`/applications/${appId}/events`"
        active-class="text-primary border-primary font-semibold"
        class="px-4 py-2 text-[13px] border-b-2 border-transparent text-subtext hover:text-text transition-colors"
      >Eventos</router-link>
    </nav>
  </div>
</template>
