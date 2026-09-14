#!/usr/bin/env bash
set -euo pipefail

# Regenerate env.local from the two committed halves — docs/deployment/13_security.md §5.2.
#
#     .env.shared  +  secrets.enc.env  ──> env.local  (gitignored, 0600)
#
# env.local is a BUILD ARTEFACT, not a source. Ten services declare `env_file: env.local`
# (docker-compose.yml ×6, docker-compose.grm.yml ×4) and the Makefile greps it directly,
# so the file must keep existing — but nothing should be edited in it by hand.
#
# Usage:  scripts/ops/gen_env_local.sh [repo_dir]
# Env:    SOPS_AGE_KEY_FILE  (default ~/.config/sops/age/keys.txt)
#
# ⚠ This script must never print a secret VALUE. It reports names and counts only.

REPO="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
SHARED="$REPO/.env.shared"
ENC="$REPO/secrets.enc.env"
OUT="$REPO/env.local"
export SOPS_AGE_KEY_FILE="${SOPS_AGE_KEY_FILE:-$HOME/.config/sops/age/keys.txt}"

die() { echo "gen_env_local: $*" >&2; exit 1; }

command -v sops >/dev/null || die "sops not installed (see docs/deployment/18_sops_migration_handover.md §1)"
[ -f "$SHARED" ] || die "missing $SHARED"
[ -f "$ENC" ]    || die "missing $ENC"
[ -r "$SOPS_AGE_KEY_FILE" ] || die "age key not readable at $SOPS_AGE_KEY_FILE"

# Decrypt outside the repo, 0600, removed on any exit path.
TMP="$(mktemp -d)"; chmod 700 "$TMP"
trap 'rm -rf "$TMP"' EXIT INT TERM
PLAIN="$TMP/secrets"
( umask 077; sops --decrypt "$ENC" > "$PLAIN" ) || die "sops decrypt failed — is your age key a recipient of $ENC?"

# Splice: each `#@secret NAME` marker is replaced by that NAME's line from the decrypted
# file, so env.local keeps .env.shared's ordering, section headers and comments.
# Fails loudly when the two halves disagree in EITHER direction.
( umask 077; awk -v plain="$PLAIN" -v enc="secrets.enc.env" '
  BEGIN {
    print "# ─────────────────────────────────────────────────────────────────────────────"
    print "# env.local — GENERATED FILE. DO NOT EDIT."
    print "#"
    print "# Produced by: scripts/ops/gen_env_local.sh   (make env-local)"
    print "# Sources    : .env.shared (plaintext, committed) + secrets.enc.env (SOPS, committed)"
    print "#"
    print "# Hand edits are lost on the next regeneration, and a secret typed in here never"
    print "# reaches staging or production. Change a value at its source instead:"
    print "#   non-secret -> edit .env.shared"
    print "#   secret     -> sops secrets.enc.env"
    print "# ─────────────────────────────────────────────────────────────────────────────"
    skip = 1
    while ((getline line < plain) > 0) {
      if (line ~ /^sops_/) continue
      if (match(line, /^[A-Za-z_][A-Za-z0-9_]*=/)) { v[substr(line,1,RLENGTH-1)] = line }
    }
  }
  skip { if ($0 ~ /^#@shared-header-end$/) skip = 0; next }
  /^#@secret / {
    name = $2
    if (!(name in v)) { print "gen_env_local: " name " is marked in .env.shared but absent from secrets.enc.env" > "/dev/stderr"; bad=1; next }
    print v[name]; used[name]=1; next
  }
  { print }
  END {
    for (n in v) if (!(n in used)) { print "gen_env_local: " n " is in secrets.enc.env but has no #@secret marker in .env.shared" > "/dev/stderr"; bad=1 }
    if (bad) exit 3
  }
' "$SHARED" > "$TMP/out" ) || die "the two halves disagree — fix .env.shared / secrets.enc.env (see above)"

# Per-developer / per-host overlay (gitignored): PROD_SERVER_USER, PROD_HOST, PROD_SSH_KEY,
# and anything else that must not be committed to either half. Appended verbatim, so it wins
# on any duplicate key — dotenv semantics are last-one-wins.
EXTRA="$REPO/env.local.extra"
if [ -f "$EXTRA" ]; then
  { printf '\n# ── appended from env.local.extra (gitignored, not part of either committed half) ──\n'
    cat "$EXTRA"; } >> "$TMP/out"
  extra_n="$(grep -cE '^[A-Za-z_][A-Za-z0-9_]*=' "$EXTRA" || true)"
else
  extra_n=0
fi

install -m 600 "$TMP/out" "$OUT"

want="$(grep -cE '^[A-Za-z_][A-Za-z0-9_]*=' "$SHARED" || true)"
mark="$(grep -c '^#@secret ' "$SHARED" || true)"
got="$(grep -cE '^[A-Za-z_][A-Za-z0-9_]*=' "$OUT" || true)"
[ "$got" -eq "$((want + mark + extra_n))" ] || die "variable count mismatch: expected $((want + mark + extra_n)), wrote $got"

msg="env.local regenerated: $got variables ($want plaintext + $mark from secrets.enc.env"
[ "$extra_n" -gt 0 ] && msg="$msg + $extra_n from env.local.extra"
echo "$msg), mode 0600"
