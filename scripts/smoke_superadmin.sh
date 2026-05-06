#!/usr/bin/env bash
# Smoke test e2e del sprint superadmin (curl matrix).
#
# Requisitos:
#   - Stack docker compose arriba (api en :8001).
#   - Bootstrap previo del superadmin con:
#       docker compose exec api python -m web.api.bootstrap superadmin \
#           --email super@tecnomedia.es --password supersecret123 \
#           --display "Super TecnoMedia"
#
# Cubre 19 casos: registro cerrado, login + me, /admin/tenants y
# /admin/users (200 con superadmin, 403 con company_admin, 401 sin
# token), creación de tenant + admin, plan inválido (422), nombre
# duplicado (409), suspensión + login bloqueado (401), DELETE cascade
# y protección del tenant TecnoMedia (409), guards self-modify (409).
set -u

BASE="${DOCSCAN_API_BASE:-http://localhost:8001/api}"
SUPER_EMAIL="${SUPER_EMAIL:-super@tecnomedia.es}"
SUPER_PASSWORD="${SUPER_PASSWORD:-supersecret123}"

PASS=0
FAIL=0

check() {
  local name=$1 expected=$2 got=$3
  if [ "$got" = "$expected" ]; then
    echo "  ✓ $name (HTTP $got)"
    PASS=$((PASS+1))
  else
    echo "  ✗ $name → esperado $expected, got $got"
    FAIL=$((FAIL+1))
  fi
}

echo "=== 1) Registro público está cerrado ==="
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/auth/register" \
  -H 'Content-Type: application/json' -d '{}')
check "POST /auth/register" 404 "$code"

echo
echo "=== 2) Login del superadmin ==="
SUPER_TOKEN=$(curl -s -X POST "$BASE/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$SUPER_EMAIL\",\"password\":\"$SUPER_PASSWORD\"}" | jq -r .access_token)
if [ -n "$SUPER_TOKEN" ] && [ "$SUPER_TOKEN" != "null" ]; then
  echo "  ✓ token obtenido"
  PASS=$((PASS+1))
else
  echo "  ✗ login superadmin falló (¿hizo bootstrap?)"
  FAIL=$((FAIL+1))
  echo
  echo "Resultados: PASS=$PASS FAIL=$FAIL"
  exit 1
fi
ME=$(curl -s -H "Authorization: Bearer $SUPER_TOKEN" "$BASE/auth/me" | jq -r .role)
check "GET /auth/me .role" "superadmin" "$ME"

echo
echo "=== 3) Endpoints /admin/* requieren superadmin ==="
code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/admin/tenants")
check "GET /admin/tenants sin token" 401 "$code"
code=$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $SUPER_TOKEN" "$BASE/admin/tenants")
check "GET /admin/tenants con superadmin" 200 "$code"
code=$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $SUPER_TOKEN" "$BASE/admin/users")
check "GET /admin/users con superadmin" 200 "$code"

echo
echo "=== 4) Crear tenant + admin desde superadmin ==="
RESP=$(curl -s -X POST "$BASE/admin/tenants" \
  -H "Authorization: Bearer $SUPER_TOKEN" -H 'Content-Type: application/json' \
  -d '{"tenant_name":"SmokeAcme","plan":"basic","admin_email":"admin@smokeacme.es","admin_password":"adminpw1234","admin_display_name":"Admin Smoke"}')
NEW_TENANT_ID=$(echo "$RESP" | jq -r .id)
NEW_TENANT_NAME=$(echo "$RESP" | jq -r .name)
if [ "$NEW_TENANT_NAME" = "SmokeAcme" ]; then
  echo "  ✓ tenant creado id=$NEW_TENANT_ID name=$NEW_TENANT_NAME"
  PASS=$((PASS+1))
else
  echo "  ✗ creación falló: $RESP"
  FAIL=$((FAIL+1))
fi

echo
echo "=== 5) Plan inválido → 422 ==="
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/admin/tenants" \
  -H "Authorization: Bearer $SUPER_TOKEN" -H 'Content-Type: application/json' \
  -d '{"tenant_name":"X","plan":"INVENTADO","admin_email":"x@example.es","admin_password":"abcdefgh","admin_display_name":"X"}')
check "POST /admin/tenants con plan inválido" 422 "$code"

echo
echo "=== 6) Nombre duplicado → 409 ==="
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/admin/tenants" \
  -H "Authorization: Bearer $SUPER_TOKEN" -H 'Content-Type: application/json' \
  -d '{"tenant_name":"SmokeAcme","plan":"free","admin_email":"y@example.es","admin_password":"abcdefgh","admin_display_name":"Y"}')
check "POST /admin/tenants con nombre duplicado" 409 "$code"

echo
echo "=== 7) Login del company_admin recién creado ==="
ADMIN_TOKEN=$(curl -s -X POST "$BASE/auth/login" -H 'Content-Type: application/json' \
  -d '{"email":"admin@smokeacme.es","password":"adminpw1234"}' | jq -r .access_token)
