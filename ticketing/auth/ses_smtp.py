"""
AWS SES SMTP credentials derived from IAM access keys.

Keycloak realm email uses SMTP. The Messaging API uses boto3 SES with the same
IAM user — AWS documents that SMTP username = access key ID and SMTP password
is an HMAC-derived form of the secret key (no separate SMTP password in env).

See: https://docs.aws.amazon.com/ses/latest/dg/smtp-credentials.html
"""
from __future__ import annotations

import base64
import hashlib
import hmac


def derive_ses_smtp_password(secret_access_key: str) -> str:
    """Derive SES SMTP password from AWS_SECRET_ACCESS_KEY."""
    signature = hmac.new(
        secret_access_key.encode("utf-8"),
        "SendRawEmail".encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    return base64.b64encode(bytes([0x04]) + signature).decode("utf-8")
