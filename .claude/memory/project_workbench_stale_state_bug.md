---
name: Bug preexistente — WorkbenchView no recarga al cambiar de lote
description: Descubierto durante smoke hito 13 (2026-05-11). Navegar entre lotes deja el store con páginas del lote anterior y produce 404 al pedir /image cross-batch. F5 lo soluciona.
type: project
originSessionId: f19935ac-e52e-4b9e-879a-36b3000ed3f0
---
Bug independiente del hito 13, presente en `web/frontend/src/views/batches/WorkbenchView.vue`.

**Why:** `batchId = computed(() => Number(route.params.id))` reacciona al cambio de ruta, pero la carga inicial (`store.fetchOne`, `store.fetchPages`, `store.fetchPage` del primer page, `appStore.fetchOne`) está en un `onMounted` que sólo corre la primera vez. Vue Router reutiliza la instancia del componente al navegar entre `/batches/5` → `/batches/6` (misma ruta, param distinto) → el store mantiene `pages` y `currentPage` del lote anterior. El thumbnail panel pide `/api/batches/<nuevo>/pages/<id-del-viejo>/image` → 404 (correcto cross-batch en el backend) → thumbs y viewer vacíos.

**How to apply:** al retomar el hito 13 (smoke), avisar al operario de que recargue con F5 entre lotes. Tras cerrar el sprint D, abrir issue separada. Fix mínimo:
- Extraer la lógica del `onMounted` (líneas ~221-260) a una función `loadBatch(id)`.
- Reemplazar `onMounted(async () => { ... })` por `onMounted(() => loadBatch(batchId.value))` + `watch(batchId, loadBatch)`.
- Resetear `store.pages = []` y `store.currentPage = null` al entrar a `loadBatch` antes de cualquier fetch.

Alternativa más bruta: `<router-view :key="$route.params.id" />` en el layout fuerza re-mount. Más simple pero pierde state intencionado del workbench (composables, websocket) al navegar — descartada.

NO contaminar los commits del hito 13 con este fix; es un bug ortogonal.
