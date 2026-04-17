<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const appId = computed(() => Number(route.params.id))
</script>

<template>
  <div>
    <button
      @click="router.push(`/applications/${appId}`)"
      class="text-xs text-subtext hover:text-text mb-2 inline-flex items-center gap-1 transition-colors"
    >
      ← Aplicación
    </button>
    <h1 class="text-2xl font-bold text-text">Editor de pipeline</h1>
    <p class="text-sm text-subtext mt-2">App #{{ appId }} — en construcción.</p>
  </div>
</template>
