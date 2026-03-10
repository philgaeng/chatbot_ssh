# Spec 13: Grievance Modification Flow (Status Check)

## Purpose

Define the flow when a user chooses **"Modify grievance"** after viewing their grievance in the status-check flow. All fields of the existing grievance can be modified; we need a clear UX and implementation approach.

**Current state:** The button exists and is wired (`/status_check_modify_grievance` → `action_status_check_modify_grievance`), but the action only utters a placeholder: `"utterance - modify grievance"`. No real modification flow exists yet.

---

## Scope

- **Entry:** User has just seen grievance details and the three options: "Request follow up" | "Modify grievance" | "Skip".
- **Context:** We have `status_check_grievance_id_selected` and always load the full grievance + complainant data for this ID.
- **Goal:** Let the user **add** information (more grievance narrative, missing contact/location fields, or attachments). We do **not** treat “completely change my address” or “move grievance to another office” as primary use cases; the realistic actions are appending content or filling in missing info.

**Note — Add pictures:** We now explicitly support adding pictures/attachments **from this modification menu**. All uploads must be attached to the **existing** grievance using `status_check_grievance_id_selected` (no orphan files).

---

## Reasonable changes (use cases)

1. **Add pictures and documents** — User wants to add files to the existing grievance. Files are attached to the grievance identified by `status_check_grievance_id_selected`. We should avoid duplicate uploads (e.g. by filename) and inform the user when a file has already been added.
2. **Add more info to my grievance** — User wants to add narrative, answer saved follow‑up questions, keep adding more detail. At the end we ask if they want to add other contact or related info if still incomplete.
3. **Add missing info** — User wants to fill in fields that were skipped or empty (phone, name, location, email). We show only **missing** fields, in a fixed order, with a limited set of buttons per screen so they are not overwhelmed.

---

## Design Options

### Option A: Reuse existing forms with `story_main` (or similar) for context

- **Idea:** Reuse `form_grievance` (grievance details / narrative) and `form_contact` (location + contact) that already exist for the **new grievance** flow.
- **Mechanism:** Set a slot such as `story_main = "status_check_modify"` (or a dedicated `modify_grievance_flow = True`) so that:
  - The **same validation logic** is used (provinces, districts, phone, etc.).
  - **Different utterances** are shown (e.g. “Which contact information would you like to modify?” instead of “Do you want to provide location?”).
- **Pros:** Less duplicate code; validation and backend update logic stay in one place.
- **Cons:** Forms are currently tied to “first-time filing” UX; we must guard required_slots and messaging so we don’t ask for everything again. Need clear branching on `story_main` (or equivalent) in utterances and possibly in required_slots.

### Option B: New forms dedicated to modification

- **Idea:** Introduce new forms, e.g. `form_modify_grievance_details`, `form_modify_contact`, that only run in the “modify” context.
- **Pros:** Clear separation; no risk of breaking the new-grievance flow; modification-specific prompts and field sets.
- **Cons:** Duplicate validation logic (or shared mixins) and more forms to maintain.

**Decision:** **Option B** — dedicated modify forms with **isolation** from the new-grievance flow; share validation via **mixins** to avoid duplication while keeping modification logic separate.

---

## Proposed user flow

**Step 1 — Single question, three options**

After the user taps **"Modify grievance"**, we show a short explanation and three options:

- **Prompt text (example):** “You can add documents, add more to your grievance text, or fill in contact/location details you skipped.”
- **Buttons:**
  - **[Add pictures and documents]** — opens the file attachment modal, attaching files to the existing grievance ID
  - **[Add more info to my grievance]**
  - **[Add missing info]**

We also provide **[Cancel]** to exit modification and return to the status‑check summary (no changes in this step).

---

### Flow A: Add more info to my grievance

1. Show the **grievance summary** (so the user sees what’s already there).
2. User can **answer the saved additional (follow‑up) questions** we have for this grievance (if any) and **keep adding more info** (narrative, details).
   - These follow‑up questions come from the grievance classification step (e.g. `follow_up_question` set by `form_grievance_complainant_review`) and must be persisted alongside `grievance_summary` / `grievance_categories` so they are available here.
   - If there are **no** saved follow‑up questions, Flow A becomes “append more narrative text only.”
