import { onMounted, onUnmounted, watch, type Ref } from "vue";
import type { BatchListItem } from "@/api/types";

/**
 * Estados que indican que un lote está siendo procesado en background
 * y por tanto su `state` puede cambiar sin que el frontend lo provoque.
 * El listado debe poll-refrescarse mientras al menos un lote esté en
 * uno de estos estados.
 */
export const ACTIVE_STATES: ReadonlySet<string> = new Set([
  "running",
  "transferring",
]);

export interface BatchesPollingOptions {
  /** Intervalo entre ticks en ms. Default 4000 (4s). */
  intervalMs?: number;
}

/**
 * Polling condicional para el listado de lotes: refetch silencioso
 * cada N segundos mientras haya algún lote en estado activo.
 *
 * Garantías:
 * - El polling NO arranca si no hay ningún lote activo (no consume red
 *   sin motivo).
 * - El polling se detiene automáticamente cuando el último lote activo
 *   pasa a estado terminal.
 * - Solo se programa el siguiente tick cuando termina el actual (no se
 *   solapan refetches con `setInterval`).
 * - Si llegan errores en el refetch (ej. 401, red caída), se silencian
 *   — el listado mantiene su data anterior y el siguiente tick reintenta.
 * - Cleanup completo en `onUnmounted`: cancela timers y stoppea el
 *   watcher.
 *
 * @param items - ref reactivo al array de lotes (`store.items`).
 * @param refetch - callback que recarga el listado (silencioso).
 * @param options.intervalMs - intervalo entre ticks. Default 4000.
 */
export function useBatchesPolling(
  items: Ref<BatchListItem[]>,
  refetch: () => Promise<void>,
  options: BatchesPollingOptions = {},
): void {
  const intervalMs = options.intervalMs ?? 4000;
  let timerId: ReturnType<typeof setTimeout> | null = null;
  let stopped = false;

  function hasActiveBatches(): boolean {
    return items.value.some((b) => ACTIVE_STATES.has(b.state));
  }

  async function tick(): Promise<void> {
    timerId = null;
    if (stopped) return;
    try {
      await refetch();
    } catch {
      // Silenciar errores transitorios (red, 5xx). El siguiente tick lo
      // reintenta. Errores 401 ya redirigen a /login desde el cliente API.
    }
    if (stopped) return;
    if (hasActiveBatches()) {
      schedule();
    }
  }

  function schedule(): void {
    if (stopped || timerId !== null) return;
    timerId = setTimeout(tick, intervalMs);
  }

  function maybeStart(): void {
    if (timerId !== null) return; // ya hay un tick pendiente
    if (hasActiveBatches()) schedule();
  }

  // Cuando cambia el array (por refetch inicial o tras un tick), arrancar
  // el polling si han aparecido lotes activos. Si todos los activos han
  // pasado a terminal, el `tick()` ya no programa el siguiente.
  const stopWatch = watch(items, () => maybeStart(), { deep: true });

  onMounted(maybeStart);

  onUnmounted(() => {
    stopped = true;
    if (timerId !== null) {
      clearTimeout(timerId);
      timerId = null;
    }
    stopWatch();
  });
}
