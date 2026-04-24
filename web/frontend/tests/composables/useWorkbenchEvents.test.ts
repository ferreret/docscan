import { describe, it, expect, beforeEach, vi } from "vitest";
import { useWorkbenchEvents } from "@/composables/useWorkbenchEvents";
import * as client from "@/api/client";

describe("useWorkbenchEvents", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("fireSync devuelve EventResult del backend", async () => {
    vi.spyOn(client, "fireEvent").mockResolvedValue({
      executed: true,
      result: "ok",
      cancel: false,
      target_page_id: null,
      fields_updated: {},
      batch_fields_updated: {},
      logs: [],
      error: null,
    });
    const events = useWorkbenchEvents(1);
    const res = await events.fireSync("on_batch_loaded", {});
    expect(res.executed).toBe(true);
    expect(res.result).toBe("ok");
  });

  it("fireSync respeta cancel=true", async () => {
    vi.spyOn(client, "fireEvent").mockResolvedValue({
      executed: true,
      result: null,
      cancel: true,
      target_page_id: null,
      fields_updated: {},
      batch_fields_updated: {},
      logs: [],
      error: null,
    });
    const events = useWorkbenchEvents(1);
    const res = await events.fireSync("on_navigate_prev", { page_id: 7 });
    expect(res.cancel).toBe(true);
  });

  it("fireSync propaga target_page_id", async () => {
    vi.spyOn(client, "fireEvent").mockResolvedValue({
      executed: true,
      result: null,
      cancel: false,
      target_page_id: 42,
      fields_updated: {},
      batch_fields_updated: {},
      logs: [],
      error: null,
    });
    const events = useWorkbenchEvents(1);
    const res = await events.fireSync("on_navigate_next", { page_id: 7 });
    expect(res.target_page_id).toBe(42);
  });

  it("fireAsync no bloquea y devuelve undefined", () => {
    vi.spyOn(client, "fireEvent").mockResolvedValue({
      executed: true,
      result: null,
      cancel: false,
      target_page_id: null,
      fields_updated: {},
      batch_fields_updated: {},
      logs: [],
      error: null,
    });
    const events = useWorkbenchEvents(1);
    const r = events.fireAsync("on_page_changed", { page_id: 7 });
    expect(r).toBeUndefined();
  });

  it("fireAsync aplica throttle 100ms para el mismo evento", async () => {
    const spy = vi.spyOn(client, "fireEvent").mockResolvedValue({
      executed: true,
      result: null,
      cancel: false,
      target_page_id: null,
      fields_updated: {},
      batch_fields_updated: {},
      logs: [],
      error: null,
    });
    const events = useWorkbenchEvents(1);
    events.fireAsync("on_page_changed", { page_id: 7 });
    events.fireAsync("on_page_changed", { page_id: 7 });
    events.fireAsync("on_page_changed", { page_id: 7 });
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it("error del backend se captura y devuelve executed=false synthético", async () => {
    vi.spyOn(client, "fireEvent").mockRejectedValue(new Error("network"));
    const events = useWorkbenchEvents(1);
    const res = await events.fireSync("on_batch_loaded", {});
    expect(res.executed).toBe(false);
    expect(res.error).toContain("network");
  });

  it("fields_updated disparan callback onApplyPageFields", async () => {
    vi.spyOn(client, "fireEvent").mockResolvedValue({
      executed: true,
      result: null,
      cancel: false,
      target_page_id: null,
      fields_updated: { cliente: "Acme" },
      batch_fields_updated: {},
      logs: [],
      error: null,
    });
    const onApply = vi.fn();
    const events = useWorkbenchEvents(1, { onApplyPageFields: onApply });
    await events.fireSync("on_page_changed", { page_id: 7 });
    expect(onApply).toHaveBeenCalledWith(7, { cliente: "Acme" });
  });

  it("batch_fields_updated disparan callback onApplyBatchFields", async () => {
    vi.spyOn(client, "fireEvent").mockResolvedValue({
      executed: true,
      result: null,
      cancel: false,
      target_page_id: null,
      fields_updated: {},
      batch_fields_updated: { total: 5 },
      logs: [],
      error: null,
    });
    const onApply = vi.fn();
    const events = useWorkbenchEvents(1, { onApplyBatchFields: onApply });
    await events.fireSync("on_batch_loaded", {});
    expect(onApply).toHaveBeenCalledWith({ total: 5 });
  });
});
