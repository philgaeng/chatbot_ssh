# Decision — project participants & supervision (revised model)

> **Status: DECIDED 2026-07-10** (sprint owner). Supersedes the org-project-**role** system and the org-tree-derived supervisor. This is the authoritative record; doc 13, doc 16 §5, the OC-03/OC-04 specs, Frame 05 + atlas, the project-type seeds, and BUILD-HANDOVER §1 are updated to match and cite this file.
> **Standing rule — keep [`PROGRESS.md`](PROGRESS.md) current.** Update it at every commit for the tickets this touches. (Same rule across the sprint — [README](README.md), [agents/README](agents/README.md), [agents/BUILD-HANDOVER](agents/BUILD-HANDOVER.md), every spec.)

---

## 0. The reframe

A project is **not** defined by an org-role layer on top of the org tree. It is defined by **who is staffed to it**. Three structures stay strictly orthogonal:

| Structure | Answers | Crosses the org tree? |
|---|---|---|
| **Org forest** (OC-01) | who *employs / administers* an officer; territory; admin scope | it *is* the tree |
| **Project participants** (this doc) | the *accountable agency* + optional *donors* | thin typed fields, per project |
| **Project staffing = the workflow ladder** (OC-03 + engine) | who *handles / oversees / is informed* at each level | **yes — by design** |

The old per-project **actor-role catalog** (`project_actor_roles`, `project_organizations.org_role`, the "+ Add role" action, super_admin-authored role vocabulary) tried to encode in structure what is either **constant** (the implementing agency = the signing ministry) or already implied by **staffing**. It is removed.

---

## 1. Remove the org project-role catalog

- **Drop** the per-project actor-role vocabulary: `project_actor_roles` table, `project_organizations.org_role`, `project_types.actor_roles`, `routing_org_role`, the "+ Add role" action on the Projects surface, and the super_admin catalog-authoring flow for actor roles.
- Grievance operations run entirely through **officer roles / the workflow cast** (Handles it / Oversees / Kept informed / Can view), staffed per project.
- **Build note:** `project_organizations` survives only if still needed as the officer-scoping link; the *role* dimension is gone regardless. Officer participation is already carried by `officer_scopes(organization_id, project_id, location)`.

## 2. Implementing agency = one defaulted field

- **`projects.implementing_agency_org_id`** — a single org pointer, **defaulted to the project's owning ministry** (per the field rule: *the ministry that signs the contract is the implementing agency*). It is the **routing + reporting anchor**, not a hierarchy.
- Constraints: **exactly one**, org must be **`government`/`local_government`** category (reject a contractor/donor as IA).
- Replaces `routing_org_role` (`validate_jurisdiction()` and routing read this field instead of an actor-role lookup).
- Because it is defaulted, the old "IA is set" go-live gate is effectively always satisfied — it folds into the staffing gate (§7).

## 3. Donor = optional, multi-role, with the last-step-informed guardrail

- **Donors are optional** (most projects have none) and **0..n** (co-financing: ADB + World Bank both possible). A donor is an org of category **`donor`**.
- A donor's staff hold **differentiated roles** — `donor-consultant`, `donor-national`, `donor-hq` (generalizing the legacy `adb_national_project_director` / `adb_hq_safeguards` / `adb_hq_project` / `adb_hq_exec` observers). These are ordinary **catalog roles in the observer/informed tier**, owned by the donor org (org-scoped catalog).
- **Association:** `project_donors(project_id, organization_id)` — 0..n. This is the only "participant" structure besides the IA field; it exists solely to hang the guardrail.
- **The guardrail (org-level):** when a project includes donor **D**, the **last workflow step's "Kept informed" cast must be represented by ≥1 of D's roles**, so donor staff are notified on final escalation.
  - **Auto-populate:** including D drops **all of D's project-scoped roles** into the final step's "Kept informed" slot — visible and adjustable (admin may trim to ≥1).
  - **Strength: BLOCK go-live** if a donor is present but no donor role is in the last-step informed cast (matches the IA-required rigor; ADB visibility on escalated grievances is compliance).
  - **Notifications** derive from the cast (§4.5) — nothing bespoke.
- **SEAH leak-proofing (mandatory, tested):** donor roles are **not** SEAH roles, so on the **SEAH track** every donor tier is **suppressed** at the final step — a donor must receive **nothing** that reveals a SEAH case. The guardrail applies to the **standard** track's final step only. This is a leak vector; it gets an explicit SEAH-leak test.
- ADB has **not** asked us to collect grievances cross-country — donor visibility is per-project, last-step only. No cross-project donor aggregation.

## 4. Contractors / CSC / subcontractors

- No catalog, no guardrail, no go-live gate. If they have people in the flow, those people are **officers staffed via workflow roles** (their home org is the contractor). If they are only a record (e.g., "contractor responsible for remediation"), that stays **narrative in the resolution summary** or an **optional free tag** on the project — never a role system.

## 5. Supervisor = per-step project reassignment authority

