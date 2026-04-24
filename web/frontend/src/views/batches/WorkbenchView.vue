<script setup lang="ts">
import {
  computed,
  onMounted,
  onUnmounted,
  ref,
  useTemplateRef,
  watch,
} from "vue";
import { useRoute, useRouter } from "vue-router";
import { Splitpanes, Pane } from "splitpanes";
import "splitpanes/dist/splitpanes.css";

import { ApiError } from "@/api/client";
import DocumentViewer from "@/components/DocumentViewer.vue";
import ThumbnailPanel from "@/components/workbench/ThumbnailPanel.vue";
import BarcodePanel from "@/components/workbench/BarcodePanel.vue";
import MetadataPanel from "@/components/workbench/MetadataPanel.vue";
import ViewerToolbar from "@/components/workbench/ViewerToolbar.vue";
import WorkbenchToolbar from "@/components/workbench/WorkbenchToolbar.vue";
import ThumbnailContextMenu from "@/components/workbench/ThumbnailContextMenu.vue";
import AddBarcodeDialog from "@/components/workbench/AddBarcodeDialog.vue";
import DeleteBarcodeDialog from "@/components/workbench/DeleteBarcodeDialog.vue";
import { useBatchesStore } from "@/stores/batches";
import { useApplicationsStore } from "@/stores/applications";
import { useToast } from "@/composables/useToast";
import { useWorkbenchLayout } from "@/composables/useWorkbenchLayout";
import { useOverlayToggles } from "@/composables/useOverlayToggles";
import { useWorkbenchLog } from "@/composables/useWorkbenchLog";
import { usePageActions } from "@/composables/usePageActions";
import { useWorkbenchEvents } from "@/composables/useWorkbenchEvents";
import { useWorkbenchShortcuts } from "@/composables/useWorkbenchShortcuts";
import ShortcutsHelpDialog from "@/components/workbench/ShortcutsHelpDialog.vue";
import type { PageListItem, PageResponse } from "@/api/types";

const route = useRoute();
const router = useRouter();
const store = useBatchesStore();
const appStore = useApplicationsStore();
const toast = useToast();
const { sizes, setSizes } = useWorkbenchLayout();
const { showBarcodes, showFields } = useOverlayToggles();
const log = useWorkbenchLog();
const pageActions = usePageActions();

const batchId = computed(() => Number(route.params.id));
const workbenchEvents = useWorkbenchEvents(batchId.value, {
  onApplyPageFields: (pageId, _fields) => {
    void store.fetchPage(batchId.value, pageId);
  },
  onApplyBatchFields: () => {
    void store.fetchOne(batchId.value);
  },
  onLogs: (logs) => {
    logs.forEach((l) => {
      const level =
        l.level === "warning"
          ? "warn"
          : (l.level as "debug" | "info" | "warn" | "error");
      log.append(level, "script", l.message);
    });
  },
});
const selectedPageIndex = ref(0);
const uploading = ref(false);
const running = ref(false);
const transferring = ref(false);
const transferStatus = ref<
  "idle" | "running" | "completed" | "error" | "aborted"
>("idle");
const transferMessage = ref<string | null>(null);
const transferProgress = ref<{ page_index: number; total: number } | null>(
  null,
);
const progress = ref<{ processed: number; total: number } | null>(null);
const error = ref<string | null>(null);
const savingMetadata = ref(false);

// Cache-bust tick: incrementa al rotar para forzar recarga del blob de imagen.
const imageCacheTick = ref(0);

// Modal de ayuda de shortcuts
const helpDialogOpen = ref(false);

// Context menu state
const contextMenuVisible = ref(false);
const contextMenuX = ref(0);
const contextMenuY = ref(0);
const contextMenuPageId = ref(0);

// Barcode dialogs state
const addBarcodeOpen = ref(false);
const deleteBarcodeOpen = ref(false);
const deleteBarcodeTarget = ref<{ id: number; value: string } | null>(null);

const viewerRef =
  useTemplateRef<InstanceType<typeof DocumentViewer>>("viewerRef");

// WebSocket activo (pipeline o transferencia). Se cierra en onUnmounted para
// evitar que handlers tardíos corrompan el estado de otras vistas.
const activeWs = ref<WebSocket | null>(null);

