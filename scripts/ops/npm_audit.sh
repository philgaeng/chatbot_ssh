#!/usr/bin/env bash
set -uo pipefail

# Run `npm audit --json` for the officer UI and write the report where the ops
# dependency_scan can ingest it (source='npm'). The ops container is the Python
# image with no node, so this runs in the UI image or CI, on a shared path.
#
# Usage:
#   scripts/ops/npm_audit.sh [repo_dir]
#
# Env:
#   NPM_AUDIT_JSON (default: /var/backups/grms/npm_audit.json)
#   UI_DIR         (default: <repo>/channels/ticketing-ui)

REPO_DIR="${1:-$(pwd)}"
UI_DIR="${UI_DIR:-$REPO_DIR/channels/ticketing-ui}"
OUT="${NPM_AUDIT_JSON:-/var/backups/grms/npm_audit.json}"

mkdir -p "$(dirname "$OUT")"
if ! command -v npm >/dev/null 2>&1; then
  echo "npm not available; skipping" >&2
  exit 0
fi
if [[ ! -d "$UI_DIR" ]]; then
  echo "UI dir not found: $UI_DIR" >&2
  exit 0
fi

cd "$UI_DIR"
# npm audit exits non-zero when vulns exist; that's expected — capture JSON anyway.
npm audit --json > "$OUT" 2>/dev/null || true
echo "npm audit report written to $OUT"
