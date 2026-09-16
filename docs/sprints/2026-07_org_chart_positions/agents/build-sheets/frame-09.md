# Build sheet — Frame 09 · Notifications

> RB-0 deliverable. Grounds wireframe Frame 09 + atlas Surface 09 in the NOW-REAL API.
> Spec: DESIGN §4.5 (notifications derive from the cast; one per-track grid; observers silent; proto = in-app only). IA: Workflows & roles ▸ Notifications. Data owner: `settings.notification_rules` (existing), derived from the Frame 04 cast.

---

## 1. Visual ref

- **Wireframe:** `settings-wireframes.html` Frame 09 (lines 1242–1321). **Atlas:** `settings-state-atlas.html` Surface 09 (lines 731–752).
- **Layout:** "When does someone get alerted?" with a **track switch** (Standard grievances | SEAH). A blue proto banner: "Right now, officers get in-app alerts only. The Email & SMS below are the target setup and switch on later — the grid is safe to leave as-is." Then a **per-track grid**: rows = 7 events (New case / Escalated / SLA breached / Resolved / GRC convened / Assigned to me / Quarterly report); columns = the 4 **cast slots** (Handles it / Oversees / Kept informed / Can view); cells = channel chips (In-app / Email / SMS) or "—". **Can view is a silent column by design.** Tap a cell toggles a channel. A footer note: SEAH track omits GRC convened & Quarterly report. A second blue infobar: complainants notified separately (chatbot-first + SMS fallback); "Assigned to me" SMS leg configured per project under Messaging (read-only context).
- **States (atlas 09):** _loading_ (skeleton; reads from `settings.notification_rules`); _proto-phasing_ (banner reconciling seeded matrix with "in-app only" policy); _read-only/scoped_ (project_admin sees "Notification rules are set by an organisation admin … this is read-only").

---

## 2. Component subtree (DESIGN §3, `components/settings/workflows/`)

```
NotificationRules             [new]      per-track event × slot × channel grid (§4.5)
  (track switch: Standard | SEAH)
  ProtoPhasingBanner          [inline]   in-app enabled / email+SMS "phase-in" muted
  shared/ErrorNotice          [new]      save failures via user-messages.ts
  shared/SeverityBadge/labels  used for the "silent column" + phase-in muting
```

**Replaces (god-file):** `WorkflowNotificationsPanel` (page.tsx:1655–~1910) — today a **collapsible panel per workflow slug** buried inside the workflow editor. DESIGN promotes it to a **first-class sub-nav surface** under Workflows & roles with a track switch (not one collapsible per workflow). Reuses existing constants `NOTIFICATION_EVENTS` (1642), `SEAH_EVENTS` (1651), `NOTIF_TIERS` (1652), `NOTIF_CHANNELS` (1653) — extract these to a shared module.

---

## 3. Governing interaction rules

- **Derived from the cast, not per-step (§4.5):** the slot a role sits in *is* its notification tier — Handles it→`actor`, Oversees→`supervisor`, Kept informed→`informed`, Can view→`observer`. The grid is the *only* place to tune defaults; the admin never wires notifications per step. Frame 04 surfaces the consequence inline ("Oversees → alerted on escalation & SLA").
- **Shape (as-built `settings.notification_rules`, seeded by migration `j8l0n2p4r6`):** `track ("standard"|"seah") → event → tier → [channels]`. Read via `should_notify(workflow_slug, event, tier, channel)` — **safe by default: missing key → no send** (`ticketing/tasks/notifications.py:24-67`).
- **Events (7):** `ticket_created` (New case), `ticket_escalated` (Escalated), `sla_breach` (SLA breached), `ticket_resolved` (Resolved), `grc_convened` (GRC convened), `assignment` (Assigned to me), `quarterly_report` (Quarterly report). **SEAH omits** `grc_convened` + `quarterly_report` (`SEAH_EVENTS` set, `page.tsx:1651`).
- **Tiers (4):** `actor`, `supervisor`, `informed`, `observer` (= the 4 cast slots). **Observer is a silent column by design** — pre-seeded empty; render as a quiet column.
- **Channels (3), phased:** `app` (In-app) enabled in proto; `email` / `sms` shown as the **target** matrix but muted "phase-in" (§7.E) — reconciles the seeded matrix with CLAUDE.md's locked "in-app only (proto)". "Assigned to me" is the one leg that SMSes the actor; that channel is configured per project under Messaging (doc 06 §5) — shown read-only for context.
- **Complainant notifications = separate track** (`_DEFAULT_COMPLAINANT_NOTIFICATIONS`, chatbot-first + SMS fallback) — shown read-only, never edited here.
- **Save = full-object merge:** the PUT replaces the whole `notification_rules` value; the client must merge the edited track back into the other track (existing pattern, `page.tsx:1690-1692`: read current → spread → overwrite `[workflowSlug]`).
- **Open design point (§4.5):** rules are **track-level, not per-step** — recommended to keep. Flag if the ministry needs per-step differences.

