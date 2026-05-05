import { ref, type ComputedRef, type Ref } from "vue";

import { ApiError } from "@/api/client";
import type { useApplicationsStore } from "@/stores/applications";
import type { useBatchesStore } from "@/stores/batches";
import type { useToast } from "@/composables/useToast";
import type { useWorkbenchLog } from "@/composables/useWorkbenchLog";
import type { PageListItem } from "@/api/types";

export type TransferStatus =
  | "idle"
  | "running"
  | "completed"
  | "error"
  | "aborted";

interface WsDeps {
  store: ReturnType<typeof useBatchesStore>;
  appStore: ReturnType<typeof useApplicationsStore>;
  toast: ReturnType<typeof useToast>;
  log: ReturnType<typeof useWorkbenchLog>;
  currentPageListItem: ComputedRef<PageListItem | undefined>;
  // Refs compartidos con el componente que se mutan dentro/fuera del composable.
  running: Ref<boolean>;
  error: Ref<string | null>;
  progress: Ref<{ processed: number; total: number } | null>;
  transferring: Ref<boolean>;
  transferStatus: Ref<TransferStatus>;
  transferMessage: Ref<string | null>;
  transferProgress: Ref<{ page_index: number; total: number } | null>;
}

/**
 * Encapsula la apertura de WebSocket y los handlers de eventos del Workbench
 * para `runPipeline` y `transfer`. La guarda `activeWs` previene que handlers
 * tardíos muten estado tras desmontar/abrir otra conexión.
 */
export function useWorkbenchWebSocket(batchId: Ref<number>, deps: WsDeps) {
  const activeWs = ref<WebSocket | null>(null);

  function openWs(): WebSocket {
    const token = localStorage.getItem("access_token") ?? "";
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    return new WebSocket(
      `${proto}://${window.location.host}/ws/batches/${batchId.value}?token=${encodeURIComponent(token)}`,
    );
  }

  function close(): void {
    activeWs.value?.close();
    activeWs.value = null;
  }

  async function runPipeline(): Promise<void> {
    const { store, appStore, toast, log, currentPageListItem } = deps;
    deps.running.value = true;
    deps.error.value = null;
    deps.progress.value = null;
    const ws = openWs();
    activeWs.value = ws;
    ws.onmessage = async (msg) => {
      if (activeWs.value !== ws) return;
      const event = JSON.parse(msg.data);
      log.appendFromEvent(event);
      if (event.type === "pipeline_started") {
        deps.progress.value = { processed: 0, total: event.total_pages };
        await store.fetchOne(batchId.value);
      } else if (event.type === "page_processed") {
        deps.progress.value = {
          processed: event.processed,
          total: event.total,
        };
      } else if (event.type === "pipeline_completed") {
        await Promise.all([
          store.fetchOne(batchId.value),
          store.fetchPages(batchId.value),
        ]);
        if (currentPageListItem.value)
          await store.fetchPage(batchId.value, currentPageListItem.value.id);
        deps.running.value = false;
        deps.progress.value = null;
        ws.close();
        if (activeWs.value === ws) activeWs.value = null;
        toast[event.any_error ? "error" : "success"](
          event.any_error ? "Pipeline con errores" : "Pipeline completado",
        );
        if (appStore.current?.auto_transfer && store.current?.state === "read") {
          await transfer();
        }
      } else if (event.type === "pipeline_error") {
        deps.error.value = `Error pipeline: ${event.error}`;
        deps.running.value = false;
        deps.progress.value = null;
        ws.close();
        if (activeWs.value === ws) activeWs.value = null;
        toast.error(deps.error.value);
      } else if (event.type === "page_updated") {
        await store.fetchOne(batchId.value);
        await store.fetchPages(batchId.value);
        if (currentPageListItem.value?.id === event.page_id) {
          await store.fetchPage(batchId.value, event.page_id);
        }
      }
    };
    ws.onerror = () => {
      deps.error.value = "Error de conexión";
      deps.running.value = false;
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
      deps.error.value =
        e instanceof ApiError ? e.detail : "Error al ejecutar pipeline";
      deps.running.value = false;
      ws.close();
      if (activeWs.value === ws) activeWs.value = null;
    }
  }

  async function transfer(): Promise<void> {
    if (deps.transferring.value) return;
    const { store, toast, log } = deps;
    deps.transferring.value = true;
    deps.transferStatus.value = "running";
    deps.transferMessage.value = null;
    deps.transferProgress.value = null;
    const ws = openWs();
    activeWs.value = ws;
    ws.onmessage = async (msg) => {
      if (activeWs.value !== ws) return;
      const event = JSON.parse(msg.data);
      log.appendFromEvent(event);
      if (event.type === "transfer_started") {
        deps.transferProgress.value = {
          page_index: 0,
          total: event.total_pages,
        };
        await store.fetchOne(batchId.value);
      } else if (event.type === "transfer_page" && deps.transferProgress.value) {
        deps.transferProgress.value = {
          page_index: event.page_index + 1,
          total: deps.transferProgress.value.total,
        };
      } else if (event.type === "transfer_completed") {
        deps.transferring.value = false;
        ws.close();
        if (activeWs.value === ws) activeWs.value = null;
        deps.transferStatus.value = event.success ? "completed" : "error";
        deps.transferMessage.value = event.success
          ? event.output_path
            ? `Transferencia → ${event.output_path}`
            : "Transferencia completada"
          : event.errors?.join("; ") || "Error en transferencia";
        toast[event.success ? "success" : "error"](
          deps.transferMessage.value!,
        );
        deps.transferProgress.value = null;
        await store.fetchOne(batchId.value);
      } else if (event.type === "transfer_error") {
        deps.transferring.value = false;
        deps.transferStatus.value = "error";
        deps.transferMessage.value = `Error: ${event.error}`;
        deps.transferProgress.value = null;
        ws.close();
        if (activeWs.value === ws) activeWs.value = null;
        toast.error(deps.transferMessage.value);
      } else if (event.type === "transfer_aborted") {
        deps.transferring.value = false;
        deps.transferStatus.value = "aborted";
        deps.transferMessage.value = `Transferencia abortada: ${event.reason}`;
        deps.transferProgress.value = null;
        ws.close();
        if (activeWs.value === ws) activeWs.value = null;
        toast.error(deps.transferMessage.value);
      }
    };
    ws.onerror = () => {
      deps.transferring.value = false;
      deps.transferStatus.value = "error";
      deps.transferMessage.value =
        "Error de conexión durante la transferencia";
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
      deps.transferring.value = false;
      deps.transferStatus.value = "error";
      deps.transferMessage.value =
        e instanceof Error ? e.message : "Error al iniciar transferencia";
      ws.close();
      if (activeWs.value === ws) activeWs.value = null;
      toast.error(deps.transferMessage.value!);
    }
  }

  return { runPipeline, transfer, close };
}
