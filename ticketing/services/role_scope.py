"""SH-2 — role ↔ workflow-track scope logic (single source).

A workflow step binds up to four role references (assigned / supervisor / informed /
observer). OC-06 F2: these were written verbatim with no check that the role *exists*
or matches the workflow's **track**, so wrong-track / non-existent bindings persisted
silently and produced misrouted or zero-ticket workflows.

`role_scope_matches_track` is the single source for "is this role usable on this track?"
— it mirrors the predicate previously inlined in `list_roles` (users.py). A role with
no `workflow_scope` (None) or "Both" is valid on any track.
"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ticketing.models.user import Role
from ticketing.services.admin_access import workflow_track_from_type

# Role.workflow_scope values acceptable for each workflow track.
_SCOPE_OK: dict[str, set[str | None]] = {
    "standard": {"Standard", "Both", None},
    "seah": {"SEAH", "Both", None},
}


def role_scope_matches_track(workflow_scope: str | None, track: str) -> bool:
    """True if a role with `workflow_scope` may be used on `track` ('standard'|'seah')."""
    return workflow_scope in _SCOPE_OK.get((track or "").lower(), {None})


def validate_step_roles(
    db: Session,
    *,
    workflow_type: str,
    assigned_role_key: str | None = None,
    supervisor_role: str | None = None,
    informed_roles: list[str] | None = None,
    observer_roles: list[str] | None = None,
) -> None:
    """Reject a workflow step whose role references don't exist or don't match the track.

    Raises HTTPException(422) on the first offending reference. Empty/None references are
    skipped — `assigned_role_key` may be blank at draft time (publish enforces non-empty
    separately); when present it is validated like the tier roles.
    """
    track = workflow_track_from_type(workflow_type)

    refs: list[tuple[str, str]] = []
    if assigned_role_key:
        refs.append(("assigned role", assigned_role_key))
    if supervisor_role:
        refs.append(("supervisor role", supervisor_role))
    for rk in informed_roles or []:
        if rk:
            refs.append(("informed role", rk))
    for rk in observer_roles or []:
        if rk:
            refs.append(("observer role", rk))
    if not refs:
        return

    keys = {rk for _, rk in refs}
    found: dict[str, Role] = {
        r.role_key: r
        for r in db.execute(select(Role).where(Role.role_key.in_(keys))).scalars().all()
    }
    for tier, rk in refs:
        role = found.get(rk)
        if role is None:
            raise HTTPException(
                status_code=422,
                detail=f"{tier} '{rk}' does not exist in the role catalog",
            )
        if not role_scope_matches_track(role.workflow_scope, track):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"{tier} '{rk}' is a {role.workflow_scope or 'unscoped'} role, "
                    f"but this workflow is {track} track"
                ),
            )


# ── Every job at a level must be named (doc 12 §6.2) ──────────────────────────

#: The four jobs, in the order they appear on the step editor, with the word the editor uses
#: for each. The name an author writes replaces this everywhere an officer reads it; these
#: strings exist only to say *which* job is unnamed.
TIER_JOBS: tuple[tuple[str, str], ...] = (
    ("actor", "Works it"),
    ("supervisor", "Oversees"),
    ("participant", "Kept informed"),
    ("observer", "Can view"),
)


def enabled_tiers(step) -> list[str]:
    """The jobs this level actually uses — a job is enabled by having a role bound to it."""
    out = []
    if step.assigned_role_key:
        out.append("actor")
    if step.supervisor_role:
        out.append("supervisor")
    if step.informed_roles:
        out.append("participant")
    if step.observer_roles:
        out.append("observer")
    return out


def unnamed_jobs(step) -> list[str]:
    """Enabled jobs with no author-given name, as the editor's words for them.

    The name is the whole point of the job: officers read it on the staffing screen, in the
    case view and in go-live's messages, and it is the one thing that lets a deployment use
    the words on its own contract ("Safeguard Officer", "Grievance Officer"). An unnamed job
    used to fall back to the bound role's display name, which is why the workflow screen
    looked like it was being ignored — see `r4t6v8x0`.
    """
    labels = step.tier_labels or {}
    enabled = set(enabled_tiers(step))
    return [
        word
        for tier, word in TIER_JOBS
        if tier in enabled and not ((labels.get(tier) or {}).get("label") or "").strip()
    ]


def require_named_jobs(step) -> None:
    """Raise 422 naming the jobs still waiting for a name."""
    missing = unnamed_jobs(step)
    if not missing:
        return
    raise HTTPException(
        status_code=422,
        detail=(
            "Name every job at this level before saving — still unnamed: "
            + ", ".join(f"“{m}”" for m in missing)
            + ". The name is what officers see on every screen."
        ),
    )
