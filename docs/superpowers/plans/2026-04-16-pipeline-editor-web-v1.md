# Editor de Pipeline en web — Plan de implementación v1

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** [docs/superpowers/specs/2026-04-16-pipeline-editor-web-design.md](../specs/2026-04-16-pipeline-editor-web-design.md)

**Goal:** Implementar v1 del editor de pipeline en la web: infraestructura completa + edición de `BarcodeStep`. Los otros tres tipos de step (`ImageOp`, `OCR`, `Script`) quedan para v2/v3/v4 y no se tocan en este plan.

**Architecture:**
- Backend: dos endpoints nuevos en `web/api/routers/pipeline.py` (`GET` y `PUT` del pipeline entero), con validación delegada a `app/pipeline/serializer.deserialize()`.
- Frontend: página dedicada `/applications/:id/pipeline`, store Pinia que mantiene el pipeline en memoria, drawer lateral con `BarcodeStepForm`, drag-to-reorder con `vue-draggable-plus`. Save explícito por step: el drawer usa draft local; al guardar, el store se actualiza y dispara `PUT` con el pipeline completo.

**Tech Stack:** FastAPI + SQLAlchemy 2.x (backend), Vue 3 + Vite + TypeScript 6 + Pinia + Vue Router 4 + Tailwind 4 (frontend), `vue-draggable-plus` (nuevo), `vitest` (nuevo para tests de store).

---

## Estructura de archivos

**Backend (crear):**
- `web/api/schemas/pipeline.py` — schemas pydantic (`PipelineUpdate`, `PipelineResponse`, `StepPayload`).
- `web/api/routers/pipeline.py` — router con dos endpoints.

**Backend (modificar):**
- `web/api/main.py` — registrar el nuevo router.

**Backend (tests, añadir a archivo existente):**
- `tests/test_web_api.py` — nueva `TestPipelineEditor` con los 9 tests del spec.

**Frontend (crear):**
- `web/frontend/src/views/applications/PipelineEditorView.vue`
- `web/frontend/src/components/pipeline/PipelineStepList.vue`
- `web/frontend/src/components/pipeline/PipelineStepRow.vue`
- `web/frontend/src/components/pipeline/PipelineStepDrawer.vue`
- `web/frontend/src/components/pipeline/AddStepMenu.vue`
- `web/frontend/src/components/pipeline/forms/BarcodeStepForm.vue`
- `web/frontend/src/stores/pipeline.ts`
- `web/frontend/src/api/pipeline.ts`
- `web/frontend/src/api/types-pipeline.ts` — tipos TS del dominio pipeline
- `web/frontend/tests/stores/pipeline.store.test.ts`
- `web/frontend/vitest.config.ts`

**Frontend (modificar):**
- `web/frontend/src/api/client.ts` — añadir método `put`.
- `web/frontend/src/router/index.ts` — nueva ruta.
- `web/frontend/src/views/applications/ApplicationDetailView.vue` — botón "Editar pipeline".
- `web/frontend/package.json` — dependencias nuevas (`vue-draggable-plus`, `vitest`, `@vue/test-utils`, `jsdom`, `@pinia/testing`).

---

## Task 1 — Backend: schemas pydantic

**Files:**
- Create: `web/api/schemas/pipeline.py`

- [ ] **Step 1: Crear el fichero de schemas**

Código completo de `web/api/schemas/pipeline.py`:

```python
"""Schemas pydantic para el editor de pipeline.

La validación fina de cada step se delega a
``app.pipeline.serializer.deserialize()`` (misma fuente que usa el runner).
Por eso ``StepPayload`` permite campos extra y solo valida ``id``,
``type`` y ``enabled``.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StepPayload(BaseModel):
    """Representa un step en el JSON request/response.

    Los campos específicos del tipo (engine, symbologies, etc.) se
    aceptan como ``extra`` y se validan en backend vía ``deserialize()``.
    """

    model_config = ConfigDict(extra="allow")

    id: str = Field(min_length=1)
    type: Literal["image_op", "barcode", "ocr", "script"]
    enabled: bool = True


class PipelineUpdate(BaseModel):
    """Body del ``PUT /applications/{id}/pipeline``."""

    steps: list[StepPayload]


class PipelineResponse(BaseModel):
    """Response del ``GET`` y el ``PUT``."""

    steps: list[dict[str, Any]]
```

- [ ] **Step 2: Commit**

```bash
git add web/api/schemas/pipeline.py
git commit -m "feat(web): schemas pydantic para el editor de pipeline"
```

---

## Task 2 — Backend: tests del GET (TDD, deben fallar)

**Files:**
- Modify: `tests/test_web_api.py` (añadir al final)

- [ ] **Step 1: Añadir helper y tests del GET al final de `tests/test_web_api.py`**

Añade este bloque al **final** del fichero:

```python
# ===================================================================
# Editor de pipeline
# ===================================================================


def _barcode_step_payload(step_id: str = "bc-1") -> dict:
    """Payload mínimo de un BarcodeStep válido para usar en requests."""
    return {
        "id": step_id,
        "type": "barcode",
        "enabled": True,
        "engine": "motor1",
        "symbologies": [],
        "regex": "",
        "regex_include_symbology": False,
        "orientations": ["horizontal", "vertical"],
        "quality_threshold": 0.0,
        "window": None,
    }


class TestPipelineEditorGet:
    def test_get_pipeline_app_nueva_devuelve_lista_vacia(self, client):
        h = _auth_header(client)
        app_id = _create_app_and_get_id(client, h)

        resp = client.get(f"/api/applications/{app_id}/pipeline", headers=h)

        assert resp.status_code == 200
        assert resp.json() == {"steps": []}

    def test_get_pipeline_con_steps_preexistentes(self, client):
        h = _auth_header(client)
        import json

        pipeline = json.dumps([_barcode_step_payload()])
        app_id = _create_app_with_pipeline(client, h, pipeline)

        resp = client.get(f"/api/applications/{app_id}/pipeline", headers=h)

        assert resp.status_code == 200
        steps = resp.json()["steps"]
        assert len(steps) == 1
        assert steps[0]["type"] == "barcode"
        assert steps[0]["id"] == "bc-1"

    def test_get_pipeline_otro_tenant_404(self, client):
        h_a = _auth_header(client, email="a@a.com", tenant_name="A")
        app_id = _create_app_and_get_id(client, h_a)
        h_b = _auth_header(client, email="b@b.com", tenant_name="B")

        resp = client.get(f"/api/applications/{app_id}/pipeline", headers=h_b)

        assert resp.status_code == 404

    def test_get_pipeline_app_inexistente_404(self, client):
        h = _auth_header(client)

        resp = client.get("/api/applications/99999/pipeline", headers=h)

        assert resp.status_code == 404

    def test_get_pipeline_sin_auth_401(self, client):
        resp = client.get("/api/applications/1/pipeline")
        assert resp.status_code == 401
```

- [ ] **Step 2: Ejecutar los tests y verificar que fallan**

Run: `pytest tests/test_web_api.py::TestPipelineEditorGet -v`

Expected: 5 tests fallan con 404 (porque la ruta no existe).

- [ ] **Step 3: Commit**

