# Workbench web Fase 3 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cerrar el Workbench web con edición completa (rotación, barcodes manuales, flags, eliminar, reordenado), overlays de fields con toggles, tab Log funcional y bloqueo de ediciones durante ejecución.

**Architecture:** Backend FastAPI añade 6 endpoints nuevos y extiende `Batch.state` con `"running"`/`"transferring"`, gestionados con `try/finally` en los runners. Frontend Vue 3 añade 4 componentes nuevos, 3 composables y extiende 7 componentes existentes con el contrato `readOnly` cascada. Evento WS `page_updated` coordina clientes múltiples.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2.x, pytest (backend). Vue 3 + TypeScript + Tailwind v4, vitest, `vue-draggable-plus` (nuevo), `vue-virtual-scroller` opcional (frontend).

**Spec:** `docs/superpowers/specs/2026-04-23-workbench-web-fase-3-design.md`

---

## Map of files

### Backend — archivos que cambian
- `web/api/routers/pages.py` — 3 endpoints nuevos (PATCH, rotate, add/delete barcode)
- `web/api/routers/batches.py` — 2 endpoints nuevos (reorder, delete-after) + 409 guard en /run y /transfer
- `web/api/routers/ws.py` — método helper `broadcast_page_updated`
- `web/api/tasks/pipeline_runner.py` — state "running" con try/finally
- `web/api/tasks/transfer_runner.py` — state "transferring" con try/finally
- `web/api/schemas/page.py` — schemas request (PatchPageIn, RotatePageIn, AddBarcodeIn) + response BarcodeResponse ya existe
- `web/api/schemas/batch.py` — schemas request (ReorderBatchIn)
- `tests/test_web_api.py` — nuevas clases `TestPagesPatch`, `TestPagesRotate`, `TestPagesBarcodes`, `TestBatchesReorder`, `TestBatchesDeleteAfter`, `TestRunnersState`, `TestWsPageUpdated`

### Frontend — archivos nuevos
- `web/frontend/src/composables/useOverlayToggles.ts`
- `web/frontend/src/composables/usePageActions.ts`
- `web/frontend/src/composables/useWorkbenchLog.ts`
- `web/frontend/src/components/workbench/LogPanel.vue`
- `web/frontend/src/components/workbench/ThumbnailContextMenu.vue`
- `web/frontend/src/components/workbench/AddBarcodeDialog.vue`
- `web/frontend/src/components/workbench/DeleteBarcodeDialog.vue`
- Tests vitest correspondientes en `web/frontend/tests/`

### Frontend — archivos extendidos
- `web/frontend/src/components/DocumentViewer.vue` — overlays fields + toggles
- `web/frontend/src/components/workbench/ViewerToolbar.vue` — dropdown rotar + 2 toggles
- `web/frontend/src/components/workbench/ThumbnailPanel.vue` — drag-drop + contextmenu
- `web/frontend/src/components/workbench/PageThumbnail.vue` — badges ⊘/⚐
- `web/frontend/src/components/workbench/BarcodePanel.vue` — add/delete + readOnly
- `web/frontend/src/components/workbench/MetadataPanel.vue` — activa tab Log
- `web/frontend/src/views/batches/WorkbenchView.vue` — integración completa

---

## Dependencies

```
Task 1 (Batch.state runners)
  └─> Task 2 (PATCH /pages) ── Task 3 (rotate) ── Task 4 (barcodes) ── Task 5 (delete barcode)
  └─> Task 6 (reorder) ── Task 7 (delete-after)
  └─> Task 8 (409 guards run/transfer)
  └─> Task 9 (WS page_updated)

Task 10 (useOverlayToggles)
Task 11 (DocumentViewer fields overlays)      -- independientes del backend, UI-only
Task 12 (ViewerToolbar rotate + toggles)
Task 13 (usePageActions) ── depende de Tasks 2-7
Task 14 (ThumbnailContextMenu) ── depende de Task 13
Task 15 (PageThumbnail badges)
Task 16 (ThumbnailPanel drag + contextmenu) ── depende de Task 14
Task 17 (AddBarcodeDialog)
Task 18 (DeleteBarcodeDialog)
Task 19 (BarcodePanel edit) ── depende de Tasks 17, 18
Task 20 (useWorkbenchLog)
Task 21 (LogPanel) ── depende de Task 20
Task 22 (MetadataPanel activate Log) ── depende de Task 21
Task 23 (WorkbenchView integration) ── depende de todo lo anterior
Task 24 (QA visual + cleanup)
```

Tasks 2-7 pueden ir en paralelo tras Task 1. Tasks 10-12 / 15 / 17 / 18 / 20 son independientes UI-only y paralelizables. Task 23 es el punto de integración final.

---

## Task 1: `Batch.state` — runners con try/finally

**Objetivo:** Los dos runners marcan el lote como `"running"` / `"transferring"` al empezar, y garantizan estado terminal al salir (`try/finally`).

**Files:**
- Modify: `web/api/tasks/pipeline_runner.py`
- Modify: `web/api/tasks/transfer_runner.py`
- Test: `tests/test_web_api.py` (nueva clase `TestRunnersState`)

- [ ] **Step 1: Escribir tests que fallan**

Añadir al final de `tests/test_web_api.py` (antes de la última línea):

```python
class TestRunnersState:
    """Verifica que los runners gestionan batch.state con try/finally."""

    def test_pipeline_run_marks_running_then_read(self, client, db_session, monkeypatch):
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        batch_id, _ = _create_batch_with_page(client, headers, app_id)

        # Antes de /run, state == "created"
        r = client.get(f"/api/batches/{batch_id}", headers=headers)
        assert r.json()["state"] == "created"

        # Capturar estado durante ejecución mediante hook
        states_during = []

        import web.api.tasks.pipeline_runner as runner_mod
        orig = runner_mod.run_pipeline_for_batch

        def spy(batch_id: int, storage):
            from app.db.database import get_session_factory
            Session = get_session_factory()
            with Session() as s:
                from app.models.batch import Batch
                b = s.query(Batch).filter_by(id=batch_id).first()
                states_during.append(b.state)
            return orig(batch_id=batch_id, storage=storage)

        monkeypatch.setattr(runner_mod, "run_pipeline_for_batch", spy)

        r = client.post(f"/api/batches/{batch_id}/run", headers=headers)
        assert r.status_code == 202

        # Tras run (síncrono en tests): "read" o "error_read"
        r = client.get(f"/api/batches/{batch_id}", headers=headers)
        assert r.json()["state"] in ("read", "error_read")

    def test_pipeline_run_error_goes_to_error_read(
        self, client, db_session, monkeypatch,
    ):
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        batch_id, _ = _create_batch_with_page(client, headers, app_id)

        # Forzar excepción dentro del runner
        import web.api.tasks.pipeline_runner as runner_mod

        def boom(*args, **kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr(runner_mod, "_execute_pipeline", boom)

        r = client.post(f"/api/batches/{batch_id}/run", headers=headers)
        # Status 202 porque FastAPI ya aceptó, pero background falla
        assert r.status_code == 202

        r = client.get(f"/api/batches/{batch_id}", headers=headers)
        assert r.json()["state"] == "error_read"
```

- [ ] **Step 2: Ejecutar tests → fallan**

Run: `pytest tests/test_web_api.py::TestRunnersState -v`
Expected: FAIL (state sigue en "created" o AttributeError `_execute_pipeline`)

- [ ] **Step 3: Refactor `pipeline_runner.py`**

Extraer el cuerpo actual del runner a una función privada `_execute_pipeline(batch_id, storage, db)`. En la función pública `run_pipeline_for_batch`:

```python
def run_pipeline_for_batch(batch_id: int, storage) -> None:
    """Ejecuta el pipeline del lote con gestión de estado."""
    from app.db.database import get_session_factory

    Session = get_session_factory()
    with Session() as db:
        batch = db.query(Batch).filter_by(id=batch_id).first()
        if batch is None:
            log.warning("Batch %s no existe, abortando run", batch_id)
            return

        batch.state = "running"
        db.commit()

        try:
            _execute_pipeline(batch_id=batch_id, storage=storage, db=db)
        except Exception:
            log.exception("Pipeline falló para batch %s", batch_id)
            db.rollback()
            batch = db.query(Batch).filter_by(id=batch_id).first()
            if batch:
                batch.state = "error_read"
                db.commit()
            raise
        finally:
            # Garantía de estado terminal
            db.rollback()
            batch = db.query(Batch).filter_by(id=batch_id).first()
            if batch and batch.state == "running":
                batch.state = "error_read"
                db.commit()
```

Mover todo el cuerpo actual a `_execute_pipeline` y que su última línea sea `batch.state = "read" if not any_error else "error_read"; db.commit()`.

- [ ] **Step 4: Aplicar el mismo patrón a `transfer_runner.py`**

Mismo patrón con valor `"transferring"` en vez de `"running"`.

- [ ] **Step 5: Ejecutar tests → pasan**

Run: `pytest tests/test_web_api.py::TestRunnersState -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add web/api/tasks/pipeline_runner.py web/api/tasks/transfer_runner.py tests/test_web_api.py
git commit -m "feat(web-api): batch.state running/transferring con try/finally en runners"
```

---

## Task 2: `PATCH /api/pages/{page_id}`

**Objetivo:** Toggle flags (`is_excluded`, `needs_review`, `review_reason`).

**Files:**
- Modify: `web/api/schemas/page.py`
- Modify: `web/api/routers/pages.py`
- Test: `tests/test_web_api.py` (nueva clase `TestPagesPatch`)

- [ ] **Step 1: Añadir schema request**

En `web/api/schemas/page.py`:

```python
class PagePatchIn(BaseModel):
    """Patch parcial de flags de página."""

    is_excluded: bool | None = None
    needs_review: bool | None = None
    review_reason: str | None = None
```

- [ ] **Step 2: Escribir tests que fallan**

```python
class TestPagesPatch:
    def test_toggle_is_excluded(self, client):
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        batch_id, page_id = _create_batch_with_page(client, headers, app_id)

        r = client.patch(
            f"/api/pages/{page_id}",
            json={"is_excluded": True},
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["is_excluded"] is True

    def test_toggle_needs_review_with_reason(self, client):
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        _, page_id = _create_batch_with_page(client, headers, app_id)

        r = client.patch(
            f"/api/pages/{page_id}",
            json={"needs_review": True, "review_reason": "check manually"},
            headers=headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["needs_review"] is True
        assert body["review_reason"] == "check manually"

    def test_patch_other_tenant_404(self, client, db_session):
        headers_a = _auth_header(client, email="a@a.com")
        app_id = _create_app_with_pipeline(client, headers_a, "[]")
        _, page_id = _create_batch_with_page(client, headers_a, app_id)

        headers_b = _auth_header(client, email="b@b.com")
        r = client.patch(
            f"/api/pages/{page_id}",
            json={"is_excluded": True},
            headers=headers_b,
        )
        assert r.status_code == 404

    def test_patch_409_when_running(self, client, db_session):
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        batch_id, page_id = _create_batch_with_page(client, headers, app_id)

        # Forzar estado running
        from app.models.batch import Batch
        batch = db_session.query(Batch).filter_by(id=batch_id).first()
        batch.state = "running"
        db_session.commit()

        r = client.patch(
            f"/api/pages/{page_id}",
            json={"is_excluded": True},
            headers=headers,
        )
        assert r.status_code == 409
```

- [ ] **Step 3: Ejecutar tests → fallan**

Run: `pytest tests/test_web_api.py::TestPagesPatch -v`
Expected: FAIL (endpoint no existe)

- [ ] **Step 4: Implementar endpoint**

En `web/api/routers/pages.py`, añadir:

```python
@router.patch("/{page_id}", response_model=PageResponse)
def patch_page(
    page_id: int,
    payload: PagePatchIn,
    user: CurrentUser,
    db: SessionDep,
):
    """Actualiza flags de una página (is_excluded, needs_review, review_reason)."""
    page = _get_page_for_user(page_id, user, db)  # 404 si no es del tenant
    batch = page.batch
    if batch.state in ("running", "transferring"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se pueden editar páginas mientras el lote está en ejecución",
        )

    if payload.is_excluded is not None:
        page.is_excluded = payload.is_excluded
    if payload.needs_review is not None:
        page.needs_review = payload.needs_review
    if payload.review_reason is not None:
        page.review_reason = payload.review_reason

    db.commit()
    db.refresh(page)
    return page
```