const sortedPages = computed(() =>
  [...(store.pages ?? [])].sort((a, b) => a.page_index - b.page_index),
);
const currentPageListItem = computed<PageListItem | undefined>(
  () => sortedPages.value[selectedPageIndex.value],
);

const currentPage = computed<PageResponse | null>(() => store.currentPage);
const currentImageUrl = computed(() => {
  if (!currentPageListItem.value) return "";
  const base = store.pageImageUrl(batchId.value, currentPageListItem.value.id);
  const tick = imageCacheTick.value;
  return tick > 0 ? `${base}?v=${tick}` : base;
});

const currentFields = computed<Record<string, unknown>>(() => {
  if (!currentPage.value) return {};
  try {
    const parsed = JSON.parse(currentPage.value.index_fields_json || "{}");
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
});

// Read-only cascade when pipeline/transfer está corriendo
const isReadOnly = computed(() => {
  const st = store.current?.state ?? "";
  return st === "running" || st === "transferring";
});

// Context menu page state snapshot
const contextMenuPage = computed<PageResponse | PageListItem | undefined>(
  () => {
    const pid = contextMenuPageId.value;
    if (!pid) return undefined;
    if (currentPage.value?.id === pid) return currentPage.value;
    return sortedPages.value.find((p) => p.id === pid);
  },
);

const contextMenuIsLastPage = computed(() => {
  if (!contextMenuPageId.value) return false;
  const last = sortedPages.value[sortedPages.value.length - 1];
  return last?.id === contextMenuPageId.value;
});

const contextMenuIsExcluded = computed(() => {
  const p = contextMenuPage.value as PageResponse | undefined;
  return !!p?.is_excluded;
});

const contextMenuNeedsReview = computed(
  () => !!contextMenuPage.value?.needs_review,
);

const counters = computed(() => {
  const total = sortedPages.value.length;
  const needsReview = sortedPages.value.filter((p) => p.needs_review).length;
  // withBarcode y separators requieren datos de barcodes de todas las páginas
  // que hoy no están cargados; se quedan en 0 hasta que el backend lo sirva.
  return { total, withBarcode: 0, separators: 0, needsReview };
});

watch(
  () => currentPageListItem.value?.id,
  async (id, oldId) => {
    if (id) await store.fetchPage(batchId.value, id);
    if (id && id !== oldId) {
      workbenchEvents.fireAsync("on_page_changed", { page_id: id });
    }
  },
);

// Cuando las páginas se cargan/cambian, vuelca los errores persistidos al log.
watch(
  () => store.pages,
  (pages) => {
    if (pages && pages.length > 0) {
      // Solo consideramos entradas que tengan processing_errors_json/script_errors_json
      // (PageListItem no los tiene, pero ampliamos aquí con un cast defensivo).
      const withErrors = pages.filter((p) => {
        const ap = p as unknown as {
          processing_errors_json?: string;
          script_errors_json?: string;
        };
        return ap.processing_errors_json || ap.script_errors_json;
      }) as unknown as Array<{
        id: number;
        page_index: number;
        processing_errors_json: string;
        script_errors_json: string;
        updated_at: string;
      }>;
      if (withErrors.length > 0) log.loadPersistedErrors(withErrors);
    }
  },
  { immediate: false },
);

onMounted(async () => {
  await store.fetchOne(batchId.value);
  await store.fetchPages(batchId.value);
  if (store.current?.application_id)
    await appStore.fetchOne(store.current.application_id);
  if (sortedPages.value.length > 0) {
    await store.fetchPage(batchId.value, sortedPages.value[0].id);
  }
  const loaded = await workbenchEvents.fireSync("on_batch_loaded");
  if (loaded.cancel) {
    toast.error("Carga del lote cancelada por script");
    router.push("/batches");
    return;
  }
});

onUnmounted(() => {
  // Cierra cualquier WebSocket activo para que handlers tardíos no muten estado
  // de otras vistas tras navegar fuera del Workbench.
  activeWs.value?.close();
  activeWs.value = null;
});

function openWs(): WebSocket {
  const token = localStorage.getItem("access_token") ?? "";
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return new WebSocket(
    `${proto}://${window.location.host}/ws/batches/${batchId.value}?token=${encodeURIComponent(token)}`,
  );
}

async function onUpload(files: File[]): Promise<void> {
  uploading.value = true;
  error.value = null;
  try {
    await store.uploadFiles(batchId.value, files);
    await store.fetchOne(batchId.value);
  } catch (e) {
    error.value = e instanceof ApiError ? e.detail : "Error al subir ficheros";
    toast.error(error.value!);
  } finally {
    uploading.value = false;
  }
}

async function onRunPipeline(): Promise<void> {
  running.value = true;
  error.value = null;
  progress.value = null;
  const ws = openWs();
  activeWs.value = ws;
  ws.onmessage = async (msg) => {
    // Early-return si el componente se desmontó o se abrió otra WS.
    if (activeWs.value !== ws) return;
    const event = JSON.parse(msg.data);
    log.appendFromEvent(event);
    if (event.type === "pipeline_started") {
      progress.value = { processed: 0, total: event.total_pages };
      await store.fetchOne(batchId.value);
    } else if (event.type === "page_processed") {
      progress.value = { processed: event.processed, total: event.total };
    } else if (event.type === "pipeline_completed") {
      await Promise.all([
        store.fetchOne(batchId.value),
        store.fetchPages(batchId.value),
      ]);
      if (currentPageListItem.value)
        await store.fetchPage(batchId.value, currentPageListItem.value.id);
      running.value = false;
      progress.value = null;
      ws.close();
      if (activeWs.value === ws) activeWs.value = null;
      toast[event.any_error ? "error" : "success"](
        event.any_error ? "Pipeline con errores" : "Pipeline completado",
      );
      if (appStore.current?.auto_transfer && store.current?.state === "read") {
        await onTransfer();
      }
    } else if (event.type === "pipeline_error") {
      error.value = `Error pipeline: ${event.error}`;
      running.value = false;
      progress.value = null;
      ws.close();
      if (activeWs.value === ws) activeWs.value = null;
      toast.error(error.value);
    } else if (event.type === "page_updated") {
      // Refrescar datos del lote y de la página afectada
      await store.fetchOne(batchId.value);
      await store.fetchPages(batchId.value);
      if (currentPageListItem.value?.id === event.page_id) {
        await store.fetchPage(batchId.value, event.page_id);
      }
    }
  };
  ws.onerror = () => {
    error.value = "Error de conexión";
    running.value = false;
  };
  try {
    await new Promise<void>((resolve, reject) => {
      ws.onopen = () => resolve();
      ws.addEventListener("error", () => reject(new Error("ws")), {
        once: true,
      });
    });
    await store.runPipeline(batchId.value);
  } catch (e) {
    error.value =
      e instanceof ApiError ? e.detail : "Error al ejecutar pipeline";
    running.value = false;
    ws.close();
    if (activeWs.value === ws) activeWs.value = null;
  }
}

async function onTransfer(): Promise<void> {
  if (transferring.value) return;
  transferring.value = true;
  transferStatus.value = "running";
  transferMessage.value = null;
  transferProgress.value = null;
  const ws = openWs();
  activeWs.value = ws;
  ws.onmessage = async (msg) => {
    // Early-return si el componente se desmontó o se abrió otra WS.
    if (activeWs.value !== ws) return;
    const event = JSON.parse(msg.data);
    log.appendFromEvent(event);
    if (event.type === "transfer_started") {
      transferProgress.value = { page_index: 0, total: event.total_pages };
      await store.fetchOne(batchId.value);
    } else if (event.type === "transfer_page" && transferProgress.value) {
      transferProgress.value = {
        page_index: event.page_index + 1,
        total: transferProgress.value.total,
      };
    } else if (event.type === "transfer_completed") {
      transferring.value = false;
      ws.close();
      if (activeWs.value === ws) activeWs.value = null;
      transferStatus.value = event.success ? "completed" : "error";
      transferMessage.value = event.success
        ? event.output_path
          ? `Transferencia → ${event.output_path}`
          : "Transferencia completada"
        : event.errors?.join("; ") || "Error en transferencia";
      toast[event.success ? "success" : "error"](transferMessage.value!);
      transferProgress.value = null;
      await store.fetchOne(batchId.value);
    } else if (event.type === "transfer_error") {
      transferring.value = false;
      transferStatus.value = "error";
      transferMessage.value = `Error: ${event.error}`;
      transferProgress.value = null;
      ws.close();
      if (activeWs.value === ws) activeWs.value = null;
      toast.error(transferMessage.value);
    } else if (event.type === "transfer_aborted") {
      transferring.value = false;
      transferStatus.value = "aborted";
      transferMessage.value = `Transferencia abortada: ${event.reason}`;
      transferProgress.value = null;
      ws.close();
      if (activeWs.value === ws) activeWs.value = null;
      toast.error(transferMessage.value);
    }
  };
  ws.onerror = () => {
    transferring.value = false;
    transferStatus.value = "error";
    transferMessage.value = "Error de conexión durante la transferencia";
  };
  try {
    await new Promise<void>((resolve, reject) => {
      ws.onopen = () => resolve();
      ws.addEventListener("error", () => reject(new Error("ws transfer")), {
        once: true,
      });
    });
    const token = localStorage.getItem("access_token") ?? "";
    const res = await fetch(`/api/batches/${batchId.value}/transfer`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(body.detail || `Error ${res.status}`);
    }
  } catch (e) {
    transferring.value = false;
    transferStatus.value = "error";
    transferMessage.value =
      e instanceof Error ? e.message : "Error al iniciar transferencia";
    ws.close();
    if (activeWs.value === ws) activeWs.value = null;
    toast.error(transferMessage.value!);
  }
}

async function onDownloadZip(): Promise<void> {
  const token = localStorage.getItem("access_token") ?? "";
  const res = await fetch(`/api/batches/${batchId.value}/export`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    toast.error("Error al descargar ZIP");
    return;
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `batch_${batchId.value}.zip`;
  a.click();
  URL.revokeObjectURL(url);
}

async function onDeleteBatch(): Promise<void> {
  if (!confirm("¿Eliminar este lote? Esta acción no se puede deshacer."))
    return;
  await store.remove(batchId.value);
  router.push("/batches");
}

async function onSaveMetadata(fields: Record<string, unknown>): Promise<void> {
  if (!store.current) return;
  savingMetadata.value = true;
  try {
    await fetch(`/api/batches/${batchId.value}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}`,
      },
      body: JSON.stringify({ fields_json: JSON.stringify(fields) }),
    });
    await store.fetchOne(batchId.value);
    toast.success("Lote guardado");
  } catch (e) {
    toast.error(e instanceof Error ? e.message : "Error al guardar");
  } finally {
    savingMetadata.value = false;
  }
}

