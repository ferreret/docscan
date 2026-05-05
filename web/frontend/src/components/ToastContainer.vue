<script setup lang="ts">
import { useToast, type ToastKind } from '@/composables/useToast'

const { toasts, dismiss } = useToast()

const kindStyles: Record<ToastKind, string> = {
  success: 'bg-success-soft border-success text-success',
  error: 'bg-danger-soft border-danger text-danger',
  info: 'bg-primary-soft border-primary text-primary',
}

const kindIcons: Record<ToastKind, string> = {
  success: '✓',
  error: '✕',
  info: 'i',
}
</script>

<template>
  <div class="pointer-events-none fixed bottom-6 right-6 z-50 flex flex-col gap-2">
    <TransitionGroup name="toast">
      <div
        v-for="t in toasts"
        :key="t.id"
        :class="[
          'pointer-events-auto flex min-w-[260px] max-w-md items-start gap-3 rounded-card border-l-4 bg-base px-4 py-3 shadow-lg',
          kindStyles[t.kind],
        ]"
      >
        <span class="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs font-bold">
          {{ kindIcons[t.kind] }}
        </span>
        <p class="flex-1 text-sm leading-snug text-text">{{ t.message }}</p>
        <button
          class="text-subtext hover:text-text"
          aria-label="Cerrar notificación"
          @click="dismiss(t.id)"
        >
          ×
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: all 0.25s ease;
}
.toast-enter-from {
  opacity: 0;
  transform: translateX(20px);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(20px);
}
</style>
