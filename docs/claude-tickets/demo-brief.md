# GRM Ticketing System — Demo Brief
**For use in Claude.ai chat to generate presentation slides, speaker notes, and demo script.**

---

## Context

ADB-compliant Grievance Redress Mechanism (GRM) ticketing system for Nepal road infrastructure projects (KL Road / Kakarbhitta–Laukahi Road, ADB Loan 52097-003).

- Complainants file grievances via a **QR-code-activated chatbot** on their phone
- The chatbot creates a ticket that lands in this ticketing system
- Officers manage, escalate, and resolve cases through a structured workflow
- Fully auditable, SLA-tracked, bilingual (Nepali ↔ English AI translation)

**Demo date:** May 10, 2026
**Target audience:** ADB project managers, safeguards officers, DOR/MoPIT representatives

---

## App Summary: 6 Pages

### 1. Officer Queue (`/queue`) — Main landing page

The dashboard every officer sees on login.

**3 summary tiles (top):**
- **Action Needed** — tickets requiring the officer's response (red badge)
- **Due Today** — SLA expires in < 24 hours (yellow warning)
- **Overdue** — SLA already breached (red urgent)

**4 tabs with live badge counts:**
| Tab | What it shows |
|-----|---------------|
| My Queue 🔴 | Officer's own assigned tickets |
| All Tickets | Full system view (admin + senior roles) |
| Escalated 🔴 | All escalated cases across the org |
| Resolved | Historical closed cases |

**Ticket rows show:**
- Urgency dot (🔴 overdue / 🟠 warning / 🟢 ok)
- Grievance reference ID, summary, location, project code
- 🔒 SEAH badge (visible only to SEAH-role officers)
- Status + priority badges
- SLA countdown timer
- Unread event counter (red bubble)

---

### 2. Ticket Detail (`/tickets/[id]`) — Case management view

Two-column layout: **thread on the left, information cards on the right**.

**Compact top bar (always visible):**
- Ticket ID, status badge, priority badge, SEAH badge
- Primary action buttons (role-gated, for assigned officer):
  - **Acknowledge** → starts SLA clock
  - **Escalate** → moves to next workflow level
  - **Resolve** → closes with resolution note
  - **Close** → administrative close
  - **Convene GRC** → schedules L3 hearing (GRC chair only)
  - **GRC Decide** → records Resolved or Escalate-to-Legal (GRC chair only)
- Secondary actions: Reply, Assign, Task, Translations

**Left column — Thread:**
- Chronological event log with filter chips: All / Mine / Supervisor / Observer / Tasks / Complainant / System
- Internal notes (officers only, never visible to complainants)
- Field reports (tagged with `#report` slash command)
- System events (escalation, SLA breach, assignment changes)
- Task cards (assigned tasks with Done button)
- Compose bar with slash commands: `#report`, `#escalate`, `#assign`, `#inspect`, `#call`
- Viewers bar — shows avatars of all officers watching the case

**Right column — Info cards:**
1. **Workflow** — visual progress through L1→L2→L3 GRC→L4 Legal nodes
2. **Tasks** — pending / completed tasks, `+ Task` button
3. **Original Grievance** — summary, categories, location
4. **Field Reports** — officer-added site reports in amber cards
5. **AI Findings** *(role-gated: GRC chair, ADB roles, admins)* — LLM-generated case summary, regeneratable
6. **Complainant** — name, masked phone ("Reveal" button, action logged), email, address, edit button
7. **Attachments** — complainant files (download gated behind Reveal) + officer uploads

**Translation panel (right overlay):**
- Appears when "Translations" button clicked
- Shows original Nepali note alongside English AI translation
- Pending translations shown with spinner

---

### 3. Reports (`/reports`)

**Manual export:**
- Date-range picker (defaults to current quarter)
- Optional organization filter
- **Download XLSX** button — generates full ADB-format report

**Report columns:**
Reference number · Date submitted · Nature/categories · AI summary · Location · Organization · Level reached before resolution · Current status · Days at each level · SLA breached (Y/N per level) · Instance (Standard / SEAH)

