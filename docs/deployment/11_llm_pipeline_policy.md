# LLM Pipeline Policy

**Last updated:** 2026-09-04 — sprint citations folded — reasons kept inline, forks recorded in `DECISIONS.md` (lifecycle §10) · ⚠ header date backfilled; content not re-verified against the code

## How the GRM ticketing system queries LLMs, and what PII guarantees apply

> **Audience:** anyone touching the chatbot intake flow, the ticketing findings pipeline,
> or adding new LLM calls to either system.
> Read this before writing any LLM prompt that involves grievance content.

---

## Overview — two pipelines

| Pipeline | Trigger | Model — registry key (default) | Output | Owner |
|---|---|---|---|---|
| **Note translation** | Every `NOTE_ADDED` or `COMPLAINANT_MESSAGE` event | `ticket_translate` (falls back to `translate`: `gpt-4`) | `payload.translation_en` on the event | Ticketing Celery task |
| **Case findings** | Ticket RESOLVED, or manual trigger (admin) | `ticket_findings` (`gpt-4o-mini`) / `ticket_findings_seah` (`gpt-4o`) | `Ticket.ai_summary_en` + `ticket_context_cache.findings_json` | Ticketing Celery task |

> ⚠ **Corrected 2026-08-18 (DPG-12).** This table said note translation used `gpt-4o-mini`. The code
> called `gpt-4`, and had since the pipeline was written — nobody had reason to notice, because the
> model name lived in the call site and the table lived here. The row now names the **registry key**,
> which is what the code actually resolves; the parenthesised default is a convenience for the reader
> and is the only part that can go stale.

Both pipelines are implemented in `ticketing/tasks/llm.py` and `ticketing/clients/llm_client.py`.
Neither pipeline is called inline — they are always Celery async tasks so API latency is unaffected.

> **Where the model names come from (DPG-17).** Not from this document, and not from the code that
> calls the model: every model name, endpoint and timeout on **both** LLM surfaces is declared once,
> in [`backend/config/llm_config.py`](../../backend/config/llm_config.py). The table above names the
> models for the reader's benefit; the registry is what the code reads. If they ever disagree, the
> registry is right and this table is stale — `model_for("ticket_findings")` answers the question
> without ambiguity.

---

## PII boundary model

PII flows into the system in two ways: **structured fields** (name, phone, address — stored
in `public.complainants`) and **free text** (the grievance narrative — stored in
`public.grievances`).

The ticketing schema (`ticketing.*`) never stores PII by design (CLAUDE.md rule 4).
The LLM pipelines read only from `ticketing.*`. This creates a natural boundary:

> ## ✅ Reconciled 2026-08-27 (DPG-36) — this section asserted a control that did not exist
>
> Until this date the diagram below said `grievance_summary` **MUST be PII-scrubbed before storage**
> and **nothing scrubbed it.** There was no scrubber in the codebase. That is engineering rule 9 and
> it is the same failure CLAUDE.md documents at length about the decryption claim — *"this line
> claimed decryption for months before it was true"* — which produced a whole workaround subsystem
> built on a sentence.
>
> **It is true now**, and the diagram below describes what runs. What made it true is **not** the
> prompt change the old *ACTION REQUIRED* section asked for: see the note replacing it.

```
Complainant submits grievance (free text, may contain PII)
    │
    ▼ stored UNREDACTED — deliberately (Q-12b: redact at transmission, not at storage)
public.grievances.grievance_description ← the officer's record, names intact
    │
    ▼ every model call goes through call_llm(), which pseudonymises by default (DPG-33)
    ▼   redact_for_model(): phones · emails · citizenship + vehicle numbers · person names
    ▼   · settlement addresses · BOTH digit systems.  District/province deliberately kept.
LLM sees <PERSON_1>, <PHONE_1>, <ADDRESS_1> — never the values
    │
    ▼ the summary comes back built from pseudonymised text, then gets a SECOND pass (§31.4)
    ▼   _redact_generated_text() over the model's OUTPUT, before anything is persisted
public.grievances.grievance_summary ← ✅ carries no names (DPG-31/33/34)
    │
    ▼ copied at ticket creation
ticketing.tickets.grievance_summary ← what the LLM and the officer queue read
    │
    ▼
context_builder.py assembles JSON context → LLM call (pseudonymised again at the chokepoint)
    │
    ▼
findings output → Ticket.ai_summary_en
```

**The structural guarantee:** `context_builder.py` is the single place that assembles
event data for the LLM. It explicitly whitelists fields and never includes:
- `created_by_user_id` (uses `actor_role` only)
- `complainant_id` / `session_id` / `chatbot_id`
- name, phone, email, address (never stored in `ticketing.*` anyway)

**The prompt-level safety net:** `_FINDINGS_SYSTEM` in `llm_client.py` explicitly
instructs the model: *"NEVER include names, phone numbers, email addresses, or physical
addresses in output. Replace any that appear in notes with role descriptors."*
This is a fallback — it does not substitute for source-level scrubbing.

---

## Chatbot-side requirements — ✅ BUILT 2026-08-27, and not the way this section asked

