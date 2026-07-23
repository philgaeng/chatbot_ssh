"""Shared SEAH form slot logic (H2-08).

`ValidateFormSeah2` (victim intake) and `ValidateFormSeahFocalPoint2` (focal-point intake)
are copy-paste siblings: identical `seah_project_identification` extract/validate, identical
`sensitive_issues_new_detail` extract, and a `sensitive_issues_new_detail` validate that differs
only in two parameters. Their multiselect ask-actions repeated one button builder verbatim.

This module holds the single source of truth:

* `SeahSharedFormMixin` — mixed into both `BaseFormValidationAction` subclasses. Its methods
  call `self.*` (`_handle_slot_extraction`, `validate_seah_project_identification_value`,
  `SKIP_VALUE`, …) resolved through the concrete form's MRO, so the mixin is only meaningful
  when combined with `BaseFormValidationAction`.
* `build_seah_multiselect_buttons` — the one button builder for the focal multiselect ask
  actions.

Utterance keys are unaffected: `file_name` derives from the *concrete* class's module and
ask-actions resolve utterances/buttons via `self.name()` (see base_mixins `ActionHelpersMixin`),
so moving these bodies into the mixin changes no lookup key.
"""
from typing import Any, Dict, List, Text

from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict


class SeahSharedFormMixin:
    """Shared SEAH slot extract/validate logic for the victim and focal-point forms.

    Subclasses set the two `sensitive_issues_new_detail` parameters as class attributes:
      * ``_SEAH_DETAIL_SKIP_ALLOWED`` — victim form accepts skip (default slot ``SKIP_VALUE``);
        focal form requires an incident summary (default slot ``None`` → re-ask).
      * ``_SEAH_DETAIL_MIN_LENGTH`` — minimum accepted detail length. Preserves the original
        thresholds exactly: the victim form's ``len > 3`` is encoded as ``>= 4`` (identical for
        integer lengths); the focal form's ``len >= 8`` as ``>= 8``.
    """

    # Overridden per form; these defaults mirror the victim form.
    _SEAH_DETAIL_SKIP_ALLOWED: bool = True
    _SEAH_DETAIL_MIN_LENGTH: int = 4

    async def extract_seah_project_identification(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        latest_text = (tracker.latest_message or {}).get("text")
        if isinstance(latest_text, str) and latest_text.strip().startswith("/"):
            return {"seah_project_identification": latest_text.strip().lstrip("/")}
        return await self._handle_slot_extraction(
            "seah_project_identification",
            tracker,
            dispatcher,
            domain,
        )

    async def validate_seah_project_identification(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        lang = getattr(self, "language_code", None) or tracker.get_slot("language_code") or "en"
        return self.validate_seah_project_identification_value(
            slot_value,
            language_code=lang,
        )

    async def extract_sensitive_issues_new_detail(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "sensitive_issues_new_detail",
            tracker,
            dispatcher,
            domain,
        )

    async def validate_sensitive_issues_new_detail(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        return self._validate_sensitive_issues_new_detail(
            slot_value,
            tracker,
            skip_allowed=self._SEAH_DETAIL_SKIP_ALLOWED,
            min_length=self._SEAH_DETAIL_MIN_LENGTH,
        )

    def _validate_sensitive_issues_new_detail(
        self,
        slot_value: Any,
        tracker: Tracker,
        *,
        skip_allowed: bool,
        min_length: int,
    ) -> Dict[Text, Any]:
        expected_values = {"restart", "add_more_details", "submit_details"}
        if isinstance(slot_value, str):
            slot_value = slot_value.strip()
            slot_value = slot_value.lstrip("/")

        if slot_value == "restart":
            return {
                "sensitive_issues_new_detail": None,
                "grievance_description": None,
                "grievance_description_status": "restart",
            }

        if slot_value == "add_more_details":
            return {
                "sensitive_issues_new_detail": None,
                "grievance_description_status": "add_more_details",
            }

        if slot_value == "submit_details":
            return {
                "sensitive_issues_new_detail": "completed",
                "grievance_description": tracker.get_slot("grievance_description"),
                "grievance_description_status": "completed",
            }

        # Victim form accepts skip → default SKIP_VALUE; focal form requires a summary → None.
        default_value = self.SKIP_VALUE if skip_allowed else None
        slots: Dict[Text, Any] = {"sensitive_issues_new_detail": default_value}
        if (
            slot_value not in [self.SKIP_VALUE, None]
            and slot_value not in expected_values
            and len(slot_value.strip()) >= min_length
        ):
            existing_description = tracker.get_slot("grievance_description")
            base_text = (
                existing_description.strip()
                if isinstance(existing_description, str) and existing_description.strip()
                else ""
            )
            new_text = slot_value.strip()
            slots["sensitive_issues_new_detail"] = None
            slots["grievance_description"] = f"{base_text}\n{new_text}" if base_text else new_text
            slots["grievance_description_status"] = "show_options"
        return slots


def build_seah_multiselect_buttons(
    action: Any,
    tracker: Tracker,
    selected_slot: Text,
) -> List[Dict[Text, Any]]:
    """Buttons for a focal-point multiselect ask action: the slot's option buttons minus the
    already-selected ones, plus a localized Done button.

    `action.get_buttons(1)` resolves via the concrete ask-action's `self.name()`, so each
    action still gets its own option set — only the repeated builder body is shared.
    """
    language_code = tracker.get_slot("language_code") or "en"
    selected = tracker.get_slot(selected_slot) or []
    if not isinstance(selected, list):
        selected = [str(selected)]
    buttons = [b for b in (action.get_buttons(1) or []) if b.get("title") not in selected]
    done_title = "Done" if language_code == "en" else "सम्पन्न"
    buttons.append({"title": done_title, "payload": "/selection_done"})
    return buttons
