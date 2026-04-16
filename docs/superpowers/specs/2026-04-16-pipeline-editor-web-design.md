# Editor de Pipeline en web — Diseño

**Fecha:** 2026-04-16
**Estado:** Diseño aprobado (pendiente de revisión del usuario y plan de implementación)
**Scope de este documento:** v1 — infraestructura del editor + `BarcodeStep`. Los tipos `ImageOpStep`, `OcrStep` y `ScriptStep` se abordan en specs posteriores (v2, v3, v4 respectivamente).

## Motivación

La versión web de DocScan Studio (rama `feature/web`) es funcional pero **no autónoma**: un cliente nuevo se registra y crea una aplicación, pero para configurar el pipeline necesita abrir el configurador de escritorio. Esto rompe la promesa SaaS.

El objetivo del sub-proyecto es alcanzar paridad funcional con la pestaña **Pipeline** del configurador de escritorio (`app/ui/configurator/tabs/tab_pipeline.py` + `app/ui/configurator/step_dialogs/*.py`) dentro de la web. Se entrega de forma incremental por tipo de step; v1 cubre `BarcodeStep`, que es el más útil para lotes típicos y el más simple de los cuatro.

## Decisiones acumuladas del brainstorming

| Decisión | Elección | Motivo |
|---|---|---|
| Fases de entrega | Incremental por tipo de step (v1 barcode → v2 image_op → v3 ocr → v4 script) | Cada release es usable en producción; el ScriptStep (más complejo) se deja al final |
| Ubicación en el frontend | Página dedicada `/applications/:id/pipeline` | URL compartible, pantalla propia, enfoque claro |
| Representación de la lista | Rows compactas con drag-to-reorder | Escala a pipelines largos (10-20 steps) y es lo más cercano al desktop |
| Mecánica de edición | Drawer lateral derecho | Lista visible mientras se edita; espacio suficiente para futuros editores complejos (ScriptStep) |
| Flujo de guardado | Save explícito por step (drawer con draft local) + drag persistente | Predecible, permite cancelar, estándar en editores SaaS |
| Modelo de endpoint | `PUT /api/applications/:id/pipeline` con el pipeline completo | El `pipeline_json` es el agregado natural; validación con `deserialize()` existente |

## Arquitectura

```
┌────────────────────────────────────────────────────────────────┐
│  Frontend (Vue 3 + Pinia + vue-draggable-plus)                 │
│                                                                │
│  Ruta: /applications/:id/pipeline                              │
│                                                                │
│  PipelineEditorView.vue                                        │
│    ├── PipelineStepList.vue (vue-draggable-plus)               │
│    │     └── PipelineStepRow.vue (×N)                          │
│    ├── AddStepMenu.vue                                         │
│    └── PipelineStepDrawer.vue                                  │
│          └── forms/BarcodeStepForm.vue  (v1)                   │
│                                                                │
│  usePipelineStore (Pinia): steps, loading, saving, error       │
└──────────────────────┬─────────────────────────────────────────┘
                       │ HTTP
┌──────────────────────▼─────────────────────────────────────────┐
│  Backend (FastAPI)                                             │
│                                                                │
│  GET /api/applications/:id/pipeline                            │
│  PUT /api/applications/:id/pipeline                            │
│                                                                │
│  Validación: delegada a deserialize() de                       │
│  app/pipeline/serializer.py (fuente única)                     │
└────────────────────────────────────────────────────────────────┘
```

### Principio de reuso

La validación del pipeline **no se duplica** en el backend web. Se reusa `app/pipeline/serializer.deserialize()` — la misma función que usa el runner del pipeline en `web/api/tasks/pipeline_runner.py:160`. Así, un pipeline que valida en el editor es un pipeline que el ejecutor puede correr.

## Backend

### Archivos

- `web/api/routers/pipeline.py` — router nuevo con los dos endpoints.
- `web/api/schemas/pipeline.py` — schemas pydantic.
- `web/api/main.py` — registrar el router.

### Endpoints

#### `GET /api/applications/{app_id}/pipeline`

Devuelve el pipeline actual. Multi-tenancy: 404 si la app no pertenece al tenant del usuario.

**Respuesta 200:**
```json
{
  "steps": [
    { "id": "abc-123", "type": "barcode", "enabled": true, "engine": "motor1", "symbologies": [], "regex": "", "regex_include_symbology": false, "orientations": ["horizontal","vertical"], "quality_threshold": 0.0, "window": null }
  ]
}
```

**Respuesta 404:** app inexistente o de otro tenant.

#### `PUT /api/applications/{app_id}/pipeline`

Reemplaza el pipeline completo.

**Body:**
```json
{ "steps": [ {...}, {...} ] }
```

