# Sprint June5 — Voice notes & UX

**Source brief:** [`../voice-notes-and-ux-feature-brief.md`](../voice-notes-and-ux-feature-brief.md)  
**Dates:** June 2026 (folder name: June5)

## Spec documents

| File | Audience | Tickets |
|------|----------|---------|
| [`01-chatbot-p1-spec.md`](01-chatbot-p1-spec.md) | Chatbot / REST webchat agent | CB-03, CB-04, CB-05, CB-07 |
| [`02-chatbot-p2-spec.md`](02-chatbot-p2-spec.md) | Chatbot agent (phase 2) | CB-01, CB-06, CB-08, CB-09 |
| [`03-portal-p1-spec.md`](03-portal-p1-spec.md) | Ticketing UI + `ticketing/` API agent | TP-01 … TP-12, **TP-13** (UX follow-on) |
| [`04-portal-p2-spec.md`](04-portal-p2-spec.md) | Ticketing agent (phase 2) | TP-02 |
| [`05-roles-permissions-spec.md`](05-roles-permissions-spec.md) | Ticketing UI + API (admin matrix) | RP-01 … RP-11 |

## Agent prompts (copy into Cursor)

| File | Use when |
|------|----------|
| [`agents/chatbot-p1.md`](agents/chatbot-p1.md) | Starting CB-03, CB-04, CB-05, CB-07 |
| [`agents/chatbot-p2.md`](agents/chatbot-p2.md) | Starting CB-01, CB-06, CB-08, CB-09 |
| [`agents/portal-p1.md`](agents/portal-p1.md) | Starting TP-01 … TP-12 (P1 set) |
| [`agents/portal-p1-bugs.md`](agents/portal-p1-bugs.md) | TP-13 — friendly validation messages, no API alerts |
| [`agents/portal-p2.md`](agents/portal-p2.md) | Starting TP-02 |
| [`agents/roles-permissions.md`](agents/roles-permissions.md) | Starting RP-01 … RP-11 (admin matrix, roles, Settings) |

Index: [`agents/README.md`](agents/README.md)

## Progress tracking

| File | Purpose |
|------|---------|
| [`PROGRESS.md`](PROGRESS.md) | Per-agent instructions, status placeholders, commit notes |

## Repo map (this worktree)

| Area | Path |
|------|------|
| REST webchat (production chatbot UI) | `channels/REST_webchat/` |
| Legacy webchat (mirror changes if still deployed) | `channels/webchat/` |
| Orchestrator + flow | `backend/orchestrator/` |
| Chatbot actions (submit, outro, forms) | `backend/actions/` |
| Shared APIs (upload, grievance, voice) | `backend/api/` |
| Ticketing UI (portal) | `channels/ticketing-ui/` |
| Ticketing backend | `ticketing/` |
| REST chatbot docs | `docs/rest_chatbot/` |
| Ticketing docs | `docs/ticketing_system/` |

**Note:** Portal code lives under `channels/ticketing-ui/` (not `ticketing-system`).

## Agent assignment (default)

1. **Chatbot P1** → `01-chatbot-p1-spec.md` only until P1 checklist complete.  
2. **Portal P1** → `03-portal-p1-spec.md` (can run in parallel with chatbot P1).  
3. **Chatbot P2** → after P1 shipped or branched.  
4. **Portal P2** → after TP-01 (player) shipped.

Update [`PROGRESS.md`](PROGRESS.md) when starting or finishing each ticket.
