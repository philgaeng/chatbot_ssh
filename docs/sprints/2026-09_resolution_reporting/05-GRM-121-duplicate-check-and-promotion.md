# `GRM-121` — nothing stops an admin creating the same resolution action twice

**Origin:** user request (owner, Q-07, 2026-09-15) · **Lane:** `resolution-reporting` · **Reported:** 2026-09-15
**Design:** [`DESIGN-resolution-reporting.md`](DESIGN-resolution-reporting.md) §3.1.1 ·
**Wireframe:** [`ui/08_resolution_actions_catalog.html`](../../ticketing_system/ui/08_resolution_actions_catalog.html) frame 2b, and frame 5's *checking* row

> Split from `GRM-119` on 2026-09-15. The owner's words (Q-07): *"a balance between letting users
> naturally grow the list and crazy creation of duplicates — in the best case an agent can manage that
> and check new entries against what is already in the list and judge whether it justifies an addition
> or recommend an existing one."*
>
> **Simplified 2026-09-15 by the owner's wireframe review (Q-10) — size M → S.** The check has **two
> outcomes, not four**: a similar action exists (*Use it* / *Create anyway*), or it does not. Gone:
> widening another office's action, the audited reason prompt, cross-ministry duplicate lists and
> merge (merge and clean-up → `GRM-123`). Added: the check **pre-fills what a local action counts as
> nationally**. Two things now keep duplicates from hurting: a workflow offers at most 8 actions, and
> every local action counts as a shared one, so DOR's totals are right even when a duplicate slips
> through.

## Kind

**`feature`** — question 1: no live spec describes a similarity check.

## Profile

| ✓ | Question | Fires |
|---|---|---|
| ✔ | Changes user-visible behaviour | `G-PRODUCT` · `G-SPEC` · `G-VERIFY` |
| ✔ | A UI surface changes shape | `G-DESIGN` — the suggestion inside `GRM-119`'s dialog; `ui/08` frame 2b |
| ✗ | Schema changes | — |
| ✔ | PII · auth · SEAH · complainant channel · new egress | `G-SENSITIVE` — **a new LLM call** (egress), and cross-organization isolation of what it is shown |
| ✔ | API or event shape changes | `G-CONTRACT` — one new endpoint |
| ✔ | Deployed | `G-RELEASE` |
| ■ | always | `G-TEST` |

> **profile:** `UI feature` +CONTRACT **+SENSITIVE** · **gates:** PRODUCT · DESIGN · SENSITIVE · CONTRACT · SPEC · TEST · VERIFY · RELEASE
> **model:** Opus · **size:** S

## Blocked by

**`GRM-119` merged** — the create/edit dialog and its endpoints.

## The change

### 1. The check

`POST /workflows/{id}/resolution-actions/check` `{label, default_wording, exclude_code?}` →

```jsonc
{
  "similar": { "code": "ROAD_REPAIRED", "label": "Hazard repaired" },   // or null
  "national_suggestion": { "code": "ROAD_REPAIRED", "label": "Hazard repaired" },   // or null
  "method": "model" | "text_similarity"
}
```

- **`similar`** — at most **one** action, chosen **only among the actions this workflow can use**
  (owned by its organization or above, active). Selecting it needs no change to anything, so the
  dialog can always offer **Use "…"**. ⚠ **Never** actions outside that set — a model shown another
  ministry's catalog leaks it through its suggestions. The server builds the candidate list; the client
  cannot widen it.
- **`national_suggestion`** — the best match among the **shared actions of the workflow's ministry**,
  used to pre-fill *In national reports, count this as*. `null` when the workflow's organization is the
  ministry (no field to fill).
- **The admin decides; the check never blocks.** *Create anyway* creates. Each override is written to
  `admin_audit_log` with the suggestion it passed over — automatically, with no reason prompt.
- **Edit runs the same check** (`exclude_code` = itself): renaming *Drain cleaned* into *Culvert
  cleared* is a duplicate made by another door. There is nothing to *use* from the edit dialog, so a
  match shows as a warning — *"Close to 'Culvert cleared'"* — and *Save* still works.

### 2. The model call

- A task key in [`backend/config/llm_config.py`](../../../backend/config/llm_config.py) —
  `resolution_action_dedup` — resolved with `model_for(...)`. **No model name at the call site**
  (pinned by `tests/backend/test_llm_config_pins.py`).
- **Input:** the proposed label + wording and the candidates' labels + wording. Institutional text
  only: no case data, no names, no location. The output names at most one candidate code for each of
  the two answers; a code **not among the candidates** is discarded and treated as a failure.
- ⚠ **Degrades, never fails.** Provider disabled, down, slow past its deadline, or output invalid →
  `method: "text_similarity"`: normalised token overlap picks the answers, or none. **The dialog looks
  the same either way** — no "check unavailable" state for an admin to interpret. Authoring must never
  depend on an external provider being up.
- Runs synchronously in the request with the ticketing LLM deadline; the Create button shows
  *Checking…* and the dialog stays open.

## Files it may touch

- `backend/config/llm_config.py` · `.env.example` (generated from it)
- `ticketing/services/resolution_dedup.py` *(new)* · `ticketing/services/resolution_catalog.py`
- `ticketing/api/routers/workflows.py` (or `routers/resolution_actions.py`) · `ticketing/api/schemas/resolution_action.py`
- `channels/ticketing-ui/components/settings/resolution/ResolutionActionDialog.tsx` · `lib/api.ts`
- Specs (G-SPEC, same PR): `12` (*Resolution actions* — the check) · `docs/services/` LLM task inventory if one lists task keys

## Gates — evidence

- **G-SENSITIVE** —
  - a PD-ADB workflow's check never includes a sibling office's or another ministry's action — asserted on the **candidate list sent to the model**, not only on the response
  - `national_suggestion` is always a shared action of the workflow's own ministry
  - the model input contains no field outside label and wording (test on the built prompt)
  - with the provider disabled, create and edit still succeed
- **G-TEST** — output parsing, including a hallucinated code (→ discarded, text similarity used);
  text-similarity ordering; `similar` null when nothing is close; `national_suggestion` null on a
  ministry-owned workflow; an override writes one audit row naming the passed-over code.
- **G-VERIFY** — e2e with the model stubbed: on a PD-ADB workflow, type *Pothole filled* → see *Hazard
  repaired* suggested and the national field pre-filled → *Use it* adds it; *Create anyway* creates
  *Pothole filled* counting as *Hazard repaired*, and the audit row exists. One manual run against the
  real provider, recorded in the PR.

## Non-goals

Widening or re-owning another office's action. Cross-ministry duplicate lists, merge, clean-up
(`GRM-123`). A reason prompt. Checking *officers'* free text. Auto-applying a suggestion. Translating
labels. Storing check results.

## Register line

```
| `GRM-121` — nothing stops an admin creating the same resolution action twice | feature | ui-feature+CONTRACT+SENSITIVE | `blocked` | S | resolution-reporting | … |
```
