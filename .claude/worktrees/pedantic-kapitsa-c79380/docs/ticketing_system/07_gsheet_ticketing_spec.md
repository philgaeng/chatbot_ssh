# Gsheet-Based Ticketing – Spec (Current State and Add/Fix)

This document describes the **current** gsheet monitoring setup and the **additions and fixes** needed to support the lightweight ticketing design: PII protection, OTP-gated contact reveal, escalation rules, and documentation of discussions (screenshots).

---

## 1. Current State

### 1.1 Backend

- **Endpoint:** `GET /gsheet-get-grievances` (FastAPI router in `backend/api/routers/gsheet.py`).
- **Auth:** Bearer token (`GSHEET_BEARER_TOKEN`) or Bearer with office username (validated against `office_user` and `office_municipality_ward`).
- **Data source:** `gsheet_query_manager.get_grievances_for_gsheet()` – joins complainants, grievances, latest status from `grievance_status_history`; optional filters: `status`, `start_date`, `end_date`; per-user municipality filter for non-admin users.
- **Response fields (per grievance):**  
  `grievance_id`, `complainant_id`, `complainant_full_name`, `complainant_phone`, `complainant_municipality`, `complainant_village`, `complainant_address`, `grievance_description`, `grievance_summary`, `grievance_categories`, `grievance_sensitive_issue`, `grievance_high_priority`, `grievance_creation_date`, `grievance_timeline`, `status`, `grievance_status_update_date`, `notes`.

### 1.2 Apps Script and Sheet

- **Script:** `channels/monitoring-gsheet/gsheet-appscript.js` (bound to the spreadsheet).
- **Config:** `API_TOKEN`, `BASE_URL` in Script Properties; set via "Set Config Manually" or "Setup Configuration".
- **Scopes:** `spreadsheets`, `script.external_request` (no Gmail/Drive).
- **Flow:** Menu "Refresh Data" (and onOpen) calls `GET ${BASE_URL}/gsheet-get-grievances` with `Authorization: Bearer ${API_TOKEN}`, then writes the response into the active sheet.
- **Headers (current):**  
  User ID, Grievance ID, Full Name, Contact Phone, Municipality, Village, Address, Grievance Details, Summary, Categories, Creation Date, **Status**.
- **Status column:** Data validation with values: `SUBMITTED`, `UNDER_EVALUATION`, `ESCALATED`, `RESOLVED`, `DENIED`, `DISPUTED`, `CLOSED`.
- **Write-back:** Status changes in the sheet are **not** currently sent back to the backend; the sheet is overwritten on next refresh. So status edits in the sheet are lost unless a separate mechanism persists them.

### 1.3 Gaps vs. Desired Ticketing Behaviour

| Gap | Description |
|-----|-------------|
| PII in sheet | Full name, phone, address, etc. are written in plain text. Anyone with sheet access sees complainant identity. |
| No contact reveal audit | There is no "request contact" step; no logging of who saw contact details and when. |
| No OTP-gated reveal | Contact details are always visible in the sheet. |
| No escalation rules in sheet | Escalation/SLA rules are not configurable via a gsheet; they would need to be in backend or a separate settings sheet. |
| No screenshot/attachment for escalate/resolve | No requirement to attach evidence (e.g. chat screenshots) when escalating or resolving. |
| Status not persisted from sheet | Editing status in the sheet does not update the backend; refresh overwrites. |
| No shared folder for attachments | No designated storage and link column for attachments (e.g. discussion screenshots). |

---

## 2. Add/Fix – Summary

1. **PII handling** – Do not show PII in the main sheet. Show grievance content (description, summary, categories, dates, status) and opaque IDs. Store PII encrypted or only in DB; reveal only after OTP.
2. **OTP-gated contact reveal** – "Request contact" action: backend sends OTP to complainant, staff enters OTP, backend returns contact for that grievance and logs the request (who, when, which grievance). Show contact in sidebar/popup only, not in sheet.
3. **Escalation rules in a settings sheet** – Optional second sheet (or same workbook) with rules encoded as rows (e.g. workflow_type, current_status, escalate_after_hours, escalate_to). Backend or script applies these on refresh/schedule.
4. **Screenshot/attachment required for escalate/resolve** – When staff escalate or resolve, require at least one attachment (e.g. screenshot of chat). Store in shared folder; link stored on ticket. Backend reject escalate/resolve if no attachment (or enforce in UI).
5. **Persist status from sheet** – Either: (a) onEdit (or explicit "Save status") calls backend to PATCH grievance status and notes, or (b) backend remains source of truth and sheet is read-only for status (staff change status via backend/API only). If (a), need backend endpoint to accept status updates from gsheet (with auth).
6. **Shared folder for attachments** – One folder per resolution center (or one shared folder with subfolders per grievance/ticket). Links only in sheet or in ticket record; no raw images in WhatsApp groups (see [08_messaging_rules_whatsapp_sms.md](08_messaging_rules_whatsapp_sms.md)).

---

## 3. Add/Fix – Detail

### 3.1 Sheet Columns (Target)

**Main grievance view (no PII in cells):**

