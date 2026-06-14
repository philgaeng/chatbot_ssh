#!/usr/bin/env bash
# Replace prod Postgres (public + ticketing + keycloak) from AWS staging, then drop mock demo rows.
#
# Requires: VPN to prod, SSH key to prod (PROD_SSH_KEY in env.local), AWS key (~/.ssh/pg_rasa_train.pem).
# Safety:    make prod-sync-db-from-aws CONFIRM=1
#
# Does NOT copy Redis. Uploads volume is synced from AWS backend /app/uploads.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

_get_env() {
  grep -E "^${1}=" env.local 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'"
}

AWS_USER="${AWS_SYNC_USER:-ubuntu}"
AWS_HOST="${AWS_SYNC_HOST:-52.76.171.73}"
AWS_DIR="${AWS_SYNC_DIR:-/home/ubuntu/nepal_chatbot}"
AWS_KEY="${AWS_SYNC_KEY:-$HOME/.ssh/pg_rasa_train.pem}"

PROD_USER="${PROD_SYNC_USER:-$(_get_env PROD_SERVER_USER)}"
PROD_HOST="${PROD_SYNC_HOST:-$(_get_env PROD_HOST)}"
PROD_DIR="${PROD_SYNC_DIR:-$(_get_env PROD_REMOTE_DIR)}"
PROD_KEY="${PROD_SYNC_KEY:-$(_get_env PROD_SSH_KEY)}"

PROD_USER="${PROD_USER:-administrator}"
PROD_DIR="${PROD_DIR:-/home/${PROD_USER}/nepal_chatbot}"

if [[ -z "${PROD_HOST:-}" ]]; then
  echo "PROD_HOST is not set (env.local PROD_HOST or PROD_SYNC_HOST)." >&2
  exit 1
fi
if [[ ! -f "$AWS_KEY" ]]; then
  echo "AWS SSH key not found: $AWS_KEY" >&2
  exit 1
fi
if [[ -n "$PROD_KEY" && ! -f "$PROD_KEY" ]]; then
  echo "Prod SSH key not found: $PROD_KEY" >&2
  exit 1
fi

AWS_SSH=(ssh -i "$AWS_KEY" -o ConnectTimeout=30 -o StrictHostKeyChecking=accept-new "${AWS_USER}@${AWS_HOST}")
PROD_SSH=(ssh)
if [[ -n "$PROD_KEY" ]]; then
  PROD_SSH+=(-i "$PROD_KEY")
fi
PROD_SSH+=(-o ConnectTimeout=30 -o StrictHostKeyChecking=accept-new "${PROD_USER}@${PROD_HOST}")

COMPOSE=(docker compose --env-file env.local
  -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml
  --profile auth)

echo "════════════════════════════════════════════════════════════════"
echo " AWS → prod DB sync (REPLACE)"
echo "   Source: ${AWS_USER}@${AWS_HOST}:${AWS_DIR}"
echo "   Target: ${PROD_USER}@${PROD_HOST}:${PROD_DIR}"
echo "   Schemas: public, ticketing, keycloak (+ uploads volume)"
echo "   Excludes mock rows: GRV-2025-* / CPL-2025-* after restore"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "Prod stack will be stopped briefly. Requires identical DB_ENCRYPTION_KEY on both hosts."
echo ""

DROP_SQL="
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = current_database()
  AND pid <> pg_backend_pid();
DROP SCHEMA IF EXISTS keycloak CASCADE;
DROP SCHEMA IF EXISTS ticketing CASCADE;
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO public;
GRANT ALL ON SCHEMA public TO \"user\";
"

echo "[1/6] Stop prod application containers (keep db)..."
"${PROD_SSH[@]}" "cd $(printf '%q' "$PROD_DIR") && $(printf '%s ' "${COMPOSE[@]}") stop \
  backend orchestrator celery_default celery_llm celery_file grm_celery grm_celery_beat \
  ticketing_api ticketing_api_auth grm_ui grm_ui_auth keycloak nginx 2>/dev/null || true"

echo "[2/6] Ensure prod Postgres is up..."
"${PROD_SSH[@]}" "cd $(printf '%q' "$PROD_DIR") && $(printf '%s ' "${COMPOSE[@]}") up -d db"
sleep 3

echo "[3/6] Drop prod schemas (public, ticketing, keycloak)..."
"${PROD_SSH[@]}" "cd $(printf '%q' "$PROD_DIR") && $(printf '%s ' "${COMPOSE[@]}") exec -T db \
  psql -U user -d app_db -v ON_ERROR_STOP=1 -c $(printf '%q' "$DROP_SQL")"

echo "[4/6] Stream pg_dump (AWS) → pg_restore (prod)..."
"${AWS_SSH[@]}" "cd $(printf '%q' "$AWS_DIR") && $(printf '%s ' "${COMPOSE[@]}") exec -T db \
  pg_dump -U user -Fc --no-owner app_db" \
| "${PROD_SSH[@]}" "cd $(printf '%q' "$PROD_DIR") && $(printf '%s ' "${COMPOSE[@]}") exec -T db \
  pg_restore -U user -d app_db --no-owner --role=user --exit-on-error"

echo "[5/6] Remove mock demo tickets (GRV-2025-* / CPL-2025-*)..."
"${PROD_SSH[@]}" "cd $(printf '%q' "$PROD_DIR") && $(printf '%s ' "${COMPOSE[@]}") exec -T db \
  psql -U user -d app_db -v ON_ERROR_STOP=1" < "$ROOT/scripts/ops/prod_sync_remove_mock_data.sql"

echo "[6/6] Sync uploads/ volume AWS → prod..."
"${AWS_SSH[@]}" "cd $(printf '%q' "$AWS_DIR") && $(printf '%s ' "${COMPOSE[@]}") run --rm --no-deps backend \
  tar czf - -C /app/uploads ." \
| "${PROD_SSH[@]}" "cd $(printf '%q' "$PROD_DIR") && $(printf '%s ' "${COMPOSE[@]}") run --rm --no-deps backend \
  tar xzf - -C /app/uploads"

echo "Starting full prod stack..."
"${PROD_SSH[@]}" "cd $(printf '%q' "$PROD_DIR") && $(printf '%s ' "${COMPOSE[@]}") up -d"

echo ""
echo "prod-sync-db-from-aws OK"
echo "Next: verify Keycloak/OIDC URLs in prod env.local, re-send invites from prod Keycloak if needed."
