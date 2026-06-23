"""Thin validate_* delegates for ContactFormValidationAction (imported into form_contact)."""

from __future__ import annotations

from typing import Any, Dict, Text

from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from backend.actions.services.contact import seah_merge
from backend.actions.services.contact import validators as contact_validators


class ContactValidationDelegates:
    """Mixin-style helpers — mixed into ContactFormValidationAction via multiple inheritance."""

    def _merge_seah_contact_provided_from_partial(
        self, tracker: Tracker, partial: Dict[str, Any]
    ) -> Dict[str, Any]:
        return seah_merge.merge_seah_contact_and_party_slots(
            tracker.get_slot("story_main"),
            dict(tracker.current_slot_values()),
            partial,
            helpers=self.helpers,
            default_values=self.DEFAULT_VALUES,
        )

    async def validate_complainant_province(
        self, slot_value, dispatcher, tracker, domain
    ) -> Dict[Text, Any]:
        return contact_validators.validate_province(
            slot_value, dispatcher,
            helpers=self.helpers, skip_value=self.SKIP_VALUE, language_code=self.language_code,
        )

    async def validate_complainant_district(
        self, slot_value, dispatcher, tracker, domain
    ) -> Dict[Text, Any]:
        return contact_validators.validate_district(
            slot_value, dispatcher, tracker,
            helpers=self.helpers, skip_value=self.SKIP_VALUE, language_code=self.language_code,
        )

    async def validate_complainant_municipality_temp(
        self, slot_value, dispatcher, tracker, domain
    ) -> Dict[Text, Any]:
        return contact_validators.validate_municipality_temp(
            slot_value, tracker, helpers=self.helpers, skip_value=self.SKIP_VALUE,
        )

    async def validate_complainant_municipality_confirmed(
        self, slot_value, dispatcher, tracker, domain
    ) -> Dict[Text, Any]:
        return contact_validators.validate_municipality_confirmed(slot_value, tracker)

    async def validate_complainant_village_temp(
        self, slot_value, dispatcher, tracker, domain
    ) -> Dict[Text, Any]:
        return contact_validators.validate_village_temp(
            slot_value, dispatcher, tracker,
            helpers=self.helpers, skip_value=self.SKIP_VALUE, language_code=self.language_code,
        )

    async def validate_complainant_village_confirmed(
        self, slot_value, dispatcher, tracker, domain
    ) -> Dict[Text, Any]:
        return contact_validators.validate_village_confirmed(slot_value, tracker)

    async def validate_complainant_ward(
        self, slot_value, dispatcher, tracker, domain
    ) -> Dict[Text, Any]:
        return contact_validators.validate_ward(slot_value, skip_value=self.SKIP_VALUE)

    async def validate_complainant_address_temp(
        self, slot_value, dispatcher, tracker, domain
    ) -> Dict[Text, Any]:
        return contact_validators.validate_address_temp(
            slot_value, dispatcher, skip_value=self.SKIP_VALUE, language_code=self.language_code,
        )

    async def validate_complainant_address_confirmed(
        self, slot_value, dispatcher, tracker, domain
    ) -> Dict[Text, Any]:
        return contact_validators.validate_address_confirmed(
            slot_value, tracker, dispatcher,
            language_code=self.language_code,
            helpers=self.helpers,
            default_values=self.DEFAULT_VALUES,
        )

    async def validate_complainant_location_consent(
        self, slot_value, dispatcher, tracker, domain
    ) -> Dict[Text, Any]:
        return contact_validators.validate_location_consent(slot_value, skip_value=self.SKIP_VALUE)

    async def validate_complainant_consent(
        self, slot_value, dispatcher, tracker, domain
    ) -> Dict[Text, Any]:
        return contact_validators.validate_consent(
            slot_value, tracker,
            skip_value=self.SKIP_VALUE,
            helpers=self.helpers,
            default_values=self.DEFAULT_VALUES,
        )

    async def validate_complainant_full_name(
        self, slot_value, dispatcher, tracker, domain
    ) -> Dict[Text, Any]:
        return contact_validators.validate_full_name(
            slot_value, dispatcher, tracker,
            skip_value=self.SKIP_VALUE,
            language_code=self.language_code,
            helpers=self.helpers,
            default_values=self.DEFAULT_VALUES,
        )

    async def validate_complainant_email_temp(
        self, slot_value, dispatcher, tracker, domain
    ) -> Dict[Text, Any]:
        return contact_validators.validate_email_temp(
            slot_value, dispatcher, tracker,
            skip_value=self.SKIP_VALUE,
            language_code=self.language_code,
            helpers=self.helpers,
            default_values=self.DEFAULT_VALUES,
        )

    async def validate_complainant_email_confirmed(
        self, slot_value, dispatcher, tracker, domain
    ) -> Dict[Text, Any]:
        return contact_validators.validate_email_confirmed(
            slot_value, tracker,
            skip_value=self.SKIP_VALUE,
            helpers=self.helpers,
            default_values=self.DEFAULT_VALUES,
        )
