import { describe, it, expect, vi } from "vitest";
import { handleNotFound } from "@/utils/handleNotFound";
import { ApiError } from "@/api/client";

function makeOpts() {
  const router = { replace: vi.fn() };
  const toast = {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    toasts: { value: [] },
    dismiss: vi.fn(),
  };
  return {
    // El helper solo usa router.replace y toast.error; el cast es seguro.
    opts: {
      router: router as never,
      toast: toast as never,
      fallback: "/batches",
      message: "El lote no existe o no tienes acceso",
    },
    router,
    toast,
  };
}

describe("handleNotFound", () => {
  it("redirige y muestra toast.error cuando el error es ApiError 404", () => {
    const { opts, router, toast } = makeOpts();
    const err = new ApiError(404, "Lote no encontrado");

    const handled = handleNotFound(err, opts);

    expect(handled).toBe(true);
    expect(router.replace).toHaveBeenCalledWith("/batches");
    expect(toast.error).toHaveBeenCalledWith(
      "El lote no existe o no tienes acceso",
    );
  });

  it("ignora ApiError con otros status (403, 500, etc.)", () => {
    const { opts, router, toast } = makeOpts();
    for (const status of [400, 401, 403, 409, 422, 500]) {
      const err = new ApiError(status, "otro error");
      const handled = handleNotFound(err, opts);
      expect(handled).toBe(false);
    }
    expect(router.replace).not.toHaveBeenCalled();
    expect(toast.error).not.toHaveBeenCalled();
  });

  it("ignora errores que no son ApiError (TypeError, Error, string, etc.)", () => {
    const { opts, router, toast } = makeOpts();
    const cases = [
      new TypeError("network"),
      new Error("boom"),
      "literal string",
      null,
      undefined,
      { status: 404 },
    ];
    for (const err of cases) {
      const handled = handleNotFound(err, opts);
      expect(handled).toBe(false);
    }
    expect(router.replace).not.toHaveBeenCalled();
    expect(toast.error).not.toHaveBeenCalled();
  });

  it("usa el fallback y mensaje específicos pasados por opts", () => {
    const { opts, router, toast } = makeOpts();
    opts.fallback = "/applications";
    opts.message = "La aplicación no existe o no tienes acceso";
    const err = new ApiError(404, "Aplicación no encontrada");

    handleNotFound(err, opts);

    expect(router.replace).toHaveBeenCalledWith("/applications");
    expect(toast.error).toHaveBeenCalledWith(
      "La aplicación no existe o no tienes acceso",
    );
  });
});