**Validación:**
1. La app pertenece al tenant del usuario (→ 404).
2. Cada step se valida construyendo su dataclass (`deserialize()`). Si falla, 422 con el mensaje original.
3. Tipos de step permitidos: los cuatro tipos, aunque v1 solo exponga `barcode` en el frontend. Esto permite que una app configurada desde desktop conserve su pipeline al pasar por la web.

**Respuesta 200:** el pipeline guardado.
**Respuesta 422:** `{"detail": "Pipeline inválido: <detalle>"}`
**Respuesta 404:** app inexistente o de otro tenant.

### Schemas

```python
# web/api/schemas/pipeline.py

from typing import Literal
from pydantic import BaseModel, ConfigDict

class StepPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    type: Literal["image_op", "barcode", "ocr", "script"]
    enabled: bool = True

class PipelineUpdate(BaseModel):
    steps: list[StepPayload]

class PipelineResponse(BaseModel):
    steps: list[dict]
```

El `extra="allow"` es intencionado: los campos específicos de cada tipo los valida `deserialize()`, que es más expresivo que el sistema de pydantic.

### Migraciones

Ninguna. `applications.pipeline_json` ya existe como `Text`.

### Tests backend

- `test_get_pipeline_ok` — app nueva devuelve 200 con `[]`.
- `test_get_pipeline_con_steps_existentes` — app con pipeline pre-cargado por fixture.
- `test_get_pipeline_otro_tenant_404`.
- `test_put_pipeline_barcode_ok` — round-trip.
- `test_put_pipeline_reemplaza_existente` — PUT con lista distinta sustituye por completo.
- `test_put_pipeline_step_sin_campos_obligatorios_422`.
- `test_put_pipeline_tipo_desconocido_422`.
- `test_put_pipeline_otro_tenant_404`.
- `test_put_pipeline_persiste_pipeline_json` — verifica `pipeline_json` en DB tras PUT.

## Frontend

### Dependencias nuevas

- `vue-draggable-plus` — fork mantenido de `vuedraggable` para Vue 3. Wrapper de SortableJS.

### Archivos

```
web/frontend/src/
├── views/applications/
│   └── PipelineEditorView.vue         [NUEVO]
├── components/pipeline/
│   ├── PipelineStepList.vue           [NUEVO]
│   ├── PipelineStepRow.vue            [NUEVO]
│   ├── PipelineStepDrawer.vue         [NUEVO]
│   ├── AddStepMenu.vue                [NUEVO]
│   └── forms/
│       └── BarcodeStepForm.vue        [NUEVO]
├── stores/
│   └── pipeline.ts                    [NUEVO]
├── api/
│   └── pipeline.ts                    [NUEVO]
├── router/
│   └── index.ts                       [MOD]
└── views/applications/
    └── ApplicationDetailView.vue      [MOD: botón "Editar pipeline"]
```

### Store

```ts
// stores/pipeline.ts

interface PipelineStep {
  id: string
  type: 'image_op' | 'barcode' | 'ocr' | 'script'
  enabled: boolean
  [key: string]: any
}

export const usePipelineStore = defineStore('pipeline', () => {
  const steps = ref<PipelineStep[]>([])
  const loading = ref(false)
  const saving = ref(false)
  const error = ref<string | null>(null)

  async function fetch(appId: number): Promise<void>
  async function save(appId: number): Promise<void>
  function addStep(type: StepType, defaults: Partial<PipelineStep>): PipelineStep
  function updateStep(id: string, patch: Partial<PipelineStep>): void
  function removeStep(id: string): void
  function reorder(newOrder: PipelineStep[]): void

  return { steps, loading, saving, error, fetch, save, addStep, updateStep, removeStep, reorder }
})
```

**Generación de IDs:** `crypto.randomUUID()` al añadir un step nuevo.

### Drawer con draft local

El drawer **no muta el store** mientras se edita. Mantiene una copia local (`draft`) del step; al "Guardar step", emite evento con el draft → el contenedor llama a `store.updateStep()` + `store.save()`.

Ventaja: cancelar descarta el draft. El store siempre refleja el estado persistido (o en vuelo hacia el servidor).

### Forms por tipo de step

Cada `*StepForm.vue` recibe `v-model="draft"` y es autónomo. En v1 solo se implementa `BarcodeStepForm.vue`:

**Campos del BarcodeStepForm:**
- `engine`: select (motor1 / motor2)
- `enabled`: checkbox
- `symbologies`: multi-select (CODE128, CODE39, QR, DATAMATRIX, ...; lista vacía = todas)
- `regex`: input de texto
- `regex_include_symbology`: checkbox
- `orientations`: checkboxes (horizontal / vertical)
- `quality_threshold`: input numérico (0.0-1.0)
- `window`: en v1, toggle "Página completa / Región personalizada" + 4 inputs numéricos (x, y, w, h) si "Región personalizada". Selección visual con rectángulo sobre imagen queda para v2+.

