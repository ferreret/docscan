---
name: next-session-resume
description: Punto de retoma para la próxima sesión de DocScan. Desde 2026-07-27 el foco es EJECUTAR las propuestas extraídas de FlexibarNET10.
metadata: 
  node_type: memory
  type: project
  modified: 2026-07-27T16:15:24.865Z
  originSessionId: 27894c49-5636-4cae-b9eb-e82cec45ee87
---

# Punto de retoma — sesión del 2026-07-28

## FOCO ACORDADO: ejecutar las propuestas de FlexibarNET10

El usuario cerró la sesión del 2026-07-27 diciendo **«mañana empezamos con las
propuestas»**. Lo primero al arrancar es **priorizar con él** qué entra, partiendo de la
tabla de 13 propuestas del informe.

**Informe completo**: `docs/propuestas_desde_flexibarnet10_2026-07-27.md`
**Contexto del análisis**: [[project_propuestas_flexibarnet10]]

## Lote 1 recomendado (lo que le propuse: una tarde, bajo riesgo)

1. **C1 — caché de scripts por contenido, no por `step.id`** (XS).
   `app/services/script_engine.py:57,85,138`. Bug latente: editar un script puede seguir
   ejecutando la versión antigua. Es el arreglo de mayor valor por minuto invertido.
2. **B9 — salto directo a página** en el contador `N / M` del visor (XS). Petición típica
   de operador en lotes grandes.
3. **C4+C5+C8 — robustez** (S): escritura atómica (temp+rename) de preferencias/perfiles;
   borrar carpetas de lote **solo tras** confirmar la BD; curar ids de paso vacíos o
   duplicados al deserializar el pipeline.

## Lote 2 (release temática, si quiere ir a por lo grande)

- **B2+B3** launcher tipo hub: icono/color por app + etiquetas derivadas de la config
  (función pura sobre `pipeline_json`/`transfer_json`) + grupos colapsables.
- **A1** separador como propiedad de `Page` (`separator_value`, migración Alembic) →
  desbloquea **A2** documento lógico + transferencia por documento.

## Pendientes de verificar antes de decidir (marcados así en el informe)

- **C9** «lo que ves es lo que se transfiere»: confirmar quién persiste al fichero el
  resultado de un `ImageOpStep` (`executor.py:105` solo propaga si hubo `replace_image`).
- **C2** ¿un `BarcodeStep` sin config hereda la del paso anterior?
- **C3** ¿hay timeout en las regex de barcode? (riesgo ReDoS)
- **A8** ¿el flag `required` de los campos de lote bloquea de verdad la transferencia?

## Estado del repo al cerrar 2026-07-27

- `main` limpia y sincronizada con origin, **v0.1.5**, **883 tests verdes** (~30 s).
- Release v0.1.5 publicada con sus 3 assets; todos los runs de CI en verde.
- Fichero basura `--db-path` sin trackear en la raíz (volvió a aparecer; borrable).

## Pendientes de campo (solo el usuario puede)

- Validar la v0.1.5 instalada con el **Canon DR-M160**: versión en «Acerca de», eventos
  nuevos del catálogo, `page.id` en scripts.
- **Email SMTP** en notificaciones: falta UI + cifrado Fernet de la contraseña (la
  estructura JSON ya lo admite sin migración).