3. Reuse or mirror the “add more details” / grievance narrative flow (e.g. same kind of prompts as in initial filing, but in “append” mode, not overwrite).
4. Provide a clear **stop action** (e.g. [Save and continue]) so the user knows when their additions are stored.
5. **At the end of this flow:** ask *“Do you want to add other contact or related info if something is not complete?”*
   - If **yes** → go to **Add missing info (Flow B)**.
   - If **no** → save, confirm, and return to the status-check summary.

---

### Flow B: Add missing info

- We **only store and validate contact/location fields once**, in a shared **BaseContactForm** used by both the original contact form and the modify-contact flow.

#### Shared base contact form (new)

- Introduce a `BaseContactForm` class in `backend/actions/base_classes/base_classes.py` that:
  - Encapsulates all **contact/location validation logic** (phone, full name, province, district, municipality, village, ward, address, email), reusing the existing validators from the current contact form.
  - Provides shared helper methods for:
    - Computing the **ordered list of contact/location slots**.
    - Running per-slot extraction/validation.
    - Building per-field **“ask” actions** (text + buttons) that can be reused by multiple forms.
  - Is subclassed by:
    - `ContactFormValidationAction` (new grievance contact collection).
    - `ValidateFormModifyContact` (Flow B – add missing info).

#### Flow B behavior (on top of BaseContactForm)

- **Field order and selection** (we only show those that are missing, in this order): this mean we need to retrieve the info from the database first and store them in the tracker so that required fields can work appropriately
  1. Contact phone  
  2. Full name  
  3. Province (if empty)  
  4. District (if empty)  
  5. Location fields in the order of the current (contact) flow: **municipality → village → ward → address**  
  6. Email 

  Since the phone is the first element of the list, we may need to reuse otp_form first

- The modify-contact form:
  - Loads grievance + complainant by `status_check_grievance_id_selected`.
  - Computes the list of **missing fields** (empty or skipped) using the shared BaseContactForm helpers.
  - Sets `required_slots` to **only those missing fields** (single-field flow, not a “list + pick” UI).

- **Per-field UX:**
  - For each missing field, an ask action shows a **field-specific prompt** (e.g. "Please provide your phone number…" / "Please provide your address…").
  - **Phone has a dedicated ask action:** Use `action_ask_form_modify_contact_complainant_phone` when `form_modify_contact` has `requested_slot == "complainant_phone"`, so we can use modify-specific wording (and reuse OTP form for collection/verification if needed). For all other missing fields, use the generic `action_ask_modify_missing_field` (with `requested_slot` / `field_label` for the prompt). The orchestrator/form wiring must invoke the phone ask action when the requested slot is phone, and the generic ask action otherwise.
  - Buttons:
    - `[Skip]` → skip this field and move to the next missing one.
    - `[I’m done]` → set a completion flag (e.g. `modify_missing_info_complete`) so Flow B can stop early.

- **Zero-missing case:**
  - If there are **no** missing fields when Flow B starts, the form immediately completes and the orchestrator:
    - Sends a message such as: “All contact and location info for this grievance is already complete.”
    - Returns the user to the **modify grievance menu** (e.g. [Add more info to my grievance] / [Add pictures and documents] / [Back to status check]).

- **Persistence:**
  - After a field validates successfully, we:
    - Update the corresponding complainant/contact field in the DB.
    - Clear any selection helper slots and move to the next missing field.
  - Validation and persistence logic are **shared** between the main contact form and modify-contact form via `BaseContactForm`.

**Open points (for later refinement):**

- Whether we need a more complex “multi-field list + See more” UI on top of this base form; for now we prioritize **reusing validation and per-field prompts** from the shared base and keeping the Flow B interaction simple and linear.

---