function onColumnsResize(panes: Array<{ size: number }>): void {
  setSizes({
    columns: panes.map((p) => p.size) as [number, number, number],
    rightVertical: sizes.value.rightVertical,
  });
}

function onRightResize(panes: Array<{ size: number }>): void {
  setSizes({
    columns: sizes.value.columns,
    rightVertical: panes.map((p) => p.size) as [number, number],
  });
}

// --- Page actions handlers (Fase 3) ---

function handleApiError(e: unknown, fallback: string): void {
  if (e instanceof ApiError) {
    if (e.status === 409) {
      toast.error("El lote está en ejecución, no se puede modificar");
    } else if (e.status === 404) {
      toast.error("Recurso no encontrado");
    } else {
      toast.error(e.detail || fallback);
    }
  } else {
    toast.error(e instanceof Error ? e.message : fallback);
  }
}

function onThumbContextMenu(pageId: number, x: number, y: number): void {
  if (isReadOnly.value) return;
  contextMenuPageId.value = pageId;
  contextMenuX.value = x;
  contextMenuY.value = y;
  contextMenuVisible.value = true;
}

function closeContextMenu(): void {
  contextMenuVisible.value = false;
}

async function refreshPages(): Promise<void> {
  await store.fetchPages(batchId.value);
  if (currentPageListItem.value?.id) {
    await store.fetchPage(batchId.value, currentPageListItem.value.id);
  }
}

