# T3-06 — Harden the grievance API (authn + authz + read audit + contract) (M)

> Workstream F · Branch `dev/tier3-structural` · **Phase 2 — pairs with T3-04; land the two together.**
> Evidence: [`00-reassessment.md`](00-reassessment.md) §6. **Read §6 first — this ticket exists because the boundary reassessment inverted a claim the whole PII workstream rested on.**
> Line numbers as of `dev/tier3-structural` @ 2026-07-15 — re-locate before editing.

---

## Why this ticket exists

The Tier-3 PII workstream was built on the premise that `GET /api/grievance/{id}` is the **single auditable PII boundary** — the one chokepoint where grievance reads are authenticated, authorized, logged and rate-limitable. That premise was never checked against the code.

**It is false on all four counts.** Measured 2026-07-15:

| Property | `GET /api/grievance/{id}` | Ticketing's *"violating"* direct SQL read |
|---|---|---|
| Authn | **none** | Keycloak JWT (`routers/tickets/crud.py:430`) |
| Authz | **none** | `assert_ticket_visibility` — SEAH + jurisdiction (`crud.py:446`) |
| Read audit | **none** | `REVEAL_ORIGINAL` events (`routers/tickets/pii.py:124-141`) |
| Response contract | **none** (`SELECT g.*` → untyped dict) | pinned 9-column `text()` select |

The endpoint that was supposed to be the boundary is the *least* protected path to grievance data in the system. **Until this ticket lands, "route reads through the grievance API" is not an option** — it would be a net security regression (§6). This ticket is the prerequisite that makes that conversation possible later. It does not itself move any read.

**Scope note.** This is a `backend/` security ticket, not an architecture ticket. It does **not** migrate `grievance_content.py`, does **not** touch the boundary policy (that is T3-07), and does **not** remove ticketing's direct reads — those are now legitimized as-built per §6's decision.

---

## ⚠️ Blast radius — stable shared service

`backend/api/routers/grievance.py` serves the **live chatbot** and the **officer portal**. Adding auth to an endpoint that currently has none **will** break every caller that doesn't send a key. CLAUDE.md §Service boundaries: *"stable shared services — modify only with clear intent + tests."*

**Enumerate every caller before writing the first line.** Known at 2026-07-15:

| Caller | Site | Sends `x-api-key` today? |
|---|---|---|
| ticketing → `GET /api/grievance/{id}` | `ticketing/clients/grievance_api.py:46` | **verify** — `clients/backend_auth.py` exists; confirm it is applied to the GET, not just the PATCHes |
| ticketing → `POST /api/grievance/{id}/status` | `ticketing/clients/grievance_api.py:76`; callers `engine/ticket_actions.py:31`, `services/archiving.py:247,312` | **verify** |
| chatbot internal | grep `backend/` for direct `grievance_manager.get_grievance_by_id` — **~20 non-test callers** (see [`03-pii-boundary-spec.md`](03-pii-boundary-spec.md) §Blast radius) | n/a — in-process, not via HTTP |
| portal (browser) | must **never** call this directly — PII is brokered via `GET /tickets/{id}/pii` | n/a |

- [ ] **Grep the full HTTP caller list yourself and record it in PROGRESS.md before commit 1.** The table above is a starting point, not an inventory.
- [ ] Confirm no browser/webchat JS calls `/api/grievance/*` directly (if any does, auth breaks it — that is a finding, log it).

---

## Order (BINDING)

Auth first would break callers before they can authenticate. Contract first is inert and safe.

```
1. CONTRACT   — response_model on the GET. Inert; no behavior change.
2. AUDIT      — read-audit record. Inert; additive.
3. AUTHN      — GET + POST /status behind _ticketing_auth_check, AFTER
                every caller is confirmed to send the key.
4. RATE LIMIT — optional; only if cheap. Log a deferral if dropped.
```

---

## Step 1 — response contract (commit 1)

`get_grievance` (`backend/api/routers/grievance.py:249-250`) has **no `response_model`**; the payload is whatever `SELECT g.*` returned (`grievance_manager.py:154-167`), passed through verbatim at `:264-274`.

- [ ] Pydantic v2 response model for `GET /api/grievance/{id}`. **The 9 fields `ticketing/services/grievance_content.py:22-35` selects are load-bearing** — `grievance_id`, `grievance_summary`, `grievance_categories`, `grievance_description`, `grievance_location`, `grievance_classification_status`, `grievance_high_priority`, `grievance_sensitive_issue`, `grievance_modification_date`. All 9 are confirmed present today via `g.*` (`migrations/public/versions/pub000_public_core_baseline.py:499-523`).
- [ ] **Do not narrow the payload in this commit.** ~20 in-process callers + the portal read this shape. Model it as-is; log anything that looks vestigial rather than dropping it.
  > `SELECT g.*` means the response shape is defined by the table. A `response_model` that omits a column silently drops it from the API. Enumerate against `pub000` before asserting a field is unused.
- [ ] Schema-drift test: the model's fields exist in `public.grievances`. Mirrors the CL-01 schema-baseline gate pattern.

## Step 2 — read audit (commit 2)

