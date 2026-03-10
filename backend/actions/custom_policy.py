from rasa.core.policies.rule_policy import RulePolicy
from rasa.engine.recipes.default_recipe import DefaultV1Recipe
from rasa.shared.core.trackers import DialogueStateTracker
from rasa.shared.core.domain import Domain
from rasa.shared.core.events import SlotSet, UserUttered, ActionExecuted
from rasa.engine.storage.resource import Resource
from rasa.engine.storage.storage import ModelStorage
from rasa.engine.graph import ExecutionContext
import numpy as np

@DefaultV1Recipe.register("PreviousStatePolicy", is_trainable=False)
class PreviousStatePolicy(RulePolicy):
    def __init__(
        self,
        config: dict,
        model_storage: ModelStorage,
        resource: Resource,
        execution_context: ExecutionContext,
        **kwargs,
    ):
        super().__init__(config, model_storage, resource, execution_context, **kwargs)

    def predict_action_probabilities(
        self,
        tracker: DialogueStateTracker,
        domain: Domain,
    ) -> np.ndarray:
        # Call the parent RulePolicy to get the action probabilities
        probabilities = super().predict_action_probabilities(tracker, domain)

        # Automatically set the `previous_state` slot
        if tracker.latest_action_name:
            tracker.update(SlotSet("previous_state", tracker.latest_action_name))

        # Automatically set the `current_process` slot based on the latest intent
        latest_intent = tracker.latest_message.intent.get("name")
        if latest_intent:
            tracker.update(SlotSet("current_process", self.get_process_name(latest_intent)))

        # Automatically set the `story_current` slot
        if tracker.active_loop_name:
            tracker.update(SlotSet("story_current", tracker.active_loop_name))
        else:
            tracker.update(SlotSet("story_current", self.get_story_name(tracker)))

        return probabilities

    def get_process_name(self, intent: str) -> str:
        # Map intents to process names
        process_mapping = {
            "submit_grievance": "grievance",
            "provide_contact_info": "contact info",
            "restart_story": "current process",
            "greet": "greeting",
            "mood_unhappy": "issue resolution",
        }
        return process_mapping.get(intent, "general flow")

    def get_story_name(self, tracker: DialogueStateTracker) -> str:
        # Derive the story name based on the events in the tracker
        for event in reversed(tracker.events):
            if isinstance(event, UserUttered):
                return "user interaction"
            elif isinstance(event, ActionExecuted):
                return event.action_name  # Access the action's name
        return "unknown story"
