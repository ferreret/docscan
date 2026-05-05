# Editor de pipeline v2 — ImageOpStep (diseño)

**Fecha:** 2026-04-20
**Rama:** `feature/web`
**Estado:** aprobado — listo para plan de implementación
**Relación con v1:** reutiliza el 100 % de la infraestructura aprobada en
`2026-04-16-pipeline-editor-web-design.md` (store Pinia, endpoints REST
`GET` / `PUT /api/applications/{id}/pipeline`, `PipelineStepList`,
`PipelineStepRow`, `PipelineStepDrawer`, `vue-draggable-plus`, validación
por `serializer.deserialize`).

## 1 · Objetivo

Permitir crear, editar, reordenar y eliminar pasos de tipo `ImageOpStep`
desde el editor web, con paridad funcional completa frente al desktop
(24 operaciones soportadas) y UX tipado — sin texto libre `k=v, k=v` como
el diálogo desktop.

**Fuera de scope:**

1. Preview del resultado de la operación (requiere endpoint nuevo, upload
   y componente dedicado — sub-proyecto independiente si se decide
   implementar).
2. Selector visual de ROI sobre una imagen (depende de preview).
3. Cualquier cambio en la ejecución del pipeline o en `IMAGE_OPS` del
   backend.

## 2 · Arquitectura general

### 2.1 Cambios de alto nivel

- **Frontend (nuevo):** un catálogo TS con las 24 operaciones y sus
  parámetros, 5 widgets genéricos de campo (`NumberField`, `EnumField`,
  `BooleanField`, `PointField`, `ColorField`), un `WindowField` para el
  ROI rectangular y un `ImageOpStepForm` que ensambla todo.
- **Frontend (modificación mínima):** habilitar la opción "Operación de
  imagen" en `AddStepMenu.vue`, añadir `defaultsFor('image_op')` en el
  store y la rama `image_op` en el `switch` del drawer, además del
  resumen compacto en `PipelineStepRow`.
- **Backend:** sin cambios. Las 24 ops ya están registradas en
  `app/services/image_pipeline.py::IMAGE_OPS` y
  `app/pipeline/serializer.py::deserialize()` ya valida `ImageOpStep`
  por su dataclass.

### 2.2 Fuente de verdad del catálogo de parámetros

El catálogo de operaciones (nombres, campos, tipos, defaults, rangos,
etiquetas en castellano) vive **solo en frontend**
(`web/frontend/src/api/image-op-catalog.ts`). Esta decisión se tomó
conscientemente:

- Los nombres y defaults de cada op ya están documentados en
  `app/services/image_pipeline.py`, que sirve como referencia para
  construir el catálogo TS.
- Añadir metadata de schema al backend (dataclasses por op, o un endpoint
  `GET /api/image-ops/schema`) requeriría tocar 24 funciones y no aporta
  valor en v2 — las 24 ops son estables, no cambian con frecuencia.
- Si en el futuro se añade una op nueva al backend, **también hay que
  añadir su entrada en el catálogo TS**. Un test de paridad
  (`image-op-catalog.test.ts`) lo detectará si se olvida (ver §9).

## 3 · Catálogo de operaciones

### 3.1 Tipos TypeScript

Fichero nuevo: `web/frontend/src/api/image-op-catalog.ts`.

```ts
export type FieldType =
  | 'int' | 'float' | 'enum' | 'bool' | 'point' | 'color';

export type Category =
  | 'geometry' | 'color' | 'cleanup'
  | 'morphology' | 'channels' | 'effects';

export interface FieldSchema {
  key: string;               // nombre del param backend: "threshold"
  type: FieldType;
  label: string;             // etiqueta en castellano
  default: unknown;
  min?: number;
  max?: number;
  step?: number;             // para float
  options?: { value: string | number; label: string }[]; // solo enum
  help?: string;             // tooltip
}

export interface OpSchema {
  name: string;              // clave backend exacta: "AutoDeskew"
  label: string;             // "Corrección automática de inclinación"
  category: Category;
  description: string;       // una frase
  fields: FieldSchema[];     // [] si la op no tiene parámetros
}

export const IMAGE_OP_CATALOG: OpSchema[] = [ /* 24 entradas */ ];

export const CATEGORY_LABELS: Record<Category, string> = {
  geometry: 'Geometría',
  color: 'Color y tono',
  cleanup: 'Limpieza',
  morphology: 'Morfología',
  channels: 'Canales',
  effects: 'Efectos',
};
```

