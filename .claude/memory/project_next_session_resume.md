---
name: next-session-resume
description: "Punto de retoma para la próxima sesión de DocScan. Tras el 2026-10-29: cifras de la v0.1.9 publicadas, README sin Flexibar ni clientes, ficha del portfolio en manos de Nicolás; siguiente, escáner DR-M160."
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

**Sesión del 2026-10-29 (solo docs, todo empujado)**: cifras remedidas sobre el tag v0.1.9
(1226 tests, 75 % de cobertura; `c93227d`) en README, informe y `docs/portfolio/metricas.md`;
README sin FlexibarNET10 ni clientes (`96308a6`, ver [[feedback-readme-sin-flexibar-ni-clientes]]).
La ficha del portfolio la está terminando **Nicolás directamente en el repo del portfolio**
(rama local `content/docscan-v0.1.8`: borrador `2e6e316` + mis cifras v0.1.9 `2f1eaf0`); no
tocarla desde DocScan. SANE ya comprobado: `canon_dr` habilitado, DR-M160 en `canon_dr.conf` y
en el hwdb de udev (acceso sin sudo); el escáner seguía sin conectar.

**Próxima sesión (decidido 2026-10-28, sigue vigente): conectar el Canon DR-M160 en Ubuntu** y probar
las Apps del Arnau (`~/DocScanArnau/arrancar.sh`, backend sane; hojas de
`~/DocScanArnau/paginas/` impresas). Hoy solo SANE ve la HP DeskJet por red (escl).
`main` lleva el arreglo del actualizador (PR #10, merge `44b8b9b`) sin publicar: v0.1.10
pendiente.

0. **v0.1.9 publicada 2026-10-27** (commit `4e2344d`, tag `v0.1.9`; binario Linux validado en local
   contra copia de BD real). Lleva: documentación pública al día (PR #6), autoría de Nicolás Barceló
   sin la empresa (PR #8, ver [[feedback-sin-nombre-empresa]]), bugs de scripting corregidos (PR #7),
   Pipeline Assistant retirado e inglés/catalán completos con 652 textos (PR #9). 1226 tests.
   **Pendiente**: la ficha del portfolio (la termina Nicolás en ese repo, 2026-10-29); modelo Anthropic por
   defecto del AI Mode (`claude-sonnet-4-20250514`). Las métricas de README/portfolio son de la v0.1.9
   (`docs/portfolio/metricas.md`, medidas el 2026-10-29).
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

- ~~Validar la v0.1.9 instalada~~ HECHO 2026-10-28 en Linux (AppImage aislado en `~/DocScanPrueba`): Acerca de, BD de la v0.1.8 e idiomas EN/CA OK. **El actualizador de Linux no sustituía el AppImage** (leía `sys.argv[0]` en vez de `APPIMAGE`, y `rename` tmpfs→ext4 falla) y decía «aplicada»: arreglado en PR #10 (rama `fix/actualizador-appimage`, CI verde), va en la v0.1.10. Desde ≤0.1.9 en Linux hay que actualizar a mano una vez. Ubuntu 26.04 necesita `libfuse2t64` para los AppImage. Falta probar el instalador de Windows.
- Escáner físico en Ubuntu.
