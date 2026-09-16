# SPDX-License-Identifier: Apache-2.0

"""SMS env resolution and Nepal phone normalization.

⚠ **There is one SMS transport: the DOIT government gateway, in Nepal.** The AWS SNS fallback was
removed on 2026-08-24 — SMS providers serving Nepal must be in Nepal, and that path could only format
Philippine numbers, so it could never reach a Nepali complainant. These tests pin the removal: the
resolver must **fail closed to `disabled`**, never to a cross-border transport.
"""
import pytest

from backend.config.sms_config import (
    SmsProvider,
    normalize_nepal_mobile,
    resolve_sms_config,
)


@pytest.fixture(autouse=True)
def _clear_sms_env(monkeypatch):
    for key in (
        "SMS_PROVIDER",
        "SMS_ENABLED",
        "SMS_WHITELIST_ONLY",
        "DOIT_SMS_BEARER_TOKEN",
        "DOIT_SMS_BASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)


def test_resolve_doit_when_token_set(monkeypatch):
    monkeypatch.setenv("DOIT_SMS_BEARER_TOKEN", "test-token")
    monkeypatch.setenv("SMS_ENABLED", "true")

    cfg = resolve_sms_config()
    assert cfg.provider == "doit"
    assert cfg.enabled is True
    assert cfg.bearer_token == "test-token"
    assert cfg.base_url == "https://sms.doit.gov.np"
    assert cfg.whitelist_only is False


def test_resolves_to_disabled_without_a_doit_token():
    """⚠ Was `aws_sns` — a missing token used to route SMS abroad silently. It must fail closed."""
    cfg = resolve_sms_config()
    assert cfg.provider == "disabled"
    assert cfg.whitelist_only is False


def test_doit_without_a_token_degrades_to_disabled(monkeypatch):
    monkeypatch.setenv("SMS_PROVIDER", "doit")
    assert resolve_sms_config().provider == "disabled"


def test_no_cross_border_provider_can_be_selected(monkeypatch):
    """The removal is the point: naming the old provider must not resurrect it."""
    monkeypatch.setenv("SMS_PROVIDER", "aws_sns")
    assert resolve_sms_config().provider == "disabled"

    monkeypatch.setenv("DOIT_SMS_BEARER_TOKEN", "test-token")
    assert resolve_sms_config().provider == "doit"

    assert set(SmsProvider.__args__) == {"doit", "disabled"}


def test_whitelist_is_opt_in_only(monkeypatch):
    monkeypatch.setenv("DOIT_SMS_BEARER_TOKEN", "test-token")
    assert resolve_sms_config().whitelist_only is False

    monkeypatch.setenv("SMS_WHITELIST_ONLY", "true")
    assert resolve_sms_config().whitelist_only is True


def test_normalize_nepal_mobile_variants():
    assert normalize_nepal_mobile("9841234567") == "9841234567"
    assert normalize_nepal_mobile("+9779841234567") == "9841234567"
    assert normalize_nepal_mobile("9779841234567") == "9841234567"
    assert normalize_nepal_mobile("09841234567") == "9841234567"


def test_normalize_nepal_mobile_rejects_a_non_nepali_number():
    with pytest.raises(ValueError):
        normalize_nepal_mobile("+12025550143")


def test_a_non_nepali_whitelist_entry_is_skipped_not_raised(monkeypatch):
    """⚠ Regression pin. `SMS_WHITELIST_ONLY=true` used to raise ValueError out of `send_sms`.

    The list held Philippine numbers from the SNS demo path while the DOIT path normalised them as
    Nepali, and the comprehension sat outside the surrounding try. A malformed entry must not be
    able to take down the send path.
    """
    from backend.services import messaging

    monkeypatch.setattr(
        messaging, "WHITELIST_PHONE_NUMBERS_OTP_TESTING", ["+12025550143", "9841234567"]
    )
    assert messaging._normalized_whitelist() == {"9841234567"}
