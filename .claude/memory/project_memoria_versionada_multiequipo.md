---
name: project_memoria_versionada_multiequipo
description: La memoria del proyecto se replica en .claude/memory/ del repo para trabajar desde varios PCs; hay que resincronizarla a mano al cerrar sesión
metadata: 
  node_type: memory
  type: project
  originSessionId: 5966e6af-a4d4-494d-a16a-3cfdda69dc92
  modified: 2026-08-04T14:22:53.222Z
---

Desde 2026-08-04 la memoria de este proyecto está **replicada dentro del repo**
en `.claude/memory/` (commit `8d71a14`), porque el usuario trabaja también desde
un PC con Windows.

**Why:** la memoria nativa vive en `~/.claude/projects/<slug>/memory/`, fuera del
repo, y el slug deriva de la ruta absoluta del proyecto — en Linux es
`-media-nicolas-DATA-Tecnomedia-DocScan` y en Windows sería otro. Sin la copia
versionada, el equipo nuevo arranca sin ningún histórico.

**How to apply:**
- Al cerrar una sesión en la que se haya escrito o modificado memoria,
  resincronizar: `cp ~/.claude/projects/<slug>/memory/*.md .claude/memory/` y
  commitear junto con el resto. **No se actualiza sola.**
- **El repo es público**: antes de commitear esa carpeta, barrer credenciales
  con `grep -rniE "password|secret|token|api[_-]?key|\$2b\$" .claude/memory/`.
  En el volcado inicial se redactaron las contraseñas de la BD docker del
  proyecto web archivado (ver [[project_bd_docker_estado]]).
- `CLAUDE.md` ya apunta a `.claude/memory/MEMORY.md` como primera lectura de
  sesión.

En la misma tanda se hizo portable el resto del tooling: los hooks toleran la
ausencia de `jq` (Git Bash no lo trae) y entienden rutas con `\`; `.mcp.json`
usa `${CLAUDE_PROJECT_DIR:-.}` y admite `DOCSCAN_DB_PATH`. Detalle en la sección
«On Windows» de `CLAUDE.md`.
