# Follow-up — ticketing reads `public.*` directly via its own DB session

> **Status:** 🔴 **OPEN — deferred out of T3-04 (2026-07-15).** · **Owner:** ticketing · **Priority:** medium (architectural/auditability, not a live defect — the reads are correct and parameterized; they violate the locked data rules and defeat the "single auditable boundary" goal)
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
