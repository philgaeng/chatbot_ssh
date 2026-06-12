from abc import ABC, abstractmethod
import logging
from typing import Any, Dict, List, Literal, Optional, Text, Tuple

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher
from backend.actions.services.messaging import grievance_data as messaging_grievance_data
from backend.actions.services.messaging import recap_email as messaging_recap
from backend.actions.services.messaging import sms as messaging_sms
from backend.actions.services.routing import form_next_action as routing
from backend.actions.services.seah import contact_channels as seah_channels
from backend.actions.services.seah import contact_points as seah_contact_points
from backend.actions.services.seah import outro as seah_outro
from backend.actions.services.seah import party_payload as seah_party
from backend.actions.services.seah import project_identification as seah_project
from backend.actions.services.seah import sensitive_detection as seah_sensitive
from backend.actions.services.status_check import (
    complainant_hydrate,
    display as status_display,
    follow_up,
    full_name_lookup,
    grievance_lookup,
    name_matching,
    phone_retrieval,
    slot_reset,
)
from backend.actions.utils import language as language_helpers
from backend.actions.utils.mapping_buttons import (
    BUTTON_AFFIRM,
    BUTTON_DENY,
    BUTTON_SKIP,
    VALIDATION_SKIP,
)
from backend.actions.utils.utterance_mapping_rasa import (
    SENSITIVE_ISSUES_UTTERANCES_AND_BUTTONS,
    UTTERANCE_MAPPING,
    get_buttons_base,
    get_utterance_base,
)
from backend.config.constants import (
    DEFAULT_VALUES,
    LLM_CLASSIFICATION,
)
from backend.config.database_constants import (
    GRIEVANCE_CLASSIFICATION_STATUS,
    GRIEVANCE_STATUS,
    TASK_STATUS,
)
from backend.services.database_services.postgres_services import db_manager
from backend.shared_functions.helpers_repo import helpers_repo

DEFAULT_LANGUAGE_CODE = DEFAULT_VALUES["DEFAULT_LANGUAGE_CODE"]
SKIP_VALUE = DEFAULT_VALUES["SKIP_VALUE"]


class ActionCommonMixin(Action, ABC):
    """Shared init: logger, db_manager, constants."""

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.file_name = self.__class__.__module__.split(".")[-1]
        self.helpers = helpers_repo
        self.db_manager = db_manager
        self.SENSITIVE_ISSUES_UTTERANCES_AND_BUTTONS = SENSITIVE_ISSUES_UTTERANCES_AND_BUTTONS
        self.SKIP_VALUE = SKIP_VALUE
        self.VALIDATION_SKIP = VALIDATION_SKIP
        self.DEFAULT_LANGUAGE_CODE = DEFAULT_LANGUAGE_CODE
        self.DEFAULT_PROVINCE = DEFAULT_VALUES["DEFAULT_PROVINCE"]
        self.DEFAULT_DISTRICT = DEFAULT_VALUES["DEFAULT_DISTRICT"]
        self.DEFAULT_OFFICE = DEFAULT_VALUES["DEFAULT_OFFICE"]
        self.BUTTON_SKIP = BUTTON_SKIP
        self.BUTTON_AFFIRM = BUTTON_AFFIRM
        self.BUTTON_DENY = BUTTON_DENY
        self.DEFAULT_VALUES = DEFAULT_VALUES
        self.TASK_STATUS = TASK_STATUS
        self.GRIEVANCE_CLASSIFICATION_STATUS = GRIEVANCE_CLASSIFICATION_STATUS
        self.GRIEVANCE_STATUS = GRIEVANCE_STATUS
        self.helpers_repo = helpers_repo
        self.NOT_PROVIDED = self.DEFAULT_VALUES["NOT_PROVIDED"]
        self.LLM_CLASSIFICATION = LLM_CLASSIFICATION

    @abstractmethod
    def name(self) -> Text:
        pass


