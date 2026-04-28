import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { mount } from "@vue/test-utils";
import { defineComponent, h } from "vue";
import { useWorkbenchShortcuts } from "@/composables/useWorkbenchShortcuts";
import type { ShortcutAction } from "@/constants/shortcuts";

function makeHost(
  handlers: Partial<Record<ShortcutAction, () => void>>,
  isReadOnly = false,
) {
  return defineComponent({
    setup() {
      useWorkbenchShortcuts({
        handlers,
        isReadOnly: () => isReadOnly,
        fireKeyEvent: () => {},
      });
      return () => h("div", "host");
    },
  });
}

function dispatchKey(
  opts: Partial<KeyboardEventInit & { key: string }>,
  target?: HTMLElement,
) {
  const ev = new KeyboardEvent("keydown", {
    bubbles: true,
    cancelable: true,
    ...opts,
  });
  (target ?? document.body).dispatchEvent(ev);
  return ev;
}

describe("useWorkbenchShortcuts", () => {
  let wrapper: ReturnType<typeof mount>;

  afterEach(() => {
    wrapper?.unmount();
  });

  it("tecla R dispara rotate", () => {
    const rotate = vi.fn();
    wrapper = mount(makeHost({ rotate }));
    dispatchKey({ key: "r" });
    expect(rotate).toHaveBeenCalled();
  });

  it("F5 dispara runPipeline y preventDefault", () => {
    const runPipeline = vi.fn();
    wrapper = mount(makeHost({ runPipeline }));
    const ev = dispatchKey({ key: "F5" });
    expect(runPipeline).toHaveBeenCalled();
    expect(ev.defaultPrevented).toBe(true);
  });

  it("? abre el modal de ayuda", () => {
    const openHelp = vi.fn();
    wrapper = mount(makeHost({ openHelp }));
    dispatchKey({ key: "?" });
    expect(openHelp).toHaveBeenCalled();
  });

  it("Delete dispara deletePage", () => {
    const deletePage = vi.fn();
    wrapper = mount(makeHost({ deletePage }));
    dispatchKey({ key: "Delete" });
    expect(deletePage).toHaveBeenCalled();
  });

  it("ArrowRight dispara nextPage", () => {
    const nextPage = vi.fn();
    wrapper = mount(makeHost({ nextPage }));
    dispatchKey({ key: "ArrowRight" });
    expect(nextPage).toHaveBeenCalled();
  });

  it("Shift+ArrowRight dispara nextReviewPage", () => {
    const nextReviewPage = vi.fn();
    wrapper = mount(makeHost({ nextReviewPage }));
    dispatchKey({ key: "ArrowRight", shiftKey: true });
    expect(nextReviewPage).toHaveBeenCalled();
  });

  it("input enfocado ignora R", () => {
    const rotate = vi.fn();
    wrapper = mount(makeHost({ rotate }));
    const input = document.createElement("input");
    document.body.appendChild(input);
    input.focus();
    dispatchKey({ key: "r" }, input);
    expect(rotate).not.toHaveBeenCalled();
    input.remove();
  });

  it("textarea enfocada ignora R", () => {
    const rotate = vi.fn();
    wrapper = mount(makeHost({ rotate }));
    const ta = document.createElement("textarea");
    document.body.appendChild(ta);
    ta.focus();
    dispatchKey({ key: "r" }, ta);
    expect(rotate).not.toHaveBeenCalled();
    ta.remove();
  });

  it("elemento contenteditable ignora R", () => {
    const rotate = vi.fn();
    wrapper = mount(makeHost({ rotate }));
    const div = document.createElement("div");
    div.setAttribute("contenteditable", "true");
    document.body.appendChild(div);
    div.focus();
    dispatchKey({ key: "r" }, div);
    expect(rotate).not.toHaveBeenCalled();
    div.remove();
  });

  it("dialog modal abierto ignora atajos aunque el target sea body", () => {
    // Regresión: con un AddBarcodeDialog abierto y foco perdido (body), R
    // no debe rotar la página de fondo.
    const rotate = vi.fn();
    const closeBatch = vi.fn();
    wrapper = mount(makeHost({ rotate, closeBatch }));
    const dlg = document.createElement("div");
    dlg.setAttribute("role", "dialog");
    dlg.setAttribute("aria-modal", "true");
    document.body.appendChild(dlg);
    dispatchKey({ key: "r" });
    dispatchKey({ key: "Escape" });
    expect(rotate).not.toHaveBeenCalled();
    expect(closeBatch).not.toHaveBeenCalled();
    dlg.remove();
  });

  it("dialog sin aria-modal NO bloquea (regresión-safe)", () => {
    // role=dialog sin aria-modal=true podría usarse en componentes no-modal;
    // el filtro debe seguir requiriendo aria-modal=true.
    const rotate = vi.fn();
    wrapper = mount(makeHost({ rotate }));
    const dlg = document.createElement("div");
    dlg.setAttribute("role", "dialog");
    document.body.appendChild(dlg);
    dispatchKey({ key: "r" });
    expect(rotate).toHaveBeenCalled();
    dlg.remove();
  });

  it("isReadOnly oculta acciones de edición pero permite navegación", () => {
    const rotate = vi.fn();
    const nextPage = vi.fn();
    wrapper = mount(makeHost({ rotate, nextPage }, true));
    dispatchKey({ key: "r" });
    dispatchKey({ key: "ArrowRight" });
    expect(rotate).not.toHaveBeenCalled();
    expect(nextPage).toHaveBeenCalled();
  });

  it("tecla con modificador no mapeada dispara fireKeyEvent", () => {
    const fireKeyEvent = vi.fn();
    const Host = defineComponent({
      setup() {
        useWorkbenchShortcuts({
          handlers: {},
          isReadOnly: () => false,
          fireKeyEvent,
        });
        return () => h("div");
      },
    });
    wrapper = mount(Host);
    dispatchKey({ key: "l", ctrlKey: true, altKey: true });
    expect(fireKeyEvent).toHaveBeenCalledWith("Ctrl+l");
  });

  it("unmount elimina el listener", () => {
    const rotate = vi.fn();
    wrapper = mount(makeHost({ rotate }));
    wrapper.unmount();
    dispatchKey({ key: "r" });
    expect(rotate).not.toHaveBeenCalled();
  });
});
