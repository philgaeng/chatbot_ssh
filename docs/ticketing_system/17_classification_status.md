# Classification status model (Option B)

**Status:** As-built (July 2026) — implemented via TP-14. Promoted from `docs/sprints/archive/June5/04-classification-status-spec.md` (locked 2026-06-03).
**Field:** `public.grievances.grievance_classification_status` (TEXT; lookup table `public.grievance_classification_statuses`, seeded from `GRIEVANCE_CLASSIFICATION_STATUS_SEED_DATA` in `backend/config/database_tables.py`)
**Code:** `backend/config/classification_status.py` (chatbot side), `ticketing/constants/classification.py` (portal side), `ticketing/services/grievance_content.py`, `ticketing/api/routers/tickets.py`, `channels/ticketing-ui/components/tickets/ClassificationGrievancePanel.tsx`
**Related:** [03_ticketing_api_integration.md](03_ticketing_api_integration.md) (§ Tickets actions), [02_ticketing_domain_and_settings.md](02_ticketing_domain_and_settings.md)

---

## 1. Purpose

One enum tracks **LLM classification progress + who validated summary/categories**:

1. A grievance can be **submitted before** classification finishes (`pending`).
2. The row **updates** when the LLM writes summary/categories (`LLM_generated`) or fails (`LLM_failed`).
3. **Complainant** validation in the chatbot review sets `complainant_confirmed`.
4. **Officer** must validate in the portal when the complainant did not — including the skip-LLM path (`LLM_skipped`).

Not used for case workflow (that is `grievance_status` / ticket `status_code`), and no longer gated on `is_temporary`.

---

## 2. Codes (active) — `backend/config/classification_status.py`

| Code | Meaning | Set by | Officer validation required? |
|---|---|---|---|
| `pending` | Default on row create; LLM not finished/started | DB default / first insert | No — wait for LLM or skip path |
| `LLM_generated` | LLM wrote summary + categories | Celery classification task | **Yes** (gate below) |
| `LLM_failed` | LLM failed after retries (no transient "retrying" code in DB) | LLM task failure path | **Yes** |
| `LLM_skipped` | User/org skipped LLM classification (replaces `slot_skipped`) | Chatbot skip path | **Yes** — officer classifies manually |
| `complainant_confirmed` | Complainant validated categories/summary in chatbot review | Chatbot review form + submit | No |
| `officer_confirmed` | Officer edited/confirmed categories + summary in portal | `PATCH /tickets/{id}/classification` | No |

`OFFICER_VALIDATION_REQUIRED = {LLM_generated, LLM_failed, LLM_skipped}` (legacy `LLM_error` also treated as requiring validation).

### Deprecated (read-compat only — never written)

| Old code | Handling (as-built) |
|---|---|
| `LLM_error` | `normalize_classification_status()` maps → `LLM_failed` |
| `slot_skipped` | normalized → `LLM_skipped` |
| `REVIEWING` | Session/slot only while editing in chatbot; DB stays `LLM_generated` until confirmed |
| `is_temporary` | Retired from app, sync, and read logic — `grievance_content.py` reads with **no** `is_temporary` filter; `grievance_sync` creates/updates by `grievance_id` presence |

---

## 3. State transitions

```text
[*] → pending
pending → LLM_generated          (LLM success)
pending → LLM_failed             (LLM final failure)
pending → LLM_skipped            (user skips LLM)

LLM_generated → complainant_confirmed   (chatbot review: Yes)
LLM_generated → officer_confirmed       (portal validate)
LLM_generated → (unchanged)             (complainant declines review — stays until officer)

LLM_failed  → officer_confirmed         (portal manual classify)
LLM_skipped → officer_confirmed         (portal manual classify)
```

No DB status exists for "Celery retry in progress" — the row stays `pending` until success or final failure. Transitions are enforced by the write paths (chatbot tasks/forms + the single portal endpoint), not by a DB constraint (unverified: no CHECK/trigger-level enforcement).

---

## 4. Portal rules (ticketing)

### Officer validation gate (as-built)

`POST /tickets/{id}/actions` with `ACKNOWLEDGE` fetches the grievance row and **rejects with 422** when `officer_validation_required(status)` — i.e. status in `LLM_generated` / `LLM_failed` / `LLM_skipped` (or legacy `LLM_error`):

> "Review and confirm the grievance summary and categories before acknowledging this ticket."

UI: `ClassificationGrievancePanel.tsx` shows an amber **"Review required before acknowledge"** panel for those statuses; green "Validated by complainant/officer" badge for confirmed statuses. Any officer with ticket access can validate (same as TP-14).

### Officer confirm — `PATCH /api/v1/tickets/{id}/classification`

One endpoint (`validate_ticket_classification` in `ticketing/api/routers/tickets.py`) atomically:

1. Writes `grievance_summary`, `grievance_categories`, `grievance_classification_status = officer_confirmed` to `public.grievances` (via `patch_grievance_classification` backend call — failure → 502, nothing cached).
2. Updates the `ticketing.tickets` non-PII cache (summary/categories).
3. Appends a `CLASSIFICATION_VALIDATED` ticket event (actor + field diff payload).
4. **Re-resolves the workflow** if the category edit changes the matching `project_workflows` binding (note event: "Workflow re-resolved after officer classification update").

Category options come from the taxonomy: `GET /api/v1/reference/grievance-categories` (`public.grievance_classification_taxonomy`).

---

## 5. Hybrid sync (list vs detail)

| Layer | Rule (as-built) |
|---|---|
| Detail GET | Merges `public.grievances` + `ticketing.tickets` cache via `ticketing/services/grievance_content.py`; status normalized (`slot_skipped`→`LLM_skipped`, `LLM_error`→`LLM_failed`); never filters `is_temporary` |
| List / queue | Reads the ticket cache, warmed by forward sync |
| Forward sync | Celery `sync_grievances` (every 2 min) UPDATEs existing tickets when grievance summary/categories/location change (Option A — see `03_ticketing_api_integration.md` §1.2) |

---

## 6. GRM export mapping (`backend/config/grm_config.py` — `GRM_STATUS_MAPPING`)

| Classification status | GRM `processing_status` |
|---|---|
| `pending`, `LLM_generated`, `LLM_failed`, `LLM_skipped` | `pending` |
| `complainant_confirmed` | `submitted` |
| `officer_confirmed` | `under_evaluation` |
