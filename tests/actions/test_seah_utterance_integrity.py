"""H2-08 utterance-integrity guard for the SEAH flow.

Cheap structural checks that prevent the EN/NE drift class this ticket fixed:
  * every SEAH utterance resolves for both `en` and `ne` (non-empty);
  * no NE value equals its EN value (the untranslated-placeholder smell), except keys
    explicitly whitelisted here with a reason.
"""
import pytest

from backend.actions.utils.utterance_mapping_rasa import (
    SENSITIVE_ISSUES_UTTERANCES_AND_BUTTONS,
    UTTERANCE_MAPPING,
)

SEAH_FORMS = ["form_seah_2", "form_seah_focal_point"]

# Keys whose NE may legitimately equal EN (e.g. a bare URL/code). Empty today — add entries
# with a one-line justification if a genuinely language-neutral string appears.
NE_EQUALS_EN_WHITELIST: set = set()


def _seah_utterance_rows():
    rows = []
    for form in SEAH_FORMS:
        for action, block in UTTERANCE_MAPPING.get(form, {}).items():
            for idx, d in block.get("utterances", {}).items():
                rows.append((f"{form}.{action}.{idx}", d))
    for idx, d in SENSITIVE_ISSUES_UTTERANCES_AND_BUTTONS["utterances"].items():
        rows.append((f"sensitive_issues_referral.{idx}", d))
    return rows


_ROWS = _seah_utterance_rows()
_IDS = [key for key, _ in _ROWS]


@pytest.mark.parametrize("key,entry", _ROWS, ids=_IDS)
def test_seah_utterance_has_en_and_ne(key, entry):
    for lang in ("en", "ne"):
        assert lang in entry, f"{key}: missing '{lang}'"
        assert isinstance(entry[lang], str) and entry[lang].strip(), f"{key}: empty '{lang}'"


@pytest.mark.parametrize("key,entry", _ROWS, ids=_IDS)
def test_seah_ne_not_equal_en(key, entry):
    if key in NE_EQUALS_EN_WHITELIST:
        return
    assert entry["ne"].strip() != entry["en"].strip(), (
        f"{key}: NE equals EN — untranslated placeholder (whitelist here if intentional)"
    )


def test_seah_menu_button_is_translated_and_not_tripled():
    buttons = UTTERANCE_MAPPING["action_ask_commons"]["action_ask_story_main"]["buttons"][1]
    en = next(b["title"] for b in buttons["en"] if "seah_intake" in b["payload"])
    ne = next(b["title"] for b in buttons["ne"] if "seah_intake" in b["payload"])
    assert ne != en
    # The old bug repeated "असुरक्षित व्यवहार" three times instead of translating SEA/H.
    assert ne.count("असुरक्षित व्यवहार") <= 1


def test_shared_sensitive_issues_block_is_single_source():
    """The victim and focal forms must reference the SAME merged block (no re-drift)."""
    victim = UTTERANCE_MAPPING["form_seah_2"]["action_ask_form_seah_2_sensitive_issues_new_detail"]
    focal = UTTERANCE_MAPPING["form_seah_focal_point"][
        "action_ask_form_seah_focal_point_2_sensitive_issues_new_detail"
    ]
    assert victim is focal, "the two forms should share one sensitive_issues_new_detail block"
