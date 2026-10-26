---
name: project_ficha_portfolio
description: Replanteamiento de la ficha de DocScan en el portfolio (decisiones del 2026-10-26); se actualiza al terminar el rediseño visual
metadata:
  node_type: memory
  type: project
  originSessionId: a3179c8e-b715-4850-bc31-8171d2fb96b8
  modified: 2026-10-26T16:45:58.923Z
---

**Dónde está.** La ficha de DocScan en el portfolio de Nicolás es
`~/Projects/Personal/portfolio/data/projects/docscan-studio.ts`, en inglés y castellano
(web: portfolio.nicolasbarcelo.dev). La captura es `public/docscan-studio.webp`.

El 2026-10-26 se decidió replantearla. Ahora está desfasada: dice 849 tests y la
v0.1.0, tiene el estado `production` y afirmaciones sin prueba («90 % de requisitos»).
La captura es de la interfaz antigua y nombra un hospital real en un volante ficticio.

**Decisiones de Nicolás:**
- **Se puede nombrar** FlexibarNET10, Tecnomedia y sus implantaciones en hospitales,
  con nombres.
- **Estado: `in-development`**: hay versiones publicadas con instaladores, pero ninguna
  instalación en producción.
- **Se actualiza al terminar el rediseño visual** ([[project_rediseno_ui]]), con
  capturas nuevas de datos ficticios **neutros**: sin nombres de hospitales reales.

**Esquema acordado.** Mismo estilo que la ficha del agente de recepción veterinaria:
cada lección con su evidencia o su número.
- **Problema:** FlexibarNET (.NET, solo Windows, SDK con licencia) en producción en
  hospitales. DocScan es su reimplementación multiplataforma en Python, con paridad
  funcional ([[project_paridad_flexibarnet10]]) e IA encima.
- **Métricas medidas en el momento de publicar:** tests, versión, versiones de Flexibar
  analizadas (19 y 6 auditorías en la segunda pasada) y bugs hallados por smoke e2e que
  los tests unitarios no veían.
- **Lecciones con prueba:**
  - La paridad con un producto en producción es una especificación contra la que
    probar.
  - Un fallo tratado como éxito: `on_transfer_advanced` lanzaba y el lote se marcaba
    como exportado.
  - El dato del papel no es de confianza: un barcode `/tmp/x` escribía fuera del
    destino.
  - Los tests unitarios pasaban mientras el worker no leía ningún barcode.
  - Documentación y asistentes de IA se desvían del código: firmas de eventos que
    fallaban sin avisar.
  - Las migraciones SQLite con recreación de tabla borraban datos: se prueban sobre una
    copia, comparando `COUNT(*)`.
- **Opcional:** un artículo en el blog relacionado (`relatedPostId`).
