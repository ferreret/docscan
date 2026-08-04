---
name: GitHub API via curl con tokens del entorno
description: Usar curl + $GITHUB_PAT para API de GitHub (releases, assets), no buscar gh CLI ni pedir tokens
type: feedback
---

Usar siempre `curl` con `$GITHUB_PAT` o `$GITHUB_PERSONAL_ACCESS_TOKEN` para operaciones de GitHub API (crear releases, subir assets, etc.). No buscar `gh` CLI ni pedir tokens al usuario.

**Why:** Los tokens ya están en las variables de entorno del sistema. En la sesión del 26-mar se usó este método sin problemas; el 27-mar se perdió tiempo buscando `gh` y preguntando por tokens.

**How to apply:** Antes de cualquier operación GitHub API, usar directamente `curl -H "Authorization: token $GITHUB_PAT"` contra `api.github.com`.
