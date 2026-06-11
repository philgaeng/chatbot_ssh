"""SMS env resolution and Nepal phone normalization."""
import pytest

from backend.config.sms_config import (
    format_philippines_e164,
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


def test_resolve_aws_sns_without_doit_token(monkeypatch):
    cfg = resolve_sms_config()
    assert cfg.provider == "aws_sns"
    assert cfg.whitelist_only is True


def test_normalize_nepal_mobile_variants():
    assert normalize_nepal_mobile("9841234567") == "9841234567"
    assert normalize_nepal_mobile("+9779841234567") == "9841234567"
    assert normalize_nepal_mobile("9779841234567") == "9841234567"
    assert normalize_nepal_mobile("09841234567") == "9841234567"


def test_normalize_nepal_mobile_invalid():
    with pytest.raises(ValueError):
        normalize_nepal_mobile("+639175330841")


def test_format_philippines_e164():
    assert format_philippines_e164("09175330841") == "+639175330841"
    assert format_philippines_e164("+639175330841") == "+639175330841"
