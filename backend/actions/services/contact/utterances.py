"""Utterance lookup for form_contact validators."""

from backend.actions.utils.utterance_mapping_rasa import get_utterance_base


def contact_utterance(function_name: str, language_code: str, index: int = 1) -> str:
    return get_utterance_base("form_contact", function_name, index, language_code)
