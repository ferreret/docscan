---
name: batch.lock descartado
description: No implementar batch.lock (BAT-03) — foco en mono-estacion, no multi-puesto
type: feedback
---

batch.lock (BAT-03) del REQUIREMENTS.md descartado.

**Why:** El proyecto se focaliza en mono-estacion. No hay acceso concurrente a lotes desde multiples puestos.

**How to apply:** No proponer lock files ni modo supervisor para liberar locks. Simplifica el modelo de lotes.
