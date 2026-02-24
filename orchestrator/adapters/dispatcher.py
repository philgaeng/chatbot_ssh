"""
CollectingDispatcher - adapter matching Rasa's CollectingDispatcher surface
so existing Rasa actions can run without Rasa's runtime.

Messages are appended to self.messages for retrieval after action execution.
"""

from typing import Any, Dict, List, Optional


class CollectingDispatcher:
    """
    Collects messages from action utter_message() calls.
    Matches the interface used by rasa_chatbot actions.
    """

    def __init__(self) -> None:
        self.messages: List[Dict[str, Any]] = []

    def utter_message(
        self,
        text: Optional[str] = None,
        buttons: Optional[List[Dict[str, str]]] = None,
        json_message: Optional[Dict[str, Any]] = None,
        response: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Append a message to self.messages.
        Supports: text, buttons, json_message (e.g. grievance_id_set), response (utter template).
        For the spike, response templates are not resolved; pass-through or skip.
        """
        msg: Dict[str, Any] = {}
        if text is not None:
            msg["text"] = text
        if buttons is not None:
            msg["buttons"] = buttons
        if json_message is not None:
            msg["json_message"] = json_message
        if response is not None:
            # response is an utter template name; for spike we store as response key
            # optionally resolve from domain - for now just store
            msg["response"] = response
            if kwargs:
                msg["response_kwargs"] = kwargs
        elif kwargs:
            msg["custom"] = kwargs
        self.messages.append(msg)