Añadir el helper `_get_page_for_user` si no existe (o adaptar el existente `_get_page_in_batch_or_404`).

- [ ] **Step 5: Ejecutar tests → pasan**

Run: `pytest tests/test_web_api.py::TestPagesPatch -v`
Expected: PASS (4/4)

- [ ] **Step 6: Commit**

```bash
git add web/api/schemas/page.py web/api/routers/pages.py tests/test_web_api.py
git commit -m "feat(web-api): PATCH /pages/:id para toggle de flags"
```

---

## Task 3: `POST /api/pages/{page_id}/rotate`

**Objetivo:** Rotación destructiva 90°/180°/270° CW con ajuste de coords de barcodes.

**Files:**
- Modify: `web/api/schemas/page.py`
- Modify: `web/api/routers/pages.py`
- Test: `tests/test_web_api.py` (clase `TestPagesRotate`)

- [ ] **Step 1: Añadir schema**

```python
class RotatePageIn(BaseModel):
    """Número de rotaciones 90° CW a aplicar."""

    turns: int = 1
```

- [ ] **Step 2: Escribir tests que fallan**

```python
class TestPagesRotate:
    def test_rotate_90_swaps_dimensions(self, client, storage_dir):
        import cv2
        import numpy as np
        from pathlib import Path

        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        _, page_id = _create_batch_with_page(client, headers, app_id)

        # Verificar dimensiones antes
        r = client.get(f"/api/pages/{page_id}", headers=headers)
        image_path_before = r.json()["image_path"]
        img_before = cv2.imread(str(Path(storage_dir) / image_path_before))
        h_before, w_before = img_before.shape[:2]

        r = client.post(
            f"/api/pages/{page_id}/rotate",
            json={"turns": 1},
            headers=headers,
        )
        assert r.status_code == 200

        img_after = cv2.imread(str(Path(storage_dir) / image_path_before))
        h_after, w_after = img_after.shape[:2]
        assert h_after == w_before
        assert w_after == h_before

    def test_rotate_180_preserves_dimensions(self, client, storage_dir):
        import cv2
        from pathlib import Path

        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        _, page_id = _create_batch_with_page(client, headers, app_id)

        r = client.get(f"/api/pages/{page_id}", headers=headers)
        image_path = r.json()["image_path"]
        img_before = cv2.imread(str(Path(storage_dir) / image_path))
        h_before, w_before = img_before.shape[:2]

        r = client.post(
            f"/api/pages/{page_id}/rotate",
            json={"turns": 2},
            headers=headers,
        )
        assert r.status_code == 200

        img_after = cv2.imread(str(Path(storage_dir) / image_path))
        assert img_after.shape[:2] == (h_before, w_before)

    def test_rotate_adjusts_barcode_coords(self, client, db_session):
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        _, page_id = _create_batch_with_page(client, headers, app_id)

        # Inyectar barcode con coords conocidas (img ~200x100)
        from app.models.barcode import Barcode
        from app.models.page import Page
        page = db_session.query(Page).filter_by(id=page_id).first()
        h, w = 100, 200  # asume _make_png_bytes crea 4x4, ajustar tras leer real
        # Leer dimensiones reales
        import cv2
        from pathlib import Path
        img = cv2.imread(page.image_path)
        h, w = img.shape[:2]

        bc = Barcode(
            page_id=page_id, value="TEST", symbology="CODE128",
            engine="test", step_id="s1", pos_x=10, pos_y=20,
            pos_w=30, pos_h=5,
        )
        db_session.add(bc)
        db_session.commit()
        bc_id = bc.id

        r = client.post(
            f"/api/pages/{page_id}/rotate",
            json={"turns": 1},
            headers=headers,
        )
        assert r.status_code == 200

        db_session.refresh(bc)
        # 90° CW: new_x = h - old_y - old_h, new_y = old_x, new_w = old_h, new_h = old_w
        assert bc.pos_x == h - 20 - 5
        assert bc.pos_y == 10
        assert bc.pos_w == 5
        assert bc.pos_h == 30

    def test_rotate_409_when_running(self, client, db_session):
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        batch_id, page_id = _create_batch_with_page(client, headers, app_id)

        from app.models.batch import Batch
        batch = db_session.query(Batch).filter_by(id=batch_id).first()
        batch.state = "running"
        db_session.commit()

        r = client.post(
            f"/api/pages/{page_id}/rotate",
            json={"turns": 1},
            headers=headers,
        )
        assert r.status_code == 409
```

- [ ] **Step 3: Ejecutar tests → fallan**

Run: `pytest tests/test_web_api.py::TestPagesRotate -v`
Expected: FAIL

- [ ] **Step 4: Implementar endpoint**

En `web/api/routers/pages.py`:

```python
import cv2

@router.post("/{page_id}/rotate", response_model=PageResponse)
def rotate_page(
    page_id: int,
    payload: RotatePageIn,
    user: CurrentUser,
    db: SessionDep,
):
    """Rota la imagen N×90° CW (destructivo) y actualiza coords de barcodes."""
    page = _get_page_for_user(page_id, user, db)
    if page.batch.state in ("running", "transferring"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede rotar mientras el lote está en ejecución",
        )
    if payload.turns not in (1, 2, 3):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="turns debe ser 1, 2 o 3",
        )

    img = cv2.imread(page.image_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise HTTPException(500, "No se pudo leer la imagen")
    h, w = img.shape[:2]

    for _ in range(payload.turns):
        img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)

    cv2.imwrite(page.image_path, img)

    # Ajustar coords de barcodes N veces
    cur_h, cur_w = h, w
    for _ in range(payload.turns):
        for bc in page.barcodes:
            old_x, old_y, old_w, old_h = bc.pos_x, bc.pos_y, bc.pos_w, bc.pos_h
            bc.pos_x = cur_h - old_y - old_h
            bc.pos_y = old_x
            bc.pos_w = old_h
            bc.pos_h = old_w
        cur_h, cur_w = cur_w, cur_h

    db.commit()
    db.refresh(page)
    return page
```

- [ ] **Step 5: Ejecutar tests → pasan**

Run: `pytest tests/test_web_api.py::TestPagesRotate -v`
Expected: PASS (4/4)

- [ ] **Step 6: Commit**

```bash
git add web/api/schemas/page.py web/api/routers/pages.py tests/test_web_api.py
git commit -m "feat(web-api): POST /pages/:id/rotate con ajuste de coords de barcodes"
```

---

## Task 4: `POST /api/pages/{page_id}/barcodes` — añadir manual

**Files:**
- Modify: `web/api/schemas/page.py`
- Modify: `web/api/routers/pages.py`
- Test: `tests/test_web_api.py` (clase `TestPagesBarcodes`)

- [ ] **Step 1: Schema**

```python
class AddBarcodeIn(BaseModel):
    value: str
    symbology: str = "MANUAL"
```

- [ ] **Step 2: Tests que fallan**

```python
class TestPagesBarcodes:
    def test_add_manual_barcode(self, client):
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        _, page_id = _create_batch_with_page(client, headers, app_id)

        r = client.post(
            f"/api/pages/{page_id}/barcodes",
            json={"value": "ABC123", "symbology": "MANUAL"},
            headers=headers,
        )
        assert r.status_code == 201
        bc = r.json()
        assert bc["value"] == "ABC123"
        assert bc["symbology"] == "MANUAL"
        assert bc["engine"] == "manual"
        assert bc["pos_x"] == 0 and bc["pos_y"] == 0

    def test_add_barcode_empty_value_422(self, client):
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        _, page_id = _create_batch_with_page(client, headers, app_id)

        r = client.post(
            f"/api/pages/{page_id}/barcodes",
            json={"value": "", "symbology": "MANUAL"},
            headers=headers,
        )
        assert r.status_code == 422

    def test_add_barcode_409_when_running(self, client, db_session):
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        batch_id, page_id = _create_batch_with_page(client, headers, app_id)

        from app.models.batch import Batch
        batch = db_session.query(Batch).filter_by(id=batch_id).first()
        batch.state = "running"
        db_session.commit()

        r = client.post(
            f"/api/pages/{page_id}/barcodes",
            json={"value": "X", "symbology": "MANUAL"},
            headers=headers,
        )
        assert r.status_code == 409

    def test_add_barcode_other_tenant_404(self, client):
        headers_a = _auth_header(client, email="a@a.com")
        app_id = _create_app_with_pipeline(client, headers_a, "[]")
        _, page_id = _create_batch_with_page(client, headers_a, app_id)

        headers_b = _auth_header(client, email="b@b.com")
        r = client.post(
            f"/api/pages/{page_id}/barcodes",
            json={"value": "X", "symbology": "MANUAL"},
            headers=headers_b,
        )
        assert r.status_code == 404
```

- [ ] **Step 3: Tests fallan**

Run: `pytest tests/test_web_api.py::TestPagesBarcodes -v`
Expected: FAIL

- [ ] **Step 4: Implementar**

```python
from app.models.barcode import Barcode

@router.post(
    "/{page_id}/barcodes",
    response_model=BarcodeResponse,
    status_code=201,
)
def add_manual_barcode(
    page_id: int,
    payload: AddBarcodeIn,
    user: CurrentUser,
    db: SessionDep,
):
    """Añade un barcode manual a la página."""
    page = _get_page_for_user(page_id, user, db)
    if page.batch.state in ("running", "transferring"):
        raise HTTPException(409, "Lote en ejecución")
    if not payload.value.strip():
        raise HTTPException(422, "value no puede estar vacío")

    bc = Barcode(
        page_id=page.id,
        value=payload.value,
        symbology=payload.symbology or "MANUAL",
        engine="manual",
        step_id="manual",
        quality=0.0,
        pos_x=0, pos_y=0, pos_w=0, pos_h=0,
        role="",
    )
    db.add(bc)
    db.commit()
    db.refresh(bc)
    return bc
```

- [ ] **Step 5: Tests pasan**

Run: `pytest tests/test_web_api.py::TestPagesBarcodes -v`
Expected: PASS (4/4)

- [ ] **Step 6: Commit**

```bash
git add web/api/schemas/page.py web/api/routers/pages.py tests/test_web_api.py
git commit -m "feat(web-api): POST /pages/:id/barcodes para añadir barcode manual"
```

---

## Task 5: `DELETE /api/pages/{page_id}/barcodes/{barcode_id}`

**Files:**
- Modify: `web/api/routers/pages.py`
- Test: `tests/test_web_api.py` (extender `TestPagesBarcodes`)

- [ ] **Step 1: Tests que fallan**

Añadir a la clase `TestPagesBarcodes`:

```python
    def test_delete_barcode(self, client, db_session):
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        _, page_id = _create_batch_with_page(client, headers, app_id)

        r = client.post(
            f"/api/pages/{page_id}/barcodes",
            json={"value": "X", "symbology": "MANUAL"},
            headers=headers,
        )
        bc_id = r.json()["id"]

        r = client.delete(
            f"/api/pages/{page_id}/barcodes/{bc_id}",
            headers=headers,
        )
        assert r.status_code == 204

        # Verificar ya no existe
        from app.models.barcode import Barcode
        assert db_session.query(Barcode).filter_by(id=bc_id).first() is None

    def test_delete_barcode_from_wrong_page_404(self, client, db_session):
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        _, page_id_a = _create_batch_with_page(client, headers, app_id)
        _, page_id_b = _create_batch_with_page(client, headers, app_id)

        r = client.post(
            f"/api/pages/{page_id_a}/barcodes",
            json={"value": "X", "symbology": "MANUAL"},
            headers=headers,
        )
        bc_id = r.json()["id"]

        # Intentar borrar desde página distinta
        r = client.delete(
            f"/api/pages/{page_id_b}/barcodes/{bc_id}",
            headers=headers,
        )
        assert r.status_code == 404

    def test_delete_barcode_409_when_running(self, client, db_session):
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        batch_id, page_id = _create_batch_with_page(client, headers, app_id)

        r = client.post(
            f"/api/pages/{page_id}/barcodes",
            json={"value": "X", "symbology": "MANUAL"},
            headers=headers,
        )
        bc_id = r.json()["id"]

        from app.models.batch import Batch
        batch = db_session.query(Batch).filter_by(id=batch_id).first()
        batch.state = "running"
        db_session.commit()

        r = client.delete(
            f"/api/pages/{page_id}/barcodes/{bc_id}",
            headers=headers,
        )
        assert r.status_code == 409
```

