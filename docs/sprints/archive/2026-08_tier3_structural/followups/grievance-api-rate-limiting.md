# Follow-up — the grievance API has no rate limiting

> **Status:** 🟡 **OPEN — deferred out of T3-06 (2026-07-15).** · **Owner:** backend / deployment · **Priority:** low *today* (the port is not internet-reachable and the endpoints are now authenticated); revisit if `/api/grievance/*` is ever proxied publicly.
> **Origin:** T3-06 step 4 ([`../05-grievance-api-hardening-spec.md`](../05-grievance-api-hardening-spec.md)) makes rate limiting optional — *"Only if there is an existing mechanism to reuse. **If dropped, log the deferral** … the §6 audit-chokepoint argument cites rate-limiting, so its absence must stay visible rather than being quietly dropped from the story."* This is that log.

## The finding

`GET /api/grievance/{id}` and `POST /api/grievance/{id}/status` are unthrottled. T3-06 gave both authn (`Depends(_ticketing_auth_check)`) and gave the GET a read audit, but a holder of `TICKETING_SECRET_KEY` can still enumerate or hammer them without limit, and a brute-force against the key itself is unthrottled.

This matters beyond the endpoints themselves because [`00-reassessment.md`](../00-reassessment.md) §6 rests part of its argument on rate-limitability:

> *"**Auditability:** reads that go through `GET /api/grievance/{id}` **are** loggable, authorizable, and rate-limitable at one place."*

§6 already corrected the verb from *"are"* to *"could be"* for all three. T3-06 converted **loggable** and (partly) **authorizable** from aspiration into fact. **Rate-limitable remains aspirational.** Anyone citing the chokepoint argument in a future sprint should know that one third of it is still unbuilt.

## Why it was deferred — measured, not assumed

The ticket's condition was "only if there is an existing mechanism to reuse". There is not one that reaches these endpoints:

| Candidate | Verdict (measured 2026-07-15) |
|---|---|
| nginx `limit_req_zone` — **exists** (`deployment/nginx/webchat_rest_compose_prod.tls.conf:8-10`, zones `public` 30r/m and `uploads` 20r/m) | **Cannot reach these endpoints.** nginx has **no `location /api/grievance` block** in any conf. Traffic to `:5001` bypasses nginx entirely, so the zones never apply. Reusing it would first require proxying the endpoints publicly — the opposite of the current posture. |
| A Python limiter (`slowapi` etc.) | **Does not exist.** `grep -rin "slowapi\|ratelimit\|flask-limiter" requirements*.txt` → no hits. Adding one is a new dependency on a stable shared service, which is not "cheap". |
| In-code `rate_limit` symbols | Red herrings — outbound throttles for third-party geocode APIs (`shared_functions/reverse_geocode.py`, `map_pin_geocode.py`) and report quotas (`ticketing/services/report_limits.py`). None is a request limiter. |

## Why it is low priority today

- **Not internet-reachable.** Verified 2026-07-15 against the live AWS account (`ap-southeast-1`): security group `sg-01739221c73ab3eb1`, attached to `chatbot-main`/`chatbot-rest`, admits **80, 443, 22 (restricted), 8000, 3000 — not 5001**. See PROGRESS.md T3-06.
- **Now authenticated.** Pre-T3-06 an anonymous caller could read any grievance; the unthrottled surface is now key-holders only.
- **DOR prod is unverified** — `grm-chatbot.dor.gov.np` runs on DOR infra, not this AWS account, so its firewall could not be checked from here. See the open item in PROGRESS.md.

## Definition of done

1. Decide the posture first: are `/api/grievance/*` **internal-only** (current reality — no nginx block, port closed) or intended to be publicly proxied? The answer decides everything below; do not add a limiter without it.
2. **If internal-only** (recommended): the cheapest real control is network, not code — keep `:5001` closed at the firewall and consider binding the host mapping to `127.0.0.1` (see [`grievance-api-host-port-binding.md`](grievance-api-host-port-binding.md)). Then close this item as *won't-do*, and amend §6's chokepoint argument to stop citing rate-limiting.
3. **If ever publicly proxied:** add a `location /api/grievance` block reusing the existing `public` zone — at that point the mechanism *does* exist and this becomes cheap.
4. Independently of the above, consider throttling **auth failures** on `_ticketing_auth_check`; an unthrottled key check is brute-forceable regardless of network posture. This is the one piece that is not solved by keeping the port closed.
5. **Pair it with auditing the failures.** Verified 2026-07-15 against the running container: a rejected request emits **no `audit.grievance_read` record** — the dependency raises before the handler, so the audit (which is a *read* audit by design) never runs. A caller probing keys therefore leaves no trace in the audit stream; only uvicorn's access log shows the bare 401, with no principal. Unthrottled **and** unaudited is the combination that makes a brute-force cheap and invisible. If a limiter is added, emit an audit record on rejection at the same time — the two controls are worth little apart.

**Recommended trigger:** any change that puts `/api/grievance/*` behind nginx, or opens `:5001` in a security group.