```bash
git add tests/test_web_api.py
git commit -m "test(web): tests del GET /applications/:id/pipeline (failing)"
```

---

## Task 3 — Backend: implementación del GET + integración

**Files:**
- Create: `web/api/routers/pipeline.py`
- Modify: `web/api/main.py`

- [ ] **Step 1: Crear el router con el endpoint GET**

Código completo de `web/api/routers/pipeline.py`:

```python
"""Router del editor de pipeline de una aplicación.

Expone dos endpoints:

- ``GET /applications/{app_id}/pipeline`` — lee el pipeline actual.
- ``PUT /applications/{app_id}/pipeline`` — reemplaza el pipeline entero.

La validación se delega a ``app.pipeline.serializer.deserialize()``,
que es la misma función que usa el runner del pipeline.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.application import Application
from app.pipeline.serializer import (
    PipelineSerializationError,
    deserialize,
    serialize,
)
from web.api.auth.dependencies import CurrentUser
from web.api.database import SessionDep
from web.api.schemas.pipeline import PipelineResponse, PipelineUpdate

router = APIRouter()


def _get_app_or_404(app_id: int, tenant_id: int, db: Session) -> Application:
    """Obtiene una aplicación del tenant actual o lanza 404.

    Duplicado controlado: existe helper equivalente en applications.py,
    pero duplicarlo aquí evita un import cruzado entre routers.
    """
    app = db.execute(
        select(Application).where(
            Application.id == app_id,
            Application.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aplicación no encontrada",
        )
    return app


def _steps_as_dicts(json_str: str) -> list[dict]:
    """Convierte el pipeline_json a lista de dicts (via deserialize + asdict).

    Pasa por deserialize para validar y filtrar tipos eliminados
    (REMOVED_STEP_TYPES), y luego re-serializa a dicts para el cliente.
    """
    from dataclasses import asdict

    steps = deserialize(json_str) if json_str else []
    return [asdict(s) for s in steps]


@router.get("/{app_id}/pipeline", response_model=PipelineResponse)
def get_pipeline(app_id: int, user: CurrentUser, db: SessionDep):
    """Devuelve el pipeline de la aplicación."""
    app = _get_app_or_404(app_id, user.tenant_id, db)
    try:
        steps = _steps_as_dicts(app.pipeline_json or "[]")
    except PipelineSerializationError as e:
        # Pipeline corrupto en BD: devolver vacío y loggear
        import logging

        logging.getLogger(__name__).warning(
            "Pipeline corrupto en app %d: %s", app_id, e
        )
        steps = []
    return {"steps": steps}
```

- [ ] **Step 2: Registrar el router en `web/api/main.py`**

Modifica `web/api/main.py` añadiendo la importación y el `include_router`. En la sección de imports de routers (línea 74-80), añade:

```python
    from web.api.routers.pipeline import router as pipeline_router
```

Y tras `app.include_router(team_router, prefix="/api", tags=["team"])` añade:

```python
    app.include_router(
        pipeline_router, prefix="/api/applications", tags=["pipeline"]
    )
```

- [ ] **Step 3: Ejecutar los tests y verificar que pasan**

Run: `pytest tests/test_web_api.py::TestPipelineEditorGet -v`

Expected: 5 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add web/api/routers/pipeline.py web/api/main.py
git commit -m "feat(web): endpoint GET /applications/:id/pipeline"
```

---

## Task 4 — Backend: tests del PUT (TDD)

**Files:**
- Modify: `tests/test_web_api.py`

- [ ] **Step 1: Añadir `TestPipelineEditorPut` al final del fichero**

```python
class TestPipelineEditorPut:
    def test_put_pipeline_barcode_ok_round_trip(self, client):
        h = _auth_header(client)
        app_id = _create_app_and_get_id(client, h)

        body = {"steps": [_barcode_step_payload()]}
        resp = client.put(
            f"/api/applications/{app_id}/pipeline", headers=h, json=body
        )

        assert resp.status_code == 200
        assert len(resp.json()["steps"]) == 1
        assert resp.json()["steps"][0]["engine"] == "motor1"

        # GET devuelve lo mismo
        resp2 = client.get(f"/api/applications/{app_id}/pipeline", headers=h)
        assert resp2.json()["steps"][0]["id"] == "bc-1"

    def test_put_pipeline_reemplaza_completo(self, client):
        h = _auth_header(client)
        app_id = _create_app_and_get_id(client, h)

        # Primer PUT con 2 steps
        body1 = {
            "steps": [
                _barcode_step_payload("bc-a"),
                _barcode_step_payload("bc-b"),
            ]
        }
        client.put(f"/api/applications/{app_id}/pipeline", headers=h, json=body1)

        # Segundo PUT con solo 1 step distinto
        body2 = {"steps": [_barcode_step_payload("bc-c")]}
        resp = client.put(
            f"/api/applications/{app_id}/pipeline", headers=h, json=body2
        )

        assert resp.status_code == 200
        steps = resp.json()["steps"]
        assert len(steps) == 1
        assert steps[0]["id"] == "bc-c"

    def test_put_pipeline_tipo_desconocido_422(self, client):
        h = _auth_header(client)
        app_id = _create_app_and_get_id(client, h)

        body = {
            "steps": [
                {"id": "x", "type": "xxxx_unknown", "enabled": True},
            ]
        }
        resp = client.put(
            f"/api/applications/{app_id}/pipeline", headers=h, json=body
        )

        # Pydantic lo rechaza por Literal mismatch antes de llegar al deserialize
        assert resp.status_code == 422

    def test_put_pipeline_campo_invalido_en_step_422(self, client):
        h = _auth_header(client)
        app_id = _create_app_and_get_id(client, h)

        # Barcode con "engine" inválido (no es "motor1" ni "motor2")
        body = {
            "steps": [
                {
                    "id": "bc-1",
                    "type": "barcode",
                    "enabled": True,
                    "engine": "motor_fantasma",
                }
            ]
        }
        resp = client.put(
            f"/api/applications/{app_id}/pipeline", headers=h, json=body
        )

        assert resp.status_code == 422
        assert "Pipeline inválido" in resp.json()["detail"]

    def test_put_pipeline_otro_tenant_404(self, client):
        h_a = _auth_header(client, email="a@a.com", tenant_name="A")
        app_id = _create_app_and_get_id(client, h_a)
        h_b = _auth_header(client, email="b@b.com", tenant_name="B")

        body = {"steps": [_barcode_step_payload()]}
        resp = client.put(
            f"/api/applications/{app_id}/pipeline", headers=h_b, json=body
        )

        assert resp.status_code == 404

    def test_put_pipeline_persiste_en_pipeline_json(self, client):
        h = _auth_header(client)
        app_id = _create_app_and_get_id(client, h)

        body = {"steps": [_barcode_step_payload("bc-xyz")]}
        client.put(f"/api/applications/{app_id}/pipeline", headers=h, json=body)

        # Verifica via GET /applications/:id (endpoint existente)
        resp = client.get(f"/api/applications/{app_id}", headers=h)
        import json

        stored = json.loads(resp.json()["pipeline_json"])
        assert len(stored) == 1
        assert stored[0]["id"] == "bc-xyz"

    def test_put_pipeline_lista_vacia_ok(self, client):
        h = _auth_header(client)
        app_id = _create_app_and_get_id(client, h)

        resp = client.put(
            f"/api/applications/{app_id}/pipeline", headers=h, json={"steps": []}
        )

        assert resp.status_code == 200
        assert resp.json()["steps"] == []