- [ ] **Step 2: Run → fallan**

Run: `pytest tests/test_web_api.py::TestPagesBarcodes::test_delete_barcode -v`
Expected: FAIL

- [ ] **Step 3: Implementar endpoint**

En `web/api/routers/pages.py`:

```python
from fastapi import Response

@router.delete("/{page_id}/barcodes/{barcode_id}", status_code=204)
def delete_barcode(
    page_id: int,
    barcode_id: int,
    user: CurrentUser,
    db: SessionDep,
):
    """Elimina un barcode de la página."""
    page = _get_page_for_user(page_id, user, db)
    if page.batch.state in ("running", "transferring"):
        raise HTTPException(409, "Lote en ejecución")

    bc = next((b for b in page.barcodes if b.id == barcode_id), None)
    if bc is None:
        raise HTTPException(404, "Barcode no encontrado en esta página")

    db.delete(bc)
    db.commit()
    return Response(status_code=204)
```

- [ ] **Step 4: Tests pasan**

Run: `pytest tests/test_web_api.py::TestPagesBarcodes -v`
Expected: PASS (7/7)

- [ ] **Step 5: Commit**

```bash
git add web/api/routers/pages.py tests/test_web_api.py
git commit -m "feat(web-api): DELETE /pages/:id/barcodes/:bid"
```

---

## Task 6: `POST /api/batches/{batch_id}/reorder`

**Files:**
- Create/Modify: `web/api/schemas/batch.py`
- Modify: `web/api/routers/batches.py`
- Test: `tests/test_web_api.py` (clase `TestBatchesReorder`)

- [ ] **Step 1: Schema**

Añadir en `web/api/schemas/batch.py`:

```python
class ReorderBatchIn(BaseModel):
    page_ids: list[int]
```

- [ ] **Step 2: Tests que fallan**

```python
class TestBatchesReorder:
    def _make_batch_with_n_pages(self, client, headers, n=3):
        app_id = _create_app_with_pipeline(client, headers, "[]")
        batch_id, page_id1 = _create_batch_with_page(client, headers, app_id)
        page_ids = [page_id1]
        for _ in range(n - 1):
            files = [("files", ("p.png", _make_png_bytes(), "image/png"))]
            r = client.post(
                f"/api/batches/{batch_id}/pages/upload",
                files=files, headers=headers,
            )
            page_ids.extend(p["id"] for p in r.json()["created"])
        return batch_id, page_ids

    def test_reorder_changes_indices(self, client):
        headers = _auth_header(client)
        batch_id, ids = self._make_batch_with_n_pages(client, headers, 3)

        reversed_ids = list(reversed(ids))
        r = client.post(
            f"/api/batches/{batch_id}/reorder",
            json={"page_ids": reversed_ids},
            headers=headers,
        )
        assert r.status_code == 200

        r = client.get(f"/api/batches/{batch_id}/pages", headers=headers)
        pages = r.json()["items"] if "items" in r.json() else r.json()
        assert [p["id"] for p in pages] == reversed_ids
        assert [p["page_index"] for p in pages] == [0, 1, 2]

    def test_reorder_422_if_set_mismatch(self, client):
        headers = _auth_header(client)
        batch_id, ids = self._make_batch_with_n_pages(client, headers, 2)

        r = client.post(
            f"/api/batches/{batch_id}/reorder",
            json={"page_ids": [ids[0], 9999]},
            headers=headers,
        )
        assert r.status_code == 422

    def test_reorder_409_when_running(self, client, db_session):
        headers = _auth_header(client)
        batch_id, ids = self._make_batch_with_n_pages(client, headers, 2)

        from app.models.batch import Batch
        batch = db_session.query(Batch).filter_by(id=batch_id).first()
        batch.state = "running"
        db_session.commit()

        r = client.post(
            f"/api/batches/{batch_id}/reorder",
            json={"page_ids": list(reversed(ids))},
            headers=headers,
        )
        assert r.status_code == 409
```

- [ ] **Step 3: Tests fallan**

Run: `pytest tests/test_web_api.py::TestBatchesReorder -v`
Expected: FAIL

- [ ] **Step 4: Implementar**

En `web/api/routers/batches.py`:

```python
from app.models.page import Page
from web.api.schemas.batch import ReorderBatchIn

@router.post("/{batch_id}/reorder", response_model=BatchResponse)
def reorder_batch(
    batch_id: int,
    payload: ReorderBatchIn,
    user: CurrentUser,
    db: SessionDep,
):
    """Reordena las páginas del lote aplicando page_index = posición en la lista."""
    batch = get_batch_for_tenant(batch_id, user.tenant_id, db)
    if batch.state in ("running", "transferring"):
        raise HTTPException(409, "Lote en ejecución")

    pages = db.query(Page).filter_by(batch_id=batch_id).all()
    existing = {p.id for p in pages}
    requested = set(payload.page_ids)
    if existing != requested or len(payload.page_ids) != len(existing):
        raise HTTPException(
            status_code=422,
            detail="page_ids no coincide con el set actual de páginas del lote",
        )

    id_to_page = {p.id: p for p in pages}
    for idx, pid in enumerate(payload.page_ids):
        id_to_page[pid].page_index = idx
    db.commit()
    db.refresh(batch)
    return batch
```

- [ ] **Step 5: Tests pasan**

Run: `pytest tests/test_web_api.py::TestBatchesReorder -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add web/api/schemas/batch.py web/api/routers/batches.py tests/test_web_api.py
git commit -m "feat(web-api): POST /batches/:id/reorder"
```

---

## Task 7: `DELETE /api/batches/{batch_id}/pages/after/{page_id}`

**Objetivo:** Eliminar página actual + todas las siguientes.

**Files:**
- Modify: `web/api/routers/batches.py`
- Test: `tests/test_web_api.py` (clase `TestBatchesDeleteAfter`)

- [ ] **Step 1: Tests que fallan**

```python
class TestBatchesDeleteAfter:
    def _make_batch_with_n_pages(self, client, headers, n=5):
        app_id = _create_app_with_pipeline(client, headers, "[]")
        batch_id, page_id1 = _create_batch_with_page(client, headers, app_id)
        page_ids = [page_id1]
        for _ in range(n - 1):
            files = [("files", ("p.png", _make_png_bytes(), "image/png"))]
            r = client.post(
                f"/api/batches/{batch_id}/pages/upload",
                files=files, headers=headers,
            )
            page_ids.extend(p["id"] for p in r.json()["created"])
        return batch_id, page_ids

    def test_delete_from_middle(self, client):
        headers = _auth_header(client)
        batch_id, ids = self._make_batch_with_n_pages(client, headers, 5)

        # Eliminar desde la posición 2 (índice 2 = tercera página), se borran 3
        r = client.delete(
            f"/api/batches/{batch_id}/pages/after/{ids[2]}",
            headers=headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["deleted"] == 3
        assert body["batch_page_count"] == 2

    def test_delete_after_page_not_in_batch_404(self, client):
        headers = _auth_header(client)
        batch_id, _ = self._make_batch_with_n_pages(client, headers, 2)

        r = client.delete(
            f"/api/batches/{batch_id}/pages/after/9999",
            headers=headers,
        )
        assert r.status_code == 404

    def test_delete_after_409_when_running(self, client, db_session):
        headers = _auth_header(client)
        batch_id, ids = self._make_batch_with_n_pages(client, headers, 3)

        from app.models.batch import Batch
        batch = db_session.query(Batch).filter_by(id=batch_id).first()
        batch.state = "running"
        db_session.commit()

        r = client.delete(
            f"/api/batches/{batch_id}/pages/after/{ids[1]}",
            headers=headers,
        )
        assert r.status_code == 409
```

- [ ] **Step 2: Tests fallan**

Run: `pytest tests/test_web_api.py::TestBatchesDeleteAfter -v`
Expected: FAIL

- [ ] **Step 3: Implementar**

```python
@router.delete("/{batch_id}/pages/after/{page_id}")
def delete_pages_from(
    batch_id: int,
    page_id: int,
    user: CurrentUser,
    db: SessionDep,
    storage: StorageDep,
):
    """Elimina page_id y todas las páginas con page_index >= page_id.page_index."""
    batch = get_batch_for_tenant(batch_id, user.tenant_id, db)
    if batch.state in ("running", "transferring"):
        raise HTTPException(409, "Lote en ejecución")

    anchor = db.query(Page).filter_by(id=page_id, batch_id=batch_id).first()
    if anchor is None:
        raise HTTPException(404, "Página no encontrada en este lote")

    to_delete = (
        db.query(Page)
        .filter(Page.batch_id == batch_id, Page.page_index >= anchor.page_index)
        .all()
    )
    deleted_count = len(to_delete)
    for p in to_delete:
        # Borrar imagen de storage (best effort)
        try:
            storage.delete(p.image_path)
        except Exception:
            log.warning("No se pudo borrar %s", p.image_path)
        db.delete(p)

    db.flush()
    batch.page_count = db.query(Page).filter_by(batch_id=batch_id).count()
    db.commit()

    return {"deleted": deleted_count, "batch_page_count": batch.page_count}
```

- [ ] **Step 4: Tests pasan**

Run: `pytest tests/test_web_api.py::TestBatchesDeleteAfter -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/api/routers/batches.py tests/test_web_api.py
git commit -m "feat(web-api): DELETE /batches/:id/pages/after/:page_id (eliminar desde aquí)"
```

---

## Task 8: 409 guards en `POST /batches/:id/run` y `/transfer`

**Objetivo:** Rechazar relanzamiento concurrente cuando el lote ya está en `running`/`transferring`.

**Files:**
- Modify: `web/api/routers/batches.py`
- Test: `tests/test_web_api.py` (extender `TestPipelineRun` y `TestTransferEndpoint`)

- [ ] **Step 1: Tests que fallan**

Añadir:

```python
    def test_run_409_when_already_running(self, client, db_session):
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        batch_id, _ = _create_batch_with_page(client, headers, app_id)

        from app.models.batch import Batch
        batch = db_session.query(Batch).filter_by(id=batch_id).first()
        batch.state = "running"
        db_session.commit()

        r = client.post(f"/api/batches/{batch_id}/run", headers=headers)
        assert r.status_code == 409

    def test_transfer_409_when_already_transferring(self, client, db_session):
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        batch_id, _ = _create_batch_with_page(client, headers, app_id)

        from app.models.batch import Batch
        batch = db_session.query(Batch).filter_by(id=batch_id).first()
        batch.state = "transferring"
        db_session.commit()

        r = client.post(f"/api/batches/{batch_id}/transfer", headers=headers)
        assert r.status_code == 409
```

En la clase `TestPipelineRun` y `TestTransferEndpoint` respectivamente.

- [ ] **Step 2: Tests fallan**

Run: `pytest tests/test_web_api.py::TestPipelineRun::test_run_409_when_already_running tests/test_web_api.py::TestTransferEndpoint::test_transfer_409_when_already_transferring -v`

- [ ] **Step 3: Añadir guards**

En `run_batch_pipeline`:
```python
    if batch.state in ("running", "transferring"):
        raise HTTPException(409, "Lote en ejecución")
```

En `transfer_batch` reemplazar el check actual `if batch.state != "read"` manteniendo el 409 pero permitiendo adicionalmente rechazar desde "running":
```python
    if batch.state in ("running", "transferring"):
        raise HTTPException(409, "Lote en ejecución")
    if batch.state != "read":
        raise HTTPException(409, "El lote no está listo para transferir")
```

- [ ] **Step 4: Tests pasan**

Run: `pytest tests/test_web_api.py -k "409_when_already" -v`

- [ ] **Step 5: Commit**

```bash
git add web/api/routers/batches.py tests/test_web_api.py
git commit -m "feat(web-api): 409 guards en /run y /transfer cuando lote en ejecución"
```

---

## Task 9: Evento WS `page_updated`

**Objetivo:** Emitir evento por cada mutación de página en los endpoints de Tasks 2-7.

**Files:**
- Modify: `web/api/routers/ws.py` (o el módulo que gestiona broadcasters)
- Modify: `web/api/routers/pages.py` y `batches.py` (llamadas emit)
- Test: `tests/test_web_api.py` (clase `TestWsPageUpdated`)

