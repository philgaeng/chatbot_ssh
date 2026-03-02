"""
Action registry: invoke Rasa actions with adapters and parse events to slot updates.
"""

import asyncio
import os
import sys
from typing import Any, Dict, List

# Ensure project root and rasa_chatbot are on path
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
_RASA_DIR = os.path.join(_REPO_ROOT, "rasa_chatbot")
if _RASA_DIR not in sys.path:
    sys.path.insert(0, _RASA_DIR)

from orchestrator.adapters import CollectingDispatcher, SessionTracker

# Action class mapping (lazy import to avoid circular deps and heavy startup)
_ACTIONS: Dict[str, Any] = {}


def _get_action(action_name: str) -> Any:
    """Lazy-load action instances."""
    if not _ACTIONS:
        from rasa_chatbot.actions.generic_actions import (
            ActionIntroduce,
            ActionNextAction,
            ActionSetEnglish,
            ActionSetNepali,
            ActionMainMenu,
        )
        from rasa_chatbot.actions.forms.form_grievance import (
            ActionStartGrievanceProcess,
            ActionAskGrievanceNewDetail,
        )
        from rasa_chatbot.actions.forms.form_status_check import (
            ActionStartStatusCheck,
            ActionAskStatusCheckMethod,
            ActionAskFormStatusCheck1ComplainantPhone,
            ActionAskStatusCheckRetrieveGrievances,
            ActionAskStatusCheckListGrievanceId,
            ActionAskStatusCheckComplainantFullName,
            ActionStatusCheckRequestFollowUp,
            ActionStatusCheckModifyGrievance,
            ActionStatusCheckRetrieveComplainantData,
            ActionSkipStatusCheckOutro,
            ActionAskStatusCheckGrievanceIdSelected,
        )
        from rasa_chatbot.actions.forms.form_otp import (
            ActionAskOtpConsent,
            ActionAskOtpInput,
        )
        from rasa_chatbot.actions.forms.form_status_check_skip import (
            ActionAskValidProvinceAndDistrict,
        )
        from rasa_chatbot.actions.forms.form_grievance_complainant_review import (
            ActionRetrieveClassificationResults,
            ActionAskFormGrievanceComplainantReviewGrievanceClassificationConsent,
            ActionAskFormGrievanceComplainantReviewGrievanceCategoriesStatus,
            ActionAskFormGrievanceComplainantReviewGrievanceCatModify,
            ActionAskFormGrievanceComplainantReviewGrievanceSummaryStatus,
            ActionAskFormGrievanceComplainantReviewGrievanceSummaryTemp,
            ActionUpdateGrievanceCategorization,
        )
        from rasa_chatbot.actions.action_submit_grievance import (
            ActionSubmitGrievance,
            ActionGrievanceOutro,
        )
        from rasa_chatbot.actions.action_ask_commons import (
            ActionAskComplainantLocationConsent,
            ActionAskComplainantProvince,
            ActionAskComplainantDistrict,
            ActionAskComplainantMunicipalityTemp,
            ActionAskComplainantMunicipalityConfirmed,
            ActionAskComplainantVillageTemp,
            ActionAskComplainantVillageConfirmed,
            ActionAskComplainantWard,
            ActionAskComplainantAddressTemp,
            ActionAskComplainantAddressConfirmed,
            ActionAskComplainantConsent,
            ActionAskComplainantFullName,
            ActionAskComplainantEmailTemp,
            ActionAskComplainantEmailConfirmed,
            ActionAskComplainantPhone,
        )
        # Intro/menu
        _ACTIONS["action_introduce"] = ActionIntroduce()
        _ACTIONS["action_next_action"] = ActionNextAction()
        _ACTIONS["action_set_english"] = ActionSetEnglish()
        _ACTIONS["action_set_nepali"] = ActionSetNepali()
        _ACTIONS["action_main_menu"] = ActionMainMenu()

        # Grievance
        _ACTIONS["action_start_grievance_process"] = ActionStartGrievanceProcess()
        _ACTIONS["action_ask_grievance_new_detail"] = ActionAskGrievanceNewDetail()
        _ACTIONS["action_submit_grievance"] = ActionSubmitGrievance()

        # Status check
        _ACTIONS["action_start_status_check"] = ActionStartStatusCheck()
        _ACTIONS["action_ask_status_check_method"] = ActionAskStatusCheckMethod()
        _ACTIONS["action_ask_status_check_retrieve_grievances"] = ActionAskStatusCheckRetrieveGrievances()
        _ACTIONS["action_ask_status_check_list_grievance_id"] = ActionAskStatusCheckListGrievanceId()
        _ACTIONS["action_ask_status_check_complainant_full_name"] = ActionAskStatusCheckComplainantFullName()
        _ACTIONS["action_status_check_request_follow_up"] = ActionStatusCheckRequestFollowUp()
        _ACTIONS["action_status_check_modify_grievance"] = ActionStatusCheckModifyGrievance()
        _ACTIONS["action_status_check_retrieve_complainant_data"] = ActionStatusCheckRetrieveComplainantData()
        _ACTIONS["action_skip_status_check_outro"] = ActionSkipStatusCheckOutro()
        _ACTIONS["action_ask_status_check_grievance_id_selected"] = ActionAskStatusCheckGrievanceIdSelected()

        # Contact
        _ACTIONS["action_ask_complainant_location_consent"] = ActionAskComplainantLocationConsent()
        _ACTIONS["action_ask_complainant_province"] = ActionAskComplainantProvince()
        _ACTIONS["action_ask_complainant_district"] = ActionAskComplainantDistrict()
        _ACTIONS["action_ask_complainant_municipality_temp"] = ActionAskComplainantMunicipalityTemp()
        _ACTIONS["action_ask_complainant_municipality_confirmed"] = ActionAskComplainantMunicipalityConfirmed()
        _ACTIONS["action_ask_complainant_village_temp"] = ActionAskComplainantVillageTemp()
        _ACTIONS["action_ask_complainant_village_confirmed"] = ActionAskComplainantVillageConfirmed()
        _ACTIONS["action_ask_complainant_ward"] = ActionAskComplainantWard()
        _ACTIONS["action_ask_complainant_address_temp"] = ActionAskComplainantAddressTemp()
        _ACTIONS["action_ask_complainant_address_confirmed"] = ActionAskComplainantAddressConfirmed()
        _ACTIONS["action_ask_complainant_consent"] = ActionAskComplainantConsent()
        _ACTIONS["action_ask_complainant_full_name"] = ActionAskComplainantFullName()
        _ACTIONS["action_ask_complainant_email_temp"] = ActionAskComplainantEmailTemp()
        _ACTIONS["action_ask_complainant_email_confirmed"] = ActionAskComplainantEmailConfirmed()
        _ACTIONS["action_ask_complainant_phone"] = ActionAskComplainantPhone()
        _ACTIONS["action_ask_form_status_check_1_complainant_phone"] = ActionAskFormStatusCheck1ComplainantPhone()

        # OTP
        _ACTIONS["action_ask_otp_consent"] = ActionAskOtpConsent()
        _ACTIONS["action_ask_otp_input"] = ActionAskOtpInput()

        # Status check skip (valid_province_and_district; complainant_* use shared contact actions)
        _ACTIONS["action_ask_form_status_check_skip_valid_province_and_district"] = ActionAskValidProvinceAndDistrict()
        _ACTIONS["action_ask_form_status_check_skip_complainant_district"] = ActionAskComplainantDistrict()
        _ACTIONS["action_ask_form_status_check_skip_complainant_municipality_temp"] = ActionAskComplainantMunicipalityTemp()
        _ACTIONS["action_ask_form_status_check_skip_complainant_municipality_confirmed"] = ActionAskComplainantMunicipalityConfirmed()

        # Grievance review (retrieve classification from DB before showing review)
        _ACTIONS["action_retrieve_classification_results"] = ActionRetrieveClassificationResults()
        _ACTIONS["action_ask_form_grievance_complainant_review_grievance_classification_consent"] = ActionAskFormGrievanceComplainantReviewGrievanceClassificationConsent()
        _ACTIONS["action_ask_form_grievance_complainant_review_grievance_categories_status"] = ActionAskFormGrievanceComplainantReviewGrievanceCategoriesStatus()
        _ACTIONS["action_ask_form_grievance_complainant_review_grievance_cat_modify"] = ActionAskFormGrievanceComplainantReviewGrievanceCatModify()
        _ACTIONS["action_ask_form_grievance_complainant_review_grievance_summary_status"] = ActionAskFormGrievanceComplainantReviewGrievanceSummaryStatus()
        _ACTIONS["action_ask_form_grievance_complainant_review_grievance_summary_temp"] = ActionAskFormGrievanceComplainantReviewGrievanceSummaryTemp()
        _ACTIONS["action_update_grievance_categorization"] = ActionUpdateGrievanceCategorization()
        _ACTIONS["action_grievance_outro"] = ActionGrievanceOutro()
    return _ACTIONS.get(action_name)


def events_to_slot_updates(events: List[Any]) -> Dict[str, Any]:
    """Extract SlotSet events to {slot_name: value}."""
    result: Dict[str, Any] = {}
    for e in events or []:
        if hasattr(e, "as_dict"):
            d = e.as_dict()
        elif isinstance(e, dict):
            d = e
        else:
            continue
        if d.get("event") == "slot":
            result[d["name"]] = d.get("value")
    return result


async def invoke_action(
    action_name: str,
    dispatcher: CollectingDispatcher,
    tracker: SessionTracker,
    domain: Dict[str, Any],
) -> List[Any]:
    """
    Invoke action by name. Returns list of events (SlotSet, etc.).
    dispatcher.messages contains any utterances.
    """
    action = _get_action(action_name)
    if not action:
        raise ValueError(f"Unknown action: {action_name}")
    return await action.run(dispatcher, tracker, domain)
