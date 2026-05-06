# Ticketing System – SLA and Escalation Rules

This document specifies how **SLAs** and **escalation rules** work in the ticketing system. All roles, levels, timelines, and actions are **configurable through settings** (see [02_ticketing_domain_and_settings.md](02_ticketing_domain_and_settings.md)). Concrete roles are described in **TOR GRMS** (Terms of Reference – Grievance Redress System); the system must support 100% configuration of access levels and escalation behaviour.

---

## 1. Concepts

| Concept              | Meaning                                                                                                       | Configurable                                       |
| -------------------- | ------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| **Escalation level** | A step in the grievance resolution path (e.g. Level 1 = site, Level 2 = PIU, Level 3 = GRC, Level 4 = legal). | Yes – number and names per workflow.               |
| **Assigned role**    | Who is responsible at this level (e.g. “Site Safeguards Focal Person”, “PD/PIU Safeguards Focal Person”).     | Yes – mapped to access levels / roles in settings. |
| **Stakeholders**     | Parties involved at this level (for information or coordination).                                             | Yes – list per level.                              |
| **Response time**    | Time within which the level must first respond (e.g. 24 hours).                                               | Yes – per level or global.                         |
| **Resolution time**  | Time within which the level must resolve or escalate (e.g. 1–2 days, 7 days, 15 days).                        | Yes – per level.                                   |
| **Actions**          | Expected activities at this level (assessment, documentation, GRC review, etc.).                              | Yes – descriptive list per level.                  |

Escalation is **time-based**: if the resolution time is exceeded at a level, the ticket escalates to the next level (or triggers a configurable action). Optional: manual escalation by an assigned user.

---

## 2. Example: ADB-financed KL Road Project (Annex I)

This is the **reference example** from the project. The system must support this pattern via configuration, not hard-coding.

### 2.1 SLA Rules

- **Response time (standard):** 24 hours.
- **Resolution time by level:**

| Level  | Resolution time                      |
| ------ | ------------------------------------ |
| First  | 1–2 days                             |
| Second | 7 days                               |
| Third  | 15 days                              |
| Fourth | No specific timeline (legal process) |

### 2.2 Escalation Rules (four levels)

#### Level 1 – First level

- **Assigned to:** Site Safeguards Focal Person
- **Stakeholders:** Contractor, Supervision Consultant (CSC), Site Project Office
- **Timeline:** 1–2 days
- **Actions:**
  - Initial assessment
  - Basic resolution attempt
  - Documentation of actions taken

#### Level 2 – Second level

- **Assigned to:** PD/PIU Safeguards Focal Person
- **Stakeholders:** Project Directorate (PD), Project Implementation Unit (PIU)
- **Timeline:** 7 days
- **Actions:**
  - Review of first level actions
  - Coordination with relevant departments
  - Detailed investigation
  - Resolution proposal

#### Level 3 – Third level

- **Assigned to:** Project Office Safeguards Focal Person (GRC Secretariat)
- **Stakeholders:** Grievance Redress Committee (GRC), PIU, Site Office, Affected Persons
- **Timeline:** 15 days
- **Actions:**
  - GRC review
  - Formal resolution process
  - Stakeholder consultation
  - Final resolution attempt

#### Level 4 – Fourth level

- **Assigned to:** Legal Institutions
- **Stakeholders:** All previous stakeholders
- **Timeline:** No specific timeline
- **Actions:**
  - Legal review
  - Court proceedings if necessary
  - Legal resolution

---

## 3. Mapping to Domain Model

- **Escalation level** → workflow step in `Workflow_definition` (order = level 1, 2, 3, 4).
- **Assigned to** → role name mapped to an **access level** in settings; assignment targets users who have that role for the relevant org/location.
- **Stakeholders** → optional list per step (for display, notifications, or reporting).
- **Timeline** → SLA stored per step: `response_time_hours`, `resolution_time_days` (nullable for “no specific timeline”).
- **Actions** → list of action labels or descriptions per step (for UI and reporting).

Workflow assignment can still be by (organization, location, project, ticket type, priority, sensitive/high-priority flag) so that, for example, one organization can have different workflows for standard vs sensitive/high-priority (as per answered Q3.2 in [00_ticketing_overview_and_questions.md](00_ticketing_overview_and_questions.md)).

---

## 4. Auto-escalation Behaviour

- When **resolution time** for the current level is exceeded (and ticket is not resolved or closed), the system:
  - Moves the ticket to the **next escalation level** (next workflow step),
  - Assigns according to the next level’s “Assigned to” role,
  - Optionally notifies stakeholders and assignees via the **Messaging API**.
- **Fourth level** (or any level with “no specific timeline”) does not auto-escalate by time; escalation from that level is manual or by a different rule if needed.
- All time windows and “no timeline” behaviour are **configurable** per workflow/level.

---

## 5. References

- **Roles and access levels:** TOR GRMS – to be 100% configurable in the system (see [02_ticketing_domain_and_settings.md](02_ticketing_domain_and_settings.md)).
- **Overview and answered questions:** [00_ticketing_overview_and_questions.md](00_ticketing_overview_and_questions.md).
- **API for notifications:** [03_ticketing_api_integration.md](03_ticketing_api_integration.md) (Messaging API for SMS/email).
