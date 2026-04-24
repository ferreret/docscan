# Workbench web Fase 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cerrar el Workbench web con 5 eventos lifecycle ejecutables server-side (`on_batch_loaded`, `on_navigate_prev/next`, `on_page_changed`, `on_key_event`), 16 atajos de teclado con filtro de foco y un modal de ayuda abierto con `?`.

**Architecture:** Un único endpoint nuevo `POST /api/batches/{id}/events/{name}` ejecuta el script Python asociado al evento vía el `ScriptEngine` existente y devuelve un `EventResult` tipado (cancel/target_page_id/fields_updated/logs/error). En el frontend, dos composables (`useWorkbenchEvents` para invocar los eventos, `useWorkbenchShortcuts` para capturar teclas con filtro de foco) más un componente `ShortcutsHelpDialog` y el wiring en `WorkbenchView.vue`. Los eventos bloqueantes usan `fireSync` (con `await`), los fire-and-forget usan `fireAsync`. No se toca código desktop.

**Tech Stack:** FastAPI + SQLAlchemy 2.x + Pydantic v2 (backend); Vue 3 + Pinia + Vitest + Tailwind (frontend); `ScriptEngine` existente para ejecución de scripts Python con timeout.

**Spec:** `docs/superpowers/specs/2026-04-24-workbench-web-fase-4-design.md`.

---

## Estructura de archivos

### Nuevos

- `web/api/schemas/event.py` — schemas `EventFireIn` y `EventResult`.
- `web/api/services/__init__.py` — marker del módulo.
- `web/api/services/event_dispatcher.py` — lógica de ejecución compartida.
- `web/api/routers/events.py` — router con el endpoint POST.
- `web/frontend/src/constants/shortcuts.ts` — catálogo único de atajos.
- `web/frontend/src/composables/useWorkbenchEvents.ts` — composable de eventos.
- `web/frontend/src/composables/useWorkbenchShortcuts.ts` — composable de atajos.
- `web/frontend/src/components/workbench/ShortcutsHelpDialog.vue` — modal de ayuda.
- `web/frontend/tests/composables/useWorkbenchEvents.test.ts`
- `web/frontend/tests/composables/useWorkbenchShortcuts.test.ts`
- `web/frontend/tests/components/workbench/ShortcutsHelpDialog.test.ts`

### Modificados

- `web/api/main.py` — registrar router `events`.
- `web/api/schemas/__init__.py` — re-exportar nuevos schemas.
- `web/frontend/src/api/types.ts` — tipo `EventFireIn`/`EventResult`.
- `web/frontend/src/api/events-catalog.ts` — añadir 5 `EventDefinition`.
- `web/frontend/src/api/client.ts` — método `fireEvent`.
- `web/frontend/src/views/batches/WorkbenchView.vue` — wiring completo (onMounted, watch, handlers de navegación, shortcuts, dialog).
- `web/frontend/src/components/workbench/WorkbenchToolbar.vue` — botón "?" nuevo.
- `tests/test_web_api.py` — clase `TestEventsFire`.
- `web/frontend/tests/api/events-catalog.test.ts` — expectativas para 9 eventos.
- `web/frontend/tests/views/batches/WorkbenchView.test.ts` — 5 tests de integración nuevos.

---

## Task 1: Schemas `EventFireIn` y `EventResult`

**Files:**
- Create: `web/api/schemas/event.py`
- Modify: `web/api/schemas/__init__.py` (re-export)

- [ ] **Step 1: Crear el schema con los dos modelos**

Crear `web/api/schemas/event.py`:

```python
"""Schemas para el dispatcher de eventos lifecycle del workbench web."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EventFireIn(BaseModel):
    """Payload para disparar un evento lifecycle."""

    page_id: int | None = None
    key: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class EventResult(BaseModel):
    """Respuesta tipada tras ejecutar un script de evento."""

    executed: bool
    result: Any = None
    cancel: bool = False
    target_page_id: int | None = None
    fields_updated: dict[str, Any] = Field(default_factory=dict)
    batch_fields_updated: dict[str, Any] = Field(default_factory=dict)
    logs: list[dict[str, str]] = Field(default_factory=list)
    error: str | None = None
```

- [ ] **Step 2: Re-exportar desde `__init__.py` (si el módulo usa ese patrón)**

Leer primero `web/api/schemas/__init__.py`. Si re-exporta otros schemas, añadir:

```python
from .event import EventFireIn, EventResult
```

Si el módulo `__init__.py` está vacío, dejarlo vacío y saltar este paso.

- [ ] **Step 3: Verificar que importa sin errores**

