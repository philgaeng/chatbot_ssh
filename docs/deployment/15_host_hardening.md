# Host Hardening Runbook

**Status:** Operational runbook (manual, prod host). Companion to [`../services/12_security_monitoring_service.md`](../services/12_security_monitoring_service.md) §3 item 12 and [`13_security.md`](13_security.md).

Single Ubuntu host, Docker Compose, public on `grm-chatbot.dor.gov.np`. These are host-OS controls that sit underneath the container hardening.

---

## 1. Firewall (ufw)

Allow only SSH + HTTP/HTTPS. Never expose Postgres (5432) or Redis (6379).

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status verbose
```

> Docker can bypass ufw via its own iptables chains. Ensure no compose service publishes `5432`/`6379` to `0.0.0.0` (the preflight gate asserts this). For host-side psql, bind to `127.0.0.1` only.

---

## 2. SSH lockdown + fail2ban

```bash
# /etc/ssh/sshd_config.d/10-hardening.conf
PasswordAuthentication no
PermitRootLogin no
KbdInteractiveAuthentication no
```
```bash
sudo systemctl reload ssh
sudo apt-get install -y fail2ban
# /etc/fail2ban/jail.local → [sshd] enabled = true, maxretry = 5, bantime = 1h
sudo systemctl enable --now fail2ban
```

The daily ops report surfaces SSH failed-login + fail2ban ban counts (§5 of the security spec); the watchdog can read `/var/log/auth.log` / `fail2ban-client status sshd`.

---

## 3. Unattended security updates

```bash
sudo apt-get install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```
`ops.maintenance.os_update_check` reports pending updates as a backstop.

---

## 4. Docker daemon

- Do **not** expose the Docker API over TCP (no `-H tcp://`). Keep it on the local socket.
- No app/monitor container mounts `/var/run/docker.sock` (asserted by preflight; the `ops` monitor deliberately has none — host actions live in `host_watchdog.sh`).
- Run containers non-root where feasible (future hardening).
- Container logs are bounded by the json-file driver (`x-logging` in compose).

---

## 5. Backups & keys

- DB + uploads backups: `scripts/ops/backup_db.sh` (encrypt with `BACKUP_GPG_RECIPIENT`/`BACKUP_PASSPHRASE`, off-box via `BACKUP_REMOTE`).
- Weekly restore verification: `scripts/ops/restore_drill.sh`.
- `DB_ENCRYPTION_KEY` stored separately — see [`14_key_and_secret_lifecycle.md`](14_key_and_secret_lifecycle.md).

---

## 6. Cron installers (host)

```bash
scripts/ops/install_watchdog_cron.sh /opt/grms      # L0 watchdog every 5 min
scripts/ops/install_tls_renew_cron.sh /opt/grms     # certbot renew
# Add to root crontab: daily backup + weekly restore drill
#   15 2 * * *  /opt/grms/scripts/ops/backup_db.sh /opt/grms
#   30 4 * * 0  /opt/grms/scripts/ops/restore_drill.sh /opt/grms
```

---

## 7. Pre-promotion

Run the gate before every staging/prod promotion:

```bash
make security-preflight     # or scripts/ops/security-preflight.sh /opt/grms
```
Non-zero exit blocks promotion. Its result is also folded into the daily ops report.
