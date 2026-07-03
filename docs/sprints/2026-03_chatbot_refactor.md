# Sprint summary — March 2026: Chatbot refactor ("Kill the Rasa runtime")

> Original specs: [`archive/Refactor specs/March 5/`](<archive/Refactor specs/March 5/>) · Status: **Delivered** (Feb–Mar 2026)

## Goal

Replace the Rasa server/action-server runtime with a deterministic FastAPI orchestrator while keeping the existing state, slot, and action names, and migrate the backend off Flask.

## Delivered

- Feasibility evaluation and migration plan for Rasa → deterministic FastAPI orchestrator (states/slots/actions preserved).
- Orchestrator: `POST /message` API, session store, state machine covering the full new-grievance and status-check flows.
- Action layer: `CollectingDispatcher`/`SessionTracker` adapters + action registry running Rasa-SDK-style actions in-process; Celery lazy-import fix and `ENABLE_CELERY_CLASSIFICATION` flag.
- Form-loop driver (`run_form_turn`) with complete slot → ask-action maps for all forms.
- Webchat Socket.IO bridge (transitional) and the new Rasa-free `channels/REST_webchat/` with the `utterances.js` i18n pattern.
- Flask → FastAPI backend migration (files/grievance/messaging/voice/gsheet routers; URL surface preserved).
- Non-blocking file-upload UX (snapshot/restore, input lock, add-more/go-back).
- Sensitive-content detection: lightweight LLM task with two-bucket policy (sexual/gender harassment → sensitive handling; land/violence → high-priority normal flow).
- Grievance modification flow design (Option B: dedicated modify forms + shared `BaseContactForm` validation).
- Repo restructure: actions + orchestrator moved to `backend/`, `rasa_chatbot/` deleted, domain/stories colocated under `backend/orchestrator/config/`, `dev-scripts/` seeding + DB-backed reference data, pandas removed.

## Where the durable content lives now

| Content | Permanent home |
|---|---|
| Orchestrator API, session model, state machine | `docs/rest_chatbot/01_backend_spec.md`, `02_flow_spec.md` |
| REST webchat frontend + `utterances.js` pattern | `docs/rest_chatbot/03_frontend_spec.md` |
| Two-bucket sensitive-detection policy | `docs/seah/` (decision log) |
| Backend/Celery architecture | `docs/deployment/04_backend.md`, `docs/services/07_task_queue_service.md` |

## Leftovers noted at close

- Extended-flow test checklist (spec 06 §8) was never fully executed.
- The Socket.IO bridge was transitional; REST_webchat is the active channel.
