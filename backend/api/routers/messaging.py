from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, ValidationError, constr

from backend.services.messaging import Messaging
from backend.logger.logger import TaskLogger


router = APIRouter()


class MessageContext(BaseModel):
    source_system: Optional[str] = Field(
        default=None,
        description="Originating system, e.g. chatbot, ticketing, gsheet",
    )
    purpose: Optional[str] = Field(
        default=None,
        description="High-level purpose, e.g. escalation_notification, otp, digest",
    )
    grievance_id: Optional[str] = None
    ticket_id: Optional[str] = None
    office_user: Optional[str] = None
    channel: Optional[str] = None
    client_message_id: Optional[str] = Field(
        default=None,
        description="Optional idempotency key from caller",
    )
    # Allow arbitrary extra keys for forward compatibility
    extra: Optional[Dict[str, Any]] = None


class SendSmsRequest(BaseModel):
    to: constr(strip_whitespace=True, min_length=1)  # type: ignore[valid-type]
    text: constr(strip_whitespace=True, min_length=1)  # type: ignore[valid-type]
    context: Optional[MessageContext] = None


class SendEmailRequest(BaseModel):
    to: List[EmailStr]
    subject: constr(strip_whitespace=True, min_length=1)  # type: ignore[valid-type]
    html_body: constr(strip_whitespace=True, min_length=1)  # type: ignore[valid-type]
    context: Optional[MessageContext] = None


class MessagingResponse(BaseModel):
    status: str
    message: Optional[str] = None
    message_id: Optional[str] = None
    error_code: Optional[str] = None
    error: Optional[str] = None


def get_messaging() -> Messaging:
    return Messaging()


def _get_logger():
    task_logger = TaskLogger(service_name="messaging_api")
    return task_logger.logger


def _auth_check(x_api_key: Optional[str] = Header(default=None)) -> None:
    # Minimal placeholder for now; wire to real auth later.
    expected = None  # e.g. os.getenv("MESSAGING_API_KEY")
    if expected and x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"status": "FAILED", "error_code": "UNAUTHORIZED", "error": "Invalid API key"},
        )


@router.post(
    "/api/messaging/send-sms",
    response_model=MessagingResponse,
    status_code=status.HTTP_200_OK,
)
def send_sms(
    payload: SendSmsRequest,
    _auth: None = Depends(_auth_check),
    messaging: Messaging = Depends(get_messaging),
):
    logger = _get_logger()
    try:
        logger.info(
            "Messaging API send-sms request",
            extra={
                "to": payload.to,
                "context": payload.context.dict() if payload.context else None,
            },
        )
        ok = messaging.send_sms(payload.to, payload.text)
        if not ok:
            return MessagingResponse(
                status="FAILED",
                error_code="DELIVERY_ERROR",
                error="SMS delivery failed or disabled",
            )
        # SNS MessageId is logged inside Messaging; we do not have it here yet.
        return MessagingResponse(status="SUCCESS", message="SMS sent")
    except HTTPException:
        raise
    except ValidationError as ve:
        # Should not normally happen here (Pydantic already validated), but keep for completeness.
        logger.exception("Validation error in send-sms: %s", ve)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "FAILED",
                "error_code": "VALIDATION_ERROR",
                "error": str(ve),
            },
        )
    except Exception as exc:
        logger.exception("Unexpected error in send-sms: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "FAILED",
                "error_code": "INTERNAL_ERROR",
                "error": str(exc),
            },
        )


@router.post(
    "/api/messaging/send-email",
    response_model=MessagingResponse,
    status_code=status.HTTP_200_OK,
)
def send_email(
    payload: SendEmailRequest,
    _auth: None = Depends(_auth_check),
    messaging: Messaging = Depends(get_messaging),
):
    logger = _get_logger()
    try:
        if not payload.to:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "FAILED",
                    "error_code": "VALIDATION_ERROR",
                    "error": "Field 'to' must contain at least one email address",
                },
            )

        logger.info(
            "Messaging API send-email request",
            extra={
                "to": payload.to,
                "context": payload.context.dict() if payload.context else None,
            },
        )
        ok = messaging.send_email(payload.to, payload.subject, payload.html_body)
        if not ok:
            return MessagingResponse(
                status="FAILED",
                error_code="DELIVERY_ERROR",
                error="Email delivery failed",
            )
        return MessagingResponse(status="SUCCESS", message="Email sent")
    except HTTPException:
        raise
    except ValidationError as ve:
        logger.exception("Validation error in send-email: %s", ve)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "FAILED",
                "error_code": "VALIDATION_ERROR",
                "error": str(ve),
            },
        )
    except Exception as exc:
        logger.exception("Unexpected error in send-email: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "FAILED",
                "error_code": "INTERNAL_ERROR",
                "error": str(exc),
            },
        )

