<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router'
import { usePipelineStore } from '@/stores/pipeline'
import { useApplicationsStore } from '@/stores/applications'
import PipelineStepList from '@/components/pipeline/PipelineStepList.vue'
import PipelineStepDrawer from '@/components/pipeline/PipelineStepDrawer.vue'
import AddStepMenu from '@/components/pipeline/AddStepMenu.vue'
import type { PipelineStep, StepType } from '@/api/types-pipeline'

const route = useRoute()
const router = useRouter()
const pipelineStore = usePipelineStore()
const appStore = useApplicationsStore()

const appId = computed(() => Number(route.params.id))
const drawerOpen = ref(false)
const drawerStep = ref<PipelineStep | null>(null)
const drawerIsNew = ref(false)
const toast = ref<{ kind: 'ok' | 'error'; msg: string } | null>(null)

onMounted(async () => {
  try {
    await appStore.fetchOne(appId.value)
    await pipelineStore.fetch(appId.value)
  } catch (e) {
    const err = e as Error & { status?: number }
    if (err.status === 404) {
      router.push('/applications')
    } else {
      showToast('error', `No se pudo cargar el pipeline: ${err.message}`)
    }
  }
})

onBeforeRouteLeave(() => {
  if (pipelineStore.saving) {
    return confirm('Hay cambios guardándose. ¿Salir de todos modos?')
  }
  return true
})

function showToast(kind: 'ok' | 'error', msg: string) {
  toast.value = { kind, msg }
  setTimeout(() => (toast.value = null), 3500)
}

async function persist() {
  try {
    await pipelineStore.save(appId.value)
    showToast('ok', 'Pipeline actualizado')
  } catch (e) {
    showToast('error', (e as Error).message)
  }
}

function onEditStep(step: PipelineStep) {
  drawerStep.value = { ...step }
  drawerIsNew.value = false
  drawerOpen.value = true
}

function onAddStep(type: StepType) {
  const step = pipelineStore.addStep(type)
  drawerStep.value = { ...step }
  drawerIsNew.value = true
  drawerOpen.value = true
}

async function onRemoveStep(step: PipelineStep) {
  if (!confirm(`¿Eliminar este step "${step.type}"?`)) return
  pipelineStore.removeStep(step.id)
  await persist()
}

async function onReorder(newOrder: PipelineStep[]) {
  pipelineStore.reorder(newOrder)
  await persist()
}

async function onDrawerSave(updated: PipelineStep) {
  pipelineStore.updateStep(updated.id, updated)
  drawerOpen.value = false
  await persist()
}

function onDrawerCancel() {
  // Si era un step nuevo y cancela, lo quitamos.
  if (drawerIsNew.value && drawerStep.value) {
    pipelineStore.removeStep(drawerStep.value.id)
  }
  drawerOpen.value = false
}
</script>

<template>
  <div>
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <button
          @click="router.push(`/applications/${appId}`)"
          class="text-xs text-subtext hover:text-text mb-2 inline-flex items-center gap-1 transition-colors"
        >
          ← {{ appStore.current?.name || 'Aplicación' }}
        </button>
        <h1 class="text-2xl font-bold text-text">Editor de pipeline</h1>
        <p class="text-xs text-subtext mt-1">
          {{ pipelineStore.steps.length }} step<span v-if="pipelineStore.steps.length !== 1">s</span>
          <span v-if="pipelineStore.saving" class="ml-2 text-primary">guardando…</span>
        </p>
      </div>
      <AddStepMenu @select="onAddStep" />
    </div>

    <!-- Lista -->
    <div v-if="pipelineStore.loading" class="text-center py-12 text-subtext">
      Cargando…
    </div>
    <PipelineStepList
      v-else
      :model-value="pipelineStore.steps"
      @update:model-value="onReorder"
      @edit-step="onEditStep"
      @remove-step="onRemoveStep"
    />

    <!-- Drawer -->
    <PipelineStepDrawer
      :open="drawerOpen"
      :step="drawerStep"
      :is-new="drawerIsNew"
      @save="onDrawerSave"
      @cancel="onDrawerCancel"
    />

    <!-- Toast -->
    <div
      v-if="toast"
      class="fixed bottom-4 right-4 px-4 py-2 rounded-md shadow-lg text-sm z-50"
      :class="toast.kind === 'ok'
        ? 'bg-green-500 text-white'
        : 'bg-red-500 text-white'"
    >
      {{ toast.msg }}
    </div>
  </div>
</template>