async function onContextMenuAction(
  type: "toggle-excluded" | "toggle-review" | "delete-page" | "delete-after",
  pageId: number,
): Promise<void> {
  try {
    if (type === "toggle-excluded") {
      const p = sortedPages.value.find((x) => x.id === pageId) as
        | PageResponse
        | undefined;
      const next = !(p?.is_excluded ?? false);
      await pageActions.toggleExcluded(pageId, next);
      log.append(
        "info",
        "user",
        `Página ${pageId} ${next ? "excluida" : "incluida"}`,
      );
      await refreshPages();
    } else if (type === "toggle-review") {
      const p = sortedPages.value.find((x) => x.id === pageId);
      const next = !(p?.needs_review ?? false);
      await pageActions.toggleReview(pageId, next);
      log.append(
        "info",
        "user",
        `Página ${pageId} ${next ? "marcada para revisión" : "revisión retirada"}`,
      );
      await refreshPages();
    } else if (type === "delete-page") {
      if (!confirm("¿Eliminar esta página?")) return;
      await pageActions.deletePage(batchId.value, pageId);
      log.append("info", "user", `Página ${pageId} eliminada`);
      selectedPageIndex.value = Math.max(0, selectedPageIndex.value - 1);
      await refreshPages();
      await store.fetchOne(batchId.value);
    } else if (type === "delete-after") {
      if (!confirm("¿Eliminar desde esta página hasta el final?")) return;
      await pageActions.deleteFromPage(batchId.value, pageId);
      log.append("info", "user", `Páginas eliminadas desde ${pageId}`);
      await refreshPages();
      await store.fetchOne(batchId.value);
    }
  } catch (e) {
    handleApiError(e, "Error al actualizar la página");
  }
}

