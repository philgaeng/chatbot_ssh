# GRM Specification — All Decisions Locked
# Source: ADB EIA 52097-003 + Round 1 + Round 2 decisions
# Last updated: April 2026

---

## Two Workflows (LOCKED)

```
Standard GRM   → 4 levels, regular officers, visible to standard roles only
SEAH           → SEAH officers only, invisible to standard roles
```

One grievance = one ticket = one workflow. Never both simultaneously.
SEAH tickets filtered at DB query level — role-based WHERE clause on every query.

Routing on ticket creation:
- `workflow_type: "standard"` → standard GRM workflow_definition
- `workflow_type: "seah"` → SEAH workflow_definition

---

## Standard GRM — Four Levels

### L1 — Site Specific | SLA: 48h
**Handler:** `site_safeguards_focal_person`
**Stakeholders:** Contractor, CSC, Site Project Office
**Actions:** Initial assessment, basic resolution, documentation
**Escalation trigger:** Unresolved → L2 (auto at 48h, or manual)

### L2 — Local Level | SLA: 168h (7 days)
**Handler:** `pd_piu_safeguards_focal`
**Stakeholders:** PD, PIU
**Actions:** Review L1, coordinate, investigate, propose resolution
**Escalation trigger:** Unresolved → L3 (auto at 168h, or manual)

### L3 — Project Level / GRC | SLA: 360h (15 days)
**Handler:** `grc_chair` (convenes + decides) + `grc_member` (inputs)
**Convened by:** `piu_project_director`
**GRC composition:** min 5 persons — chair + members + affected rep + local committee rep

**Two-step GRC process:**
1. `piu_project_director` activates L3 with written referral
2. `grc_chair` action: **Convene** → notifies all GRC members in system for this project
3. `grc_chair` action: **Decide** → records resolution, advances workflow

**Escalation trigger:** Unresolved at 15 days → notify `adb_national_project_director` + MOPIT (no auto L4)

### L4 — Court of Law | SLA: N/A (external)
Complainants may seek legal redress at ANY time regardless of GRM level.
No auto-escalation. Manual or separate rule if needed.

---

## SEAH Workflow

Dedicated to Sexual Exploitation, Abuse, and Harassment complaints.
Routed from `feat/seah-sensitive-intake` chatbot branch.

| Aspect | Rule |
|--------|------|
| Visibility | `seah_national_officer`, `seah_hq_officer`, `adb_hq_exec`, `super_admin` only |
| Visual | 🔒 SEAH badge (red), red left border on ticket card |
| SMS | No SMS to complainant (policy) |
| Notifications | In-app only for officers |
| Post-proto | 2FA/MFA for SEAH reviewers |

---

## Escalation Rules

### Auto (Celery, every 15 min):
When `resolution_time_days` exceeded and ticket not resolved:
1. Advance `current_step_id` to next step
2. Assign to users with next level's role for this org/location
3. Write `ticket_events` row (type: ESCALATED, auto=True)
4. Trigger in-app notification badge for newly assigned officers

### Manual (officer button):
Officer clicks "Escalate" at any time before SLA breach.
Same result as auto. `ticket_events` row (type: ESCALATED, auto=False).

---

## Notification Rules (LOCKED)

| Event | Channel | Recipients |
|-------|---------|-----------|
| Ticket assigned | In-app badge | Assigned officer |
| SLA warning (24h before) | In-app badge | Current officer |
| SLA breached | In-app badge | Current officer |
| Manual/auto escalation | In-app badge | Newly assigned officer |
| GRC convening | In-app badge | All GRC members (this project) |
| Complainant: escalation/resolution | Chatbot (POST /message) | Complainant |
| Complainant: session expired fallback | SMS (AWS SNS) | Complainant |
| Quarterly report | Email (SES via Messaging API) | By role |

**In-app badge:** badge count refreshes on navigation (proto).
**Post-proto upgrade:** Server-Sent Events (SSE) for real-time push.

---

## Complainant Notification Flow (LOCKED)

```
Event occurs (escalation, resolution)
  ↓
Check: session_id stored on ticket?
  ↓ YES                    ↓ NO / session stale
POST /message             → silently drop for now
  ↓ success               (post-proto: queue for next session)
Done
  ↓ error (session expired)
POST /api/messaging/send-sms (AWS SNS, works internationally)
```

`session_id` MUST be included in ticket creation payload and stored on `ticketing.tickets`.

---

## Officer Case View — Queue Layout (LOCKED)

### Tabs (top navigation with badge counts):
```
[My Queue  🔴 3] [Watching  12] [Escalated  🔴 1] [Resolved]
```
- **My Queue** — tickets assigned to current officer needing action. Red badge.
- **Watching** — tickets where officer is observer/stakeholder, no action needed. Plain count.
- **Escalated** — any SLA-breached or manually escalated ticket. Red badge.
- **Resolved** — closed tickets, read-only. No badge.

### Summary tiles (3 per tab — clicking filters the list below):