### Comportamiento de la UI

| Acción | Resultado |
|---|---|
| Drag-and-drop de un row | `store.reorder()` + `store.save()` inmediato. Spinner corto en el row durante el save. |
| Click en ✎ | Abre drawer con el step. |
| Click en 🗑 | `confirm()` + `store.removeStep()` + `store.save()`. |
| Click en "+ Añadir step" → Barcode | Abre drawer con BarcodeStep con valores por defecto (nuevo draft). |
| "Guardar step" en drawer | `store.addStep()` o `store.updateStep()` según el caso + `store.save()`. |
| "Cancelar" o cerrar drawer con cambios | `confirm('¿Descartar cambios?')`. |
| Navegar fuera con save en curso | `beforeRouteLeave` + `confirm`. |

### Alcance explícito v1

- Solo `BarcodeStepForm.vue` se implementa.
- El menú "+ Añadir step" muestra únicamente "Barcode" + indicador "Próximamente: image_op, ocr, script".
- Steps de otros tipos (añadidos desde desktop) **se muestran en la lista** con su icono y resumen. El usuario puede **borrarlos y reordenarlos** desde la web, pero **no editarlos**: al pulsar ✎ el drawer muestra: *"Este tipo de step se edita desde el configurador de escritorio. Próximamente disponible aquí."*

### Tests frontend (Vitest + Vue Test Utils)

- `pipeline.store.test.ts` — add/update/remove/reorder, `save()` envía payload correcto, `fetch()` popula el state, manejo de errores.
- `PipelineStepList.test.ts` — render N steps, eventos emit de edit/delete, drag reordena.
- `PipelineStepDrawer.test.ts` — draft local independiente, emit `save`/`cancel`, confirm al descartar.
- `BarcodeStepForm.test.ts` — binding v-model de todos los campos, validación de `regex` (si se especifica).
- `PipelineEditorView.test.ts` — integración: mount con app mockeada, fetch, añadir step, verificar llamada a `PUT`.

## Flujo de datos (ejemplo: añadir BarcodeStep)

1. Usuario entra a `/applications/42/pipeline`.
2. `PipelineEditorView` → `store.fetch(42)` → `GET /api/applications/42/pipeline`.
3. Usuario pulsa "+ Añadir step" → "Barcode". Drawer abierto con draft vacío.
4. Rellena `engine=motor1`, `symbologies=[QR]`, `regex=^DOC-\d+$`. Pulsa "Guardar step".
5. `store.addStep('barcode', draft)` → añade al array local.
6. `store.save(42)` → `PUT /api/applications/42/pipeline` con todos los steps.
7. Backend deserializa → valida → persiste `pipeline_json` → 200.
8. Toast "Pipeline actualizado". Drawer cerrado.

## Manejo de errores

| Escenario | UX |
|---|---|
| GET falla (red/500) | Skeleton + toast rojo con "Reintentar" |
| GET 404 | Redirect a `/applications` + toast "Aplicación no encontrada" |
| PUT 422 | Toast con mensaje del backend. Cambios locales conservados. Botón "Guardar step" se reactiva. |
| PUT 500 / red | Toast "Error de red". Cambios locales conservados. |
| Cerrar drawer con cambios | `confirm('¿Descartar cambios?')` |
| Navegar fuera con save en curso | `beforeRouteLeave` bloquea con confirm |
| Validación cliente (regex mal formada) | Mensaje inline bajo el campo; botón "Guardar step" deshabilitado mientras haya errores |

## Concurrencia

- **Editar durante batch en ejecución**: seguro. El ejecutor construye el `PipelineExecutor` al arrancar el batch (`web/api/tasks/pipeline_runner.py:158`), con los steps ya deserializados en memoria. Cambios posteriores al `pipeline_json` no afectan al batch en curso.
- **Dos admins editando a la vez**: last-write-wins. No se considera colaboración en v1 (patrón estándar para editores admin en SaaS pequeños). Si se vuelve un problema real, se añade `If-Match` con `updated_at` en v+.

## Fuera de alcance (v1)

- Formularios de `ImageOpStep`, `OcrStep`, `ScriptStep` → v2, v3, v4.
- Selección visual de `window` (rectángulo sobre imagen) → v2+.
- Preview/test de un step sobre una página de ejemplo → futuro.
- Editor de scripts con CodeMirror 6 → v4 (con `ScriptStep`).
- Clonar aplicación con pipeline completo → futuro.
- Undo/redo → futuro.

## Criterios de aceptación v1

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