Run:
```bash
source .venv/bin/activate && python3.14 -c "from web.api.schemas.event import EventFireIn, EventResult; print('OK')"
```
Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add web/api/schemas/event.py web/api/schemas/__init__.py
git commit -m "feat(web-api): schemas EventFireIn y EventResult para eventos lifecycle"
```

---

## Task 2: Test del dispatcher (TDD — test primero)

**Files:**
- Modify: `tests/test_web_api.py` (añadir clase `TestEventsFire` al final)

- [ ] **Step 1: Añadir clase de tests con el primer caso (script no definido)**

Al final de `tests/test_web_api.py`, antes del último `if __name__`:

```python
class TestEventsFire:
    """Endpoint POST /api/batches/{id}/events/{name}."""

    def test_fire_script_no_definido_devuelve_executed_false(self, client):
        h = _auth_header(client)
        batch_id = _create_batch(client, h)
        resp = client.post(
            f"/api/batches/{batch_id}/events/on_batch_loaded",
            headers=h,
            json={},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["executed"] is False
        assert data["cancel"] is False
        assert data["error"] is None
```

- [ ] **Step 2: Ejecutar el test y confirmar que falla**

Run:
```bash
source .venv/bin/activate && DOCSCAN_WEB_DATABASE__URL="sqlite:///test.db" pytest tests/test_web_api.py::TestEventsFire::test_fire_script_no_definido_devuelve_executed_false -xvs
```
Expected: FAIL con `404` o `405` (el endpoint no existe todavía).

- [ ] **Step 3: Commit del test**

```bash
git add tests/test_web_api.py
git commit -m "test(web-api): primer test TDD para endpoint de eventos"
```

---

## Task 3: Event dispatcher (servicio)

**Files:**
- Create: `web/api/services/__init__.py`
- Create: `web/api/services/event_dispatcher.py`

- [ ] **Step 1: Crear el módulo**

Crear `web/api/services/__init__.py` con un string vacío o `"""Servicios de la API web."""`.

- [ ] **Step 2: Escribir `event_dispatcher.py`**

Crear `web/api/services/event_dispatcher.py`:

```python
"""Ejecuta eventos lifecycle del workbench web en el backend.

Reutiliza el ScriptEngine del pipeline. Los scripts viven en
``application.events_json`` bajo la clave del nombre del evento.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.batch import Batch
from app.models.page import Page
from app.pipeline.page_context import AppContext, BatchContext, PageContext
from app.services.script_engine import ScriptEngine

from web.api.schemas.event import EventResult

log = logging.getLogger(__name__)

# Eventos lifecycle soportados por el endpoint web en Fase 4.
SUPPORTED_EVENTS = frozenset({
    "on_batch_loaded",
    "on_navigate_prev",
    "on_navigate_next",
    "on_page_changed",
    "on_key_event",
})

# Eventos que requieren page_id en el payload.
EVENTS_REQUIRING_PAGE_ID = frozenset({
    "on_navigate_prev",
    "on_navigate_next",
    "on_page_changed",
})

SCRIPT_TIMEOUT_SECONDS = 5.0


def dispatch_event(
    *,
    event_name: str,
    application: Application,
    batch: Batch,
    page: Page | None,
    key: str | None,
    extra: dict[str, Any],
    session: Session,
) -> EventResult:
    """Ejecuta el script asociado al evento y devuelve el resultado tipado.

    - Si el script no está definido en ``events_json`` devuelve
      ``EventResult(executed=False)``.
    - Un retorno ``False`` del script equivale a ``cancel=True``.
    - Un retorno ``dict`` se mapea a ``EventResult`` campo a campo
      (``cancel``, ``target_page_id``, ``fields_updated``, ``batch_fields_updated``,
      ``logs``, ``result``).
    - Cualquier excepción del script se captura y devuelve
      ``EventResult(executed=True, error=str(e))``.
    - Las mutaciones de ``page.fields`` y ``batch.fields`` se persisten en BD.
    """
    script_source = _load_event_script(application, event_name)
    if not script_source:
        return EventResult(executed=False)

    engine = ScriptEngine()
    try:
        engine.compile_script(event_name, script_source, event_name)
    except Exception as e:
        log.warning("Error compilando %s (app %d): %s", event_name, application.id, e)
        return EventResult(executed=True, error=f"compile error: {e}")

    app_ctx = _build_app_context(application)
    batch_ctx = _build_batch_context(batch)
    page_ctx = _build_page_context(page) if page else None

    kwargs: dict[str, Any] = {"app": app_ctx, "batch": batch_ctx}
    if page_ctx is not None:
        kwargs["page"] = page_ctx
    if key is not None:
        kwargs["key"] = key
    if extra:
        kwargs["extra"] = extra

    try:
        raw = engine.run_event(
            script_id=event_name,
            entry_point=event_name,
            timeout=SCRIPT_TIMEOUT_SECONDS,
            **kwargs,
        )
    except TimeoutError:
        return EventResult(executed=True, error="timeout")
    except Exception as e:
        log.warning("Error ejecutando %s (app %d): %s", event_name, application.id, e)
        return EventResult(executed=True, error=str(e))

    result = _map_return_to_event_result(raw)

    if page is not None and page_ctx is not None and page_ctx.fields:
        result.fields_updated = page_ctx.fields.copy()
        page.index_fields_json = json.dumps(page_ctx.fields, ensure_ascii=False)
        session.add(page)

    if batch_ctx.fields:
        result.batch_fields_updated = batch_ctx.fields.copy()
        batch.fields_json = json.dumps(batch_ctx.fields, ensure_ascii=False)
        session.add(batch)

    if result.fields_updated or result.batch_fields_updated:
        session.commit()

    return result


def _load_event_script(application: Application, event_name: str) -> str | None:
    """Devuelve el código fuente del evento o None si no está definido."""
    try:
        events = json.loads(application.events_json or "{}")
    except json.JSONDecodeError:
        return None
    script = events.get(event_name)
    if not script or not script.strip():
        return None
    return script


def _build_app_context(application: Application) -> AppContext:
    return AppContext(
        id=application.id,
        name=application.name,
        description=application.description,
        output_format=application.output_format,
        auto_transfer=application.auto_transfer,
    )


def _build_batch_context(batch: Batch) -> BatchContext:
    try:
        fields = json.loads(batch.fields_json) if batch.fields_json else {}
    except json.JSONDecodeError:
        fields = {}
    return BatchContext(
        id=batch.id,
        fields=fields,
        state=batch.state,
        page_count=batch.page_count,
        folder_path=batch.folder_path,
        hostname=batch.hostname,
    )


def _build_page_context(page: Page) -> PageContext:
    try:
        fields = json.loads(page.index_fields_json) if page.index_fields_json else {}
    except json.JSONDecodeError:
        fields = {}
    ctx = PageContext(page_index=page.page_index, image=None)
    ctx.fields = fields
    return ctx


def _map_return_to_event_result(raw: Any) -> EventResult:
    """Convierte el retorno del script en EventResult."""
    if raw is None or raw is True:
        return EventResult(executed=True)
    if raw is False:
        return EventResult(executed=True, cancel=True)
    if isinstance(raw, dict):
        return EventResult(
            executed=True,
            result=raw.get("result"),
            cancel=bool(raw.get("cancel", False)),
            target_page_id=raw.get("target_page_id"),
            fields_updated=dict(raw.get("fields_updated") or {}),
            batch_fields_updated=dict(raw.get("batch_fields_updated") or {}),
            logs=list(raw.get("logs") or []),
        )
    return EventResult(executed=True, result=raw)
```

- [ ] **Step 3: Verificar import**

Run:
```bash
source .venv/bin/activate && python3.14 -c "from web.api.services.event_dispatcher import dispatch_event, SUPPORTED_EVENTS; print(sorted(SUPPORTED_EVENTS))"
```
Expected: `['on_batch_loaded', 'on_key_event', 'on_navigate_next', 'on_navigate_prev', 'on_page_changed']`

- [ ] **Step 4: Commit**

```bash
git add web/api/services/__init__.py web/api/services/event_dispatcher.py
git commit -m "feat(web-api): event_dispatcher con mapeo a EventResult"
```

---

## Task 4: Router `events.py` con el endpoint POST

**Files:**
- Create: `web/api/routers/events.py`
- Modify: `web/api/main.py` (registrar)

- [ ] **Step 1: Escribir el router**

Crear `web/api/routers/events.py`:

```python
"""Router para eventos lifecycle del workbench web."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from web.api.deps import CurrentUser, SessionDep
from web.api.routers._helpers import get_batch_for_tenant
from web.api.schemas.event import EventFireIn, EventResult
from web.api.services.event_dispatcher import (
    EVENTS_REQUIRING_PAGE_ID,
    SUPPORTED_EVENTS,
    dispatch_event,
)
from app.models.page import Page

router = APIRouter(prefix="/api/batches", tags=["events"])


@router.post(
    "/{batch_id}/events/{event_name}",
    response_model=EventResult,
)
def fire_event(
    batch_id: int,
    event_name: str,
    payload: EventFireIn,
    user: CurrentUser,
    db: SessionDep,
) -> EventResult:
    """Ejecuta un evento lifecycle del workbench.

    - 404 si el lote no es del tenant.
    - 400 si ``event_name`` no es uno de los soportados.
    - 422 si faltan campos requeridos (``page_id`` para navegación/page_changed;
      ``key`` para on_key_event).
    - 404 si el ``page_id`` no pertenece al lote.
    - 200 con ``executed=false`` si el script no está definido.
    """
    if event_name not in SUPPORTED_EVENTS:
        raise HTTPException(
            status_code=400,
            detail=f"Evento no soportado: {event_name}",
        )

    if event_name in EVENTS_REQUIRING_PAGE_ID and payload.page_id is None:
        raise HTTPException(
            status_code=422,
            detail=f"page_id es requerido para {event_name}",
        )

    if event_name == "on_key_event" and not payload.key:
        raise HTTPException(
            status_code=422,
            detail="key es requerido para on_key_event",
        )

    batch = get_batch_for_tenant(batch_id, user.tenant_id, db)

    page: Page | None = None
    if payload.page_id is not None:
        page = (
            db.query(Page)
            .filter(Page.id == payload.page_id, Page.batch_id == batch_id)
            .first()
        )
        if page is None:
            raise HTTPException(
                status_code=404,
                detail="Página no pertenece al lote",
            )

    return dispatch_event(
        event_name=event_name,
        application=batch.application,
        batch=batch,
        page=page,
        key=payload.key,
        extra=payload.extra,
        session=db,
    )
```

- [ ] **Step 2: Registrar en `web/api/main.py`**

Leer `web/api/main.py` buscando los imports de routers y `include_router`. Añadir:

```python
from web.api.routers import events as events_router
...
app.include_router(events_router.router)
```

Colocarlo junto a los demás `include_router` (p.ej. `pages_router.router`).

- [ ] **Step 3: Ejecutar el test de la Task 2 y confirmar que pasa**

Run:
```bash
source .venv/bin/activate && DOCSCAN_WEB_DATABASE__URL="sqlite:///test.db" pytest tests/test_web_api.py::TestEventsFire::test_fire_script_no_definido_devuelve_executed_false -xvs
```
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add web/api/routers/events.py web/api/main.py
git commit -m "feat(web-api): endpoint POST /batches/:id/events/:name"
```

---

## Task 5: Tests backend — casos de éxito (on_batch_loaded ejecuta + result)

**Files:**
- Modify: `tests/test_web_api.py`

- [ ] **Step 1: Añadir helper y tests de ejecución básica**

En `tests/test_web_api.py`, dentro de `TestEventsFire`, tras el primer test, añadir:

```python
    def _set_event_script(self, client, h, application_id: int, event_name: str, script: str):
        """Helper: configura el script de un evento en events_json de la app."""
        resp = client.get(f"/api/applications/{application_id}", headers=h)
        events = resp.json().get("events_json") or "{}"
        import json as _json
        events_d = _json.loads(events)
        events_d[event_name] = script
        client.patch(
            f"/api/applications/{application_id}",
            headers=h,
            json={"events_json": _json.dumps(events_d)},
        )

    def test_fire_on_batch_loaded_ejecuta_devuelve_executed_true(self, client):
        h = _auth_header(client)
        app_id = _create_application(client, h)
        batch_id = _create_batch(client, h, app_id=app_id)
        self._set_event_script(
            client, h, app_id, "on_batch_loaded",
            "def on_batch_loaded(app, batch):\n    return {'result': 'hola'}\n",
        )
        resp = client.post(
            f"/api/batches/{batch_id}/events/on_batch_loaded",
            headers=h, json={},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["executed"] is True
        assert data["result"] == "hola"
        assert data["cancel"] is False

    def test_fire_on_navigate_prev_con_cancel_true(self, client):
        h = _auth_header(client)
        app_id = _create_application(client, h)
        batch_id = _create_batch(client, h, app_id=app_id)
        page_id = _upload_page(client, h, batch_id)
        self._set_event_script(
            client, h, app_id, "on_navigate_prev",
            "def on_navigate_prev(app, batch, page):\n    return False\n",
        )
        resp = client.post(
            f"/api/batches/{batch_id}/events/on_navigate_prev",
            headers=h, json={"page_id": page_id},
        )
        assert resp.status_code == 200
        assert resp.json()["cancel"] is True

    def test_fire_on_navigate_next_con_target_page_id(self, client):
        h = _auth_header(client)
        app_id = _create_application(client, h)
        batch_id = _create_batch(client, h, app_id=app_id)
        page_id = _upload_page(client, h, batch_id)
        self._set_event_script(
            client, h, app_id, "on_navigate_next",
            "def on_navigate_next(app, batch, page):\n"
            "    return {'target_page_id': 999}\n",
        )
        resp = client.post(
            f"/api/batches/{batch_id}/events/on_navigate_next",
            headers=h, json={"page_id": page_id},
        )
        assert resp.status_code == 200
        assert resp.json()["target_page_id"] == 999
```

Nota: si `_create_application` o `_upload_page` no existen como helpers, crearlos al principio del archivo siguiendo el patrón de `_create_batch`. Buscar con:

```bash
grep -nE "^def _create_application|^def _upload_page" tests/test_web_api.py
```

Si no existen, **saltar este paso y el siguiente**, añadirlos en una Task 5-bis (ver nota final del archivo).

- [ ] **Step 2: Ejecutar los 3 tests**

Run:
```bash
source .venv/bin/activate && DOCSCAN_WEB_DATABASE__URL="sqlite:///test.db" pytest tests/test_web_api.py::TestEventsFire -xvs
```
Expected: 4 PASS (1 original + 3 nuevos).

- [ ] **Step 3: Commit**

```bash
git add tests/test_web_api.py
git commit -m "test(web-api): casos de éxito eventos (ejecuta, cancel, target_page_id)"
```

---

## Task 6: Tests backend — casos de error y edge cases

**Files:**
- Modify: `tests/test_web_api.py`

- [ ] **Step 1: Añadir los 10 tests restantes**

En `TestEventsFire`, tras los de la Task 5:

```python
    def test_fire_on_page_changed_aplica_fields_updated(self, client):
        h = _auth_header(client)
        app_id = _create_application(client, h)
        batch_id = _create_batch(client, h, app_id=app_id)
        page_id = _upload_page(client, h, batch_id)
        self._set_event_script(
            client, h, app_id, "on_page_changed",
            "def on_page_changed(app, batch, page):\n"
            "    page.fields['cliente'] = 'Acme'\n",
        )
        resp = client.post(
            f"/api/batches/{batch_id}/events/on_page_changed",
            headers=h, json={"page_id": page_id},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["fields_updated"] == {"cliente": "Acme"}

    def test_fire_on_key_event_recibe_key(self, client):
        h = _auth_header(client)
        app_id = _create_application(client, h)
        batch_id = _create_batch(client, h, app_id=app_id)
        self._set_event_script(
            client, h, app_id, "on_key_event",
            "def on_key_event(app, batch, key):\n    return {'result': key}\n",
        )
        resp = client.post(
            f"/api/batches/{batch_id}/events/on_key_event",
            headers=h, json={"key": "Ctrl+Alt+L"},
        )
        assert resp.status_code == 200
        assert resp.json()["result"] == "Ctrl+Alt+L"

    def test_fire_script_lanza_devuelve_error(self, client):
        h = _auth_header(client)
        app_id = _create_application(client, h)
        batch_id = _create_batch(client, h, app_id=app_id)
        self._set_event_script(
            client, h, app_id, "on_batch_loaded",
            "def on_batch_loaded(app, batch):\n    raise RuntimeError('boom')\n",
        )
        resp = client.post(
            f"/api/batches/{batch_id}/events/on_batch_loaded",
            headers=h, json={},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["executed"] is True
        assert "boom" in (data["error"] or "")

    def test_fire_event_name_no_valido_400(self, client):
        h = _auth_header(client)
        batch_id = _create_batch(client, h)
        resp = client.post(
            f"/api/batches/{batch_id}/events/on_evento_raro",
            headers=h, json={},
        )
        assert resp.status_code == 400

    def test_fire_batch_otro_tenant_404(self, client):
        h1 = _auth_header(client)
        batch_id = _create_batch(client, h1)
        h2 = _auth_header(client, email="otro@docscan.example.com")
        resp = client.post(
            f"/api/batches/{batch_id}/events/on_batch_loaded",
            headers=h2, json={},
        )
        assert resp.status_code == 404

    def test_fire_on_navigate_prev_sin_page_id_422(self, client):
        h = _auth_header(client)
        batch_id = _create_batch(client, h)
        resp = client.post(
            f"/api/batches/{batch_id}/events/on_navigate_prev",
            headers=h, json={},
        )
        assert resp.status_code == 422

    def test_fire_on_key_event_sin_key_422(self, client):
        h = _auth_header(client)
        batch_id = _create_batch(client, h)
        resp = client.post(
            f"/api/batches/{batch_id}/events/on_key_event",
            headers=h, json={},
        )
        assert resp.status_code == 422

    def test_fire_on_page_changed_page_de_otro_lote_404(self, client):
        h = _auth_header(client)
        batch_a = _create_batch(client, h)
        batch_b = _create_batch(client, h)
        page_id_b = _upload_page(client, h, batch_b)
        resp = client.post(
            f"/api/batches/{batch_a}/events/on_page_changed",
            headers=h, json={"page_id": page_id_b},
        )
        assert resp.status_code == 404

    def test_fire_on_batch_loaded_permitido_durante_running(self, client, monkeypatch):
        h = _auth_header(client)
        app_id = _create_application(client, h)
        batch_id = _create_batch(client, h, app_id=app_id)
        # Forzar state="running" directamente en BD
        from web.api.deps import SessionLocal
        from app.models.batch import Batch
        with SessionLocal() as s:
            b = s.query(Batch).get(batch_id)
            b.state = "running"
            s.commit()
        self._set_event_script(
            client, h, app_id, "on_batch_loaded",
            "def on_batch_loaded(app, batch):\n    return {'result': batch.state}\n",
        )
        resp = client.post(
            f"/api/batches/{batch_id}/events/on_batch_loaded",
            headers=h, json={},
        )
        assert resp.status_code == 200
        assert resp.json()["result"] == "running"

    def test_fire_on_page_changed_permitido_durante_running(self, client):
        h = _auth_header(client)
        app_id = _create_application(client, h)
        batch_id = _create_batch(client, h, app_id=app_id)
        page_id = _upload_page(client, h, batch_id)
        from web.api.deps import SessionLocal
        from app.models.batch import Batch
        with SessionLocal() as s:
            b = s.query(Batch).get(batch_id)
            b.state = "running"
            s.commit()
        self._set_event_script(
            client, h, app_id, "on_page_changed",
            "def on_page_changed(app, batch, page):\n    return True\n",
        )
        resp = client.post(
            f"/api/batches/{batch_id}/events/on_page_changed",
            headers=h, json={"page_id": page_id},
        )
        assert resp.status_code == 200
        assert resp.json()["executed"] is True
```

Nota: `monkeypatch` aparece como parámetro; pytest lo inyecta automáticamente, no necesita configuración adicional.

- [ ] **Step 2: Ejecutar todos los tests de la clase**

Run:
```bash
source .venv/bin/activate && DOCSCAN_WEB_DATABASE__URL="sqlite:///test.db" pytest tests/test_web_api.py::TestEventsFire -xvs
```
Expected: 14 PASS.

- [ ] **Step 3: Ejecutar toda la suite backend para detectar regresiones**

Run:
```bash
source .venv/bin/activate && DOCSCAN_WEB_DATABASE__URL="sqlite:///test.db" pytest tests/test_web_api.py -q
```
Expected: 186 passed (172 antes + 14 nuevos).

- [ ] **Step 4: Commit**

```bash
git add tests/test_web_api.py
git commit -m "test(web-api): errores y edge cases del dispatcher de eventos"
```

---

## Task 5-bis: Helpers `_create_application` y `_upload_page` (si faltan)

**Solo necesaria si la búsqueda `grep -nE "^def _create_application|^def _upload_page" tests/test_web_api.py` no devuelve nada. Si ya existen, saltar esta task.**

**Files:**
- Modify: `tests/test_web_api.py`

- [ ] **Step 1: Añadir los helpers junto a `_create_batch`**

Buscar la definición de `_create_batch` y añadir justo encima:

```python
def _create_application(client, h, name: str = "TestApp") -> int:
    """Crea una aplicación vacía y devuelve su id."""
    resp = client.post(
        "/api/applications",
        headers=h,
        json={"name": name, "description": "Test app"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _upload_page(client, h, batch_id: int) -> int:
    """Sube un PNG dummy al lote y devuelve el page_id."""
    files = [("files", ("a.png", _make_png_bytes(), "image/png"))]
    resp = client.post(
        f"/api/batches/{batch_id}/pages",
        headers=h, files=files,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["created"][0]["id"]
```

Si `_create_batch` ya acepta `app_id`, revisar su firma; si no:

```python
def _create_batch(client, h, app_id: int | None = None) -> int:
    if app_id is None:
        app_id = _create_application(client, h)
    resp = client.post(
        "/api/batches",
        headers=h,
        json={"application_id": app_id},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]
```

- [ ] **Step 2: Commit**

```bash
git add tests/test_web_api.py
git commit -m "test(web-api): helpers _create_application y _upload_page para tests"
```

---

## Task 7: Endpoint `POST /api/pages/{id}/reprocess`

Nuevo endpoint síncrono para reprocesar el pipeline de una sola página. Habilita el shortcut `P` y es útil para debugging/testing de scripts.

**Files:**
- Modify: `web/api/routers/pages.py`
- Modify: `tests/test_web_api.py`

- [ ] **Step 1: Escribir los 4 tests primero**

En `tests/test_web_api.py`, añadir una nueva clase `TestPageReprocess` (tras `TestPagesRotate`):

```python
class TestPageReprocess:
    """Endpoint POST /api/pages/{id}/reprocess — re-ejecuta pipeline en 1 página."""

    def test_reprocess_pagina_devuelve_200_y_page_response(self, client):
        h = _auth_header(client)
        app_id = _create_application(client, h)
        batch_id = _create_batch(client, h, app_id=app_id)
        page_id = _upload_page(client, h, batch_id)
        resp = client.post(f"/api/pages/{page_id}/reprocess", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == page_id
        assert data["pipeline_processed"] is True

    def test_reprocess_reaplica_pipeline_fields(self, client):
        h = _auth_header(client)
        app_id = _create_application(client, h)
        # Configurar pipeline con ScriptStep que setea un field
        import json as _json
        pipeline = _json.dumps([{
            "id": "s1", "type": "script", "name": "Set", "enabled": True,
            "label": "S", "entry_point": "main",
            "script": "def main(page, batch, app, pipeline):\n    page.fields['reproc'] = 'ok'\n",
        }])
        client.patch(
            f"/api/applications/{app_id}",
            headers=h, json={"pipeline_json": pipeline},
        )
        batch_id = _create_batch(client, h, app_id=app_id)
        page_id = _upload_page(client, h, batch_id)
        # Reprocesar debe setear fields aunque la página ya no estaba processed
        resp = client.post(f"/api/pages/{page_id}/reprocess", headers=h)
        assert resp.status_code == 200
        fields = _json.loads(resp.json()["index_fields_json"])
        assert fields["reproc"] == "ok"

    def test_reprocess_page_no_existe_404(self, client):
        h = _auth_header(client)
        resp = client.post("/api/pages/9999999/reprocess", headers=h)
        assert resp.status_code == 404

    def test_reprocess_page_otro_tenant_404(self, client):
        h1 = _auth_header(client)
        batch_id = _create_batch(client, h1)
        page_id = _upload_page(client, h1, batch_id)
        h2 = _auth_header(client, email="otro@docscan.example.com")
        resp = client.post(f"/api/pages/{page_id}/reprocess", headers=h2)
        assert resp.status_code == 404

    def test_reprocess_bloqueado_durante_running_409(self, client):
        h = _auth_header(client)
        app_id = _create_application(client, h)
        batch_id = _create_batch(client, h, app_id=app_id)
        page_id = _upload_page(client, h, batch_id)
        from web.api.deps import SessionLocal
        from app.models.batch import Batch
        with SessionLocal() as s:
            b = s.query(Batch).get(batch_id)
            b.state = "running"
            s.commit()
        resp = client.post(f"/api/pages/{page_id}/reprocess", headers=h)
        assert resp.status_code == 409
```

- [ ] **Step 2: Ejecutar los tests y confirmar que fallan**

Run:
```bash
source .venv/bin/activate && DOCSCAN_WEB_DATABASE__URL="sqlite:///test.db" pytest tests/test_web_api.py::TestPageReprocess -xvs
```
Expected: FAIL con 404/405 (el endpoint no existe).

- [ ] **Step 3: Commit de los tests**

```bash
git add tests/test_web_api.py
git commit -m "test(web-api): TDD para reprocess de página individual"
```

- [ ] **Step 4: Implementar el endpoint en `web/api/routers/pages.py`**

Al final del archivo, tras `rotate_page`:

```python
@router.post("/pages/{page_id}/reprocess", response_model=PageResponse)
def reprocess_page(
    page_id: int,
    user: CurrentUser,
    db: SessionDep,
    storage: StorageDep,
) -> PageResponse:
    """Re-ejecuta el pipeline solo en esta página (síncrono).

    Útil para iterar sobre scripts durante desarrollo. Bloquea durante la
    ejecución y devuelve el PageResponse actualizado.

    - 404 si la página no existe o no pertenece al tenant.
    - 409 si el lote está en estado running/transferring.
    """
    from web.api.tasks.pipeline_runner import (
        _build_app_context, _build_batch_context, _process_page,
        _build_executor,
    )

    page = _get_page_for_user(page_id, user.tenant_id, db)
    batch = page.batch
    ensure_batch_mutable(batch, action="reprocesar página")

    executor, script_engine = _build_executor(batch.application)
    try:
        app_ctx = _build_app_context(batch.application)
        batch_ctx = _build_batch_context(batch)
        _process_page(page, executor, app_ctx, batch_ctx, storage, db)
        page.pipeline_processed = True
        db.commit()
        db.refresh(page)
    finally:
        script_engine.shutdown()

    return PageResponse.model_validate(page)
```

Si el helper `_get_page_for_user` no está importado, importarlo desde `_helpers.py` (o replicar su uso: `db.query(Page).join(Batch).filter(Page.id == page_id, Batch.tenant_id == user.tenant_id).first()`, 404 si `None`).

- [ ] **Step 5: Ejecutar los tests y verificar que pasan**

Run:
```bash
source .venv/bin/activate && DOCSCAN_WEB_DATABASE__URL="sqlite:///test.db" pytest tests/test_web_api.py::TestPageReprocess -xvs
```
Expected: 5 PASS.

- [ ] **Step 6: Ejecutar suite completa**

Run:
```bash
source .venv/bin/activate && DOCSCAN_WEB_DATABASE__URL="sqlite:///test.db" pytest tests/test_web_api.py -q
```
Expected: 191 passed (186 anteriores + 5 nuevos).

- [ ] **Step 7: Commit del endpoint backend**

```bash
git add web/api/routers/pages.py
git commit -m "feat(web-api): endpoint POST /api/pages/:id/reprocess"
```

- [ ] **Step 8: Añadir `reprocessPage` al composable frontend**

Editar `web/frontend/src/composables/usePageActions.ts`, añadir dentro del objeto retornado:

```typescript
    reprocessPage: (pageId: number) =>
      api.post(`/pages/${pageId}/reprocess`, {}),
```

- [ ] **Step 9: Extender test del composable**

Editar `web/frontend/tests/composables/usePageActions.test.ts` y añadir:

```typescript
  it('reprocessPage llama POST /pages/:id/reprocess', async () => {
    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({} as any)
    const actions = usePageActions()
    await actions.reprocessPage(42)
    expect(postSpy).toHaveBeenCalledWith('/pages/42/reprocess', {})
  })
```

- [ ] **Step 10: Ejecutar el test**

Run:
```bash
cd web/frontend && npx vitest run tests/composables/usePageActions.test.ts 2>&1 | tail -6
```
Expected: todos PASS (11 tests anteriores + 1 nuevo).

- [ ] **Step 11: Commit del composable**

```bash
git add web/frontend/src/composables/usePageActions.ts web/frontend/tests/composables/usePageActions.test.ts
git commit -m "feat(web-frontend): usePageActions.reprocessPage"
```

---

## Task 8: Catálogo único de shortcuts en TypeScript

**Files:**
- Create: `web/frontend/src/constants/shortcuts.ts`

- [ ] **Step 1: Crear el catálogo**

Crear `web/frontend/src/constants/shortcuts.ts`:

```typescript
/**
 * Catálogo único de atajos de teclado del Workbench web.
 * Usado tanto por useWorkbenchShortcuts como por ShortcutsHelpDialog.
 */

export type ShortcutCategory = 'batch' | 'edit' | 'nav' | 'zoom'

export interface ShortcutDef {
  /** Tecla en formato KeyboardEvent.key (o sintético: "Shift+ArrowRight"). */
  key: string
  /** Identificador del handler que se llamará (mapping en WorkbenchView). */
  action: ShortcutAction
  /** Texto humano para el cheatsheet. */
  label: string
  /** Categoría para el modal. */
  category: ShortcutCategory
  /** True si requiere !isReadOnly para ejecutarse. */
  editOnly: boolean
  /** Label amigable de la tecla (para el <kbd>). */
  display: string
}

export type ShortcutAction =
  | 'runPipeline'
  | 'transfer'
  | 'closeBatch'
  | 'openHelp'
  | 'rotate'
  | 'toggleReview'
  | 'toggleExcluded'
  | 'reprocessPage'
  | 'insertBarcode'
  | 'deletePage'
  | 'prevPage'
  | 'nextPage'
  | 'nextReviewPage'
  | 'navigateScript'
  | 'zoom100'
  | 'zoomIn'
  | 'zoomOut'
  | 'fitPage'

export const SHORTCUTS: ShortcutDef[] = [
  { key: 'F5', action: 'runPipeline', label: 'Ejecutar pipeline', category: 'batch', editOnly: true, display: 'F5' },
  { key: 't', action: 'transfer', label: 'Transferir lote', category: 'batch', editOnly: true, display: 'T' },
  { key: 'w', action: 'closeBatch', label: 'Cerrar lote', category: 'batch', editOnly: false, display: 'W' },
  { key: 'Escape', action: 'closeBatch', label: 'Cerrar lote', category: 'batch', editOnly: false, display: 'Esc' },
  { key: '?', action: 'openHelp', label: 'Abrir ayuda', category: 'batch', editOnly: false, display: '?' },
  { key: 'h', action: 'openHelp', label: 'Abrir ayuda', category: 'batch', editOnly: false, display: 'H' },

  { key: 'r', action: 'rotate', label: 'Rotar página 90°', category: 'edit', editOnly: true, display: 'R' },
  { key: 'm', action: 'toggleReview', label: 'Toggle revisión', category: 'edit', editOnly: true, display: 'M' },
  { key: 'x', action: 'toggleExcluded', label: 'Toggle excluida', category: 'edit', editOnly: true, display: 'X' },
  { key: 'p', action: 'reprocessPage', label: 'Reprocesar página', category: 'edit', editOnly: true, display: 'P' },
  { key: 'b', action: 'insertBarcode', label: 'Insertar barcode', category: 'edit', editOnly: true, display: 'B' },
  { key: 'Delete', action: 'deletePage', label: 'Eliminar página', category: 'edit', editOnly: true, display: 'Del' },

  { key: 'ArrowLeft', action: 'prevPage', label: 'Página anterior', category: 'nav', editOnly: false, display: '←' },
  { key: 'ArrowRight', action: 'nextPage', label: 'Página siguiente', category: 'nav', editOnly: false, display: '→' },
  { key: 'Shift+ArrowRight', action: 'nextReviewPage', label: 'Siguiente con revisión', category: 'nav', editOnly: false, display: 'Shift+→' },
  { key: 'Ctrl+g', action: 'navigateScript', label: 'Script de navegación', category: 'nav', editOnly: false, display: 'Ctrl+G' },

  { key: '0', action: 'zoom100', label: 'Zoom 100%', category: 'zoom', editOnly: false, display: '0' },
  { key: '+', action: 'zoomIn', label: 'Zoom in', category: 'zoom', editOnly: false, display: '+' },
  { key: '-', action: 'zoomOut', label: 'Zoom out', category: 'zoom', editOnly: false, display: '−' },
  { key: 'f', action: 'fitPage', label: 'Fit to page', category: 'zoom', editOnly: false, display: 'F' },
]

export const CATEGORY_LABELS: Record<ShortcutCategory, string> = {
  batch: 'Lote',
  edit: 'Edición',
  nav: 'Navegación',
  zoom: 'Zoom',
}

/**
 * Convierte un KeyboardEvent en el string sintético que usamos como índice.
 * Reglas:
 * - F5, Escape, ArrowLeft, ArrowRight, Delete: se devuelven tal cual.
 * - Shift+ArrowRight: combinación especial.
 * - Ctrl+g: Ctrl + letra minúscula.
 * - ?, +, -, 0, r, m, x, t, w, p, b, h, f: tecla tal cual (minúscula).
 */
export function eventToKeyString(event: KeyboardEvent): string {
  const k = event.key
  if (k === 'ArrowRight' && event.shiftKey) return 'Shift+ArrowRight'
  if (event.ctrlKey && !event.shiftKey && !event.altKey && k.length === 1) {
    return `Ctrl+${k.toLowerCase()}`
  }
  if (['F5', 'Escape', 'ArrowLeft', 'ArrowRight', 'Delete'].includes(k)) return k
  if (k.length === 1) return k.toLowerCase() === k ? k : k.toLowerCase()
  return k
}

/**
 * Devuelve la ShortcutDef que coincide con el evento, o null.
 */
export function matchShortcut(event: KeyboardEvent): ShortcutDef | null {
  const keyStr = eventToKeyString(event)
  return SHORTCUTS.find((s) => s.key === keyStr) || null
}
```

- [ ] **Step 2: Verificar que TypeScript compila**

Run:
```bash
cd web/frontend && npx vue-tsc --noEmit 2>&1 | head -20
```
Expected: sin errores.

- [ ] **Step 3: Commit**

```bash
git add web/frontend/src/constants/shortcuts.ts
git commit -m "feat(web-frontend): catálogo único de shortcuts con eventToKeyString"
```

---

## Task 9: Test de `useWorkbenchEvents`

**Files:**
- Create: `web/frontend/tests/composables/useWorkbenchEvents.test.ts`

- [ ] **Step 1: Escribir los 8 tests**

Crear el archivo:

```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useWorkbenchEvents } from '@/composables/useWorkbenchEvents'
import * as client from '@/api/client'

describe('useWorkbenchEvents', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('fireSync devuelve EventResult del backend', async () => {
    vi.spyOn(client, 'fireEvent').mockResolvedValue({
      executed: true, result: 'ok', cancel: false, target_page_id: null,
      fields_updated: {}, batch_fields_updated: {}, logs: [], error: null,
    })
    const events = useWorkbenchEvents(1)
    const res = await events.fireSync('on_batch_loaded', {})
    expect(res.executed).toBe(true)
    expect(res.result).toBe('ok')
  })

  it('fireSync respeta cancel=true', async () => {
    vi.spyOn(client, 'fireEvent').mockResolvedValue({
      executed: true, result: null, cancel: true, target_page_id: null,
      fields_updated: {}, batch_fields_updated: {}, logs: [], error: null,
    })
    const events = useWorkbenchEvents(1)
    const res = await events.fireSync('on_navigate_prev', { page_id: 7 })
    expect(res.cancel).toBe(true)
  })

  it('fireSync propaga target_page_id', async () => {
    vi.spyOn(client, 'fireEvent').mockResolvedValue({
      executed: true, result: null, cancel: false, target_page_id: 42,
      fields_updated: {}, batch_fields_updated: {}, logs: [], error: null,
    })
    const events = useWorkbenchEvents(1)
    const res = await events.fireSync('on_navigate_next', { page_id: 7 })
    expect(res.target_page_id).toBe(42)
  })

  it('fireAsync no bloquea y devuelve undefined', () => {
    vi.spyOn(client, 'fireEvent').mockResolvedValue({
      executed: true, result: null, cancel: false, target_page_id: null,
      fields_updated: {}, batch_fields_updated: {}, logs: [], error: null,
    })
    const events = useWorkbenchEvents(1)
    const r = events.fireAsync('on_page_changed', { page_id: 7 })
    expect(r).toBeUndefined()
  })

  it('fireAsync aplica throttle 100ms para el mismo evento', async () => {
    const spy = vi.spyOn(client, 'fireEvent').mockResolvedValue({
      executed: true, result: null, cancel: false, target_page_id: null,
      fields_updated: {}, batch_fields_updated: {}, logs: [], error: null,
    })
    const events = useWorkbenchEvents(1)
    events.fireAsync('on_page_changed', { page_id: 7 })
    events.fireAsync('on_page_changed', { page_id: 7 })
    events.fireAsync('on_page_changed', { page_id: 7 })
    expect(spy).toHaveBeenCalledTimes(1)
  })

  it('error del backend se captura y devuelve executed=false synthético', async () => {
    vi.spyOn(client, 'fireEvent').mockRejectedValue(new Error('network'))
    const events = useWorkbenchEvents(1)
    const res = await events.fireSync('on_batch_loaded', {})
    expect(res.executed).toBe(false)
    expect(res.error).toContain('network')
  })

  it('fields_updated disparan callback onApplyPageFields', async () => {
    vi.spyOn(client, 'fireEvent').mockResolvedValue({
      executed: true, result: null, cancel: false, target_page_id: null,
      fields_updated: { cliente: 'Acme' }, batch_fields_updated: {}, logs: [], error: null,
    })
    const onApply = vi.fn()
    const events = useWorkbenchEvents(1, { onApplyPageFields: onApply })
    await events.fireSync('on_page_changed', { page_id: 7 })
    expect(onApply).toHaveBeenCalledWith(7, { cliente: 'Acme' })
  })

  it('batch_fields_updated disparan callback onApplyBatchFields', async () => {
    vi.spyOn(client, 'fireEvent').mockResolvedValue({
      executed: true, result: null, cancel: false, target_page_id: null,
      fields_updated: {}, batch_fields_updated: { total: 5 }, logs: [], error: null,
    })
    const onApply = vi.fn()
    const events = useWorkbenchEvents(1, { onApplyBatchFields: onApply })
    await events.fireSync('on_batch_loaded', {})
    expect(onApply).toHaveBeenCalledWith({ total: 5 })
  })
})
```

- [ ] **Step 2: Ejecutar y confirmar que fallan por falta de `fireEvent` en client**

Run:
```bash
cd web/frontend && npx vitest run tests/composables/useWorkbenchEvents.test.ts 2>&1 | tail -15
```
Expected: FAIL — `fireEvent is not a function` o similar.

- [ ] **Step 3: Commit de los tests**

```bash
git add web/frontend/tests/composables/useWorkbenchEvents.test.ts
git commit -m "test(web-frontend): tests TDD para useWorkbenchEvents"
```

---

## Task 10: Cliente API `fireEvent` y tipos TS

**Files:**
- Modify: `web/frontend/src/api/types.ts`
- Modify: `web/frontend/src/api/client.ts`

- [ ] **Step 1: Añadir tipos a `types.ts`**

Al final de `web/frontend/src/api/types.ts`:

```typescript
// --- Events ---

export interface EventFireIn {
  page_id?: number | null
  key?: string | null
  extra?: Record<string, unknown>
}

export interface EventResult {
  executed: boolean
  result: unknown
  cancel: boolean
  target_page_id: number | null
  fields_updated: Record<string, unknown>
  batch_fields_updated: Record<string, unknown>
  logs: { level: string; message: string }[]
  error: string | null
}
```

- [ ] **Step 2: Añadir el método `fireEvent` a `client.ts`**

Buscar un método similar (p.ej. `patchPage`) y añadir junto a él:

```typescript
export async function fireEvent(
  batchId: number,
  eventName: string,
  payload: EventFireIn = {},
): Promise<EventResult> {
  return api.post<EventResult>(`/batches/${batchId}/events/${eventName}`, payload)
}
```

Añadir el import de `EventFireIn` y `EventResult` arriba del archivo si no estaban:

```typescript
import type { ..., EventFireIn, EventResult } from './types'
```

- [ ] **Step 3: Verificar TypeScript**

Run:
```bash
cd web/frontend && npx vue-tsc --noEmit 2>&1 | head -10
```
Expected: sin errores.

- [ ] **Step 4: Commit**

```bash
git add web/frontend/src/api/types.ts web/frontend/src/api/client.ts
git commit -m "feat(web-frontend): tipo EventResult + cliente fireEvent"
```

---

## Task 11: Implementación de `useWorkbenchEvents`

**Files:**
- Create: `web/frontend/src/composables/useWorkbenchEvents.ts`

- [ ] **Step 1: Escribir el composable**

Crear:

```typescript
import { fireEvent as apiFireEvent } from '@/api/client'
import type { EventFireIn, EventResult } from '@/api/types'

interface EventsOptions {
  onApplyPageFields?: (pageId: number, fields: Record<string, unknown>) => void
  onApplyBatchFields?: (fields: Record<string, unknown>) => void
  onLogs?: (logs: { level: string; message: string }[]) => void
}

const THROTTLE_MS = 100

/**
 * Dispara eventos lifecycle del workbench contra el backend.
 * - fireSync: POST con await, devuelve EventResult.
 * - fireAsync: POST sin await. Aplica throttle por (event, page_id) para
 *   evitar doble dispatch en mismo frame.
 */
export function useWorkbenchEvents(batchId: number, options: EventsOptions = {}) {
  const lastFired = new Map<string, number>()

  function throttleKey(name: string, payload: EventFireIn): string {
    return `${name}:${payload.page_id ?? 0}`
  }

  function applyResult(result: EventResult, payload: EventFireIn): void {
    if (result.fields_updated && Object.keys(result.fields_updated).length && payload.page_id) {
      options.onApplyPageFields?.(payload.page_id, result.fields_updated)
    }
    if (result.batch_fields_updated && Object.keys(result.batch_fields_updated).length) {
      options.onApplyBatchFields?.(result.batch_fields_updated)
    }
    if (result.logs && result.logs.length) {
      options.onLogs?.(result.logs)
    }
  }

  async function fireSync(name: string, payload: EventFireIn = {}): Promise<EventResult> {
    try {
      const res = await apiFireEvent(batchId, name, payload)
      applyResult(res, payload)
      return res
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      return {
        executed: false, result: null, cancel: false, target_page_id: null,
        fields_updated: {}, batch_fields_updated: {}, logs: [], error: msg,
      }
    }
  }

  function fireAsync(name: string, payload: EventFireIn = {}): void {
    const k = throttleKey(name, payload)
    const now = Date.now()
    const last = lastFired.get(k) ?? 0
    if (now - last < THROTTLE_MS) return
    lastFired.set(k, now)
    apiFireEvent(batchId, name, payload)
      .then((res) => applyResult(res, payload))
      .catch((e) => {
        const msg = e instanceof Error ? e.message : String(e)
        options.onLogs?.([{ level: 'error', message: `Evento ${name}: ${msg}` }])
      })
  }

  return { fireSync, fireAsync }
}
```

- [ ] **Step 2: Ejecutar los 8 tests y verificar que pasan**

Run:
```bash
cd web/frontend && npx vitest run tests/composables/useWorkbenchEvents.test.ts 2>&1 | tail -10
```
Expected: 8 PASS.

- [ ] **Step 3: Commit**

```bash
git add web/frontend/src/composables/useWorkbenchEvents.ts
git commit -m "feat(web-frontend): useWorkbenchEvents con fireSync/fireAsync y throttle"
```

---

## Task 12: Test de `useWorkbenchShortcuts`

**Files:**
- Create: `web/frontend/tests/composables/useWorkbenchShortcuts.test.ts`

- [ ] **Step 1: Escribir 12 tests**

Crear:

```typescript
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { useWorkbenchShortcuts } from '@/composables/useWorkbenchShortcuts'
import type { ShortcutAction } from '@/constants/shortcuts'

function makeHost(handlers: Partial<Record<ShortcutAction, () => void>>, isReadOnly = false) {
  return defineComponent({
    setup() {
      useWorkbenchShortcuts({
        handlers,
        isReadOnly: () => isReadOnly,
        fireKeyEvent: () => {},
      })
      return () => h('div', 'host')
    },
  })
}

function dispatchKey(opts: Partial<KeyboardEventInit & { key: string }>, target?: HTMLElement) {
  const ev = new KeyboardEvent('keydown', { bubbles: true, cancelable: true, ...opts })
  ;(target ?? document.body).dispatchEvent(ev)
  return ev
}

describe('useWorkbenchShortcuts', () => {
  let wrapper: ReturnType<typeof mount>

  afterEach(() => {
    wrapper?.unmount()
  })

  it('tecla R dispara rotate', () => {
    const rotate = vi.fn()
    wrapper = mount(makeHost({ rotate }))
    dispatchKey({ key: 'r' })
    expect(rotate).toHaveBeenCalled()
  })

  it('F5 dispara runPipeline y preventDefault', () => {
    const runPipeline = vi.fn()
    wrapper = mount(makeHost({ runPipeline }))
    const ev = dispatchKey({ key: 'F5' })
    expect(runPipeline).toHaveBeenCalled()
    expect(ev.defaultPrevented).toBe(true)
  })

  it('? abre el modal de ayuda', () => {
    const openHelp = vi.fn()
    wrapper = mount(makeHost({ openHelp }))
    dispatchKey({ key: '?' })
    expect(openHelp).toHaveBeenCalled()
  })

  it('Delete dispara deletePage', () => {
    const deletePage = vi.fn()
    wrapper = mount(makeHost({ deletePage }))
    dispatchKey({ key: 'Delete' })
    expect(deletePage).toHaveBeenCalled()
  })

  it('ArrowRight dispara nextPage', () => {
    const nextPage = vi.fn()
    wrapper = mount(makeHost({ nextPage }))
    dispatchKey({ key: 'ArrowRight' })
    expect(nextPage).toHaveBeenCalled()
  })

  it('Shift+ArrowRight dispara nextReviewPage', () => {
    const nextReviewPage = vi.fn()
    wrapper = mount(makeHost({ nextReviewPage }))
    dispatchKey({ key: 'ArrowRight', shiftKey: true })
    expect(nextReviewPage).toHaveBeenCalled()
  })

  it('input enfocado ignora R', () => {
    const rotate = vi.fn()
    wrapper = mount(makeHost({ rotate }))
    const input = document.createElement('input')
    document.body.appendChild(input)
    input.focus()
    dispatchKey({ key: 'r' }, input)
    expect(rotate).not.toHaveBeenCalled()
    input.remove()
  })

  it('textarea enfocada ignora R', () => {
    const rotate = vi.fn()
    wrapper = mount(makeHost({ rotate }))
    const ta = document.createElement('textarea')
    document.body.appendChild(ta)
    ta.focus()
    dispatchKey({ key: 'r' }, ta)
    expect(rotate).not.toHaveBeenCalled()
    ta.remove()
  })

  it('elemento contenteditable ignora R', () => {
    const rotate = vi.fn()
    wrapper = mount(makeHost({ rotate }))
    const div = document.createElement('div')
    div.setAttribute('contenteditable', 'true')
    document.body.appendChild(div)
    div.focus()
    dispatchKey({ key: 'r' }, div)
    expect(rotate).not.toHaveBeenCalled()
    div.remove()
  })

  it('isReadOnly oculta acciones de edición pero permite navegación', () => {
    const rotate = vi.fn()
    const nextPage = vi.fn()
    wrapper = mount(makeHost({ rotate, nextPage }, true))
    dispatchKey({ key: 'r' })
    dispatchKey({ key: 'ArrowRight' })
    expect(rotate).not.toHaveBeenCalled()
    expect(nextPage).toHaveBeenCalled()
  })

  it('tecla con modificador no mapeada dispara fireKeyEvent', () => {
    const fireKeyEvent = vi.fn()
    const Host = defineComponent({
      setup() {
        useWorkbenchShortcuts({
          handlers: {},
          isReadOnly: () => false,
          fireKeyEvent,
        })
        return () => h('div')
      },
    })
    wrapper = mount(Host)
    dispatchKey({ key: 'l', ctrlKey: true, altKey: true })
    expect(fireKeyEvent).toHaveBeenCalledWith('Ctrl+l')
  })

  it('unmount elimina el listener', () => {
    const rotate = vi.fn()
    wrapper = mount(makeHost({ rotate }))
    wrapper.unmount()
    dispatchKey({ key: 'r' })
    expect(rotate).not.toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Ejecutar y confirmar que fallan**

Run:
```bash
cd web/frontend && npx vitest run tests/composables/useWorkbenchShortcuts.test.ts 2>&1 | tail -10
```
Expected: FAIL — el composable no existe.

- [ ] **Step 3: Commit**

```bash
git add web/frontend/tests/composables/useWorkbenchShortcuts.test.ts
git commit -m "test(web-frontend): tests TDD para useWorkbenchShortcuts"
```

---

## Task 13: Implementación de `useWorkbenchShortcuts`

**Files:**
- Create: `web/frontend/src/composables/useWorkbenchShortcuts.ts`

- [ ] **Step 1: Escribir el composable**

```typescript
import { onMounted, onUnmounted } from 'vue'
import {
  SHORTCUTS,
  matchShortcut,
  eventToKeyString,
  type ShortcutAction,
} from '@/constants/shortcuts'

interface ShortcutsOptions {
  handlers: Partial<Record<ShortcutAction, () => void | Promise<void>>>
  isReadOnly: () => boolean
  fireKeyEvent?: (key: string) => void
}

/**
 * Captura keydown global y dispara handlers según el catálogo de shortcuts.
 *
 * - Ignora si el foco está en input/textarea/select/contenteditable o dentro
 *   de un [role=dialog].
 * - Respeta isReadOnly: las acciones con editOnly=true son no-op.
 * - Teclas no mapeadas con modificador (Ctrl/Alt/Meta) se reenvían como
 *   on_key_event vía fireKeyEvent.
 */
export function useWorkbenchShortcuts(options: ShortcutsOptions) {
  function isEditableTarget(target: EventTarget | null): boolean {
    if (!(target instanceof HTMLElement)) return false
    const tag = target.tagName
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true
    if (target.isContentEditable) return true
    if (target.closest('[role="dialog"]')) return true
    return false
  }

  function onKeyDown(event: KeyboardEvent): void {
    if (isEditableTarget(event.target)) return

    const shortcut = matchShortcut(event)
    if (shortcut) {
      if (shortcut.editOnly && options.isReadOnly()) {
        event.preventDefault()
        return
      }
      event.preventDefault()
      const handler = options.handlers[shortcut.action]
      handler?.()
      return
    }

    // No mapeada: si tiene modificador y hay fireKeyEvent, enviar como on_key_event
    if ((event.ctrlKey || event.altKey || event.metaKey) && options.fireKeyEvent) {
      const keyStr = eventToKeyString(event)
      options.fireKeyEvent(keyStr)
    }
  }

  onMounted(() => {
    document.addEventListener('keydown', onKeyDown, { capture: true })
  })

  onUnmounted(() => {
    document.removeEventListener('keydown', onKeyDown, { capture: true })
  })

  return { SHORTCUTS }
}
```

- [ ] **Step 2: Ejecutar los tests y verificar que pasan**

Run:
```bash
cd web/frontend && npx vitest run tests/composables/useWorkbenchShortcuts.test.ts 2>&1 | tail -10
```
Expected: 12 PASS.

- [ ] **Step 3: Commit**

```bash
git add web/frontend/src/composables/useWorkbenchShortcuts.ts
git commit -m "feat(web-frontend): useWorkbenchShortcuts con filtro de foco y fallback on_key_event"
```

---

## Task 14: Test de `ShortcutsHelpDialog`

**Files:**
- Create: `web/frontend/tests/components/workbench/ShortcutsHelpDialog.test.ts`

- [ ] **Step 1: Escribir 4 tests**

```typescript
import { describe, it, expect, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ShortcutsHelpDialog from '@/components/workbench/ShortcutsHelpDialog.vue'

describe('ShortcutsHelpDialog', () => {
  let wrapper: ReturnType<typeof mount>
  afterEach(() => wrapper?.unmount())

  it('renderiza cuando isOpen=true', () => {
    wrapper = mount(ShortcutsHelpDialog, { props: { isOpen: true } })
    expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Lote')
    expect(wrapper.text()).toContain('Edición')
    expect(wrapper.text()).toContain('Navegación')
    expect(wrapper.text()).toContain('Zoom')
  })

  it('no renderiza cuando isOpen=false', () => {
    wrapper = mount(ShortcutsHelpDialog, { props: { isOpen: false } })
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
  })

  it('emite close al pulsar Escape', async () => {
    wrapper = mount(ShortcutsHelpDialog, { props: { isOpen: true } })
    await wrapper.find('[role="dialog"]').trigger('keydown', { key: 'Escape' })
    expect(wrapper.emitted('close')).toBeTruthy()
  })

  it('muestra al menos 15 filas de shortcuts', () => {
    wrapper = mount(ShortcutsHelpDialog, { props: { isOpen: true } })
    const kbds = wrapper.findAll('kbd')
    expect(kbds.length).toBeGreaterThanOrEqual(15)
  })
})
```

- [ ] **Step 2: Ejecutar y confirmar que fallan**

Run:
```bash
cd web/frontend && npx vitest run tests/components/workbench/ShortcutsHelpDialog.test.ts 2>&1 | tail -10
```
Expected: FAIL.

- [ ] **Step 3: Commit**

```bash
git add web/frontend/tests/components/workbench/ShortcutsHelpDialog.test.ts
git commit -m "test(web-frontend): tests TDD para ShortcutsHelpDialog"
```

---

## Task 15: Implementación de `ShortcutsHelpDialog.vue`

**Files:**
- Create: `web/frontend/src/components/workbench/ShortcutsHelpDialog.vue`

- [ ] **Step 1: Escribir el componente**

```vue
<script setup lang="ts">
import { computed } from 'vue'
import { SHORTCUTS, CATEGORY_LABELS, type ShortcutCategory } from '@/constants/shortcuts'

defineProps<{ isOpen: boolean }>()
const emit = defineEmits<{ (e: 'close'): void }>()

const grouped = computed(() => {
  const map: Record<ShortcutCategory, typeof SHORTCUTS> = {
    batch: [], edit: [], nav: [], zoom: [],
  }
  for (const s of SHORTCUTS) map[s.category].push(s)
  return map
})

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') emit('close')
}
</script>

<template>
  <div
    v-if="isOpen"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
    @click.self="emit('close')"
  >
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Atajos de teclado"
      tabindex="-1"
      class="bg-base text-text rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto"
      @keydown="onKeydown"
    >
      <div class="flex items-center justify-between px-4 py-3 border-b border-surface-1">
        <h2 class="text-lg font-semibold">Atajos de teclado</h2>
        <button
          type="button"
          class="text-text-muted hover:text-text"
          aria-label="Cerrar"
          @click="emit('close')"
        >
          ✕
        </button>
      </div>
      <div class="p-4 space-y-4">
        <section v-for="(items, cat) in grouped" :key="cat">
          <h3 class="text-sm font-semibold uppercase tracking-wide text-text-muted mb-2">
            {{ CATEGORY_LABELS[cat as ShortcutCategory] }}
          </h3>
          <table class="w-full">
            <tbody>
              <tr v-for="s in items" :key="`${cat}-${s.key}`" class="border-b border-surface-1 last:border-0">
                <td class="py-1 w-24">
                  <kbd class="px-2 py-0.5 bg-surface-0 rounded text-xs font-mono">{{ s.display }}</kbd>
                </td>
                <td class="py-1 text-sm">{{ s.label }}</td>
              </tr>
            </tbody>
          </table>
        </section>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 2: Ejecutar los tests y verificar que pasan**

Run:
```bash
cd web/frontend && npx vitest run tests/components/workbench/ShortcutsHelpDialog.test.ts 2>&1 | tail -10
```
Expected: 4 PASS.

- [ ] **Step 3: Commit**

```bash
git add web/frontend/src/components/workbench/ShortcutsHelpDialog.vue
git commit -m "feat(web-frontend): ShortcutsHelpDialog con 4 categorías"
```

---

## Task 16: Actualizar catálogo `events-catalog.ts` y su test

**Files:**
- Modify: `web/frontend/src/api/events-catalog.ts`
- Modify: `web/frontend/tests/api/events-catalog.test.ts`

- [ ] **Step 1: Añadir los 5 eventos al catálogo**

En `web/frontend/src/api/events-catalog.ts`, después de las constantes `BASE_VARS`/`PAGE_VAR` y antes de `EVENT_DEFINITIONS`, añadir:

```typescript
const BASE_WITH_PAGE_VARS: ContextVariable[] = [...BASE_VARS, PAGE_VAR]

const KEY_VAR: ContextVariable = {
  name: 'key',
  summary: 'str — Tecla pulsada en formato "Ctrl+Alt+L" o similar.',
  members: [],
}
```

Luego, dentro del array `EVENT_DEFINITIONS`, añadir al final (antes del `]` de cierre):

```typescript
  {
    name: 'on_batch_loaded',
    description: 'Se dispara al abrir el lote en el workbench. Retornar {cancel: true} impide la carga.',
    signature: 'def on_batch_loaded(app, batch)',
    template:
      'def on_batch_loaded(app, batch):\n' +
      '    """Se ejecuta al abrir el lote."""\n' +
      '    pass\n',
    contextVariables: BASE_VARS,
  },
  {
    name: 'on_navigate_prev',
    description: 'Antes de navegar a la página anterior. Retornar {cancel: true} o {target_page_id: N}.',
    signature: 'def on_navigate_prev(app, batch, page)',
    template:
      'def on_navigate_prev(app, batch, page):\n' +
      '    """Controla la navegación previa."""\n' +
      '    return None\n',
    contextVariables: BASE_WITH_PAGE_VARS,
  },
  {
    name: 'on_navigate_next',
    description: 'Antes de navegar a la página siguiente. Retornar {cancel: true} o {target_page_id: N}.',
    signature: 'def on_navigate_next(app, batch, page)',
    template:
      'def on_navigate_next(app, batch, page):\n' +
      '    """Controla la navegación siguiente."""\n' +
      '    return None\n',
    contextVariables: BASE_WITH_PAGE_VARS,
  },
  {
    name: 'on_page_changed',
    description: 'Tras cambiar a una página. Fire-and-forget. Puede mutar page.fields para actualizar la UI.',
    signature: 'def on_page_changed(app, batch, page)',
    template:
      'def on_page_changed(app, batch, page):\n' +
      '    """Al navegar a otra página."""\n' +
      '    pass\n',
    contextVariables: BASE_WITH_PAGE_VARS,
  },
  {
    name: 'on_key_event',
    description: 'Tecla pulsada no mapeada por defecto. Fire-and-forget.',
    signature: 'def on_key_event(app, batch, key)',
    template:
      'def on_key_event(app, batch, key):\n' +
      '    """Maneja teclas custom."""\n' +
      '    pass\n',
    contextVariables: [...BASE_VARS, KEY_VAR],
  },
```

- [ ] **Step 2: Actualizar el test de paridad**

En `web/frontend/tests/api/events-catalog.test.ts`, reemplazar el primer test:

```typescript
  it('EVENT_DEFINITIONS contiene los 9 eventos (4 originales + 5 Fase 4)', () => {
    expect(EVENT_DEFINITIONS).toHaveLength(9)
    const names = EVENT_DEFINITIONS.map((e) => e.name)
    expect(names).toContain('on_scan_complete')
    expect(names).toContain('on_transfer_validate')
    expect(names).toContain('on_transfer_advanced')
    expect(names).toContain('on_transfer_page')
    expect(names).toContain('on_batch_loaded')
    expect(names).toContain('on_navigate_prev')
    expect(names).toContain('on_navigate_next')
    expect(names).toContain('on_page_changed')
    expect(names).toContain('on_key_event')
  })
```

Y añadir tests nuevos:

```typescript
  it('on_key_event tiene key en contextVariables', () => {
    const event = EVENT_DEFINITIONS.find((e) => e.name === 'on_key_event')!
    const names = event.contextVariables.map((v) => v.name)
    expect(names).toContain('key')
  })

  it('on_navigate_prev tiene page en contextVariables', () => {
    const event = EVENT_DEFINITIONS.find((e) => e.name === 'on_navigate_prev')!
    const names = event.contextVariables.map((v) => v.name)
    expect(names).toContain('page')
  })

  it('on_batch_loaded template empieza con def on_batch_loaded(', () => {
    const event = EVENT_DEFINITIONS.find((e) => e.name === 'on_batch_loaded')!
    expect(event.template.startsWith('def on_batch_loaded(')).toBe(true)
  })
```

- [ ] **Step 3: Ejecutar todos los tests del archivo**

Run:
```bash
cd web/frontend && npx vitest run tests/api/events-catalog.test.ts 2>&1 | tail -10
```
Expected: todos PASS.

- [ ] **Step 4: Commit**

```bash
git add web/frontend/src/api/events-catalog.ts web/frontend/tests/api/events-catalog.test.ts
git commit -m "feat(web-frontend): 5 eventos Fase 4 en events-catalog"
```

---

## Task 17: Wiring en `WorkbenchView.vue` — eventos on_batch_loaded + on_page_changed

**Files:**
- Modify: `web/frontend/src/views/batches/WorkbenchView.vue`

- [ ] **Step 1: Añadir el composable y wiring de los 2 eventos**

Leer `web/frontend/src/views/batches/WorkbenchView.vue` y localizar:
- El bloque de imports al principio
- El `onMounted(async () => {...})`
- El `watch` sobre `currentPage` (si no existe, identificar dónde cambia la página actual y añadir el watch)

**Import** (junto a los demás composables):
```typescript
import { useWorkbenchEvents } from '@/composables/useWorkbenchEvents'
```

**Instanciar** (cerca de donde se usan `log`, `events`):
```typescript
const workbenchEvents = useWorkbenchEvents(batchId.value, {
  onApplyPageFields: (pageId, fields) => {
    store.patchPageFields?.(pageId, fields)
  },
  onApplyBatchFields: (fields) => {
    store.patchBatchFields?.(fields)
  },
  onLogs: (logs) => {
    logs.forEach((l) => log.append({ level: l.level as 'info' | 'warning' | 'error', source: 'script', message: l.message }))
  },
})
```

Nota: si `store.patchPageFields` / `patchBatchFields` no existen, usar `store.fetchPage(batchId.value, pageId)` / `store.fetchOne(batchId.value)` respectivamente.

**En `onMounted`** (al final, tras cargar batch+pages):
```typescript
const loaded = await workbenchEvents.fireSync('on_batch_loaded')
if (loaded.cancel) {
  toast.error('Carga del lote cancelada por script')
  router.push('/batches')
  return
}
```

**Watch sobre `currentPage`** (si no existe, añadir):
```typescript
watch(
  () => currentPage.value?.id,
  (newId, oldId) => {
    if (newId && newId !== oldId) {
      workbenchEvents.fireAsync('on_page_changed', { page_id: newId })
    }
  },
)
```

- [ ] **Step 2: Type-check**

Run:
```bash
cd web/frontend && npx vue-tsc --noEmit 2>&1 | tail -10
```
Expected: sin errores relacionados con el cambio.

- [ ] **Step 3: Commit**

```bash
git add web/frontend/src/views/batches/WorkbenchView.vue
git commit -m "feat(web-frontend): wiring on_batch_loaded y on_page_changed"
```

---

## Task 18: Wiring en `WorkbenchView.vue` — navegación con on_navigate_prev/next

**Files:**
- Modify: `web/frontend/src/views/batches/WorkbenchView.vue`

- [ ] **Step 1: Refactorizar los handlers de navegación**

Buscar `goPrev`/`goNext` o las funciones que responden al botón `←`/`→` del toolbar. Envolver:

```typescript
async function goPrev() {
  const currentId = currentPage.value?.id
  if (!currentId) return
  const res = await workbenchEvents.fireSync('on_navigate_prev', { page_id: currentId })
  if (res.cancel) return
  if (res.target_page_id != null) {
    const idx = pages.value.findIndex((p) => p.id === res.target_page_id)
    if (idx >= 0) selectedIndex.value = idx
    return
  }
  if (selectedIndex.value > 0) selectedIndex.value--
}

async function goNext() {
  const currentId = currentPage.value?.id
  if (!currentId) return
  const res = await workbenchEvents.fireSync('on_navigate_next', { page_id: currentId })
  if (res.cancel) return
  if (res.target_page_id != null) {
    const idx = pages.value.findIndex((p) => p.id === res.target_page_id)
    if (idx >= 0) selectedIndex.value = idx
    return
  }
  if (selectedIndex.value < pages.value.length - 1) selectedIndex.value++
}
```

Nombres reales de refs (`selectedIndex`, `pages`) se adaptan al código actual.

- [ ] **Step 2: Type-check y tests existentes**

Run:
```bash
cd web/frontend && npx vue-tsc --noEmit 2>&1 | tail -10
cd web/frontend && npx vitest run tests/views/batches/WorkbenchView.test.ts 2>&1 | tail -10
```
Expected: sin errores nuevos; los tests actuales siguen pasando (puede ser necesario ajustar mocks).

- [ ] **Step 3: Commit**

```bash
git add web/frontend/src/views/batches/WorkbenchView.vue
git commit -m "feat(web-frontend): navegación prev/next respeta on_navigate_*"
```

---

## Task 19: Wiring en `WorkbenchView.vue` — shortcuts + dialog de ayuda

**Files:**
- Modify: `web/frontend/src/views/batches/WorkbenchView.vue`
- Modify: `web/frontend/src/components/workbench/WorkbenchToolbar.vue` (botón "?")

- [ ] **Step 1: Añadir `useWorkbenchShortcuts` y handlers**

En `WorkbenchView.vue`:

```typescript
import { useWorkbenchShortcuts } from '@/composables/useWorkbenchShortcuts'
import ShortcutsHelpDialog from '@/components/workbench/ShortcutsHelpDialog.vue'
```

Añadir ref para el dialog:
```typescript
const helpDialogOpen = ref(false)
```

Y el composable (después de `workbenchEvents`):

```typescript
useWorkbenchShortcuts({
  isReadOnly: () => isReadOnly.value,
  fireKeyEvent: (key) => workbenchEvents.fireAsync('on_key_event', { key }),
  handlers: {
    runPipeline: () => onRunPipeline(),
    transfer: () => onTransfer(),
    closeBatch: () => router.push('/batches'),
    openHelp: () => { helpDialogOpen.value = true },
    rotate: async () => {
      if (!currentPage.value) return
      await pageActions.rotatePage(currentPage.value.id, 1)
      await refreshCurrent()
    },
    toggleReview: async () => {
      if (!currentPage.value) return
      await pageActions.toggleReview(currentPage.value.id, !currentPage.value.needs_review)
      await refreshCurrent()
    },
    toggleExcluded: async () => {
      if (!currentPage.value) return
      await pageActions.toggleExcluded(currentPage.value.id, !currentPage.value.is_excluded)
      await refreshCurrent()
    },
    reprocessPage: async () => {
      if (!currentPage.value) return
      await pageActions.reprocessPage(currentPage.value.id)
      await refreshCurrent()
    },
    insertBarcode: () => { addBarcodeDialogOpen.value = true },
    deletePage: () => currentPage.value && onDeletePage(currentPage.value.id),
    prevPage: () => goPrev(),
    nextPage: () => goNext(),
    nextReviewPage: () => goNextReview(),
    navigateScript: () => workbenchEvents.fireAsync('on_navigate_script', { page_id: currentPage.value?.id ?? null }),
    zoom100: () => viewerRef.value?.zoom100(),
    zoomIn: () => viewerRef.value?.zoomIn(),
    zoomOut: () => viewerRef.value?.zoomOut(),
    fitPage: () => viewerRef.value?.fitPage(),
  },
})
```

Nota: las acciones `goNextReview`, `refreshCurrent` y el método `viewerRef.value.zoom*` pueden no existir. Si faltan, crear stubs mínimos:
- `refreshCurrent`: `() => currentPage.value && store.fetchPage(batchId.value, currentPage.value.id)`
- `goNextReview`: `() => { const i = pages.value.findIndex((p, idx) => idx > selectedIndex.value && p.needs_review); if (i >= 0) selectedIndex.value = i }`
- `viewerRef.value.zoom100()`: expose en `DocumentViewer.vue` mediante `defineExpose({ zoomIn, zoomOut, zoom100, fitPage })` (añadir si no está).

- [ ] **Step 2: Añadir el dialog al template**

Al final del template, antes del cierre:

```vue
  <ShortcutsHelpDialog :is-open="helpDialogOpen" @close="helpDialogOpen = false" />
```

- [ ] **Step 3: Añadir botón "?" al `WorkbenchToolbar.vue`**

Leer `WorkbenchToolbar.vue`. Añadir un botón nuevo junto a los existentes con emit `help`:

```vue
<button type="button" @click="emit('help')" title="Ayuda (?)">?</button>
```

Y en `WorkbenchView.vue` añadir `@help="helpDialogOpen = true"` al `<WorkbenchToolbar>`.

- [ ] **Step 4: Type-check y tests**

Run:
```bash
cd web/frontend && npx vue-tsc --noEmit 2>&1 | tail -10
cd web/frontend && npx vitest run 2>&1 | tail -10
```
Expected: sin errores; ~353 tests passing.

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/views/batches/WorkbenchView.vue web/frontend/src/components/workbench/WorkbenchToolbar.vue
git commit -m "feat(web-frontend): shortcuts integrados + botón de ayuda en toolbar"
```

---

## Task 20: Tests de integración en `WorkbenchView.test.ts`

**Files:**
- Modify: `web/frontend/tests/views/batches/WorkbenchView.test.ts`

- [ ] **Step 1: Añadir 5 tests**

Al final del `describe` principal:

```typescript
  it('on_batch_loaded se dispara en mount', async () => {
    const spy = vi.spyOn(client, 'fireEvent').mockResolvedValue({
      executed: false, result: null, cancel: false, target_page_id: null,
      fields_updated: {}, batch_fields_updated: {}, logs: [], error: null,
    })
    // setup completo del mount (reusar helper existente)
    await mountWorkbench()
    expect(spy).toHaveBeenCalledWith(expect.any(Number), 'on_batch_loaded', {})
  })

  it('on_batch_loaded con cancel navega fuera', async () => {
    vi.spyOn(client, 'fireEvent').mockResolvedValue({
      executed: true, result: null, cancel: true, target_page_id: null,
      fields_updated: {}, batch_fields_updated: {}, logs: [], error: null,
    })
    const router = await mountWorkbench()
    // comprobar que router.push('/batches') se llamó
    expect(router.push).toHaveBeenCalledWith('/batches')
  })

  it('on_page_changed se dispara al cambiar de página', async () => {
    const spy = vi.spyOn(client, 'fireEvent').mockResolvedValue({
      executed: false, result: null, cancel: false, target_page_id: null,
      fields_updated: {}, batch_fields_updated: {}, logs: [], error: null,
    })
    const { wrapper } = await mountWorkbench()
    // seleccionar página 2
    await wrapper.find('[data-test="page-thumbnail-1"]').trigger('click')
    await wrapper.vm.$nextTick()
    const calls = spy.mock.calls.filter((c) => c[1] === 'on_page_changed')
    expect(calls.length).toBeGreaterThan(0)
  })

  it('F5 dispara onRunPipeline', async () => {
    const { wrapper } = await mountWorkbench()
    const runSpy = vi.spyOn(wrapper.vm as any, 'onRunPipeline').mockResolvedValue(undefined)
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'F5', bubbles: true }))
    await wrapper.vm.$nextTick()
    expect(runSpy).toHaveBeenCalled()
  })

  it('? abre el modal de ayuda', async () => {
    const { wrapper } = await mountWorkbench()
    document.dispatchEvent(new KeyboardEvent('keydown', { key: '?', bubbles: true }))
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
  })
