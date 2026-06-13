"""Category resolution when complainant confirms LLM taxonomy in Nepali sessions."""

from types import SimpleNamespace

from backend.actions.base_classes.base_mixins import LanguageHelpersMixin


class _CategoryHarness(LanguageHelpersMixin):
    def name(self):
        return "test_category_harness"


def test_english_labels_preserved_when_language_is_ne():
    harness = _CategoryHarness()
    harness.language_code = "ne"
    categories = ["Air Pollution - Air Pollution", "Dust - Dust"]
    assert harness._get_categories_in_english(categories) == categories


def test_resolve_from_local_slot_when_english_labels():
    harness = _CategoryHarness()
    harness.language_code = "ne"
    tracker = SimpleNamespace(
        slots={
            "grievance_categories_local": [
                "Air Pollution - Air Pollution",
                "Dust - Dust",
            ],
            "grievance_categories": [],
        }
    )
    tracker.get_slot = lambda name: tracker.slots.get(name)
    assert harness._resolve_grievance_categories_for_db(tracker) == [
        "Air Pollution - Air Pollution",
        "Dust - Dust",
    ]
