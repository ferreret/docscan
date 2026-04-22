<script setup lang="ts">
import { useRouter } from 'vue-router'
import { computed } from 'vue'

const props = defineProps<{
  appId: number
  appName: string
  description?: string
}>()

const router = useRouter()

const tabs = computed(() => [
  { to: `/applications/${props.appId}`, label: 'Resumen', exact: true },
  { to: `/applications/${props.appId}/general`, label: 'General', exact: false },
  { to: `/applications/${props.appId}/pipeline`, label: 'Pipeline', exact: false },
  { to: `/applications/${props.appId}/image`, label: 'Imagen', exact: false },
  { to: `/applications/${props.appId}/batch-fields`, label: 'Campos', exact: false },
  { to: `/applications/${props.appId}/events`, label: 'Eventos', exact: false },
])
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
        v-for="tab in tabs"
        :key="tab.to"
        data-test="app-tab"
        :to="tab.to"
        active-class="text-primary border-primary font-semibold"
        :exact-active-class="tab.exact ? 'text-primary border-primary font-semibold' : undefined"
        class="px-4 py-2 text-[13px] border-b-2 border-transparent text-subtext hover:text-text transition-colors"
      >{{ tab.label }}</router-link>
    </nav>
  </div>
</template>