```

- [ ] **Step 2: Ejecutar los tests y verificar que fallan**

Run: `pytest tests/test_web_api.py::TestPipelineEditorPut -v`

Expected: 7 tests fallan con 405 (Method Not Allowed) porque el PUT todavía no existe.

- [ ] **Step 3: Commit**

```bash
git add tests/test_web_api.py
git commit -m "test(web): tests del PUT /applications/:id/pipeline (failing)"
```

---

## Task 5 — Backend: implementación del PUT

**Files:**
- Modify: `web/api/routers/pipeline.py`

- [ ] **Step 1: Añadir el endpoint PUT**

En `web/api/routers/pipeline.py`, añade al final:

```python
@router.put("/{app_id}/pipeline", response_model=PipelineResponse)
def update_pipeline(
    app_id: int,
    data: PipelineUpdate,
    user: CurrentUser,
    db: SessionDep,
):
    """Reemplaza el pipeline entero de la aplicación.

    Valida con ``deserialize()`` para garantizar que el pipeline
    guardado es ejecutable por el runner. Si falla, responde 422.
    """
    app = _get_app_or_404(app_id, user.tenant_id, db)

    # Construir JSON del cliente y validar vía deserialize
    import json

    raw_steps = [step.model_dump() for step in data.steps]
    candidate_json = json.dumps(raw_steps, ensure_ascii=False)

    try:
        steps = deserialize(candidate_json)
    except PipelineSerializationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Pipeline inválido: {e}",
        )

    # Re-serializar con la versión canónica (tuplas→listas, etc.)
    app.pipeline_json = serialize(steps)
    db.commit()

    from dataclasses import asdict

    return {"steps": [asdict(s) for s in steps]}
```

- [ ] **Step 2: Ejecutar los tests y verificar que pasan**

Run: `pytest tests/test_web_api.py::TestPipelineEditorPut -v`

Expected: 7 tests PASS.

- [ ] **Step 3: Ejecutar toda la suite backend para regresión**

Run: `pytest tests/test_web_api.py -v`

Expected: todos los tests que ya pasaban siguen pasando (no debe haber regresiones).

- [ ] **Step 4: Commit**

```bash
git add web/api/routers/pipeline.py
git commit -m "feat(web): endpoint PUT /applications/:id/pipeline con validacion deserialize()"
```

---

## Task 6 — Frontend: dependencias nuevas + método `put` en api client

**Files:**
- Modify: `web/frontend/package.json` (via npm install)
- Modify: `web/frontend/src/api/client.ts`

- [ ] **Step 1: Instalar dependencias**

```bash
cd web/frontend
npm install vue-draggable-plus
npm install -D vitest @vue/test-utils jsdom @pinia/testing
cd -
```

- [ ] **Step 2: Añadir método `put` al api client**

Modifica `web/frontend/src/api/client.ts`, en el objeto `api` (líneas 79-102), añade un método `put` tras `patch`:

```typescript
  put: <T>(path: string, data: unknown) =>
    request<T>(path, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
```

Después del cambio, el objeto `api` queda con `get`, `post`, `patch`, `put`, `delete`, `uploadFiles`.

- [ ] **Step 3: Verificar que el build sigue compilando**

```bash
cd web/frontend && npx vue-tsc --noEmit && cd -
```

Expected: sin errores.

- [ ] **Step 4: Commit**

```bash
git add web/frontend/package.json web/frontend/package-lock.json web/frontend/src/api/client.ts
git commit -m "chore(web): dep vue-draggable-plus, vitest; api.put()"
```

---

## Task 7 — Frontend: tipos TS + API wrapper

**Files:**
- Create: `web/frontend/src/api/types-pipeline.ts`
- Create: `web/frontend/src/api/pipeline.ts`

- [ ] **Step 1: Crear tipos TS**

`web/frontend/src/api/types-pipeline.ts`:

```typescript
// Tipos del dominio pipeline (compartidos entre store, vistas y forms).

export type StepType = 'image_op' | 'barcode' | 'ocr' | 'script'

export interface BasePipelineStep {
  id: string
  type: StepType
  enabled: boolean
}

export interface BarcodeStep extends BasePipelineStep {
  type: 'barcode'
  engine: 'motor1' | 'motor2'
  symbologies: string[]
  regex: string
  regex_include_symbology: boolean
  orientations: string[]
  quality_threshold: number
  window: [number, number, number, number] | null
}

// Union para el resto de tipos: en v1 solo se leen, no se editan.
export interface GenericStep extends BasePipelineStep {
  [key: string]: unknown
}

export type PipelineStep = BarcodeStep | GenericStep

export interface PipelineResponse {
  steps: PipelineStep[]
}

// Opciones de simbología soportadas por pyzbar/zxing-cpp (referencia).
export const SYMBOLOGIES = [
  'CODE128',
  'CODE39',
  'EAN13',
  'EAN8',
  'QRCODE',
  'DATAMATRIX',
  'PDF417',
  'AZTEC',
  'ITF',
  'UPCA',
  'UPCE',
] as const
```

- [ ] **Step 2: Crear el wrapper de API**

`web/frontend/src/api/pipeline.ts`:

```typescript
import { api } from '@/api/client'
import type { PipelineResponse, PipelineStep } from '@/api/types-pipeline'

export const pipelineApi = {
  get: (appId: number) =>
    api.get<PipelineResponse>(`/applications/${appId}/pipeline`),

  put: (appId: number, steps: PipelineStep[]) =>
    api.put<PipelineResponse>(`/applications/${appId}/pipeline`, { steps }),
}
```

- [ ] **Step 3: Verificar tipado**

```bash
cd web/frontend && npx vue-tsc --noEmit && cd -
```

- [ ] **Step 4: Commit**

```bash
git add web/frontend/src/api/types-pipeline.ts web/frontend/src/api/pipeline.ts
git commit -m "feat(web-frontend): tipos y API wrapper de pipeline"
```

---

## Task 8 — Frontend: setup de vitest + store con tests

**Files:**
- Create: `web/frontend/vitest.config.ts`
- Create: `web/frontend/src/stores/pipeline.ts`
- Create: `web/frontend/tests/stores/pipeline.store.test.ts`
- Modify: `web/frontend/package.json` (script `test`)

- [ ] **Step 1: Crear config de vitest**

`web/frontend/vitest.config.ts`:

```typescript
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
  },
})
```

- [ ] **Step 2: Añadir script `test` en `package.json`**

Modifica `web/frontend/package.json`, en `"scripts"` añade:

```json
    "test": "vitest run",
    "test:watch": "vitest"
```

- [ ] **Step 3: Escribir los tests del store (failing)**

`web/frontend/tests/stores/pipeline.store.test.ts`:

```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { usePipelineStore } from '@/stores/pipeline'
import type { BarcodeStep } from '@/api/types-pipeline'

