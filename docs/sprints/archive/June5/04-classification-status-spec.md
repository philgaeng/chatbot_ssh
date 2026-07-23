# Classification status model (Option B) — locked 2026-06-03

**Field:** `public.grievances.grievance_classification_status` (TEXT, lookup `grievance_classification_statuses`)

**Not used for this lifecycle:** `is_temporary` (retire from app/sync/read logic), `grievance_status` / `grievance_status_history` (case workflow: `SUBMITTED`, `UNDER_EVALUATION`, …).

**Parent tickets:** TP-14 in [`03-portal-p1-spec.md`](03-portal-p1-spec.md), brief in [`voice-notes-and-ux-feature-brief.md`](../voice-notes-and-ux-feature-brief.md) § TP-14.

---

## Purpose

One enum tracks **LLM classification + who validated summary/categories**:

1. Grievance can be **submitted before** classification finishes (`pending`).
2. Row **updates** when LLM writes summary/categories (`LLM_generated`) or fails (`LLM_failed`).
3. **Complainant** validation sets `complainant_confirmed` (chatbot review Yes / equivalent).
4. **Officer** must validate when complainant did not, including skip-LLM path (`LLM_skipped`).

---

## Allowed codes (active)

| Code | Meaning | Set by | Officer validation required? |
|------|---------|--------|------------------------------|
| `pending` | **Default** on row create. Intake may be submitted; LLM not finished or not started. | DB default / first insert | No — wait for LLM or skip path |
| `LLM_generated` | LLM wrote summary + categories (may be empty partial — treat as “needs review” if no content). | Celery `classify_and_summarize_grievance_task` | **Yes**, when officer works ticket (see gate below) |
| `LLM_failed` | LLM failed after retries (no transient “retrying” code in DB). | LLM task failure path | **Yes** |
| `LLM_skipped` | Complainant/org chose **skip LLM** entirely (replaces `slot_skipped`). | Chatbot when user skips classification | **Yes** — officer must classify manually |
| `complainant_confirmed` | Complainant validated categories/summary in chatbot review. | Chatbot review form + persist on submit/update | **No** |
| `officer_confirmed` | Officer edited/confirmed categories (+ summary per TP-14) in portal. | Portal `VALIDATE_CLASSIFICATION` / PATCH | **No** |

### Deprecated (do not write new rows)

| Old code | Action |
|----------|--------|
| `LLM_error` | Do not store during Celery retry; on final failure use `LLM_failed` |
| `slot_skipped` | Rename usage → `LLM_skipped` |
| `REVIEWING` | **Session/slot only** while editing in chatbot; DB stays `LLM_generated` until confirmed |
| `is_temporary` | Stop reading/writing in application code |

### Backward compatibility (one release)

- Readers accept legacy `LLM_generated` / `slot_skipped` / `pending` on old rows.
- Migration script: `slot_skipped` → `LLM_skipped`; optional `LLM_error` → `LLM_failed`.
- Update `GRIEVANCE_CLASSIFICATION_STATUS_SEED_DATA` and `grm_config.GRM_STATUS_MAPPING`.

---

## State transitions

```text
[*] → pending
pending → LLM_generated     (LLM success)
pending → LLM_failed        (LLM final failure)
pending → LLM_skipped       (user skips LLM)
pending → complainant_confirmed  (only if review completes without LLM — edge; prefer LLM_skipped)

LLM_generated → complainant_confirmed   (chatbot review Yes)
LLM_generated → officer_confirmed       (portal)
LLM_generated → (unchanged)             (complainant declined review / skip review — stays until officer)

LLM_failed → officer_confirmed          (portal manual classify)
LLM_skipped → officer_confirmed         (portal manual classify)

complainant_confirmed → officer_confirmed  (optional re-review — out of scope P1 unless product asks)
```

**No DB status for Celery retry in progress** — row stays `pending` until success (`LLM_generated`) or final failure (`LLM_failed`).

---

## Portal / ticketing rules

### When officer validation is required

Officer must **review, edit if needed, and confirm** (sets `officer_confirmed`) when:

```text
grievance_classification_status IN ('LLM_generated', 'LLM_failed', 'LLM_skipped')
```

and the officer is handling the ticket (product: **at assignment** and **before Acknowledge**).

| Status | UI |
|--------|-----|
| `complainant_confirmed` | Green badge “Validated by complainant”; Acknowledge allowed (other TP gates apply). |
| `officer_confirmed` | Green badge “Validated by officer”; Acknowledge allowed. |
| `LLM_generated` / `LLM_failed` / `LLM_skipped` | Amber **Review & confirm** panel; **Acknowledge disabled** until `officer_confirmed`. |
| `pending` | Show description; summary/categories may be empty; no officer classification gate until LLM completes or `LLM_skipped` / failure. |

### Who can validate

Any officer with ticket access (assignee, supervisor, informed, observer) — same as TP-14.

### Persist on officer confirm

1. `public.grievances`: `grievance_summary`, `grievance_categories`, `grievance_classification_status = officer_confirmed`
2. `ticketing.tickets`: cache summary/categories (and description if cached)
3. `ticketing.ticket_events`: e.g. `CLASSIFICATION_VALIDATED` with actor + optional field diff

---

## Chatbot write paths (implementation)

| Event | `grievance_classification_status` | Also |
|-------|-----------------------------------|------|
| Row created | `pending` | Default column |
| LLM task success | `LLM_generated` | Update summary, categories |
| LLM task final fail | `LLM_failed` | |
| User skips LLM | `LLM_skipped` | Replaces `slot_skipped` |
| Review: categories Yes | `complainant_confirmed` | Persist in `action_update_grievance_categorization` **and** final submit |
| Review: user declines review | Stays `LLM_generated` | Officer validates later |
| Final submit | Persist slot status to column | `dispatch_ticket` loads summary/categories from DB if slots empty |

**Remove:** setting `is_temporary = false` as sync gate; `grievance_sync` creates/updates by `grievance_id` not in `ticketing.tickets` (no `is_temporary` filter).

---

## Data read / sync (TP-14)

| Layer | Rule |
|-------|------|
| Detail GET | Merge `public.grievances` + `ticketing.tickets` cache; never filter `is_temporary`. |
| List / queue | Hybrid: cache on ticket, warmed by forward sync (&lt;2 min after LLM). |
| Forward sync | UPDATE existing tickets when grievance summary/categories/status change. |
| Backfill | One-time SQL/AWS for tickets with empty cache (e.g. `B-GR-20260602-KOJH-5491`). |

---

## GRM export mapping (update `grm_config.py`)

| Classification status | GRM `processing_status` |
|----------------------|-------------------------|
| `pending` | `pending` |
| `LLM_generated`, `LLM_failed`, `LLM_skipped` | `pending` |
| `complainant_confirmed` | `submitted` |
| `officer_confirmed` | `under_evaluation` |

---

## Acceptance (classification slice)

- [ ] New grievance row defaults to `pending`.
- [ ] After LLM, status is `LLM_generated` (not left `pending` if summary exists).
- [ ] Skip-LLM path sets `LLM_skipped`, not `slot_skipped`.
- [ ] Complainant Yes sets `complainant_confirmed` in **DB**, not slots only.
- [ ] Portal blocks Acknowledge for `LLM_generated` / `LLM_failed` / `LLM_skipped`; allows after `officer_confirmed`.
- [ ] Officer confirm sets `officer_confirmed` + audit event.
- [ ] No new rows written with `LLM_error` or `is_temporary` driving sync.