### 3.2 Reparto de las 24 operaciones en categorías

| Categoría | Operaciones |
| --- | --- |
| **Geometría** (5) | AutoDeskew, Crop, Resize, Rotate, RotateAngle |
| **Color y tono** (5) | FxGrayscale, FxNegative, FxEqualizeIntensity, SetBrightness, SetContrast |
| **Limpieza** (6) | ConvertTo1Bpp, RemoveLines, FxDespeckle, CropWhiteBorders, CropBlackBorders, RemoveHolePunch |
| **Morfología** (2) | FxDilate, FxErode |
| **Canales** (3) | KeepChannel, RemoveChannel, ScaleChannel |
| **Efectos** (3) | FloodFill, SwapColor, SetResolution |

### 3.3 Parámetros por operación (referencia)

Extraídos literalmente de `app/services/image_pipeline.py`:

- **AutoDeskew**: sin parámetros.
- **ConvertTo1Bpp**: `threshold: int (0-255, def 128)`.
- **Crop**: `x, y, w, h: int (def 0/0/ancho/alto)`.
- **CropWhiteBorders / CropBlackBorders**: `margin: int (def 5)`.
- **Resize**: `scale: float (opc.)`, `width: int (opc.)`, `height: int (opc.)`.
  En el form se modela con un `EnumField` "modo" (escala vs tamaño) y
  campos condicionales; ver §5.2.
- **Rotate**: `degrees: enum (90/180/270, def 90)`.
- **RotateAngle**: `angle: float (-360..360, def 0)`.
- **SetBrightness**: `value: int (-100..100, def 0)`.
- **SetContrast**: `factor: float (0-3, def 1.0)`.
- **RemoveLines**: `direction: enum (H/V/HV, def HV)`.
- **FxDespeckle**: `kernel_size: int (impar, 1-21, def 3)`.
- **FxGrayscale / FxNegative / FxEqualizeIntensity**: sin parámetros.
- **FxDilate / FxErode**: `kernel_size: int (1-15, def 3)`,
  `iterations: int (1-10, def 1)`.
- **FloodFill**: `x, y: int (def 0)`, `color: color (def [255,255,255])`.
- **RemoveHolePunch**: `min_radius: int (def 10)`, `max_radius: int (def 30)`.
- **SetResolution**: sin parámetros útiles (placeholder en backend).
- **SwapColor**: `from: color (def [0,0,0])`, `to: color (def [255,255,255])`,
  `tolerance: int (0-50, def 10)`.
- **KeepChannel / RemoveChannel**: `channel: enum (R/G/B, def R)`.
- **ScaleChannel**: `channel: enum (R/G/B, def R)`, `factor: float (0-2, def 1.0)`.

## 4 · Widgets genéricos de campo

Carpeta nueva: `web/frontend/src/components/pipeline/fields/`. Cada widget
es **fully-controlled**: recibe `modelValue` y emite `update:modelValue`
con el valor nuevo. No mantiene estado local — idéntico patrón al
`BarcodeStepForm` de v1.

### 4.1 Firma común

```ts
defineProps<{
  modelValue: unknown;
  label: string;
  help?: string;
  disabled?: boolean;
}>()
defineEmits<{ 'update:modelValue': [value: unknown] }>()
```

### 4.2 Lista de widgets

| Widget | Props extra | Render | Notas |
| --- | --- | --- | --- |
| `NumberField.vue` | `min`, `max`, `step`, `integer` | `<input type="number">` | Coerce a `Number`, clamp a `min`/`max` en `@input`. Si `integer`, `step=1` y `parseInt`. |
| `EnumField.vue` | `options: {value, label}[]` | `<select>` | Valor del select se mantiene como `value` del `option`, no como string. |
| `BooleanField.vue` | — | checkbox + label | — |
| `PointField.vue` | — | 2 `NumberField` (X, Y) en línea | Valor emite como `{ x: number, y: number }`. |
| `ColorField.vue` | — | 3 `NumberField` (R, G, B) + swatch de color | Valor emite como `[r, g, b]` (array de 3 enteros 0-255). El backend ya acepta tanto `tuple` como `list` (`swap_color` convierte `list → tuple`). |

### 4.3 Mapping JSON ↔ backend

- `int` / `float` / `bool` / `enum` → valor literal en `params[key]`.
- `point` → **dos claves separadas en params**: `params.x`, `params.y`
  (así lo espera `flood_fill` en `image_pipeline.py:223-226`). El widget
  emite `{x, y}` hacia el form; el form lo expande a dos claves al
  guardar.