vi.mock('@/api/pipeline', () => ({
  pipelineApi: {
    get: vi.fn(),
    put: vi.fn(),
  },
}))

import { pipelineApi } from '@/api/pipeline'

const barcodeDefaults: BarcodeStep = {
  id: 'bc-1',
  type: 'barcode',
  enabled: true,
  engine: 'motor1',
  symbologies: [],
  regex: '',
  regex_include_symbology: false,
  orientations: ['horizontal', 'vertical'],
  quality_threshold: 0,
  window: null,
}

describe('usePipelineStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('fetch popula steps y resetea error', async () => {
    vi.mocked(pipelineApi.get).mockResolvedValue({ steps: [barcodeDefaults] })
    const store = usePipelineStore()

    await store.fetch(42)

    expect(store.steps).toHaveLength(1)
    expect(store.steps[0].id).toBe('bc-1')
    expect(store.error).toBeNull()
  })

  it('addStep añade al final con id generado', () => {
    const store = usePipelineStore()
    const step = store.addStep('barcode', { engine: 'motor2' })

    expect(store.steps).toHaveLength(1)
    expect(step.id).toBeTruthy()
    expect(step.type).toBe('barcode')
    expect((step as BarcodeStep).engine).toBe('motor2')
  })

  it('updateStep modifica por id', () => {
    const store = usePipelineStore()
    store.steps = [{ ...barcodeDefaults }]

    store.updateStep('bc-1', { enabled: false, regex: 'XYZ' })

    expect(store.steps[0].enabled).toBe(false)
    expect((store.steps[0] as BarcodeStep).regex).toBe('XYZ')
  })

  it('updateStep con id inexistente no hace nada', () => {
    const store = usePipelineStore()
    store.steps = [{ ...barcodeDefaults }]

    store.updateStep('no-existe', { enabled: false })

    expect(store.steps[0].enabled).toBe(true)
  })

  it('removeStep elimina por id', () => {
    const store = usePipelineStore()
    store.steps = [
      { ...barcodeDefaults, id: 'a' },
      { ...barcodeDefaults, id: 'b' },
    ]

    store.removeStep('a')

    expect(store.steps).toHaveLength(1)
    expect(store.steps[0].id).toBe('b')
  })

  it('reorder sustituye la lista', () => {
    const store = usePipelineStore()
    const a = { ...barcodeDefaults, id: 'a' }
    const b = { ...barcodeDefaults, id: 'b' }
    store.steps = [a, b]

    store.reorder([b, a])

    expect(store.steps[0].id).toBe('b')
    expect(store.steps[1].id).toBe('a')
  })

  it('save envía los steps actuales al endpoint', async () => {
    vi.mocked(pipelineApi.put).mockResolvedValue({ steps: [barcodeDefaults] })
    const store = usePipelineStore()
    store.steps = [{ ...barcodeDefaults }]

    await store.save(42)

    expect(pipelineApi.put).toHaveBeenCalledWith(42, [barcodeDefaults])
    expect(store.saving).toBe(false)
    expect(store.error).toBeNull()
  })

  it('save guarda error si falla', async () => {
    vi.mocked(pipelineApi.put).mockRejectedValue(
      new Error('Pipeline inválido: foo')
    )
    const store = usePipelineStore()
    store.steps = [{ ...barcodeDefaults }]

    await expect(store.save(42)).rejects.toThrow('Pipeline inválido')
    expect(store.error).toContain('Pipeline inválido')
    expect(store.saving).toBe(false)
  })
})
```

- [ ] **Step 4: Ejecutar los tests (deben fallar porque no existe el store)**

```bash
cd web/frontend && npm run test && cd -
```

Expected: todos fallan con "Cannot find module '@/stores/pipeline'".

- [ ] **Step 5: Implementar el store**

`web/frontend/src/stores/pipeline.ts`:

```typescript
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { pipelineApi } from '@/api/pipeline'
import type { PipelineStep, StepType, BarcodeStep } from '@/api/types-pipeline'

function defaultsFor(type: StepType): Partial<PipelineStep> {
  if (type === 'barcode') {
    const defaults: Omit<BarcodeStep, 'id'> = {
      type: 'barcode',
      enabled: true,
      engine: 'motor1',
      symbologies: [],
      regex: '',
      regex_include_symbology: false,
      orientations: ['horizontal', 'vertical'],
      quality_threshold: 0,
      window: null,
    }
    return defaults
  }
  // Otros tipos no son editables en v1; no se construyen nuevos.
  return { type, enabled: true }
}

export const usePipelineStore = defineStore('pipeline', () => {
  const steps = ref<PipelineStep[]>([])
  const loading = ref(false)
  const saving = ref(false)
  const error = ref<string | null>(null)

  async function fetch(appId: number): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const res = await pipelineApi.get(appId)
      steps.value = res.steps
    } catch (e) {
      error.value = (e as Error).message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function save(appId: number): Promise<void> {
    saving.value = true
    error.value = null
    try {
      const res = await pipelineApi.put(appId, steps.value)
      steps.value = res.steps
    } catch (e) {
      error.value = (e as Error).message
      throw e
    } finally {
      saving.value = false
    }
  }

  function addStep(
    type: StepType,
    overrides: Partial<PipelineStep> = {},
  ): PipelineStep {
    const base = defaultsFor(type)
    const step = {
      id: crypto.randomUUID(),
      ...base,
      ...overrides,
    } as PipelineStep
    steps.value = [...steps.value, step]
    return step
  }

  function updateStep(id: string, patch: Partial<PipelineStep>): void {
    const idx = steps.value.findIndex((s) => s.id === id)
    if (idx === -1) return
    steps.value = [
      ...steps.value.slice(0, idx),
      { ...steps.value[idx], ...patch } as PipelineStep,
      ...steps.value.slice(idx + 1),
    ]
  }

  function removeStep(id: string): void {
    steps.value = steps.value.filter((s) => s.id !== id)
  }

  function reorder(newOrder: PipelineStep[]): void {
    steps.value = newOrder
  }

  return {
    steps,
    loading,
    saving,
    error,
    fetch,
    save,
    addStep,
    updateStep,
    removeStep,
    reorder,
  }
})
```

- [ ] **Step 6: Ejecutar los tests y verificar que pasan**

```bash
cd web/frontend && npm run test && cd -
```

Expected: 8 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add web/frontend/vitest.config.ts web/frontend/package.json \
  web/frontend/src/stores/pipeline.ts web/frontend/tests/stores/pipeline.store.test.ts
git commit -m "feat(web-frontend): Pinia store del pipeline + vitest setup"
```

---

## Task 9 — Frontend: router + botón "Editar pipeline" en detalle de app

**Files:**
- Modify: `web/frontend/src/router/index.ts`
- Modify: `web/frontend/src/views/applications/ApplicationDetailView.vue`

- [ ] **Step 1: Añadir la ruta**

Lee `web/frontend/src/router/index.ts` y añade esta ruta en el array de rutas, siguiendo el patrón existente:

```typescript
  {
    path: '/applications/:id/pipeline',
    name: 'pipeline-editor',
    component: () =>
      import('@/views/applications/PipelineEditorView.vue'),
    meta: { requiresAuth: true },
  },
```

