# Follow-up — drop `ticketing.project_locations`

**Logged:** 2026-08-08, alongside the change that stopped reading it (migration `t6v8x0z2`).
**Owner:** ticketing · **Size:** small (one migration + one model + two dead endpoints)

## What is outstanding

`ticketing.project_locations` still exists, still has rows, and **nothing reads it**. Coverage is
declared on packages only ([13 §5C](../../ticketing_system/13_projects_and_packages.md)). The
table's last two readers were removed on 2026-08-08:

- go-live check **D1** — deleted; **B2** inherited the blocking role
- the project editor's **Linked locations** section — folded into **Packages**

## What is left to remove

| Thing | Where |
|---|---|
| `ProjectLocation` model + `Project.locations` relationship | `ticketing/models/project.py` |
| `GET/POST/DELETE /projects/{id}/locations/...` | `ticketing/api/routers/locations.py` (~2092–2160) |
| `addProjectLocation` / `removeProjectLocation` | `channels/ticketing-ui/lib/api.ts` |
| `ProjectItem.location_codes` | `channels/ticketing-ui/lib/api.ts` — check the report filters first, they use a *different* `location_codes` |
| the table itself | a new migration, `DROP TABLE ticketing.project_locations` |

## Why it was not done in the same change

Dropping a populated table is irreversible, and bundling it into a behaviour change means a
rollback of the behaviour cannot restore the data. The rows are worth nothing today, but that is
an argument for dropping them *deliberately* in their own migration, not for free.

**Before dropping**, confirm the endpoints have no callers left outside this repo — the chatbot
does not use them (`grep` over `backend/` finds nothing), but the API is public within the VPC.

## Acceptance

- [ ] `grep -rn "project_locations\|ProjectLocation"` returns migrations only
- [ ] `tests/ticketing` green, including `@integration`
- [ ] `docs/ticketing_system/13_projects_and_packages.md` §5C.1 amended: "left in the database" → "dropped"
