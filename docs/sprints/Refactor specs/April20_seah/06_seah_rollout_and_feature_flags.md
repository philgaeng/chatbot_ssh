# 06 - SEAH Rollout and Feature Flags

## Objective

Define practical rollout steps for SEAH intake implementation using the simplified branch strategy.

This spec is a child of:
- `docs/Refactor specs/April20_seah/00_seah_sensitive_flow_spec.md`

Follow:
- `docs/Refactor specs/AGENT_INSTRUCTIONS.md`

---

## Branch strategy (agreed)

- Primary branch: `feat/seah-sensitive-intake`
- Optional support branch only if needed: `feat/seah-sensitive-intake-tests`
- No mandatory multi-child branch split by component.

---

## Rollout phases

1. **Phase 1: Flow and content stabilization**
   - Complete specs `01` and `02`.
2. **Phase 2: Submission/validation readiness**
   - Complete specs `03` and `04`.
3. **Phase 3: Test hardening**
   - Complete spec `05`, run full regression.
4. **Phase 4: Release readiness**
   - Resolve open blocking questions in `00`.
   - Finalize known placeholders (`REPLACE_ME`).
   - Merge to `main` after approvals and green checks.

---

## Feature-flag guidance

If rollout risk is non-trivial, gate new route behind a runtime flag:
- `ENABLE_SEAH_DEDICATED_FLOW=true|false`

When flag is `false`:
- keep legacy behavior unchanged.

When flag is `true`:
- route users through dedicated SEAH path and submission logic.

---

## Release checklist

1. All acceptance criteria from `01`-`05` met.
2. No complainant-facing SMS in SEAH path.
3. Case reference behavior validated against decisions in `00`.
4. Open `TBD` decisions explicitly accepted for demo scope where applicable.
5. Demo script prepared for:
   - survivor path
   - focal-point path
   - not-ADB-project path

---

## Post-merge follow-ups

- Track unresolved ticketing-system items in:
  - `docs/Refactor specs/April20_seah/xx-ticketing-sytem-seah.md`
- Create a short retro note on rollout friction and required hardening for production.
