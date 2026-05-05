import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import BatchStateBadge from "@/components/batches/BatchStateBadge.vue";

describe("BatchStateBadge", () => {
  it("muestra 'creado' en amarillo para state=created", () => {
    const wrapper = mount(BatchStateBadge, { props: { state: "created" } });
    expect(wrapper.text()).toBe("creado");
    expect(wrapper.classes()).toContain("bg-warning-soft");
    expect(wrapper.classes()).toContain("text-warning");
    expect(wrapper.classes()).not.toContain("animate-pulse");
  });

  it("muestra 'procesando…' con pulse para state=running", () => {
    const wrapper = mount(BatchStateBadge, { props: { state: "running" } });
    expect(wrapper.text()).toBe("procesando…");
    expect(wrapper.classes()).toContain("bg-primary-soft");
    expect(wrapper.classes()).toContain("animate-pulse");
  });

  it("muestra 'procesado' en azul para state=read", () => {
    const wrapper = mount(BatchStateBadge, { props: { state: "read" } });
    expect(wrapper.text()).toBe("procesado");
    expect(wrapper.classes()).toContain("bg-primary-soft");
    expect(wrapper.classes()).not.toContain("animate-pulse");
  });

  it("muestra 'transfiriendo…' con pulse para state=transferring", () => {
    const wrapper = mount(BatchStateBadge, {
      props: { state: "transferring" },
    });
    expect(wrapper.text()).toBe("transfiriendo…");
    expect(wrapper.classes()).toContain("bg-warning-soft");
    expect(wrapper.classes()).toContain("animate-pulse");
  });

  it("muestra 'transferido' en verde para state=transferred", () => {
    const wrapper = mount(BatchStateBadge, { props: { state: "transferred" } });
    expect(wrapper.text()).toBe("transferido");
    expect(wrapper.classes()).toContain("bg-success-soft");
    expect(wrapper.classes()).toContain("text-success");
  });

  it("muestra 'error' en rojo para cualquier state que empiece por error", () => {
    const w1 = mount(BatchStateBadge, { props: { state: "error_read" } });
    expect(w1.text()).toBe("error");
    expect(w1.classes()).toContain("bg-danger-soft");

    const w2 = mount(BatchStateBadge, {
      props: { state: "error_transferred" },
    });
    expect(w2.text()).toBe("error");
    expect(w2.classes()).toContain("text-danger");
  });

  it("usa fallback gris y muestra el state crudo si es desconocido", () => {
    const wrapper = mount(BatchStateBadge, { props: { state: "futuro" } });
    expect(wrapper.text()).toBe("futuro");
    expect(wrapper.classes()).toContain("bg-mantle");
    expect(wrapper.classes()).toContain("text-subtext");
  });

  it("expone el state crudo como title para tooltip", () => {
    const wrapper = mount(BatchStateBadge, { props: { state: "running" } });
    expect(wrapper.attributes("title")).toBe("running");
  });
});
