# Follow-up — "Redis has no persistence volume" is an inference, and four documents state it as fact

> **Raised:** 2026-08-27, building [DPG-30](../04-pii-redaction-spec.md#dpg-30).
> **Status:** 🔴 **OPEN — unresolvable on this machine** (Docker unavailable in this WSL distro).
> **Size:** XS to check — three commands. S to fix, if the check comes back the wrong way.

---

## The finding

Four documents say some version of *"the `redis` service declares no persistence volume, so payloads
are not written to durable storage"*:

| Document | Where | What it concludes from it |
|---|---|---|
| [`privacy-assessment.md`](../../../dpg/privacy-assessment.md) | §2.2 leg **L3** | The unredacted-grievance-text leg is **mitigated** |
| [`19_incident_response.md`](../../../deployment/19_incident_response.md) | `:107`, `:125` | *"in memory only"*; *"restarting Redis drops queued tasks — that is a containment"* |
| [`14_key_and_secret_lifecycle.md`](../../../deployment/14_key_and_secret_lifecycle.md) | `:34` | Rotation advice: *"a restart drops queued tasks — check `LLEN` first"* |
| [`TODO.md`](../../../TODO.md) | `:550` | *"no persistence volume, so no dataset to migrate"* |

**All four trace to one inference**, made during the 2026-08-17 `redis:8.10` licence pin and never
tested since.

## What is actually established

✅ Verified from source, and not in doubt:

- `docker-compose.yml:214-234` defines `redis` **once**, with **no `volumes:` key**.
- Its command is `redis-server` with at most `--requirepass` — **no `--save`, no `--appendonly`**.
- **No `redis.conf` is mounted anywhere** in the repository.
- `redis` is **absent** from `docker-compose.grm.yml`, `.prod.yml` and `.aws.yml`, so the base
  definition is what runs on every deployment.

❌ **Not established, and this is the gap:** that any of the above means nothing reaches disk.

## Why the inference does not hold

Two mechanisms sit between "compose declares no volume" and "nothing is written", and neither is
visible in the compose file:

1. **The official `redis` image declares its own `VOLUME /data`.** A service that declares no volume in
   compose still gets an **anonymous** volume, created by Docker, living on the host filesystem.
2. **`redis-server` started with no config file uses Redis's compiled-in defaults**, and the default
   `save` points enable RDB snapshotting. Redis would write `dump.rdb` into that directory on its own
   schedule, unasked.

If both hold, then grievance narratives — including SEAH disclosures — are being **snapshotted to a
host volume that no backup covers, no retention policy names, and no document knows exists.** The
privacy assessment's mitigation would be exactly backwards, and the incident runbook's containment
property would be false at the moment someone relies on it.

## ⚠ The 2026-08-18 "VERIFIED LIVE" note does not close this

`TODO.md:550` carries a **✅ VERIFIED LIVE 2026-08-18** marker, which reads as though the question was
settled. It was not. That check verified the **licence and usage** audit — `redis_version:8.10.0`,
auth, `PING` / `SET … EX` / `GET` / `LLEN` / `INFO memory`, a pub/sub round-trip — all of which it
reports accurately.

Its persistence sentence is *"No data to migrate, as predicted — the service declares no volume."*
**That restates the inference; it does not test it.** Worth noting as a pattern: a verification note
that is accurate about everything it checked can still launder an unchecked assumption sitting next to
the checked ones.

## What would close it — three commands

```bash
docker compose exec redis redis-cli CONFIG GET save
docker compose exec redis redis-cli CONFIG GET appendonly
docker inspect $(docker compose ps -q redis) --format '{{json .Mounts}}'
```

Then, and only then:

- **If persistence is off and there is no mount** — the four documents are correct. Add the command
  output to `19_incident_response.md` so the next person inherits evidence instead of an inference.
- **If persistence is on, or an anonymous volume exists** — the fix is to make the claim *true* rather
  than to soften it: add `--save "" --appendonly no` to the compose command, recreate, re-check. Then
  correct L3, both runbook lines and the lifecycle doc, and record it as a deviation.

⚠ **Do not resolve this by adding a named volume.** That makes the exposure durable *and* documented,
which is worse than either alone — a broker holding unredacted SEAH text does not need better
persistence, it needs less.

⚠ **And do not resolve it by deleting the sentence.** L3's mitigation is doing real work in the
assessment; removing it without an answer downgrades a leg on no evidence, which is the opposite error.

## Related

- [`pii-egress-inventory.md`](../../../dpg/pii-egress-inventory.md) §2 — the full finding, and §0 on why it could not be closed here
- [`../04-pii-redaction-spec.md#dpg-34`](../04-pii-redaction-spec.md#dpg-34) — owns the fix if one is needed
- [`../../../TODO.md`](../../../TODO.md) — the backlog row
