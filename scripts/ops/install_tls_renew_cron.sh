#!/usr/bin/env bash
set -euo pipefail

# Install the certbot renewal cron for docker-compose nginx deployments.
#
# Usage:
#   scripts/ops/install_tls_renew_cron.sh /home/ubuntu/nepal_chatbot
#
# Optional env vars:
#   CRON_SCHEDULE        (default: "17 3 * * *")
#   CERTBOT_CONF         (default: <repo>/deployment/certbot/conf)
#   CERTBOT_WWW          (default: <repo>/deployment/certbot/www)
#   CERTBOT_WORK         (default: <repo>/deployment/certbot/work)
#   CERTBOT_LOGS         (default: <repo>/deployment/certbot/logs)
#   NGINX_CONTAINER      (default: nepal_chatbot-nginx-1)
#   MIN_DAYS_REMAINING   (default: 21) — wrapper fails loudly below this
#   CRON_MAILTO          (default: root)
#
# Two things this script gets right, both learned the hard way (2026-08-13, when the
# staging cert expired unnoticed):
#
#   1. It renews with the HOST certbot and explicit --config-dir/--work-dir/--logs-dir.
#      It does NOT run certbot in Docker. The renewal configs under $CERTBOT_CONF/renewal
#      record ABSOLUTE HOST paths (archive_dir, cert, privkey, ...). Inside a container
#      those paths do not exist, so certbot rejects the config with
#      "expected .../cert.pem to be a symlink ... parsefail" and renews nothing.
#
#   2. It verifies the certs afterwards. `certbot renew` exits 0 even when every renewal
#      config failed to parse, so a --quiet cron that trusts the exit code reports success
#      forever while the cert quietly expires. The wrapper re-checks real expiry dates and
#      exits non-zero if anything is inside MIN_DAYS_REMAINING, which is what actually
#      makes the failure visible.

REPO_DIR="${1:-}"
if [[ -z "$REPO_DIR" ]]; then
  echo "Usage: $0 <absolute-repo-path>" >&2
  exit 1
fi

if [[ ! -d "$REPO_DIR" ]]; then
  echo "Repository directory not found: $REPO_DIR" >&2
  exit 1
fi

REPO_DIR="$(cd "$REPO_DIR" && pwd)"

CRON_SCHEDULE="${CRON_SCHEDULE:-17 3 * * *}"
CERTBOT_CONF="${CERTBOT_CONF:-$REPO_DIR/deployment/certbot/conf}"
CERTBOT_WWW="${CERTBOT_WWW:-$REPO_DIR/deployment/certbot/www}"
CERTBOT_WORK="${CERTBOT_WORK:-$REPO_DIR/deployment/certbot/work}"
CERTBOT_LOGS="${CERTBOT_LOGS:-$REPO_DIR/deployment/certbot/logs}"
NGINX_CONTAINER="${NGINX_CONTAINER:-nepal_chatbot-nginx-1}"
MIN_DAYS_REMAINING="${MIN_DAYS_REMAINING:-21}"
CRON_MAILTO="${CRON_MAILTO:-root}"

CRON_FILE="/etc/cron.d/nepal-chatbot-cert-renew"
WRAPPER="/usr/local/bin/nepal-chatbot-cert-renew"

if ! command -v certbot >/dev/null 2>&1; then
  echo "certbot not found on PATH. Install it on the host first (apt install certbot)." >&2
  echo "This script deliberately does not use the certbot Docker image — see header." >&2
  exit 1
fi

sudo mkdir -p "$CERTBOT_CONF" "$CERTBOT_WWW" "$CERTBOT_WORK" "$CERTBOT_LOGS"

# --- renewal wrapper -------------------------------------------------------
# Config is interpolated here; the logic below comes from a quoted heredoc so it
# stays literal.
sudo tee "$WRAPPER" >/dev/null <<EOF
#!/usr/bin/env bash
# Managed by scripts/ops/install_tls_renew_cron.sh — edit that script, not this file.
set -uo pipefail

CERTBOT_CONF="$CERTBOT_CONF"
CERTBOT_WORK="$CERTBOT_WORK"
CERTBOT_LOGS="$CERTBOT_LOGS"
NGINX_CONTAINER="$NGINX_CONTAINER"
MIN_DAYS_REMAINING="\${MIN_DAYS_REMAINING:-$MIN_DAYS_REMAINING}"
EOF

sudo tee -a "$WRAPPER" >/dev/null <<'EOF'

# --deploy-hook fires only on an actual renewal, so nginx is not reloaded daily.
certbot renew \
  --config-dir "$CERTBOT_CONF" \
  --work-dir "$CERTBOT_WORK" \
  --logs-dir "$CERTBOT_LOGS" \
  --quiet \
  --deploy-hook "docker exec $NGINX_CONTAINER nginx -s reload"
rc=$?

status=0
[ "$rc" -ne 0 ] && { echo "cert-renew: certbot exited $rc" >&2; status=1; }

# certbot exits 0 on parsefail, so trust the certificates, not the exit code.
shopt -s nullglob
found=0
for cert in "$CERTBOT_CONF"/live/*/cert.pem; do
  found=1
  name="$(basename "$(dirname "$cert")")"
  if ! openssl x509 -in "$cert" -noout -checkend "$((MIN_DAYS_REMAINING * 86400))" >/dev/null 2>&1; then
    expiry="$(openssl x509 -in "$cert" -noout -enddate 2>/dev/null | cut -d= -f2)"
    echo "cert-renew: $name expires $expiry (under ${MIN_DAYS_REMAINING}d) — renewal is NOT working" >&2
    status=1
  fi
done

if [ "$found" -eq 0 ]; then
  echo "cert-renew: no certificates under $CERTBOT_CONF/live — nothing is being renewed" >&2
  status=1
fi

exit $status
EOF

sudo chmod 755 "$WRAPPER"

# --- cron entry ------------------------------------------------------------
# cron.d has no line continuations: the schedule line must stay on one line.
sudo tee "$CRON_FILE" >/dev/null <<EOF
# Managed by scripts/ops/install_tls_renew_cron.sh — do not edit by hand.
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
MAILTO=$CRON_MAILTO

$CRON_SCHEDULE root $WRAPPER
EOF

sudo chmod 644 "$CRON_FILE"

echo "Installed: $WRAPPER"
echo "Installed: $CRON_FILE"
sudo cat "$CRON_FILE"
echo
echo "Verify now with a no-op run:  sudo $WRAPPER && echo OK"
