# SPDX-License-Identifier: Apache-2.0

"""
D-51 — a category value either resolves onto the live taxonomy or it does not get stored.

**The four cases at the top are the ones the model actually produced**, measured over the 105-item
benchmark (`docs/dpg/model-benchmarks.md` §3.1). They are here so the repair is pinned to observed
behaviour rather than to what a repair *could* plausibly need to handle.

⚠ The other half of this file matters as much: **what must NOT be repaired.** A resolver that
guesses is worse than one that drops, because a wrong category is stored, shown to the complainant
as the system's understanding of their complaint, and synced to ticketing — silently.
"""
from __future__ import annotations

import pytest

from backend.config.constants import CLASSIFICATION_DATA
from backend.services.category_resolution import (
    build_leaf_index,
    fold_category_key,
    resolve_categories,
)


# ── what the model actually got wrong ────────────────────────────────────────

@pytest.mark.parametrize(
    "produced, expected",
    [
        # The classification half dropped. A formatting failure, not a new concept.
        ("Cultural Site Disturbances", "Cultural, Social - Cultural Site Disturbances"),
        ("Wildlife Passage", "Wildlife, Environmental - Wildlife Passage"),
        # A real leaf filed under the wrong family: the model asking for a seventh Road Hazard
        # subcategory when the leaf it names already exists under Environmental.
        ("Road Hazard - Noise Pollution", "Environmental - Noise Pollution"),
        # The doubled-leaf form our own Nepali round-trip used to write (see
        # tests/shared/test_grievance_categories_resolve.py).
        ("Air Pollution - Air Pollution", "Environmental - Air Pollution"),
    ],
)
def test_the_categories_the_benchmark_saw_invented_all_resolve(produced, expected):
    resolution = resolve_categories([produced], CLASSIFICATION_DATA)

    assert resolution.kept == [expected]
    assert resolution.repaired == [(produced, expected)]
    assert resolution.dropped == []


def test_a_canonical_key_is_left_exactly_alone():
    """The common case. A resolver that rewrites correct answers is a resolver nobody can trust."""
    keys = list(CLASSIFICATION_DATA)[:5]
    resolution = resolve_categories(keys, CLASSIFICATION_DATA)

    assert resolution.kept == keys
    assert not resolution.changed


def test_casing_and_hyphens_are_folded_not_dropped():
    resolution = resolve_categories(["environmental - air pollution"], CLASSIFICATION_DATA)
    assert resolution.kept == ["Environmental - Air Pollution"]


# ── what must not be repaired ────────────────────────────────────────────────

def test_a_category_that_exists_nowhere_is_dropped_and_reported():
    """⚠ This is the whole point. It used to be logged and then stored anyway."""
    resolution = resolve_categories(["Teleportation Damage"], CLASSIFICATION_DATA)

    assert resolution.kept == []
    assert resolution.dropped == ["Teleportation Damage"]


def test_a_bare_classification_is_not_resolved_to_one_of_its_children():
    """`Environmental` names six leaves. Picking one would be inventing the complainant's answer."""
    assert resolve_categories(["Environmental"], CLASSIFICATION_DATA).dropped == ["Environmental"]


def test_a_leaf_two_classifications_share_is_refused_rather_than_guessed():
    """
    An administrator may add `Safety - Dust` beside `Road Hazard - Dust` tomorrow. On that day a
    bare `Dust` stops being answerable, and saying so is the honest outcome — silently keeping
    whichever key was iterated first would make the repair depend on dictionary order.
    """
    catalogue = ["Road Hazard - Dust", "Safety - Dust", "Environmental - Air Pollution"]

    assert "dust" not in build_leaf_index(catalogue)
    assert resolve_categories(["Dust"], catalogue).dropped == ["Dust"]
    # The unambiguous neighbour is unaffected.
    assert resolve_categories(["Air Pollution"], catalogue).kept == [
        "Environmental - Air Pollution"
    ]


def test_resolution_never_reaches_outside_the_catalogue_it_was_given():
    """The catalogue is admin-configurable and passed in; nothing here may consult a global."""
    catalogue = ["Only - One"]
    resolution = resolve_categories(["Environmental - Air Pollution", "One"], catalogue)

    assert resolution.kept == ["Only - One"]
    assert resolution.dropped == ["Environmental - Air Pollution"]


# ── list hygiene ─────────────────────────────────────────────────────────────

def test_two_spellings_of_the_same_category_collapse_to_one():
    resolution = resolve_categories(
        ["Environmental - Air Pollution", "Air Pollution"], CLASSIFICATION_DATA
    )
    assert resolution.kept == ["Environmental - Air Pollution"]


def test_exclude_keeps_an_alternative_from_duplicating_the_primary_it_resolved_onto():
    resolution = resolve_categories(
        ["Road Hazard - Noise Pollution"],
        CLASSIFICATION_DATA,
        exclude=["Environmental - Noise Pollution"],
    )
    assert resolution.kept == []
    assert resolution.dropped == []


@pytest.mark.parametrize("junk", [None, "", "   "])
def test_empty_values_are_skipped_not_reported_as_inventions(junk):
    assert not resolve_categories([junk], CLASSIFICATION_DATA).changed


# ── the fold the benchmark scores with ───────────────────────────────────────

def test_the_fold_keeps_a_hyphen_inside_a_name_and_the_separator_apart():
    """`Gender-Based Access Issues` is why the fold splits on `" - "` before touching hyphens."""
    assert fold_category_key("gender - gender-based access issues") == (
        "Gender - Gender Based Access Issues"
    )


def test_the_benchmark_scores_with_this_exact_fold():
    """
    ⚠ Product and measurement must agree on what "the same category" means. The benchmark used to
    carry its own copy of this rule; it now delegates, and this is the pin that keeps it doing so.
    """
    from scripts.ops.llm_benchmark import canonical_category

    assert canonical_category is fold_category_key
