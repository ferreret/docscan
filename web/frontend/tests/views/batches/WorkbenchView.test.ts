import { describe, it, expect, beforeEach, vi } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { mount, flushPromises } from "@vue/test-utils";
import { createRouter, createMemoryHistory } from "vue-router";
import WorkbenchView from "@/views/batches/WorkbenchView.vue";
import { useBatchesStore } from "@/stores/batches";
import { useApplicationsStore } from "@/stores/applications";
import { useWorkbenchLog } from "@/composables/useWorkbenchLog";
import ThumbnailPanel from "@/components/workbench/ThumbnailPanel.vue";
import BarcodePanel from "@/components/workbench/BarcodePanel.vue";
import ViewerToolbar from "@/components/workbench/ViewerToolbar.vue";
import ThumbnailContextMenu from "@/components/workbench/ThumbnailContextMenu.vue";
import AddBarcodeDialog from "@/components/workbench/AddBarcodeDialog.vue";
import DeleteBarcodeDialog from "@/components/workbench/DeleteBarcodeDialog.vue";
import * as client from "@/api/client";
import MetadataPanel from "@/components/workbench/MetadataPanel.vue";
import { useToast } from "@/composables/useToast";

function makeRouter(initial = "/batches/1") {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/batches", component: { template: "<div/>" } },
      { path: "/batches/:id", component: WorkbenchView, props: true },
    ],
  });
  router.push(initial);
  return router;
}