- [ ] **Step 2: Crear un `PipelineEditorView.vue` mínimo para evitar error de routing**

`web/frontend/src/views/applications/PipelineEditorView.vue` (versión placeholder, se completa en Task 11):

```vue
<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const appId = computed(() => Number(route.params.id))
</script>

<template>
  <div>
    <button
      @click="router.push(`/applications/${appId}`)"
      class="text-xs text-subtext hover:text-text mb-2 inline-flex items-center gap-1 transition-colors"
    >
      ← Aplicación
    </button>
    <h1 class="text-2xl font-bold text-text">Editor de pipeline</h1>
    <p class="text-sm text-subtext mt-2">App #{{ appId }} — en construcción.</p>
  </div>
</template>
```

- [ ] **Step 3: Añadir botón en `ApplicationDetailView.vue`**

En `web/frontend/src/views/applications/ApplicationDetailView.vue`, en la sección de botones del header (líneas ~42-55), añade **antes** de "+ Nuevo lote":

```vue
        <button
          @click="router.push(`/applications/${appId}/pipeline`)"
          class="bg-white text-primary border border-primary/40 rounded-md px-4 py-2 text-[13px] font-medium hover:bg-primary hover:text-white transition-colors"
        >
          Editar pipeline
        </button>
```

- [ ] **Step 4: Verificar manualmente (si tienes el stack corriendo)**

Arranca el frontend (`cd web/frontend && npm run dev`) y navega a una aplicación. Debe aparecer el botón "Editar pipeline" y llevarte a la placeholder.

Si no tienes el stack corriendo, al menos verifica tipado:

```bash
cd web/frontend && npx vue-tsc --noEmit && cd -
```

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/router/index.ts \
  web/frontend/src/views/applications/PipelineEditorView.vue \
  web/frontend/src/views/applications/ApplicationDetailView.vue
git commit -m "feat(web-frontend): ruta /applications/:id/pipeline con placeholder"
```

---

## Task 10 — Frontend: `PipelineStepRow` + `PipelineStepList` con drag

**Files:**
- Create: `web/frontend/src/components/pipeline/PipelineStepRow.vue`
- Create: `web/frontend/src/components/pipeline/PipelineStepList.vue`

- [ ] **Step 1: Crear `PipelineStepRow.vue`**

`web/frontend/src/components/pipeline/PipelineStepRow.vue`:

```vue
<script setup lang="ts">
import type { PipelineStep, BarcodeStep } from '@/api/types-pipeline'
import { computed } from 'vue'

const props = defineProps<{ step: PipelineStep; index: number }>()
defineEmits<{ edit: []; remove: [] }>()

const typeColors: Record<string, string> = {
  barcode: 'bg-sky-500',
  image_op: 'bg-emerald-500',
  ocr: 'bg-amber-500',
  script: 'bg-violet-500',
}

const summary = computed(() => {
  const s = props.step
  if (s.type === 'barcode') {
    const bc = s as BarcodeStep
    const region = bc.window ? 'región custom' : 'página completa'
    const symbols = bc.symbologies.length ? bc.symbologies.join(',') : 'todas'
    return `${bc.engine} · ${region} · ${symbols}`
  }
  return 'Editable desde configurador de escritorio'
})
</script>

<template>
  <div
    class="flex items-center gap-2 p-2 bg-white rounded-md border border-surface-0 hover:border-primary/40 transition-colors"
    :class="{ 'opacity-50': !step.enabled }"
  >
    <span class="cursor-grab text-subtext select-none" title="Reordenar">⋮⋮</span>
    <span
      class="text-white text-[11px] px-2 py-0.5 rounded font-medium"
      :class="typeColors[step.type] || 'bg-gray-500'"
    >
      {{ step.type }}
    </span>
    <span class="flex-1 text-sm text-text truncate">{{ summary }}</span>
    <button
      @click="$emit('edit')"
      class="text-subtext hover:text-primary text-sm"
      title="Editar"
    >
      ✎
    </button>
    <button
      @click="$emit('remove')"
      class="text-subtext hover:text-danger text-sm"
      title="Eliminar"
    >
      🗑
    </button>
  </div>
</template>
```

- [ ] **Step 2: Crear `PipelineStepList.vue`**

`web/frontend/src/components/pipeline/PipelineStepList.vue`:

```vue
<script setup lang="ts">
import { VueDraggable } from 'vue-draggable-plus'
import { computed } from 'vue'
import PipelineStepRow from './PipelineStepRow.vue'
import type { PipelineStep } from '@/api/types-pipeline'

const props = defineProps<{ modelValue: PipelineStep[] }>()
const emit = defineEmits<{
  'update:modelValue': [steps: PipelineStep[]]
  'edit-step': [step: PipelineStep]
  'remove-step': [step: PipelineStep]
}>()

const list = computed({
  get: () => props.modelValue,
  set: (v: PipelineStep[]) => emit('update:modelValue', v),
})
</script>

<template>
  <div v-if="list.length === 0" class="text-center py-12 text-subtext">
    <p class="text-sm">Todavía no hay ningún step en el pipeline.</p>
    <p class="text-xs mt-1">
      Pulsa «+ Añadir step» para empezar.
    </p>
  </div>

  <VueDraggable
    v-else
    v-model="list"
    handle=".cursor-grab"
    :animation="150"
    class="flex flex-col gap-1.5"
  >
    <PipelineStepRow
      v-for="(step, idx) in list"
      :key="step.id"
      :step="step"
      :index="idx"
      @edit="emit('edit-step', step)"
      @remove="emit('remove-step', step)"
    />
  </VueDraggable>
</template>
```

- [ ] **Step 3: Verificar tipado**

```bash
cd web/frontend && npx vue-tsc --noEmit && cd -
```

- [ ] **Step 4: Commit**

```bash
git add web/frontend/src/components/pipeline/PipelineStepRow.vue \
  web/frontend/src/components/pipeline/PipelineStepList.vue
git commit -m "feat(web-frontend): PipelineStepList con drag-to-reorder"
```

---

## Task 11 — Frontend: `BarcodeStepForm` + `PipelineStepDrawer`

**Files:**
- Create: `web/frontend/src/components/pipeline/forms/BarcodeStepForm.vue`
- Create: `web/frontend/src/components/pipeline/PipelineStepDrawer.vue`

- [ ] **Step 1: Crear `BarcodeStepForm.vue`**

Patrón **fully-controlled**: no mantiene estado local; recibe `modelValue`, emite `update:modelValue` con el step completo actualizado. Así evita el bucle de doble watcher.

`web/frontend/src/components/pipeline/forms/BarcodeStepForm.vue`:

```vue
<script setup lang="ts">
import { computed, watch } from 'vue'
import type { BarcodeStep } from '@/api/types-pipeline'
import { SYMBOLOGIES } from '@/api/types-pipeline'

const props = defineProps<{ modelValue: BarcodeStep }>()
const emit = defineEmits<{
  'update:modelValue': [step: BarcodeStep]
  'validity-change': [valid: boolean]
}>()

function patch(update: Partial<BarcodeStep>): void {
  emit('update:modelValue', { ...props.modelValue, ...update })
}

