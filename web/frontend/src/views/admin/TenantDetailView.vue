<script setup lang="ts">
// Stub temporal — la implementación llega en hito 10.
defineProps<{ id: string }>()
</script>

<template>
  <div>
    <h2 class="text-xl font-semibold text-text">Detalle del tenant {{ id }}</h2>
    <p class="text-subtext text-sm mt-1">Vista en construcción.</p>
  </div>
</template>