async function onReorder(newOrder: number[]): Promise<void> {
  try {
    await pageActions.reorderPages(batchId.value, newOrder);
    log.append("info", "user", "Orden de páginas actualizado");
    await refreshPages();
  } catch (e) {
    handleApiError(e, "Error al reordenar");
    // Rollback: refetch desde el backend recupera el orden auténtico.
    await store.fetchPages(batchId.value);
  }
}

async function onRotate(turns: number): Promise<void> {
  const pid = currentPageListItem.value?.id;
  if (!pid) return;
  try {
    await pageActions.rotatePage(pid, turns);
    imageCacheTick.value = Date.now();
    log.append("info", "user", `Página ${pid} rotada ${turns * 90}°`);
    await store.fetchPage(batchId.value, pid);
  } catch (e) {
    handleApiError(e, "Error al rotar la página");
  }
}

function onToggleBarcodes(): void {
  showBarcodes.value = !showBarcodes.value;
}

function onToggleFields(): void {
  showFields.value = !showFields.value;
}

function onAddBarcodeClick(): void {
  if (isReadOnly.value) return;
  addBarcodeOpen.value = true;
}

async function onAddBarcodeSubmit(data: {
  value: string;
  symbology: string;
}): Promise<void> {
  const pid = currentPageListItem.value?.id;
  if (!pid) return;
  try {
    await pageActions.addBarcode(pid, data.value, data.symbology);
    log.append(
      "info",
      "user",
      `Barcode añadido a página ${pid}: ${data.value}`,
    );
    addBarcodeOpen.value = false;
    await store.fetchPage(batchId.value, pid);
  } catch (e) {
    handleApiError(e, "Error al añadir barcode");
  }
}

function onDeleteBarcodeClick(id: number): void {
  if (isReadOnly.value) return;
  const bc = currentPage.value?.barcodes?.find((b) => b.id === id);
  if (!bc) return;
  deleteBarcodeTarget.value = { id, value: bc.value };
  deleteBarcodeOpen.value = true;
}

async function onDeleteBarcodeConfirm(): Promise<void> {
  const pid = currentPageListItem.value?.id;
  const target = deleteBarcodeTarget.value;
  if (!pid || !target) return;
  try {
    await pageActions.deleteBarcode(pid, target.id);
    log.append(
      "info",
      "user",
      `Barcode ${target.value} eliminado de página ${pid}`,
    );
    deleteBarcodeOpen.value = false;
    deleteBarcodeTarget.value = null;
    await store.fetchPage(batchId.value, pid);
  } catch (e) {
    handleApiError(e, "Error al eliminar barcode");
  }
}

// --- Navegación prev/next con soporte de on_navigate_prev / on_navigate_next ---

async function goPrev(): Promise<void> {
  const currentId = currentPageListItem.value?.id;
  if (!currentId) return;
  const res = await workbenchEvents.fireSync("on_navigate_prev", {
    page_id: currentId,
  });
  if (res.cancel) return;
  if (res.target_page_id != null) {
    const idx = sortedPages.value.findIndex((p) => p.id === res.target_page_id);
    if (idx >= 0) selectedPageIndex.value = idx;
    return;
  }
  if (selectedPageIndex.value > 0) selectedPageIndex.value--;
}