- [ ] **Step 1: Investigar canal WS actual**

Leer `web/api/routers/ws.py` para entender cómo se emiten eventos. Buscar función tipo `broadcast_to_batch(batch_id, event_dict)` o gestor de conexiones. Si no existe helper, extraer de los runners.

- [ ] **Step 2: Añadir helper `broadcast_page_updated`**

```python
async def broadcast_page_updated(
    batch_id: int,
    page_id: int,
    action: str,
    extra: dict | None = None,
) -> None:
    payload = {
        "type": "page_updated",
        "page_id": page_id,
        "action": action,
    }
    if extra:
        payload.update(extra)
    await broadcast_to_batch(batch_id, payload)
```

Si el canal es síncrono desde FastAPI endpoints, exponer una versión sync (`asyncio.run_coroutine_threadsafe` o la abstracción existente).

- [ ] **Step 3: Test que falla**

```python
class TestWsPageUpdated:
    def test_patch_page_emits_event(self, client):
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        batch_id, page_id = _create_batch_with_page(client, headers, app_id)

        with client.websocket_connect(f"/ws/batches/{batch_id}") as ws:
            client.patch(
                f"/api/pages/{page_id}",
                json={"is_excluded": True},
                headers=headers,
            )
            ev = ws.receive_json()
            assert ev["type"] == "page_updated"
            assert ev["page_id"] == page_id
            assert ev["action"] == "flags"

    def test_rotate_emits_event(self, client):
        headers = _auth_header(client)
        app_id = _create_app_with_pipeline(client, headers, "[]")
        batch_id, page_id = _create_batch_with_page(client, headers, app_id)

        with client.websocket_connect(f"/ws/batches/{batch_id}") as ws:
            client.post(
                f"/api/pages/{page_id}/rotate",
                json={"turns": 1},
                headers=headers,
            )
            ev = ws.receive_json()
            assert ev["type"] == "page_updated"
            assert ev["action"] == "rotated"
```

Run: `pytest tests/test_web_api.py::TestWsPageUpdated -v`
Expected: FAIL

- [ ] **Step 4: Llamar al broadcaster en cada endpoint**

- `patch_page`: al final, `broadcast_page_updated(page.batch_id, page.id, "flags")`
- `rotate_page`: `broadcast_page_updated(page.batch_id, page.id, "rotated")`
- `add_manual_barcode`: `broadcast_page_updated(page.batch_id, page.id, "barcode_added", {"barcode_id": bc.id})`
- `delete_barcode`: `broadcast_page_updated(page.batch_id, page.id, "barcode_deleted", {"barcode_id": barcode_id})`
- `delete_page` (endpoint existente de Fase 2): añadir `broadcast_page_updated(page.batch_id, page.id, "deleted")`
- `reorder_batch`: `broadcast_page_updated(batch_id, 0, "reordered", {"new_order": payload.page_ids})`
- `delete_pages_from`: emitir `"deleted"` por cada id borrado o uno agregado con lista.

- [ ] **Step 5: Tests pasan**

Run: `pytest tests/test_web_api.py::TestWsPageUpdated -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add web/api/routers/ws.py web/api/routers/pages.py web/api/routers/batches.py tests/test_web_api.py
git commit -m "feat(web-api): evento WS page_updated en mutaciones de página"
```

---

## Task 10: Composable `useOverlayToggles`

**Objetivo:** Persistir `{showBarcodes, showFields}` en localStorage.

**Files:**
- Create: `web/frontend/src/composables/useOverlayToggles.ts`
- Test: `web/frontend/tests/composables/useOverlayToggles.test.ts`

- [ ] **Step 1: Test que falla**

```ts
import { describe, it, expect, beforeEach } from 'vitest'
import { useOverlayToggles } from '@/composables/useOverlayToggles'

describe('useOverlayToggles', () => {
  beforeEach(() => { localStorage.clear() })

  it('defaults: both true', () => {
    const t = useOverlayToggles()
    expect(t.showBarcodes.value).toBe(true)
    expect(t.showFields.value).toBe(true)
  })

  it('persists to localStorage', () => {
    const t = useOverlayToggles()
    t.showBarcodes.value = false
    expect(JSON.parse(localStorage.getItem('workbench.overlays')!).barcodes).toBe(false)
  })

  it('loads from localStorage on init', () => {
    localStorage.setItem('workbench.overlays', JSON.stringify({ barcodes: false, fields: true }))
    const t = useOverlayToggles()
    expect(t.showBarcodes.value).toBe(false)
    expect(t.showFields.value).toBe(true)
  })
})
```

Run: `cd web/frontend && npx vitest run tests/composables/useOverlayToggles.test.ts`
Expected: FAIL (file not found)

- [ ] **Step 2: Implementar**

`web/frontend/src/composables/useOverlayToggles.ts`:

```ts
import { ref, watch } from 'vue'

const STORAGE_KEY = 'workbench.overlays'

interface StoredToggles { barcodes: boolean; fields: boolean }

const readStored = (): StoredToggles => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { barcodes: true, fields: true }
    const parsed = JSON.parse(raw)
    return {
      barcodes: typeof parsed.barcodes === 'boolean' ? parsed.barcodes : true,
      fields: typeof parsed.fields === 'boolean' ? parsed.fields : true,
    }
  } catch {
    return { barcodes: true, fields: true }
  }
}

export function useOverlayToggles() {
  const stored = readStored()
  const showBarcodes = ref(stored.barcodes)
  const showFields = ref(stored.fields)

  watch([showBarcodes, showFields], ([b, f]) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ barcodes: b, fields: f }))
  })

  return { showBarcodes, showFields }
}
```

- [ ] **Step 3: Tests pasan**

Run: `cd web/frontend && npx vitest run tests/composables/useOverlayToggles.test.ts`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add web/frontend/src/composables/useOverlayToggles.ts web/frontend/tests/composables/useOverlayToggles.test.ts
git commit -m "feat(web-frontend): composable useOverlayToggles con persistencia"
```

---

## Task 11: DocumentViewer con overlays de fields + toggles

**Objetivo:** Extender `DocumentViewer.vue` para pintar overlays de fields con `{x,y,w,h,value}` y aceptar props `showBarcodes`/`showFields`.

**Files:**
- Modify: `web/frontend/src/components/DocumentViewer.vue`
- Test: `web/frontend/tests/components/DocumentViewer.test.ts` (crear si no existe)

- [ ] **Step 1: Test que falla**

```ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import DocumentViewer from '@/components/DocumentViewer.vue'

describe('DocumentViewer — fields overlays', () => {
  it('renders field overlay when value has x/y/w/h', () => {
    const wrapper = mount(DocumentViewer, {
      props: {
        imageUrl: '/test.png',
        barcodes: [],
        fields: {
          cliente: { x: 10, y: 20, w: 100, h: 30, value: 'Acme Inc' },
          fecha: 'no coords',  // no debe pintarse
        },
        showBarcodes: false,
        showFields: true,
      },
    })
    const overlays = wrapper.findAll('[data-field-overlay]')
    expect(overlays).toHaveLength(1)
    expect(overlays[0].text()).toContain('cliente')
    expect(overlays[0].text()).toContain('Acme Inc')
  })

  it('hides barcode overlays when showBarcodes=false', () => {
    const wrapper = mount(DocumentViewer, {
      props: {
        imageUrl: '/test.png',
        barcodes: [{
          id: 1, value: 'X', symbology: 'EAN', engine: 'zxing',
          step_id: 's', quality: 0.9, pos_x: 0, pos_y: 0,
          pos_w: 50, pos_h: 20, role: '',
        }],
        fields: {},
        showBarcodes: false,
        showFields: true,
      },
    })
    expect(wrapper.findAll('[data-barcode-overlay]')).toHaveLength(0)
  })

  it('hides field overlays when showFields=false', () => {
    const wrapper = mount(DocumentViewer, {
      props: {
        imageUrl: '/test.png',
        barcodes: [],
        fields: {
          cliente: { x: 10, y: 20, w: 100, h: 30, value: 'X' },
        },
        showBarcodes: true,
        showFields: false,
      },
    })
    expect(wrapper.findAll('[data-field-overlay]')).toHaveLength(0)
  })
})
```

Run: `cd web/frontend && npx vitest run tests/components/DocumentViewer.test.ts`
Expected: FAIL

- [ ] **Step 2: Extender props y marcado**

En `<script setup lang="ts">` de `DocumentViewer.vue`:

```ts
interface FieldValue {
  x?: number; y?: number; w?: number; h?: number; value?: string
}

const props = withDefaults(defineProps<{
  imageUrl: string
  barcodes?: BarcodeResponse[]
  fields?: Record<string, FieldValue | string | number>
  showBarcodes?: boolean
  showFields?: boolean
}>(), {
  barcodes: () => [],
  fields: () => ({}),
  showBarcodes: true,
  showFields: true,
})

const fieldOverlays = computed(() =>
  Object.entries(props.fields).flatMap(([name, v]) => {
    if (typeof v !== 'object' || v === null) return []
    const obj = v as FieldValue
    if (!obj.x || !obj.y || !obj.w || !obj.h) return []
    return [{ name, ...obj }]
  })
)

const FIELD_PALETTE = ['#8839ef', '#d20f39', '#df8e1d', '#40a02b', '#04a5e5', '#1e66f5']
</script>
```

En el template, añadir junto al `v-for` existente de barcodes:

```html
<!-- Overlays de barcodes (sólo si showBarcodes) -->
<div
  v-if="showBarcodes"
  v-for="(bc, idx) in barcodes ?? []"
  :key="'bc-' + idx"
  data-barcode-overlay
  :style="{ ... }"  <!-- mismo estilo actual -->
/>

<!-- Overlays de fields (sólo si showFields) -->
<div
  v-if="showFields"
  v-for="(f, idx) in fieldOverlays"
  :key="'field-' + idx"
  data-field-overlay
  :style="{
    position: 'absolute',
    left: f.x + 'px',
    top: f.y + 'px',
    width: f.w + 'px',
    height: f.h + 'px',
    border: '2px dashed ' + FIELD_PALETTE[idx % FIELD_PALETTE.length],
    backgroundColor: FIELD_PALETTE[idx % FIELD_PALETTE.length] + '22',
    pointerEvents: 'none',
  }"
>
  <span
    :style="{
      position: 'absolute',
      top: '-20px',
      left: '0',
      background: FIELD_PALETTE[idx % FIELD_PALETTE.length],
      color: 'white',
      padding: '1px 4px',
      fontSize: '11px',
      borderRadius: '2px',
      whiteSpace: 'nowrap',
    }"
  >{{ f.name }}: {{ f.value ?? '' }}</span>
</div>
```

Verificar que el `v-if="showBarcodes"` del barcode actual no rompe el iterador existente (puede requerir `<template v-if>`).

- [ ] **Step 3: Tests pasan**

Run: `cd web/frontend && npx vitest run tests/components/DocumentViewer.test.ts`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add web/frontend/src/components/DocumentViewer.vue web/frontend/tests/components/DocumentViewer.test.ts
git commit -m "feat(web-frontend): DocumentViewer pinta overlays de fields con toggles"
```

---

## Task 12: ViewerToolbar — rotar + toggles overlay

**Files:**
- Modify: `web/frontend/src/components/workbench/ViewerToolbar.vue`
- Test: `web/frontend/tests/components/workbench/ViewerToolbar.test.ts` (extender)

- [ ] **Step 1: Extender tests**

```ts
  it('emits rotate with turns=1/2/3', async () => {
    const wrapper = mount(ViewerToolbar, { props: { ...defaultProps, canRotate: true } })
    await wrapper.find('[data-testid="btn-rotate"]').trigger('click')
    await wrapper.find('[data-testid="rotate-90"]').trigger('click')
    expect(wrapper.emitted('rotate')?.[0]).toEqual([1])

    await wrapper.find('[data-testid="btn-rotate"]').trigger('click')
    await wrapper.find('[data-testid="rotate-180"]').trigger('click')
    expect(wrapper.emitted('rotate')?.[1]).toEqual([2])
  })

  it('emits toggle-barcodes', async () => {
    const wrapper = mount(ViewerToolbar, {
      props: { ...defaultProps, showBarcodes: true },
    })
    await wrapper.find('[data-testid="btn-toggle-barcodes"]').trigger('click')
    expect(wrapper.emitted('toggle-barcodes')).toBeTruthy()
  })

  it('emits toggle-fields', async () => {
    const wrapper = mount(ViewerToolbar, {
      props: { ...defaultProps, showFields: true },
    })
    await wrapper.find('[data-testid="btn-toggle-fields"]').trigger('click')
    expect(wrapper.emitted('toggle-fields')).toBeTruthy()
  })

  it('disables rotate when canRotate=false (readOnly)', () => {
    const wrapper = mount(ViewerToolbar, { props: { ...defaultProps, canRotate: false } })
    expect(wrapper.find('[data-testid="btn-rotate"]').attributes('disabled')).toBeDefined()
  })
```

