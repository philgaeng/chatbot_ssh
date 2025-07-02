from base_classes import BaseAction
from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict
from rasa_sdk.events import SlotSet
from actions_server.constants import TASK_STATUS

TASK_SLOTS_TO_UPDATE_MAP = {
    "process_file_upload_task": "file_upload_status",
    "classify_and_summarize_grievance_task": "classification_status",
    "translate_grievance_to_english_task": "translation_status",
   }

IN_PROGRESS = TASK_STATUS["IN_PROGRESS"]
SUCCESS = TASK_STATUS["SUCCESS"]
FAILED = TASK_STATUS["FAILED"]
ERROR = TASK_STATUS["ERROR"]
RETRY = TASK_STATUS["RETRY"]

class ActionEmitStatusUpdate(BaseAction):
    def name(self) -> Text:
        return "action_emit_status_update"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        if tracker.get_slot("data_to_emit") is None:
            raise Exception("No data to emit")
            pass
        data = tracker.get_slot("data_to_emit")
        task_name = data.get("task_name")
        task_status = data.get("status")
        if task_status in [SUCCESS, FAILED]: #Only emit status update for success or failure to not clutter websocket
            dispatcher.utter_message(json_message=data)
            if task_name in TASK_SLOTS_TO_UPDATE_MAP:
                slot_name = TASK_SLOTS_TO_UPDATE_MAP[task_name]
                slots_to_set = {slot_name: task_status}
                return [SlotSet(slot_name, task_status), SlotSet("data_to_emit", None)]
            return [SlotSet("data_to_emit", None)]
        else:
            return []