async function goNext(): Promise<void> {
  const currentId = currentPageListItem.value?.id;
  if (!currentId) return;
  const res = await workbenchEvents.fireSync("on_navigate_next", {
    page_id: currentId,
  });
  if (res.cancel) return;
  if (res.target_page_id != null) {
    const idx = sortedPages.value.findIndex((p) => p.id === res.target_page_id);
    if (idx >= 0) selectedPageIndex.value = idx;
    return;
  }
  if (selectedPageIndex.value < sortedPages.value.length - 1)
    selectedPageIndex.value++;
}

// --- Helpers para shortcuts ---

async function refreshCurrent(): Promise<void> {
  if (currentPageListItem.value) {
    await store.fetchPage(batchId.value, currentPageListItem.value.id);
  }
}

function goNextReview(): void {
  const from = selectedPageIndex.value;
  const i = sortedPages.value.findIndex(
    (p, idx) => idx > from && p.needs_review,
  );
  if (i >= 0) selectedPageIndex.value = i;
}

async function onDeletePage(pageId: number): Promise<void> {
  if (!confirm("¿Eliminar esta página?")) return;
  try {
    await pageActions.deletePage(batchId.value, pageId);
    log.append("info", "user", `Página ${pageId} eliminada`);
    selectedPageIndex.value = Math.max(0, selectedPageIndex.value - 1);
    await store.fetchPages(batchId.value);
    await store.fetchOne(batchId.value);
  } catch (e) {
    handleApiError(e, "Error al eliminar la página");
  }
}

// --- Wiring de shortcuts de teclado ---

useWorkbenchShortcuts({
  isReadOnly: () => isReadOnly.value,
  fireKeyEvent: (key) => workbenchEvents.fireAsync("on_key_event", { key }),
  handlers: {
    runPipeline: () => onRunPipeline(),
    transfer: () => onTransfer(),
    closeBatch: () => router.push("/batches"),
    openHelp: () => {
      helpDialogOpen.value = true;
    },
    rotate: async () => {
      if (!currentPageListItem.value) return;
      await pageActions.rotatePage(currentPageListItem.value.id, 1);
      imageCacheTick.value = Date.now();
      await refreshCurrent();
    },
    toggleReview: async () => {
      if (!currentPageListItem.value || !currentPage.value) return;
      await pageActions.toggleReview(
        currentPageListItem.value.id,
        !currentPage.value.needs_review,
      );
      await refreshCurrent();
      await store.fetchPages(batchId.value);
    },
    toggleExcluded: async () => {
      if (!currentPageListItem.value || !currentPage.value) return;
      await pageActions.toggleExcluded(
        currentPageListItem.value.id,
        !currentPage.value.is_excluded,
      );
      await refreshCurrent();
      await store.fetchPages(batchId.value);
    },
    reprocessPage: async () => {
      if (!currentPageListItem.value) return;
      await pageActions.reprocessPage(currentPageListItem.value.id);
      await refreshCurrent();
    },
    insertBarcode: () => {
      addBarcodeOpen.value = true;
    },
    deletePage: () => {
      if (currentPageListItem.value)
        void onDeletePage(currentPageListItem.value.id);
    },
    prevPage: () => goPrev(),
    nextPage: () => goNext(),
    nextReviewPage: () => goNextReview(),
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    navigateScript: () =>
      workbenchEvents.fireAsync("on_navigate_script" as any, {
        page_id: currentPageListItem.value?.id ?? null,
      }),
    zoom100: () => viewerRef.value?.zoom100?.(),
    zoomIn: () => viewerRef.value?.zoomIn?.(),
    zoomOut: () => viewerRef.value?.zoomOut?.(),
    fitPage: () => viewerRef.value?.fitPage?.(),
  },
});
</script>