- [ ] **Step 2: Tests fallan**

Run: `cd web/frontend && npx vitest run tests/components/workbench/ViewerToolbar.test.ts`
Expected: FAIL

- [ ] **Step 3: Extender el componente**

Añadir props `canRotate: boolean`, `showBarcodes: boolean`, `showFields: boolean`. Añadir emits `rotate`, `toggle-barcodes`, `toggle-fields`.

En el template, añadir 3 botones: botón rotar con menú dropdown (90°/180°/270°) + dos toggles con aspecto on/off. Usar mismas variables Catppuccin y tamaños de botón.

- [ ] **Step 4: Tests pasan**

Run: `cd web/frontend && npx vitest run tests/components/workbench/ViewerToolbar.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/components/workbench/ViewerToolbar.vue web/frontend/tests/components/workbench/ViewerToolbar.test.ts
git commit -m "feat(web-frontend): ViewerToolbar con rotar-dropdown y toggles overlay"
```

---

## Task 13: Composable `usePageActions`

**Objetivo:** Centralizar mutaciones HTTP con rollback optimista.

**Files:**
- Create: `web/frontend/src/composables/usePageActions.ts`
- Test: `web/frontend/tests/composables/usePageActions.test.ts`

- [ ] **Step 1: Test que falla**

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { usePageActions } from '@/composables/usePageActions'
import { api } from '@/api/client'

vi.mock('@/api/client', () => ({
  api: {
    patch: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('usePageActions', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('toggleExcluded calls PATCH /pages/:id', async () => {
    ;(api.patch as any).mockResolvedValue({ data: { id: 1, is_excluded: true } })
    const actions = usePageActions()
    const res = await actions.toggleExcluded(1, true)
    expect(api.patch).toHaveBeenCalledWith('/pages/1', { is_excluded: true })
    expect(res.data.is_excluded).toBe(true)
  })

  it('rotatePage calls POST /pages/:id/rotate', async () => {
    ;(api.post as any).mockResolvedValue({ data: { id: 1 } })
    const actions = usePageActions()
    await actions.rotatePage(1, 2)
    expect(api.post).toHaveBeenCalledWith('/pages/1/rotate', { turns: 2 })
  })

  it('reorderPages calls POST /batches/:id/reorder', async () => {
    ;(api.post as any).mockResolvedValue({ data: {} })
    const actions = usePageActions()
    await actions.reorderPages(5, [10, 20, 30])
    expect(api.post).toHaveBeenCalledWith('/batches/5/reorder', { page_ids: [10, 20, 30] })
  })

  it('addBarcode calls POST /pages/:id/barcodes', async () => {
    ;(api.post as any).mockResolvedValue({ data: { id: 1 } })
    const actions = usePageActions()
    await actions.addBarcode(1, 'ABC', 'MANUAL')
    expect(api.post).toHaveBeenCalledWith('/pages/1/barcodes', { value: 'ABC', symbology: 'MANUAL' })
  })

  it('deleteBarcode calls DELETE', async () => {
    ;(api.delete as any).mockResolvedValue({})
    const actions = usePageActions()
    await actions.deleteBarcode(1, 42)
    expect(api.delete).toHaveBeenCalledWith('/pages/1/barcodes/42')
  })

  it('deletePage calls DELETE', async () => {
    ;(api.delete as any).mockResolvedValue({})
    const actions = usePageActions()
    await actions.deletePage(1)
    expect(api.delete).toHaveBeenCalledWith('/pages/1')
  })

  it('deleteFromPage calls DELETE /batches/:id/pages/after/:pid', async () => {
    ;(api.delete as any).mockResolvedValue({ data: { deleted: 3, batch_page_count: 2 } })
    const actions = usePageActions()
    const res = await actions.deleteFromPage(5, 17)
    expect(api.delete).toHaveBeenCalledWith('/batches/5/pages/after/17')
    expect(res.data.deleted).toBe(3)
  })
})
```

- [ ] **Step 2: Tests fallan**

Run: `cd web/frontend && npx vitest run tests/composables/usePageActions.test.ts`
Expected: FAIL

- [ ] **Step 3: Implementar**

`web/frontend/src/composables/usePageActions.ts`:

```ts
import { api } from '@/api/client'

export function usePageActions() {
  return {
    toggleExcluded: (pageId: number, value: boolean) =>
      api.patch(`/pages/${pageId}`, { is_excluded: value }),
    toggleReview: (pageId: number, value: boolean, reason = '') =>
      api.patch(`/pages/${pageId}`, { needs_review: value, review_reason: reason }),
    rotatePage: (pageId: number, turns: number) =>
      api.post(`/pages/${pageId}/rotate`, { turns }),
    deletePage: (pageId: number) =>
      api.delete(`/pages/${pageId}`),
    deleteFromPage: (batchId: number, pageId: number) =>
      api.delete(`/batches/${batchId}/pages/after/${pageId}`),
    reorderPages: (batchId: number, pageIds: number[]) =>
      api.post(`/batches/${batchId}/reorder`, { page_ids: pageIds }),
    addBarcode: (pageId: number, value: string, symbology: string) =>
      api.post(`/pages/${pageId}/barcodes`, { value, symbology }),
    deleteBarcode: (pageId: number, barcodeId: number) =>
      api.delete(`/pages/${pageId}/barcodes/${barcodeId}`),
  }
}
```

- [ ] **Step 4: Tests pasan**

Run: `cd web/frontend && npx vitest run tests/composables/usePageActions.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/composables/usePageActions.ts web/frontend/tests/composables/usePageActions.test.ts
git commit -m "feat(web-frontend): composable usePageActions con todas las mutaciones"
```

---

## Task 14: ThumbnailContextMenu

**Objetivo:** Menú contextual flotante con 4 acciones, cierre con ESC y click fuera.

**Files:**
- Create: `web/frontend/src/components/workbench/ThumbnailContextMenu.vue`
- Test: `web/frontend/tests/components/workbench/ThumbnailContextMenu.test.ts`

- [ ] **Step 1: Test que falla**

```ts
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ThumbnailContextMenu from '@/components/workbench/ThumbnailContextMenu.vue'

describe('ThumbnailContextMenu', () => {
  const defaultProps = {
    visible: true, x: 100, y: 200,
    pageId: 7, isExcluded: false, needsReview: false,
    readOnly: false, isLastPage: false,
  }

  it('renders 4 actions when visible', () => {
    const wrapper = mount(ThumbnailContextMenu, { props: defaultProps })
    expect(wrapper.find('[data-testid="action-exclude"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="action-review"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="action-delete"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="action-delete-after"]').exists()).toBe(true)
  })

  it('does not render when visible=false', () => {
    const wrapper = mount(ThumbnailContextMenu, {
      props: { ...defaultProps, visible: false },
    })
    expect(wrapper.find('[data-testid="action-exclude"]').exists()).toBe(false)
  })

  it('emits action with pageId', async () => {
    const wrapper = mount(ThumbnailContextMenu, { props: defaultProps })
    await wrapper.find('[data-testid="action-exclude"]').trigger('click')
    expect(wrapper.emitted('action')?.[0]).toEqual(['toggle-excluded', 7])
  })

  it('emits close on ESC', async () => {
    const wrapper = mount(ThumbnailContextMenu, { props: defaultProps, attachTo: document.body })
    await wrapper.trigger('keydown', { key: 'Escape' })
    // Listener está a nivel document; comprobar vía dispatchEvent
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('close')).toBeTruthy()
    wrapper.unmount()
  })

  it('disables all items when readOnly', () => {
    const wrapper = mount(ThumbnailContextMenu, {
      props: { ...defaultProps, readOnly: true },
    })
    const items = wrapper.findAll('[role="menuitem"]')
    items.forEach(i => expect(i.attributes('aria-disabled')).toBe('true'))
  })

  it('hides delete-after on last page', () => {
    const wrapper = mount(ThumbnailContextMenu, {
      props: { ...defaultProps, isLastPage: true },
    })
    expect(wrapper.find('[data-testid="action-delete-after"]').exists()).toBe(false)
  })
})
```

- [ ] **Step 2: Tests fallan**

Run: `cd web/frontend && npx vitest run tests/components/workbench/ThumbnailContextMenu.test.ts`
Expected: FAIL

- [ ] **Step 3: Implementar**

`web/frontend/src/components/workbench/ThumbnailContextMenu.vue`:

```vue
<script setup lang="ts">
import { onMounted, onBeforeUnmount, watch } from 'vue'

const props = defineProps<{
  visible: boolean
  x: number
  y: number
  pageId: number
  isExcluded: boolean
  needsReview: boolean
  readOnly: boolean
  isLastPage: boolean
}>()

const emit = defineEmits<{
  (e: 'action', type: 'toggle-excluded' | 'toggle-review' | 'delete-page' | 'delete-after', pageId: number): void
  (e: 'close'): void
}>()

const handleKeydown = (ev: KeyboardEvent) => {
  if (ev.key === 'Escape') emit('close')
}
const handleClick = (ev: MouseEvent) => {
  const target = ev.target as HTMLElement
  if (!target.closest('[data-thumb-ctx]')) emit('close')
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
  document.addEventListener('mousedown', handleClick)
})
onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleKeydown)
  document.removeEventListener('mousedown', handleClick)
})

const onAction = (t: 'toggle-excluded' | 'toggle-review' | 'delete-page' | 'delete-after') => {
  if (props.readOnly) return
  emit('action', t, props.pageId)
  emit('close')
}
</script>

<template>
  <div
    v-if="visible"
    data-thumb-ctx
    role="menu"
    :style="{
      position: 'fixed',
      left: x + 'px',
      top: y + 'px',
      zIndex: 1000,
    }"
    class="bg-base border border-surface1 rounded shadow-lg py-1 min-w-[200px]"
  >
    <button
      data-testid="action-exclude"
      role="menuitem"
      :aria-disabled="readOnly"
      class="w-full text-left px-3 py-1.5 text-sm hover:bg-surface0 disabled:opacity-50"
      :disabled="readOnly"
      @click="onAction('toggle-excluded')"
    >
      {{ isExcluded ? '✓ Incluir' : '⊘ Marcar excluida' }}
    </button>
    <button
      data-testid="action-review"
      role="menuitem"
      :aria-disabled="readOnly"
      class="w-full text-left px-3 py-1.5 text-sm hover:bg-surface0 disabled:opacity-50"
      :disabled="readOnly"
      @click="onAction('toggle-review')"
    >
      {{ needsReview ? '✓ Quitar revisión' : '⚐ Marcar revisión' }}
    </button>
    <hr class="my-1 border-surface0" />
    <button
      data-testid="action-delete"
      role="menuitem"
      :aria-disabled="readOnly"
      class="w-full text-left px-3 py-1.5 text-sm text-red hover:bg-surface0 disabled:opacity-50"
      :disabled="readOnly"
      @click="onAction('delete-page')"
    >
      🗑 Eliminar página
    </button>
    <button
      v-if="!isLastPage"
      data-testid="action-delete-after"
      role="menuitem"
      :aria-disabled="readOnly"
      class="w-full text-left px-3 py-1.5 text-sm text-red hover:bg-surface0 disabled:opacity-50"
      :disabled="readOnly"
      @click="onAction('delete-after')"
    >
      🗑 Eliminar desde aquí
    </button>
  </div>
