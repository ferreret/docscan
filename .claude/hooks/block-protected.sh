#!/usr/bin/env bash
# PreToolUse hook — bloquea edits a ficheros sensibles.
#
# Ficheros protegidos:
#   - .env y .env.<entorno> (credenciales locales)
#   - secrets.enc (store Fernet-encrypted de DocScan)
#
# Permite explícitamente los templates públicos (.env.example, .env.template,
# .env.sample) que NO contienen credenciales reales y sí deben ir en el repo.
#
# Devuelve JSON con permissionDecision=deny cuando detecta un match,
# exit 0 en todos los demás casos.
#
# Portabilidad: funciona en Linux y en Windows bajo Git Bash. `jq` es opcional
# (Git Bash no lo trae); si falta, se extrae el file_path con sed. La salida
# JSON se genera con printf, sin depender de jq.

set -u

INPUT=$(cat)

# --- Extracción del file_path -------------------------------------------------
# Con jq si está disponible; si no, fallback a sed. NUNCA salir en silencio por
# falta de jq: este hook es de seguridad y debe seguir protegiendo.
if command -v jq >/dev/null 2>&1; then
    FILE_PATH=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty')
else
    # grep -o + head -1 toma la PRIMERA coincidencia, como haría jq. Con
    # `sed 's/.*"file_path"...'` el .* es greedy y cogería la última, que puede
    # venir de un old_string que contenga esa cadena.
    FILE_PATH=$(printf '%s' "$INPUT" |
        grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 |
        sed 's/.*:[[:space:]]*"\(.*\)"$/\1/')
fi

[[ -z "$FILE_PATH" ]] && exit 0

# Normalizar separadores de Windows (C:\\Users\\x\\.env) a / para que basename
# aísle correctamente el nombre del fichero.
FILE_PATH_NORM="${FILE_PATH//\\/\/}"
BASENAME=$(basename "$FILE_PATH_NORM")

REASON=""
case "$BASENAME" in
    # Templates públicos — permitidos sin bloqueo
    .env.example|.env.template|.env.sample)
        :
        ;;
    .env|.env.*)
        REASON="Fichero .env protegido (contiene credenciales). Si realmente necesitas editarlo, hazlo manualmente fuera de Claude Code."
        ;;
    secrets.enc)
        REASON="secrets.enc es un store Fernet-encrypted. No debe editarse directamente — usa las utilidades de config/secrets.py."
        ;;
esac

if [[ -n "$REASON" ]]; then
    # Los REASON son literales controlados aquí arriba (sin comillas dobles ni
    # barras invertidas), así que se pueden interpolar en el JSON sin escapar.
    printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' \
        "$REASON"
    exit 0
fi

exit 0