> ⚠ **This section used to prescribe a prompt change, and a prompt change is not a control.** It is
> kept here, rewritten, because the *reason* it was wrong is worth more than the instruction was.

**What it asked for:** extend the intake summarisation prompt with *"replace person names with role
descriptors, replace contact details, replace specific addresses…"*.

**Why that would not have worked.** A prompt instruction acts only on what comes **back**, never on
what is **sent** — so the narrative, names and all, would still have crossed the border on every
call. And it only acts at all in the case where the model chose to comply. It is defence in depth,
never the control. ⚠ The same standard is applied to the ticketing `_FINDINGS_SYSTEM` prompt below:
keep it, do not count it.

**What was built instead — ordering, then a net:**

| Layer | Where | What it does |
|---|---|---|
| **1. Pseudonymise before transmission** | `redact_for_model()` at both `call_llm()` chokepoints (DPG-33) | The model never receives a name, so it cannot echo one. **Structural** — and opt-**out**, so a new call site is covered without its author knowing this exists |
| **2. Redact the output before storage** | `_redact_generated_text()` (§31.4) | Catches what layer 1 missed. A firing logs at **WARNING**, because it means a name already reached a third party |
| **3. Redact at the log boundary** | `backend/logger/pii_filter.py` on `TaskLogger` (DPG-34) | The leak that actually happens. Redacts the **formatted** record, so `%s` arguments are covered |

**Measured, not asserted:** deterministic recall is **87.5%** on the committed benchmark —
person names **7/7**, phones **3/3**, addresses 4/6.

### ⚠ What is NOT built, stated plainly

- **Bare settlement names are not redacted.** `Duhabi`, `Itahari` — a place name with no qualifier.
  Qualified addresses (`ward 5`, `tole`, `municipality`) are. Catching bare place names needs a
  settlement gazetteer, which risks redacting the district the classifier depends on.
- ⚠ **This is pseudonymisation, not anonymisation.** The re-identification mapping exists during the
  call, so the text remains personal data under Nepal's Individual Privacy Act. **Do not tell anyone
  the grievances sent for inference are "anonymised."** The defensible claim is *only pseudonymised
  text crosses the border, and the mapping never leaves the process that made it.*
- ⚠ **Names removed is not identity removed.** A summary keeps ward-level location and circumstance,
  which the privacy assessment notes is often identifying on its own. The claim is *the summary
  carries no names* — not that it is anonymous.
- **`grievance_description` is stored unredacted, by decision** (Q-12b). The officer needs to know
  which engineer was named. That is a *storage* choice; the *transmission* boundary is above.

⭐ **Correction to an earlier version of this sprint's own plan:** it assumed person names would go
unredacted until the ML/NER layer (DPG-32) shipped. That is false. §31.2b gets them deterministically
— honorific and role-title triggers, a family-name gazetteer, self-identification patterns — at 100%
on the labelled set. **DPG-32 raises recall; it was never the whole control.**

### Two-field storage convention

| Field | Content | Who may read it |
|---|---|---|
| `grievance_summary` | ✅ **Built.** Pseudonymised summary — carries no names | Ticketing system, LLM, officers, reports |
| `grievance_description` | ✅ **Built, and it is NOT a vault.** The original narrative, stored **unredacted** in `public.grievances` | Anyone who can read the grievance row — including the officer, who reads it live via `merge_grievance_into_ticket` |
| Vault / reveal-gated original | ⚠ **NOT BUILT** | — |

⚠ **Read the middle row carefully: it is the difference between what this table used to describe and
what exists.** The original narrative is *not* behind a reveal session. It is an ordinary column, and
the officer gets it on every ticket read. That is deliberate (Q-12b: the officer needs to know which
engineer was named), and it is why redacting the *summary* costs the officer nothing — established by
DPG-30 rather than assumed.

⭐ **Which also means the summary decision was cheaper than it looked.** The stored summary carries no
names, so officer free-text search, the XLSX quarterly report to ADB/DOR, the ticketing backup and the
queue view are all clean — while the officer keeps the names via a different path they already used.

**The vault-and-reveal design in the old version of this row is a real proposal, and it is a sprint
after this one** — encrypt the original narrative at rest and serve the redacted derivative by default,
revealing the original only through the audited reveal path.
It needs a redacted derivative to exist first — which is what this sprint built. ⚠ Until it ships,
**do not describe the narrative as vaulted or reveal-gated**: `begin_reveal`/`close_reveal` gate
*contact details*, not the narrative.

### Lookup requirement for inbound messages

When a complainant sends a follow-up via chatbot, the chatbot must resolve
`session_id → ticket_id` before calling `POST /api/v1/tickets/{id}/inbound`.

Recommended approach: store `ticket_id` on the chatbot session state at the point when
`POST /api/v1/tickets` returns a `201` response (the response body contains `ticket_id`).

---

## Ticketing-side guarantees

### context_builder.py

`ticketing/engine/context_builder.py` is the **single auditable point** where raw events
are assembled into the LLM input document. Rules enforced there:

