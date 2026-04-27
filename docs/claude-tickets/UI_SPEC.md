# GRM Ticketing UI — Design Spec

> Companion to `TODO.md` and `PROGRESS.md`.
> Describes UI patterns, component behaviour, and layout decisions for `channels/ticketing-ui/`.
> Update this file when a new non-trivial UI pattern is added or changed.
> Last updated: 2026-04-27

---

## Layout overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│  AppShell                                                                │
│  ┌──────────┐  ┌──────────────────────────────────────────────────────┐ │
│  │ Sidebar  │  │ Page content                                         │ │
│  │  (nav)   │  │                                                      │ │
│  │          │  │  [Ticket detail — 3-zone layout, see below]         │ │
│  └──────────┘  └──────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

The sidebar is the only persistent collapsible column at the app shell level
(same collapse behaviour as the Stratcon reference app).

---

## Ticket detail page — 3-zone layout

```
┌──────────────────────┬─────────────┬──────────────────────────────────┐
│  Main (2/3)          │  Actions    │  Translation Panel               │
│                      │  sidebar    │  (collapsible, rightmost)        │
│  - Grievance card    │  (1/3)      │                                  │
│  - Workflow stepper  │             │  Toggle: 🌐 button in timeline   │
│  - Case timeline     │  - Complainant                                 │
│                      │  - Findings │  When open: 320 px fixed width   │
│                      │  - Files    │  When closed: hidden (zero width)│
│                      │  - Assign   │                                  │
│                      │  - Actions  │                                  │
└──────────────────────┴─────────────┴──────────────────────────────────┘
```

The translation panel is the **third zone** — a collapsible right column, inspired
by the Arc sidebar and Cursor's Explorer/Agents panels.

---

## Translation review panel

### Purpose

Field officers (DOR/L1/L2) write notes in Nepali. Supervisors and ADB observers
read English. The AI translation runs automatically but bilingual officers need a
way to check its accuracy.

The translation panel provides a **side-by-side original ↔ translation view** for
every note in the case timeline. It is separate from the timeline so:
- English-only users read the translated chip inline in the timeline (the default).
- Bilingual users open the panel to see the full original alongside the translation
  and can judge whether the AI rendering is accurate.

### Toggle behaviour

- **Default state:** hidden (zero width, no impact on the main layout).
- **Toggle button:** `🌐` icon in the Case Timeline card header (top-right corner).
  Also accessible via keyboard shortcut `T` (when focus is on the page, not an input).
- **Open state:** a 320 px panel appears flush to the right edge of the viewport,
  pushing the main content area to the left. On screens < 1280 px it overlays instead
  of pushing (same approach as Cursor on smaller screens).
- **Persistence:** open/closed state stored in `localStorage` under key
  `grm_translation_panel_open`. Survives page navigation within the same session.
- **Close button:** `×` in the panel header. Also closes on Escape or second `T` press.

### Panel content

```
┌─────────────────────────────────────────────────┐
│  🌐 Translation Review               [×] close  │
├─────────────────────────────────────────────────┤
│  2026-04-26 · by mock-officer-site-l1           │
│  ┌ Original (Nepali) ──────────────────────────┐│
│  │ धुलो धेरै भएको छ, बच्चाहरू बिरामी ...       ││
│  └─────────────────────────────────────────────┘│
│  ┌ English (AI) ───────────────────────────────┐│
│  │ There is excessive dust; the children are   ││
│  │ getting sick…                               ││
│  └─────────────────────────────────────────────┘│
│  ✓ Translated                                   │
├─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┤
│  2026-04-25 · by mock-officer-piu-l2           │
│  ┌ Original ───────────────────────────────────┐│
│  │ Site inspection completed.                  ││
│  └─────────────────────────────────────────────┘│
│  ⟳ Translation pending                         │
├─────────────────────────────────────────────────┤
│  No more notes.                                 │
└─────────────────────────────────────────────────┘
```

**Rules:**
- Only shows `NOTE_ADDED` events (not status events — no translation needed there).
- Notes are listed chronologically (oldest first — opposite of timeline, which is newest-first,
  so the panel reads like a narrative from start to finish).
