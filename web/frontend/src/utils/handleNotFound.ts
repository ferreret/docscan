import type { Router } from "vue-router";
import { ApiError } from "@/api/client";
import type { useToast } from "@/composables/useToast";

/**
 * Captura un ApiError 404 y redirige a una ruta de fallback con un toast.
 *
 * Uso típico en `onMounted` de vistas que cargan recursos por id:
 *
 *     try {
 *       await store.fetchOne(id);
 *     } catch (err) {
 *       if (handleNotFound(err, { router, toast, fallback: "/batches",
 *           message: "El lote no existe o no tienes acceso" })) return;
 *       throw err;
 *     }
 *
 * Cubre el caso de aislamiento multi-tenant en que el backend devuelve
 * un 404 unificado para recursos de otro tenant: en lugar de dejar la
 * vista colgada con un "Unhandled error during execution of mounted
 * hook", redirige al listado y muestra un toast informativo.
 *
 * @returns true si capturó un 404 (y redirigió), false en caso contrario
 *          (el caller debe re-lanzar el error).
 */
export function handleNotFound(
  err: unknown,
  opts: {
    router: Router;
    toast: ReturnType<typeof useToast>;
    fallback: string;
    message: string;
  },
): boolean {
  if (err instanceof ApiError && err.status === 404) {
    opts.toast.error(opts.message);
    opts.router.replace(opts.fallback);
    return true;
  }
  return false;
}