## Implementation notes (when we build it)
- **Forms** : use the base form for contact and reuse OTP form to capture the phone number - for OTP form, we need to decide if it makes sense to create a base form and recycle it as well - may be easier to manage the utterances that way.
- **Slots:** Reuse existing grievance + contact slots. Load grievance + complainant from DB by `status_check_grievance_id_selected`. For **Add missing info**, compute the list of missing fields (empty or skipped) in the fixed order: contact phone, full name, province, district, municipality, village, ward, address, email
- **Saved follow‑up questions:** Reuse the follow‑up questions produced by the grievance classification / complainant-review step (e.g. `follow_up_question` from `form_grievance_complainant_review`). Ensure they are **persisted** with the grievance so they can be retrieved during modification.
- **Backend:** Reuse or extend existing APIs to append grievance narrative and to update complainant contact/location so the orchestrator/actions call the same persistence layer.
- **Attachments:** When the user chooses **Add pictures and documents**, attach files to the existing grievance identified by `status_check_grievance_id_selected`. Avoid duplicates (e.g. same filename for the same grievance) and give a clear message if a file is already attached.
- **Orchestrator:** New state(s) for “modify grievance” (e.g. `modify_grievance_menu`, `add_more_info_flow`, `add_missing_info_flow`) and transitions from `status_check_form` when intent is `status_check_modify_grievance`; after add-more or add-missing, transition back to done or status-check summary.
- **Utterances:** Add/use keys for the three-option choice, “Add more info” steps (including the clear stop action), “Add missing info” (and “See more”), zero-missing message, and per-field prompts in `utterance_mapping_rasa.py` (EN/NE). Use a dedicated action `action_ask_form_modify_contact_complainant_phone` for the phone slot in Flow B so its utterances are distinct from new-grievance contact and status-check retrieve-by-phone.
- **Context for ask actions:** Use `story_main` (and, for status_check, a step/route slot) so forms can branch on context; the OTP form already does this. Register and wire `action_ask_form_modify_contact_complainant_phone` so the orchestrator calls it when `form_modify_contact` is active and `requested_slot` is `complainant_phone`.
- **Buttons / CTAs:** Within the flows, prefer just **[Save]** and **[Cancel]** on each field/edit step. **Save** writes the data and moves to the next appropriate step (e.g. back to the missing-fields list or out of the flow); **Cancel** returns to the previous list/screen without saving changes from that step.

---

## Devil’s advocate: critique of the updated flow

*Honest evaluation of the current design — where it could still confuse users, create edge cases, or complicate implementation.*

### 1. **Add pictures: scope creep and attachment target**

The spec first said add-pictures should be “a step earlier” and “out of scope” for this menu; the flow now has **[Add pictures and documents]** as the first option and “triggers the file attachment modal.” So we *are* in scope. That’s fine, but:

- **Attachment target:** Uploads must be tied to the **existing** grievance (`status_check_grievance_id_selected`). If the current upload flow only associates files with a *new* grievance or session, we need a clear path: “attach these files to grievance B-GR-…” or the equivalent API. Otherwise we get orphan uploads or errors.
- **Duplicate uploads:** Users who already added pictures at filing might tap “Add pictures” again and add more. That may be intended; if not, we could show “You already have N attachment(s). Add more?” or similar, and/or prevent adding exact-duplicate files (e.g. same filename) for the same grievance.

---

### 2. **“Add more info” vs “Add missing info” — boundary**

Three options are clear, but the boundary can still be fuzzy for users: *“I didn’t give my phone when I filed — is that ‘Add missing info’ or ‘Add more info’?”* (It’s Add missing.) Consider one short line in the first message, e.g. “You can add documents, add more to your grievance text, or fill in contact/location details you skipped.”

---

### 3. **“Saved additional questions” — where do they live?**

Flow A says “answer the saved additional questions we had (if any).” That implies a config or stored list per grievance (or per type/office). If that doesn’t exist yet, “Add more info” effectively becomes “add narrative only” until we define and store “additional questions.” And we need a **clear stop**: e.g. [Submit additions] or [I’m done adding], so the user isn’t left wondering when their text is saved. Without that, we risk endless free text or confusion.


---

### 4. **Add missing info — zero missing fields**

We only show **missing** fields. If the grievance already has phone, name, location, and email, the list is **empty**. We must handle that: e.g. message “All contact and location info is already complete” and [Back] to the three-option menu. An empty screen or a broken “See more” would be a bad experience.
---

### 5. **Province and district — non‑QR users**

The spec assumes province and district are “always filled already by the QR code,” so Add missing info only offers municipality, village, ward, address. For users who **didn’t** come via QR (e.g. web chat), province and district can be empty. We should either:

- Include province and district in the “missing” list when they’re empty, or  
- Document that this modification flow assumes QR has set province/district and that non‑QR entry is handled elsewhere (e.g. we never show “Modify grievance” for them, or we have another path).

