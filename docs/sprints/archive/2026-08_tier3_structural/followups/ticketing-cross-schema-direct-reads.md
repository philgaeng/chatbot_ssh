# Follow-up — ticketing reads `public.*` directly via its own DB session

> # ✅ CLOSED 2026-07-15 — RESOLVED BY DECISION, NOT BY FIX
>
> **The rule this document prosecutes was retired.** The reads are **legitimized as-built**. Do not implement anything below.
>
> **This document's DoD item 1 asked for an explicit locked-architecture decision. It was taken** (project owner, 2026-07-15), on evidence gathered after this doc was written: [`../00-reassessment.md`](../00-reassessment.md) **§6**. Outcome:
> 1. **"No SQL joins from `ticketing.*` into `public.*`" is DROPPED** → re-expressed as an enumerated, drift-guarded read/write contract.
> 2. **"No cross-schema FK" is KEPT** and pinned by a test.
> 3. **"No complainant PII columns in `ticketing.*`" is KEPT** and pinned by a test.
>
> → Implemented by **T3-07** ([`../06-boundary-policy-spec.md`](../06-boundary-policy-spec.md)). Prerequisite for ever revisiting option (a)/(c): **T3-06** ([`../05-grievance-api-hardening-spec.md`](../05-grievance-api-hardening-spec.md)).
>
> ## Three things this document got wrong — read before trusting any of it
>
> 1. **The inventory is short by 8.** Measured surface is **11 statements / 5 tables / 3 writes**, not 3 reads. It missed `services/archiving.py:168,196` (incl. an `UPDATE public.file_attachments`), `engine/ticket_actions.py:134`, `services/grievance_categories_catalog.py:90,147,148` (incl. an **unqualified `DELETE FROM public.grievance_classification_taxonomy`**), and — most tellingly — that `tasks/grievance_sync.py:178` **`LEFT JOIN`s `public.complainants`**, the one table the original spec marked *"never touch"*, every 2 minutes.
> 2. **§Why this matters → "Auditability" is inverted.** It asserts reads via `GET /api/grievance/{id}` *"**are** loggable, authorizable, and rate-limitable at one place."* **None of the three is implemented.** That endpoint has **no authn, no authz, no audit** (`backend/api/routers/grievance.py:249-250`); the direct SQL it condemns sits behind Keycloak JWT + `assert_ticket_visibility`'s jurisdiction gate + an audit event model. **Executing option (a) or (c) as written would have been a security downgrade** — and would have converted a PII-free query into a PII-bearing one.
> 3. **DoD item 2 is already done.** The API serves **9/9** of the fields `grievance_content.py` selects (`SELECT g.*`), and `services/resolved_summary_builder.py:139-150` **already** reads `grievance_description` over HTTP. Nothing needed building. What is actually missing is a `response_model` — so migrating would have *weakened* drift protection.
>
> **Retained below, unedited, as the record of a finding that was right to raise and wrong in its prescription.** The instinct — "the docs say one thing and the code does another" — was correct; §Endgame called the resolution exactly right, and it resolved toward *amend*, not *enforce*.
>
> ## ✅ T3-07 landed 2026-07-15 — what this document's DoD became
>
> | This doc's DoD | Outcome |
> |---|---|
> | **1.** Decide the boundary policy — "escalate before starting" | ✅ **Escalated and decided** by the project owner (§6 → DECISION). Outcome was **(b)**, not the recommended **(c)**: option (c) would have routed `grievance_description` through an API with **no authz** — a downgrade, not the hardening it was meant to be. **This item was the doc's best call.** |
> | **2.** If (a)/(c): extend the API, migrate callers, delete `_GRIEVANCE_SELECT` | ❌ **Not done — correctly.** Already satisfied (9/9 fields ship), and not desirable: see D-38. `_GRIEVANCE_SELECT` stays. |
> | **3.** If (b)/(c): document the contract, add a schema-drift test, amend CLAUDE.md | ✅ **Done.** Contract → [`../../../ticketing_system/03_ticketing_api_integration.md`](../../../../ticketing_system/03_ticketing_api_integration.md) §3b + CLAUDE.md §Data rules rule 1. Drift test → `tests/ticketing/test_boundary_policy.py`, mutation-verified in both directions. **"An undocumented exception to a LOCKED rule is worse than a documented one" — this doc's own line, and the reason the ticket existed.** |
> | **4.** Fold in the `grievance_sync.py` column-list TODO row | ✅ **Done** — absorbed by the same drift guard; TODO row closed. |
> | **5.** Re-verify HR-02's authz matrix if the `file_attachments` path moves | ➖ **Moot** — the path did not move. HR-02's `require_file_access` gate is untouched, which is precisely what option (b) preserves. |
>
> **The rules that survived are now enforced rather than asserted:** no cross-schema FK and no complainant PII columns, both pinned by tests that are proven to go red.

