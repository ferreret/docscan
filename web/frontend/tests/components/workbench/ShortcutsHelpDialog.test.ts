import { describe, it, expect, afterEach } from "vitest";
import { mount } from "@vue/test-utils";
import ShortcutsHelpDialog from "@/components/workbench/ShortcutsHelpDialog.vue";

describe("ShortcutsHelpDialog", () => {
  let wrapper: ReturnType<typeof mount>;
  afterEach(() => wrapper?.unmount());

  it("renderiza cuando isOpen=true", () => {
    wrapper = mount(ShortcutsHelpDialog, { props: { isOpen: true } });
    expect(wrapper.find('[role="dialog"]').exists()).toBe(true);
    expect(wrapper.text()).toContain("Lote");
    expect(wrapper.text()).toContain("Edición");
    expect(wrapper.text()).toContain("Navegación");
    expect(wrapper.text()).toContain("Zoom");
  });

  it("no renderiza cuando isOpen=false", () => {
    wrapper = mount(ShortcutsHelpDialog, { props: { isOpen: false } });
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false);
  });

  it("emite close al pulsar Escape", async () => {
    wrapper = mount(ShortcutsHelpDialog, { props: { isOpen: true } });
    await wrapper.find('[role="dialog"]').trigger("keydown", { key: "Escape" });
    expect(wrapper.emitted("close")).toBeTruthy();
  });

  it("muestra al menos 15 filas de shortcuts", () => {
    wrapper = mount(ShortcutsHelpDialog, { props: { isOpen: true } });
    const kbds = wrapper.findAll("kbd");
    expect(kbds.length).toBeGreaterThanOrEqual(15);
  });
});
