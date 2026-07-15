# Follow-up — `5001:5001` binds the backend API to all host interfaces on deployed hosts

> **Status:** 🟡 **OPEN — deferred out of T3-06 (2026-07-15).** · **Owner:** deployment · **Priority:** low (defence-in-depth; the port is closed at the firewall and the endpoints are now authenticated)
> **Origin:** T3-06 ([`../05-grievance-api-hardening-spec.md`](../05-grievance-api-hardening-spec.md)) §Exposure — *"Consider dropping the `5001:5001` host mapping from the **prod** overlay if nothing needs it."* Deferred rather than done, for the reason in §Why below.

## The finding

```yaml
# docker-compose.grm.yml:112-117
  # ── Backend API port override (base docker-compose.yml has no host port mapping) ──
  # This overlay exposes port 5001 so the host browser can reach /api/grievance/*.
  backend:
    ports:
      - "5001:5001"
```

The mapping has no interface prefix, so it binds `0.0.0.0:5001` — every host interface, not just loopback. The comment states its purpose plainly: *"so the host browser can reach `/api/grievance/*`"* — a **dev convenience**.

**It is not dev-only in practice.** The staging deploy composes this same overlay (`docs/deployment/03_operations.md:50`):

```
docker compose -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml up -d --build
```

So a dev convenience is applied verbatim on the deployed host. `docker-compose.aws.yml` maps only `80`/`443` on nginx; it does not touch the backend's ports.

## Why this is not currently an exposure

Verified 2026-07-15 against the live AWS account (`ap-southeast-1`), security group `sg-01739221c73ab3eb1` (attached to `chatbot-main` and `chatbot-rest`):

| Proto | Port | Source |
|---|---|---|
| tcp | 80 | 0.0.0.0/0 |
| tcp | 443 | 0.0.0.0/0 |
| tcp | 22 | 158.62.26.255/32 |
| tcp | 8000 | 0.0.0.0/0 |
| tcp | 3000 | 0.0.0.0/0 |
| tcp | 0 | 103.41.172.170/32 |

**5001 is not admitted.** Combined with there being no `location /api/grievance` block in any nginx conf, the endpoints were not internet-reachable even before T3-06 added authn. This is what keeps T3-06 a Phase-2 hardening ticket rather than an incident.

The firewall is therefore doing the work that the port binding is not. That is a single control, and it is one SG edit away from being wrong.

## Why it was deferred rather than fixed

The ticket says to drop it from *"the prod overlay"* — but **the mapping is not in a prod overlay**. It is in `docker-compose.grm.yml`, which is shared by the local dev stack and both deploy paths. That makes the change less trivial than it reads:

- **Removing it from `grm.yml` breaks the documented local loop** — the host-browser access the comment exists to provide, and any host tooling pointed at `localhost:5001`.
- **It cannot be cleanly overridden per-overlay.** Compose **merges** `ports` by concatenation rather than replacement, so adding `127.0.0.1:5001:5001` in `docker-compose.aws.yml` yields *both* mappings — the `0.0.0.0` bind survives, and the two may conflict on bind. The override has to happen where the mapping is declared, not in the deploy overlay.
- It is **defence-in-depth, not a live hole** (see above), so it does not justify a rushed change to deploy topology inside a `backend/` security ticket.

## Definition of done

1. Move the loopback decision to where the mapping lives. The most likely shape: make the bind address a variable in `docker-compose.grm.yml` — e.g. `"${BACKEND_HOST_BIND:-0.0.0.0}:5001:5001"` — defaulting to today's behaviour for dev and set to `127.0.0.1` in the deployed env files. This keeps one declaration and avoids the merge trap.
2. Confirm nothing on the deployed hosts reaches the backend via the instance's public/private IP rather than the Docker network. Containers use `http://backend:5001` (`docker-compose.grm.yml:146`), so this should hold — verify before changing.
3. Do the same review for `8000:8000` (orchestrator), which **is** admitted by the SG from `0.0.0.0/0` → [`orchestrator-port-8000-open.md`](orchestrator-port-8000-open.md).
4. Consider whether `3000` should stay in the SG at all: **no compose file maps `3000`**, so the rule appears vestigial. Removing an unused allow-rule is free.

**Recommended trigger:** the next deployment-configuration pass, or immediately if `:5001` is ever opened in a security group.
