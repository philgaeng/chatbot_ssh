# Agent prompt — Chatbot P2 / CB-09 Road Hazard fast path

You are **expanding CB-09** from a dust-only fast path to a **Road Hazard** fast path with subcategory selection and preset taxonomy classification.

Work **only CB-09** in this session. Do not rework CB-01, CB-06, or CB-08 unless a minimal fix is required for the road-hazard flow to work.

---

## Read first

1. `docs/sprints/June5/02-chatbot-p2-spec.md` — **§ CB-09** (authoritative flow)
2. `docs/sprints/voice-notes-and-ux-feature-brief.md` — CB-09 background; CB-06 + CB-08 dependencies
3. `docs/sprints/June5/PROGRESS.md` — **Agent: Chatbot P2** (dust MVP is `done`; this ticket supersedes dust-only menu/copy)
4. Existing implementation (read before editing):
   - `backend/actions/forms/form_dust.py` — current dust fast path
   - `backend/actions/forms/intake_submit.py` — `complete_dust_intake_submit` (preset category, skips LLM)
   - `backend/orchestrator/state_machine.py` — `dust_grievance` intent + `form_dust` loop
   - `backend/actions/utils/utterance_mapping_rasa.py` — intro menu + dust copy
   - `ticketing/constants/grievance_categories_default.json` — taxonomy source of truth
   - `ticketing/services/grievance_categories_catalog.py` — `derive_category_key(classification, generic_grievance_name)`

---

## Mission

Replace the **dust-only** fast path with a **Road Hazard** fast path.

| Step | User action | Implementation note |
|------|-------------|---------------------|
| 1 | Choose **ROAD HAZARD** | Main-menu button + intent (replace or supersede “Report road dust”) |
| 2 | Choose subcategory | Dust · Flood and Landslide · Potholes · Accident · Animal on Road · Others |
| 3 | Location | Reuse CB-06: pin **or** municipality → locality/village → optional km on road |
| 4 | File grievance | Optional short note / “File as is” (same pattern as current `form_dust`) |
| 5 | Pictures + CB-08 | Reuse existing attachment + EXIF consent flow |
| 6 | Contact optional | Skippable with obvious copy (existing optional-contact pattern) |
| 7 | Auto-classify | **Preset** `grievance_categories` to the matching catalog key — **not** LLM re-classification |

**Subcategory → category key (locked for this ticket)**

Use `derive_category_key("Road Hazard", "<subcategory>")`:

| Subcategory (EN) | `category_key` |
|------------------|----------------|
| Dust | `Road Hazard - Dust` |
| Flood and Landslide | `Road Hazard - Flood And Landslide` |
| Potholes | `Road Hazard - Potholes` |
| Accident | `Road Hazard - Accident` |
| Animal on Road | `Road Hazard - Animal On Road` |
| Others | `Road Hazard - Others` |

Add matching entries (EN + NE fields) to `ticketing/constants/grievance_categories_default.json` so portal settings, ticketing dispatch, and `public.grievance_classification_taxonomy` sync stay aligned.

**Backward compatibility:** Keep `/dust_grievance` working — route it to Road Hazard with **Dust** pre-selected (QR links, old copy, tests).

---

## You may edit

- `backend/orchestrator/state_machine.py`, `form_loop.py`, `action_registry.py`, `config/domain.yml`
- `backend/actions/forms/form_dust.py` — generalize **or** add `form_road_hazard.py` and thin-wrap dust
- `backend/actions/forms/intake_submit.py` — generalize `complete_dust_intake_submit` → road-hazard preset helper
- `backend/actions/forms/form_grievance_complainant_review.py` — extend `is_dust_intake` → road-hazard fast path
- `backend/actions/action_outro.py`, `action_submit_grievance.py`
- `backend/actions/utils/utterance_mapping_rasa.py`, `mapping_buttons.py`
- `backend/actions/generic_actions.py` — QR `package_id` / `location_code` from `ActionIntroduce._resolve_qr_token` when `t` param present
- `channels/REST_webchat/utterances.js` — only if client-side copy keys are used
- `tests/orchestrator/test_chatbot_p2.py`, `test_submit_filed_confirmation.py` — update + add subcategory cases
- `ticketing/constants/grievance_categories_default.json` — **only** the six Road Hazard subcategory rows
- `docs/rest_chatbot/02_flow_spec.md` — short topology update for road-hazard branch

---

## Do not edit

- `channels/ticketing-ui/`, `ticketing/api/`, `ticketing/seed/` (catalog JSON exception above only)
- CB-01 voice UI, CB-06 map module, CB-08 EXIF unless a one-line integration fix is unavoidable
- `docker-compose.yml`, `.env`, `requirements.txt`