const regexError = computed(() => {
  if (!props.modelValue.regex) return ''
  try {
    new RegExp(props.modelValue.regex)
    return ''
  } catch (e) {
    return (e as Error).message
  }
})

watch(regexError, (err) => emit('validity-change', !err), { immediate: true })

function toggleSymbology(sym: string) {
  const list = props.modelValue.symbologies
  const next = list.includes(sym)
    ? list.filter((s) => s !== sym)
    : [...list, sym]
  patch({ symbologies: next })
}

function toggleOrientation(ori: string) {
  const list = props.modelValue.orientations
  const next = list.includes(ori)
    ? list.filter((o) => o !== ori)
    : [...list, ori]
  patch({ orientations: next })
}

function toggleCustomRegion(v: boolean) {
  patch({ window: v ? [0, 0, 100, 100] : null })
}

function updateWindowAt(idx: number, value: number) {
  const w = props.modelValue.window!
  const next: [number, number, number, number] = [w[0], w[1], w[2], w[3]]
  next[idx] = value
  patch({ window: next })
}
</script>

<template>
  <div class="space-y-4">
    <!-- Enabled -->
    <div class="flex items-center gap-2">
      <input
        id="enabled"
        type="checkbox"
        :checked="modelValue.enabled"
        @change="(e) => patch({ enabled: (e.target as HTMLInputElement).checked })"
      />
      <label for="enabled" class="text-sm">Activo</label>
    </div>

    <!-- Engine -->
    <div>
      <label class="block text-[11px] uppercase tracking-wide text-subtext font-medium mb-1">Motor</label>
      <select
        :value="modelValue.engine"
        @change="(e) => patch({ engine: (e.target as HTMLSelectElement).value as 'motor1' | 'motor2' })"
        class="w-full border rounded-md px-2 py-1.5 text-sm"
      >
        <option value="motor1">Motor 1 (pyzbar)</option>
        <option value="motor2">Motor 2 (zxing-cpp)</option>
      </select>
    </div>

    <!-- Symbologies -->
    <div>
      <label class="block text-[11px] uppercase tracking-wide text-subtext font-medium mb-1">
        Simbologías <span class="text-subtext normal-case">(vacío = todas)</span>
      </label>
      <div class="grid grid-cols-3 gap-1.5">
        <label
          v-for="sym in SYMBOLOGIES"
          :key="sym"
          class="flex items-center gap-1.5 text-xs cursor-pointer"
        >
          <input
            type="checkbox"
            :checked="modelValue.symbologies.includes(sym)"
            @change="toggleSymbology(sym)"
          />
          {{ sym }}
        </label>
      </div>
    </div>

    <!-- Regex -->
    <div>
      <label class="block text-[11px] uppercase tracking-wide text-subtext font-medium mb-1">
        Regex <span class="text-subtext normal-case">(vacío = sin filtro)</span>
      </label>
      <input
        :value="modelValue.regex"
        @input="(e) => patch({ regex: (e.target as HTMLInputElement).value })"
        type="text"
        class="w-full border rounded-md px-2 py-1.5 text-sm font-mono"
        :class="{ 'border-danger': regexError }"
        placeholder="^DOC-\d+$"
      />
      <p v-if="regexError" class="text-[11px] text-danger mt-1">
        Regex inválida: {{ regexError }}
      </p>
      <div class="flex items-center gap-2 mt-2">
        <input
          id="regex_inc_sym"
          type="checkbox"
          :checked="modelValue.regex_include_symbology"
          @change="(e) => patch({ regex_include_symbology: (e.target as HTMLInputElement).checked })"
        />
        <label for="regex_inc_sym" class="text-xs">
          Incluir simbología en el match
        </label>
      </div>
    </div>

    <!-- Orientations -->
    <div>
      <label class="block text-[11px] uppercase tracking-wide text-subtext font-medium mb-1">Orientaciones</label>
      <div class="flex gap-4">
        <label class="flex items-center gap-1.5 text-sm cursor-pointer">
          <input
            type="checkbox"
            :checked="modelValue.orientations.includes('horizontal')"
            @change="toggleOrientation('horizontal')"
          />
          Horizontal
        </label>
        <label class="flex items-center gap-1.5 text-sm cursor-pointer">
          <input
            type="checkbox"
            :checked="modelValue.orientations.includes('vertical')"
            @change="toggleOrientation('vertical')"
          />
          Vertical
        </label>
      </div>
    </div>

    <!-- Quality threshold -->
    <div>
      <label class="block text-[11px] uppercase tracking-wide text-subtext font-medium mb-1">
        Umbral de calidad (0.0 - 1.0)
      </label>
      <input
        :value="modelValue.quality_threshold"
        @input="(e) => patch({ quality_threshold: Number((e.target as HTMLInputElement).value) })"
        type="number"
        min="0"
        max="1"
        step="0.01"
        class="w-full border rounded-md px-2 py-1.5 text-sm"
      />
    </div>

    <!-- Region -->
    <div>
      <label class="block text-[11px] uppercase tracking-wide text-subtext font-medium mb-1">Región</label>
      <div class="flex items-center gap-2 mb-2">
        <input
          id="custom_region"
          type="checkbox"
          :checked="modelValue.window !== null"
          @change="(e) => toggleCustomRegion((e.target as HTMLInputElement).checked)"
        />
        <label for="custom_region" class="text-sm">
          Usar región personalizada (en píxeles)
        </label>
      </div>
      <div v-if="modelValue.window" class="grid grid-cols-4 gap-2">
        <div v-for="(label, idx) in ['x', 'y', 'w', 'h']" :key="label">
          <label class="text-[11px] text-subtext">{{ label }}</label>
          <input
            type="number"
            :value="modelValue.window[idx]"
            @input="(e) => updateWindowAt(idx, Number((e.target as HTMLInputElement).value))"
            class="w-full border rounded-md px-2 py-1 text-sm"
          />
        </div>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 2: Crear `PipelineStepDrawer.vue`**

`web/frontend/src/components/pipeline/PipelineStepDrawer.vue`:

