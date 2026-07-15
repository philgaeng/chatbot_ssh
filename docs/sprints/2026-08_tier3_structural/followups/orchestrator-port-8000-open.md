# Follow-up — orchestrator `:8000` is open to `0.0.0.0/0` and unauthenticated

> **Status:** 🟡 **OPEN — surfaced by T3-06 (2026-07-15), out of its scope.** · **Owner:** deployment / orchestrator · **Priority:** medium — lower than it first looks (the endpoint is *meant* to be public), but it bypasses every control nginx applies.
> **Origin:** found while executing T3-06's §Exposure check ([`../05-grievance-api-hardening-spec.md`](../05-grievance-api-hardening-spec.md)), which directs the implementer to *"Check the staging + prod EC2 security groups for inbound :5001"*. That check cleared 5001 and turned up 8000.

## The finding

Three facts compose:

1. **The port is mapped on deployed hosts.** `docker-compose.grm.yml:122` maps `"8000:8000"` (all interfaces), and the staging deploy composes that overlay (`docs/deployment/03_operations.md:50`).
2. **The firewall admits it from anywhere.** SG `sg-01739221c73ab3eb1` (on `chatbot-main`, `chatbot-rest`) allows `tcp/8000` from `0.0.0.0/0` — verified 2026-07-15 in `ap-southeast-1`.
3. **The service has no auth.** `backend/orchestrator/main.py` exposes exactly two routes — `POST /message` (`:102`) and `GET /health` (`:153`) — and the module contains no `Depends`, no `Header`, no api-key check.

⇒ When the instance runs, `POST /message` is drivable by anyone on the internet, directly, over plaintext HTTP.

## Why this is less severe than it reads — state it honestly

`POST /message` is **the public chatbot entry point**. Any visitor to the web chat can already reach it through nginx; it is not a privileged endpoint, and it takes a `session_id` the caller supplies. Direct `:8000` access does not disclose anything that the public chat UI does not.

**What it does bypass** is every control that lives in nginx rather than in the app:

- **TLS** — `:8000` is plaintext; the nginx path is HTTPS (`webchat_rest_compose_prod.tls.conf`). Message content and `session_id` travel in the clear.
- **Rate limiting** — the `public` zone (30r/m, `:8` and `:100`) is an nginx-level control. Direct `:8000` is unthrottled, so it is a free path to whatever the orchestrator costs per call — which includes **LLM invocations**, i.e. a metered spend.
- Any other `location`-level guard added to nginx in future, which will silently not apply here.

So: not a data-disclosure hole, but an unmetered, unencrypted path to a paid, stateful service.

## Relationship to T3-06

None causally — this is a different service and a different port. It is recorded here only because T3-06's exposure check is what looked at the SG, and the ticket's standing practice is that findings surfaced by a check get logged rather than dropped. T3-06 deliberately did **not** touch it: the ticket is scoped to `backend/api/routers/grievance.py`.

Note the contrast that makes this worth reading: T3-06 spent four commits authenticating a port that the firewall **already closed**, while the port the firewall **leaves open** has no auth at all. The repo-level reasoning ("is there a `Depends`?") and the infrastructure reality point in opposite directions, and only checking both revealed it.

## Definition of done

1. Decide whether `:8000` needs a host mapping on deployed hosts at all. nginx reaches the orchestrator over the Docker network, so the mapping looks like the same dev convenience as `5001:5001` → see [`grievance-api-host-port-binding.md`](grievance-api-host-port-binding.md); the same compose-merge trap applies.
2. If not needed: remove `tcp/8000 0.0.0.0/0` from `sg-01739221c73ab3eb1` **and** bind the mapping to loopback. Either alone leaves the other as the only control.
3. Confirm no client is pointed at `http://<host>:8000` directly (webchat `config.js`, any Rasa/ops caller) **before** changing either — this is the outage risk.
4. While in the SG: `tcp/3000 0.0.0.0/0` appears **vestigial** — no compose file maps `3000`. Confirm and remove.
5. If direct `:8000` access must stay, give the orchestrator its own throttle — it cannot inherit nginx's.

**Recommended trigger:** the next deployment-configuration pass. Do it together with the `5001`/`3000` items above — it is one SG edit and one compose edit for all three.
