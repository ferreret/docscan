---
name: ConditionStep y HttpRequestStep descartados
description: No implementar ConditionStep ni HttpRequestStep — son redundantes con ScriptStep + AI MODE
type: feedback
---

ConditionStep (IMG-11) y HttpRequestStep (IMG-12) del REQUIREMENTS.md han sido descartados por el usuario.

**Why:** Son azucar sintactico sobre ScriptStep. Un ScriptStep de 2-3 lineas hace lo mismo, y con AI MODE generando scripts automaticamente la barrera de "el usuario no sabe Python" desaparece. Añadirlos solo sumaria complejidad (dataclass, serializer, executor, dialogo UI, tests) sin valor real.

**How to apply:** No proponerlos nunca mas. Si aparecen en REQUIREMENTS.md, ignorarlos. Los step types validos son solo: image_op, barcode, ocr, script.