if [ -n "$ADMIN_TOKEN" ] && [ "$ADMIN_TOKEN" != "null" ]; then
  echo "  ✓ login admin de SmokeAcme OK"
  PASS=$((PASS+1))
else
  echo "  ✗ login admin falló"
  FAIL=$((FAIL+1))
fi

echo
echo "=== 8) company_admin NO puede acceder a /admin/* ==="
code=$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $ADMIN_TOKEN" "$BASE/admin/tenants")
check "GET /admin/tenants con company_admin" 403 "$code"
code=$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $ADMIN_TOKEN" "$BASE/admin/users")
check "GET /admin/users con company_admin" 403 "$code"

echo
echo "=== 9) Detalle del tenant + lista de usuarios ==="
RESP=$(curl -s -H "Authorization: Bearer $SUPER_TOKEN" "$BASE/admin/tenants/$NEW_TENANT_ID")
N_USERS=$(echo "$RESP" | jq -r '.users | length')
if [ "$N_USERS" -ge 1 ]; then
  echo "  ✓ tenant tiene $N_USERS usuario(s)"
  PASS=$((PASS+1))
else
  echo "  ✗ users vacía"
  FAIL=$((FAIL+1))
fi

echo
echo "=== 10) Crear usuario directo en otro tenant (operator) ==="
RESP=$(curl -s -X POST "$BASE/admin/users" \
  -H "Authorization: Bearer $SUPER_TOKEN" -H 'Content-Type: application/json' \
  -d "{\"tenant_id\":$NEW_TENANT_ID,\"email\":\"op@smokeacme.es\",\"password\":\"oppw12345\",\"display_name\":\"Op Smoke\",\"role\":\"operator\"}")
NEW_USER_ID=$(echo "$RESP" | jq -r .id)
NEW_USER_ROLE=$(echo "$RESP" | jq -r .role)
if [ "$NEW_USER_ROLE" = "operator" ]; then
  echo "  ✓ usuario creado id=$NEW_USER_ID role=$NEW_USER_ROLE"
  PASS=$((PASS+1))
else
  echo "  ✗ creación falló: $RESP"
  FAIL=$((FAIL+1))
fi

echo
echo "=== 11) Self-modify del superadmin → 409 ==="
SELF_ID=$(curl -s -H "Authorization: Bearer $SUPER_TOKEN" "$BASE/auth/me" | jq -r .id)
code=$(curl -s -o /dev/null -w '%{http_code}' -X PATCH "$BASE/admin/users/$SELF_ID" \
  -H "Authorization: Bearer $SUPER_TOKEN" -H 'Content-Type: application/json' -d '{"role":"operator"}')
check "PATCH self → 409" 409 "$code"
code=$(curl -s -o /dev/null -w '%{http_code}' -X DELETE "$BASE/admin/users/$SELF_ID" \
  -H "Authorization: Bearer $SUPER_TOKEN")
check "DELETE self → 409" 409 "$code"

echo
echo "=== 12) Suspender tenant → login bloqueado ==="
curl -s -X PATCH "$BASE/admin/tenants/$NEW_TENANT_ID" \
  -H "Authorization: Bearer $SUPER_TOKEN" -H 'Content-Type: application/json' \
  -d '{"active":false}' > /dev/null
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@smokeacme.es","password":"adminpw1234"}')
check "Login en tenant suspendido" 401 "$code"
# Reactivar para limpiar estado antes del DELETE.
curl -s -X PATCH "$BASE/admin/tenants/$NEW_TENANT_ID" \
  -H "Authorization: Bearer $SUPER_TOKEN" -H 'Content-Type: application/json' \
  -d '{"active":true}' > /dev/null

echo
echo "=== 13) DELETE tenant cascade ==="
code=$(curl -s -o /dev/null -w '%{http_code}' -X DELETE "$BASE/admin/tenants/$NEW_TENANT_ID" \
  -H "Authorization: Bearer $SUPER_TOKEN")
check "DELETE /admin/tenants/$NEW_TENANT_ID" 204 "$code"
code=$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $SUPER_TOKEN" "$BASE/admin/tenants/$NEW_TENANT_ID")
check "GET tenant borrado" 404 "$code"
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@smokeacme.es","password":"adminpw1234"}')
check "Login con email de tenant borrado" 401 "$code"

echo
echo "=== 14) Borrar TecnoMedia → 409 (protegido) ==="
TECNO_ID=$(curl -s -H "Authorization: Bearer $SUPER_TOKEN" "$BASE/admin/tenants" \
  | jq -r '.items[] | select(.slug=="tecnomedia") | .id')
code=$(curl -s -o /dev/null -w '%{http_code}' -X DELETE "$BASE/admin/tenants/$TECNO_ID" \
  -H "Authorization: Bearer $SUPER_TOKEN")
check "DELETE tenant TecnoMedia" 409 "$code"

echo
echo "=== Resultados ==="
echo "  PASS: $PASS"
echo "  FAIL: $FAIL"
[ "$FAIL" -eq 0 ]