| Column | Content | Notes |
|--------|---------|--------|
| Complainant ID | Opaque ID | For API/backend reference only. |
| Grievance ID | Opaque ID | Link to ticket; used for "Request contact", escalate, resolve. |
| Municipality | Allowed | Low granularity; acceptable if policy allows. |
| Village | Optional or redacted | Or "—" / hash; policy decision. |
| Address | **Not in sheet** or redacted | PII; only after OTP reveal in popup. |
| Grievance Details | Yes | Non-PII complaint content. |
| Summary | Yes | Non-PII. |
| Categories | Yes | Non-PII. |
| Creation Date | Yes | Non-PII. |
| Status | Yes | With validation; persisted to backend (see 3.5). |
| Status updated | Optional | Last status change date. |
| Attachments (links) | Links to shared folder | e.g. "Discussion screenshot" link; required on escalate/resolve. |

**Removed from main sheet (only after OTP reveal):** Full Name, Contact Phone, Address (if not already removed). Shown in a sidebar or modal after successful "Request contact" (OTP).

### 3.2 OTP-Gated Contact Reveal

- **Backend:**  
  - Endpoint e.g. `POST /gsheet-request-contact` (or similar): body `{ "grievance_id": "...", "office_user": "..." }`.  
  - Backend sends OTP to complainant (using existing OTP service), stores a short-lived token or expectation (e.g. 5–10 min).  
  - Endpoint e.g. `POST /gsheet-reveal-contact`: body `{ "grievance_id": "...", "otp": "..." }`. Verifies OTP, logs (who, when, grievance_id), returns contact details (phone, name, address as needed).  
- **Apps Script:**  
  - "Request contact" button or menu per row: calls request-contact, then prompts staff for OTP, then calls reveal-contact; shows result in sidebar/modal (do not write into sheet).  
- **Audit:** All contact-reveal events logged (user, grievance_id, timestamp) for compliance.

### 3.3 Escalation Rules (Settings Sheet)

- **Location:** Same workbook, second sheet e.g. "EscalationRules" (or configurable name).
- **Columns (example):**  
  `workflow_type`, `current_status`, `escalate_after_hours`, `next_status`, `notify_role_or_list`, `resolution_center_id` (optional).  
- **Usage:** Backend (or script on refresh) reads this sheet or an API that mirrors it; applies time-based escalation and sends notifications. Alternatively, backend stores rules in DB and gsheet is only for editing/display; sync from sheet to backend on a schedule or manual "Publish rules".

### 3.4 Screenshot / Attachment on Escalate or Resolve

- **Rule:** Escalate or resolve is not allowed without at least one attachment (e.g. screenshot of chat with complainant).
- **Storage:** Upload to shared folder (e.g. Drive or backend-served); link stored in grievance/ticket record (e.g. `grievance_attachments` or `grievance_status_history.notes` + link).
- **Backend:** Endpoint for escalate/resolve accepts `attachment_urls[]` (or file upload); returns 400 if status is ESCALATED/RESOLVED and no attachment provided.
- **Sheet:** Column "Attachments" can show links; or a "View attachments" action that fetches links from backend. Add-attachment flow should be mobile-friendly (staff in the field).

### 3.5 Persisting Status from Sheet

- **Option A – Sheet writes back:**  
  On status change (onEdit or "Save status" button), Apps Script calls e.g. `PATCH /gsheet-update-grievance-status` with `grievance_id`, `status`, optional `notes`. Backend updates `grievance_status_history` and optionally `notes`.  
- **Option B – Read-only status in sheet:**  
  Status is changed only via backend/API or another UI; sheet is refresh-only. Simpler but less "spreadsheet-native".  
- Recommendation: Option A if the goal is to keep the gsheet as the primary UI for status updates; ensure auth (Bearer) and idempotency.

### 3.6 Shared Folder and Links Only in Group Chats

- Attachments (screenshots, documents) are stored in a shared folder (per resolution center or per project).  
- In WhatsApp groups: **no pictures/files**; only links to the folder (or to specific files).  
- See [08_messaging_rules_whatsapp_sms.md](08_messaging_rules_whatsapp_sms.md) for messaging rules.

---

## 4. Staff Workflow (Target)

1. **Review complaint** – Staff sees grievance list with non-PII columns only.
2. **Request contact** – Clicks "Request contact" for a row; OTP sent to complainant; staff enters OTP; contact shown in popup/sidebar (audit logged).
3. **Contact complainant** – Off-system (WhatsApp, phone, field visit) as today.
4. **Escalate or resolve** – Before completing: upload screenshot(s) to shared folder, add link(s) to ticket; then set status to ESCALATED or RESOLVED (and persist to backend).
5. **Notifications** – Staff receive 1:1 WhatsApp/SMS with links to ticket (no PII in message); dedicated person forwards to resolution-center groups as needed.

---

## 5. References

- Current Apps Script: `channels/monitoring-gsheet/gsheet-appscript.js`
- Backend: `backend/api/routers/gsheet.py`, `backend/services/database_services/gsheet_query_manager.py`
- Escalation concepts: [Escalation_rules.md](Escalation_rules.md), [02_ticketing_domain_and_settings.md](02_ticketing_domain_and_settings.md)
- Messaging: [08_messaging_rules_whatsapp_sms.md](08_messaging_rules_whatsapp_sms.md)