**Automatic quarterly reports** *(admin-only section):*
- Auto-emailed on 5th of Jan / Apr / Jul / Oct
- Recipients: ADB National Project Director, ADB HQ Safeguards, MoPIT rep, DOR rep
- Schedule configurable in Settings

---

### 4. Help (`/help`) — Officer Guide

6 expandable FAQ sections:
1. **Getting Started** — what GRM is, how to find assigned tickets
2. **Working with Tickets** — Acknowledge → Investigate → Resolve flow, SLA indicators, replying to complainants
3. **SEAH Cases** — what SEAH means, why SEAH tickets are hidden from standard officers
4. **GRC Process (Level 3)** — how to convene a hearing, how to record a decision
5. **Reports** — how to generate and download reports
6. **Support** — who to contact

Footer: *GRM Ticketing v0.1 · KL Road Project · ADB Loan 52097-003*

---

### 5. Settings (`/settings`) — Admin panel (6 tabs)

**Officers tab:**
- Invite officers by email (Keycloak-backed in production, mock in demo)
- Assign roles, manage jurisdiction scopes
- Scopes define which org / location / project / package an officer can see

**Roles tab:**
- 12 pre-defined roles: super_admin, local_admin, site_safeguards_focal_person, pd_piu_safeguards_focal, grc_chair, grc_member, adb_national_project_director, adb_hq_safeguards, adb_hq_project, adb_hq_exec, seah_national_officer, seah_hq_officer
- Role descriptions and workflow assignment (Standard / SEAH / Both)
- Edit modal per role

**Workflows tab:**
- Visual workflow builder
- Two pre-seeded workflows: **Standard 4-Level GRM** and **SEAH**
- Each step has: display name, assigned role, response time SLA, resolution time SLA
- Supervisor / Informed / Observer tiers configurable per step
- Notification rules matrix (event type × tier × channel)
- Publish / Archive actions

**Organisations & Locations tab:**
- Create and edit organizations with roles (Executing Agency, Donor, Contractor, Consultant, etc.)
- Manage projects within organizations
- Manage districts/municipalities (importable via CSV or JSON template)
- **Packages** — civil works lots/contracts within each project:
  - Package code (e.g. `SHEP/OCB/KL/01`)
  - Name, description (km range)
  - Contractor assignment
  - Location coverage (districts)
  - **QR Token management** (generate, view, revoke)

**Report Schedule tab:**
- Configure quarterly report schedule
- Recipient management by role

**System Config tab** *(super_admin only):*
- System-wide configuration

---

## Design Philosophy (key differentiators for the pitch)

### 1. Built for the Region
The UI is designed specifically for **South Asia, Central Asia, and Southeast Asia** deployment contexts:
- **High contrast** colour palette — readable in bright sunlight on low-spec devices
- **Icon-first design** — every action and status has a clear icon so the interface works across literacy levels and languages
- Tested for use on mid-range Android phones (the dominant device in the field)

### 2. WhatsApp-Inspired Collaboration — With Enforcement
The ticket thread is deliberately modelled on **messaging apps familiar to every field officer**:
- Conversation-style thread (bubbles, timestamps, read indicators)
- Case holder can **add teammates** as Informed members — they receive notifications and can contribute
- **Assign tasks** directly from the thread (like pinning a task in a group chat)
- **Attach files** — photos, PDFs, site reports — uploaded inline just like sending a file in WhatsApp
- But unlike a chat group: **privacy is enforced by role** — SEAH cases are structurally invisible to standard officers, not just hidden behind a UI toggle; PII is never stored in the ticketing layer

### 3. AI That Works for Multilingual Teams
Two AI features reduce the language burden on senior stakeholders:
- **AI Translation** — every note written in Nepali (or any local language) is automatically translated to English; ADB HQ reviewers read a bilingual thread without asking anyone for a summary
- **AI Case Findings** — one click generates a structured case summary visible to GRC chairs, ADB project directors, and HQ; keeps all stakeholders aligned without email chains

