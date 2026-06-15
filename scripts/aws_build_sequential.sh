#!/usr/bin/env bash
# Sequential Docker builds for small EC2 hosts (avoids parallel Next.js + Python OOM).
# Run ON the server:  bash scripts/aws_build_sequential.sh
# Optional service list:  bash scripts/aws_build_sequential.sh ticketing_api grm_ui_auth
set -euo pipefail

cd "$(dirname "$0")/.."

export COMPOSE_PARALLEL_LIMIT=1
COMPOSE=(docker compose --env-file env.local
  -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml
  --profile auth)

if [ "$#" -gt 0 ]; then
  SERVICES=("$@")
else
  SERVICES=(
    ticketing_api ticketing_api_auth backend celery_default
    grm_celery grm_celery_beat grm_ui_auth grm_ui
  )
fi

echo "Building ${#SERVICES[@]} service(s) one at a time: ${SERVICES[*]}"
for svc in "${SERVICES[@]}"; do
  echo "=== build ${svc} ==="
  "${COMPOSE[@]}" build --pull "${svc}"
done

echo "=== up -d ${SERVICES[*]} ==="
"${COMPOSE[@]}" up -d "${SERVICES[@]}"

echo "Done."