- **Supervisor** is the OIC's manager in the **project** tree (hierarchical or matrix), assigned **per workflow step**, **project-scoped**. It is the **"Oversees" cast slot** (`supervisor_role`), *filled per project* (staffing), not baked into the global workflow definition.
- **Supervisor ≠ next-step OIC.** They may coincide, but are different roles.
- **Operational job — reassignment on failure:** when `auto_assign_officer` finds no OIC at step N (or the OIC falls through), the ticket **parks**, the **supervisor of step N is notified**, and the supervisor holds the **reassign capability** at N. This is the safety net against an orphaned ticket.
- **Resolution order** (`resolve_supervisor(user_id, step, project) -> user_id | pool | None`):
  1. **Explicit** per-`(project, step)` supervisor (a person **or** a role pool).
  2. **Default = the next step's Handler pool** (same project) — **shown, not blank**, with provenance ("Supervisor: L2 handler pool — change"). The admin can override to a specific person or a different pool.
  3. **Top step** (no next step): **explicit is required** (no default) — typically GRC chair / project admin.
  4. Else `null` → caller falls back to the step's `supervisor_role` tier pool.
- **Prefer a pool over a single person** for this safety-net role (a lone supervisor on leave re-creates the stuck-ticket problem).
- **Drop the org-tree derivation.** The `parent_organization_id`-derived branch in the current resolver ([02-spec §55](02-officer-positions-and-invite-spec.md)) is **removed** — it mis-resolves across project/forest boundaries (a PD at HQ supervising district field officers). The position-level `reports_to_*` becomes **administrative/HR only** and no longer feeds grievance supervision.

## 6. Two upward events — keep distinct

| Event | Trigger | Goes to |
|---|---|---|
| **Escalation** | SLA breach on a case *being handled* | **next step's Handler pool** (locked, doc 16 §83) |
| **Reassignment-on-failure** | no OIC found / OIC unavailable at step N | **step N's Supervisor** (park + notify + reassign) |

## 7. Go-live gates move to staffing

The project is ready when it is **staffed**, not when an org-role layer is filled:

- **Block go-live** unless **every workflow level has ≥1 officer scoped to the project**.
- **Block go-live** unless the **donor guardrail** (§3) holds, when a donor is present.
- `implementing_agency` is set (defaulted → effectively always true).
- **Ticket-create** validation = **L1 is staffed** (replaces "L1 scoped to the IA org").
- **Coverage warnings** are **per workflow level**, not per actor org.

---

## 8. Blast radius (what changes, citing this file)

| File | Change |
|---|---|
| [doc 13](../../ticketing_system/13_projects_and_packages.md) | remove `project_actor_roles` / `org_role` / `routing_org_role` / "+ Add role"; add `implementing_agency_org_id` + `project_donors`; go-live gate table → staffing + donor guardrail; ticket-create = L1 staffed |
| [doc 16 §5](../../ticketing_system/16_org_chart_and_positions.md) | supervisor visibility/escalation-notify use the project-step resolver; drop org-tree parent |
| [02-spec](02-officer-positions-and-invite-spec.md) §54–58 | reframe `resolve_supervisor` to project-step (drop `parent_organization_id`); `reports_to_*` = admin-only |
| [03-spec](03-chart-behaviors-and-seah-spec.md) §5.3/§5.5 | supervisor = reassignment authority; add donor last-step-informed behavior + **SEAH suppression test** |
| [DESIGN §2.4/§4.3/§4.5](DESIGN-settings-redesign.md) | project-participant model; supervisor in the cast; donor informed-guardrail; §3.1 index row 05/09/13 |
| [settings-wireframes.html](settings-wireframes.html) Frame 05 | remove the actor-role column; foreground staffing + supervisor + optional donor include |
| [settings-state-atlas.html](settings-state-atlas.html) surface 05 | matching states (donor-present guardrail, unstaffed-level block) |
| project-type seeds | drop `actor_roles`; keep workflow + staffing structure |
| [agents/BUILD-HANDOVER.md §1](agents/BUILD-HANDOVER.md) | locked-decisions updated; affects OC-03/OC-04 + doc-13 backend work |

## 9. Acceptance criteria (tests these edits imply)

- [ ] Supervisor resolver: explicit wins → next-step Handler pool default → top-step requires explicit → null falls to `supervisor_role` pool; **no `parent_organization_id` path exists**.
- [ ] Assignment-failure at step N parks the ticket and notifies **step N's supervisor**, who can reassign; distinct from SLA escalation → next step.
- [ ] Go-live **blocks** on any unstaffed workflow level; **blocks** on donor-present-but-not-informed-at-last-step.
- [ ] Donor auto-populates the last-step "Kept informed" cast with its project-scoped roles; admin can trim to ≥1.
- [ ] **SEAH-leak:** a donor receives **nothing** on a SEAH case's final escalation (payload-content asserted), while receiving standard-track final-step notifications.
- [ ] Routing / `validate_jurisdiction` read `implementing_agency_org_id`; no reference to `project_actor_roles` / `routing_org_role` remains.
- [ ] `implementing_agency` rejects a non-government/local-government org; defaults to the owning ministry.

## 10. Terminology

- **Implementing agency** — the one accountable org (the signing ministry). Routing + reporting anchor.
- **Donor** — optional funder org (category `donor`); its staff hold `donor-consultant` / `donor-national` / `donor-hq` observer roles; informed at the last standard-track step.
- **Supervisor** — per-step, project-scoped manager of the OIC; the reassignment authority on assignment failure; defaults to the next step's Handler pool.
- **OIC / "Handles it"** — the `assigned_role_key` officer handling a step. The escalation target is the *next* step's OIC — **not** the supervisor.
