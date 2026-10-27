---
name: next-session-resume
description: "Punto de retoma para la próxima sesión de DocScan. Desde 2026-10-27 todo está en main y publicado como v0.1.7; siguiente, validar la release y el lote 4."
metadata:
  node_type: memory
  type: project
  originSessionId: 3a621b7a-a295-426c-a170-73582379252a
  modified: 2026-10-27T07:31:23.759Z
---

# Punto de retoma — tras la sesión del 2026-10-27

## Estado

- `main` contiene todo el trabajo de desktop: paridad FlexibarNET10, lote 3 y
  rediseño visual, integrados con el PR #2 (merge `7a002c9`).
- **v0.1.7 taggeada** en `7a002c9` el 2026-10-27; `release.yml` en verde; publicados AppImage, setup.exe y SHA256SUMS.txt.
  Antes de taggear se validó en local el binario PyInstaller de Linux contra una
  copia de una BD real (migra a head sin perder filas).
- 1093 tests verdes. Las ramas `docs/paridad-flexibarnet10`,
  `fix/lote3-nada-falla-en-silencio` y `feat/rediseno-ui` quedan subsumidas en
  main (borrables).

## Siguiente (en orden, del informe `docs/progreso_2026-10-27.md`)

1. Validar la v0.1.7 instalada: «Acerca de», actualizador desde v0.1.6 (ahora falla
   cerrado sin `SHA256SUMS.txt`).
2. Escáner físico DR-M160 en Ubuntu (solo el usuario puede).
3. Ficha del portfolio con las capturas nuevas — ver [[project_ficha_portfolio]].
4. Lote 4: atascos/cancelación del escáner, rollback de transferencia parcial (D3),
   DPI reales del escáner en cada página.
5. Lote 5 (privacidad, log con PII enmascarada) y lote 6 (separadores y documento,
   `docs/diseno_separadores_documento_2026-10-26.md`).

Ver [[project_paridad_flexibarnet10]].