<template>
  <div class="h-screen flex flex-col bg-base text-text">
    <WorkbenchToolbar
      v-if="store.current"
      :batch="store.current"
      :running="running"
      :transferring="transferring"
      :uploading="uploading"
      @upload="onUpload"
      @run-pipeline="onRunPipeline"
      @transfer="onTransfer"
      @download-zip="onDownloadZip"
      @delete-batch="onDeleteBatch"
      @help="helpDialogOpen = true"
    />
    <div v-if="error" class="bg-danger-soft text-danger text-xs px-4 py-1">
      {{ error }}
    </div>
    <div v-if="progress" class="bg-primary-soft text-primary text-xs px-4 py-1">
      Procesando {{ progress.processed }}/{{ progress.total }}…
    </div>
    <div
      v-if="transferProgress"
      class="bg-warning-soft text-warning text-xs px-4 py-1"
    >
      Transfiriendo {{ transferProgress.page_index }}/{{
        transferProgress.total
      }}…
    </div>

    <Splitpanes class="flex-1" @resized="onColumnsResize">
      <Pane :size="sizes.columns[0]" :min-size="8">
        <ThumbnailPanel
          :pages="sortedPages"
          :batchId="batchId"
          :currentIndex="selectedPageIndex"
          :readOnly="isReadOnly"
          @select="(i) => (selectedPageIndex = i)"
          @fit="viewerRef?.fitToViewport()"
          @reorder="onReorder"
          @contextmenu="onThumbContextMenu"
        />
      </Pane>
      <Pane :size="sizes.columns[1]" :min-size="20">
        <div class="relative h-full">
          <DocumentViewer
            ref="viewerRef"
            :imageUrl="currentImageUrl"
            :barcodes="currentPage?.barcodes"
            :fields="currentFields"
            :showBarcodes="showBarcodes"
            :showFields="showFields"
          />
          <ViewerToolbar
            v-if="viewerRef"
            :zoom-percent="viewerRef.zoomPercent ?? 100"
            :canRotate="!isReadOnly"
            :showBarcodes="showBarcodes"
            :showFields="showFields"
            @zoom-in="viewerRef.zoomIn()"
            @zoom-out="viewerRef.zoomOut()"
            @reset="viewerRef.resetView()"
            @fit="viewerRef.fitToViewport()"
            @rotate="onRotate"
            @toggle-barcodes="onToggleBarcodes"
            @toggle-fields="onToggleFields"
          />
        </div>
      </Pane>
      <Pane :size="sizes.columns[2]" :min-size="20">
        <Splitpanes horizontal @resized="onRightResize">
          <Pane :size="sizes.rightVertical[0]" :min-size="20">
            <BarcodePanel
              :barcodes="currentPage?.barcodes ?? []"
              :pageCounters="counters"
              :readOnly="isReadOnly"
              @add-barcode="onAddBarcodeClick"
              @delete-barcode="onDeleteBarcodeClick"
            />
          </Pane>
          <Pane :size="sizes.rightVertical[1]" :min-size="20">
            <MetadataPanel
              :app="appStore.current"
              :batch="store.current"
              :saving="savingMetadata"
              @save="onSaveMetadata"
            />
          </Pane>
        </Splitpanes>
      </Pane>
    </Splitpanes>

    <!-- Menú contextual de thumbnails -->
    <ThumbnailContextMenu
      :visible="contextMenuVisible"
      :x="contextMenuX"
      :y="contextMenuY"
      :pageId="contextMenuPageId"
      :isExcluded="contextMenuIsExcluded"
      :needsReview="contextMenuNeedsReview"
      :readOnly="isReadOnly"
      :isLastPage="contextMenuIsLastPage"
      @action="onContextMenuAction"
      @close="closeContextMenu"
    />

    <!-- Diálogos de barcode -->
    <AddBarcodeDialog
      :visible="addBarcodeOpen"
      @submit="onAddBarcodeSubmit"
      @close="addBarcodeOpen = false"
    />
    <DeleteBarcodeDialog
      :visible="deleteBarcodeOpen"
      :barcodeValue="deleteBarcodeTarget?.value ?? ''"
      @confirm="onDeleteBarcodeConfirm"
      @close="
        deleteBarcodeOpen = false;
        deleteBarcodeTarget = null;
      "
    />

    <!-- Modal de ayuda de atajos de teclado -->
    <ShortcutsHelpDialog
      :is-open="helpDialogOpen"
      @close="helpDialogOpen = false"
    />
  </div>
</template>

<style>
.splitpanes--vertical > .splitpanes__splitter {
  min-width: 4px;
  background-color: var(--color-surface-0);
}
.splitpanes--horizontal > .splitpanes__splitter {
  min-height: 4px;
  background-color: var(--color-surface-0);
}
.splitpanes__splitter:hover {
  background-color: var(--color-surface-1);
}
</style>