```vue
<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import type { PipelineStep, BarcodeStep } from '@/api/types-pipeline'
import BarcodeStepForm from './forms/BarcodeStepForm.vue'

const props = defineProps<{
  open: boolean
  step: PipelineStep | null
  isNew: boolean
}>()

const emit = defineEmits<{
  save: [step: PipelineStep]
  cancel: []
}>()

const draft = ref<PipelineStep | null>(null)
const dirty = ref(false)
const valid = ref(true)

watch(
  () => [props.open, props.step],
  () => {
    draft.value = props.step ? { ...props.step } : null
    dirty.value = false
    valid.value = true
  },
  { immediate: true },
)

function onDraftUpdate(next: PipelineStep) {
  draft.value = next
  dirty.value = true
}

function onCancel() {
  if (dirty.value && !confirm('¿Descartar cambios?')) return
  emit('cancel')
}

function onSave() {
  if (!draft.value || !valid.value) return
  emit('save', draft.value)
}

const isEditable = computed(() => props.step?.type === 'barcode')
</script>

<template>
  <div v-if="open" class="fixed inset-0 z-40">
    <!-- Backdrop -->
    <div class="absolute inset-0 bg-black/30" @click="onCancel"></div>

    <!-- Drawer -->
    <div
      class="absolute top-0 right-0 bottom-0 w-full max-w-lg bg-white shadow-2xl flex flex-col"
    >
      <div class="p-4 border-b border-surface-0 flex items-center justify-between">
        <h2 class="text-lg font-semibold text-text">
          {{ isNew ? 'Añadir step' : 'Editar step' }}
          <span v-if="step" class="text-xs text-subtext ml-2">{{ step.type }}</span>
        </h2>
        <button @click="onCancel" class="text-subtext hover:text-text text-xl">×</button>
      </div>

      <div class="flex-1 overflow-y-auto p-4">
        <BarcodeStepForm
          v-if="isEditable && draft"
          :model-value="draft as BarcodeStep"
          @update:model-value="onDraftUpdate"
          @validity-change="(v) => (valid = v)"
        />
        <div v-else class="text-sm text-subtext bg-amber-50 border border-amber-200 rounded p-3">
          Este tipo de step (<code>{{ step?.type }}</code>) se edita desde el
          configurador de escritorio. Próximamente disponible aquí.
        </div>
      </div>

      <div class="p-4 border-t border-surface-0 flex justify-end gap-2">
        <button
          @click="onCancel"
          class="px-4 py-2 text-[13px] text-text hover:bg-surface-0 rounded-md transition-colors"
        >
          Cancelar
        </button>
        <button
          v-if="isEditable"
          @click="onSave"
          :disabled="!valid"
          class="px-4 py-2 text-[13px] bg-primary text-white rounded-md font-semibold hover:bg-primary-hover transition-colors disabled:opacity-50"
        >
          Guardar step
        </button>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 3: Verificar tipado**

```bash
cd web/frontend && npx vue-tsc --noEmit && cd -
```

- [ ] **Step 4: Commit**

```bash
git add web/frontend/src/components/pipeline/forms/BarcodeStepForm.vue \
  web/frontend/src/components/pipeline/PipelineStepDrawer.vue
git commit -m "feat(web-frontend): BarcodeStepForm + PipelineStepDrawer"
```

---

## Task 12 — Frontend: `AddStepMenu` + vista completa `PipelineEditorView`

**Files:**
- Create: `web/frontend/src/components/pipeline/AddStepMenu.vue`
- Modify: `web/frontend/src/views/applications/PipelineEditorView.vue` (sustituir placeholder)

- [ ] **Step 1: Crear `AddStepMenu.vue`**

`web/frontend/src/components/pipeline/AddStepMenu.vue`:

```vue
<script setup lang="ts">
import { ref } from 'vue'
import type { StepType } from '@/api/types-pipeline'

const emit = defineEmits<{ select: [type: StepType] }>()
const open = ref(false)

function pick(type: StepType) {
  open.value = false
  emit('select', type)
}
</script>

<template>
  <div class="relative">
    <button
      @click="open = !open"
      class="bg-primary text-white rounded-md px-4 py-2 text-[13px] font-semibold hover:bg-primary-hover transition-colors shadow-sm"
    >
      + Añadir step
    </button>

    <div
      v-if="open"
      class="absolute right-0 mt-1 w-64 bg-white rounded-md border border-surface-0 shadow-lg py-1 z-10"
    >
      <button
        @click="pick('barcode')"
        class="w-full text-left px-3 py-2 text-sm hover:bg-surface-0 flex items-center gap-2"
      >
        <span class="w-2 h-2 rounded-full bg-sky-500"></span>
        <span>Barcode</span>
        <span class="ml-auto text-xs text-subtext">v1</span>
      </button>
      <div class="border-t border-surface-0 my-1"></div>
      <div class="px-3 py-1.5 text-[11px] text-subtext uppercase tracking-wide">
        Próximamente
      </div>
      <div
        v-for="type in ['image_op', 'ocr', 'script']"
        :key="type"
        class="w-full text-left px-3 py-2 text-sm text-subtext flex items-center gap-2 cursor-not-allowed"
      >
        <span class="w-2 h-2 rounded-full bg-gray-300"></span>
        <span>{{ type }}</span>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 2: Reemplazar el placeholder de `PipelineEditorView.vue` por la versión completa**

Sustituye **todo el contenido** de `web/frontend/src/views/applications/PipelineEditorView.vue` por:

```vue
<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router'
import { usePipelineStore } from '@/stores/pipeline'
import { useApplicationsStore } from '@/stores/applications'
import PipelineStepList from '@/components/pipeline/PipelineStepList.vue'
import PipelineStepDrawer from '@/components/pipeline/PipelineStepDrawer.vue'
import AddStepMenu from '@/components/pipeline/AddStepMenu.vue'
import type { PipelineStep, StepType } from '@/api/types-pipeline'

const route = useRoute()
const router = useRouter()
const pipelineStore = usePipelineStore()
const appStore = useApplicationsStore()

const appId = computed(() => Number(route.params.id))
const drawerOpen = ref(false)
const drawerStep = ref<PipelineStep | null>(null)
const drawerIsNew = ref(false)
const toast = ref<{ kind: 'ok' | 'error'; msg: string } | null>(null)

onMounted(async () => {
  try {
    await appStore.fetchOne(appId.value)
    await pipelineStore.fetch(appId.value)
  } catch (e) {
    const err = e as Error & { status?: number }
    if (err.status === 404) {
      router.push('/applications')
    } else {
      showToast('error', `No se pudo cargar el pipeline: ${err.message}`)
    }
  }
})

onBeforeRouteLeave(() => {
  if (pipelineStore.saving) {
    return confirm('Hay cambios guardándose. ¿Salir de todos modos?')
  }
  return true
})

function showToast(kind: 'ok' | 'error', msg: string) {
  toast.value = { kind, msg }
  setTimeout(() => (toast.value = null), 3500)
}

async function persist() {
  try {
    await pipelineStore.save(appId.value)
    showToast('ok', 'Pipeline actualizado')
  } catch (e) {
    showToast('error', (e as Error).message)
  }
}

function onEditStep(step: PipelineStep) {
  drawerStep.value = { ...step }
  drawerIsNew.value = false
  drawerOpen.value = true
}

function onAddStep(type: StepType) {
  const step = pipelineStore.addStep(type)
  drawerStep.value = { ...step }
  drawerIsNew.value = true
  drawerOpen.value = true
}

async function onRemoveStep(step: PipelineStep) {
  if (!confirm(`¿Eliminar este step "${step.type}"?`)) return
  pipelineStore.removeStep(step.id)
  await persist()
}

async function onReorder(newOrder: PipelineStep[]) {
  pipelineStore.reorder(newOrder)
  await persist()
}

async function onDrawerSave(updated: PipelineStep) {
  pipelineStore.updateStep(updated.id, updated)
  drawerOpen.value = false
  await persist()
}

function onDrawerCancel() {
  // Si era un step nuevo y cancela, lo quitamos.
  if (drawerIsNew.value && drawerStep.value) {
    pipelineStore.removeStep(drawerStep.value.id)
  }
  drawerOpen.value = false
}
</script>

<template>
  <div>
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <button
          @click="router.push(`/applications/${appId}`)"
          class="text-xs text-subtext hover:text-text mb-2 inline-flex items-center gap-1 transition-colors"
        >
          ← {{ appStore.current?.name || 'Aplicación' }}
        </button>
        <h1 class="text-2xl font-bold text-text">Editor de pipeline</h1>
        <p class="text-xs text-subtext mt-1">
          {{ pipelineStore.steps.length }} step<span v-if="pipelineStore.steps.length !== 1">s</span>
          <span v-if="pipelineStore.saving" class="ml-2 text-primary">guardando…</span>
        </p>
      </div>
      <AddStepMenu @select="onAddStep" />
    </div>

    <!-- Lista -->
    <div v-if="pipelineStore.loading" class="text-center py-12 text-subtext">
      Cargando…
    </div>
    <PipelineStepList
      v-else
      :model-value="pipelineStore.steps"
      @update:model-value="onReorder"
      @edit-step="onEditStep"
      @remove-step="onRemoveStep"
    />

    <!-- Drawer -->
    <PipelineStepDrawer
      :open="drawerOpen"
      :step="drawerStep"
      :is-new="drawerIsNew"
      @save="onDrawerSave"
      @cancel="onDrawerCancel"
    />

    <!-- Toast -->
    <div
      v-if="toast"
      class="fixed bottom-4 right-4 px-4 py-2 rounded-md shadow-lg text-sm z-50"
      :class="toast.kind === 'ok'
        ? 'bg-green-500 text-white'
        : 'bg-red-500 text-white'"
    >
      {{ toast.msg }}
    </div>
  </div>
</template>
```

