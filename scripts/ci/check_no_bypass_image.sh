#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
#
# QA-02 scope 4 — no deployable stack may reference the bypass UI image.
#
# The officer UI bakes its auth mode at build time, so one commit produces two images:
# `ui:<sha>` (Keycloak, deployable) and `ui:<sha>-bypass` (test only, cookie identity, no
# login). If a `-bypass` reference reached a staging or production compose file, the portal
# would serve every visitor as a seeded officer.
#
# ⚠ **This is defence in depth, not the only control.** HR-01 already makes the runtime fail
# closed: production refuses to honour AUTH_MODE=bypass. But a test-only image reaching a real
# environment is worth two checks, and this one fails in CI rather than at 3am.
#
# ⚠ **It reads UI_IMAGE_TAG, not just `image:` lines.** After QA-02 the variant is chosen by
# that variable, so that is where a `-bypass` reference would actually come from — a guard that
# only grepped `image:` would pass while the stack pulled the wrong image.
#
#   scripts/ci/check_no_bypass_image.sh            # check the deployable compose files
#   scripts/ci/check_no_bypass_image.sh a.yml b.yml   # check specific files (used by its test)
set -euo pipefail

# Compose files that describe a REAL environment. `docker-compose.grm.yml` is included because
# staging and production both layer it; the e2e stack is expected to set UI_IMAGE_TAG in its own
# environment, never in a committed file.
DEFAULT_FILES=(
  docker-compose.yml
  docker-compose.aws.yml
  docker-compose.grm.yml
  docker-compose.prod.yml
)

files=("$@")
if [ ${#files[@]} -eq 0 ]; then files=("${DEFAULT_FILES[@]}"); fi

offenders=""
for f in "${files[@]}"; do
  [ -f "$f" ] || continue
  # Any occurrence of `-bypass` in an image reference or a UI_IMAGE_TAG assignment.
  while IFS= read -r hit; do
    offenders+="  $f:$hit"$'\n'
  done < <(grep -nE '(image:.*-bypass|UI_IMAGE_TAG[[:space:]]*[:=].*-bypass)' "$f" || true)
done

if [ -n "$offenders" ]; then
  echo "ERROR: a deployable compose file references the bypass UI image."
  echo
  echo "$offenders"
  echo "The bypass build has NO login — it reads an identity from a cookie. Serving it from a"
  echo "real environment would make every visitor a seeded officer."
  echo
  echo "If you need the bypass image for a test stack, set UI_IMAGE_TAG in that stack's"
  echo "environment (as the e2e job does), never in a committed compose file."
  exit 1
fi

echo "OK: no deployable compose file references a -bypass image (checked: ${files[*]})"
