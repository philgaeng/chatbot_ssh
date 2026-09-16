#!/usr/bin/env bash
set -euo pipefail

# Run SMTP test inside the backend container (uses container env / env.local).
#
# Usage:
#   scripts/ops/test-smtp.sh --check-only
#   scripts/ops/test-smtp.sh --send-to you@example.com

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

CONTAINER="$(docker compose ps -q backend)"
if [[ -z "$CONTAINER" ]]; then
  echo "backend container is not running" >&2
  exit 1
fi

docker cp "$ROOT/scripts/ops/test_smtp.py" "${CONTAINER}:/tmp/test_smtp.py" >/dev/null

exec docker compose exec -T backend python /tmp/test_smtp.py "$@"
