---
name: feedback_no_timeout_regex_por_hilos
description: Un timeout por hilos NO acota un regex patológico en Python; re no libera el GIL y congela el intérprete entero.
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 3a574282-e6b0-4206-b4f4-4b8af65e1b75
  modified: 2026-07-28T09:23:19.251Z
---

**No intentar acotar una expresión regular con un hilo vigilante en Python.** El
módulo `re` no libera el GIL mientras evalúa, así que un patrón con backtracking
catastrófico congela **el intérprete completo**: el hilo que vigila el plazo ni
siquiera llega a despertar de su `join(timeout)`.

**Why**: se implementó así el 2026-07-28 y colgó la suite de tests entera. Al
diagnosticarlo, ni un `timeout 25` externo del sistema operativo consiguió
rescatar el proceso — quedó inerte. El mismo razonamiento invalida cualquier
`ThreadPoolExecutor` + `future.result(timeout=...)` para código que no ceda el
GIL: el plazo vence, pero el hilo sigue atrapado para siempre (ese es justo el
bug que se arregló en `ScriptEngine._renew_executor`).

**How to apply**: usar el módulo `regex` (dependencia del proyecto desde el
2026-07-28), que comprueba el plazo desde dentro del bucle de matching y además
resiste por diseño la mayoría de patrones que hacen explotar a `re`. El helper es
`app/utils/safe_regex.py`, con criterio fail-open. Para otro código que bloquee
sin ceder el GIL, la única salida real es un proceso aparte, que sí es matable.

Relacionado: [[project_lotes_flexibarnet_ejecutados]],
[[feedback_inline_tests_can_hide_bugs]].
