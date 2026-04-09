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

set -u

INPUT=$(cat)
FILE_PATH=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty')

[[ -z "$FILE_PATH" ]] && exit 0

# Extraer solo el basename para las comparaciones
BASENAME=$(basename "$FILE_PATH")

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
    jq -n --arg reason "$REASON" '{
        hookSpecificOutput: {
            hookEventName: "PreToolUse",
            permissionDecision: "deny",
            permissionDecisionReason: $reason
        }
    }'
    exit 0
fi

exit 0
