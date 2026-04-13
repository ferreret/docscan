<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import type { BarcodeResponse } from '@/api/types'

const props = defineProps<{
  imageUrl: string
  barcodes?: BarcodeResponse[]
}>()

// --- Estado ---
const src = ref<string | null>(null)
const naturalWidth = ref(0)
const naturalHeight = ref(0)

const ZOOM_MIN = 0.1
const ZOOM_MAX = 10
const ZOOM_STEP = 1.25

const zoom = ref(1)
const offsetX = ref(0)
const offsetY = ref(0)
const viewport = ref<HTMLDivElement | null>(null)
const dragging = ref(false)
let dragOriginX = 0
let dragOriginY = 0
let startOffsetX = 0
let startOffsetY = 0

function resetView() {
  zoom.value = 1
  offsetX.value = 0
  offsetY.value = 0
}

function revoke() {
  if (src.value) {
    URL.revokeObjectURL(src.value)
    src.value = null
  }
}

async function loadImage(url: string) {
  revoke()
  resetView()
  const token = localStorage.getItem('access_token')
  try {
    const res = await fetch(url, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!res.ok) return
    const blob = await res.blob()
    src.value = URL.createObjectURL(blob)
  } catch {
    /* silently */
  }
}

function onImageLoaded(event: Event) {
  const img = event.target as HTMLImageElement
  naturalWidth.value = img.naturalWidth
  naturalHeight.value = img.naturalHeight
  fitToViewport()
}

watch(
  () => props.imageUrl,
  (url) => {
    if (url) loadImage(url)
    else revoke()
  },
  { immediate: true },
)

onUnmounted(revoke)

function fitToViewport() {
  const vp = viewport.value
  if (!vp || naturalWidth.value === 0) return
  const PADDING = 32
  const scale = Math.min(
    (vp.clientWidth - PADDING * 2) / naturalWidth.value,
    (vp.clientHeight - PADDING * 2) / naturalHeight.value,
  )
  zoom.value = scale > 1 ? 1 : scale
  offsetX.value = (vp.clientWidth - naturalWidth.value * zoom.value) / 2
  offsetY.value = (vp.clientHeight - naturalHeight.value * zoom.value) / 2
}

function zoomBy(factor: number, anchorX?: number, anchorY?: number) {
  const newZoom = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, zoom.value * factor))
  if (newZoom === zoom.value) return

  // Mantener punto bajo cursor estable
  if (anchorX !== undefined && anchorY !== undefined) {
    const ratio = newZoom / zoom.value
    offsetX.value = anchorX - (anchorX - offsetX.value) * ratio
    offsetY.value = anchorY - (anchorY - offsetY.value) * ratio
  }

  zoom.value = newZoom
}

function onWheel(e: WheelEvent) {
  e.preventDefault()
  const rect = (e.currentTarget as HTMLDivElement).getBoundingClientRect()
  const x = e.clientX - rect.left
  const y = e.clientY - rect.top
  const factor = e.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP
  zoomBy(factor, x, y)
}

function onMouseDown(e: MouseEvent) {
  if (e.button !== 0) return
  dragging.value = true
  dragOriginX = e.clientX
  dragOriginY = e.clientY
  startOffsetX = offsetX.value
  startOffsetY = offsetY.value
}

function onMouseMove(e: MouseEvent) {
  if (!dragging.value) return
  offsetX.value = startOffsetX + (e.clientX - dragOriginX)
  offsetY.value = startOffsetY + (e.clientY - dragOriginY)
}

function endDrag() {
  dragging.value = false
}

const transform = computed(
  () => `translate(${offsetX.value}px, ${offsetY.value}px) scale(${zoom.value})`,
)

const zoomPercent = computed(() => Math.round(zoom.value * 100))

// --- Overlays ---
const BARCODE_PALETTE = [
  '#e53935', '#1e88e5', '#43a047', '#fb8c00',
  '#8e24aa', '#00acc1', '#d81b60', '#6d4c41',
]

function colorFor(idx: number) {
  return BARCODE_PALETTE[idx % BARCODE_PALETTE.length]
}
</script>

<template>
  <div
    ref="viewport"
    class="relative w-full h-full overflow-hidden bg-crust select-none"
    :class="dragging ? 'cursor-grabbing' : 'cursor-grab'"
    @wheel="onWheel"
    @mousedown="onMouseDown"
    @mousemove="onMouseMove"
    @mouseup="endDrag"
    @mouseleave="endDrag"
  >
    <!-- Imagen + overlays con transform compartido -->
    <div
      class="absolute top-0 left-0 origin-top-left"
      :style="{ transform, width: naturalWidth + 'px', height: naturalHeight + 'px' }"
    >
      <img
        v-if="src"
        :src="src"
        @load="onImageLoaded"
        class="block pointer-events-none"
        draggable="false"
      />

      <!-- Overlays de barcodes -->
      <div
        v-for="(bc, idx) in barcodes ?? []"
        :key="bc.id"
        class="absolute pointer-events-none"
        :style="{
          left: bc.pos_x + 'px',
          top: bc.pos_y + 'px',
          width: bc.pos_w + 'px',
          height: bc.pos_h + 'px',
          border: `2px solid ${colorFor(idx)}`,
          backgroundColor: colorFor(idx) + '22',
        }"
      >
        <span
          class="absolute -top-5 left-0 text-[10px] font-semibold px-1.5 py-0.5 rounded text-white whitespace-nowrap"
          :style="{ backgroundColor: colorFor(idx) }"
        >
          {{ bc.symbology }}: {{ bc.value }}
        </span>
      </div>
    </div>

    <!-- Toolbar overlay -->
    <div class="absolute bottom-3 left-1/2 -translate-x-1/2 flex items-center gap-1 bg-white/95 backdrop-blur border border-surface-1 rounded-lg shadow-md px-2 py-1.5">
      <button
        @click="zoomBy(1 / ZOOM_STEP)"
        class="w-7 h-7 flex items-center justify-center rounded text-text hover:bg-mantle text-base font-semibold"
        title="Reducir"
      >−</button>
      <span class="text-xs text-subtext font-medium min-w-[3rem] text-center">{{ zoomPercent }}%</span>
      <button
        @click="zoomBy(ZOOM_STEP)"
        class="w-7 h-7 flex items-center justify-center rounded text-text hover:bg-mantle text-base font-semibold"
        title="Ampliar"
      >+</button>
      <div class="w-px h-5 bg-surface-1 mx-1"></div>
      <button
        @click="fitToViewport"
        class="px-2 h-7 flex items-center rounded text-text hover:bg-mantle text-xs font-medium"
        title="Ajustar"
      >Ajustar</button>
      <button
        @click="resetView"
        class="px-2 h-7 flex items-center rounded text-text hover:bg-mantle text-xs font-medium"
        title="Tamaño real"
      >1:1</button>
    </div>

    <!-- Loader -->
    <div v-if="!src" class="absolute inset-0 flex items-center justify-center text-subtext text-sm">
      Cargando…
    </div>
  </div>
</template>