- Each note shows: timestamp, author, original text, English translation if available.
- Translation status chip:
  - `✓ Translated` (blue) — `payload.translation_en` present and differs from `note`
  - `= Same` (gray) — text already in English (`payload.translation_en` equals `note`)
  - `⟳ Pending` (amber) — no `translation_en` yet (task queued or no API key configured)
- If there are no notes at all: display "No notes in this case yet."

### Relationship to inline translation chips

The timeline and the panel serve complementary audiences:

| User's effective language | Inline chip in timeline | Translation panel |
|---------------------------|------------------------|-------------------|
| `en` (English-first)      | Shown ✅               | Available (for curiosity / checking originals) |
| `ne` (Nepali-first)       | Hidden ✗               | Available (to see what English speakers read)  |

The panel is **always available** regardless of language preference — it is the
primary accuracy-checking tool for bilingual officers.

---

## User language preference

### Data model

```
ticketing.organizations.default_language  VARCHAR(8)  DEFAULT 'ne'
ticketing.user_roles.preferred_language   VARCHAR(8)  DEFAULT NULL
```

**Effective language resolution (server + client):**
1. If `user_roles.preferred_language` is set → use it.
2. Otherwise use `organizations.default_language` for the user's primary org.
3. If organisation has no `default_language` set → fall back to `'en'`.

**Seeded defaults (CLAUDE.md orgs):**
- `DOR` → `default_language = 'ne'`  (Nepali-first)
- `ADB` → `default_language = 'en'`  (English-first)

### API

- `GET /api/v1/users/me/preferences` → `{ user_id, effective_language, preferred_language, org_default_language }`
- `PATCH /api/v1/users/me/preferences` → body `{ preferred_language: "en" | "ne" | null }`
  (`null` = reset to org default)

### Settings UI

**Settings → My Profile → Language:**
```
Preferred language: [ English ▼ ] (overrides DOR default: Nepali)
                    [ Reset to organisation default ]
```

### Alembic migration

Single migration (`down_revision: c1d5f8a2e047`):
- `ALTER TABLE ticketing.organizations ADD COLUMN default_language VARCHAR(8) DEFAULT 'ne'`
- `ALTER TABLE ticketing.user_roles ADD COLUMN preferred_language VARCHAR(8) DEFAULT NULL`
- `UPDATE ticketing.organizations SET default_language = 'en' WHERE organization_id = 'ADB'`

---

## Other UI patterns

### Collapsible panels — general rule

Any panel that a role-subset rarely needs should be collapsible rather than
conditionally rendered. Visible surface area scales with what the *current user*
routinely needs, not the maximum possible information. Examples:

| Panel               | Default state  | Who opens it              |
|---------------------|---------------|---------------------------|
| Translation Review  | Closed        | Bilingual officers        |
| Findings card       | Always open   | GRC/supervisor roles      |
| Attachments         | Always open   | All officers              |

### SLA urgency colours

| Urgency   | Class                   | Condition              |
|-----------|-------------------------|------------------------|
| `overdue` | `bg-red-50 text-red-700` | `sla_breached = true` |
| `critical`| `bg-orange-50 text-orange-700` | `< 24 h remaining` |
| `warning` | `bg-yellow-50 text-yellow-700` | `< 3 d remaining` |
| `ok`      | `bg-green-50 text-green-700`   | `> 3 d remaining`  |
| `none`    | *(no bar)*              | step has no SLA         |

### Badge counts

- **My Queue tab** and **Escalated tab** show a red dot (not a number count) when there
  are any unseen events assigned to the current user. Number shown inside the tab label.
- **Watching** shows a plain grey count — informational, not action-required.
- **Resolved** — no badge.

### SEAH visual treatment

- Ticket rows: red `🔒 SEAH` badge + subtle red left border (`border-l-4 border-red-500`).
- Ticket detail: `SeahBadge` component next to the grievance ID in the title row.
- Access control: `canSeeSeah` from `AuthProvider` gates both the queue filter and the detail 403 guard.

---

*Updated by Claude Code. Keep in sync with implemented components.*