describe("WorkbenchView", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
    // Aislamiento del log global entre tests: evita fugas de entradas.
    const log = useWorkbenchLog();
    log.clear();
    log.filterLevel.value = "debug";
  });

  it("mounts and calls store.fetchOne + fetchPages on the route batchId", async () => {
    const batches = useBatchesStore();
    const apps = useApplicationsStore();
    batches.fetchOne = vi.fn(async () => {
      batches.current = {
        id: 1,
        application_id: 5,
        state: "read",
        page_count: 0,
        created_at: "",
        updated_at: "",
        fields_json: "{}",
        folder_path: "",
        hostname: "",
      };
    });
    batches.fetchPages = vi.fn(async () => {
      batches.pages = [];
    });
    apps.fetchOne = vi.fn(async () => {});
    const router = makeRouter("/batches/1");
    await router.isReady();
    mount(WorkbenchView, { global: { plugins: [router] } });
    await flushPromises();
    expect(batches.fetchOne).toHaveBeenCalledWith(1);
    expect(batches.fetchPages).toHaveBeenCalledWith(1);
  });

  it("navigates pages with ArrowRight / ArrowLeft", async () => {
    const batches = useBatchesStore();
    const apps = useApplicationsStore();
    batches.fetchOne = vi.fn(async () => {
      batches.current = {
        id: 1,
        application_id: 5,
        state: "read",
        page_count: 3,
        created_at: "",
        updated_at: "",
        fields_json: "{}",
        folder_path: "",
        hostname: "",
      };
    });
    batches.fetchPages = vi.fn(async () => {
      batches.pages = [
        {
          id: 10,
          batch_id: 1,
          page_index: 0,
          needs_review: false,
          is_blank: false,
          pipeline_processed: false,
          created_at: "",
        },
        {
          id: 11,
          batch_id: 1,
          page_index: 1,
          needs_review: false,
          is_blank: false,
          pipeline_processed: false,
          created_at: "",
        },
        {
          id: 12,
          batch_id: 1,
          page_index: 2,
          needs_review: false,
          is_blank: false,
          pipeline_processed: false,
          created_at: "",
        },
      ];
    });
    batches.fetchPage = vi.fn(async () => {});
    apps.fetchOne = vi.fn(async () => {});
    const router = makeRouter("/batches/1");
    await router.isReady();
    const wrapper = mount(WorkbenchView, {
      global: { plugins: [router] },
      attachTo: document.body,
    });
    await flushPromises();
    document.dispatchEvent(
      new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }),
    );
    await flushPromises();
    document.dispatchEvent(
      new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }),
    );
    await flushPromises();
    expect(batches.fetchPage).toHaveBeenCalledWith(1, 11);
    expect(batches.fetchPage).toHaveBeenCalledWith(1, 12);
    wrapper.unmount();
  });

  it("removes keydown listener on unmount", async () => {
    const batches = useBatchesStore();
    const apps = useApplicationsStore();
    batches.fetchOne = vi.fn(async () => {
      batches.current = {
        id: 1,
        application_id: 5,
        state: "read",
        page_count: 0,
        created_at: "",
        updated_at: "",
        fields_json: "{}",
        folder_path: "",
        hostname: "",
      };
    });
    batches.fetchPages = vi.fn(async () => {
      batches.pages = [];
    });
    apps.fetchOne = vi.fn(async () => {});
    const router = makeRouter("/batches/1");
    await router.isReady();
    const removeSpy = vi.spyOn(document, "removeEventListener");
    const wrapper = mount(WorkbenchView, { global: { plugins: [router] } });
    await flushPromises();
    wrapper.unmount();
    expect(removeSpy).toHaveBeenCalledWith("keydown", expect.any(Function), {
      capture: true,
    });
    removeSpy.mockRestore();
  });

  it("passes readOnly=true to editable children when batch.state is running", async () => {
    const batches = useBatchesStore();
    const apps = useApplicationsStore();
    batches.fetchOne = vi.fn(async () => {
      batches.current = {
        id: 1,
        application_id: 5,
        state: "running",
        page_count: 1,
        created_at: "",
        updated_at: "",
        fields_json: "{}",
        folder_path: "",
        hostname: "",
      } as any;
    });
    batches.fetchPages = vi.fn(async () => {
      batches.pages = [
        {
          id: 10,
          batch_id: 1,
          page_index: 0,
          needs_review: false,
          is_blank: false,
          pipeline_processed: false,
          created_at: "",
        },
      ] as any;
    });
    batches.fetchPage = vi.fn(async () => {});
    apps.fetchOne = vi.fn(async () => {});
    const router = makeRouter("/batches/1");
    await router.isReady();
    const wrapper = mount(WorkbenchView, { global: { plugins: [router] } });
    await flushPromises();

    const thumb = wrapper.findComponent(ThumbnailPanel);
    expect(thumb.exists()).toBe(true);
    expect(thumb.props("readOnly")).toBe(true);

    const bc = wrapper.findComponent(BarcodePanel);
    expect(bc.exists()).toBe(true);
    expect(bc.props("readOnly")).toBe(true);

    const toolbar = wrapper.findComponent(ViewerToolbar);
    if (toolbar.exists()) {
      expect(toolbar.props("canRotate")).toBe(false);
    }
    wrapper.unmount();
  });

  it("passes readOnly=false when batch.state is read", async () => {
    const batches = useBatchesStore();
    const apps = useApplicationsStore();
    batches.fetchOne = vi.fn(async () => {
      batches.current = {
        id: 1,
        application_id: 5,
        state: "read",
        page_count: 1,
        created_at: "",
        updated_at: "",
        fields_json: "{}",
        folder_path: "",
        hostname: "",
      } as any;
    });
    batches.fetchPages = vi.fn(async () => {
      batches.pages = [
        {
          id: 10,
          batch_id: 1,
          page_index: 0,
          needs_review: false,
          is_blank: false,
          pipeline_processed: false,
          created_at: "",
        },
      ] as any;
    });
    batches.fetchPage = vi.fn(async () => {});
    apps.fetchOne = vi.fn(async () => {});
    const router = makeRouter("/batches/1");
    await router.isReady();
    const wrapper = mount(WorkbenchView, { global: { plugins: [router] } });
    await flushPromises();

    expect(wrapper.findComponent(ThumbnailPanel).props("readOnly")).toBe(false);
    expect(wrapper.findComponent(BarcodePanel).props("readOnly")).toBe(false);
    wrapper.unmount();
  });

  it("loads persisted errors into the log when pages are fetched", async () => {
    const log = useWorkbenchLog();
    log.clear();
    const batches = useBatchesStore();
    const apps = useApplicationsStore();
    batches.fetchOne = vi.fn(async () => {
      batches.current = {
        id: 1,
        application_id: 5,
        state: "read",
        page_count: 1,
        created_at: "",
        updated_at: "",
        fields_json: "{}",
        folder_path: "",
        hostname: "",
      } as any;
    });
    batches.fetchPages = vi.fn(async () => {
      batches.pages = [
        {
          id: 10,
          batch_id: 1,
          page_index: 0,
          needs_review: false,
          is_blank: false,
          pipeline_processed: true,
          created_at: "",
          updated_at: "2026-04-23T10:00:00Z",
          processing_errors_json: JSON.stringify(["OCR falló"]),
          script_errors_json: "[]",
        } as any,
      ];
    });
    batches.fetchPage = vi.fn(async () => {});
    apps.fetchOne = vi.fn(async () => {});
    const router = makeRouter("/batches/1");
    await router.isReady();
    const wrapper = mount(WorkbenchView, { global: { plugins: [router] } });
    await flushPromises();

    const errorEntries = log.entries.value.filter((e) => e.level === "error");
    expect(errorEntries.length).toBeGreaterThan(0);
    expect(errorEntries[0].message).toContain("OCR falló");
    wrapper.unmount();
  });

  it("opens ThumbnailContextMenu on right-click (non-readOnly batch)", async () => {
    const batches = useBatchesStore();
    const apps = useApplicationsStore();
    batches.fetchOne = vi.fn(async () => {
      batches.current = {
        id: 1,
        application_id: 5,
        state: "read",
        page_count: 1,
        created_at: "",
        updated_at: "",
        fields_json: "{}",
        folder_path: "",
        hostname: "",
      } as any;
    });
    batches.fetchPages = vi.fn(async () => {
      batches.pages = [
        {
          id: 10,
          batch_id: 1,
          page_index: 0,
          needs_review: false,
          is_blank: false,
          pipeline_processed: false,
          created_at: "",
        },
      ] as any;
    });
    batches.fetchPage = vi.fn(async () => {});
    apps.fetchOne = vi.fn(async () => {});
    const router = makeRouter("/batches/1");
    await router.isReady();
    const wrapper = mount(WorkbenchView, { global: { plugins: [router] } });
    await flushPromises();

    const menu = wrapper.findComponent(ThumbnailContextMenu);
    expect(menu.exists()).toBe(true);
    expect(menu.props("visible")).toBe(false);

    // Emitir el evento contextmenu desde ThumbnailPanel
    wrapper.findComponent(ThumbnailPanel).vm.$emit("contextmenu", 10, 150, 200);
    await flushPromises();

    expect(menu.props("visible")).toBe(true);
    expect(menu.props("pageId")).toBe(10);
    expect(menu.props("x")).toBe(150);
    expect(menu.props("y")).toBe(200);
    wrapper.unmount();
  });

  it("closes the context menu when the menu emits close", async () => {
    const batches = useBatchesStore();
    const apps = useApplicationsStore();
    batches.fetchOne = vi.fn(async () => {
      batches.current = {
        id: 1,
        application_id: 5,
        state: "read",
        page_count: 1,
        created_at: "",
        updated_at: "",
        fields_json: "{}",
        folder_path: "",
        hostname: "",
      } as any;
    });
    batches.fetchPages = vi.fn(async () => {
      batches.pages = [
        {
          id: 10,
          batch_id: 1,
          page_index: 0,
          needs_review: false,
          is_blank: false,
          pipeline_processed: false,
          created_at: "",
        },
      ] as any;
    });
    batches.fetchPage = vi.fn(async () => {});
    apps.fetchOne = vi.fn(async () => {});
    const router = makeRouter("/batches/1");
    await router.isReady();
    const wrapper = mount(WorkbenchView, { global: { plugins: [router] } });
    await flushPromises();

    wrapper.findComponent(ThumbnailPanel).vm.$emit("contextmenu", 10, 10, 10);
    await flushPromises();
    const menu = wrapper.findComponent(ThumbnailContextMenu);
    expect(menu.props("visible")).toBe(true);

    menu.vm.$emit("close");
    await flushPromises();
    expect(menu.props("visible")).toBe(false);
    wrapper.unmount();
  });

  it("opens AddBarcodeDialog when BarcodePanel emits add-barcode", async () => {
    const batches = useBatchesStore();
    const apps = useApplicationsStore();
    batches.fetchOne = vi.fn(async () => {
      batches.current = {
        id: 1,
        application_id: 5,
        state: "read",
        page_count: 1,
        created_at: "",
        updated_at: "",
        fields_json: "{}",
        folder_path: "",
        hostname: "",
      } as any;
    });
    batches.fetchPages = vi.fn(async () => {
      batches.pages = [
        {
          id: 10,
          batch_id: 1,
          page_index: 0,
          needs_review: false,
          is_blank: false,
          pipeline_processed: false,
          created_at: "",
        },
      ] as any;
    });
    batches.fetchPage = vi.fn(async () => {});
    apps.fetchOne = vi.fn(async () => {});
    const router = makeRouter("/batches/1");
    await router.isReady();
    const wrapper = mount(WorkbenchView, { global: { plugins: [router] } });
    await flushPromises();

    const addDialog = wrapper.findComponent(AddBarcodeDialog);
    expect(addDialog.props("visible")).toBe(false);

    wrapper.findComponent(BarcodePanel).vm.$emit("add-barcode");
    await flushPromises();
    expect(addDialog.props("visible")).toBe(true);

    addDialog.vm.$emit("close");
    await flushPromises();
    expect(addDialog.props("visible")).toBe(false);
    wrapper.unmount();
  });

  it("opens DeleteBarcodeDialog when BarcodePanel emits delete-barcode with a known barcode", async () => {
    const batches = useBatchesStore();
    const apps = useApplicationsStore();
    batches.fetchOne = vi.fn(async () => {
      batches.current = {
        id: 1,
        application_id: 5,
        state: "read",
        page_count: 1,
        created_at: "",
        updated_at: "",
        fields_json: "{}",
        folder_path: "",
        hostname: "",
      } as any;
    });
    batches.fetchPages = vi.fn(async () => {
      batches.pages = [
        {
          id: 10,
          batch_id: 1,
          page_index: 0,
          needs_review: false,
          is_blank: false,
          pipeline_processed: false,
          created_at: "",
        },
      ] as any;
    });
    batches.fetchPage = vi.fn(async () => {
      batches.currentPage = {
        id: 10,
        batch_id: 1,
        page_index: 0,
        needs_review: false,
        is_blank: false,
        pipeline_processed: false,
        created_at: "",
        updated_at: "",
        image_path: "",
        ocr_text: "",
        index_fields_json: "{}",
        review_reason: "",
        is_excluded: false,
        processing_errors_json: "[]",
        script_errors_json: "[]",
        barcodes: [
          {
            id: 1,
            value: "ABC123",
            symbology: "CODE128",
            engine: "zbar",
            step_id: "",
            quality: 100,
            pos_x: 0,
            pos_y: 0,
            pos_w: 10,
            pos_h: 10,
            role: "",
          },
        ],
      } as any;
    });
    apps.fetchOne = vi.fn(async () => {});
    const router = makeRouter("/batches/1");
    await router.isReady();
    const wrapper = mount(WorkbenchView, { global: { plugins: [router] } });
    await flushPromises();

    const delDialog = wrapper.findComponent(DeleteBarcodeDialog);
    expect(delDialog.props("visible")).toBe(false);

    wrapper.findComponent(BarcodePanel).vm.$emit("delete-barcode", 1);
    await flushPromises();
    expect(delDialog.props("visible")).toBe(true);
    expect(delDialog.props("barcodeValue")).toBe("ABC123");
    wrapper.unmount();
  });

  it("passes overlay toggles (showBarcodes / showFields) from composable to DocumentViewer", async () => {
    localStorage.setItem(
      "workbench.overlays",
      JSON.stringify({ barcodes: true, fields: false }),
    );
    const batches = useBatchesStore();
    const apps = useApplicationsStore();
    batches.fetchOne = vi.fn(async () => {
      batches.current = {
        id: 1,
        application_id: 5,
        state: "read",
        page_count: 1,
        created_at: "",
        updated_at: "",
        fields_json: "{}",
        folder_path: "",
        hostname: "",
      } as any;
    });
    batches.fetchPages = vi.fn(async () => {
      batches.pages = [
        {
          id: 10,
          batch_id: 1,
          page_index: 0,
          needs_review: false,
          is_blank: false,
          pipeline_processed: false,
          created_at: "",
        },
      ] as any;
    });
    batches.fetchPage = vi.fn(async () => {});
    apps.fetchOne = vi.fn(async () => {});
    const router = makeRouter("/batches/1");
    await router.isReady();
    const wrapper = mount(WorkbenchView, { global: { plugins: [router] } });
    await flushPromises();

    // showBarcodes/showFields se siguen pasando al DocumentViewer aunque
    // el toggle ya no esté en el toolbar (ver bitácora #22).
    const viewer = wrapper.findComponent({ name: "DocumentViewer" });
    if (viewer.exists()) {
      expect(viewer.props("showBarcodes")).toBe(true);
      expect(viewer.props("showFields")).toBe(false);
    }
    wrapper.unmount();
  });

  it("persists splitter sizes via setSizes when columns are resized", async () => {
    const batches = useBatchesStore();
    const apps = useApplicationsStore();
    batches.fetchOne = vi.fn(async () => {
      batches.current = {
        id: 1,
        application_id: 5,
        state: "read",
        page_count: 0,
        created_at: "",
        updated_at: "",
        fields_json: "{}",
        folder_path: "",
        hostname: "",
      };
    });
    batches.fetchPages = vi.fn(async () => {
      batches.pages = [];
    });
    apps.fetchOne = vi.fn(async () => {});
    const router = makeRouter("/batches/1");
    await router.isReady();
    const wrapper = mount(WorkbenchView, { global: { plugins: [router] } });
    await flushPromises();
    // Simulate splitpanes "resized" event on the outer Splitpanes
    const outerSplit = wrapper.findAllComponents({ name: "splitpanes" })[0];
    outerSplit.vm.$emit("resized", { panes: [{ size: 20 }, { size: 50 }, { size: 30 }] });
    await flushPromises();
    const stored = JSON.parse(localStorage.getItem("workbench.layout")!);
    expect(stored.columns).toEqual([20, 50, 30]);
    wrapper.unmount();
  });

  // --- Fase 4: eventos lifecycle y shortcuts ---

  it("on_batch_loaded se dispara en mount", async () => {
    const spy = vi.spyOn(client, "fireEvent").mockResolvedValue({
      executed: false,
      result: null,
      cancel: false,
      target_page_id: null,
      fields_updated: {},
      batch_fields_updated: {},
      logs: [],
      error: null,
    });
    const batches = useBatchesStore();
    const apps = useApplicationsStore();
    batches.fetchOne = vi.fn(async () => {
      batches.current = {
        id: 1,
        application_id: 5,
        state: "read",
        page_count: 0,
        created_at: "",
        updated_at: "",
        fields_json: "{}",
        folder_path: "",
        hostname: "",
      };
    });
    batches.fetchPages = vi.fn(async () => {
      batches.pages = [];
    });
    apps.fetchOne = vi.fn(async () => {});
    const router = makeRouter("/batches/1");
    await router.isReady();
    const wrapper = mount(WorkbenchView, { global: { plugins: [router] } });
    await flushPromises();
    const calls = spy.mock.calls.filter((c) => c[1] === "on_batch_loaded");
    expect(calls.length).toBeGreaterThan(0);
    spy.mockRestore();
    wrapper.unmount();
  });

  it("on_batch_loaded con cancel redirecciona a /batches", async () => {
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
    const batches = useBatchesStore();
    const apps = useApplicationsStore();
    batches.fetchOne = vi.fn(async () => {
      batches.current = {
        id: 1,
        application_id: 5,
        state: "read",
        page_count: 0,
        created_at: "",
        updated_at: "",
        fields_json: "{}",
        folder_path: "",
        hostname: "",
      };
    });
    batches.fetchPages = vi.fn(async () => {
      batches.pages = [];
    });
    apps.fetchOne = vi.fn(async () => {});
    const router = makeRouter("/batches/1");
    await router.isReady();
    const pushSpy = vi.spyOn(router, "push");
    mount(WorkbenchView, { global: { plugins: [router] } });
    await flushPromises();
    expect(pushSpy).toHaveBeenCalledWith("/batches");
    vi.restoreAllMocks();
  });

  it("on_page_changed se dispara al cambiar de página cuando hay ≥2 páginas", async () => {
    const spy = vi.spyOn(client, "fireEvent").mockResolvedValue({
      executed: false,
      result: null,
      cancel: false,
      target_page_id: null,
      fields_updated: {},
      batch_fields_updated: {},
      logs: [],
      error: null,
    });
    const batches = useBatchesStore();
    const apps = useApplicationsStore();
    batches.fetchOne = vi.fn(async () => {
      batches.current = {
        id: 1,
        application_id: 5,
        state: "read",
        page_count: 2,
        created_at: "",
        updated_at: "",
        fields_json: "{}",
        folder_path: "",
        hostname: "",
      };
    });
    batches.fetchPages = vi.fn(async () => {
      batches.pages = [
        {
          id: 10,
          batch_id: 1,
          page_index: 0,
          needs_review: false,
          is_blank: false,
          pipeline_processed: false,
          created_at: "",
        },
        {
          id: 11,
          batch_id: 1,
          page_index: 1,
          needs_review: false,
          is_blank: false,
          pipeline_processed: false,
          created_at: "",
        },
      ];
    });
    batches.fetchPage = vi.fn(async () => {});
    apps.fetchOne = vi.fn(async () => {});
    const router = makeRouter("/batches/1");
    await router.isReady();
    const wrapper = mount(WorkbenchView, {
      global: { plugins: [router] },
      attachTo: document.body,
    });
    await flushPromises();
    // Seleccionar la segunda página emitiendo el evento select desde ThumbnailPanel
    wrapper.findComponent(ThumbnailPanel).vm.$emit("select", 1);
    await flushPromises();
    const calls = spy.mock.calls.filter((c) => c[1] === "on_page_changed");
    expect(calls.length).toBeGreaterThan(0);
    spy.mockRestore();
    wrapper.unmount();
  });

  it("F5 dispara store.runPipeline", async () => {
    const batches = useBatchesStore();
    const apps = useApplicationsStore();
    batches.fetchOne = vi.fn(async () => {
      batches.current = {
        id: 1,
        application_id: 5,
        state: "read",
        page_count: 0,
        created_at: "",
        updated_at: "",
        fields_json: "{}",
        folder_path: "",
        hostname: "",
      };
    });
    batches.fetchPages = vi.fn(async () => {
      batches.pages = [];
    });
    apps.fetchOne = vi.fn(async () => {});
    // Mock WebSocket: dispara onopen en el siguiente tick para resolver la promesa
    // de openWs() que guarda onRunPipeline antes de llamar a store.runPipeline.
    class WsMock {
      onmessage: ((ev: MessageEvent) => void) | null = null;
      onerror: ((ev: Event) => void) | null = null;
      close = vi.fn();
      send = vi.fn();
      addEventListener = vi.fn();
      set onopen(cb: ((ev: Event) => void) | null) {
        if (cb) Promise.resolve().then(() => cb(new Event("open")));
      }
      get onopen() {
        return null;
      }
    }
    vi.stubGlobal("WebSocket", WsMock);
    const router = makeRouter("/batches/1");
    await router.isReady();
    const wrapper = mount(WorkbenchView, {
      global: { plugins: [router] },
      attachTo: document.body,
    });
    await flushPromises();
    const runSpy = vi
      .spyOn(batches, "runPipeline")
      .mockResolvedValue(undefined as never);
    document.dispatchEvent(
      new KeyboardEvent("keydown", { key: "F5", bubbles: true }),
    );
    await flushPromises();
    expect(runSpy).toHaveBeenCalled();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    wrapper.unmount();
  });

  it("tecla ? abre el modal de ayuda de atajos", async () => {
    const batches = useBatchesStore();
    const apps = useApplicationsStore();
    batches.fetchOne = vi.fn(async () => {
      batches.current = {
        id: 1,
        application_id: 5,
        state: "read",
        page_count: 0,
        created_at: "",
        updated_at: "",
        fields_json: "{}",
        folder_path: "",
        hostname: "",
      };
    });
    batches.fetchPages = vi.fn(async () => {
      batches.pages = [];
    });
    apps.fetchOne = vi.fn(async () => {});
    vi.spyOn(client, "fireEvent").mockResolvedValue({
      executed: false,
      result: null,
      cancel: false,
      target_page_id: null,
      fields_updated: {},
      batch_fields_updated: {},
      logs: [],
      error: null,
    });
    const router = makeRouter("/batches/1");
    await router.isReady();
    const wrapper = mount(WorkbenchView, {
      global: { plugins: [router] },
      attachTo: document.body,
    });
    await flushPromises();
    // El modal de ayuda está cerrado inicialmente
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false);
    document.dispatchEvent(
      new KeyboardEvent("keydown", { key: "?", bubbles: true }),
    );
    await wrapper.vm.$nextTick();
    expect(wrapper.find('[role="dialog"]').exists()).toBe(true);
    vi.restoreAllMocks();
    wrapper.unmount();
  });

  // --- onSaveMetadata: migración de raw fetch a api.patch ---

  it("onSaveMetadata llama a api.patch con path y body correctos", async () => {
    const patchSpy = vi.spyOn(client.api, "patch").mockResolvedValue({});
    const batches = useBatchesStore();
    const apps = useApplicationsStore();
    batches.fetchOne = vi.fn(async () => {
      batches.current = {
        id: 1,
        application_id: 5,
        state: "read",
        page_count: 0,
        created_at: "",
        updated_at: "",
        fields_json: "{}",
        folder_path: "",
        hostname: "",
      };
    });
    batches.fetchPages = vi.fn(async () => {
      batches.pages = [];
    });
    apps.fetchOne = vi.fn(async () => {});
    const router = makeRouter("/batches/1");
    await router.isReady();
    const wrapper = mount(WorkbenchView, { global: { plugins: [router] } });
    await flushPromises();
    const panel = wrapper.findComponent(MetadataPanel);
    await panel.vm.$emit("save", { ref: "ABC" });
    await flushPromises();
    expect(patchSpy).toHaveBeenCalledWith("/batches/1", {
      fields_json: JSON.stringify({ ref: "ABC" }),
    });
    vi.restoreAllMocks();
    wrapper.unmount();
  });

  it("onSaveMetadata muestra toast.error cuando api.patch falla", async () => {
    vi.spyOn(client.api, "patch").mockRejectedValue(
      new client.ApiError(500, "boom"),
    );
    const batches = useBatchesStore();
    const apps = useApplicationsStore();
    batches.fetchOne = vi.fn(async () => {
      batches.current = {
        id: 1,
        application_id: 5,
        state: "read",
        page_count: 0,
        created_at: "",
        updated_at: "",
        fields_json: "{}",
        folder_path: "",
        hostname: "",
      };
    });
    batches.fetchPages = vi.fn(async () => {
      batches.pages = [];
    });
    apps.fetchOne = vi.fn(async () => {});
    const toast = useToast();
    toast.toasts.value = [];
    const router = makeRouter("/batches/1");
    await router.isReady();
    const wrapper = mount(WorkbenchView, { global: { plugins: [router] } });
    await flushPromises();
    const panel = wrapper.findComponent(MetadataPanel);
    await panel.vm.$emit("save", { ref: "X" });
    await flushPromises();
    const errors = toast.toasts.value.filter((t) => t.kind === "error");
    expect(errors.length).toBeGreaterThan(0);
    expect(errors.some((t) => t.message.includes("boom"))).toBe(true);
    vi.restoreAllMocks();
    wrapper.unmount();
  });

  // ------------------------------------------------------------------
  // Drag & drop de ficheros (entrada #8 bitácora QA web 2026-04-27)
  // ------------------------------------------------------------------

  function makeDragEvent(type: string, files: File[] = []): Event {
    // jsdom expone DragEvent pero no DataTransfer; lo simulamos como objeto
    // con la API mínima que usa el componente: types, files, dropEffect.
    const ev = new Event(type, { bubbles: true, cancelable: true });
    Object.defineProperty(ev, "dataTransfer", {
      value: {
        types: files.length > 0 ? ["Files"] : [],
        files,
        dropEffect: "none",
      },
    });
    return ev;
  }

  async function mountWithBatch(state = "read") {
    const batches = useBatchesStore();
    const apps = useApplicationsStore();
    batches.fetchOne = vi.fn(async () => {
      batches.current = {
        id: 1,
        application_id: 5,
        state,
        page_count: 0,
        created_at: "",
        updated_at: "",
        fields_json: "{}",
        folder_path: "",
        hostname: "",
      };
    });
    batches.fetchPages = vi.fn(async () => {
      batches.pages = [];
    });
    batches.uploadFiles = vi.fn(async () => {});
    apps.fetchOne = vi.fn(async () => {});
    const router = makeRouter("/batches/1");
    await router.isReady();
    const wrapper = mount(WorkbenchView, {
      global: { plugins: [router] },
      attachTo: document.body,
    });
    await flushPromises();
    return { wrapper, batches };
  }

  it("dragenter con ficheros muestra el overlay de drop zone", async () => {
    const { wrapper } = await mountWithBatch();
    const root = wrapper.element as HTMLElement;
    root.dispatchEvent(makeDragEvent("dragenter", [new File(["x"], "a.png")]));
    await flushPromises();
    expect(
      wrapper.find('[data-testid="workbench-drop-overlay"]').exists(),
    ).toBe(true);
    wrapper.unmount();
  });

  it("dragenter sin ficheros (solo texto) NO muestra overlay", async () => {
    const { wrapper } = await mountWithBatch();
    const root = wrapper.element as HTMLElement;
    // types vacío == drag de texto/HTML, no archivos
    root.dispatchEvent(makeDragEvent("dragenter", []));
    await flushPromises();
    expect(
      wrapper.find('[data-testid="workbench-drop-overlay"]').exists(),
    ).toBe(false);
    wrapper.unmount();
  });

  it("drop con ficheros llama a store.uploadFiles y oculta overlay", async () => {
    const { wrapper, batches } = await mountWithBatch();
    const root = wrapper.element as HTMLElement;
    const f1 = new File(["x"], "a.png", { type: "image/png" });
    const f2 = new File(["y"], "b.png", { type: "image/png" });
    root.dispatchEvent(makeDragEvent("dragenter", [f1, f2]));
    root.dispatchEvent(makeDragEvent("drop", [f1, f2]));
    await flushPromises();
    expect(batches.uploadFiles).toHaveBeenCalledWith(1, [f1, f2]);
    expect(
      wrapper.find('[data-testid="workbench-drop-overlay"]').exists(),
    ).toBe(false);
    wrapper.unmount();
  });

  it("drag durante state=running NO activa overlay (canUpload=false)", async () => {
    const { wrapper } = await mountWithBatch("running");
    const root = wrapper.element as HTMLElement;
    root.dispatchEvent(makeDragEvent("dragenter", [new File(["x"], "a.png")]));
    await flushPromises();
    expect(
      wrapper.find('[data-testid="workbench-drop-overlay"]').exists(),
    ).toBe(false);
    wrapper.unmount();
  });
});