---

## Implementation hints

### 1. Orchestrator branch

Today: `/dust_grievance` → `action_start_dust_grievance_process` → `form_dust` → location consent.

Target:

```text
/road_hazard_grievance → action_start_road_hazard_grievance_process
  → form_road_hazard (slot: road_hazard_subtype)
  → form_road_hazard_detail (optional note — reuse dust detail validation pattern)
  → location consent (CB-06) → … → submit → ticketing_dispatch
```

- Add `road_hazard_grievance` to `domain.yml` intents and `menu_transition_intents` in `state_machine.py`.
- `/dust_grievance`: set `intake_fast_path` + prefill subtype **Dust**, then join the same branch.
- Preserve `story_main` values used downstream (`dust_grievance` may become `road_hazard_grievance` — grep and update all `is_dust_intake` call sites consistently).

### 2. Slots (suggested)

| Slot | Purpose |
|------|---------|
| `intake_fast_path` | `"road_hazard"` (replace `"dust"` or alias both in helpers) |
| `road_hazard_subtype` | One of six subcategory codes |
| `grievance_categories` | `[category_key]` preset after subtype chosen |
| `grievance_description` | Default line per subtype if user skips text |

Default description example (Dust): *“Road hazard (dust) report filed via the fast path (location and photos to follow).”*

### 3. Classification (step 7)

**Do not** call `trigger_async_classification` on this path. Mirror `complete_dust_intake_submit`:

- Set `grievance_categories` from subtype → `category_key`
- Set `grievance_classification_status` = `LLM_skipped`
- Set `grievance_categories_status` / `grievance_summary_status` = skip

Officers and ticketing should see the full key (e.g. `Road Hazard - Dust`) on the ticket.

### 4. Copy (EN + NE)

Update in `utterance_mapping_rasa.py` (and `utterances.js` if mirrored):

- Intro menu: **Report a road hazard (fast path)** instead of dust-only label
- Subtype picker: six buttons with payloads like `/road_hazard_subtype_dust` (or slot values — match existing button patterns)
- Optional-contact skip copy unchanged in spirit; verify road-hazard path still hits the same skip UX

### 5. QR / package prefill

When session started with QR token (`t` param), reuse existing resolution in `generic_actions.py` so `package_id` and `location_code` flow into the road-hazard path the same way as standard intake.

### 6. Tests

Extend `tests/orchestrator/test_chatbot_p2.py`:

- Start action sets `road_hazard` fast path + correct preset category per subtype
- Submit skips LLM classification for each subtype
- `/dust_grievance` still lands on Dust preset
- At least one test asserts `category_key` format matches `derive_category_key`

Run: `pytest tests/orchestrator/test_chatbot_p2.py tests/orchestrator/test_submit_filed_confirmation.py`

---

## Locked decisions

- Subcategory list is fixed (six options above); no free-text subtype on fast path
- Classification on fast path is **deterministic preset**, not LLM
- Location, photos, and optional contact reuse CB-06 / CB-08 / existing contact forms — no new UX for those steps
- End-to-end must still call `ticketing_dispatch.dispatch_ticket` on submit

---

## Progress protocol

Update `docs/sprints/June5/PROGRESS.md` → **Agent: Chatbot P2**:

- Add or update a row: **CB-09 Road Hazard expansion** → `in_progress` / `done`
- Note migration from dust-only menu; list `/dust_grievance` alias behavior
- Check P2 verification bullet: *Road hazard: subtype → pin → photos → optional contact → ticket dispatch*
- Log deviations under **Deviations from spec**

---

## Definition of done

- [ ] Main menu offers Road Hazard fast path (EN + NE)
- [ ] Six subcategories selectable; each presets correct `category_key`
- [ ] `/dust_grievance` still works (Dust alias)
- [ ] Full flow reuses pin/fallback location, photos + EXIF, skippable contact
- [ ] Grievance + ticket created via `ticketing_dispatch.dispatch_ticket`
- [ ] Six Road Hazard rows in `grievance_categories_default.json`
- [ ] Tests updated and passing
- [ ] `02_flow_spec.md` mentions road-hazard branch
- [ ] PROGRESS.md updated

---

## Report back

When finished, summarize:

1. Intent names and `story_main` / slot values used
2. Files renamed vs added (e.g. `form_dust` → `form_road_hazard`)
3. Exact `category_key` strings stored per subtype
4. How `/dust_grievance` backward compat works
5. Manual test steps (one non-Dust subtype recommended)
6. Open product questions (default description per subtype, NE labels for new subcategories)

Do not commit unless the user asks.
