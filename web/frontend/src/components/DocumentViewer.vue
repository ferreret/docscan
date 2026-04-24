<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from "vue";
import type { BarcodeResponse } from "@/api/types";

const props = withDefaults(
  defineProps<{
    imageUrl: string;
    barcodes?: BarcodeResponse[];
    fields?: Record<string, unknown>;
    showBarcodes?: boolean;
    showFields?: boolean;
  }>(),
  {
    barcodes: () => [],
    fields: () => ({}),
    showBarcodes: true,
    showFields: true,
  },
);

// --- Estado ---
const src = ref<string | null>(null);
const naturalWidth = ref(0);
const naturalHeight = ref(0);

const ZOOM_MIN = 0.1;
const ZOOM_MAX = 10;
const ZOOM_STEP = 1.25;

const zoom = ref(1);
const offsetX = ref(0);
const offsetY = ref(0);
const viewport = ref<HTMLDivElement | null>(null);
const dragging = ref(false);
let dragOriginX = 0;
let dragOriginY = 0;
let startOffsetX = 0;
let startOffsetY = 0;

function resetView() {
  zoom.value = 1;
  offsetX.value = 0;
  offsetY.value = 0;
}

function revoke() {
  if (src.value) {
    URL.revokeObjectURL(src.value);
    src.value = null;
  }
}

async function loadImage(url: string) {
  revoke();
  resetView();
  const token = localStorage.getItem("access_token");
  try {
    const res = await fetch(url, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) return;
    const blob = await res.blob();
    src.value = URL.createObjectURL(blob);
  } catch {
    /* silently */
  }
}

function onImageLoaded(event: Event) {
  const img = event.target as HTMLImageElement;
  naturalWidth.value = img.naturalWidth;
  naturalHeight.value = img.naturalHeight;
  fitToViewport();
}

watch(
  () => props.imageUrl,
  (url) => {
    if (url) loadImage(url);
    else revoke();
  },
  { immediate: true },
);

onUnmounted(revoke);

function fitToViewport() {
  const vp = viewport.value;
  if (!vp || naturalWidth.value === 0) return;
  const PADDING = 32;
  const scale = Math.min(
    (vp.clientWidth - PADDING * 2) / naturalWidth.value,
    (vp.clientHeight - PADDING * 2) / naturalHeight.value,
  );
  zoom.value = scale > 1 ? 1 : scale;
  offsetX.value = (vp.clientWidth - naturalWidth.value * zoom.value) / 2;
  offsetY.value = (vp.clientHeight - naturalHeight.value * zoom.value) / 2;
}

function zoomBy(factor: number, anchorX?: number, anchorY?: number) {
  const newZoom = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, zoom.value * factor));
  if (newZoom === zoom.value) return;

  // Mantener punto bajo cursor estable
  if (anchorX !== undefined && anchorY !== undefined) {
    const ratio = newZoom / zoom.value;
    offsetX.value = anchorX - (anchorX - offsetX.value) * ratio;
    offsetY.value = anchorY - (anchorY - offsetY.value) * ratio;
  }

  zoom.value = newZoom;
}

function onWheel(e: WheelEvent) {
  e.preventDefault();
  const rect = (e.currentTarget as HTMLDivElement).getBoundingClientRect();
  const x = e.clientX - rect.left;
  const y = e.clientY - rect.top;
  const factor = e.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP;
  zoomBy(factor, x, y);
}

function onMouseDown(e: MouseEvent) {
  if (e.button !== 0) return;
  dragging.value = true;
  dragOriginX = e.clientX;
  dragOriginY = e.clientY;
  startOffsetX = offsetX.value;
  startOffsetY = offsetY.value;
}

function onMouseMove(e: MouseEvent) {
  if (!dragging.value) return;
  offsetX.value = startOffsetX + (e.clientX - dragOriginX);
  offsetY.value = startOffsetY + (e.clientY - dragOriginY);
}

function endDrag() {
  dragging.value = false;
}

const transform = computed(
  () =>
    `translate(${offsetX.value}px, ${offsetY.value}px) scale(${zoom.value})`,
);

const zoomPercent = computed(() => Math.round(zoom.value * 100));

// --- Overlays ---
const BARCODE_PALETTE = [
  "#e53935",
  "#1e88e5",
  "#43a047",
  "#fb8c00",
  "#8e24aa",
  "#00acc1",
  "#d81b60",
  "#6d4c41",
];

// Paleta Catppuccin para fields (decalada respecto a barcodes).
const FIELD_PALETTE = [
  "#8839ef",
  "#d20f39",
  "#df8e1d",
  "#40a02b",
  "#04a5e5",
  "#1e66f5",
];

function colorFor(idx: number) {
  return BARCODE_PALETTE[idx % BARCODE_PALETTE.length];
}

function fieldColorFor(idx: number) {
  return FIELD_PALETTE[idx % FIELD_PALETTE.length];
}

interface FieldOverlay {
  name: string;
  x: number;
  y: number;
  w: number;
  h: number;
  value: string;
}

const fieldOverlays = computed<FieldOverlay[]>(() => {
  if (!props.fields) return [];
  return Object.entries(props.fields).flatMap(([name, v]) => {
    if (typeof v !== "object" || v === null) return [];
    const o = v as {
      x?: unknown;
      y?: unknown;
      w?: unknown;
      h?: unknown;
      value?: unknown;
    };
    const x = Number(o.x);
    const y = Number(o.y);
    const w = Number(o.w);
    const h = Number(o.h);
    if (!Number.isFinite(x) || !Number.isFinite(y)) return [];
    if (!Number.isFinite(w) || !Number.isFinite(h)) return [];
    if (!(w > 0) || !(h > 0)) return [];
    const value =
      o.value === undefined || o.value === null ? "" : String(o.value);
    return [{ name, x, y, w, h, value }];
  });
});

defineExpose({
  zoomIn: () => zoomBy(1.25),
  zoomOut: () => zoomBy(1 / 1.25),
  zoom100: () => {
    zoom.value = 1;
  },
  fitPage: fitToViewport,
  resetView,
  fitToViewport,
  zoomPercent,
});
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
      :style="{
        transform,
        width: naturalWidth + 'px',
        height: naturalHeight + 'px',
      }"
    >
      <img
        v-if="src"
        :src="src"
        @load="onImageLoaded"
        class="block pointer-events-none"
        draggable="false"
      />

      <!-- Overlays de barcodes -->
      <template v-if="showBarcodes">
        <div
          v-for="(bc, idx) in barcodes ?? []"
          :key="'bc-' + bc.id"
          data-barcode-overlay
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
      </template>

      <!-- Overlays de fields -->
      <template v-if="showFields">
        <div
          v-for="(f, idx) in fieldOverlays"
          :key="'field-' + f.name"
          data-field-overlay
          class="absolute pointer-events-none"
          :style="{
            left: f.x + 'px',
            top: f.y + 'px',
            width: f.w + 'px',
            height: f.h + 'px',
            border: `2px dashed ${fieldColorFor(idx)}`,
            backgroundColor: fieldColorFor(idx) + '22',
          }"
        >
          <span
            class="absolute -top-5 left-0 text-[10px] font-semibold px-1.5 py-0.5 rounded text-white whitespace-nowrap"
            :style="{ backgroundColor: fieldColorFor(idx) }"
          >
            {{ f.value ? `${f.name}: ${f.value}` : f.name }}
          </span>
        </div>
      </template>
    </div>

    <!-- Loader -->
    <div
      v-if="!src"
      class="absolute inset-0 flex items-center justify-center text-subtext text-sm"
    >
      Cargando…
    </div>
  </div>
</template>
