# GRM Ticketing System — Open Questions Round 2
# Based on your Round 1 answers. Answer these to finalize all decisions.
# Demo deadline: May 10. Sessions should start this week.
# Last updated: April 2026

---

## SECTION A — Clarifications from Round 1

### A.1 Multi-workflow clarification (from 3.2)
Your answer clarified you need TWO workflows, not parallel instances:
- **Standard GRM workflow** → regular officers (focal persons, GRC)
- **SEAH workflow** → dedicated SEAH officers only (restricted visibility)

**Confirming this architecture:**
- One grievance = one ticket = one workflow (standard OR SEAH, never both)
- SEAH tickets are invisible to non-SEAH officers
- The SEAH chatbot flow (feat/seah-sensitive-intake) routes SEAH submissions
  to the SEAH workflow automatically on ticket creation

```
Answer: CONFIRM or CORRECT
```

### A.2 Complainant notification via chatbot (from 4.1)
You said notifications go via chatbot (POST /message) not SMS.
But chatbot sessions expire — a complainant who filed 2 weeks ago won't have an active session.

**Decision needed:** When the chatbot session is no longer active, what happens?
- A) Notification is silently dropped (officer contacts complainant offline)
- B) Store notification in a queue, delivered next time complainant messages the bot
- C) Fall back to SMS even without a local entity (use Indian or international SMS provider)
- D) Email the complainant if email was provided during filing

```
Answer:
```

### A.3 In-app notification bar (from 4.2)
You want a notification bar showing pending tasks to officers.

**Decision needed:** How does this work technically?
- A) Polled every N seconds (simple, works with REST)
- B) Server-Sent Events (SSE) — real-time push from FastAPI (like the case view)
- C) Just a badge count on the queue page that refreshes on navigation

For proto, C is fastest. A is fine. B is the best UX but more work.

```
Answer:
```

### A.4 Complainant PII reveal (from 2.3)
You chose B: name shown, phone hidden behind an action — without OTP for now.

**Decision needed:** What triggers the phone reveal in proto?
- A) A "Reveal contact" button — click it, phone shown, action logged
- B) Nothing — phone is always hidden in proto (officer contacts via chatbot reply)
- C) Officer must add an internal note explaining why they're revealing contact

```
Answer:
```

---

## SECTION B — Stratcon Component Reuse Specifics

**Context:** ticketing-ui is a fresh Next.js 16 app in channels/ticketing-ui/ inside
chatbot_ssh. Cursor reads Stratcon as a reference and copies patterns manually.
Stratcon is never forked or merged.

### B.1 Stratcon pages to KEEP for ticketing
Based on what Stratcon has, these map directly:

| Stratcon page | Keep as-is? | Adapt to? |
|--------------|------------|----------|
| Login / auth (Cognito OIDC) | Keep | Officer login |
| User management (invite, roles) | Adapt | Officer account management |
| Settings shell (sidebar + layout) | Keep | Admin settings |
| Help / documentation page | Adapt | GRM officer guide |

```
Answer: confirm or correct
```

### B.2 Stratcon pages to REPLACE entirely
These Stratcon pages get replaced with GRM-specific screens:

| Stratcon page | Replace with |
|--------------|-------------|
| Dashboard (electricity summary) | Officer ticket queue |
| Report generation | Quarterly report export |
| Meter logging | Case detail + action panel |
| Explorer sidebar (clients/buildings) | Org/location/project hierarchy |
| Meter approval workflow | GRM escalation workflow |

```
Answer: confirm or correct
```

### B.3 Stratcon's user roles vs GRM roles
Stratcon has: super_admin, admin, user, viewer (or similar).
GRM needs: admin, site_safeguards_focal_person, pd_piu_safeguards_focal, grc_chair, grc_member, adb_project_director, seah_officer.

**Decision needed:** Do we reuse Stratcon's role system and rename roles,
or build a fresh role system with GRM role slugs?

```
Answer:
```

---

## SECTION C — Officer Queue & Case View

### C.1 Queue grouping
Officers will have tickets assigned to them across multiple levels.

**Decision needed:** How is the officer queue organized?
- A) Flat list sorted by SLA deadline (closest first)
- B) Grouped by status (Action Required / Watching / Resolved)
- C) Grouped by level (L1 / L2 / L3)
- D) Tabs: My Actions | All Active | Escalated | Resolved

```
Answer:
```

### C.2 Case timeline view
The case detail should show what happened (submitted, escalated, GRC convened, etc.).

**Decision needed:** Should the timeline show:
- A) System events only (status changes, escalations, assignments)
- B) System events + internal officer notes
- C) System events + notes + chatbot conversation excerpt (first message from complainant)

```
Answer:
```

### C.3 SEAH ticket visual distinction
SEAH tickets are sensitive and only visible to SEAH officers.

**Decision needed:** In the SEAH officer's queue, should SEAH tickets:
- A) Look identical to standard tickets (access control is enough)
- B) Have a visual indicator (e.g. different color badge, lock icon)
- C) Live on a completely separate queue page (/seah-queue vs /queue)

```
Answer:
```

---

## SECTION D — Admin & Workflow Config

