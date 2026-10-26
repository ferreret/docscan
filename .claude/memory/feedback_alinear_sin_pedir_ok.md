---
name: feedback_alinear_sin_pedir_ok
description: "Alinear documentación, skills y guías con el código y con la lógica de Flexibar sin pedir OK punto a punto"
metadata:
  node_type: memory
  type: feedback
  originSessionId: a3179c8e-b715-4850-bc31-8171d2fb96b8
  modified: 2026-10-26T12:37:38.519Z
---

Cuando detecte guía desfasada o incoherente (CLAUDE.md, skills de `.claude/`, README,
docs-web, conocimiento de los asistentes IA, docstrings), **la corrijo entera de una vez**,
sin pedir confirmación cambio a cambio. El criterio es el código real y la lógica de
FlexibarNET10.

**Why:** El 2026-10-26, tras varios turnos de «¿alineo también X?», Nicolás dijo:
«Alinéalo todo, no me pidas cada vez, ha de seguir la misma lógica que FlexibarNET10».
Le pesa la validación punto a punto, igual que en [[feedback_no_pause_per_section]].

**How to apply:**
- Alineación documental y de guías: hacerla y reportar al final la lista de lo cambiado.
- Siguen requiriendo OK: commits y push, editar código de producto con cambio de
  comportamiento, decisiones de diseño que se aparten de Flexibar y acciones destructivas.
- No describir como existente algo que aún no está implementado. Si la lógica de
  Flexibar todavía no está en el código, la guía dice lo que funciona hoy y remite al
  diseño.

Relacionado: [[project_paridad_flexibarnet10]].
