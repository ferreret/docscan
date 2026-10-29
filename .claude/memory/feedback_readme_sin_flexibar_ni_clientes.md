---
name: feedback-readme-sin-flexibar-ni-clientes
description: Los README públicos de GitHub no mencionan FlexibarNET10 ni clientes como el Hospital Arnau de Vilanova
metadata:
  node_type: memory
  type: feedback
  originSessionId: 0456147b-4029-4a52-a982-16c0f1ca9ebb
  modified: 2026-10-29T15:56:34.680Z
---

Los README de GitHub (`README.md` y `README.es.md`) **no mencionan FlexibarNET10 ni
clientes** como el Hospital Arnau de Vilanova: ni «reimplementación de», ni «como en
FlexibarNET 10», ni enlaces a docs con su nombre en el título, ni rutas como
`tools/arnau_apps.py`. Decisión de Nicolás del 2026-10-29; se limpiaron 14 menciones por
README ese día.

**Why:** el README es la cara pública del proyecto y Nicolás no quiere que lo asocie a
otro producto ni a sus clientes.

**How to apply:** el comportamiento se describe sin atribuirlo («nada falla en silencio»,
no «como en FlexibarNET 10»). Antes de commitear un README,
`grep -n -i -E "flexibar|arnau|hospital|vilanova|ecap" README*.md` debe salir vacío. La
regla interna de paridad ([[project_paridad_flexibarnet10]]) sigue vigente en el código, el
CLAUDE.md y los docs internos. Solo afecta a los README: el portfolio sí puede nombrar
FlexibarNET10 y el Arnau ([[project_ficha_portfolio]]), y la empresa no se nombra en ningún
sitio ([[feedback-sin-nombre-empresa]]).
