# `GRM-092` — the e2e suite drives organization creation up to the modal and stops

**Deferred 2026-09-07**, while implementing `GRM-089`. Logged here and in
[`SPINE.md`](../../../SPINE.md) per the standing deferral rule.
**Kind:** `debt` — question 4: this is a deliberate choice not to drive the last step now.

## What is driven, and what is not

[`settings-project-setup.spec.ts`](../../../../channels/ticketing-ui/e2e/flows/settings-project-setup.spec.ts)
covers the affordance, the modal opening, and cancel returning to the picker. It does **not** submit
the form.

## Why not

Submitting creates a **real organization row**, and there is no clean way to undo it:
`DELETE /organizations/{id}` refuses once tickets, officer roles or scopes reference the record, and
succeeds otherwise — so a run either leaves a row behind or deletes one non-deterministically
depending on what else the suite did first. A suite that adds `E2E Test Org 17` to a dev database
every run is a suite people stop trusting, and then stop reading.

⭐ **This is the same shape as [`GRM-075`](../../2026-09_qa_automation/followups/officer-provisioning-not-driven-by-e2e.md)**, which stops
short of provisioning a Keycloak account for the same reason: the last step has a side effect that
outlives the test. Both are cases where *the test is cheap and the cleanup is not.*

## The three ways to close it

1. **A disposable stack.** The e2e job already builds one in CI (`QA-03`'s
   `COMPOSE_PROJECT_NAME` isolation). If the suite only ever ran against a stack that is thrown
   away, the side effect stops mattering. **Cheapest, and it closes `GRM-075` too** — but it means
   deciding that e2e never runs against a developer's own stack, which is a real cost.
2. **A teardown that deletes by naming convention** — create as `zz-e2e-<runid>`, delete every
   `zz-e2e-*` afterwards. Works today, and fails exactly when a test fails midway, which is when
   the leftovers matter most.
3. **A dry-run mode on `POST /organizations`.** Cleanest and the most work, and it verifies less —
   a create that does not create has not proven the create path.

**Recommendation: (1).** It closes two items, needs no new code, and the decision it forces —
"e2e owns its own stack" — is one this repository has already half-made.

## Definition of done

- Submitting the create form is driven end to end, and the new organization is asserted **linked
  into the slot that asked for it**, not merely created — that ordering is the whole point of
  `GRM-089` and is currently unverified by anything.
- No row survives the run, by whichever mechanism.
- ✅ The **"NEVER RUN"** banner is already gone — the spec was run and passes as of 2026-09-07.
  What remains open is only the last step: **submitting the form**, and asserting the new
  organisation is *linked into the slot that asked for it*. That ordering is the whole point of
  `GRM-089` and is still verified by nothing.
