import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { defineComponent, h, ref, type Ref } from "vue";
import { mount } from "@vue/test-utils";
import {
  useBatchesPolling,
  ACTIVE_STATES,
} from "@/composables/useBatchesPolling";
import type { BatchListItem } from "@/api/types";

function makeBatch(id: number, state: string): BatchListItem {
  return {
    id,
    application_id: 1,
    state,
    page_count: 0,
    created_at: "2026-04-29T08:00:00",
  } as BatchListItem;
}

function mountWithPolling(
  items: Ref<BatchListItem[]>,
  refetch: () => Promise<void>,
  intervalMs = 1000,
) {
  const Comp = defineComponent({
    setup() {
      useBatchesPolling(items, refetch, { intervalMs });
      return () => h("div");
    },
  });
  return mount(Comp);
}

describe("useBatchesPolling", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("expone los estados activos como running/transferring", () => {
    expect(ACTIVE_STATES.has("running")).toBe(true);
    expect(ACTIVE_STATES.has("transferring")).toBe(true);
    expect(ACTIVE_STATES.has("read")).toBe(false);
    expect(ACTIVE_STATES.has("created")).toBe(false);
    expect(ACTIVE_STATES.has("transferred")).toBe(false);
  });

  it("no arranca polling si no hay lotes activos", async () => {
    const items = ref<BatchListItem[]>([
      makeBatch(1, "read"),
      makeBatch(2, "created"),
      makeBatch(3, "transferred"),
    ]);
    const refetch = vi.fn(async () => {});
    mountWithPolling(items, refetch, 1000);

    await vi.advanceTimersByTimeAsync(5000);
    expect(refetch).not.toHaveBeenCalled();
  });

  it("arranca polling si al montar hay un lote en running", async () => {
    const items = ref<BatchListItem[]>([
      makeBatch(1, "read"),
      makeBatch(2, "running"),
    ]);
    const refetch = vi.fn(async () => {});
    mountWithPolling(items, refetch, 1000);

    await vi.advanceTimersByTimeAsync(1000);
    expect(refetch).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1000);
    expect(refetch).toHaveBeenCalledTimes(2);
  });

  it("también arranca para state=transferring", async () => {
    const items = ref<BatchListItem[]>([makeBatch(1, "transferring")]);
    const refetch = vi.fn(async () => {});
    mountWithPolling(items, refetch, 1000);

    await vi.advanceTimersByTimeAsync(1000);
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("se detiene cuando el último lote activo pasa a terminal", async () => {
    const items = ref<BatchListItem[]>([makeBatch(1, "running")]);
    let tickCount = 0;
    const refetch = vi.fn(async () => {
      tickCount += 1;
      // Tras el primer refetch simulamos que el backend ya completó.
      if (tickCount === 1) items.value = [makeBatch(1, "read")];
    });
    mountWithPolling(items, refetch, 1000);

    await vi.advanceTimersByTimeAsync(1000);
    expect(refetch).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(5000);
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("arranca dinámicamente cuando aparece un lote activo después", async () => {
    const items = ref<BatchListItem[]>([makeBatch(1, "read")]);
    const refetch = vi.fn(async () => {});
    mountWithPolling(items, refetch, 1000);

    await vi.advanceTimersByTimeAsync(2000);
    expect(refetch).not.toHaveBeenCalled();

    items.value = [makeBatch(1, "read"), makeBatch(2, "running")];
    await vi.advanceTimersByTimeAsync(1000);
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("no se solapan refetches: solo programa el siguiente tras terminar", async () => {
    const items = ref<BatchListItem[]>([makeBatch(1, "running")]);
    let resolveCurrent: (() => void) | null = null;
    const refetch = vi.fn(
      () =>
        new Promise<void>((res) => {
          resolveCurrent = res;
        }),
    );
    mountWithPolling(items, refetch, 1000);

    await vi.advanceTimersByTimeAsync(1000);
    expect(refetch).toHaveBeenCalledTimes(1);
    // Aunque pase mucho más tiempo, no entra otro tick mientras el primero
    // no resuelve.
    await vi.advanceTimersByTimeAsync(5000);
    expect(refetch).toHaveBeenCalledTimes(1);

    resolveCurrent!();
    await Promise.resolve();
    await vi.advanceTimersByTimeAsync(1000);
    expect(refetch).toHaveBeenCalledTimes(2);
  });

  it("silencia errores del refetch (no rompe el polling)", async () => {
    const items = ref<BatchListItem[]>([makeBatch(1, "running")]);
    const refetch = vi
      .fn(async () => {
        throw new Error("boom");
      })
      .mockRejectedValueOnce(new Error("boom"))
      .mockResolvedValueOnce(undefined);
    mountWithPolling(items, refetch, 1000);

    await vi.advanceTimersByTimeAsync(1000);
    expect(refetch).toHaveBeenCalledTimes(1);
    // Pese al error, el polling sigue programando el siguiente tick.
    await vi.advanceTimersByTimeAsync(1000);
    expect(refetch).toHaveBeenCalledTimes(2);
  });

  it("limpia el timer en onUnmounted", async () => {
    const items = ref<BatchListItem[]>([makeBatch(1, "running")]);
    const refetch = vi.fn(async () => {});
    const wrapper = mountWithPolling(items, refetch, 1000);

    await vi.advanceTimersByTimeAsync(1000);
    expect(refetch).toHaveBeenCalledTimes(1);

    wrapper.unmount();
    await vi.advanceTimersByTimeAsync(5000);
    expect(refetch).toHaveBeenCalledTimes(1); // no se ejecutaron más ticks
  });

  it("usa el intervalMs personalizado", async () => {
    const items = ref<BatchListItem[]>([makeBatch(1, "running")]);
    const refetch = vi.fn(async () => {});
    mountWithPolling(items, refetch, 250);

    await vi.advanceTimersByTimeAsync(250);
    expect(refetch).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(250);
    expect(refetch).toHaveBeenCalledTimes(2);
  });
});
