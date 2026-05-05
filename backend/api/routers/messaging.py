from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, ValidationError, constr

from backend.api.deps.messaging_auth import MessagingApiCaller, messaging_api_guard
from backend.logger.logger import TaskLogger
from backend.services.messaging import Messaging
from backend.services.notification_routing_runtime import resolve_effective_route


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
    #: ISO 3166-1 alpha-2 (e.g. NP). Required for ticketing.notification_routes resolution.
    country_code: Optional[str] = None
    #: ticketing.projects.project_id — optional override row in notification_routes.
    project_id: Optional[str] = None
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


def _context_dict(ctx: Optional[MessageContext]) -> Optional[Dict[str, Any]]:
    if ctx is None:
        return None
    return ctx.model_dump(exclude_none=True)


@router.post(
    "/api/messaging/send-sms",
    response_model=MessagingResponse,
    status_code=status.HTTP_200_OK,
)
def send_sms(
    payload: SendSmsRequest,
    caller: MessagingApiCaller = Depends(messaging_api_guard),
    messaging: Messaging = Depends(get_messaging),
):
    logger = _get_logger()
    try:
        ctx_dict = _context_dict(payload.context)
        route = resolve_effective_route("sms", ctx_dict)
        logger.info(
            "Messaging API send-sms request client_source=%s routing=%s",
            caller.source,
            route.provider_key if route else "env_default",
            extra={
                "to": payload.to,
                "client_source": caller.source,
                "context": ctx_dict,
            },
        )
        ok = messaging.send_sms(
            payload.to,
            payload.text,
            provider_key=route.provider_key if route else None,
        )
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
    caller: MessagingApiCaller = Depends(messaging_api_guard),
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

        ctx_dict = _context_dict(payload.context)
        route = resolve_effective_route("email", ctx_dict)
        logger.info(
            "Messaging API send-email request client_source=%s routing=%s",
            caller.source,
            route.provider_key if route else "env_default",
            extra={
                "to": payload.to,
                "client_source": caller.source,
                "context": ctx_dict,
            },
        )
        ok = messaging.send_email(
            payload.to,
            payload.subject,
            payload.html_body,
            provider_key=route.provider_key if route else None,
        )
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

