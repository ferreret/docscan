<script setup lang="ts">
import { ref, watch, onUnmounted } from 'vue'

const props = defineProps<{
  url: string
  alt?: string
}>()

const src = ref<string | null>(null)

function revoke() {
  if (src.value) {
    URL.revokeObjectURL(src.value)
    src.value = null
  }
}

async function load(url: string) {
  revoke()
  const token = localStorage.getItem('access_token')
  try {
    const res = await fetch(url, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!res.ok) return
    const blob = await res.blob()
    src.value = URL.createObjectURL(blob)
  } catch {
    // silently fail
  }
}

watch(() => props.url, (url) => {
  if (url) load(url)
  else revoke()
}, { immediate: true })

onUnmounted(revoke)
</script>

<template>
  <img v-if="src" :src="src" :alt="alt" v-bind="$attrs" />
  <div v-else class="animate-pulse bg-surface-0" v-bind="$attrs" />
</template>