- [ ] **Step 3: Verificar tipado**

```bash
cd web/frontend && npx vue-tsc --noEmit && cd -
```

- [ ] **Step 4: Ejecutar tests del store para asegurar que nada se ha roto**

```bash
cd web/frontend && npm run test && cd -
```

Expected: 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/components/pipeline/AddStepMenu.vue \
  web/frontend/src/views/applications/PipelineEditorView.vue
git commit -m "feat(web-frontend): PipelineEditorView completo con drawer, drag y toasts"
```

---

## Task 13 — Validación manual end-to-end

**Files:** (sin archivos, solo verificación)

- [ ] **Step 1: Arrancar el stack completo**

En tres terminales separadas:

```bash
# Terminal 1 — Postgres local
docker start docscan-pg

# Terminal 2 — API
source .venv/bin/activate
uvicorn web.api.main:create_app --factory --reload --port 8001

# Terminal 3 — Frontend
cd web/frontend && npm run dev
```

Verifica en el log del API que no hay errores al arrancar. Navega a `http://localhost:5173`.

- [ ] **Step 2: Login con usuario de test y crear una app nueva**

- Login con `demo2@demo.com / demo12345` (o el que tengas en tu Postgres local).
- Crear una nueva aplicación "Pipeline Test v1".

- [ ] **Step 3: Probar el flujo completo del editor**

1. En la vista de la aplicación, pulsa "Editar pipeline" → debe llevarte a `/applications/:id/pipeline`.
2. La lista debe estar vacía con el mensaje "Todavía no hay ningún step…".
3. Pulsa "+ Añadir step" → "Barcode". Se abre el drawer.
4. Rellena: engine `motor1`, marca `QRCODE` en simbologías, regex `^DOC-\d+$`, umbral `0.5`.
5. Pulsa "Guardar step". Drawer cierra, fila aparece con el summary correcto, toast "Pipeline actualizado".
6. Añade un segundo BarcodeStep (engine `motor2`).
7. Prueba drag-and-drop: reordena las dos filas, debe persistir (toast).
8. Edita el primer step: cambia regex y guarda.
9. Borra un step con el botón 🗑 → confirm → desaparece + toast.
10. Refresca la página (F5): el pipeline se mantiene.

- [ ] **Step 4: Probar errores**

1. Intenta guardar un BarcodeStep con regex inválida (`[`). El botón "Guardar step" debe deshabilitarse y aparecer mensaje inline.
2. Navega a `/applications/99999/pipeline` (inexistente) → debe redirigir a `/applications` con toast o vista limpia.
3. Con DevTools abre Network, simula un `PUT` que falle (offline mode): debe mostrar toast rojo y el cambio local debe conservarse.

- [ ] **Step 5: Probar aislamiento multi-tenant**

Crea un usuario de otro tenant (o usa `colaborador@demo.com` si es del mismo tenant, que debería funcionar). Intenta acceder a la URL del pipeline de una app de otro tenant → debe devolver 404 y la UI redirigir.

- [ ] **Step 6: Probar ejecución real del pipeline**

Crea un lote en la aplicación con el BarcodeStep configurado. Sube 1-2 imágenes con código de barras. Ejecuta el pipeline. Verifica que:

- El batch se procesa sin errores.
- Los barcodes detectados se muestran en el visor.

- [ ] **Step 7: Tests completos**

Ejecuta la suite completa para asegurar cero regresiones:

```bash
pytest tests/ -v
cd web/frontend && npm run test && cd -
```

Expected: backend 955+ tests PASS (los 948 previos + 12 nuevos), frontend 8 tests PASS.

- [ ] **Step 8: Actualizar bitácora manual**

Añade una sección al final de `docs/MANUAL_TEST_WEB_MVP.md` con "Editor de pipeline v1" y los escenarios del Step 3 como checklist para regresión futura.

- [ ] **Step 9: Commit de cierre**

```bash
git add docs/MANUAL_TEST_WEB_MVP.md
git commit -m "docs: bitacora del editor de pipeline v1"
```

---

## Task 14 — Informe de progreso y merge

**Files:**
- Create: `docs/progreso_2026-04-16.md` (o la fecha en que se complete)

- [ ] **Step 1: Generar el informe de progreso**

Usa el skill `progreso-doc` para generar el informe del día. Debe incluir:

- Decisiones del brainstorming del editor de pipeline.
- Spec y plan creados.
- Implementación v1 (infraestructura + BarcodeStep).
- Tests añadidos.
- Validación manual completada.

- [ ] **Step 2: Push al remote**

```bash
git push origin feature/web
```

- [ ] **Step 3: Actualizar memoria**

Actualiza `project_web_session_next.md` para reflejar:

- v1 del editor de pipeline completado.
- Siguiente sub-proyecto pendiente: v2 (ImageOpStep).

---

## Criterios de aceptación v1

Copiados del spec para verificación final:

- [ ] Puedo navegar a `/applications/:id/pipeline` desde el detalle de la aplicación.
- [ ] Veo el pipeline actual (vacío o con steps cargados).
- [ ] Puedo añadir un `BarcodeStep` con todos sus campos y se persiste correctamente.
- [ ] Puedo editar un `BarcodeStep` existente y el cambio se refleja tras guardar.
- [ ] Puedo borrar un step con confirmación.
- [ ] Puedo reordenar los steps con drag-and-drop y el orden se persiste.
- [ ] Los errores de validación del backend se muestran claramente.
- [ ] Tests backend y frontend pasan en verde.
- [ ] Un pipeline configurado desde la web se ejecuta correctamente en un batch.
- [ ] Aislamiento multi-tenant verificado: cross-tenant devuelve 404.
