---
name: No romper la aplicación desktop al evolucionar la web
description: Restricción dura para todos los sprints web. Lo que hagamos en web/agente local no puede romper desktop ni hacer que deje de funcionar.
type: feedback
originSessionId: 7b6bd88f-a10c-476b-a06b-b548ac8a163e
---
Cualquier trabajo en la web SaaS o en el agente local debe preservar el funcionamiento de la aplicación desktop. La desktop es la versión productiva en clientes hoy y no puede regresionar.

**Why:** Restricción explícita del usuario al iniciar el sprint del cliente local web (2026-05-06). Hay clientes con la desktop en producción y la web aún no está publicada — romper desktop por "preparar la web" sería una regresión inaceptable.

**How to apply:**

1. **Modo importador, no modificador**: cuando el código web/agente reutilice servicios desktop (`scanner_service.py`, `transfer_service.py`, `image_pipeline.py`, etc.), los IMPORTA tal cual. No se cambian sus firmas, comportamiento ni efectos colaterales.

2. **Si hay que extraer código compartido**: usar el patrón ya establecido con `app/pipeline/page_context.py` — mover el código a la ubicación compartida y dejar la ubicación original como módulo que **re-exporta** los símbolos. Cualquier `from app.workers.recognition_worker import PageContext` (o similar) sigue funcionando.

3. **Checkpoint obligatorio en cada hito**: antes de cerrar un hito, ejecutar `pytest tests/ -v --tb=short` (los 859 tests desktop) y todos deben seguir verde. Si alguno se rompe es señal de regresión, no de test obsoleto.

4. **Antes de tocar un servicio compartido**: revisar `git grep` de imports desde `app/`, `main.py`, `docscan_worker/` y `tests/`. Si hay callers desktop, planificar el cambio de forma backwards-compatible (typing relaxed, parámetros opcionales con default, etc.).

5. **No "limpiar" código aprovechando la oportunidad**: la tentación de refactorizar de paso es real. Si la mejora no es necesaria para la web, no se hace en este sprint — se anota como pendiente y va en commit separado (idealmente cuando ambos productos hayan estabilizado).

6. **Si la web pide algo incompatible** con la desktop: no se modifica el servicio compartido — se crea un wrapper/adapter en `web/` o `docscan_local_agent/` que adapte. Mejor duplicar 30 líneas que romper el desktop.
