# Host Hardening Runbook

**Status:** Operational runbook (manual, prod host). Companion to [`../services/12_security_monitoring_service.md`](../services/12_security_monitoring_service.md) §3 item 12 and [`13_security.md`](13_security.md).
**Last updated:** 2026-09-17 — ✅ **`POSTGRES_PASSWORD` and `REDIS_PASSWORD` rotated on this host** (§5); §1 gains what its ufw block does and does not achieve here. ⛔ **§1, §2 and §6 were measured against the DOR host and largely do NOT describe it** (`GRM-148`): fail2ban is not installed, password SSH is on, the TLS renewal here is **Docker-based** so §6's host-certbot installer would break it, and the backup script now refuses to write an unencrypted dump. §5 and §6 record what is actually installed and working as of 2026-09-17. Earlier, 2026-09-16 — §6: ⛔ **none of these cron scripts could ever execute** — they were non-executable in git from the day they were added (`GRM-139`, measured on the DOR host). ⚠ The rest was backfilled from git 2026-09-04 and is still not re-verified against the code

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

> ### ⚠ Measured on the DOR host, 2026-09-17 (`GRM-148`)
>
> **ufw is not installed here, and the warning above is the operative fact:** `db` publishes
> `${POSTGRES_HOST_PORT:-5433}:5432` and `redis` `6379` on `0.0.0.0`, so both are reachable from the
> DOR internal network and the VPN regardless of any host firewall. **Binding them to `127.0.0.1` in
> compose is the fix; a ufw rule is not.** The preflight gate that asserts this has never been run
> against this host.
>
> ⛔ **A port scan of this host is misleading — do not act on one alone.** A TCP connect from the open
> internet *succeeds* on 5432, 5433, 6379, 18080, 3001, 5002 and 8080. That is the **upstream NAT**
> completing handshakes for ports it never forwards — the host's own interface holds a **private**
> address, and the public address is not on it at all. The protocol probe is what settles it: HTTP returns `000` and Postgres sends
> no packet. ⚠ This was mistaken for a critical exposure on 2026-09-17 on the strength of the connect
> alone. **Always follow a connect with a protocol probe before acting.**
>
> An `iptables -I DOCKER-USER … -j DROP` rule was added as a stopgap and matched **zero packets** —
> inbound traffic does not arrive the way such a rule assumes, and it would not survive a reboot
> anyway. The compose binding is the only durable fix.

---

## 2. SSH lockdown + fail2ban

> ⛔ **NOT APPLIED on the DOR production host — measured 2026-09-17 (`GRM-148`).** `fail2ban-client`
> is **not installed** (`command not found`), and password SSH is **enabled** — it is how the owner
> logs in daily, and how every `make prod-*` target authenticates. So the block below is a
> *proposal*, not a description. Treat it that way before quoting it as the host's posture.
>
> ⚠ **`PasswordAuthentication no` would lock you out of this box.** It is reachable only over the
> Sophos VPN, no SSH key is installed for `administrator`, and the Makefile's prod targets use
> password auth. Set up a key, **test it from a second terminal while the first stays open**, and
> change the Makefile path, before going anywhere near this setting.

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

- DB + uploads backups: `scripts/ops/backup_db.sh` — set `BACKUP_GPG_RECIPIENT` (preferred) or
  `BACKUP_PASSPHRASE`; off-box via `BACKUP_REMOTE`.
  ⚠ **Encryption is no longer optional** (D-19/F-4, fixed 2026-08-19). With neither variable set the
  script **discards the dump and the uploads archive** rather than leaving them on disk, unless
  `BACKUP_ALLOW_UNENCRYPTED=1` says otherwise in so many words. The reason: the contact columns stay
  ciphertext inside a dump, but the grievance narrative, every officer note, and **every voice
  recording and photograph** in the uploads tar do not — so an unencrypted backup is a complete copy
  of the most sensitive material the system holds. Losing a backup is recoverable on the next run;
  an unencrypted copy of a survivor's report is not.
- Weekly restore verification: `scripts/ops/restore_drill.sh`.
- `DB_ENCRYPTION_KEY` stored separately — see [`14_key_and_secret_lifecycle.md`](14_key_and_secret_lifecycle.md).

✅ **Credentials rotated on this host, 2026-09-17.** `POSTGRES_PASSWORD` and `REDIS_PASSWORD` were
rotated together — `sed` on `env.local`, `ALTER ROLE` for the Postgres role, then a full
`up -d --force-recreate --remove-orphans`, which also retired the two June `_auth` containers and
brought Redis up on **8.10.1**. That retires `password`, the credential
[`18_sops_migration_handover.md`](18_sops_migration_handover.md) records as live on this host and
still names in three tracked files. ⚠ **AWS staging is not rotated.** ⚠ The pre-rotation `env.local`
is in the operator's home directory, **outside the repo** — delete it once the rotation is trusted.

---

