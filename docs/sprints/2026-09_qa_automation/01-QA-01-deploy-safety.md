# QA-01 — Stop the next deploy being an outage

> **Stream A · ½ day · depends on nothing · blocks QA-02**
> Source: incident `2431da51` (2026-09-04) and its `TODO.md` row. This ticket is fixes **(1)** and
> **(3)** of the three logged there; fix **(2)** is [QA-02](02-QA-02-ci-built-images.md).

## Context

`make aws-deploy` runs `docker compose build --pull` **on the staging host** — a t4g.medium with
**3825 MB and no swap**, already running 14 containers. On 2026-09-04 the Next.js build exhausted
memory and the host stopped accepting new SSH, ping and Tailscale for 41 minutes. Established
connections survived, so every AWS-side signal read healthy: both instance checks `ok`, CPU 25–33%.
`free -m` after recovery: **96 MB free, swap 0, load average 54.92**.

This ticket does not fix the cause (that is QA-02). It makes the failure mode survivable and loud.

## Scope

1. **Swap on the staging host.** A 4 GB swapfile, `vm.swappiness` left at default, persisted in
   `/etc/fstab` so it survives reboot. Delivered as an **idempotent script** — `scripts/ops/add_swap.sh`
   — not a one-off shell session, so prod and any future host get the same treatment.
2. **Cap the Next build heap.** `NODE_OPTIONS=--max-old-space-size=<MB>` in the **builder stage** of
   `channels/ticketing-ui/Dockerfile`, exposed as a build ARG so it is tunable per host. The point is
   that the build **fails loudly at its own limit instead of taking the host down with it.**
3. **Make a stalled deploy visible.** `aws-deploy` currently prints nothing until it exits, so a
   40-minute stall is indistinguishable from a 4-minute one — and on the incident its `OK` line never
   printed at all. Echo a **timestamped line before each phase** in `REMOTE_DEPLOY_CORE` and pass
   `--progress=plain` to the build.

## Not in scope

Moving the build off the box (QA-02). Any change to what gets deployed. Prod host changes — see
[Q-15](QUESTIONS.md#q-15--who-runs-the-dor-prod-side-of-qa-02-and-when); this ticket's script should be
*runnable* on prod but is applied to staging only here.

## Files

| File | Change |
|---|---|
| `scripts/ops/add_swap.sh` | **new** — idempotent: exit 0 if swap already active; else `fallocate`/`mkswap`/`swapon` + `fstab` line |
| `channels/ticketing-ui/Dockerfile` | `ARG NODE_BUILD_HEAP_MB=1536` + `ENV NODE_OPTIONS=--max-old-space-size=$NODE_BUILD_HEAP_MB` in the **builder** stage only (never the runner) |
| `Makefile` | `REMOTE_DEPLOY_CORE` / `REMOTE_BUILD_SERVICES_SEQUENTIAL`: timestamped phase echoes, `--progress=plain` |
| `docs/deployment/15_host_hardening.md` | Swap section: why (the incident), how (the script), how to verify |
| `docs/deployment/03_operations.md` | Deploy runbook: **do not pipe `aws-deploy` through `tail`** — it buffers until the pipe closes, which is what left the operator blind for 41 minutes |

⚠ **`1536` is a starting value, not a measured one.** Measure the real peak (`/usr/bin/time -v npm run
build`, or `docker stats` during a build) and set the default just above it. Too low turns every deploy
into a failed build; the whole point is that it fails *before* the host does.

## Acceptance

- [ ] `scripts/ops/add_swap.sh` run twice in a row on staging — second run is a no-op, exit 0
- [ ] `free -m` on staging shows **4096 MB swap**; `swapon --show` non-empty; survives a reboot (`/etc/fstab` verified)
- [ ] A normal `make aws-deploy` completes with the heap cap in place
- [ ] With the cap set deliberately low (e.g. `256`), the **build fails with a clear OOM error and the
      host stays reachable over SSH throughout** — this is the test that actually proves the ticket
- [ ] `aws-deploy` prints a timestamped line per phase; a stall is visibly a stall
- [ ] Both docs updated; `PROGRESS.md` deviations logged

## Risks

- **Swap on EBS is slow.** That is the point — a slow deploy beats an unreachable host. Do not raise
  `vm.swappiness`; this is an emergency buffer, not a memory strategy.
- **A too-low heap cap breaks deploys for everyone.** Measure before you pick the default, and put the
  measured number in the commit message.
