---
name: tests inline pueden ocultar bugs reales del modo producción
description: Cuando un test usa un atajo síncrono (BackgroundTasks, modo inline) en vez del transporte real (Redis, queue), valida la lógica pero NO el contrato de serialización ni los nombres registrados. Antes de declarar "validado e2e" hay que ejercitar el camino producción.
type: feedback
originSessionId: 577d1c04-41a6-4328-b9a0-3b80dcd8493f
---
En la migración a ARQ (sesión 2026-04-29) se introdujo un modo `inline`
en `TasksSettings` para preservar los 203 tests web sin reescribirlos.
La idea era buena (evitar refactor masivo), pero pasó por alto que el
modo inline **NO atraviesa Redis**, así que dos clases de bugs quedaron
invisibles para la suite:

1. **Serialización de argumentos**: en inline, los kwargs van a una
   función Python directa con `asyncio.to_thread(func, *args, **kwargs)`.
   Cualquier objeto Python (incluido `BaseStorage` con conexiones HTTP)
   pasa sin problema. En ARQ real, los kwargs se pickle-ean y meten en
   Redis. El bug de `SerializationError` no se materializaba en tests.

2. **Nombres registrados en la cola**: en inline, el `_INLINE_REGISTRY`
   resuelve el nombre `"run_pipeline_for_batch"` a la función Python
   directamente. En ARQ real, el nombre que enrola el cliente debe
   coincidir con el `name` registrado por el worker. El handler con
   `__qualname__="pipeline_job"` no era encontrado.

**Why**: la suite pasaba al 100% (216/216) en una migración que tenía
dos bugs bloqueantes en el camino de producción. El smoke test manual
los expuso en cinco minutos.

**How to apply**:
- Cuando se introduzca un modo de tests que cortocircuita un transporte
  real (queue, broker, RPC), **siempre** programar un smoke test e2e
  contra el transporte real antes de declarar la cosa "validada".
- Los tests del modo inline cubren la lógica de negocio, no el contrato
  de transporte. Ambos hacen falta. No tratar el inline como sustituto
  del e2e.
- Si el plan original (como el del 29-04) ya menciona "smoke test del
  pipeline real" como paso pendiente, **no marcar la migración como
  cerrada hasta hacerlo**. El recovery_job funcionando no demuestra que
  el pipeline_job/transfer_job funcionen — los tres tienen contratos de
  serialización distintos.