- [ ] A read-audit record for `GET /api/grievance/{id}`: grievance_id, caller identity, timestamp, outcome. **`grep -il audit backend/` currently returns exactly one file** (`postgres_services.py`), and `base_manager.py:760`'s `log_grievance_change` is **write-only** — there is no read-audit table in `backend/`. Decide: extend `public.*` (needs a `migrations/public/` revision — chatbot stream, per CLAUDE.md §Migration traceability) or emit structured logs only.
  > **Recommendation: structured log first, table later.** A log line is reversible and unblocks the ticket; a new `public.*` table is a migration-stream commitment. Record the decision in PROGRESS.md either way.
- [ ] Caller identity must be *in* the record. An audit trail that says "someone read GRV-x" is not an audit trail. This is why step 3 (authn) and step 2 are coupled — until callers are identified, the record can only say "an api-key holder".
- [ ] `LOG_LEVEL=INFO` is the deployed default (`env.local:23`) — **`self.logger.debug` will not emit** (`grievance_manager.py:172` is invisible in prod today). Audit must log at `info` or above, and a test must assert it emits at the deployed level.

## Step 3 — authn (commit 3) — the breaking change

`_ticketing_auth_check` (`grievance.py:77-100`) already exists: `x-api-key` vs `TICKETING_SECRET_KEY`/`MESSAGING_API_KEY`, fail-closed except under `APP_ENV=dev` + `AUTH_MODE=bypass`. It is applied to `PATCH /classification` (`:283-288`) and `PATCH /complainant` (`:329-334`) — **2 of 5 endpoints**.

- [ ] `GET /api/grievance/{grievance_id}` (`:249`) → `Depends(_ticketing_auth_check)`.
- [ ] **`POST /api/grievance/{grievance_id}/status` (`:202-203`) → `Depends(_ticketing_auth_check)`.** This one is the most serious: unauthenticated, it **mutates grievance state and fires SMS + email to the complainant** (`:227` → `_send_status_update_notifications`). An anonymous caller can drive a complainant's notification stream.
- [ ] Every caller confirmed sending the key **before** this commit lands (step 0's inventory). A caller that 401s here is an outage.
- [ ] `AUTH_MODE=bypass` still works for dev — do not break the local loop.
- [ ] Tests: 401 without key / 200 with key, on **both** endpoints. **Verified red pre-fix** (the HR-04 standard) — i.e. assert the 401 test fails on today's code, because today it returns 200.

## Step 4 — rate limit (optional)

- [ ] Only if there is an existing mechanism to reuse. **If dropped, log the deferral** (`followups/` + TODO.md row, per the standing rule) — the §6 audit-chokepoint argument cites rate-limiting, so its absence must stay visible rather than being quietly dropped from the story.

---

## Exposure — verify before closing

Both endpoints are bound to the host at `docker-compose.grm.yml:117` (`5001:5001`). Prod nginx has **no** `location /api/grievance` block (only `/api/v1/` → ticketing, `webchat_rest_compose_prod.conf`), so they are not proxied to the internet.

- [ ] **Check the staging + prod EC2 security groups for inbound :5001.** This is the difference between "internal-only misconfiguration" and "unauthenticated PII read exposed to the internet". It cannot be determined from the repo. **Record the answer in PROGRESS.md** — if :5001 is open, this ticket is Phase 1, not Phase 2, and should be treated as an incident.
- [ ] Consider dropping the `5001:5001` host mapping from the **prod** overlay if nothing needs it (`docker-compose.grm.yml:112-114`'s own comment says it exists so *"the host browser can reach /api/grievance/*"* — a dev convenience).

---

## Tests (acceptance)

- [ ] 401-without-key / 200-with-key on `GET /api/grievance/{id}` and `POST /api/grievance/{id}/status` — **verified red pre-fix**.
- [ ] Audit record emitted at the deployed log level, containing caller identity + grievance_id.
- [ ] `response_model` drift test against `public.grievances`.
- [ ] Full `tests/backend` green vs baseline.
- [ ] Full `tests/actions` + `tests/orchestrator` green (baseline: **173 passed / 1 skipped**) — the ~20 in-process callers must be unaffected.
- [ ] Full `tests/ticketing` green (baseline: **545 passed / 5 skipped / 0 xfailed**) — ticketing's HTTP clients must still authenticate.

## Manual verification

- [ ] Chatbot: file a grievance end-to-end, then status-check it. The status flow calls `POST /api/grievance/{id}/status` — the endpoint that just gained auth.
- [ ] Officer portal: ticket detail renders; acknowledge works (`ticket_actions.py:31` → `POST /status`); resolve works (archiving paths `:247,312`).
- [ ] `curl` the GET with no `x-api-key` ⇒ **401**. This is the check the ticket exists for.

---

## Relationship to the other tickets

- **T3-04** (PII boundary) is independent and unblocked — it moves *decryption*, not the retrieval path. Land them in either order; they touch different functions in the same file (`grievance_manager.py`), so expect a trivial merge.
- **T3-07** (boundary policy) is independent — it amends docs and adds guard tests.
- **Neither this ticket nor T3-07 migrates any read.** Per §6's decision, ticketing's direct `public.*` reads are legitimized as-built. This ticket only makes the *option* of routing them through the API real for a future sprint — it does not exercise it.