- Only event types in `_CONTEXT_EVENT_TYPES` are included (excludes MENTION, notification-only events)
- `actor_role` is used for attribution — never `created_by_user_id`
- `grievance_summary` / `grievance_categories` / `grievance_location` are included
  (these are non-PII per CLAUDE.md rule 4 — structured fields cached at ticket creation)
- Translations (`payload.translation_en`) are preferred over original note text when available
- Output is stored in `ticketing.ticket_context_cache.context_json` before the LLM call

Any new event type that carries LLM-relevant content must be added to `_CONTEXT_EVENT_TYPES`
explicitly. Never use a wildcard or include all event types.

### Context document format

The JSON sent to the LLM follows this structure (compact-serialised to minimise tokens):

```json
{
  "ticket_id": "...",
  "generated_at": "2026-05-02T...",
  "case": {
    "grievance_id": "GRV-2025-003",
    "summary": "<scrubbed summary from chatbot intake>",
    "categories": "Health & Safety, Construction Nuisance",
    "location": "Birtamod, Jhapa District, Province 1",
    "priority": "HIGH",
    "is_seah": false,
    "status": "IN_PROGRESS",
    "workflow_level": "Level 1 – Site Safeguards"
  },
  "timeline": [
    { "seq": 1, "at": "...", "type": "CREATED",   "by_role": null,                          "note": null },
    { "seq": 2, "at": "...", "type": "ACKNOWLEDGED","by_role": "site_safeguards_focal_person","note": "Visited site" },
    { "seq": 3, "at": "...", "type": "NOTE_ADDED", "by_role": "site_safeguards_focal_person","note": "Dust levels high near km 43", "is_field_report": true },
    { "seq": 4, "at": "...", "type": "COMPLAINANT_MESSAGE","by_role": "complainant",          "note": "Children still coughing", "intent": "ADDITIONAL_INFO" }
  ],
  "field_reports": [
    { "at": "...", "by_role": "site_safeguards_focal_person", "text": "Dust levels high near km 43" }
  ],
  "event_count": 4
}
```

**What is absent by design:** user IDs, complainant name/phone/email, session tokens,
internal system metadata.

### Findings output schema

The LLM is instructed to return JSON only (no prose). The schema is validated after parsing:

```json
{
  "summary_en": "2–4 sentence plain-English case summary",
  "key_findings": ["finding 1", "finding 2"],
  "recommended_action": "one actionable sentence for the case officer",
  "urgency": "HIGH | MEDIUM | LOW",
  "languages_detected": ["en", "ne"]
}
```

`Ticket.ai_summary_en` is populated from `summary_en` for backward-compatible frontend rendering.
The full structured output is stored in `ticket_context_cache.findings_json`.

### Model selection

| Case type | Registry key | Default today | Rationale |
|---|---|---|---|
| Standard grievance | `ticket_findings` | `gpt-4o-mini` | Structured extraction task; quality indistinguishable at ~15× lower cost |
| SEAH | `ticket_findings_seah` | `gpt-4o` | Sensitive investigation; extra reasoning capacity warranted |

**The split is two registry keys, not a ternary in the code** — and that distinction is load-bearing.
It had been written out as a ternary in four modules, one of which (`resolved_summary_builder`) writes
its answer into the **persisted** `llm.model` provenance field of every resolved case. Selecting it in
one place (`findings_task(is_seah)`) is what makes that record provably the model that ran. Pinned by
`tests/backend/test_llm_config_pins.py`.

Both use `temperature=0.0` for deterministic output and `response_format={"type":"json_object"}`
to guarantee parseable JSON.

### Translation pipeline

`translate_note` fires after every `NOTE_ADDED` or `COMPLAINANT_MESSAGE` event commit.
It skips notes that look like English (heuristic: < 5% non-ASCII characters) to avoid
unnecessary API calls. Translated text is stored in `event.payload["translation_en"]` and
shown inline in the thread UI with a 🌐 indicator.

When findings are generated, `context_builder.py` uses `translation_en` in preference to
the original note — so supervisors reading AI findings always see English regardless of what
language the officer or complainant wrote in.

---

## Token budget (reference)

| Component | Typical tokens |
|---|---|
| System prompt (`_FINDINGS_SYSTEM`) | ~180 |
| Context JSON (20 events) | ~700–1 100 |
| **Total input** | **~900–1 300** |
| Output (findings JSON) | ~150–250 |

At Nepal GRM volumes (< 500 tickets/year at launch), even daily findings regeneration
across all active tickets costs < $1/month on gpt-4o-mini.

---

## Review checklist for new LLM calls

Before adding any new LLM call that involves grievance or ticket content:

- [ ] Does the input come from `ticketing.*` fields only (never directly from `public.*`)?
- [ ] If `grievance_summary` is used, is there a note in the PR that the chatbot-side scrubbing requirement applies?
- [ ] Does the system prompt include a "never output PII" instruction?
- [ ] Is `temperature=0.0` set (or explicitly justified if not)?
- [ ] Is the output schema validated after JSON parsing (don't trust raw LLM output structure)?
- [ ] Is the call async (Celery task) — never inline in an API request handler?
- [ ] Is the model choice documented with a rationale?
