# 01 - SEAH Route and Slots

## Objective

Implement the dedicated SEAH intake route and slot contract for chatbot flow control.

This spec is a child of:
- `docs/Refactor specs/April20_seah/00_seah_sensitive_flow_spec.md`

Follow:
- `docs/Refactor specs/AGENT_INSTRUCTIONS.md`

---

## Scope

In scope:
- Add/confirm dedicated SEAH entry route from main menu.
- Define SEAH intake slot list and ordering.
- Implement conditional branch for `I am the SEAH focal point`.
- Implement `Not an ADB project` branch behavior per decisions in `00`.
- Ensure non-SEAH flows remain stable.

Out of scope:
- SEAH storage schema and persistence implementation.
- Internal ticketing workflow and access control policy details.

---

## Files likely touched

- `backend/orchestrator/config/domain.yml`
- `backend/orchestrator/config/source/stories/stories.yml`
- `backend/orchestrator/state_machine.py`
- `backend/actions/forms/form_sensitive_issues.py` (or replacement SEAH form module)
- optional supporting action registration/config files

---

## Slot contract (v1)

Implement and/or confirm slots for:
- identity mode (identified/anonymous)
- victim/survivor role response
- phone and email (independently skippable)
- project identification (`cannot_specify`, `not_adb_project`)
- incident summary
- focal-point assessment fields
- informed contact consent channel

Canonical skip value:
- `skipped` (project standard)

---

## Acceptance criteria

1. User can enter dedicated SEAH route from menu.
2. Flow follows agreed question order from `00`.
3. Focal-point-only questions appear only for focal-point role.
4. `Not an ADB project` branch behaves as specified in `00`.
5. Non-SEAH route behavior remains unchanged.

---

## Test requirements

- Unit tests for slot extraction/validation and branch switching.
- Integration/state-machine tests for end-to-end SEAH route progression.
- Regression tests for existing non-SEAH paths.

---

## Delivery checklist

- Update any slot/action docs as needed.
- Note final slot names and values in PR description for downstream specs (`03`, `04`, `05`).