---

> **Status:** ~~🔴 OPEN — deferred out of T3-04 (2026-07-15).~~ **CLOSED — see above.** · **Owner:** ticketing · **Priority:** ~~medium~~ n/a
> **Origin:** Tier-3 reassessment ([`../00-reassessment.md`](../00-reassessment.md) §3). Surfaced while refuting the review's "PII decryption still dual-pathed" claim. **The review never flagged these — and they violate the data rules more than the `pii_vault` it did flag.**

## The finding

CLAUDE.md §Data rules (LOCKED) states:

> 1. No SQL joins from `ticketing.*` into `public.*`
> 2. No foreign keys from `ticketing.*` into `public.*`
> 5. Officer detail view fetches PII fresh via `GET /api/grievance/{id}`

Ticketing nonetheless reads `public.*` tables **directly through its own SQLAlchemy session**, bypassing the grievance API entirely:

### 1. `public.grievances` — including the raw narrative

`ticketing/services/grievance_content.py:22-38`:

```python
_GRIEVANCE_SELECT = text("""
    SELECT
        grievance_id, grievance_summary, grievance_categories,
        grievance_description,          # <-- the raw complainant narrative
        grievance_location, grievance_classification_status,
        grievance_high_priority, grievance_sensitive_issue,
        grievance_modification_date
    FROM public.grievances
    WHERE grievance_id = :grievance_id
""")

def fetch_grievance_row(db: Session, grievance_id: str) -> Optional[dict[str, Any]]:
    row = db.execute(_GRIEVANCE_SELECT, {"grievance_id": grievance_id}).mappings().first()
```

**Callers:** `ticketing/engine/ticket_actions.py:210`, `ticketing/api/routers/tickets/crud.py:469`.

`grievance_description` is the complainant's raw narrative — the most sensitive free-text field in the system, and the one most likely to contain self-disclosed PII regardless of the column-level encryption applied to the four `ENCRYPTED_FIELDS`.

### 2. `public.file_attachments`

- `ticketing/api/routers/tickets/files.py:91`
- `ticketing/api/ticket_access.py:167`

**Note:** HR-02's `require_file_access` was **deliberately built on** this read — chatbot files in `public.file_attachments` map to a ticket via `grievance_id` (see `2026-07_hardening/01-auth-hardening-spec.md` §2.2). So this one is load-bearing for an authorization gate and must not be casually removed.

## Why this matters

- **It is the real "single auditable PII boundary" gap.** T3-04 unifies *decryption*, which is genuinely worth doing — but the review's stated goal ("Restores the single auditable PII boundary") is **not met** by T3-04 alone, because ticketing still reaches into `public.*` for content on two other paths. T3-04's spec says so explicitly and its summary must not overclaim.
- **Auditability:** reads that go through `GET /api/grievance/{id}` are loggable, authorizable, and rate-limitable at one place. A raw `text()` select against `public.grievances` from ticketing's session is none of those.
- **Coupling:** the hardcoded column list is the same fragility already tracked for `grievance_sync.py` in TODO.md ("will break if public schema column names change"). This is a second instance of that class.
- **Schema ownership:** CLAUDE.md's three-stream migration policy assumes `public.*` DDL is invisible to ticketing. These reads make ticketing silently dependent on `public.*` column names, without a migration-stream relationship to enforce it.

