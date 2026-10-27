---
name: next-session-resume
description: "Punto de retoma para la próxima sesión de DocScan. Tras el 2026-10-27, v0.1.8 publicada con el lote 6 (separadores + Apps del Arnau)."
metadata:
  node_type: memory
  type: project
  originSessionId: 3a621b7a-a295-426c-a170-73582379252a
  modified: 2026-10-27T09:52:10.312Z
---

# Punto de retoma — tras la sesión del 2026-10-27

## Estado

- `main` = **v0.1.8** publicada el 2026-10-27 (commit `0ba7fbb`, tag `v0.1.8`; binario
  Linux validado en local contra copia de BD real: migra b4e2a7c9d1f3 → f3a8c1d72b95 con
  recuentos intactos). La v0.1.7 (merge `7a002c9` del PR #2) fue la anterior. Las ramas `docs/paridad-flexibarnet10`,
  `fix/lote3-nada-falla-en-silencio` y `feat/rediseno-ui` están subsumidas en main
  (borrables).
- **Lote 6 mergeado en `main`** el 2026-10-27 (PR #3, merge `985bcad`), tras la
  pasada manual de Nicolás con `~/DocScanArnau/arrancar.sh` (todo OK, incluido VS Code
  para el script de nombre). Incluye separadores + Apps de archivo del Arnau, el
  Configurador revisado frente a Flexibar y los PR #4 (grupos en el launcher) y #5
  (Configurador al estilo Flexibar). **1240 tests verdes en main.** Publicado en v0.1.8. Ramas `feat/lote6-separadores` y las de #4/#5 borrables.
- `.mcp.json`: el servidor sqlite recibía `--db-path` como ruta y creaba un fichero
  vacío con ese nombre en la raíz del repo; arreglado (7991c0c). Si vuelve a aparecer,
  es otra cosa.

## Siguiente (en orden)

1. Probar las Apps del Arnau con escáner real (DR-M160) y escaneos de verdad.
2. Familia eCAP del Arnau (04, 08): secretos en scripts + ODBC contra BD simulada.
3. Pendientes de la revisión de código (anteriores al lote 6): eventos que no compilan
   se saltan en silencio (viola la regla de lote 3), `on_transfer_validate` corre en el
   hilo de UI sin timeout, el reproceso duplica barcodes en BD, Ctrl+P/F9 pisan un
   RecognitionWorker vivo y los resultados se asocian por page_index y no por id.
4. Lote 4 (incluye rollback D3, que además evita duplicados al reintentar con
   «Fusionar») y lote 5.
5. Resto del lote 6: `{pagefield:}`, arrastrar miniaturas, cabeceras de documento.

## Pendientes de campo (solo el usuario)

- Validar la v0.1.8 instalada (Acerca de, actualizador desde v0.1.7).
- Escáner físico en Ubuntu.
