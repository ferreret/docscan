<script setup lang="ts">
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import ToastContainer from '@/components/ToastContainer.vue'

const auth = useAuthStore()

onMounted(() => {
  if (auth.token) {
    auth.fetchUser()
  }
})
</script>

<template>
  <router-view />
  <ToastContainer />
</template>