```

Nota: `mountWorkbench` es un helper que probablemente exista ya en este archivo. Si su firma no coincide, adaptar. Si el `vi.spyOn(wrapper.vm, 'onRunPipeline')` no funciona por inferencia de `<script setup>`, el test se simplifica a `expect(client.runPipeline).toHaveBeenCalled()` mockeando el cliente HTTP.

- [ ] **Step 2: Ejecutar los tests**

Run:
```bash
cd web/frontend && npx vitest run tests/views/batches/WorkbenchView.test.ts 2>&1 | tail -15
```
Expected: todos PASS.

- [ ] **Step 3: Commit**

```bash
git add web/frontend/tests/views/batches/WorkbenchView.test.ts
git commit -m "test(web-frontend): integración Fase 4 en WorkbenchView"
```

---

## Task 21: Correr suite completa + ruff format

**Files:** ninguno nuevo; solo verificación.

- [ ] **Step 1: Backend**

Run:
```bash
source .venv/bin/activate && DOCSCAN_WEB_DATABASE__URL="sqlite:///test.db" pytest tests/test_web_api.py -q
```
Expected: 186 passed.

- [ ] **Step 2: Frontend**

Run:
```bash
cd web/frontend && npx vitest run --reporter=default 2>&1 | tail -6
```
Expected: ~353 passed.

- [ ] **Step 3: Formato**

Run:
```bash
ruff format web/api/
cd web/frontend && npx prettier --write src/ tests/
```

- [ ] **Step 4: Commit si hay cambios de formato**

```bash
git diff --quiet || { git add -u && git commit -m "chore: format tras Fase 4"; }
```

---

## Task 22: QA visual con Playwright

Seguir el mismo procedimiento que en Fase 3 (ver `docs/progreso_2026-04-24.md`, sección 2).

- [ ] **Step 1: Levantar stack**

Run:
```bash
docker compose up -d db minio redis
source .venv/bin/activate && export DOCSCAN_WEB_DATABASE__URL="postgresql+psycopg://docscan:docscan@localhost:5432/docscan"
alembic upgrade head
setsid nohup uvicorn --factory web.api.main:create_app --host 127.0.0.1 --port 8001 < /dev/null > /tmp/flexipy-qa/backend.log 2>&1 &
cd web/frontend && setsid nohup npm run dev < /dev/null > /tmp/flexipy-qa/frontend.log 2>&1 &
```

- [ ] **Step 2: QA manual vía Playwright**

Login, abrir lote con 3+ páginas y una aplicación que tenga scripts definidos para `on_batch_loaded`, `on_navigate_prev`, `on_page_changed`, `on_key_event`.

Checks:

1. **on_batch_loaded**: script que `log.info("abierto " + batch.id)` — aparece en el Log panel al abrir.
2. **on_batch_loaded con cancel**: script `return False` — toast de error y vuelta a `/batches`.
3. **on_navigate_prev con target_page_id**: script que `return {target_page_id: pages[0].id}` — ir atrás salta a la primera.
4. **on_page_changed actualiza fields**: script que `page.fields['cliente'] = 'Acme ' + str(page.page_index)` — el field aparece en UI tras cambiar.
5. **on_key_event**: script que loguea la tecla — pulsar `Alt+L` y verificar log.
6. **Shortcut R**: rota la página actual.
7. **Shortcut P**: reprocesa el pipeline solo de la página actual (comprobar que pipeline_processed sigue true, fields recalculados).
8. **Shortcut M**: toggle revisión.
9. **Shortcut X**: toggle excluida.
10. **Shortcut Delete**: elimina la página tras confirm.
11. **Shortcut ←/→**: navega.
12. **Shortcut ?**: abre modal; Esc lo cierra.
13. **Con input enfocado**: escribir "rata" en un input no activa ningún shortcut.
14. **Durante pipeline running**: R/M/X/P/Delete son no-op; ←/→ navegan.
15. **Temas claro y oscuro**: modal legible.

- [ ] **Step 3: Fix bugs detectados**

Cada bug → commit propio.

- [ ] **Step 4: Apagar stack**

```bash
pkill -f "uvicorn.*web.api"; pkill -f "vite"; docker compose down
```

---

## Task 23: Actualizar memoria, informe de progreso y push

- [ ] **Step 1: Actualizar MEMORY**

Editar `~/.claude/projects/-media-nicolas-DATA-Tecnomedia-FlexiPy/memory/MEMORY.md`:
- Actualizar la línea de estado para marcar Fase 4 como cerrada.
- Actualizar el conteo de tests: 186 backend + 353 frontend.
- Eliminar de "Pendiente" la línea de Fase 4.
- Añadir follow-up "v0.1.1 desktop: promocionar on_page_changed y on_batch_loaded a EVENT_NAMES".

- [ ] **Step 2: Informe de progreso**

Invocar skill `progreso-doc` para generar `docs/progreso_<fecha>.md`.

- [ ] **Step 3: Push**

```bash
git push origin feature/web
```

---

## Summary

- **23 tasks** secuenciales.
- Paralelizables tras la Task 8: 9+10+11 (composable eventos), 12+13 (composable shortcuts), 14+15 (dialog) y 16 (catálogo) son independientes entre sí.
- **TDD estricto**: tests antes de implementación en Tasks 2→3, 7 (tests→impl), 9→11, 12→13, 14→15.
- **Commits frecuentes**: 23 commits como mínimo + ajustes granulares.
- **Superpowers recomendado**: `subagent-driven-development` para paralelizar.