</template>
```

- [ ] **Step 4: Tests pasan**

Run: `cd web/frontend && npx vitest run tests/components/workbench/ThumbnailContextMenu.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/components/workbench/ThumbnailContextMenu.vue web/frontend/tests/components/workbench/ThumbnailContextMenu.test.ts
git commit -m "feat(web-frontend): ThumbnailContextMenu con 4 acciones"
```

---

## Task 15: PageThumbnail con badges ⊘ / ⚐

**Files:**
- Modify: `web/frontend/src/components/workbench/PageThumbnail.vue`
- Test: `web/frontend/tests/components/workbench/PageThumbnail.test.ts` (extender)

- [ ] **Step 1: Tests extendidos**

```ts
  it('shows ⊘ badge when is_excluded', () => {
    const wrapper = mount(PageThumbnail, {
      props: { page: { ...mockPage, is_excluded: true }, ...baseProps },
    })
    expect(wrapper.find('[data-testid="badge-excluded"]').exists()).toBe(true)
  })

  it('shows ⚐ badge when needs_review', () => {
    const wrapper = mount(PageThumbnail, {
      props: { page: { ...mockPage, needs_review: true }, ...baseProps },
    })
    expect(wrapper.find('[data-testid="badge-review"]').exists()).toBe(true)
  })

  it('shows both badges when both flags true', () => {
    const wrapper = mount(PageThumbnail, {
      props: {
        page: { ...mockPage, is_excluded: true, needs_review: true },
        ...baseProps,
      },
    })
    expect(wrapper.find('[data-testid="badge-excluded"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="badge-review"]').exists()).toBe(true)
  })
```

- [ ] **Step 2: Tests fallan**

Run: `cd web/frontend && npx vitest run tests/components/workbench/PageThumbnail.test.ts`
Expected: FAIL

- [ ] **Step 3: Añadir badges**

En el template, en la esquina inferior-izquierda del thumbnail:

```html
<div class="absolute bottom-1 left-1 flex gap-0.5">
  <span
    v-if="page.is_excluded"
    data-testid="badge-excluded"
    class="bg-red/90 text-base rounded px-1 text-xs leading-tight"
    :title="$t ? $t('Excluida') : 'Excluida'"
  >⊘</span>
  <span
    v-if="page.needs_review"
    data-testid="badge-review"
    class="bg-yellow/90 text-base rounded px-1 text-xs leading-tight"
    :title="$t ? $t('Revisión') : 'Revisión'"
  >⚐</span>
</div>
```

- [ ] **Step 4: Tests pasan**

Run: `cd web/frontend && npx vitest run tests/components/workbench/PageThumbnail.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/components/workbench/PageThumbnail.vue web/frontend/tests/components/workbench/PageThumbnail.test.ts
git commit -m "feat(web-frontend): PageThumbnail con badges de excluida/revisión"
```

---

## Task 16: ThumbnailPanel con drag-drop + contextmenu

**Objetivo:** Integrar `vue-draggable-plus` para reorder y emit de right-click.

**Files:**
- Modify: `web/frontend/package.json` (añadir dep)
- Modify: `web/frontend/src/components/workbench/ThumbnailPanel.vue`
- Test: `web/frontend/tests/components/workbench/ThumbnailPanel.test.ts` (extender)

- [ ] **Step 1: Instalar dependencia**

```bash
cd web/frontend && npm install vue-draggable-plus
```

- [ ] **Step 2: Tests extendidos**

```ts
  it('emits contextmenu on right-click', async () => {
    const wrapper = mount(ThumbnailPanel, {
      props: { pages: [mockPage1, mockPage2], currentIndex: 0, readOnly: false },
    })
    await wrapper.find('[data-testid="thumb-0"]').trigger('contextmenu', { clientX: 100, clientY: 200 })
    expect(wrapper.emitted('contextmenu')?.[0]).toEqual([mockPage1.id, 100, 200])
  })

  it('emits reorder on drag end', async () => {
    // Mock el callback onEnd de vue-draggable-plus
    const wrapper = mount(ThumbnailPanel, {
      props: { pages: [mockPage1, mockPage2, mockPage3], currentIndex: 0, readOnly: false },
    })
    // Simular onEnd reordenado
    // vue-draggable-plus expone update:modelValue; emular cambio:
    ;(wrapper.vm as any).onDragEnd?.({ oldIndex: 0, newIndex: 2 })
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('reorder')?.[0]).toEqual([[mockPage2.id, mockPage3.id, mockPage1.id]])
  })

  it('disables drag when readOnly', async () => {
    const wrapper = mount(ThumbnailPanel, {
      props: { pages: [mockPage1, mockPage2], currentIndex: 0, readOnly: true },
    })
    // VueDraggable expone prop `disabled`
    const draggable = wrapper.findComponent({ name: 'VueDraggable' })
    expect(draggable.props('disabled')).toBe(true)
  })
```

- [ ] **Step 3: Tests fallan**

Run: `cd web/frontend && npx vitest run tests/components/workbench/ThumbnailPanel.test.ts`
Expected: FAIL

- [ ] **Step 4: Refactor a VueDraggable**

```vue
<script setup lang="ts">
import { VueDraggable } from 'vue-draggable-plus'
import { computed, ref, watch } from 'vue'
import PageThumbnail from './PageThumbnail.vue'
import type { PageResponse } from '@/api/types'

const props = defineProps<{
  pages: PageResponse[]
  currentIndex: number
  readOnly: boolean
}>()

const emit = defineEmits<{
  (e: 'select', index: number): void
  (e: 'reorder', newOrder: number[]): void
  (e: 'contextmenu', pageId: number, x: number, y: number): void
}>()

const list = ref<PageResponse[]>([...props.pages])
watch(() => props.pages, (v) => { list.value = [...v] }, { deep: true })

const onDragEnd = () => {
  emit('reorder', list.value.map(p => p.id))
}

const onContextMenu = (ev: MouseEvent, page: PageResponse) => {
  ev.preventDefault()
  emit('contextmenu', page.id, ev.clientX, ev.clientY)
}
</script>

<template>
  <div class="overflow-y-auto h-full p-2 bg-mantle">
    <VueDraggable
      v-model="list"
      :disabled="readOnly"
      handle=".thumb-handle"
      @end="onDragEnd"
      item-key="id"
    >
      <div
        v-for="(page, idx) in list"
        :key="page.id"
        :data-testid="`thumb-${idx}`"
        class="thumb-handle mb-2"
        @contextmenu="onContextMenu($event, page)"
        @click="emit('select', idx)"
      >
        <PageThumbnail
          :page="page"
          :active="idx === currentIndex"
          :index="idx"
        />
      </div>
    </VueDraggable>
    <p v-if="list.length === 0" class="text-subtext1 text-xs text-center mt-4">
      Sin páginas
    </p>
  </div>
</template>
```

- [ ] **Step 5: Tests pasan**

Run: `cd web/frontend && npx vitest run tests/components/workbench/ThumbnailPanel.test.ts`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add web/frontend/package.json web/frontend/package-lock.json web/frontend/src/components/workbench/ThumbnailPanel.vue web/frontend/tests/components/workbench/ThumbnailPanel.test.ts
git commit -m "feat(web-frontend): ThumbnailPanel con drag-drop (vue-draggable-plus) y contextmenu"
```

---

## Task 17: AddBarcodeDialog

**Files:**
- Create: `web/frontend/src/components/workbench/AddBarcodeDialog.vue`
- Test: `web/frontend/tests/components/workbench/AddBarcodeDialog.test.ts`

- [ ] **Step 1: Test que falla**

```ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AddBarcodeDialog from '@/components/workbench/AddBarcodeDialog.vue'

describe('AddBarcodeDialog', () => {
  it('renders when visible', () => {
    const wrapper = mount(AddBarcodeDialog, { props: { visible: true } })
    expect(wrapper.find('[data-testid="barcode-value"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="barcode-symbology"]').exists()).toBe(true)
  })

  it('disables submit when value empty', async () => {
    const wrapper = mount(AddBarcodeDialog, { props: { visible: true } })
    const submit = wrapper.find('[data-testid="submit"]')
    expect(submit.attributes('disabled')).toBeDefined()
  })

  it('emits submit with value and symbology', async () => {
    const wrapper = mount(AddBarcodeDialog, { props: { visible: true } })
    await wrapper.find('[data-testid="barcode-value"]').setValue('ABC123')
    await wrapper.find('[data-testid="barcode-symbology"]').setValue('CODE128')
    await wrapper.find('[data-testid="submit"]').trigger('click')
    expect(wrapper.emitted('submit')?.[0]).toEqual([{ value: 'ABC123', symbology: 'CODE128' }])
  })

  it('emits close on cancel', async () => {
    const wrapper = mount(AddBarcodeDialog, { props: { visible: true } })
    await wrapper.find('[data-testid="cancel"]').trigger('click')
    expect(wrapper.emitted('close')).toBeTruthy()
  })
})
```

- [ ] **Step 2: Tests fallan**

Run: `cd web/frontend && npx vitest run tests/components/workbench/AddBarcodeDialog.test.ts`
Expected: FAIL

- [ ] **Step 3: Implementar**

```vue
<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{
  (e: 'submit', data: { value: string; symbology: string }): void
  (e: 'close'): void
}>()

const value = ref('')
const symbology = ref('MANUAL')
const SYMBOLOGIES = ['MANUAL', 'CODE128', 'CODE39', 'EAN13', 'EAN8', 'QR', 'DATAMATRIX', 'PDF417']

watch(() => props.visible, (v) => {
  if (v) { value.value = ''; symbology.value = 'MANUAL' }
})

const onSubmit = () => {
  if (!value.value.trim()) return
  emit('submit', { value: value.value.trim(), symbology: symbology.value })
}
</script>

<template>
  <div
    v-if="visible"
    class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
    @click.self="emit('close')"
  >
    <div class="bg-base border border-surface1 rounded-lg p-6 min-w-[400px]">
      <h3 class="text-lg font-semibold mb-4">Añadir barcode manual</h3>
      <label class="block mb-3">
        <span class="text-sm text-subtext1 mb-1 block">Valor</span>
        <input
          data-testid="barcode-value"
          v-model="value"
          type="text"
          class="w-full px-3 py-2 border border-surface1 rounded bg-base"
          @keyup.enter="onSubmit"
          autofocus
        />
      </label>
      <label class="block mb-4">
        <span class="text-sm text-subtext1 mb-1 block">Symbology</span>
        <select
          data-testid="barcode-symbology"
          v-model="symbology"
          class="w-full px-3 py-2 border border-surface1 rounded bg-base"
        >
          <option v-for="s in SYMBOLOGIES" :key="s" :value="s">{{ s }}</option>
        </select>
      </label>
      <div class="flex justify-end gap-2">
        <button
          data-testid="cancel"
          class="px-3 py-1.5 border border-surface1 rounded hover:bg-surface0"
          @click="emit('close')"
        >Cancelar</button>
        <button
          data-testid="submit"
          class="px-3 py-1.5 bg-primary text-base rounded hover:bg-blue disabled:opacity-50"
          :disabled="!value.trim()"
          @click="onSubmit"
        >Añadir</button>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 4: Tests pasan**

Run: `cd web/frontend && npx vitest run tests/components/workbench/AddBarcodeDialog.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/components/workbench/AddBarcodeDialog.vue web/frontend/tests/components/workbench/AddBarcodeDialog.test.ts
git commit -m "feat(web-frontend): AddBarcodeDialog con value + symbology"
```

---

## Task 18: DeleteBarcodeDialog

**Files:**
- Create: `web/frontend/src/components/workbench/DeleteBarcodeDialog.vue`
- Test: `web/frontend/tests/components/workbench/DeleteBarcodeDialog.test.ts`

- [ ] **Step 1: Test que falla**

```ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import DeleteBarcodeDialog from '@/components/workbench/DeleteBarcodeDialog.vue'

describe('DeleteBarcodeDialog', () => {
  it('shows value in message', () => {
    const wrapper = mount(DeleteBarcodeDialog, {
      props: { visible: true, barcodeValue: 'ABC123' },
    })
    expect(wrapper.text()).toContain('ABC123')
  })

  it('emits confirm on click', async () => {
    const wrapper = mount(DeleteBarcodeDialog, {
      props: { visible: true, barcodeValue: 'X' },
    })
    await wrapper.find('[data-testid="confirm"]').trigger('click')
    expect(wrapper.emitted('confirm')).toBeTruthy()
  })

  it('emits close on cancel', async () => {
    const wrapper = mount(DeleteBarcodeDialog, {
      props: { visible: true, barcodeValue: 'X' },
    })
    await wrapper.find('[data-testid="cancel"]').trigger('click')
    expect(wrapper.emitted('close')).toBeTruthy()
  })
})
```

- [ ] **Step 2: Implementar**

```vue
<script setup lang="ts">
const props = defineProps<{ visible: boolean; barcodeValue: string }>()
const emit = defineEmits<{ (e: 'confirm'): void; (e: 'close'): void }>()
</script>