### 4. Fully Customisable for Any DOR Project
The system is not hardcoded to KL Road:
- **Workflows** are fully configurable in Settings — number of levels, SLA at each level, roles assigned
- **Locations** are importable from CSV (any country's administrative hierarchy)
- **Packages / Lots** can be created for any civil works contract
- **QR tokens** are generated per package — deploy a new project by creating a project, packages, and printing new QR codes; no code changes required
- **Organisations and roles** are admin-managed — DOR can onboard a new contractor or consultant in minutes
- One platform can run **multiple concurrent projects** with full data isolation by project/package scope

---

## Key Features Summary (for slide talking points)

| Feature | What it does |
|---------|-------------|
| **QR code intake** | Complainant scans QR on a site notice board → chatbot activates pre-filled with project + location → ticket filed in seconds |
| **WhatsApp-style thread** | Familiar conversation UI — add notes, files, tasks inline; feels like a group chat but with enforced privacy and full audit trail |
| **Teammate collaboration** | Case holder adds colleagues as Informed members; they get notifications and can contribute notes and tasks |
| **4-level escalation workflow** | L1 Site → L2 PIU → L3 GRC → L4 Legal; each level has SLA clocks that auto-escalate on breach |
| **SEAH case isolation** | SEAH tickets are invisible to standard officers at the DB level; separate workflow with dedicated officers; 🔒 badge for SEAH roles |
| **SLA tracking** | Per-ticket countdown visible to every officer; queue tiles surface Due Today and Overdue at a glance |
| **AI translation** | Officer notes in Nepali auto-translated to English (GPT-4, async); bilingual thread readable by ADB HQ without asking for summaries |
| **AI case findings** | LLM generates a structured case summary for senior/ADB roles; one click keeps all stakeholders aligned |
| **GRC hearing flow** | Two-step GRC: Convene (schedules hearing, notifies all GRC members) → Decide (records resolution or escalate to legal) |
| **Total complainant privacy** | Phone hidden by default; "Reveal" logged as audit event; PII never stored in ticketing schema — separated at DB architecture level |
| **Officer reply** | Officer types a reply → delivered to complainant via chatbot session or SMS fallback (AWS SNS, works internationally) |
| **XLSX reporting** | One-click quarterly export in ADB format; also auto-emailed to relevant roles on schedule |
| **Role-based access** | 12 roles with jurisdiction scopes (org + location + project + package); from site L1 officer to ADB HQ executive |
| **Fully customisable** | Any project, any workflow depth, any location hierarchy — configured in the admin UI, no code changes needed |

---

## Demo Scenario Seed Data (what's live in the demo DB)

| Ticket | Status | Story |
|--------|--------|-------|
| GRV-2025-001 | OPEN | Dust from road works, children falling sick — filed via chatbot |
| GRV-2025-002 | OPEN (SLA breached) | Same location, second complainant; SLA clock in red |
| GRV-2025-003 | IN PROGRESS | Acknowledged by L1, being investigated |
| GRV-2025-004 | ESCALATED | Unresolved after 48 h; auto-escalated to L2 PIU |
| GRV-2025-005 | IN PROGRESS (SEAH) | 🔒 SEAH case — invisible to standard officers |
| GRV-2025-006 | RESOLVED | Full L1→L2→L3 GRC cycle completed; complainant notified |

**Demo officers pre-seeded (one per role):**
- L1 site officer, L2 PIU officer, GRC chair + 2 members, ADB observer, SEAH officer, super admin
- Role switcher in the header lets you jump between roles during the demo without logging out

---

## Suggested Live Demo Flow (~8 minutes)

1. **(Phone)** Scan QR code on site notice board → chatbot opens pre-filled with "KL Road, Morang District" → complainant files dust/health complaint
2. **Login as L1 officer** → My Queue shows new ticket with SLA countdown → Acknowledge
3. Add a field report note (`#report` in compose bar) → show note appears in thread
4. **Switch to "Escalated" tab** → show GRV-2025-004 waiting at L2 → Acknowledge as L2 officer
5. **Switch to GRC chair** → Escalated ticket arrives at L3 → Convene GRC (set hearing date) → GRC Decide → Resolved
6. Show **AI Findings card** populating for GRC chair view
7. **Switch to SEAH officer** → show 🔒 case visible only to them
8. **Settings → Projects → Lot 1** → generate QR token → QR modal with scannable code + download button
9. **Reports → Download XLSX** → show column structure

---

*Generated: 2026-05-07 from live codebase at `channels/ticketing-ui/` and `ticketing/`*
