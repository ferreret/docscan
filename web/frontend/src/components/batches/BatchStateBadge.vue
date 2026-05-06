<script setup lang="ts">
import { computed } from 'vue'
import { getBatchStateInfo } from './batchStates'

const props = defineProps<{ state: string }>()

const info = computed(() => getBatchStateInfo(props.state))
</script>

<template>
  <span
    class="text-[11px] px-2 py-0.5 rounded-full font-medium border"
    :class="[info.badgeClass, info.pulse ? 'animate-pulse' : '']"
    :title="state"
  >
    {{ info.badgeLabel }}
  </span>
</template>