## Why it was deferred out of T3-04

- **Different concern.** T3-04 is about *decryption responsibility* (who holds `DB_ENCRYPTION_KEY`). This is about *retrieval path*. Conflating them doubles T3-04's risk while it is already touching a stable shared service with ~20 callers.
- **Different blast radius.** The `file_attachments` read underpins HR-02's authorization gate; changing it means re-verifying an 86-test authz matrix. That is its own ticket.
- **T3-04 is already order-critical.** Its four commits have a strict sequence with a silent-outage failure mode (see [`../03-pii-boundary-spec.md`](../03-pii-boundary-spec.md) §Order). Adding scope to it is the wrong trade.

## Measured inventory (2026-07-15)

| Site | Table | Fields | Callers | Notes |
|---|---|---|---|---|
| `services/grievance_content.py:22-38` | `public.grievances` | 9 incl. `grievance_description` | `engine/ticket_actions.py:210`, `routers/tickets/crud.py:469` | Raw narrative. No API equivalent currently used by these callers. |
| `routers/tickets/files.py:91` | `public.file_attachments` | — | (endpoint) | |
| `api/ticket_access.py:167` | `public.file_attachments` | — | `require_file_access` | **Load-bearing for HR-02's authz gate.** |
| `tasks/grievance_sync.py` | `public.grievances` | hardcoded column list | (Celery beat) | Already tracked separately in TODO.md 🔵 TECH DEBT. **Arguably in the same family — consider folding into this ticket's scope.** |

**No SQL-injection surface:** all reads are parameterized (`:grievance_id`), consistent with the review's finding of zero injection surface in ~72k LOC. This is an architecture finding, not a security defect.

## Definition of done

1. **Decide the boundary policy first — this is a design decision, not a mechanical one.** Options:
   - **(a)** Route all `public.*` content reads through the grievance API (strictest; honors the locked rules; costs an HTTP hop on `ticket_actions` and `crud` hot paths, and needs an API surface for the fields `grievance_content` selects).
   - **(b)** Accept a **read-only, explicitly-documented** `public.*` read contract for non-PII content, with an owned interface (a single module, a pinned column contract, a schema-drift test) — i.e. legitimize what exists, but make it auditable and drift-guarded.
   - **(c)** Hybrid: API for narrative/PII-bearing content (`grievance_description`), documented direct read for file metadata (preserving HR-02's gate).
   > **Recommendation: (c).** It removes the genuinely sensitive path, keeps HR-02's authz gate intact, and doesn't pay an HTTP hop for file-metadata lookups. But this is a locked-architecture question — **it needs an explicit decision, not an implementer's judgment call.** Escalate before starting.
2. If (a) or (c): extend the grievance API to serve what `grievance_content.py` needs, migrate the 2 callers, delete `_GRIEVANCE_SELECT`.
3. If (b) or (c): document the contract in `docs/ticketing_system/03_ticketing_api_integration.md`, add a schema-drift test (mirrors the CL-01 schema-baseline gate pattern), and amend CLAUDE.md's data rules to state the exception explicitly — **an undocumented exception to a LOCKED rule is worse than a documented one.**
4. Fold in the `grievance_sync.py` hardcoded-column-list TODO row (same family).
5. Re-verify HR-02's authz matrix (86 tests) if the `file_attachments` path moves.

## Endgame

Either the locked data rules hold and are enforced by tooling, or they are amended to describe what is actually built. **Today the docs say one thing and the code does another** — which is the state the devil's-advocate review exists to catch, and which it missed here. Whichever way this is decided, the outcome is that `CLAUDE.md` and the code agree.