- `color` → valor literal `[r, g, b]` en `params[key]` (donde `key` suele
  ser `color`, `from` o `to`).

## 5 · `ImageOpStepForm.vue` — ensamblador

Componente principal, fully-controlled.

### 5.1 Props / emits

```ts
defineProps<{ modelValue: ImageOpStep }>()
defineEmits<{ 'update:modelValue': [step: ImageOpStep] }>()
```

### 5.2 Layout

De arriba a abajo:

1. **Selector de operación** (`<select>` con `<optgroup>` por
   `CATEGORY_LABELS`). `<option>` muestra `op.label` (ES); el value es
   `op.name` (clave backend).
2. **Descripción** — una línea con `selectedOp.description`, solo si hay
   op elegida.
3. **Campos dinámicos** — `v-for` sobre `selectedOp.fields`, montando el
   widget que corresponde a `field.type`. Valor leído/escrito en
   `modelValue.params[field.key]` (con la excepción `point` → `{x, y}`).
4. **`WindowField`** — toggle + 4 inputs numéricos (ver §6).
5. **Toggle "Habilitado"** — mapea `modelValue.enabled` (idéntico a v1).

### 5.3 Estados

- **`op === ''`** (recién creado): solo se ve el `<select>` con placeholder
  "Elige una operación…". No se renderizan campos dinámicos ni
  `WindowField`. El botón "Guardar" del drawer queda **deshabilitado**
  (`modelValue.op === ''` es la única condición de bloqueo).
- **`op !== ''`**: se ve el form completo.

### 5.4 Transiciones

- **Cambio de `op`**: `changeOp(newOpName)` reemplaza `modelValue.params`
  por un objeto con los defaults del nuevo schema (no se arrastra nada
  del op anterior — los params son incompatibles). `window` se mantiene.
  Emite `update:modelValue` con el step completo.
- **Cambio de un field**: compone
  `{ ...modelValue, params: { ...modelValue.params, [key]: value } }` y
  emite. El drawer acumula en draft local y solo persiste al guardar.
- **Caso especial `Resize`**: tiene 3 parámetros mutuamente exclusivos
  (`scale` vs `width+height`). Se modela con un `EnumField` auxiliar
  "Modo" cuyo valor **se infiere de los params actuales**
  (`'scale'` si `params.scale` está presente, `'size'` si `params.width`
  y `params.height` están presentes, `'scale'` por defecto al crear). No
  hay estado local en el componente — el modo es un derivado puro de
  `modelValue.params`. Al cambiar de modo, se emite un `params` limpio
  con los defaults del nuevo modo (`{ scale: 1.0 }` o `{ width: 800,
  height: 600 }`), eliminando los campos del modo anterior.

## 6 · `WindowField.vue` — ROI rectangular

Campo transversal a todas las ops, hijo directo de `ImageOpStepForm`
(no está en el bucle de fields del catálogo).

### 6.1 Props / emits

```ts
defineProps<{ modelValue: [number, number, number, number] | null }>()
defineEmits<{
  'update:modelValue': [value: [number, number, number, number] | null]
}>()
```

### 6.2 UI

- Header: checkbox "Aplicar solo a una región" + label.
- **Toggle desactivado** → emite `null`, oculta los inputs.
- **Toggle activado** → grid 2×2 con `NumberField` para X, Y, Ancho,
  Alto. Valores iniciales al activar: `[0, 0, 100, 100]`. Validación:
  X ≥ 0, Y ≥ 0, Ancho ≥ 1, Alto ≥ 1.

### 6.3 Mapping JSON

- Dominio: `tuple[int, int, int, int] | null`.
- TS: `[number, number, number, number] | null`.
- El serializer del backend (`app/pipeline/serializer.py`) ya acepta
  ambos formatos de cuádrupla.

## 7 · Integración con el editor v1

Cambios mínimos en componentes existentes.

### 7.1 `AddStepMenu.vue`

Hoy solo emite `add('barcode')`. Habilitar la opción "Operación de
imagen" para que emita `add('image_op')`.

### 7.2 `stores/pipeline.ts::defaultsFor`

Añadir rama:

```ts
if (type === 'image_op') {
  return {
    id: crypto.randomUUID(),
    type: 'image_op',
    enabled: true,
    op: '',
    params: {},
    window: null,
  };
}
```

### 7.3 `PipelineStepDrawer.vue`