**My Queue tiles:**
```
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  Action Needed  │ │   Due Today     │ │    Overdue      │
│       5         │ │       2         │ │     🔴 1        │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

**Watching tiles:**
```
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  Active Cases   │ │   Escalated     │ │  Resolved       │
│      12         │ │     🔴 2        │ │  this quarter 8 │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

### Ticket rows (color-coded urgency):
```
🔴 GRV-2024-001  Dust/children sick   Birtamod    L2 → PD/PIU  ⏱ 6h left
🟡 GRV-2024-008  Road damage          Mechinagar  L1 → Site    ⏱ 2d left
🟢 GRV-2024-012  Water supply         Biratnagar  L1 → Site    ⏱ 5d left
🔒 SEAH-2024-003 [Restricted]         Province 1  L1 → SEAH    ⏱ 1d left
```
- 🔴 red = SLA < 24h | 🟡 yellow = SLA < 3 days | 🟢 green = SLA > 3 days
- 🔒 SEAH = red badge + red left border on card

### Role → default view:
| Role | My Queue | Watching |
|------|----------|---------|
| `site_safeguards_focal_person` | Their L1 tickets | — |
| `pd_piu_safeguards_focal` | Their L2 tickets | L1 tickets notified on |
| `grc_chair` | L3 to convene/decide | L1, L2 for context |
| `adb_national_project_director` | — (observer) | All active for their project |
| `adb_hq_exec` | — | All tickets across projects |
| `seah_national_officer` | SEAH tickets | — |

---

## Case Timeline

Shows: system events (status changes, assignments, escalations) + internal officer notes.
**Post-proto:** add AI summary of chatbot conversation.

---

## File Attachments

- **Existing chatbot files:** shown as read-only links in case view
- **Officer uploads:** stored in `uploads/ticketing/{ticket_id}/` (local filesystem)
- **Post-proto:** migrate to S3
- **On escalate/resolve:** warning if no attachment, but not blocked (soft enforcement)

---

## Reports (LOCKED)

**Format:** XLSX (openpyxl)
**Trigger:** Configurable date in admin settings
**Recipients:** By role — `adb_national_project_director`, `adb_hq_safeguards`, `mopit_rep`, `dor_rep`

**Columns:**
1. Reference number (grievance_id)
2. Date submitted
3. Nature / categories
4. Grievance AI summary
5. Location (district/municipality)
6. Organization
7. Level reached before resolution
8. Current status
9. Days at each level
10. SLA breached? (Y/N per level)
11. Instance (Standard / SEAH)

---

## Demo Scenarios (May 10)

### Scenario 1 — Standard GRM (dust/children sick):
- Complainant files: dust from KL Road construction, children falling sick
- L1: Site officer acknowledges → unresolved after 2 days → auto-escalates
- L2: PD/PIU investigates → unresolved after 7 days → escalates to GRC
- L3: GRC chair convenes → decides: contractor must wet-spray road twice daily
- Resolved → complainant notified via chatbot

### Scenario 2 — SEAH (harassment):
- Complainant reports harassment by construction worker
- SEAH officer investigates (invisible to standard officers)
- Escalated to SEAH supervisor
- Complaint filed with police, case closed with referral

---

## Seed Data for Demo

| Item | Include |
|------|---------|
| KL Road Standard workflow (4 levels) | YES |
| KL Road SEAH workflow | YES |
| Organizations: DOR, ADB | YES |
| Locations: Province 1 (match chatbot location data) | YES |
| Mock officers: one per role | YES |
| Mock grievances: 2 scenarios above | YES |

---

## SLA Reference

| Level | SLA | Breach action |
|-------|-----|--------------|
| L1 | 48h | Auto-escalate to L2 |
| L2 | 168h (7 days) | Auto-escalate to L3 |
| L3 | 360h (15 days) | Notify ADB + MOPIT (no auto L4) |
| L4 | External | N/A |

---

## Mandatory Documentation (all levels)

1. Name of person filing
2. Date complaint received
3. Nature of complaint
4. Location
5. How resolved

---

## Roles Reference

| Role slug | Level | Access |
|-----------|-------|--------|
| `super_admin` | All | Both workflows |
| `local_admin` | Config | Their org/location |
| `site_safeguards_focal_person` | L1 | Standard only |
| `pd_piu_safeguards_focal` | L2 | Standard only |
| `piu_project_director` | L3 activator | Standard only |
| `grc_chair` | L3 | Standard only |
| `grc_member` | L3 | Standard only |
| `adb_national_project_director` | Observer | Standard only |
| `adb_hq_safeguards` | Observer | Standard only |
| `adb_hq_project` | Observer | Standard only |
| `mopit_rep` | L3 notify | Standard only |
| `dor_rep` | L3 | Standard only |
| `seah_national_officer` | SEAH L1/L2 | SEAH only |
| `seah_hq_officer` | SEAH L3 | SEAH only |
| `adb_hq_exec` | Read-only | Both (senior oversight) |
