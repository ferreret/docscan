<script setup lang="ts">
// Vista "Mi estación" — sprint cliente local web, hito 9.
//
// Tres estados visuales según el agente local en http://127.0.0.1:47816:
//   1. Sin agente detectado: placeholder con instrucciones de descarga.
//   2. Detectado pero sin vincular: formulario de pairing (un click).
//   3. Vinculado: muestra device_name/user_email/tenant_name + lista de
//      escáneres. Los botones "Escanear" se integran en el workbench
//      del lote (hito 10), no aquí.

import { onMounted, ref, computed } from 'vue'
import { useAgentStore } from '@/stores/agent'
import { useToast } from '@/composables/useToast'

const store = useAgentStore()
const toast = useToast()

const deviceName = ref('')
const pairing = ref(false)

const status = computed(() => store.status)
const available = computed(() => store.available)
const paired = computed(() => store.paired)
const scanners = computed(() => store.scanners)
const loading = computed(() => store.loading)

onMounted(async () => {
  await store.detect()
  if (store.paired) {
    await store.loadScanners()
  }
})

async function onRefresh() {
  await store.detect()
  if (store.paired) {
    await store.loadScanners(true)
  }
}

async function onPair() {
  const name = deviceName.value.trim()
  if (!name) {
    toast.error('Pon un nombre para este equipo')
    return
  }
  pairing.value = true
  try {
    await store.pair(name)
    toast.success(`${name} vinculado correctamente`)
    deviceName.value = ''
    await store.loadScanners()
  } catch (e) {
    toast.error(e instanceof Error ? e.message : 'Error al vincular')
  } finally {
    pairing.value = false
  }
}
</script>

<template>
  <div class="space-y-6">
    <!-- Cabecera -->
    <div class="flex items-start justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold text-text">Mi estación</h1>
        <p class="text-sm text-subtext mt-1">
          Conecta este ordenador a la web para escanear con sus escáneres locales.
        </p>
      </div>
      <button
        @click="onRefresh"
        :disabled="loading"
        class="px-3 py-2 text-sm rounded-md border border-surface-1 text-text hover:bg-crust transition-colors disabled:opacity-50"
        data-testid="refresh-button"
      >
        ↻ Comprobar de nuevo
      </button>
    </div>

    <!-- Estado 1: sin agente detectado -->
    <div
      v-if="!loading && !available"
      class="rounded-lg border border-surface-1 bg-mantle p-8 text-center"
      data-testid="state-not-detected"
    >
      <div class="text-4xl mb-3">📡</div>
      <h2 class="text-lg font-semibold text-text mb-2">No detectamos el agente local</h2>
      <p class="text-sm text-subtext max-w-md mx-auto mb-4">
        El agente es un pequeño programa que se instala en tu ordenador y
        permite que esta web use los escáneres conectados (USB, red).
        Sin él, sólo puedes subir ficheros desde el explorador.
      </p>
      <div class="inline-flex items-center gap-2 px-4 py-2 rounded-md bg-crust border border-surface-1 text-xs text-subtext">
        <span>🚧</span>
        <span>Instaladores Windows / Linux disponibles próximamente</span>
      </div>
    </div>

    <!-- Estado 2: detectado pero sin vincular -->
    <div
      v-else-if="available && !paired"
      class="rounded-lg border border-surface-1 bg-mantle p-6"
      data-testid="state-unpaired"
    >
      <div class="flex items-center gap-2 mb-1">
        <span class="inline-block w-2 h-2 rounded-full bg-warning"></span>
        <span class="text-xs font-medium text-warning">Agente detectado, sin vincular</span>
      </div>
      <h2 class="text-lg font-semibold text-text mb-1">Vincula este equipo</h2>
      <p class="text-sm text-subtext mb-4">
        El agente se vinculará a tu cuenta ({{ status?.version ? `v${status.version}` : '' }}).
        Puedes desvincular cuando quieras desde el agente.
      </p>

      <form @submit.prevent="onPair" class="space-y-3 max-w-md">
        <div>
          <label class="block text-xs font-medium text-text mb-1">
            Nombre de este equipo
          </label>
          <input
            v-model="deviceName"
            type="text"
            placeholder="Ej.: Portátil mostrador, PC sala 2"
            class="w-full px-3 py-2 text-sm rounded-md border border-surface-1 bg-base text-text focus:border-primary focus:outline-none"
            :disabled="pairing"
            data-testid="device-name-input"
          />
          <p class="text-xs text-subtext mt-1">
            Sirve para distinguirlo si vinculas varios equipos.
          </p>
        </div>
        <button
          type="submit"
          :disabled="pairing || !deviceName.trim()"
          class="px-4 py-2 text-sm rounded-md bg-primary text-base font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
          data-testid="pair-button"
        >
          {{ pairing ? 'Vinculando…' : 'Vincular este equipo' }}
        </button>
      </form>
    </div>

    <!-- Estado 3: vinculado -->
    <div
      v-else-if="available && paired"
      class="space-y-4"
      data-testid="state-paired"
    >
      <!-- Tarjeta info -->
      <div class="rounded-lg border border-surface-1 bg-mantle p-6">
        <div class="flex items-center gap-2 mb-3">
          <span class="inline-block w-2 h-2 rounded-full bg-success"></span>
          <span class="text-xs font-medium text-success">Vinculado</span>
        </div>
        <dl class="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <dt class="text-xs text-subtext uppercase tracking-wide">Equipo</dt>
            <dd class="text-sm text-text font-medium mt-1">{{ status?.device_name }}</dd>
          </div>
          <div>
            <dt class="text-xs text-subtext uppercase tracking-wide">Usuario</dt>
            <dd class="text-sm text-text font-medium mt-1">{{ status?.user_email }}</dd>
          </div>
          <div>
            <dt class="text-xs text-subtext uppercase tracking-wide">Inquilino</dt>
            <dd class="text-sm text-text font-medium mt-1">{{ status?.tenant_name }}</dd>
          </div>
        </dl>
      </div>

      <!-- Lista de escáneres -->
      <div class="rounded-lg border border-surface-1 bg-mantle p-6">
        <h2 class="text-base font-semibold text-text mb-3">Escáneres disponibles</h2>
        <ul v-if="scanners.length > 0" class="space-y-2" data-testid="scanner-list">
          <li
            v-for="s in scanners"
            :key="s.name"
            class="flex items-center gap-3 px-3 py-2 rounded-md bg-crust border border-surface-1"
          >
            <span class="text-lg">🖨</span>
            <span class="text-sm text-text font-mono">{{ s.name }}</span>
          </li>
        </ul>
        <p
          v-else
          class="text-sm text-subtext"
          data-testid="no-scanners"
        >
          No se ha detectado ningún escáner. Conecta uno por USB o enciéndelo
          en la red y pulsa "Comprobar de nuevo".
        </p>
        <div
          v-if="store.error"
          class="mt-3 text-xs text-danger"
          data-testid="scanners-error"
        >
          {{ store.error }}
        </div>
        <p class="text-xs text-subtext mt-4 italic">
          Los botones para escanear aparecen al abrir un lote (workbench).
        </p>
      </div>
    </div>

    <!-- Estado loading inicial -->
    <div
      v-else-if="loading"
      class="rounded-lg border border-surface-1 bg-mantle p-8 text-center text-sm text-subtext"
      data-testid="state-loading"
    >
      Comprobando agente local…
    </div>
  </div>
</template>