Otherwise we never let them add province/district from this menu.

---

### 6. **End of “Add more info”: one path to “incomplete”**

After Flow A we ask “Do you want to add other contact or related info if not complete?” If yes, we “surface Add missing info (Flow B) or a short list of incomplete fields.” That’s two possible UIs. Better to **pick one**: e.g. “If yes → go to Add missing info (Flow B)” with the same 3 + See more screen. Avoid maintaining two different ways to show incomplete fields.

---

### 7. **After one “Add missing” field: return to list vs “Add another / I’m done”**

The spec leaves open: after collecting one missing field, do we (a) return to the “3 + See more” list of remaining missing fields, or (b) offer [Add another missing field] [I’m done]? Both are reasonable, but **choosing one** avoids inconsistent behaviour. Recommendation: return to the list so the user always sees what’s still missing; add an explicit [I’m done] on that list (or after each save) so exit is clear.

---

### 8. **Option B + mixins — contract and regression**

Isolation (Option B) is good; mixins avoid duplicating validation. The risk is that “shared mixins” become a large, unclear surface. We should **document the contract**: e.g. “LocationValidationMixin provides `validate_municipality`, `validate_village`, …” and which forms use it. Then changes to the mixin are done with both new-grievance and modify flows in mind, and we don’t break one by accident.

---

### 9. **Cancel and Back — defined behaviour**

We say “optional [Cancel] or [Back]” but not where they go. Define: **Back** = previous step within the flow, or back to the three-option menu? **Cancel** = exit without saving and return to status-check summary? Same for “I’m done” in Add missing info: does it save and exit, or only exit from the list (with saves already done per field)? Clear rules prevent users from thinking they’ve saved when they haven’t, or vice versa.

---

### 10. **“See more” with 4 missing fields**

If exactly 4 are missing (e.g. phone, full name, municipality, email), first screen shows 3 + [See more]; “See more” shows 1 (email). So two taps to reach the last field. Slightly heavy but acceptable. No change needed; just be aware that “3 + See more” doesn’t guarantee one-tap access to every field when there are more than 3 missing.

---

### Summary of critique (updated flow)

- **Add pictures:** Clarify attachment-to-existing-grievance and optional “already have attachments?” handling.
- **First screen:** Optional one-line explanation to separate “add narrative” vs “fill in skipped fields.”
- **Add more info:** Define where “saved additional questions” come from and a clear [Submit / I’m done adding]; handle “no additional questions” case.
- **Add missing info:** Handle **zero missing** (message + Back); decide province/district for non‑QR; choose **one** post–add-more path to incomplete fields; choose **one** behaviour after one collected field (return to list + explicit I’m done).
- **Option B + mixins:** Document mixin contract to avoid silent regressions.
- **Cancel / Back / I’m done:** Define exactly where each goes and what “saved” means.

---

## Summary

- **Use cases we support:** Add pictures/documents (attach files to the existing grievance and avoid duplicates); Add more info to grievance (narrative + saved follow‑up questions; then optionally “add contact/related if incomplete”); Add missing info (phone, name, location, email).
- **First screen:** One question, short clarifying line, **three options**: [Add pictures and documents] [Add more info to my grievance] [Add missing info], plus [Cancel] to exit.
- **Add more info:** Show grievance summary → one clear action “Change or add to grievance description” → user answers saved follow‑up questions (if any) and keeps adding narrative → clear stop action → if they say information is still incomplete, we always go to **Add missing info (Flow B)**.
- **Add missing info:** Show only **missing** fields, in order: contact phone, full name, province (if empty), district (if empty), **municipality → village → ward → address**, email. If ≤4 fields are missing, show all; if >4, show 3 + [See more] until 4 or fewer remain. Zero-missing case shows a “contact/location already complete” message and options to modify text or files instead. Reuse validation via mixins.
- **Design:** **Option B** — dedicated modify forms, isolation from new-grievance flow, shared validation via mixins for common rules.
- **UX rules:** Show **current value** on every step where it exists; use only **Save** and **Cancel** within steps; define **exit and “done”** clearly (Save vs Cancel, “I’m done” on missing-fields list).

All further discussion and decisions for this flow stay in this document.