## 6. Cron installers (host)

```bash
scripts/ops/install_watchdog_cron.sh /opt/grms      # L0 watchdog every 5 min
scripts/ops/install_tls_renew_cron.sh /opt/grms     # certbot renew
# Add to root crontab: daily backup + weekly restore drill
#   15 2 * * *  /opt/grms/scripts/ops/backup_db.sh /opt/grms
#   30 4 * * 0  /opt/grms/scripts/ops/restore_drill.sh /opt/grms
```

> ### ✅ What is actually installed on the DOR host, 2026-09-17 (`GRM-148`)
>
> The commands above do **not** work on this host as written. Three reasons, all measured:
>
> **1. `install_tls_renew_cron.sh` would break TLS here.** It refuses to run without a **host**
> certbot, and deliberately so — its header explains that renewal configs record absolute host
> paths, which a container cannot resolve. **On this host the opposite is true.** `certbot` is not
> installed; the certificate is issued and renewed by the **`certbot/certbot` Docker image**, and
> `renewal/grm-chatbot.dor.gov.np.conf` records *container* paths (`/etc/letsencrypt/...`,
> `webroot_path = /var/www/certbot`). Installing a host certbot and pointing it at
> `deployment/certbot/conf` would reproduce the exact parse-fail-and-report-success that let
> staging's certificate expire on 2026-08-13.
>
> It also defaults `NGINX_CONTAINER=nepal_chatbot-nginx-1` — **staging's** name. Here it is
> `grms-nginx-1`, so renewal would succeed and the reload would target nothing.
>
> **What is installed instead:** `/usr/local/bin/grms-cert-renew` — runs the certbot container,
> reloads `grms-nginx-1`, then **verifies real expiry** and exits non-zero under 21 days (the one
> safeguard the original script is right about: `certbot renew` exits 0 even when every renewal
> config failed). Scheduled daily at 03:17 via `/etc/cron.d/grms-cert-renew`. Verified end to end.
>
> **2. `backup_db.sh` now refuses to keep an unencrypted dump.** The first run after the September
> deploy produced `dump_ok=false, size=0` — correctly, since the archive holds complainant PII,
> voice notes and photographs. A cron calling the script bare would have produced **nothing every
> night**, reporting success in its own log. It needs `BACKUP_GPG_RECIPIENT`, `BACKUP_PASSPHRASE`,
> or an explicit `BACKUP_ALLOW_UNENCRYPTED=1`.
>
> **What is installed instead:** `/etc/grms-backup.env` (root-only, holds a symmetric passphrase)
> plus `/usr/local/bin/grms-backup` and `/usr/local/bin/grms-restore-drill`, scheduled in
> `/etc/cron.d/grms-backup`. ⚠ **The passphrase exists only on this host and in the owner's password
> manager.** An encrypted backup whose passphrase died with the machine is not a backup.
>
> **3. The scripts were non-executable until 2026-09-16** (`GRM-139`), which is the older half of
> why none of this ran.
>
> ✅ **First successful restore drill in the system's history, 2026-09-17:** the encrypted dump was
> decrypted and restored into a scratch database, 130 grievances and 130 tickets verified, `ok=true`.
> Until that moment nothing had ever been restored from a backup of this system.
>
> ⏳ **Still open:** `offbox=false`. The backups sit on the machine they protect.

> ### ⛔ None of this ran, from 2026-06-23 to 2026-09-16 (`GRM-139`)
>
> Every script above was mode **`100644`** in git — non-executable. Invoked by path, as cron
> invokes them, each answered `Permission denied`. **The nightly backup, the weekly restore drill
> and the five-minute watchdog had never executed on any host.** Measured on the DOR production
> host on 2026-09-16, by being the first person to run the backup by hand.
>
> `GRM-114` had recorded production's backups as *unverified*. They were not unverified, they were
> **absent** — and the distinction matters, because "unverified" invites a check while "absent"
> demands a restore test.
>
> **Why nobody noticed.** `GRM-094` had already fixed this class, for the scripts a **Make target**
> runs — the ones that fail loudly, in front of a person, on a fresh clone. Its test scoped itself
> to the Makefile. Cron scripts fail at 02:15 with nobody watching, and production runs no monitor
> to notice the missing status file. The fix is the mode bit; the durable half is
> `tests/repo/test_make_scripts_executable.py`, which now requires **every tracked `.sh` with a
> shebang** to be `100755`, on the reasoning that a shebang *is* the declaration that a file is
> meant to be run.
>
> ⚠ **On a host that already has the old checkout, `git pull` fixes the bit** — git tracks it — but
> verify rather than assume, and run one backup by hand before trusting the cron again.

---

## 7. Pre-promotion

Run the gate before every staging/prod promotion:

```bash
make security-preflight     # or scripts/ops/security-preflight.sh /opt/grms
```
Non-zero exit blocks promotion. Its result is also folded into the daily ops report.
