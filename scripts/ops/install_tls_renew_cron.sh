#!/usr/bin/env bash
set -euo pipefail

# Install a certbot renewal cron entry for docker-compose nginx deployments.
#
# Usage:
#   scripts/ops/install_tls_renew_cron.sh /home/ubuntu/nepal_chatbot
#
# Optional env vars:
#   CRON_SCHEDULE   (default: "17 3 * * *")
#   CERTBOT_CONF    (default: <repo>/deployment/certbot/conf)
#   CERTBOT_WWW     (default: <repo>/deployment/certbot/www)

REPO_DIR="${1:-}"
if [[ -z "$REPO_DIR" ]]; then
  echo "Usage: $0 <absolute-repo-path>" >&2
  exit 1
fi

if [[ ! -d "$REPO_DIR" ]]; then
  echo "Repository directory not found: $REPO_DIR" >&2
  exit 1
fi

CRON_SCHEDULE="${CRON_SCHEDULE:-17 3 * * *}"
CERTBOT_CONF="${CERTBOT_CONF:-$REPO_DIR/deployment/certbot/conf}"
CERTBOT_WWW="${CERTBOT_WWW:-$REPO_DIR/deployment/certbot/www}"
CRON_FILE="/etc/cron.d/nepal-chatbot-cert-renew"

sudo mkdir -p "$CERTBOT_CONF" "$CERTBOT_WWW"

sudo tee "$CRON_FILE" >/dev/null <<EOF
$CRON_SCHEDULE root docker run --rm -v $CERTBOT_CONF:/etc/letsencrypt -v $CERTBOT_WWW:/var/www/certbot certbot/certbot renew --webroot -w /var/www/certbot --quiet && docker compose -f $REPO_DIR/docker-compose.yml exec -T nginx nginx -s reload
EOF

sudo chmod 644 "$CRON_FILE"
echo "Installed: $CRON_FILE"
sudo cat "$CRON_FILE"
