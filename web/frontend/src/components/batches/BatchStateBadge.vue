<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{ state: string }>();

type BadgeConfig = { label: string; cls: string; pulse?: boolean };

const config = computed<BadgeConfig>(() => {
  switch (props.state) {
    case "created":
      return {
        label: "creado",
        cls: "bg-warning-soft text-warning border-warning/30",
      };
    case "running":
      return {
        label: "procesando…",
        cls: "bg-primary-soft text-primary border-primary/30",
        pulse: true,
      };
    case "read":
      return {
        label: "procesado",
        cls: "bg-primary-soft text-primary border-primary/30",
      };
    case "transferring":
      return {
        label: "transfiriendo…",
        cls: "bg-warning-soft text-warning border-warning/30",
        pulse: true,
      };
    case "transferred":
      return {
        label: "transferido",
        cls: "bg-success-soft text-success border-success/30",
      };
    default:
      if (props.state.startsWith("error")) {
        return {
          label: "error",
          cls: "bg-danger-soft text-danger border-danger/30",
        };
      }
      return {
        label: props.state,
        cls: "bg-mantle text-subtext border-surface-0",
      };
  }
});
</script>

<template>
  <span
    class="text-[11px] px-2 py-0.5 rounded-full font-medium border"
    :class="[config.cls, config.pulse ? 'animate-pulse' : '']"
    :title="state"
  >
    {{ config.label }}
  </span>
</template>
