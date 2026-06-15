import base64
import smtplib
from contextlib import contextmanager
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

import boto3
import requests
from botocore.exceptions import ClientError
from typing import Any, Text, Dict, List, Optional, Protocol
from backend.config.constants import (
    WHITELIST_PHONE_NUMBERS_OTP_TESTING,
    AWS_REGION,
)
from backend.config.sms_config import (
    SmsConfig,
    format_philippines_e164,
    normalize_nepal_mobile,
    resolve_sms_config,
    sms_config_summary,
)
from backend.config.smtp_config import (
    SmtpConfig,
    SmtpProfileLabel,
    resolve_smtp_delivery_configs,
    smtp_delivery_summary,
)
from backend.logger.logger import TaskLogger
from backend.services.db_debug_log import email_send_log_summary, mask_phone_for_log, text_len_for_log
import os


class Messaging:
    """
    Main messaging class that provides functions called by Rasa Actions.
    Uses separate service classes for SMS and Email functionality.
    Implements singleton pattern to prevent multiple initializations.
    """
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not Messaging._initialized:
            try:
                self.sms_config = resolve_sms_config()
                self.sms_client = _build_sms_client(self.sms_config)
                self.email_client = EmailClient()
                self.task_logger = TaskLogger(service_name='messaging_service')
                self.logger = self.task_logger.logger
                self.log_event = self.task_logger.log_event
                self.logger.info(
                    "Successfully initialized Messaging repository (%s)",
                    sms_config_summary(),
                )
                Messaging._initialized = True
            except Exception as e:
                # Create a basic logger for error reporting if the main one failed
                try:
                    self.logger.error(f"Failed to initialize Messaging repository: {str(e)}")
                except:
                    pass  # If even the error logger fails, just raise the original exception
                raise

    def send_sms(self, phone_number: str, message: str) -> bool:
        """
        Send SMS to the given phone number.
        Args:
            phone_number: Phone number to send SMS to
            message: Message to send
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            return self.sms_client.send_sms(phone_number, message)
        except Exception as e:
            self.logger.error(f"Failed to send SMS: {str(e)}")
            return False

    def send_email(
        self,
        to_emails: List[str],
        subject: str,
        body: str,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        """
        Send email to the given email addresses.
        Args:
            to_emails: List of email addresses to send to
            subject: Email subject
            body: Email body (HTML)
            attachments: Optional list of dicts with filename, content_base64, content_type
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            return self.email_client.send_email(to_emails, subject, body, attachments=attachments)
        except Exception as e:
            self.logger.error(f"Failed to send email: {str(e)}")
            return False

    def test_sms_connection(self, test_phone_number: str) -> bool:
        """
        Test SMS sending functionality.
        Args:
            test_phone_number: Phone number to send test SMS to
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            return self.sms_client.test_connection(test_phone_number)
        except Exception as e:
            self.logger.error(f"Failed to test SMS connection: {str(e)}")
            return False

    def format_phone_number(self, phone_number: str) -> str:
        """
        Format phone number for the active SMS provider.
        """
        try:
            return self.sms_client.format_phone_number(phone_number)
        except Exception as e:
            self.logger.error(f"Failed to format phone number: {str(e)}")
            raise


class SmsTransport(Protocol):
    def send_sms(self, phone_number: str, message: str) -> bool: ...

    def test_connection(self, test_phone_number: str) -> bool: ...

    def format_phone_number(self, phone_number: str) -> str: ...


def _build_sms_client(config: SmsConfig) -> SmsTransport:
    if config.provider == "doit":
        return DoitSmsClient(config)
    if config.provider == "aws_sns":
        return SnsSmsClient(config)
    return DisabledSmsClient()


class DisabledSmsClient:
    def __init__(self) -> None:
        self.task_logger = TaskLogger(service_name="messaging_service")
        self.logger = self.task_logger.logger

    def send_sms(self, phone_number: str, message: str) -> bool:
        self.logger.info("SMS disabled — message not sent to %s", mask_phone_for_log(phone_number))
        return False

    def test_connection(self, test_phone_number: str) -> bool:
        return False

    def format_phone_number(self, phone_number: str) -> str:
        return normalize_nepal_mobile(phone_number)


class DoitSmsClient:
    """Nepal DOIT government SMS gateway (sms.doit.gov.np)."""

    def __init__(self, config: SmsConfig) -> None:
        self.config = config
        self.task_logger = TaskLogger(service_name="messaging_service")
        self.logger = self.task_logger.logger
        self.log_event = self.task_logger.log_event
        self.logger.info("DOIT SMS client initialized (base_url=%s)", config.base_url)
        self._log_balance_on_startup()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.bearer_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _log_balance_on_startup(self) -> None:
        try:
            balance = self.get_balance()
            if "balance" in balance:
                self.logger.info(
                    "DOIT SMS account balance=%s ntc_rate=%s ncell_rate=%s",
                    balance.get("balance"),
                    balance.get("ntc_rate"),
                    balance.get("ncell_rate"),
                )
            else:
                self.logger.warning("DOIT SMS balance check returned: %s", balance)
        except Exception as exc:
            self.logger.warning("DOIT SMS balance check failed: %s", exc)

    def get_balance(self) -> dict[str, Any]:
        response = requests.get(
            f"{self.config.base_url}/api/balance",
            headers=self._headers(),
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {"raw": payload}

    def test_connection(self, test_phone_number: str) -> bool:
        try:
            return self.send_sms(test_phone_number, "DOIT SMS connectivity test from GRM chatbot.")
        except Exception as e:
            self.logger.error(
                "DOIT test SMS to %s failed: %s",
                mask_phone_for_log(test_phone_number),
                e,
            )
            return False

    def send_sms(self, phone_number: str, message: str) -> bool:
        if not self.config.enabled:
            self.logger.info("SMS_ENABLED is false — DOIT message not sent")
            return False

        try:
            mobile = normalize_nepal_mobile(phone_number)
        except ValueError as exc:
            self.logger.error("DOIT SMS invalid number %s: %s", mask_phone_for_log(phone_number), exc)
            return False

        if self.config.whitelist_only and mobile not in {
            normalize_nepal_mobile(p) for p in WHITELIST_PHONE_NUMBERS_OTP_TESTING
        }:
            self.logger.warning(
                "Phone number %s not in whitelist. DOIT SMS not sent.",
                mask_phone_for_log(mobile),
            )
            return False

        try:
            self.logger.info("Sending SMS via DOIT to %s", mask_phone_for_log(mobile))
            response = requests.post(
                f"{self.config.base_url}/api/sms",
                headers=self._headers(),
                json={"message": message, "mobile": mobile},
                timeout=30,
            )
            payload = response.json() if response.content else {}
            if response.ok and isinstance(payload, dict):
                msg = str(payload.get("message", "")).lower()
                if "sent successfully" in msg or "queued" in msg:
                    self.logger.info("DOIT SMS accepted for %s", mask_phone_for_log(mobile))
                    return True
            error_detail = payload if isinstance(payload, dict) else response.text
            self.logger.error(
                "DOIT SMS failed status=%s detail=%s",
                response.status_code,
                error_detail,
            )
            return False
        except requests.RequestException as exc:
            self.logger.error("DOIT SMS request failed: %s", exc)
            return False

    def format_phone_number(self, phone_number: str) -> str:
        return normalize_nepal_mobile(phone_number)


class SnsSmsClient:
    """AWS SNS — dev / international fallback."""

    def __init__(self, config: SmsConfig) -> None:
        self.config = config
        self.task_logger = TaskLogger(service_name='messaging_service')
        self.logger = self.task_logger.logger
        self.log_event = self.task_logger.log_event
        try:
            self.sns_client = boto3.client('sns', region_name=AWS_REGION)
            self.logger.info("Successfully initialized SNS client")
        except ClientError as e:
            self.logger.error(f"Failed to initialize SNS client: {str(e)}")
            raise

    def test_connection(self, test_phone_number: str) -> bool:
        """
        Test SMS sending functionality with a test message.
        Args:
            test_phone_number: Phone number to send test SMS to
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            test_message = "This is a test message from your chatbot."
            result = self.send_sms(test_phone_number, test_message)
            
            self.logger.info(
                "Test SMS sent successfully to %s",
                mask_phone_for_log(test_phone_number),
            )
            return result
        except Exception as e:
            self.logger.error(
                "Test SMS to %s failed with error: %s",
                mask_phone_for_log(test_phone_number),
                str(e),
            )
            return False

    def send_sms(self, phone_number: str, message: str) -> bool:
        try:
            if not self.config.enabled:
                self.logger.info("SMS_ENABLED is false — SNS message not sent")
                return False

            formatted_number = self.format_phone_number(phone_number)
            if self.config.whitelist_only and formatted_number not in WHITELIST_PHONE_NUMBERS_OTP_TESTING:
                self.logger.warning(
                    "Phone number %s not in whitelist. SMS not sent.",
                    mask_phone_for_log(formatted_number),
                )
                return False

            self.logger.info(
                "Sending SMS via SNS to %s",
                mask_phone_for_log(formatted_number),
            )

            response = self.sns_client.publish(
                PhoneNumber=formatted_number,
                Message=message,
                MessageAttributes={
                    'AWS.SNS.SMS.SMSType': {
                        'DataType': 'String',
                        'StringValue': 'Transactional'
                    }
                }
            )
            self.logger.info("SNS SMS sent successfully: %s", response['MessageId'])
            return True
        except (ClientError, ValueError) as e:
            self.logger.error("Failed to send SMS via SNS: %s", e)
            return False

    def format_phone_number(self, phone_number: str) -> str:
        return format_philippines_e164(phone_number)