<template>
  <div
    v-if="visible"
    class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
    @click.self="emit('close')"
  >
    <div class="bg-base border border-surface1 rounded-lg p-6 min-w-[360px]">
      <h3 class="text-lg font-semibold mb-3">Eliminar barcode</h3>
      <p class="mb-5 text-text">¿Eliminar el barcode <strong>{{ barcodeValue }}</strong>?</p>
      <div class="flex justify-end gap-2">
        <button data-testid="cancel" class="px-3 py-1.5 border rounded" @click="emit('close')">
          Cancelar
        </button>
        <button data-testid="confirm" class="px-3 py-1.5 bg-red text-base rounded" @click="emit('confirm')">
          Eliminar
        </button>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 3: Tests pasan, commit**

```bash
cd web/frontend && npx vitest run tests/components/workbench/DeleteBarcodeDialog.test.ts
git add web/frontend/src/components/workbench/DeleteBarcodeDialog.vue web/frontend/tests/components/workbench/DeleteBarcodeDialog.test.ts
git commit -m "feat(web-frontend): DeleteBarcodeDialog de confirmación"
```

---

## Task 19: BarcodePanel editable + readOnly

**Files:**
- Modify: `web/frontend/src/components/workbench/BarcodePanel.vue`
- Test: `web/frontend/tests/components/workbench/BarcodePanel.test.ts` (extender)

- [ ] **Step 1: Tests extendidos**

```ts
  it('shows + Añadir button', () => {
    const wrapper = mount(BarcodePanel, {
      props: { barcodes: [], counters: {}, readOnly: false },
    })
    expect(wrapper.find('[data-testid="btn-add-barcode"]').exists()).toBe(true)
  })

  it('emits add-barcode on + click', async () => {
    const wrapper = mount(BarcodePanel, {
      props: { barcodes: [], counters: {}, readOnly: false },
    })
    await wrapper.find('[data-testid="btn-add-barcode"]').trigger('click')
    expect(wrapper.emitted('add-barcode')).toBeTruthy()
  })

  it('emits delete-barcode with id', async () => {
    const wrapper = mount(BarcodePanel, {
      props: {
        barcodes: [{ id: 42, value: 'X', symbology: 'MANUAL', engine: 'manual', step_id: 'manual', quality: 0, pos_x: 0, pos_y: 0, pos_w: 0, pos_h: 0, role: '' }],
        counters: {}, readOnly: false,
      },
    })
    await wrapper.find('[data-testid="btn-delete-bc-42"]').trigger('click')
    expect(wrapper.emitted('delete-barcode')?.[0]).toEqual([42])
  })

  it('hides action buttons when readOnly', () => {
    const wrapper = mount(BarcodePanel, {
      props: {
        barcodes: [{ id: 1, value: 'X', symbology: 'M', engine: 'm', step_id: '', quality: 0, pos_x: 0, pos_y: 0, pos_w: 0, pos_h: 0, role: '' }],
        counters: {}, readOnly: true,
      },
    })
    expect(wrapper.find('[data-testid="btn-add-barcode"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="btn-delete-bc-1"]').exists()).toBe(false)
  })
```

- [ ] **Step 2: Tests fallan**

Run: `cd web/frontend && npx vitest run tests/components/workbench/BarcodePanel.test.ts`
Expected: FAIL

- [ ] **Step 3: Añadir prop readOnly + botones**

En el header del panel:
```html
<button
  v-if="!readOnly"
  data-testid="btn-add-barcode"
  @click="emit('add-barcode')"
  class="ml-2 px-2 py-0.5 bg-primary text-base rounded text-xs"
>+ Añadir</button>
```

En cada fila de la tabla añadir columna:
```html
<td>
  <button
    v-if="!readOnly"
    :data-testid="`btn-delete-bc-${bc.id}`"
    @click="emit('delete-barcode', bc.id)"
    class="text-red hover:bg-surface0 rounded px-1"
    title="Eliminar"
  >×</button>
</td>
```

Añadir `readOnly: boolean` en props + emits `add-barcode`, `delete-barcode`.

- [ ] **Step 4: Tests pasan**

Run: `cd web/frontend && npx vitest run tests/components/workbench/BarcodePanel.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/components/workbench/BarcodePanel.vue web/frontend/tests/components/workbench/BarcodePanel.test.ts
git commit -m "feat(web-frontend): BarcodePanel editable con add/delete y readOnly"
```

---

## Task 20: Composable `useWorkbenchLog`

**Files:**
- Create: `web/frontend/src/composables/useWorkbenchLog.ts`
- Test: `web/frontend/tests/composables/useWorkbenchLog.test.ts`

- [ ] **Step 1: Tests**

```ts
import { describe, it, expect, beforeEach } from 'vitest'
import { useWorkbenchLog } from '@/composables/useWorkbenchLog'

describe('useWorkbenchLog', () => {
  let log: ReturnType<typeof useWorkbenchLog>
  beforeEach(() => { log = useWorkbenchLog(); log.clear() })

  it('starts empty', () => {
    expect(log.entries.value).toEqual([])
  })

  it('appends from WS event pipeline_started', () => {
    log.appendFromEvent({ type: 'pipeline_started', page_count: 5 })
    expect(log.entries.value).toHaveLength(1)
    expect(log.entries.value[0].level).toBe('info')
    expect(log.entries.value[0].source).toBe('pipeline')
    expect(log.entries.value[0].message).toContain('5')
  })

  it('appends from page_error', () => {
    log.appendFromEvent({ type: 'page_error', page_index: 2, error: 'boom' })
    const e = log.entries.value[0]
    expect(e.level).toBe('error')
    expect(e.message).toContain('boom')
  })

  it('loads persisted errors from pages', () => {
    log.loadPersistedErrors([
      {
        id: 1, page_index: 0,
        processing_errors_json: JSON.stringify(['err1']),
        script_errors_json: JSON.stringify([]),
        updated_at: '2026-04-23T10:00:00',
      },
      {
        id: 2, page_index: 1,
        processing_errors_json: JSON.stringify([]),
        script_errors_json: JSON.stringify([{ step_id: 's1', error: 'script fail' }]),
        updated_at: '2026-04-23T10:01:00',
      },
    ] as any)
    expect(log.entries.value).toHaveLength(2)
    expect(log.entries.value[0].level).toBe('error')
    expect(log.entries.value[1].level).toBe('warn')
  })

  it('filters by level', () => {
    log.appendFromEvent({ type: 'pipeline_started', page_count: 1 })  // info
    log.appendFromEvent({ type: 'page_error', page_index: 0, error: 'x' })  // error
    log.filterLevel.value = 'error'
    expect(log.filteredEntries.value).toHaveLength(1)
    expect(log.filteredEntries.value[0].level).toBe('error')
  })

  it('clear empties entries', () => {
    log.appendFromEvent({ type: 'pipeline_started', page_count: 1 })
    log.clear()
    expect(log.entries.value).toEqual([])
  })
})
```

- [ ] **Step 2: Tests fallan**

Run: `cd web/frontend && npx vitest run tests/composables/useWorkbenchLog.test.ts`
Expected: FAIL

- [ ] **Step 3: Implementar**

```ts
import { ref, computed } from 'vue'

export type LogLevel = 'debug' | 'info' | 'warn' | 'error'
export type LogSource = 'pipeline' | 'transfer' | 'script' | 'editor' | 'user'

export interface LogEntry {
  id: string
  timestamp: string
  level: LogLevel
  source: LogSource
  message: string
}

const LEVEL_ORDER: Record<LogLevel, number> = { debug: 0, info: 1, warn: 2, error: 3 }

const entries = ref<LogEntry[]>([])
const filterLevel = ref<LogLevel>('debug')

let idCounter = 0
const mkId = () => `${Date.now()}-${++idCounter}`

const append = (level: LogLevel, source: LogSource, message: string, ts?: string) => {
  entries.value.push({
    id: mkId(),
    timestamp: ts ?? new Date().toISOString(),
    level, source, message,
  })
  if (entries.value.length > 5000) entries.value.splice(0, entries.value.length - 5000)
}

const appendFromEvent = (ev: any) => {
  switch (ev.type) {
    case 'pipeline_started':
      append('info', 'pipeline', `Pipeline iniciado (${ev.page_count ?? '?'} páginas)`)
      break
    case 'page_processed':
      append('debug', 'pipeline', `Página ${ev.page_index + 1}/${ev.page_count ?? '?'} procesada`)
      break
    case 'page_error':
      append('error', 'pipeline', `Página ${ev.page_index + 1}: ${ev.error ?? ''}`)
      break
    case 'pipeline_completed':
      append('info', 'pipeline', `Pipeline completado${ev.elapsed ? ` en ${ev.elapsed}s` : ''}`)
      break
    case 'transfer_started':
      append('info', 'transfer', 'Transferencia iniciada')
      break
    case 'transfer_page':
      append('debug', 'transfer', `Transferida página ${ev.page_index + 1}`)
      break
    case 'transfer_completed':
      append('info', 'transfer', 'Transferencia completada')
      break
    case 'transfer_error':
      append('error', 'transfer', ev.error ?? 'Error en transferencia')
      break
    case 'transfer_aborted':
      append('warn', 'transfer', 'Transferencia abortada')
      break
    case 'page_updated':
      append('debug', 'editor', `Página ${ev.page_id}: ${ev.action}`)
      break
  }
}

const loadPersistedErrors = (pages: Array<{
  id: number; page_index: number;
  processing_errors_json: string; script_errors_json: string;
  updated_at: string;
}>) => {
  for (const p of pages) {
    let procErrs: unknown[] = []
    let scriptErrs: unknown[] = []
    try { procErrs = JSON.parse(p.processing_errors_json || '[]') } catch {}
    try { scriptErrs = JSON.parse(p.script_errors_json || '[]') } catch {}
    for (const err of procErrs) {
      append('error', 'pipeline', `Página ${p.page_index + 1}: ${err}`, p.updated_at)
    }
    for (const err of scriptErrs) {
      const e = err as any
      append('warn', 'script',
        `Página ${p.page_index + 1} paso ${e.step_id ?? '?'}: ${e.error ?? e}`,
        p.updated_at,
      )
    }
  }
}

const clear = () => { entries.value = [] }

const filteredEntries = computed(() =>
  entries.value.filter(e => LEVEL_ORDER[e.level] >= LEVEL_ORDER[filterLevel.value])
)

export function useWorkbenchLog() {
  return {
    entries,
    filteredEntries,
    filterLevel,
    appendFromEvent,
    loadPersistedErrors,
    clear,
    append,  // expuesto para acciones locales
  }
}
```

- [ ] **Step 4: Tests pasan + commit**

```bash
cd web/frontend && npx vitest run tests/composables/useWorkbenchLog.test.ts
git add web/frontend/src/composables/useWorkbenchLog.ts web/frontend/tests/composables/useWorkbenchLog.test.ts
git commit -m "feat(web-frontend): composable useWorkbenchLog (live WS + persisted errors)"
```

---

## Task 21: LogPanel component

**Files:**
- Create: `web/frontend/src/components/workbench/LogPanel.vue`
- Test: `web/frontend/tests/components/workbench/LogPanel.test.ts`

- [ ] **Step 1: Tests**