En el `switch` que monta el form por `step.type`, añadir:

```vue
<ImageOpStepForm v-if="draft.type === 'image_op'" v-model="draft" />
```

### 7.4 `PipelineStepRow.vue` — resumen compacto

Helper `stepSummary` devuelve el resumen para la fila. Añadir rama
`image_op`:

- `op` vacío → `"Operación de imagen (sin configurar)"`.
- `op` sin params → `"Operación: <label ES>"`.
- `op` con params → `"Operación: <label ES> · <k1>=<v1>, <k2>=<v2>"`
  (listar 2-3 params max; truncar el resto con `…`).
- Si `window` presente → sufijo `· región X,Y,W,H`.

### 7.5 Rutas / router

Sin cambios. La ruta `pipelines/:id` ya existe.

## 8 · Validación y errores

### 8.1 Validación frontend

- Los `NumberField` hacen coerción + clamp a `min`/`max` en `@input`. Si
  el usuario escribe texto no numérico, el `<input type="number">` lo
  bloquea nativamente.
- `ColorField` clampa cada canal a 0-255.
- `WindowField` valida Ancho ≥ 1 y Alto ≥ 1 cuando está activo.
- **Guardar deshabilitado** si `op === ''`. Única condición de bloqueo:
  el resto de campos tienen defaults válidos.
- **No validamos que `op` sea una clave de `IMAGE_OPS` del backend** en
  el frontend — el selector está acotado a las 24 ops del catálogo, que
  por contrato deben coincidir. El test de paridad (§9) verifica esto.

### 8.2 Validación backend (heredado de v1)

- `serializer.deserialize()` valida `ImageOpStep` por dataclass: tipo
  `image_op`, `op` string, `params` dict, `window` tupla o None.
- `PUT /api/applications/{id}/pipeline` usa `deserialize()` y devuelve
  `422` si falla.

### 8.3 Runtime

Si por algún motivo se guarda una op que no existe en `IMAGE_OPS` del
backend (caso imposible con el selector acotado), el pipeline fallará al
ejecutar la página con `KeyError` capturado y loggeado — mismo
comportamiento que el desktop.

### 8.4 Errores de red

El store `pipeline` (v1) ya muestra toast rojo al fallar un `PUT`; el
drawer no se cierra y el usuario puede reintentar. Sin cambios.

## 9 · Tests

### 9.1 Backend

**Cero tests nuevos.** La ruta `PUT /api/applications/{id}/pipeline` ya
cubre `ImageOpStep` en los tests existentes de v1
(`web/api/tests/routers/test_pipeline_router.py`). Si los 968 actuales
siguen verdes, la API sigue verde.

### 9.2 Frontend — vitest (~12-15 tests nuevos)

#### `tests/image-op-catalog.test.ts` (~3 tests)

- **Paridad con backend**: las 24 claves de `IMAGE_OP_CATALOG` coinciden
  exactamente con una lista estática de nombres esperados (la lista se
  mantiene a mano, pero es 24 entradas — se revisa si se toca). Rompe si
  alguien añade una op al backend sin añadir entrada al catálogo TS, o
  viceversa.
- **Forma de cada entrada**: todos los fields tienen `default`, los
  enums tienen `options` no vacío, los `int`/`float` con `min`/`max`
  tienen `min <= max`.
- **Categorías**: cada `category` de cada op está en `CATEGORY_LABELS`.

#### `tests/fields/*.test.ts` (~6 tests)

- `NumberField`: emite `update:modelValue` con el número correcto; clamp
  a `min`/`max`.
- `EnumField`: emite el value (no el label) al cambiar el `<select>`.
- `BooleanField`: toggle emite true/false.
- `PointField`: emite `{x, y}` al cambiar cualquiera de los dos inputs.
- `ColorField`: emite `[r, g, b]` al cambiar un canal; clamp a 0-255.
- `WindowField`: emite `null` al desactivar el toggle; emite tupla al
  activarlo; emite tupla actualizada al cambiar un campo.

#### `tests/ImageOpStepForm.test.ts` (~3-4 tests)

- Al cambiar `op`, `params` se reemplaza por los defaults del nuevo
  schema y `window` se mantiene.
- Una op sin fields (FxGrayscale) no renderiza ningún field dinámico.
- Una op con field `enum` (Rotate → degrees) renderiza `<select>` con
  las 3 opciones correctas (90/180/270).
- Con `op: ''` solo se ve el selector.

