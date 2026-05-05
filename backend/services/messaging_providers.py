"""
Pluggable SMS / email providers for the messaging service.

Configure with env (defaults keep current AWS SNS + SES behaviour):
  MESSAGING_SMS_PROVIDER=sns|noop
  MESSAGING_EMAIL_PROVIDER=ses|noop

Additional providers (e.g. Twilio, SendGrid) can be added as new classes
and wired in build_sms_provider / build_email_provider.
"""

from __future__ import annotations

import logging
import os
import re
from typing import List, Protocol, runtime_checkable

import boto3
from botocore.exceptions import ClientError

from backend.config.constants import (
    AWS_REGION,
    SMS_ENABLED,
    WHITELIST_PHONE_NUMBERS_OTP_TESTING,
)
from backend.services.db_debug_log import email_send_log_summary, mask_phone_for_log, text_len_for_log

logger = logging.getLogger(__name__)


def format_phone_number_ph(phone_number: str) -> str:
    """Format Philippines mobile numbers to E.164 (+63…)."""
    cleaned_number = re.sub(r"[^\d+]", "", phone_number)

    if re.match(r"^\+63\d{10}$", cleaned_number):
        return cleaned_number

    if cleaned_number.startswith("09"):
        formatted_number = "+63" + cleaned_number[1:]
    elif cleaned_number.startswith("63"):
        formatted_number = "+" + cleaned_number
    elif cleaned_number.startswith("0063"):
        formatted_number = "+" + cleaned_number[2:]
    else:
        raise ValueError(f"Invalid phone number format: {phone_number}")

    if not re.match(r"^\+63\d{10}$", formatted_number):
        raise ValueError(
            f"Invalid phone number format - final: {phone_number}, {formatted_number}"
        )

    return formatted_number


@runtime_checkable
class SMSProvider(Protocol):
    def send_sms(self, phone_number: str, message: str) -> bool: ...
    def test_connection(self, test_phone_number: str) -> bool: ...


@runtime_checkable
class EmailProvider(Protocol):
    def send_email(self, to_emails: List[str], subject: str, body: str) -> bool: ...


class NoopSmsProvider:
    """SMS disabled / local dev — logs only, returns True."""

    def send_sms(self, phone_number: str, message: str) -> bool:
        logger.info(
            "[noop-sms] skip send to=%s chars=%s",
            mask_phone_for_log(phone_number),
            len(message or ""),
        )
        return True

    def test_connection(self, test_phone_number: str) -> bool:
        logger.info("[noop-sms] test_connection to=%s", mask_phone_for_log(test_phone_number))
        return True


class NoopEmailProvider:
    def send_email(self, to_emails: List[str], subject: str, body: str) -> bool:
        logger.info(
            "[noop-email] skip send %s subject_chars=%s",
            email_send_log_summary(to_emails),
            len(subject or ""),
        )
        return True


class SnsSmsProvider:
    def __init__(self) -> None:
        self._sns = boto3.client("sns", region_name=AWS_REGION)
        logger.info("SNS SMS provider initialized (region=%s)", AWS_REGION)

    def send_sms(self, phone_number: str, message: str) -> bool:
        try:
            if not SMS_ENABLED:
                logger.warning("SMS_ENABLED is False; SMS not sent.")
                return False

            formatted_number = format_phone_number_ph(phone_number)
            if formatted_number not in WHITELIST_PHONE_NUMBERS_OTP_TESTING:
                logger.warning(
                    "Phone number %s not in whitelist. SMS not sent.",
                    mask_phone_for_log(formatted_number),
                )
                return False

            logger.info(
                "Sending SMS via SNS to whitelisted number: %s",
                mask_phone_for_log(formatted_number),
            )

            response = self._sns.publish(
                PhoneNumber=formatted_number,
                Message=message,
                MessageAttributes={
                    "AWS.SNS.SMS.SMSType": {
                        "DataType": "String",
                        "StringValue": "Transactional",
                    }
                },
            )
            logger.info("SNS SMS sent successfully: %s", response["MessageId"])
            return True
        except ClientError as e:
            logger.error("Failed to send SMS via SNS: %s", e)
            return False
        except Exception as e:
            logger.error("Failed to send SMS: %s", e)
            return False

    def test_connection(self, test_phone_number: str) -> bool:
        test_message = "This is a test message from your chatbot."
        try:
            result = self.send_sms(test_phone_number, test_message)
            logger.info(
                "Test SMS to %s result=%s",
                mask_phone_for_log(test_phone_number),
                result,
            )
            return result
        except Exception as e:
            logger.error(
                "Test SMS to %s failed: %s",
                mask_phone_for_log(test_phone_number),
                e,
            )
            return False


class SesEmailProvider:
    def __init__(self) -> None:
        self._ses = boto3.client(
            "ses",
            region_name=AWS_REGION,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        )
        self._sender = os.getenv("SES_VERIFIED_EMAIL")
        if not self._sender:
            raise ValueError("SES_VERIFIED_EMAIL not set in environment")
        logger.info("SES email provider initialized (region=%s)", AWS_REGION)

    def send_email(self, to_emails: List[str], subject: str, body: str) -> bool:
        try:
            logger.info(
                "Attempting SES send: %s subject_chars=%s %s",
                email_send_log_summary(to_emails),
                len(subject or ""),
                text_len_for_log("body", body),
            )
            self._ses.send_email(
                Source=self._sender,
                Destination={"ToAddresses": to_emails},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {"Html": {"Data": body, "Charset": "UTF-8"}},
                },
            )
            logger.info("SES email sent to %s", email_send_log_summary(to_emails))
            return True
        except Exception as e:
            logger.error("SES send failed: %s", e)
            return False


def build_sms_provider_named(provider_key: str | None) -> SMSProvider:
    """
    Build SMS provider from an explicit key (from ticketing.notification_routes).
    ``None`` or empty → fall back to env ``MESSAGING_SMS_PROVIDER``.
    """
    if provider_key is None or not str(provider_key).strip():
        return build_sms_provider()
    name = str(provider_key).strip().lower()
    if name == "noop":
        return NoopSmsProvider()
    if name == "sns":
        return SnsSmsProvider()
    logger.warning("Unknown routing SMS provider_key=%r; using noop", provider_key)
    return NoopSmsProvider()


def build_email_provider_named(provider_key: str | None) -> EmailProvider:
    """Explicit email provider key, or env ``MESSAGING_EMAIL_PROVIDER`` when None."""
    if provider_key is None or not str(provider_key).strip():
        return build_email_provider()
    name = str(provider_key).strip().lower()
    if name == "noop":
        return NoopEmailProvider()
    if name == "ses":
        return SesEmailProvider()
    logger.warning("Unknown routing email provider_key=%r; using noop", provider_key)
    return NoopEmailProvider()


def build_sms_provider() -> SMSProvider:
    name = os.getenv("MESSAGING_SMS_PROVIDER", "sns").strip().lower()
    if name == "noop":
        return NoopSmsProvider()
    if name == "sns":
        return SnsSmsProvider()
    logger.warning("Unknown MESSAGING_SMS_PROVIDER=%r; using noop", name)
    return NoopSmsProvider()


def build_email_provider() -> EmailProvider:
    name = os.getenv("MESSAGING_EMAIL_PROVIDER", "ses").strip().lower()
    if name == "noop":
        return NoopEmailProvider()
    if name == "ses":
        return SesEmailProvider()
    logger.warning("Unknown MESSAGING_EMAIL_PROVIDER=%r; using noop", name)
    return NoopEmailProvider()