### D.1 Workflow seeding approach for proto
Confirmed: developer seeds KL Road workflow via migration. UI configurator is v2.

**Decision needed:** What seed data is needed for the May 10 demo?
- KL Road Standard workflow (4 levels, standard roles) — YES/NO
- KL Road SEAH workflow (restricted to SEAH officers) — YES/NO
- Mock organizations: DOR, ADB — YES/NO
- Mock locations: Province 1 (KL Road area) — YES/NO
- Mock officers: one per role — YES/NO

```
Answer: YES/NO per item
```

### D.2 GRC as a committee step
At L3, the GRC requires minimum 5 members and a formal hearing.

**Decision needed:** In the proto, how is the GRC step handled?
- A) Same as other steps — one GRC chair actor, others are observers
- B) All GRC members are actors (all must submit their input before step advances)
- C) GRC chair convenes the committee (action: "convene"), then resolves (action: "decide")

```
Answer:
```

---

## SECTION E — File Attachments

### E.1 Where do officer-uploaded files go?
You chose C: show existing chatbot files + allow officer uploads.
The chatbot stores files in `uploads/` on the server filesystem.

**Decision needed:** Where do officer-uploaded files (investigation docs, screenshots) go?
- A) Same `uploads/` folder on the server, subfolder per ticket
- B) AWS S3 (you mentioned Phase 2 in deployment docs)
- C) Same folder as chatbot for now, S3 later

```
Answer:
```

### E.2 File required on escalate/resolve?
The gsheet spec says attachments should be required when escalating or resolving.

**Decision needed:** In the proto, is attaching a file:
- A) Required before officer can escalate or resolve (enforced in UI)
- B) Strongly encouraged but not blocked (warning only)
- C) Optional — no enforcement in proto

```
Answer:
```

---

## SECTION F — Reports

### F.1 XLSX report content
You chose XLSX/CSV for quarterly reports.

**Decision needed:** What columns does the quarterly report include?
Proposed standard set (add/remove):

```
[ ] Reference number (grievance_id)
[ ] Ticket ID
[ ] Date submitted
[ ] Nature / categories
[ ] Location (district/municipality)
[ ] Organization
[ ] Level reached before resolution
[ ] Current status
[ ] Days at each level
[ ] SLA breached? (Y/N per level)
[ ] Resolution date
[ ] Resolved / Unresolved
[ ] Instance (Standard / SEAH)
[ ] Assigned officer name
[ ] Internal notes count
```

```
Answer: tick/untick or add columns
```

### F.2 Report trigger
You said reports sent automatically based on roles.

**Decision needed:** When exactly is the quarterly report sent?
- A) First day of each quarter (Jan 1, Apr 1, Jul 1, Oct 1)
- B) Last day of each quarter
- C) First working day of the month after quarter end
- D) Configurable date in admin settings

```
Answer:
```

---

## SECTION G — May 10 Demo Specifics

### G.1 Demo scenario
For the May 10 demo with ADB/DOR stakeholders.

**Decision needed:** Walk us through the demo scenario so we can mock the right data.
What story do you want to tell?

Example: "A complainant files about water supply on KL Road → officer at site
acknowledges → escalates because unresolved → GRC convenes → resolved"

```
Answer: describe your demo narrative
```

### G.2 Who is in the room for the demo?
**Decision needed:** Who are the stakeholders watching the demo?
This affects which roles/screens need to be polished.

```
Answer:
```

### G.3 Demo environment
**Decision needed:** Is the demo running:
- A) Locally on your laptop (WSL)
- B) On the production EC2 (grm.facets-ai.com)
- C) On a staging server

```
Answer:
```

---

## REMAINING OPEN FROM ROUND 1

### 9.1 Stratcon components table
You filled in the table partially. Two items need clarification:

- **Explorer sidebar → "adapt completely"**: Adapt to what exactly?
  The GRM sidebar should show: My Queue | All Tickets | Escalated | Reports | Settings?

- **Email delivery → "No, built service in chatbot already on same SES"**:
  Confirmed — ticketing uses the chatbot's Messaging API (`POST /api/messaging/send-email`).
  No direct SES calls from ticketing. ✓ (Just confirming this is correct)

```
Answer: confirm sidebar navigation items
```

---

## PRIORITY ORDER FOR MAY 10

Given your deadline, here's what I recommend Claude Code builds first.
Correct if wrong:

```
Week 1 (Apr 21-27): Backend
  Session 1: ticketing.* schema migrations + SQLAlchemy models
  Session 2: FastAPI skeleton + ticket CRUD API + mock data seeder
  Session 3: Workflow engine + escalation logic + Celery tasks

Week 2 (Apr 28 - May 4): Frontend (Cursor)
  Fork Stratcon → GRM shell
  Officer queue page
  Ticket detail + action panel (acknowledge/escalate/resolve)
  SLA countdown + notification bar
  Internal notes

Week 3 (May 5-9): Polish + demo prep
  SEAH workflow + access control
  File attachments (read + upload)
  Mock data for demo scenario
  Chatbot → ticketing webhook (POST /api/v1/tickets on submit)
  Bug fixes + deployment to grm.facets-ai.com

May 10: Demo
```

```
Answer: adjust timeline or confirm
```
