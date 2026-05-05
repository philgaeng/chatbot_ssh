import os
from typing import List, Optional

from backend.logger.logger import TaskLogger
from backend.services.messaging_providers import (
    EmailProvider,
    SMSProvider,
    build_email_provider,
    build_email_provider_named,
    build_sms_provider,
    build_sms_provider_named,
    format_phone_number_ph,
)


def _use_remote_messaging() -> bool:
    return os.getenv("MESSAGING_USE_REMOTE_API", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def get_action_messaging():
    """
    Entry point for Rasa actions, Celery, and other chatbot-side code.

    - Default: in-process Messaging singleton (same host as backend API).
    - Split deploy: MESSAGING_USE_REMOTE_API=true and MESSAGING_REMOTE_BASE_URL / keys —
      uses HTTP to the messaging API on another server.
    """
    if _use_remote_messaging():
        from backend.services.messaging_remote import RemoteMessagingAPI

        return RemoteMessagingAPI()
    return Messaging()


class Messaging:
    """
    Facade for SMS and email used by Rasa actions and in-process API handlers.

    Providers are selected via MESSAGING_SMS_PROVIDER / MESSAGING_EMAIL_PROVIDER
    (see backend.services.messaging_providers).
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        sms_provider: Optional[SMSProvider] = None,
        email_provider: Optional[EmailProvider] = None,
    ) -> None:
        if Messaging._initialized:
            return
        try:
            self._sms: SMSProvider = sms_provider or build_sms_provider()
            self._email: EmailProvider = email_provider or build_email_provider()
            self.task_logger = TaskLogger(service_name="messaging_service")
            self.logger = self.task_logger.logger
            self.log_event = self.task_logger.log_event
            self.logger.info("Messaging facade initialized")
            Messaging._initialized = True
        except Exception as e:
            try:
                self.logger.error("Failed to initialize Messaging: %s", str(e))
            except Exception:
                pass
            raise

    def send_sms(
        self,
        phone_number: str,
        message: str,
        *,
        provider_key: str | None = None,
    ) -> bool:
        """If ``provider_key`` is set (from ticketing.notification_routes), use that adapter for this send only."""
        try:
            impl = (
                build_sms_provider_named(provider_key)
                if provider_key
                else self._sms
            )
            return impl.send_sms(phone_number, message)
        except Exception as e:
            self.logger.error("Failed to send SMS: %s", e)
            return False

    def send_email(
        self,
        to_emails: List[str],
        subject: str,
        body: str,
        *,
        provider_key: str | None = None,
    ) -> bool:
        try:
            impl = (
                build_email_provider_named(provider_key)
                if provider_key
                else self._email
            )
            return impl.send_email(to_emails, subject, body)
        except Exception as e:
            self.logger.error("Failed to send email: %s", e)
            return False

    def test_sms_connection(self, test_phone_number: str) -> bool:
        try:
            return self._sms.test_connection(test_phone_number)
        except Exception as e:
            self.logger.error("Failed to test SMS connection: %s", e)
            return False

    def format_phone_number(self, phone_number: str) -> str:
        try:
            return format_phone_number_ph(phone_number)
        except Exception as e:
            self.logger.error("Failed to format phone number: %s", e)
            raise


# Celery / legacy imports — always in-process singleton on the API host
messaging = Messaging()
