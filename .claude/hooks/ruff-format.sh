#!/usr/bin/env bash
# PostToolUse hook — formatea y corrige lint de ficheros Python tras Edit/Write.
#
# Recibe por stdin el JSON del evento. Solo actúa sobre ficheros .py.
# Se ejecuta silenciosamente si ruff no está disponible o el fichero no es .py.
#
# Portabilidad: funciona en Linux y en Windows bajo Git Bash. `jq` es opcional
# (Git Bash no lo trae); si falta, se extraen los campos con sed. Busca el ruff
# del venv tanto en el layout POSIX (.venv/bin) como en el de Windows
# (.venv/Scripts).

set -u

INPUT=$(cat)

# --- Extracción de campos -----------------------------------------------------
if command -v jq >/dev/null 2>&1; then
    FILE_PATH=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty')
    CWD=$(printf '%s' "$INPUT" | jq -r '.cwd // empty')
else
    # grep -o + head -1 toma la PRIMERA coincidencia, como haría jq (con sed el
    # .* es greedy y cogería la última).
    json_field() {
        printf '%s' "$INPUT" |
            grep -o "\"$1\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" | head -1 |
            sed 's/.*:[[:space:]]*"\(.*\)"$/\1/'
    }
    FILE_PATH=$(json_field file_path)
    CWD=$(json_field cwd)
fi

# Salir limpio si no hay file_path o no es un .py
[[ -z "$FILE_PATH" ]] && exit 0
[[ "$FILE_PATH" != *.py ]] && exit 0
[[ ! -f "$FILE_PATH" ]] && exit 0

# Usar el ruff del venv del proyecto si existe, si no el del PATH.
# .venv/bin es el layout de Linux/macOS; .venv/Scripts el de Windows.
RUFF_BIN=""
if [[ -n "$CWD" && -x "$CWD/.venv/bin/ruff" ]]; then
    RUFF_BIN="$CWD/.venv/bin/ruff"
elif [[ -n "$CWD" && -x "$CWD/.venv/Scripts/ruff.exe" ]]; then
    RUFF_BIN="$CWD/.venv/Scripts/ruff.exe"
elif command -v ruff >/dev/null 2>&1; then
    RUFF_BIN="ruff"
else
    # Ruff no disponible: salir silenciosamente
    exit 0
fi

# Cambiar al cwd del proyecto para que ruff encuentre pyproject.toml/ruff.toml
[[ -n "$CWD" ]] && cd "$CWD" || true

# Ejecutar format + check --fix; redirigir stdout a stderr para que aparezca
# como feedback del hook sin interferir con el output JSON.
"$RUFF_BIN" format "$FILE_PATH" >&2 2>&1 || true
"$RUFF_BIN" check --fix "$FILE_PATH" >&2 2>&1 || true

exit 0
