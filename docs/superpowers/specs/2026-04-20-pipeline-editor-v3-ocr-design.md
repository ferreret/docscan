# Editor de pipeline v3 — OcrStep (diseño)

**Fecha:** 2026-04-20
**Rama:** `feature/web`
**Estado:** aprobado — listo para plan de implementación
**Relación con v1/v2:** reutiliza toda la infraestructura del editor de
pipeline (store, REST `GET`/`PUT`, `PipelineStepList`, `PipelineStepRow`,
`PipelineStepDrawer`, `canSave`, `WindowField`) más los widgets genéricos
introducidos en v2 (`EnumField`, `BooleanField`).

## 1 · Objetivo

Permitir crear, editar, reordenar y eliminar pasos de tipo `OcrStep`
desde el editor web, con paridad funcional completa frente al desktop y
UX tipado.

**Fuera de scope:**

1. Validar que los códigos de idioma son válidos para el motor elegido
   (cada motor usa convenciones distintas: rapidocr `ch/en`, easyocr
   `es/en/fr/…`, tesseract `spa/eng/fra/…`). El usuario es responsable
   de conocer su motor.
2. Preview del resultado OCR (mismo argumento que en v2 — requiere
   endpoint y componente dedicados).

## 2 · Arquitectura general

### 2.1 Cambios de alto nivel

- **Frontend (nuevo):** un widget `TagInput.vue` (chips con add/remove)
  y un `OcrStepForm.vue` que ensambla los 4 campos del dataclass.
- **Frontend (modificación mínima):** habilitar `ocr` en `AddStepMenu`,
  añadir `defaultsFor('ocr')` al store, rama `ocr` en el switch del
  drawer y en el summary de la fila.
- **Backend:** **cero cambios**. `OcrStep` ya está soportado por
  `app/pipeline/steps.py` y `app/pipeline/serializer.py::deserialize()`.

### 2.2 Dataclass de referencia (backend)

```python
@dataclass
class OcrStep(PipelineStep):
    type: Literal["ocr"] = "ocr"
    engine: Literal["rapidocr", "easyocr", "tesseract"] = "rapidocr"
    languages: list[str] = field(default_factory=lambda: ["es"])
    full_page: bool = True
    window: tuple[int, int, int, int] | None = None
```

## 3 · Tipo TypeScript `OcrStep`

Fichero a modificar: `web/frontend/src/api/types-pipeline.ts`.

Nueva interfaz:

```ts
export interface OcrStep extends BasePipelineStep {
  type: 'ocr'
  engine: 'rapidocr' | 'easyocr' | 'tesseract'
  languages: string[]
  full_page: boolean
  window: [number, number, number, number] | null
}
```

Actualizar union:

```ts
export type PipelineStep =
  | BarcodeStep | ImageOpStep | OcrStep | GenericStep
```

## 4 · Widget `TagInput.vue`

Fichero nuevo: `web/frontend/src/components/pipeline/fields/TagInput.vue`.

### 4.1 Props / emits

```ts
defineProps<{
  modelValue: string[]
  label: string
  placeholder?: string
  help?: string
  disabled?: boolean
}>()
defineEmits<{ 'update:modelValue': [value: string[]] }>()
```

### 4.2 Comportamiento

- Input de texto debajo del label.
- **Enter** o **,** (coma) convierten el texto en chip y lo añaden al
  array, limpiando el input. La coma se trimea y no aparece como parte
  del chip.
- Cada chip aparece como pill con texto + botón `✕` que lo elimina al
  pulsar.
- **Duplicados ignorados**: si el texto ya existe en `modelValue`, no se
  añade.
- Texto vacío tras trim también se ignora.
- Layout: chips debajo del input (wrap en flex), para que añadir uno
  nuevo no desplace los existentes.

### 4.3 Validación

No valida contra una lista de códigos válidos — los códigos dependen
del motor OCR y el backend no expone esa información. El usuario es
responsable.

## 5 · Componente `OcrStepForm.vue`

Fichero nuevo: `web/frontend/src/components/pipeline/forms/OcrStepForm.vue`.

### 5.1 Props / emits

```ts
defineProps<{ modelValue: OcrStep }>()
defineEmits<{ 'update:modelValue': [step: OcrStep] }>()
```

### 5.2 Layout (de arriba a abajo)

1. **Activo** (checkbox) — mapea `modelValue.enabled`.
2. **Motor** (`EnumField`) con opciones `rapidocr | easyocr | tesseract`
   y descripción debajo: "rapidocr es rápido y offline; easyocr tiene
   alta precisión (requiere PyTorch); tesseract es ligero y requiere
   códigos ISO 639-3 (spa/eng/fra)."
3. **Idiomas** (`TagInput`) — placeholder `"es, en, fr"`; help:
   "Los códigos varían según el motor."
4. **Página completa** (`BooleanField`) — default `true`.
5. **`WindowField`** (ROI) — se muestra siempre (aunque
   `full_page === true` lo hace ignorable por el backend, la UI permite
   configurar ambos valores para no perder el ROI al alternar el flag).

### 5.3 Transiciones

- Cambio de cualquier campo → compone el step completo
  (`{ ...modelValue, [key]: newValue }`) y emite `update:modelValue`.
- No hay caso especial tipo "Resize mode" — los campos son
  independientes.

## 6 · Integración con el editor

### 6.1 `AddStepMenu.vue`

