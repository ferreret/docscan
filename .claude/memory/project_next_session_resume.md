---
name: next-session-resume
description: "Punto de retoma para la próxima sesión de DocScan. Tras el 2026-10-27, v0.1.7 publicada y lote 6 (separadores + Apps del Arnau) en rama sin mergear."
metadata:
  node_type: memory
  type: project
  originSessionId: 3a621b7a-a295-426c-a170-73582379252a
  modified: 2026-10-27T09:52:10.312Z
---

# Punto de retoma — tras la sesión del 2026-10-27

## Estado

- `main` = **v0.1.7** publicada (merge `7a002c9` del PR #2; release con AppImage,
  setup.exe y SHA256SUMS.txt). Las ramas `docs/paridad-flexibarnet10`,
  `fix/lote3-nada-falla-en-silencio` y `feat/rediseno-ui` están subsumidas en main
  (borrables).
- **Rama `feat/lote6-separadores`** (solo local: el push quedó pendiente de permiso, sin PR): lote 6 S1+S2 + nombre por
  script + Apps de archivo del Arnau. 1172 tests verdes. Estado detallado en §8 de
  `docs/diseno_separadores_documento_2026-10-26.md`. Ver [[project-apps-arnau]].

## Siguiente (en orden)

1. Nicolás revisa `feat/lote6-separadores` → PR a main (el CHANGELOG ya está en
   `[Unreleased]`).
2. Probar las Apps del Arnau con escáner real (DR-M160) y escaneos de verdad.
3. Familia eCAP del Arnau (04, 08): secretos en scripts + ODBC contra BD simulada.
4. Pendientes de la revisión de código (anteriores al lote 6): eventos que no compilan
   se saltan en silencio (viola la regla de lote 3), `on_transfer_validate` corre en el
   hilo de UI sin timeout, el reproceso duplica barcodes en BD, Ctrl+P/F9 pisan un
   RecognitionWorker vivo y los resultados se asocian por page_index y no por id.
5. Lote 4 (incluye rollback D3, que además evita duplicados al reintentar con
   «Fusionar») y lote 5.
6. Resto del lote 6: `{pagefield:}`, arrastrar miniaturas, cabeceras de documento.

## Pendientes de campo (solo el usuario)

- Validar la v0.1.7 instalada (Acerca de, actualizador desde v0.1.6).
- Escáner físico en Ubuntu.
