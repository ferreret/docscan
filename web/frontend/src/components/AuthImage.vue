<script setup lang="ts">
import { ref, watch, onUnmounted } from 'vue'

const props = defineProps<{
  src: string
  alt?: string
}>()

const objectUrl = ref<string | null>(null)

function revoke() {
  if (objectUrl.value) {
    URL.revokeObjectURL(objectUrl.value)
    objectUrl.value = null
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
    objectUrl.value = URL.createObjectURL(blob)
  } catch {
    // silently fail
  }
}

watch(() => props.src, (url) => {
  if (url) load(url)
  else revoke()
}, { immediate: true })

onUnmounted(revoke)
</script>

<template>
  <img v-if="objectUrl" :src="objectUrl" :alt="alt" v-bind="$attrs" />
  <div v-else class="animate-pulse bg-surface-0" v-bind="$attrs" />
</template>