class LanguageHelpersMixin(ActionCommonMixin):
    """Language/skip helpers — logic in backend.actions.utils.language."""

    def detect_language(self, text: str) -> str:
        return language_helpers.detect_language(text)

    def _get_fuzzy_match_score(self, text: str, target_words: List[str]) -> Tuple[float, str]:
        return language_helpers.fuzzy_match_score(text, target_words)

    def is_skip_instruction(self, input_text: str) -> Tuple[bool, bool, str]:
        return language_helpers.is_skip_instruction(input_text)

    def _validate_string_length(self, text: str, min_length: int = 2) -> bool:
        return language_helpers.validate_string_length(text, min_length)

    def _update_language_code_and_location_info(self, tracker: Tracker) -> None:
        self.language_code = tracker.get_slot("language_code") or self.DEFAULT_LANGUAGE_CODE
        self.province = tracker.get_slot("complainant_province") or self.DEFAULT_PROVINCE
        self.district = tracker.get_slot("complainant_district") or self.DEFAULT_DISTRICT
        self.office = tracker.get_slot("complainant_office") or self.DEFAULT_OFFICE

    def _initialize_language_and_helpers(self, tracker: Tracker) -> None:
        self._update_language_code_and_location_info(tracker)
        if not hasattr(self, "keyword_detector"):
            self.keyword_detector = self.helpers.keyword_detector
        else:
            if not hasattr(self.keyword_detector, "language_code"):
                self.keyword_detector._initialize_constants(self.language_code)
            if self.keyword_detector.language_code != self.language_code:
                self.keyword_detector._initialize_constants(self.language_code)

        if not hasattr(self, "location_validator"):
            self.location_validator = self.helpers.location_validator
        else:
            if not hasattr(self.location_validator, "language_code"):
                self.location_validator._initialize_constants(self.language_code)
            if self.location_validator.language_code != self.language_code:
                self.location_validator._initialize_constants(self.language_code)

    def _get_categories_in_local_language(self, categories: List[str]) -> List[str]:
        return language_helpers.categories_in_local_language(categories, self.language_code)

    def _get_categories_in_english(self, categories: List[str]) -> List[str]:
        return language_helpers.categories_in_english(categories, self.language_code)

    def is_valid_email(self, email: str) -> bool:
        return language_helpers.is_valid_email(email)

    def get_status_and_description_str_in_language(self, status: str) -> str:
        return language_helpers.status_and_description_in_language(status, self.language_code)


