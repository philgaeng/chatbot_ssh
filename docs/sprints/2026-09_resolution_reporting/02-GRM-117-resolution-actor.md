# `GRM-117` — a resolved case does not record which office took the action

**Origin:** user request (client, 2026-09-15) · **Lane:** `resolution-reporting` · **Reported:** 2026-09-15
**Design:** [`DESIGN-resolution-reporting.md`](DESIGN-resolution-reporting.md) §3.2, §3.3, §3.5, §4, §5, §6

## Kind

**`feature`** — question 1: no live spec records who acted. `resolved_by_display_name` in
[`08`](../../ticketing_system/08_ticket_resolution_and_case_summary.md) §3.4 is the officer who
clicked Resolve, not the office that did the work.

## Profile

| ✓ | Question | Fires |
|---|---|---|
| ✔ | Changes user-visible behaviour | `G-PRODUCT` · `G-SPEC` · `G-VERIFY` |
| ✔ | A UI surface changes shape | `G-DESIGN` — a new section in the resolve form; wireframe + six states in DESIGN §4 |
| ✗ | Schema changes | — stored in the existing `ticket_events.payload` |
| ✔ | PII · auth · SEAH · complainant channel · new egress | `G-SENSITIVE` — the field feeds a forwarded Excel; must be structurally unable to hold a name |
| ✔ | API or event shape changes | `G-CONTRACT` — `RESOLVE` gains three optional fields; ticket detail gains three lists; payload gains four keys |
| ✔ | Deployed | `G-RELEASE` |
| ■ | always | `G-TEST` |

> **profile:** `UI feature` +CONTRACT **+SENSITIVE** · **gates:** PRODUCT · DESIGN · SENSITIVE · CONTRACT · SPEC · TEST · VERIFY · RELEASE
> **model:** Opus · **size:** M

## Blocked by

**Nothing.** Independent of `GRM-116` in code; if both are in flight, land `GRM-116` first — they
edit the same form and the same `RESOLVE` branch.

## The change

1. **`RESOLUTION_EXTERNAL_ACTORS`** in `ticketing/constants/resolution.py` — the five keys of DESIGN
   §3.2 (plus *Users' committee* if Q-06 adds it).
2. **`resolve_self_offices(db, user_id, ticket)`** — the §3.2.1 derivation, in a service module
   (suggested `ticketing/services/resolution_actor.py`). Returns 0 … n `{organization_id, name}`;
   the fallback to `tickets.organization_id` happens here, not in the router.
3. **Ticket detail** returns `resolution_self_offices`, `resolution_office_suggestions` (orgs linked
   to the case's project, and to its package when it has one) and `resolution_external_actors`.
4. **`TicketActionRequest`** gains `resolution_actor_kind`, `resolution_actor_organization_id`,
   `resolution_actor_external` — rules and 422s in DESIGN §5. Omitted kind → `self`.
5. **`RESOLVE`** writes `resolution_actor_kind`, `resolution_actor_organization_id`,
   `resolution_actor_external`, `resolution_actor_label` into **both** events' payloads. Same on the
   backfill path.
6. **`format_resolution_note`** adds `Resolved by: <label>` under `Date:`.
7. **Resolved case summary** — `resolution.actor_label` in `summary_json`; included in the findings
   LLM input bundle as read-only context (`08` §3.6.1).
8. **UI** — the *Who took the action?* section in `ResolutionSheet.tsx`, with the six states of DESIGN
   §4. Office search uses `GET /organizations?q=&active_only=true`, debounced.

## Files it may touch

- `ticketing/constants/resolution.py` · `ticketing/services/resolution_actor.py` *(new)*
- `ticketing/api/schemas/ticket.py` · `ticketing/api/routers/tickets/crud.py` · `ticketing/engine/ticket_actions.py`
- `ticketing/services/resolved_summary_builder.py` · `ticketing/engine/context_builder.py` (if the resolution block is built there)
- `channels/ticketing-ui/components/ResolutionSheet.tsx` · `lib/api.ts` · `lib/useTicketThread.ts` · `app/tickets/[id]/page.tsx` · `app/m/tickets/[id]/page.tsx`
- Specs (G-SPEC, same PR): `08` §2.3 · §2.4 · §2.5 · §2.6 · §3.4 · §3.6.1

## Gates — evidence

- **G-CONTRACT** — additive; an old client omitting the new fields records `self`. Stated in `08` §2.5.
- **G-SENSITIVE** — DESIGN §6 check 1: **the schema has no string field an officer types into.**
  `resolution_actor_label` is always computed server-side from an org row or the fixed list; the
  request cannot set it. Test that a request carrying `resolution_actor_label` ignores it.
- **G-TEST** —
  - unit, derivation: one position; two positions with one linked to the project; two unlinked (returns both); none (falls back to the ticket's org); an inactive position is ignored
  - integration: each kind stores the right four keys on both events; `organization` with an inactive or unknown org → 422; `external` with an unknown key → 422; `self` with several offices and none chosen → 422
  - integration: the thread note carries `Resolved by:`
- **G-VERIFY** — e2e: resolve three cases, one per kind, and read *Resolved by* in the thread bubble.

## Non-goals

Free text. *Resolved by* on the complainant closure page or public share. Backfilling old cases.
Letting an officer add an organization to the directory from this form.

## Register line

```
| `GRM-117` — a resolved case does not record which office took the action | feature | UI feature +CONTRACT +SENSITIVE | `ready` | M | resolution-reporting | … |
```
