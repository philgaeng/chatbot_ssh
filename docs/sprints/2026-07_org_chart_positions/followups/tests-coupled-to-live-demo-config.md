# Follow-up — ticket tests are coupled to the demo project's go-live state

**Raised:** 2026-08-07, from a live incident. **Owner:** unassigned. **Cost:** ~half a day.

## What happened

An admin ticked **Staffed for each lot** on KL Road's standard workflow, Level 1 — a legitimate
configuration change, made through the UI the feature was built for. KL Road's five lots have no
per-lot Level 1 officer, so go-live check C1 began to fail and `POST /api/v1/tickets` started
returning **422 "Ticket intake blocked"**.

**Thirteen tests went red without a line of code changing.** Ten of them
(`test_ticket_uniqueness.py`, `test_grievance_sync.py`) are about idempotency and watermarks and
have nothing to do with staffing — they create tickets on the real `KL_ROAD` project, so they
inherit its intake gate. Three (`test_step_staffing_scope.py`, `test_donor_guardrail.py`) asserted
a mutable checkbox as though it were a standing fact and **were fixed in the same commit** by
setting their own precondition instead of reading whatever the database happened to say.

## The debt

The remaining ten still create tickets against the shared demo project. Any admin who configures
KL Road in a way that closes intake reds the suite, and the failure message points at ticket
creation rather than at the staffing gap that actually caused it. A suite that fails when someone
*uses the application* teaches people to ignore it.

## The fix

Give ticket-lifecycle tests a **disposable project fixture** — created in the test, staffed to
exactly the shape the test needs, torn down after — instead of `kl_road_project`. The demo project
stays what it is for: a demo. Suggested shape: a `throwaway_project` fixture beside the existing
`kl_road_project` in `tests/ticketing/conftest.py`, built from an active project type with one
project-wide level and one officer scoped to it.

**Rule that falls out of this, worth keeping:** a test may read the demo database for things the
demo *is* (DOR is a government organization, ADB is a donor) but never for things an admin is
invited to change in the UI. If a screen has a checkbox for it, the test must set it.

## Not fixed here because

The go-live gate on intake is correct and deliberate — a project that cannot route a grievance
must not accept one. Loosening it to keep tests green would be fixing the wrong thing.