class SensitiveContentHelpersMixin(ActionCommonMixin):
    """SEAH / sensitive intake — logic in backend.actions.services.seah."""

    def __init__(self):
        super().__init__()
        self.PARTY_SLOT_BY_ROLE = seah_party.PARTY_SLOT_BY_ROLE

    def detect_sensitive_content(
        self, dispatcher: CollectingDispatcher, slot_value: str
    ) -> Dict[Text, Any]:
        return seah_sensitive.detect_sensitive_content_slots(
            self.helpers, slot_value, self.language_code
        )

    def dispatch_sensitive_content_utterances_and_buttons(
        self, dispatcher: CollectingDispatcher
    ) -> None:
        seah_sensitive.dispatch_sensitive_content_utterances(
            dispatcher,
            self.language_code,
            self.SENSITIVE_ISSUES_UTTERANCES_AND_BUTTONS,
        )

    def get_available_seah_contact_channels(
        self, phone_value: Any, email_value: Any
    ) -> List[str]:
        return seah_channels.get_available_seah_contact_channels(
            self.helpers, phone_value, email_value
        )

    def build_seah_contact_channel_buttons(
        self,
        buttons: List[Dict[str, str]],
        phone_value: Any,
        email_value: Any,
    ) -> List[Dict[str, str]]:
        return seah_channels.build_seah_contact_channel_buttons(
            buttons, phone_value, email_value, self.helpers
        )

    def parse_project_pick_uuid(self, slot_value: Any) -> Optional[str]:
        return seah_project.parse_project_pick_uuid(slot_value)

    def _project_button_title(self, row: Dict[str, Any], language_code: str) -> str:
        return seah_project.project_button_title(row, language_code)

    def build_seah_project_identification_buttons(
        self, tracker: Tracker, *, max_projects: int = 12
    ) -> List[Dict[str, str]]:
        return seah_project.build_seah_project_identification_buttons(
            tracker, self.db_manager, max_projects=max_projects
        )

    def validate_seah_project_identification_value(
        self, slot_value: Any, *, language_code: Optional[str] = None
    ) -> Dict[str, Any]:
        return seah_project.validate_seah_project_identification_value(
            slot_value,
            self.db_manager,
            skip_value=self.SKIP_VALUE,
            language_code=language_code or self.language_code,
        )

    def find_seah_contact_point(self, tracker: Tracker) -> Optional[Dict[str, Any]]:
        return seah_contact_points.find_seah_contact_point(
            tracker, self.db_manager, action_name=self.name()
        )

    def format_seah_contact_point_block(
        self, row: Dict[str, Any], language_code: str
    ) -> str:
        return seah_contact_points.format_seah_contact_point_block(row, language_code)

    def _slot_nonempty(self, value: Any) -> bool:
        return seah_party.slot_nonempty(value, default_values=self.DEFAULT_VALUES)

    def compute_seah_contact_provided(self, slots: Dict[Text, Any]) -> bool:
        return seah_channels.compute_seah_contact_provided(slots, self.helpers)

    def seah_contact_provided_update(
        self,
        story_main: Any,
        current_slots: Dict[str, Any],
        updates: Dict[str, Any],
    ) -> Dict[str, bool]:
        return seah_channels.seah_contact_provided_update(
            story_main, current_slots, updates, self.helpers
        )

    def resolve_seah_outro_variant(self, slots: Dict[Text, Any]) -> Text:
        return seah_outro.resolve_seah_outro_variant(slots, self.helpers)

    def _normalize_party_role(self, role: Any) -> str:
        return seah_party.normalize_party_role(role)

    def derive_active_party_role(self, slots: Dict[Text, Any]) -> str:
        return seah_party.derive_active_party_role(slots)

    def build_party_payload_from_slots(self, slots: Dict[Text, Any]) -> Dict[str, Any]:
        return seah_party.build_party_payload_from_slots(
            slots, default_values=self.DEFAULT_VALUES
        )

    def upsert_active_party_payload(
        self,
        current_slots: Dict[str, Any],
        updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        return seah_party.upsert_active_party_payload(
            current_slots, updates, default_values=self.DEFAULT_VALUES
        )


class ActionHelpersMixin(LanguageHelpersMixin, SensitiveContentHelpersMixin):
    def get_utterance(self, utterance_index: int = 1):
        return get_utterance_base(
            self.file_name, self.name(), utterance_index, self.language_code
        )

    def get_buttons(self, button_index: int = 1):
        return get_buttons_base(
            self.file_name, self.name(), button_index, self.language_code
        )

    def check_form_function_name(self, form_name: str, function_name: str) -> bool:
        try:
            UTTERANCE_MAPPING[form_name][function_name]
            return True
        except Exception as exc:
            self.logger.error(
                "check_form_function_name: %s | form=%s function=%s",
                exc,
                form_name,
                function_name,
            )
            return False

    def validate_full_name_to_list(self, full_name: str) -> list:
        return full_name_lookup.validate_full_name_to_list(
            full_name, self.db_manager, self.helpers
        )


class ActionFlowHelpersMixin(ActionHelpersMixin):
    def reset_slots(self, tracker: Tracker, flow: str, output: str = "dict"):
        return slot_reset.reset_slots(tracker, flow, output=output)

    def get_follow_up_phone_issue(
        self, tracker: Tracker
    ) -> Optional[Literal["no_phone", "not_verified"]]:
        return follow_up.get_follow_up_phone_issue(
            tracker, self.helpers, skip_value=self.SKIP_VALUE
        )

    def prepare_grievance_text_for_display(
        self, grievance: Dict, display_only_short: bool = True
    ) -> str:
        return status_display.prepare_grievance_text_for_display(
            grievance,
            language_code=self.language_code,
            display_only_short=display_only_short,
        )

    def collect_grievance_data_from_id(
        self, grievance_id: str, tracker: Tracker, domain: Dict[Text, Any]
    ) -> Dict[Text, Any]:
        return grievance_lookup.collect_grievance_data_from_id(
            grievance_id, tracker, self.db_manager
        )

    def validate_grievance_id_format(self, text: Any) -> bool:
        return grievance_lookup.validate_grievance_id_format(text)

    def standardize_grievance_id_response(self, text: Any) -> str:
        return grievance_lookup.standardize_grievance_id_response(text)

    def fetch_grievance_id_from_slot(self, text: Any) -> str:
        return grievance_lookup.fetch_grievance_id_from_db(text, self.db_manager)

    def select_grievances_from_full_name_list(
        self,
        full_name_matches: List[Tuple[str, float, int]],
        list_grievances_by_phone: list,
        dispatcher: CollectingDispatcher,
    ) -> List[str]:
        return name_matching.select_grievances_from_full_name_list(
            full_name_matches, list_grievances_by_phone, dispatcher
        )

    def match_similar_full_names_in_list(self, list_full_names: list) -> list:
        return name_matching.match_similar_full_names_in_list(
            list_full_names, self.helpers
        )

    def convert_grievance_datetime_to_string(
        self, list_grievances: List[Dict[Text, Any]]
    ) -> List[Dict[Text, Any]]:
        return name_matching.convert_grievance_datetime_to_string(list_grievances)

    def extract_unique_full_names_from_list(
        self, list_grievances: List[Dict[Text, Any]]
    ) -> List[str]:
        return name_matching.extract_unique_full_names_from_list(
            list_grievances, not_provided=self.DEFAULT_VALUES["NOT_PROVIDED"]
        )

    def get_next_action_for_form(self, tracker: Tracker) -> str:
        return routing.get_next_action_for_form(tracker, skip_value=self.SKIP_VALUE)

    def _retrieve_and_set_grievances_by_phone(
        self, tracker: Tracker, phone: Optional[Text] = None
    ) -> Dict[Text, Any]:
        return phone_retrieval.retrieve_grievances_by_phone(
            tracker,
            self.db_manager,
            phone=phone,
            skip_value=self.SKIP_VALUE,
            not_provided=self.DEFAULT_VALUES["NOT_PROVIDED"],
            action_name=self.name(),
        )

    def get_complainant_slot_events_from_grievance(
        self, grievance_id: Optional[Text]
    ) -> List[SlotSet]:
        return complainant_hydrate.get_complainant_slot_events_from_grievance(
            grievance_id, self.db_manager, self.helpers
        )


class ActionMessagingHelpersMixin(ActionHelpersMixin):
    def prepare_recap_email(
        self,
        to_emails: List[str],
        email_data: Dict[str, Any],
        body_name: str,
    ) -> Tuple[str, str]:
        return messaging_recap.prepare_recap_email(
            email_data,
            body_name,
            language_code=self.language_code,
            not_provided=self.NOT_PROVIDED,
        )

    async def send_recap_email(
        self,
        to_emails: List[str],
        grievance_data: Dict[str, Any],
        body_name: str,
    ) -> None:
        await messaging_recap.send_recap_email(
            to_emails,
            grievance_data,
            body_name,
            language_code=self.language_code,
            not_provided=self.NOT_PROVIDED,
        )

    async def send_recap_email_to_admin(
        self,
        grievance_data: Dict[str, Any],
        body_name: str,
        dispatcher: CollectingDispatcher,
    ) -> None:
        await messaging_recap.send_recap_email_to_admin(
            grievance_data,
            body_name,
            language_code=self.language_code,
            not_provided=self.NOT_PROVIDED,
        )

    async def send_recap_email_to_complainant(
        self,
        complainant_email: str,
        body_name: str,
        grievance_data: Dict[str, Any],
        dispatcher: CollectingDispatcher,
    ) -> None:
        await messaging_recap.send_recap_email_to_complainant(
            complainant_email,
            body_name,
            grievance_data,
            dispatcher,
            language_code=self.language_code,
            not_provided=self.NOT_PROVIDED,
            get_utterance=self.get_utterance,
        )

    def send_sms(self, sms_data: Dict[str, Any], body_name: str) -> None:
        messaging_sms.send_sms_from_template(
            sms_data, body_name, language_code=self.language_code
        )

    def _get_attached_files_info(self, grievance_id: str) -> Dict[str, Any]:
        return messaging_grievance_data.get_attached_files_info(
            grievance_id, self.db_manager
        )

    def collect_grievance_data_from_tracker(
        self, tracker: Tracker = None
    ) -> Dict[str, Any]:
        return messaging_grievance_data.collect_grievance_data_from_tracker(tracker)
