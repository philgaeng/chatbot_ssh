#!/usr/bin/env bash
set -euo pipefail

# Install the host watchdog as a cron entry (every 5 minutes).
#
# Usage:
#   scripts/ops/install_watchdog_cron.sh /home/ubuntu/nepal_chatbot
#
# Env:
#   CRON_SCHEDULE (default "*/5 * * * *")  ALERT_EMAIL ("")

REPO_DIR="${1:-}"
if [[ -z "$REPO_DIR" || ! -d "$REPO_DIR" ]]; then
  echo "Usage: $0 <absolute-repo-path>" >&2
  exit 1
fi

CRON_SCHEDULE="${CRON_SCHEDULE:-*/5 * * * *}"
ALERT_EMAIL="${ALERT_EMAIL:-}"
CRON_FILE="/etc/cron.d/nepal-grms-watchdog"
LOG_FILE="/var/log/grms-watchdog.log"

sudo tee "$CRON_FILE" >/dev/null <<EOF
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
$CRON_SCHEDULE root ALERT_EMAIL=$ALERT_EMAIL $REPO_DIR/scripts/ops/host_watchdog.sh $REPO_DIR >> $LOG_FILE 2>&1
EOF

sudo chmod 644 "$CRON_FILE"
sudo touch "$LOG_FILE"
echo "Installed: $CRON_FILE"
sudo cat "$CRON_FILE"
