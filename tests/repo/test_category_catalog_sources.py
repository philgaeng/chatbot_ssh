# SPDX-License-Identifier: Apache-2.0
"""
D-58 — the grievance taxonomy is authored in two files, and nothing compared them.

  * `backend/dev-resources/grievances_categorization_v1.1.csv` — read by the chatbot
    (`backend/config/constants.py`) and by `dev-scripts/seed_reference_data.py`.
  * `ticketing/constants/grievance_categories_default.json` — loaded by `load_default_catalog()`
    and written over `public.grievance_classification_taxonomy` by
    `sync_categories_to_public_taxonomy()`, which DELETEs the table first.

**Why this pin exists.** Both were edited for months and drifted to 64 disagreeing fields. The half
that mattered: D-49 (`1d794c6c`) repaired `high_priority` on four categories in the CSV, but the
seeder rewrites the taxonomy from the JSON, so in any environment seeded that way the repair never
arrived — the dust complaint and the SEAH route were still `high_priority=False`. D-51 (`71a91b8a`)
rewrote the six Road Hazard categories, again CSV-only. And the JSON carried the literal string
`"True"` as one category's `description`, a column-shift artefact nobody had reason to look at.

**Why the existing test could not catch it.**
`tests/backend/test_benchmark_set.py::test_the_seeded_taxonomy_matches_the_authored_csv` compares
the *seeded database* to the CSV. It went red — every CI run on this branch since 2026-08-23 — but
it can only see `high_priority`, because that is the only drifting field it reads, and it reports
the symptom ("re-seed this environment") rather than the cause: re-seeding from the ticketing path
re-applies the stale JSON. This test compares the two **authored files** directly, so it fails in
the repository, before any database exists.

**Scope comes from `scripts/ops/sync_category_catalog_json.py`, imported by path** — the same
arrangement as `test_spdx_headers.py`. Restating the field list or the comparison here would create
a hand-maintained mirror, which is the failure mode `tests/ticketing/test_boundary_policy.py` was
rewritten to remove (CLAUDE.md §Data rules, amended 2026-07-15). One definition, imported.

Fix when this goes red: `python scripts/ops/sync_category_catalog_json.py`
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "ops" / "sync_category_catalog_json.py"


def _load_script():
    """Import the sync script by path — `scripts/` is not an importable package."""
    spec = importlib.util.spec_from_file_location("sync_category_catalog_json", SCRIPT)
    assert spec and spec.loader, f"could not load {SCRIPT}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sync_script = _load_script()


# ── The mechanism is committed and re-runnable ──────────────────────────────


def test_the_sync_script_exists_and_exposes_its_api():
    """A pin whose fix is "edit 64 fields by hand" gets fixed by suppressing the pin."""
    assert SCRIPT.is_file(), "scripts/ops/sync_category_catalog_json.py is the fix for this pin"
    for name in ("differences", "sync", "SHARED_STRING_FIELDS", "derive_category_key"):
        assert hasattr(sync_script, name), f"the script must define {name}"


def test_both_authored_files_are_present():
    """An absent file makes `differences()` raise, not return []. Say which one, plainly."""
    assert sync_script.CSV_PATH.is_file(), f"missing {sync_script.CSV_PATH}"
    assert sync_script.JSON_PATH.is_file(), f"missing {sync_script.JSON_PATH}"


# ── The script's view of the catalog matches the catalog module's ───────────


def test_the_shared_field_list_matches_the_catalog_module():
    """The script compares `SHARED_STRING_FIELDS`; the catalog keeps `_STRING_FIELDS`. If the
    catalog grows a field and the script does not, the new field drifts unpinned — which is exactly
    how `intake_route` came to exist in one file only."""
    from ticketing.services.grievance_categories_catalog import _STRING_FIELDS

    assert set(sync_script.SHARED_STRING_FIELDS) == set(_STRING_FIELDS), (
        "scripts/ops/sync_category_catalog_json.py compares a different field set than "
        "ticketing/services/grievance_categories_catalog.py normalizes. Fields present in one and "
        "not the other are silently exempt from this pin."
    )


def test_category_key_derivation_agrees_with_the_catalog_module():
    """The script re-implements `derive_category_key` to stay importable without SQLAlchemy. That
    is a copy, so it is pinned behaviourally — over every real category, not a sample."""
    from ticketing.services.grievance_categories_catalog import derive_category_key as canonical

    disagreements = []
    for entry in sync_script.load_json():
        classification = entry["classification"]
        generic = entry["generic_grievance_name"]
        mine = sync_script.derive_category_key(classification, generic)
        theirs = canonical(classification, generic)
        if mine != theirs:
            disagreements.append(f"({classification!r}, {generic!r}): {mine!r} != {theirs!r}")

    assert not disagreements, (
        "the script's derive_category_key has diverged from the catalog module's:\n  "
        + "\n  ".join(disagreements)
    )


# ── The pin itself ──────────────────────────────────────────────────────────


def test_the_two_authored_taxonomies_agree():
    drift = sync_script.differences()
    assert not drift, (
        f"{len(drift)} disagreement(s) between the authored CSV and the bundled JSON — the JSON is "
        "what seeds public.grievance_classification_taxonomy, so a CSV-only edit never reaches a "
        "running system:\n  "
        + "\n  ".join(drift[:20])
        + ("\n  …" if len(drift) > 20 else "")
        + "\n\nFix: python scripts/ops/sync_category_catalog_json.py"
    )


def test_every_category_carries_an_intake_route():
    """`intake_route` exists only in the JSON, so `sync()` carries it across per category rather
    than deriving it, and a category added to the CSV arrives without one.

    ⚠ Nothing reads it today: `normalize_category_entry()` builds its output from `category_key`,
    `_STRING_FIELDS` and `high_priority`, so `load_default_catalog()` drops the field before it
    reaches `ticketing.settings`. This pin therefore guards authored data, not a live code path —
    it exists so a re-sync cannot quietly discard a field the CSV can never restore."""
    missing = [
        entry.get("category_key") for entry in sync_script.load_json() if not entry.get("intake_route")
    ]
    assert not missing, (
        f"{len(missing)} category/categories have no intake_route: {missing}. The CSV cannot supply "
        "one — set it by hand in ticketing/constants/grievance_categories_default.json."
    )


# ── Mutation checks: the pin goes red when it should ────────────────────────


@pytest.mark.parametrize("field", ["description", "high_priority"])
def test_the_pin_goes_red_when_a_json_field_drifts(monkeypatch, field):
    """A comparison that reports [] for the wrong reason is worse than none. Mutate one field of
    one entry and require a report naming it."""
    entries = sync_script.load_json()
    victim = dict(entries[0])
    victim[field] = "drifted" if field == "description" else not victim[field]
    monkeypatch.setattr(sync_script, "load_json", lambda: [victim] + entries[1:])

    drift = sync_script.differences()
    assert any(field in line for line in drift), (
        f"mutating {field} produced no report — the comparison is not reading it"
    )


def test_the_pin_goes_red_when_a_category_is_dropped(monkeypatch):
    entries = sync_script.load_json()
    monkeypatch.setattr(sync_script, "load_json", lambda: entries[1:])

    drift = sync_script.differences()
    assert any("absent from the JSON" in line for line in drift), (
        "removing a category from the JSON produced no report"
    )