class EmailClient:
    def __init__(self):
        self.task_logger = TaskLogger(service_name="messaging_service")
        self.logger = self.task_logger.logger
        self.log_event = self.task_logger.log_event
        self.smtp_profiles: list[tuple[SmtpProfileLabel, SmtpConfig]] = []
        # First profile (primary when set) — kept for callers that read .smtp_config
        self.smtp_config: SmtpConfig | None = None

        try:
            self.smtp_profiles = resolve_smtp_delivery_configs()
            if not self.smtp_profiles:
                raise ValueError(
                    "SMTP is not configured. Set SMTP_* and/or TEMP_SMTP_* "
                    "(SERVER, USERNAME, PASSWORD, FROM)."
                )
            self.smtp_config = self.smtp_profiles[0][1]
            self.logger.info("Email transport: SMTP (%s)", smtp_delivery_summary())
        except Exception as e:
            self.logger.error("Failed to initialize email client: %s", e)
            raise

    def name(self) -> Text:
        return "email_client"

    def send_email(
        self,
        to_emails: List[str],
        subject: str,
        body: str,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        self.logger.info(
            "Attempting to send email via SMTP: %s subject_chars=%s %s",
            email_send_log_summary(to_emails),
            len(subject or ""),
            text_len_for_log("body", body),
        )
        for index, (label, cfg) in enumerate(self.smtp_profiles):
            try:
                self._send_via_smtp(
                    to_emails, subject, body, attachments=attachments, cfg=cfg
                )
                if index > 0:
                    self.logger.warning(
                        "Email delivered via %s SMTP (%s:%s)",
                        label,
                        cfg.host,
                        cfg.port,
                    )
                return True
            except Exception as e:
                self.logger.warning(
                    "SMTP %s failed (%s:%s): %s",
                    label,
                    cfg.host,
                    cfg.port,
                    e,
                )
        self.logger.error("Email failure (all SMTP profiles): %s", email_send_log_summary(to_emails))
        self.logger.error("%s", text_len_for_log("subject", subject))
        self.logger.error("%s", text_len_for_log("body", body))
        return False

    @contextmanager
    def _smtp_session(self, cfg: SmtpConfig, timeout: int = 30):
        """Authenticated SMTP session (SMTPS on 465, STARTTLS on other ports)."""
        use_ssl = cfg.port == 465
        smtp_cls = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
        with smtp_cls(cfg.host, cfg.port, timeout=timeout) as smtp:
            smtp.ehlo()
            if not use_ssl:
                smtp.starttls()
                smtp.ehlo()
            smtp.login(cfg.username, cfg.password)
            yield smtp

    def test_connection(
        self,
        *,
        send_to: Optional[List[str]] = None,
        check_only: bool = False,
        timeout: int = 30,
    ) -> bool:
        """
        Verify SMTP reachability and credentials; optionally send a test message.
        Tries primary SMTP_* first, then TEMP_SMTP_* fallback.
        """
        for index, (label, cfg) in enumerate(self.smtp_profiles):
            try:
                with self._smtp_session(cfg, timeout=timeout) as smtp:
                    smtp.noop()
                    if check_only:
                        self.logger.info(
                            "SMTP check-only OK [%s] (%s:%s, transport=%s)",
                            label,
                            cfg.host,
                            cfg.port,
                            "ssl" if cfg.port == 465 else "starttls",
                        )
                        return True
                    if not send_to:
                        raise ValueError("send_to is required when check_only is False")
                    subject = "GRM SMTP test"
                    body = (
                        "<p>This is a test message from the GRM chatbot SMTP checker.</p>"
                        f"<p>Profile: {label}</p>"
                        f"<p>From: {cfg.from_addr}</p>"
                    )
                    msg = MIMEText(body, "html", "utf-8")
                    msg["Subject"] = subject
                    msg["From"] = formataddr((cfg.from_display, cfg.from_addr))
                    msg["To"] = ", ".join(send_to)
                    smtp.sendmail(cfg.from_addr, send_to, msg.as_string())
                self.logger.info(
                    "SMTP test email sent [%s] from %s to %s",
                    label,
                    cfg.from_addr,
                    email_send_log_summary(send_to),
                )
                if index > 0:
                    self.logger.warning(
                        "SMTP test used %s profile (%s:%s)",
                        label,
                        cfg.host,
                        cfg.port,
                    )
                return True
            except Exception as e:
                self.logger.warning(
                    "SMTP test [%s] failed (%s:%s): %s",
                    label,
                    cfg.host,
                    cfg.port,
                    e,
                )
        self.logger.error("SMTP test failed for all configured profiles")
        return False

    def _send_via_smtp(
        self,
        to_emails: List[str],
        subject: str,
        body: str,
        attachments: Optional[List[Dict[str, Any]]] = None,
        *,
        cfg: SmtpConfig,
    ) -> None:
        from_header = formataddr((cfg.from_display, cfg.from_addr))

        if attachments:
            msg: MIMEMultipart | MIMEText = MIMEMultipart()
            msg.attach(MIMEText(body or "", "html", "utf-8"))
            for item in attachments:
                filename = str(item.get("filename") or "attachment")
                raw = base64.b64decode(str(item.get("content_base64") or ""))
                part = MIMEApplication(raw, Name=filename)
                part.add_header("Content-Disposition", "attachment", filename=filename)
                content_type = item.get("content_type")
                if content_type:
                    part.set_type(str(content_type))
                msg.attach(part)
        else:
            msg = MIMEText(body or "", "html", "utf-8")

        msg["Subject"] = subject
        msg["From"] = from_header
        msg["To"] = ", ".join(to_emails)

        with self._smtp_session(cfg, timeout=30) as smtp:
            smtp.sendmail(cfg.from_addr, to_emails, msg.as_string())

        self.logger.info("SMTP email sent from %s", cfg.from_addr)


# Global instance for backward compatibility
messaging = Messaging()