```ts
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import LogPanel from '@/components/workbench/LogPanel.vue'
import { useWorkbenchLog } from '@/composables/useWorkbenchLog'

describe('LogPanel', () => {
  beforeEach(() => { useWorkbenchLog().clear() })

  it('shows empty state when no entries', () => {
    const wrapper = mount(LogPanel)
    expect(wrapper.text()).toMatch(/sin eventos/i)
  })

  it('renders entries with level color', () => {
    const log = useWorkbenchLog()
    log.appendFromEvent({ type: 'pipeline_started', page_count: 3 })
    log.appendFromEvent({ type: 'page_error', page_index: 0, error: 'boom' })
    const wrapper = mount(LogPanel)
    expect(wrapper.findAll('[data-testid="log-entry"]')).toHaveLength(2)
    expect(wrapper.find('[data-level="error"]').exists()).toBe(true)
  })

  it('filter works', async () => {
    const log = useWorkbenchLog()
    log.appendFromEvent({ type: 'pipeline_started', page_count: 1 })  // info
    log.appendFromEvent({ type: 'page_error', page_index: 0, error: 'x' })  // error
    const wrapper = mount(LogPanel)
    const select = wrapper.find('[data-testid="filter-level"]')
    await select.setValue('error')
    expect(wrapper.findAll('[data-testid="log-entry"]')).toHaveLength(1)
  })

  it('clear button empties list', async () => {
    const log = useWorkbenchLog()
    log.appendFromEvent({ type: 'pipeline_started', page_count: 1 })
    const wrapper = mount(LogPanel)
    await wrapper.find('[data-testid="btn-clear"]').trigger('click')
    expect(wrapper.findAll('[data-testid="log-entry"]')).toHaveLength(0)
  })
})
```

- [ ] **Step 2: Implementar**

```vue
<script setup lang="ts">
import { useWorkbenchLog, type LogLevel } from '@/composables/useWorkbenchLog'

const log = useWorkbenchLog()
const LEVEL_COLOR: Record<LogLevel, string> = {
  debug: 'text-subtext1',
  info: 'text-text',
  warn: 'text-yellow',
  error: 'text-red',
}
</script>

<template>
  <div class="h-full flex flex-col bg-base">
    <div class="flex items-center gap-2 p-2 border-b border-surface0 text-xs">
      <select
        data-testid="filter-level"
        v-model="log.filterLevel.value"
        class="border border-surface1 rounded px-2 py-0.5 bg-base"
      >
        <option value="debug">Debug+</option>
        <option value="info">Info+</option>
        <option value="warn">Warn+</option>
        <option value="error">Error</option>
      </select>
      <button
        data-testid="btn-clear"
        @click="log.clear()"
        class="ml-auto px-2 py-0.5 border border-surface1 rounded hover:bg-surface0"
      >🗑 Limpiar</button>
      <span class="text-subtext1">{{ log.filteredEntries.value.length }} entries</span>
    </div>
    <div class="flex-1 overflow-y-auto font-mono text-xs p-2">
      <div
        v-for="e in log.filteredEntries.value"
        :key="e.id"
        data-testid="log-entry"
        :data-level="e.level"
        :class="LEVEL_COLOR[e.level]"
        class="py-0.5"
      >
        <span class="text-subtext1">{{ e.timestamp.slice(11, 19) }}</span>
        <span class="mx-1 uppercase text-[10px]">{{ e.level }}</span>
        <span class="text-subtext1">·{{ e.source }}·</span>
        <span>{{ e.message }}</span>
      </div>
      <p v-if="log.filteredEntries.value.length === 0" class="text-subtext1 italic text-center mt-4">
        Sin eventos aún. Los mensajes aparecerán aquí mientras procesas el lote.
      </p>
    </div>
  </div>
</template>
```

- [ ] **Step 3: Tests pasan + commit**

```bash
cd web/frontend && npx vitest run tests/components/workbench/LogPanel.test.ts
git add web/frontend/src/components/workbench/LogPanel.vue web/frontend/tests/components/workbench/LogPanel.test.ts
git commit -m "feat(web-frontend): LogPanel con filtro, clear y color por nivel"
```

---

## Task 22: Activar tab Log en MetadataPanel

**Files:**
- Modify: `web/frontend/src/components/workbench/MetadataPanel.vue`
- Test: `web/frontend/tests/components/workbench/MetadataPanel.test.ts` (extender)

- [ ] **Step 1: Test extendido**

```ts
  it('renders LogPanel inside Log tab', async () => {
    const wrapper = mount(MetadataPanel, { props: { ...defaultProps } })
    await wrapper.find('[data-testid="tab-log"]').trigger('click')
    expect(wrapper.findComponent({ name: 'LogPanel' }).exists()).toBe(true)
  })

  it('shows warning count in Log tab label', async () => {
    const log = useWorkbenchLog()
    log.clear()
    log.appendFromEvent({ type: 'page_error', page_index: 0, error: 'x' })
    const wrapper = mount(MetadataPanel, { props: { ...defaultProps } })
    expect(wrapper.find('[data-testid="tab-log-label"]').text()).toContain('(1 ⚠)')
  })
```

- [ ] **Step 2: Tests fallan**

Run: `cd web/frontend && npx vitest run tests/components/workbench/MetadataPanel.test.ts`
Expected: FAIL

- [ ] **Step 3: Activar tab**

Importar LogPanel, quitar `disabled` del tab Log, renderizar `<LogPanel />` cuando el tab está activo. Añadir contador reactivo de warns+errors en el label.

- [ ] **Step 4: Tests pasan + commit**

```bash
cd web/frontend && npx vitest run tests/components/workbench/MetadataPanel.test.ts
git add web/frontend/src/components/workbench/MetadataPanel.vue web/frontend/tests/components/workbench/MetadataPanel.test.ts
git commit -m "feat(web-frontend): activar tab Log con contador de warnings"
```

---

## Task 23: WorkbenchView — integración final

**Objetivo:** Orquestar todo: readOnly cascada, handlers nuevos, WS `page_updated`, carga de errores persistidos.

**Files:**
- Modify: `web/frontend/src/views/batches/WorkbenchView.vue`
- Test: `web/frontend/tests/views/WorkbenchView.test.ts` (extender)

- [ ] **Step 1: Tests extendidos**

```ts
  it('passes readOnly=true to children when batch is running', () => {
    const wrapper = mount(WorkbenchView, {
      props: { ...defaultProps, batch: { ...mockBatch, state: 'running' } },
    })
    expect(wrapper.findComponent({ name: 'BarcodePanel' }).props('readOnly')).toBe(true)
    expect(wrapper.findComponent({ name: 'ThumbnailPanel' }).props('readOnly')).toBe(true)
  })

  it('passes readOnly=false when state is read', () => {
    const wrapper = mount(WorkbenchView, {
      props: { ...defaultProps, batch: { ...mockBatch, state: 'read' } },
    })
    expect(wrapper.findComponent({ name: 'BarcodePanel' }).props('readOnly')).toBe(false)
  })

  it('loads persisted errors when batch mounts', async () => {
    const log = useWorkbenchLog()
    log.clear()
    const pagesWithErrors = [{
      id: 1, page_index: 0,
      processing_errors_json: JSON.stringify(['boom']),
      script_errors_json: '[]',
      updated_at: '2026-04-23T10:00:00',
    }]
    mount(WorkbenchView, {
      props: { ...defaultProps, pages: pagesWithErrors },
    })
    await flushPromises()
    expect(log.entries.value.some(e => e.message.includes('boom'))).toBe(true)
  })

  it('WS page_updated triggers refetch', async () => {
    // Mock WS...
  })
```

- [ ] **Step 2: Integrar**

En `WorkbenchView.vue`:

1. Importar `usePageActions`, `useWorkbenchLog`, `useOverlayToggles`, `ThumbnailContextMenu`, `AddBarcodeDialog`, `DeleteBarcodeDialog`.
2. `const isReadOnly = computed(() => ['running', 'transferring'].includes(batch.value?.state ?? ''))`.
3. `onMounted`: llamar a `log.loadPersistedErrors(pages.value)`.
4. Extender handler WS para:
   - Pasar TODOS los eventos al log vía `log.appendFromEvent(ev)`.
   - Al recibir `page_updated`: refetch del lote (o actualización granular según `action`).
5. Handler right-click de ThumbnailPanel → abre ThumbnailContextMenu con coords.
6. Acción del context-menu → llama a `pageActions.toggleExcluded / toggleReview / deletePage / deleteFromPage`.
7. Handler reorder de ThumbnailPanel → `pageActions.reorderPages(batch.id, newOrder)` con rollback si falla.
8. Handler rotate del ViewerToolbar → `pageActions.rotatePage(currentPage.id, turns)` → cache-bust (`image_url + '?v=' + Date.now()`).
9. Handler toggle-barcodes / toggle-fields → `overlayToggles.showBarcodes.value = !overlayToggles.showBarcodes.value` (idem fields).
10. AddBarcodeDialog controlado por ref `addBarcodeOpen`; onSubmit → `pageActions.addBarcode(...)` + append a la lista local.
11. DeleteBarcodeDialog controlado por refs `deleteBarcodeTarget` + `deleteBarcodeOpen`; onConfirm → `pageActions.deleteBarcode(...)` + filter local.
12. Pasar `readOnly`, `show-barcodes`, `show-fields`, `fields` al DocumentViewer; `readOnly` a BarcodePanel y ThumbnailPanel; `canRotate=!isReadOnly` a ViewerToolbar.
13. Toast de error al pillar 409 desde cualquier `pageActions.*`.

- [ ] **Step 3: Tests pasan**

Run: `cd web/frontend && npx vitest run tests/views/WorkbenchView.test.ts`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add web/frontend/src/views/batches/WorkbenchView.vue web/frontend/tests/views/WorkbenchView.test.ts
git commit -m "feat(web-frontend): WorkbenchView integra todas las features de Fase 3"
```

---

## Task 24: QA visual + cleanup

- [ ] **Step 1: Levantar stack**

```bash
# Terminal 1
source .venv/bin/activate && uvicorn web.api.main:app --reload
# Terminal 2
cd web/frontend && npm run dev
```

- [ ] **Step 2: QA manual con Playwright**

Navegar a `http://localhost:5173`, login, abrir un lote con páginas. Verificar:

1. **Rotación**: botón rotar en ViewerToolbar → 90° → imagen rota, overlay de barcodes sigue en sitio.
2. **Overlays fields**: crear un lote con pipeline que setee `page.fields["cliente"] = {"x":10,"y":20,"w":100,"h":30,"value":"Acme"}` vía ScriptStep → run → ver overlay.
3. **Toggles overlay**: click en toggle barcodes, toggle fields — persistencia al refrescar.
4. **Menú contextual**: right-click en miniatura → 4 acciones visibles → excluir → badge ⊘ aparece.
5. **Revisión**: right-click → revisar → badge ⚐ aparece.
6. **Eliminar página**: right-click → eliminar → dialog → confirma → desaparece.
7. **Eliminar desde aquí**: en lote con 5+ páginas → página 3 → eliminar desde aquí → confirma "Se eliminarán 3" → solo quedan 2.
8. **Reorder**: drag miniatura de pos 1 a pos 3 → se reordena.
9. **Add/Delete barcode**: + en BarcodePanel → modal → añadir → fila nueva → × → dialog → eliminada.
10. **Tab Log**: ver eventos al subir y ejecutar pipeline; errores persistidos al reabrir lote.
11. **Bloqueo durante run**: `POST /batches/:id/run` → intentar rotar durante ejecución → botón disabled + tooltip.
12. **Temas claro y oscuro**: cambiar tema y verificar los 11 casos anteriores.

- [ ] **Step 3: Fix bugs detectados**

Cada bug = commit propio con mensaje descriptivo.

- [ ] **Step 4: Limpieza**

- Revisar consola del navegador y logs del backend: 0 warnings nuevos.
- Formatear: `cd web/frontend && npx prettier --write src/` + `ruff format web/api/`.
- Commit final: `chore: format after Fase 3`.

- [ ] **Step 5: Actualizar MEMORY.md**

Añadir al proyecto MEMORY la mención de Fase 3 cerrada y los archivos nuevos. Actualizar `project_web_session_next.md` con "Fase 3 cerrada, pendiente Fase 4".

- [ ] **Step 6: Push**

```bash
git push origin feature/web
```

- [ ] **Step 7: Generar informe de progreso**

Invocar skill `progreso-doc` para generar `docs/progreso_2026-04-23.md`.

---

## Summary

- **24 tasks** secuenciales con dependencias documentadas.
- **Fase de paralelización**:
  - Tasks 2-7 → paralelizables tras Task 1.
  - Tasks 10, 11, 12, 15, 17, 18, 20 → UI-only, paralelizables.
- **Subagent-driven-development recomendado** para disparar fases paralelas por dispatch.
- **TDD estricto**: cada task empieza por el test que falla.
- **Commits frecuentes**: 1 commit por task + ajustes granulares.
