<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router'
import { usePipelineStore } from '@/stores/pipeline'
import { useApplicationsStore } from '@/stores/applications'
import PipelineStepList from '@/components/pipeline/PipelineStepList.vue'
import PipelineStepDrawer from '@/components/pipeline/PipelineStepDrawer.vue'
import AddStepMenu from '@/components/pipeline/AddStepMenu.vue'
import AppHeader from '@/components/AppHeader.vue'
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
  if (pipelineStore.saving || drawerOpen.value) {
    return confirm('Hay cambios sin guardar. ¿Salir de todos modos?')
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
  if (drawerIsNew.value && drawerStep.value) {
    pipelineStore.removeStep(drawerStep.value.id)
  }
  drawerOpen.value = false
}
</script>

<template>
  <div>
    <!-- Header -->
    <AppHeader
      v-if="appStore.current"
      :app-id="appId"
      :app-name="appStore.current.name"
      :description="appStore.current.description || undefined"
    >
      <template #actions>
        <AddStepMenu @select="onAddStep" />
      </template>
    </AppHeader>

    <!-- Estado del pipeline -->
    <p class="text-xs text-subtext mb-4">
      {{ pipelineStore.steps.length }} step<span v-if="pipelineStore.steps.length !== 1">s</span>
      <span v-if="pipelineStore.saving" class="ml-2 text-primary">guardando…</span>
    </p>

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