#### `tests/stores/pipeline.store.test.ts` (ampliación, ~1-2 tests)

- `defaultsFor('image_op')` devuelve el step correcto (`op: ''`,
  `params: {}`, `window: null`, `enabled: true`).

### 9.3 Total esperado al cierre

**~980-985 tests** (968 actuales + ~12-15 frontend). Sin cambios backend
= sin tests backend nuevos.

## 10 · Archivos afectados

### 10.1 Nuevos

- `web/frontend/src/api/image-op-catalog.ts`
- `web/frontend/src/components/pipeline/forms/ImageOpStepForm.vue`
- `web/frontend/src/components/pipeline/WindowField.vue`
- `web/frontend/src/components/pipeline/fields/NumberField.vue`
- `web/frontend/src/components/pipeline/fields/EnumField.vue`
- `web/frontend/src/components/pipeline/fields/BooleanField.vue`
- `web/frontend/src/components/pipeline/fields/PointField.vue`
- `web/frontend/src/components/pipeline/fields/ColorField.vue`
- `web/frontend/tests/image-op-catalog.test.ts`
- `web/frontend/tests/fields/NumberField.test.ts`
- `web/frontend/tests/fields/EnumField.test.ts`
- `web/frontend/tests/fields/BooleanField.test.ts`
- `web/frontend/tests/fields/PointField.test.ts`
- `web/frontend/tests/fields/ColorField.test.ts`
- `web/frontend/tests/fields/WindowField.test.ts`
- `web/frontend/tests/ImageOpStepForm.test.ts`

### 10.2 Modificados

- `web/frontend/src/components/pipeline/AddStepMenu.vue` — habilitar
  opción `image_op`.
- `web/frontend/src/components/pipeline/PipelineStepDrawer.vue` — rama
  `image_op` en el switch.
- `web/frontend/src/components/pipeline/PipelineStepRow.vue` — resumen
  compacto para `image_op`.
- `web/frontend/src/stores/pipeline.ts` — rama `defaultsFor('image_op')`.
- `web/frontend/tests/stores/pipeline.store.test.ts` — tests de
  `defaultsFor`.

### 10.3 Sin cambios

- Todo el backend (`web/api/**`, `app/pipeline/**`, `app/services/**`).
- `web/frontend/src/api/types-pipeline.ts`, `pipeline.ts`,
  `stores/pipeline.ts` (salvo `defaultsFor`), `PipelineStepList.vue`,
  `PipelineEditorView.vue`.

## 11 · Riesgos y mitigaciones

| Riesgo | Mitigación |
| --- | --- |
| Divergencia entre catálogo TS y `IMAGE_OPS` del backend | Test de paridad en `image-op-catalog.test.ts`. |
| Default incorrecto copiado mal al catálogo | Revisión cuidadosa leyendo `image_pipeline.py` al construir el catálogo + el QA manual al cierre prueba 2-3 ops de cada categoría. |
| Usuario espera preview y lo echa en falta | Se documenta explícitamente en el changelog del sub-proyecto que la preview está fuera de scope; si se demanda, se gestiona como sub-proyecto separado. |
| Caso `Resize` con parámetros mutuamente exclusivos | Modelado con `EnumField` auxiliar "Modo" (scale vs tamaño) cuyo valor se infiere de `params`; al cambiar se emite un `params` limpio del nuevo modo. Tests específicos para este caso. |
| Parámetros `x`/`y` de `FloodFill` como punto agrupado | `PointField` emite `{x, y}`; el form los expande a dos claves separadas `params.x` y `params.y` al guardar. |

## 12 · Criterios de éxito

1. Las 24 operaciones se pueden crear y editar desde el editor web sin
   recurrir a la aplicación desktop.
2. Los params editados se persisten correctamente
   (`GET /api/applications/{id}/pipeline` tras un `PUT` devuelve el
   mismo objeto).
3. Un pipeline con `ImageOpStep` creado desde web se ejecuta
   correctamente en runtime (verificación manual con una aplicación de
   prueba en la BD local — app id 8 "Pipeline Test v1", añadir ops y
   ejecutar un lote de prueba).
4. Los 968 tests actuales siguen verdes; se añaden ~12-15 nuevos
   (frontend).
5. El drawer mantiene el patrón de v1: draft local, guardia `dirty`,
   save/cancel explícitos.

## 13 · Próximo paso

Invocar `superpowers:writing-plans` para generar
`docs/superpowers/plans/2026-04-20-pipeline-editor-v2-imageop-plan.md`.