---

## 4. Concrete endpoints (real — generic settings K/V store; wrappers `lib/api.ts`)

| Action | Method + path | Payload | Response | Wrapper |
|---|---|---|---|---|
| Get rules | `GET /api/v1/settings/notification_rules` | — | `{key, value: NotificationRulesValue}` (unwrap `.value`) | `getNotificationRules` (2016) |
| Save rules | `PUT /api/v1/settings/notification_rules` | `{value: NotificationRulesValue}` | `SettingsResponse` | `saveNotificationRules` (2022) |

`NotificationRulesValue` (`lib/api.ts:2007-2013`): `Record<track, Record<event, Record<tier, string[]>>>` where track ∈ `"standard"|"seah"`, tier ∈ `"actor"|"supervisor"|"informed"|"observer"`, channels ∈ `"app"|"email"|"sms"`.

There is **no dedicated notifications router** — it rides the generic settings store (`ticketing/api/routers/settings.py`). Write auth: `notification_rules` is **not** in `SUPER_ADMIN_ONLY_KEYS` (`settings.py:19-21`), so `upsert_setting` falls to `elif not current_user.is_admin: 403` (`settings.py:81`) — **any admin may write** (see GAP #1).

---

## 5. Tokens / labels contract

- **Labels not slugs (F11):** event/tier/channel rendered via `lib/labels.ts` display map — "New case" not `ticket_created`, "Handles it" not `actor`, "In-app" not `app`. The existing `NOTIFICATION_EVENTS` label pairs (`page.tsx:1642-1650`) seed this map; extend to tiers/channels.
- **Colors via `design-tokens.ts`:** channel chips (In-app / Email / SMS) and the muted "phase-in" state use tokens, not raw `chan--app/email/sms` literals; no banned hues; no emoji (ℹ/⚠ → Lucide via `@/lib/icons`).
- **Friendly errors:** save failure → `ErrorNotice` via `formatUserFacingError` (current panel shows a raw `e.message`, `page.tsx:1695`).
- **No `<Bilingual>` needed** — event/tier/channel labels are UI chrome strings (i18n is the RB-1 ticket), not `_ne` data fields.
- **Text severity over color:** the "silent" observer column and "phase-in" email/SMS state must read in text, not color alone (a whole quiet column labelled, muted chips labelled "phase-in").

---

## 6. Data owner + open gaps / risks

**Owner:** `settings.notification_rules` (existing `ticketing.settings` K/V; defaults `_DEFAULT_NOTIFICATION_RULES` seeded by migration `j8l0n2p4r6`; consumed by `tasks/notifications.py should_notify`). No new backend model — the grid derives from the Frame 04 cast.

**GAPs / risks for RB-2/3/4:**
1. **`[GAP]` Write gating doesn't match the spec.** Atlas Surface 09 shows a **project_admin read-only** state, and §4.5/§2.5 say notification rules belong to catalog owners (super/org_admin). But the server gate is a **blanket `is_admin`** (`settings.py:81`) — a `project_admin` or `officer_admin` can currently PUT the grid, and it is **not track-scoped** (a SEAH-only admin could edit the Standard grid). To honour the read-only state as more than a UI nicety, add `notification_rules` to a scoped gate (e.g. `require_settings_write(... track=)` like roles/workflows) — backend ticket. Until then the UI gate is defense-only.
2. **`[GAP]` Per-track write is a full-blob overwrite with no server validation.** `PUT` accepts any JSON shape (generic `SettingsUpsert.value: Any`, `settings.py:24`) — no schema check that keys are valid tracks/events/tiers/channels, and a concurrent editor of the *other* track can be clobbered if the client doesn't re-read before merge. RB must (a) re-read + merge on save (existing pattern), and (b) consider a validated `PUT /notification-rules` endpoint if drift becomes a risk.
3. **Risk — "Assigned to me" SMS leg is cross-owned.** The `assignment` row's SMS channel is described as configured per project under Messaging (doc 06 §5), yet the grid also stores an `assignment`/`actor`/`sms` cell. Clarify which is authoritative so the read-only "context" chip doesn't contradict an editable cell.
4. **Risk — SEAH column visibility.** The SEAH grid must be gated to `can_see_seah` (the workflow list already hides SEAH; the notifications surface must too) — the track switch should not expose SEAH to non-SEAH admins. No server enforcement on the settings key itself (see GAP #1).
5. **Consistency — extract shared constants.** `NOTIFICATION_EVENTS`/`SEAH_EVENTS`/`NOTIF_TIERS`/`NOTIF_CHANNELS` (`page.tsx:1642-1653`) must move to a shared module so Frame 04's "the slot also sets notifications" hint and Frame 09's grid read from one source.
