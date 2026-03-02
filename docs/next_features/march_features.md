# March features (potential / next)

## Backend: migrate to FastAPI first, then Messaging API

**Rationale:** Use a single stack (FastAPI) so we have one place to troubleshoot and so file upload and the orchestrator integrate cleanly while the user interacts with the bot.

- **Troubleshooting:** The main backend service (files, grievance API, status updates) needs ongoing work; doing this in Flask while the orchestrator is FastAPI means two codebases and two runtimes. Migrating the backend to FastAPI gives one stack to debug and deploy.
- **Bot + file integration:** The user interacts with the bot (orchestrator) and adds files in the same session. The webchat gets `grievance_id` from the orchestrator (custom payload `grievance_id_set`) and sends uploads to the backend with that id. Having both behind one FastAPI app (or at least one deployment story) simplifies:
  - Shared middleware, logging, and error handling
  - Optional: real-time feedback (e.g. “File received” / “Processing…” in the chat via the same Socket.IO or response flow)
  - One place to fix issues that span “conversation + upload”

**Order:** (1) Migrate Flask backend to FastAPI (same endpoints, same URLs). (2) Add Messaging API on FastAPI. (3) Other features (e.g. email copy below) on the single stack.

---

## Optional email copy after status-check follow-up

**Summary:** Offer the complainant a copy of the follow-up details by email *after* the details are shown in the chat, instead of (or in addition to) only notifying admins.

**Current flow:**
1. Show follow-up message in chat (grievance ID, phone).
2. Send SMS to complainant.
3. Always send admin recap email.

**Proposed change:**
- Add a follow-up step **after** the “Our officer will follow up…” message:
  - Prompt: e.g. “Would you like a copy of this by email?” (Yes / No).
- **If Yes** (and we have complainant email): send recap email to complainant (`send_recap_email_to_complainant`).
- **Admin recap email:** keep as today (always send) so the office still gets the notification.

**Implementation outline:**
- New state or short form step after `action_status_check_request_follow_up`: e.g. “status_check_email_choice” or a single slot (e.g. `email_copy_requested`).
- Orchestrator: after status_check_form → done, optionally transition to this step; on Yes → invoke `send_recap_email_to_complainant` then → done.
- Reuse existing `send_recap_email_to_complainant`; ensure complainant email is available (from tracker or collect from user in this step if not already present).

**UX note:** If complainant email is not in tracker, either skip the question or add a one-slot “Enter your email for a copy” before sending.
