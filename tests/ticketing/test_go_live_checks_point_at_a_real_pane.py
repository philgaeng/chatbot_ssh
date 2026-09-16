"""Every go-live check names the pane that fixes it — and that pane must exist, and must be
the one holding the control.

A check carries `section=`, and the project console uses it for three things at once: the rail's
coloured dot, the one-line hint under a section, and the "Fix →" jump. So the string is a
promise: *this is where you go to fix this*.

Two ways it broke on 2026-08-08, both silent:

  • **B3** ("every package names the organizations it needs") stayed `section="packages"` after
    the per-package organization editor moved to **Organizations**. The rail put a red dot and
    a Fix button on a screen that no longer had the control.
  • A check pointing at a section key that no longer exists — `locations` was folded into
    `packages` the same day — does not error. `sectionOfCheck()` returns null and the check
    **vanishes from the rail**: still blocking activation, now invisible. Worse than wrong.

`projectSections.ts` is the single list, and this pins the Python against it.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
GO_LIVE = REPO / "ticketing" / "services" / "project_go_live.py"
SECTIONS_TS = (
    REPO / "channels" / "ticketing-ui" / "components" / "settings" / "projects" / "projectSections.ts"
)


def _section_keys() -> set[str]:
    """The `SectionKey` union in projectSections.ts — the console's whole taxonomy."""
    src = SECTIONS_TS.read_text()
    union = re.search(r"export type SectionKey =(.*?);", src, re.S)
    assert union, "SectionKey union not found — projectSections.ts changed shape"
    return set(re.findall(r'"([a-z_]+)"', union.group(1)))


def _sections_used() -> set[str]:
    return set(re.findall(r'section="([a-z_]+)"', GO_LIVE.read_text()))


def test_every_check_points_at_a_section_that_exists():
    unknown = _sections_used() - _section_keys()
    assert not unknown, (
        f"go-live checks point at panes that do not exist: {sorted(unknown)}. "
        "sectionOfCheck() drops these, so the check disappears from the rail while still "
        "blocking activation."
    )


def test_package_organizations_are_fixed_under_organizations():
    """B3's control lives in the Organizations section, so B3 must send the reader there.

    Pinned by name because it is the one that got it wrong: the editor moved and the check did
    not, which is invisible in a diff and obvious on screen.
    """
    src = GO_LIVE.read_text()
    b3 = re.search(r'id="B3".*?section="([a-z_]+)"', src, re.S)
    assert b3, "B3 check not found"
    assert b3.group(1) == "actors", (
        f'B3 points at "{b3.group(1)}"; the per-package organization editor is in the '
        "Organizations section (`actors`)."
    )


@pytest.mark.integration
def test_b3_reports_actors_at_runtime(db, kl_road_project):
    """The source check above reads the literal; this reads what the service actually emits."""
    from ticketing.services import project_go_live as go_live_svc

    report = go_live_svc.evaluate_go_live(db, kl_road_project.project_id)
    b3 = next((c for c in report.checks if c.id == "B3"), None)
    if b3 is None:
        pytest.skip("KL Road's type marks no organization per package")
    assert b3.section == "actors"