Promover `ocr` de "Próximamente" a activo con badge v3:

```vue
<button @click="pick('ocr')" class="...">
  <span class="w-2 h-2 rounded-full bg-amber-500"></span>
  <span>OCR</span>
  <span class="ml-auto text-xs text-subtext">v3</span>
</button>
```

Dejar solo `script` en "Próximamente".

### 6.2 `stores/pipeline.ts::defaultsFor`

Añadir rama:

```ts
if (type === 'ocr') {
  const defaults: Omit<OcrStep, 'id'> = {
    type: 'ocr',
    enabled: true,
    engine: 'rapidocr',
    languages: ['es'],
    full_page: true,
    window: null,
  }
  return defaults
}
```

### 6.3 `PipelineStepDrawer.vue`

- Importar `OcrStep` y `OcrStepForm`.
- Extender `isEditable`: `barcode || image_op || ocr`.
- `canSave` para `ocr` siempre `true` (no hay campo bloqueante). El
  motor tiene default, idiomas tienen default, full_page es booleano.
- Rama `ocr` en el switch del template.

### 6.4 `PipelineStepRow.vue` — resumen compacto

Extender `summary`:

- Engine + idiomas + región/página:
  `"OCR (rapidocr) · es,en · página completa"`.
  `"OCR (tesseract) · spa · región 10,20,300,400"`.
- Si `languages` está vacío, mostrar `"sin idiomas"` (raro pero
  defensivo).

## 7 · Validación y errores

### 7.1 Frontend

- `TagInput` no valida códigos (ver §4.3).
- `canSave` del drawer siempre `true` para `ocr` — todos los campos
  tienen defaults válidos.

### 7.2 Backend

- `deserialize()` ya valida `OcrStep`. Devuelve 422 si la estructura
  falla. Heredado de v1.

## 8 · Tests

### 8.1 Backend

Cero tests nuevos.

### 8.2 Frontend — vitest (~10-12 tests nuevos)

#### `tests/fields/TagInput.test.ts` (~5 tests)

- Añadir chip con Enter.
- Añadir chip con coma.
- Eliminar chip con ✕.
- Duplicado ignorado.
- Texto vacío ignorado.

#### `tests/OcrStepForm.test.ts` (~3-4 tests)

- Renderiza los 4 campos + WindowField con defaults.
- Cambio de engine emite step con nuevo engine.
- Añadir idioma via TagInput emite step con nueva lista.
- Toggle de `full_page` emite step con booleano invertido.

#### `tests/stores/pipeline.store.test.ts` (ampliación, 1 test)

- `addStep('ocr')` devuelve step con defaults correctos.

### 8.3 Total esperado al cierre

**~54-56 tests** (44 actuales + ~10-12 nuevos). Suite frontend verde.

## 9 · Archivos afectados

### 9.1 Nuevos

- `web/frontend/src/components/pipeline/fields/TagInput.vue`
- `web/frontend/src/components/pipeline/forms/OcrStepForm.vue`
- `web/frontend/tests/fields/TagInput.test.ts`
- `web/frontend/tests/OcrStepForm.test.ts`

### 9.2 Modificados

- `web/frontend/src/api/types-pipeline.ts` — añadir `OcrStep` al union.
- `web/frontend/src/stores/pipeline.ts` — rama `ocr` en `defaultsFor`.
- `web/frontend/src/components/pipeline/AddStepMenu.vue` — activar
  opción OCR.
- `web/frontend/src/components/pipeline/PipelineStepDrawer.vue` — rama
  `ocr` y `canSave`.
- `web/frontend/src/components/pipeline/PipelineStepRow.vue` — summary
  para `ocr`.
- `web/frontend/tests/stores/pipeline.store.test.ts` — 1 test nuevo.

### 9.3 Sin cambios

- Todo el backend.
- Widgets existentes (`NumberField`, `EnumField`, `BooleanField`,
  `ColorField`, `PointField`, `WindowField`).
- `ImageOpStepForm.vue`, `BarcodeStepForm.vue`.

## 10 · Riesgos y mitigaciones

| Riesgo | Mitigación |
| --- | --- |
| Usuario pone códigos inválidos para el motor elegido | Ayuda debajo del campo Motor explicando las convenciones; el pipeline falla en runtime con log (igual que el desktop). |
| Confusión entre `full_page=true` y `window` no nulo | La UI permite configurar ambos; el backend ignora `window` cuando `full_page=true`. Documentado en el help del checkbox. |
| Chips muy largos rompen el layout | CSS con `max-width` y `text-overflow: ellipsis` en cada pill. |

## 11 · Criterios de éxito

1. Los 3 motores y cualquier combinación de idiomas pueden configurarse
   desde la web sin recurrir al desktop.
2. Un pipeline con `OcrStep` creado desde web se persiste correctamente
   (round-trip `GET` = `PUT`).
3. Los 44 tests frontend actuales siguen verdes; se añaden ~10-12
   nuevos.
4. El drawer reutiliza el mismo patrón de v1/v2 sin regresiones.
5. QA manual: crear un `OcrStep` con engine=tesseract, idiomas=[spa,
   eng], full_page=false y window custom; verificar persistencia en BD.

## 12 · Próximo paso

Invocar `superpowers:writing-plans` para generar
`docs/superpowers/plans/2026-04-20-pipeline-editor-v3-ocr-plan.md`.
