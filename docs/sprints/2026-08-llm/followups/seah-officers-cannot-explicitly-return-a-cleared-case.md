# Follow-up — a SEAH officer has no explicit way to return a cleared case to the standard queue

> **Raised:** 2026-08-24, by the project owner, while correcting the framing of
> [`seah-detector-flags-gendered-non-harassment-complaints.md`](seah-detector-flags-gendered-non-harassment-complaints.md).
> **Status:** ⬜ **OPEN — new feature.**
> **Size:** S for the action + event + test. M if the round-trip instrumentation is included.
> **Why it matters more than its size suggests:** the SEAH detector is **deliberately** tuned to
> over-flag. That trade is only sound while the return path works, so this is not a convenience — it
> is the second half of a design decision that is currently only half built.

---

## The design this serves

The safeguarding detector prefers false positives to false negatives, on purpose. A **miss** leaves a
harassment report in the ordinary queue where nobody knows to look for it and is unrecoverable; a
**false alarm** costs a SEAH officer a review and carries **no risk to the complainant**, because a
SEAH officer reading a dust complaint discloses nothing to anyone.

**The cheap error is only cheap if it can be undone.** On the committed benchmark the detector flags
**5 of 8** deliberately-authored gendered non-harassment items, so this path is exercised routinely
rather than exceptionally.

## What exists today — verified in the code, 2026-08-24

The capability is real, and it arrived as a side effect rather than as a feature:

| Step | Where |
|---|---|
| Officer edits the ticket's summary and categories | `PATCH /tickets/{ticket_id}/classification` — `ticketing/api/routers/tickets/crud.py:523` |
| Workflow is re-resolved from the corrected categories | `maybe_reroute_ticket_workflow` — `ticketing/services/ticket_workflow_reroute.py:28` |
| ⭐ The detector's flag is **not sticky** | the re-resolution passes `legacy_is_seah=False`, so `is_seah` is re-derived from the resolved workflow rather than carried forward |
| Ticket returns to L1 of the standard workflow, reassigned | same file |
| Surfaced to officers | `channels/ticketing-ui/components/tickets/ClassificationGrievancePanel.tsx` |

⚠ **One behaviour here is deliberate and must not be "fixed".** A grievance the *complainant* routed to
SEAH by choosing that intake path stays on it regardless of categories —
`effective_intake_route_for_reroute` (`ticketing/services/workflow_routing.py:78`) preserves the
original route by design. **Only a machine flag is reversible; a person's own choice is not
overridden.**

## The gap

1. ⚠ **There is no explicit action.** `ACTION_HANDLERS` (`ticketing/engine/ticket_actions.py:561`)
   offers `ACKNOWLEDGE`, `ESCALATE`, `RESOLVE`, `NOTE`, `FIELD_REPORT`, `REASSIGNMENT_REQUESTED`,
   `GRC_CONVENE` — and nothing that says *"this is not a SEAH case; return it to the standard queue"*.
   An officer has to know that editing the categories is what moves it.
2. ⚠ **The audit trail records the wrong thing.** The event written is `CLASSIFICATION_VALIDATED`. A
   case leaving the confidential stream is a materially different act from a classification tidy-up,
   and it should carry its own event, its own reason, and its own reviewer.
3. ⚠ **No test pins the flag-clearing.** Nothing asserts that a re-resolution sets `is_seah` back to
   `False`. **The single property the recall-first trade depends on is unprotected against
   regression** — and it is invisible when it breaks, because the case simply stays in the SEAH queue.
4. ⚠ **The round-trip is unmeasured.** Nobody knows how long a misrouted complaint waits before it is
   returned. A recall-first design is only as good as that latency, and it is currently unobservable.

## Definition of done

- [ ] An explicit action — *"Not a SEAH case — return to standard queue"* — available to officers cast
      on the sensitive workflow, requiring a reason
- [ ] Its own audit event, distinct from `CLASSIFICATION_VALIDATED`, naming the actor and the reason
- [ ] A test that pins `is_seah` clearing on re-resolution, **and** a test that pins the complainant's
      own SEAH intake route as *not* reversible — both directions, because each is a different bug
- [ ] The round-trip latency (flagged → returned) recorded, so the cost of the recall-first trade can
      be reported rather than assumed
- [ ] ⚠ Confirm the officer UI makes the action discoverable without needing to know that categories
      are the underlying mechanism

## Related

- [`seah-detector-flags-gendered-non-harassment-complaints.md`](seah-detector-flags-gendered-non-harassment-complaints.md) — the measurement, and why over-flagging is intentional
- [`../../../dpg/00_compliance_status.md`](../../../dpg/00_compliance_status.md) §9 — where this is assessed as the indicator-9 gap
- [`../../../dpg/model-benchmarks.md`](../../../dpg/model-benchmarks.md) §3.2 — the 5-of-8 measurement
- [`../../../models/01_seah_detection_benchmark.md`](../../../models/01_seah_detection_benchmark.md) §1 — the asymmetric error costs
- [`../../../TODO.md`](../../../TODO.md) — the backlog row
