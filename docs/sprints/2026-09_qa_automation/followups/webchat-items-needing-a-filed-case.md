# Follow-up — four webchat items that need an intake driven to a filed case

**Logged:** 2026-09-06, on QA-04d, with six of HR-07's ten sweep items automated and passing.
**Owner:** qa · **Status:** deferred with a named blocker, tracked as `GRM-077`.

## What is automated, and what is not

HR-07's sweep is ten items across seven headings. Six are driven by
`channels/ticketing-ui/e2e/webchat/`:

| Item | Covered by |
|---|---|
| EN/NE switch | `intake.spec.ts` — the *menu* is asserted in each language, not the bilingual greeting |
| Status check | `intake.spec.ts` |
| SEAH route entry + persistent close controls | `intake.spec.ts` — including the swap of "Close session" for "Close browser tab" |
| Send-lock double-Enter → one `POST /message` | `send-lock.spec.ts` |
| Send-lock under a dead backend → 15 s failsafe release | `send-lock.spec.ts`, simulated with `page.route()` |
| Session-id persistence + `/clear_session` rotation | `session.spec.ts` — id stability and rotation, **not** intake resumption (HR-07's own caveat) |
| SRI load-cleanliness in a real browser | `assets.spec.ts` |
| Image upload — **partial** | `attachment.spec.ts` covers picker, preview and the hold-until-a-case behaviour |

**Four remain**, and they share one blocker.

| Item | What it needs |
|---|---|
| Image upload — the upload itself | a selected case, so `/upload-files` actually fires |
| Voice note | the same, **plus** an ASR stub — the transcript is a live, paid model call |
| Map pin | the location step of a real intake |
| Filed-banner renders the id as text, not HTML | a **filed** grievance, which is the end of the whole intake |

## The blocker, stated precisely

**Reaching a case means driving the intake, and the intake runs the classifier.** That is a
model call per run, on a pipeline whose `backend-tests` job excludes `@live_llm` *because it
costs money* and whose one spending job is deliberately not a required check. A webchat suite
that classifies a grievance on every pull request contradicts both.

⚠ **It is not only cost.** A driven intake also files a real grievance per run, and this system
has **no erasure path by decision** — so the rows accumulate on the complainant side of the
database, which is a heavier thing to leave behind than the officer-side tickets QA-04c creates.

## What would unblock it — in the order they should be tried

1. **A deterministic classifier stub at the service boundary**, selected by env, the way QA-04d
   was told to stub ASR. Covers all four items, costs nothing per run, and the stub is small.
   ⚠ It changes what is under test: the intake path is exercised, the classification is not.
2. **A seeded, already-filed grievance** the status-check flow can select. Unblocks the upload
   and the filed banner without touching intake at all — **this is the cheapest partial**, and
   it is worth doing even if (1) never happens.
3. Driving a real intake against a live model in a **nightly** job rather than per pull request.
   Honest, complete, and the only version that tests classification — but it needs an owner for
   the spend.

⭐ **Recommendation: (2) first.** It is a seed fixture, it needs no new machinery, and it turns
two of the four items green. (1) is the right long-term answer and belongs with whoever next
touches the intake pipeline.

## Definition of done

- [ ] `/upload-files` is driven end to end and the file appears against a case
- [ ] A voice note is driven with a **stubbed** ASR response, asserting the UI contract — recorder
      state, chunk upload order, the message landing in the thread — and not the transcript
- [ ] The map pin sets a location that survives to the filed grievance
- [ ] The filed banner is asserted to render its id as **text**, with a `<` in the id proving it
      is not being interpreted as HTML — the actual regression HR-07's change #4 prevents
- [ ] Whatever is still not covered is named here, with its reason
