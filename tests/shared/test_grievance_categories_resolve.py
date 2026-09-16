"""Category resolution when a complainant confirms the LLM taxonomy in a Nepali session.

⚠ **This file pinned the bug it was written to describe** (D-51, fixed 2026-08-25). Its fixtures
were `"Air Pollution - Air Pollution"` and `"Dust - Dust"` — not categories, but the output of
`categories_in_local_language`, which looked the *leaf* up in a catalogue keyed by
`Classification - Leaf`, missed every time, and doubled the leaf. Those values then reached the
database through the very method under test here, where they matched no filter, no report and no
`high_priority` lookup. The assertions were copied from the observed output, so the net held the
defect in place instead of catching it.

What is pinned now: a Nepali session round-trips to **canonical keys**, and the legacy doubled
form still in live slots resolves home rather than being stored as-is.
"""

from types import SimpleNamespace

from backend.actions.base_classes.base_mixins import LanguageHelpersMixin

AIR = "Environmental - Air Pollution"
DUST = "Road Hazard - Dust"


class _CategoryHarness(LanguageHelpersMixin):
    def name(self):
        return "test_category_harness"


def _harness(language_code: str = "ne") -> _CategoryHarness:
    harness = _CategoryHarness()
    harness.language_code = language_code
    return harness


def _tracker(**slots) -> SimpleNamespace:
    tracker = SimpleNamespace(slots=slots)
    tracker.get_slot = lambda name: tracker.slots.get(name)
    return tracker


def test_english_labels_preserved_when_language_is_ne():
    """The UI may show English taxonomy labels in a Nepali session; they must pass through."""
    assert _harness()._get_categories_in_english([AIR, DUST]) == [AIR, DUST]


def test_a_nepali_session_round_trips_to_canonical_keys():
    """Key → Nepali label → key. The middle step is what stored junk for months."""
    harness = _harness()
    local = harness._get_categories_in_local_language([AIR, DUST])

    assert local != [AIR, DUST], "a Nepali session must actually see Nepali"
    assert harness._get_categories_in_english(local) == [AIR, DUST]


def test_resolve_from_local_slot_when_english_labels():
    """The local slot is preferred for the DB write, so it has to resolve to real keys."""
    tracker = _tracker(grievance_categories_local=[AIR, DUST], grievance_categories=[])
    assert _harness()._resolve_grievance_categories_for_db(tracker) == [AIR, DUST]


def test_the_legacy_doubled_leaf_form_resolves_instead_of_being_stored():
    """`Air Pollution - Air Pollution` is in live slots. It must not reach the database as-is."""
    tracker = _tracker(
        grievance_categories_local=["Air Pollution - Air Pollution", "Dust - Dust"],
        grievance_categories=[],
    )
    assert _harness()._resolve_grievance_categories_for_db(tracker) == [AIR, DUST]


def test_an_unknown_label_is_never_translated_into_something_it_is_not():
    """Repair only where the taxonomy answers. Passing it through beats inventing a mapping."""
    harness = _harness()
    assert harness._get_categories_in_local_language(["Teleportation Damage"]) == [
        "Teleportation Damage"
    ]
    assert harness._get_categories_in_english(["Teleportation Damage"]) == [
        "Teleportation Damage"
    ]


def test_a_category_missing_its_classification_half_does_not_crash_the_review_step():
    """`Wildlife Passage` — the classifier's own malformed shape — used to raise IndexError here."""
    assert _harness()._get_categories_in_local_language(["Wildlife Passage"]) == [
        "Wildlife Passage"
    ]
