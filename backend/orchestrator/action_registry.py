"""
Action registry: invoke Rasa actions with adapters and parse events to slot updates.
"""

import asyncio
import os
import sys
from typing import Any, Dict, List

# Ensure project root is on path (backend is at repo root)
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.orchestrator.adapters import CollectingDispatcher, SessionTracker

# Action class mapping (lazy import to avoid circular deps and heavy startup)
_ACTIONS: Dict[str, Any] = {}


def _get_action(action_name: str) -> Any:
    """Lazy-load action instances."""
    if not _ACTIONS:
        from backend.actions.generic_actions import (
            ActionIntroduce,
            ActionNextAction,
            ActionSetEnglish,
            ActionSetNepali,
            ActionMainMenu,
        )
        from backend.actions.forms.form_grievance import (
            ActionStartGrievanceProcess,
            ActionAskGrievanceNewDetail,
        )
        from backend.actions.forms.form_seah_1 import (
            ActionAskFormSeah1SensitiveIssuesFollowUp,
            ActionAskFormSeah1SeahVictimSurvivorRole,
        )
        from backend.actions.forms.form_seah_2 import (
            ActionAskFormSeah2SeahProjectIdentification,
            ActionAskFormSeah2SensitiveIssuesNewDetail,
            ActionAskFormSeah2SeahContactConsentChannel,
        )
        from backend.actions.forms.form_seah_focal_point import (
            ActionAskFormSeahFocalPointSeahProjectIdentification,
            ActionAskFormSeahFocalPointSeahFocalFullName,
            ActionAskFormSeahFocalPointSeahFocalOtpInput,
            ActionAskFormSeahFocalPointSeahFocalSurvivorRisks,
            ActionAskFormSeahFocalPointSeahFocalMitigationMeasures,
            ActionAskFormSeahFocalPointSeahFocalOtherAtRiskParties,
            ActionAskFormSeahFocalPointSeahFocalProjectRisk,
            ActionAskFormSeahFocalPointSeahFocalReputationalRisk,
            ActionAskFormSeahFocalPointSeahFocalLearnedWhen,
            ActionAskFormSeahFocalPointSensitiveIssuesNewDetail,
            ActionAskFormSeahFocalPointSeahContactConsentChannel,
            ActionOutroSensitiveIssues,
        )
        from backend.actions.forms.form_modify_grievance import (
            ActionAskModifyFollowUpAnswer,
            ActionAskModifyGrievanceNewDetail,
        )
        from backend.actions.forms.form_modify_contact import (
            ActionAskFormModifyContactComplainantPhone,
            ActionAskModifyMissingField,
        )
        from backend.actions.forms.form_status_check import (
            ActionStartStatusCheck,
            ActionAskStatusCheckMethod,
            ActionAskFormStatusCheck1ComplainantPhone,
            ActionAskStatusCheckRetrieveGrievances,
            ActionAskStatusCheckListGrievanceId,
            ActionAskStatusCheckComplainantFullName,
            ActionStatusCheckRequestFollowUp,
            ActionStatusCheckModifyGrievance,
            ActionSkipStatusCheckOutro,
            ActionAskStatusCheckGrievanceIdSelected,
        )
        from backend.actions.forms.form_otp import (
            ActionAskOtpConsent,
            ActionAskOtpInput,
        )
        from backend.actions.forms.form_status_check_skip import (
            ActionAskValidProvinceAndDistrict,
        )
        from backend.actions.forms.form_grievance_complainant_review import (
            ActionRetrieveClassificationResults,
            ActionAskFormGrievanceComplainantReviewGrievanceClassificationConsent,
            ActionAskFormGrievanceComplainantReviewGrievanceCategoriesStatus,
            ActionAskFormGrievanceComplainantReviewGrievanceCatModify,
            ActionAskFormGrievanceComplainantReviewGrievanceSummaryStatus,
            ActionAskFormGrievanceComplainantReviewGrievanceSummaryTemp,
            ActionUpdateGrievanceCategorization,
        )
        from backend.actions.action_submit_grievance import (
            ActionSubmitGrievance,
            ActionSubmitSeah,
            ActionGrievanceOutro,
        )
        from backend.actions.action_ask_commons import (
            ActionAskStoryStep,
            ActionAskStoryRoute,
            ActionAskLanguageCode,
            ActionAskStoryMain,
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
        _ACTIONS["action_submit_seah"] = ActionSubmitSeah()

        # SEAH forms
        _ACTIONS["action_ask_form_seah_1_sensitive_issues_follow_up"] = ActionAskFormSeah1SensitiveIssuesFollowUp()
        _ACTIONS["action_ask_form_seah_1_seah_victim_survivor_role"] = ActionAskFormSeah1SeahVictimSurvivorRole()
        _ACTIONS["action_ask_form_seah_2_seah_project_identification"] = ActionAskFormSeah2SeahProjectIdentification()
        _ACTIONS["action_ask_form_seah_2_sensitive_issues_new_detail"] = ActionAskFormSeah2SensitiveIssuesNewDetail()
        _ACTIONS["action_ask_form_seah_2_seah_contact_consent_channel"] = ActionAskFormSeah2SeahContactConsentChannel()
        _ACTIONS["action_ask_form_seah_focal_point_seah_project_identification"] = ActionAskFormSeahFocalPointSeahProjectIdentification()
        _ACTIONS["action_ask_form_seah_focal_point_seah_focal_full_name"] = ActionAskFormSeahFocalPointSeahFocalFullName()
        _ACTIONS["action_ask_form_seah_focal_point_seah_focal_otp_input"] = ActionAskFormSeahFocalPointSeahFocalOtpInput()
        _ACTIONS["action_ask_form_seah_focal_point_seah_focal_survivor_risks"] = ActionAskFormSeahFocalPointSeahFocalSurvivorRisks()
        _ACTIONS["action_ask_form_seah_focal_point_seah_focal_mitigation_measures"] = ActionAskFormSeahFocalPointSeahFocalMitigationMeasures()
        _ACTIONS["action_ask_form_seah_focal_point_seah_focal_other_at_risk_parties"] = ActionAskFormSeahFocalPointSeahFocalOtherAtRiskParties()
        _ACTIONS["action_ask_form_seah_focal_point_seah_focal_project_risk"] = ActionAskFormSeahFocalPointSeahFocalProjectRisk()
        _ACTIONS["action_ask_form_seah_focal_point_seah_focal_reputational_risk"] = ActionAskFormSeahFocalPointSeahFocalReputationalRisk()
        _ACTIONS["action_ask_form_seah_focal_point_seah_focal_learned_when"] = ActionAskFormSeahFocalPointSeahFocalLearnedWhen()
        _ACTIONS["action_ask_form_seah_focal_point_sensitive_issues_new_detail"] = ActionAskFormSeahFocalPointSensitiveIssuesNewDetail()
        _ACTIONS["action_ask_form_seah_focal_point_seah_contact_consent_channel"] = ActionAskFormSeahFocalPointSeahContactConsentChannel()
        _ACTIONS["action_outro_sensitive_issues"] = ActionOutroSensitiveIssues()

        # Status check
        _ACTIONS["action_start_status_check"] = ActionStartStatusCheck()
        _ACTIONS["action_ask_status_check_method"] = ActionAskStatusCheckMethod()
        _ACTIONS["action_ask_status_check_retrieve_grievances"] = ActionAskStatusCheckRetrieveGrievances()
        _ACTIONS["action_ask_status_check_list_grievance_id"] = ActionAskStatusCheckListGrievanceId()
        _ACTIONS["action_ask_status_check_complainant_full_name"] = ActionAskStatusCheckComplainantFullName()
        _ACTIONS["action_status_check_request_follow_up"] = ActionStatusCheckRequestFollowUp()
        _ACTIONS["action_status_check_modify_grievance"] = ActionStatusCheckModifyGrievance()
        _ACTIONS["action_ask_modify_follow_up_answer"] = ActionAskModifyFollowUpAnswer()
        _ACTIONS["action_ask_modify_grievance_new_detail"] = ActionAskModifyGrievanceNewDetail()
        _ACTIONS["action_ask_form_modify_contact_complainant_phone"] = ActionAskFormModifyContactComplainantPhone()
        _ACTIONS["action_ask_modify_missing_field"] = ActionAskModifyMissingField()
        _ACTIONS["action_skip_status_check_outro"] = ActionSkipStatusCheckOutro()
        _ACTIONS["action_ask_status_check_grievance_id_selected"] = ActionAskStatusCheckGrievanceIdSelected()

        # Flow/story common actions (status-check menus and language selection)
        _ACTIONS["action_ask_story_step"] = ActionAskStoryStep()
        _ACTIONS["action_ask_story_route"] = ActionAskStoryRoute()
        _ACTIONS["action_ask_language_code"] = ActionAskLanguageCode()
        _ACTIONS["action_ask_story_main"] = ActionAskStoryMain()

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
