---
name: Acceso a GitHub con gh CLI
description: Usar gh CLI (autenticado) para la API de GitHub; el $GITHUB_PAT está caducado
type: feedback
---

Usar **`gh`** para todo lo de GitHub: releases, assets, logs de CI (`gh run view
--log-failed`), clonar repos privados como `Tecnomedia/FlexibarNET10` y llamadas con
`gh api`. Está autenticado como `ferreret` en el PC Linux nuevo (minis-nick-linux,
comprobado el 2026-10-26) y ya lo estaba en el anterior.

**Why:** En marzo se usaba `curl` con `$GITHUB_PAT`. Desde julio de 2026 ese token
devuelve 401 (caducado), y esta entrada contradecía a la de «Herramientas de
diagnóstico» del índice.

**How to apply:** `gh` primero. No pedir tokens al usuario. Usar `$GITHUB_PAT` solo si
`gh auth status` falla y el token responde.
