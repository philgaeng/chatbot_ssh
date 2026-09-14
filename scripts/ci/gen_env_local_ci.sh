#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
#
# QA-05 — build a **test-only** env.local for an ephemeral CI stack.
#
# `scripts/ops/gen_env_local.sh` is the real generator: `.env.shared` + `secrets.enc.env`,
# decrypted with SOPS and an age key. A CI runner has neither, and ⭐ **should not** — an e2e
# stack has no business holding production credentials. It talks to its own throwaway Postgres,
# its own Redis, and no external service.
#
# So this produces the same file shape from `.env.shared` alone, filling each `#@secret NAME`
# marker with an obviously-fake value. Same splice, same ordering, same section headers — so a
# variable added to `.env.shared` reaches the CI stack automatically, and one that is *missing*
# fails here rather than as a compose interpolation error twenty lines into a job.
#
# ⚠ **Never run this on a real host.** The values below authenticate nothing; a stack built with
# them can talk to its own containers and nothing else. That is the point.
set -euo pipefail

cd "$(dirname "$0")/../.."
[ -f .env.shared ] || { echo "gen_env_local_ci: .env.shared missing"; exit 1; }

# ⚠ **Refuses to clobber a developer's env.local.** Written after doing exactly that while
# testing this script: it replaced a working local config with fake credentials in one command,
# and the only reason it cost nothing was a backup taken seconds earlier. `env.local` is
# gitignored, so git cannot get it back for you.
if [ -f env.local ] && [ "${CI:-}" != "true" ] && [ "${1:-}" != "--force" ]; then
  echo "gen_env_local_ci: env.local already exists and CI is not set — refusing to overwrite it."
  echo "  This writes FAKE credentials and is meant for a throwaway CI stack."
  echo "  If you really want that here:  scripts/ci/gen_env_local_ci.sh --force"
  echo "  To rebuild a real one instead: make env-local"
  exit 1
fi

# Deterministic, visibly fake. Anything not listed gets a generic marker, so a NEW secret in
# .env.shared does not break the job — it just gets a placeholder, which is right for a stack
# that reaches nothing outside itself.
awk '
  BEGIN {
    v["POSTGRES_PASSWORD"]        = "ci-test-postgres-password"
    v["OPS_DB_PASSWORD"]          = "ci-test-ops-password"
    v["REDIS_PASSWORD"]           = "ci-test-redis-password"
    v["DB_ENCRYPTION_KEY"]        = "ci-test-db-encryption-key-not-a-real-key"
    v["TICKETING_SECRET_KEY"]     = "ci-test-ticketing-secret"
    v["KEYCLOAK_ADMIN_PASSWORD"]  = "ci-test-keycloak-admin"
    v["KEYCLOAK_CLIENT_SECRET"]   = "ci-test-keycloak-client"
    v["KEYCLOAK_WEBHOOK_SECRET"]  = "ci-test-keycloak-webhook"
    print "# env.local — GENERATED FOR CI BY scripts/ci/gen_env_local_ci.sh. TEST VALUES ONLY."
    print "# Every secret below is fake. This stack reaches nothing outside its own containers."
    skip = 1
  }
  skip { if ($0 ~ /^#@shared-header-end$/) skip = 0; next }
  /^#@secret / { name = $2; print name "=" (name in v ? v[name] : "ci-test-" tolower(name)); next }
  { print }
' .env.shared > env.local

# The bypass build is what the e2e suite needs (Q-07): cookie identity, no Keycloak container.
# APP_ENV=dev is what makes the runtime honour it at all — production fails closed (HR-01).
{
  echo ""
  echo "# ── QA-05: this is a test stack ──────────────────────────────────────────────"
  echo "APP_ENV=dev"
  echo "AUTH_MODE=bypass"
} >> env.local

chmod 600 env.local
echo "gen_env_local_ci: wrote env.local ($(grep -c '=' env.local) settings, all secrets fake)"
