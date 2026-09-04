# OM-08 — Extract the generic model into the starter kit

> **kind:** feature (docs) · **profile:** chore+SPEC · **size:** S · **depends on:** OM-01…OM-06
> **Last ticket in the sprint, deliberately.**

## Context

`docs/_starter_kit/` is this project's portable skeleton of its standards — and its credibility comes
from being **extracted from a working project** rather than authored as an ideal. That is the property
distinguishing it from the external reference prompt this sprint reviewed. Extraction happens *after*
the rules have held here, not before ([`DESIGN`](DESIGN-operating-model.md) §5).

## Scope

1. `_starter_kit/engineering/07_work_items.template.md` — the generic model: kinds, the triage test,
   gate derivation, profiles, ready, the two states. Project-specific content becomes a `‹…›`
   placeholder or a **FILL:** callout — `G-SENSITIVE`'s trigger list is the obvious one (here: PII ·
   auth · SEAH · complainant channel · egress).
2. Reference packs, the design gate, the verification ladder and the session-close block, into their
   template counterparts.
3. `_starter_kit/README.md` — the new standard in the map, and what a new project must decide first.
4. **The lessons worth carrying that the reference prompt lacked**, recorded where the kit will use
   them: the spec edit rides the code commit · a rule with no enforcement point is a preference · move
   a rule's reason with the rule · the branch is the version · promote early and mark honestly · a
   deferral register · a questions register with a recommendation per question · an audience field per
   document. Full list: `resources/01-assessment-generic-prompt.md` §8.

## Not in scope

Anything project-specific. If a placeholder cannot be written without naming this codebase, it belongs
in `docs/engineering/`, not here.

## Acceptance

- [ ] The template contains no reference to this repository, its schemas, or its hosts
- [ ] A reader can fill it for a new project without reading `docs/engineering/`
- [ ] Every rule kept carries its *why* — a rule extracted without its reason is the failure the kit exists to prevent
- [ ] `_starter_kit/README.md` updated; `docs/README.md` starter-kit paragraph still accurate
