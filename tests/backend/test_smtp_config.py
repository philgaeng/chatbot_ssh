"""SMTP env resolution."""
import pytest

from backend.config.smtp_config import (
    missing_smtp_env_fields,
    resolve_smtp_config,
    resolve_smtp_delivery_configs,
    resolve_temp_smtp_config,
)


@pytest.fixture(autouse=True)
def _clear_smtp_env(monkeypatch):
    for key in (
        "SMTP_SERVER",
        "SMTP_PORT",
        "SMTP_USERNAME",
        "SMTP_PASSWORD",
        "SMTP_FROM",
        "SMTP_FROM_DISPLAY",
        "TEMP_SMTP_SERVER",
        "TEMP_SMTP_PORT",
        "TEMP_SMTP_USERNAME",
        "TEMP_SMTP_PASSWORD",
        "TEMP_SMTP_FROM",
        "TEMP_SMTP_FROM_DISPLAY",
    ):
        monkeypatch.delenv(key, raising=False)


def test_resolve_from_smtp_vars(monkeypatch):
    monkeypatch.setenv("SMTP_SERVER", "mail.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USERNAME", "user@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")
    monkeypatch.setenv("SMTP_FROM_DISPLAY", "GRM")

    cfg = resolve_smtp_config()
    assert cfg is not None
    assert cfg.host == "mail.example.com"
    assert cfg.port == 587
    assert cfg.username == "user@example.com"
    assert cfg.password == "secret"
    assert cfg.from_addr == "noreply@example.com"
    assert cfg.from_display == "GRM"


def test_from_addr_falls_back_to_username(monkeypatch):
    monkeypatch.setenv("SMTP_SERVER", "mail.example.com")
    monkeypatch.setenv("SMTP_USERNAME", "user@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")

    cfg = resolve_smtp_config()
    assert cfg is not None
    assert cfg.from_addr == "user@example.com"


def test_missing_smtp_env_fields(monkeypatch):
    assert "SMTP_SERVER" in missing_smtp_env_fields()
    monkeypatch.setenv("SMTP_SERVER", "mail.example.com")
    assert "SMTP_SERVER" not in missing_smtp_env_fields()


def test_resolve_temp_smtp_config(monkeypatch):
    monkeypatch.setenv("TEMP_SMTP_SERVER", "mail.temp.example")
    monkeypatch.setenv("TEMP_SMTP_PORT", "587")
    monkeypatch.setenv("TEMP_SMTP_USERNAME", "temp@example.com")
    monkeypatch.setenv("TEMP_SMTP_PASSWORD", "secret")
    monkeypatch.setenv("TEMP_SMTP_FROM", "temp@example.com")

    cfg = resolve_temp_smtp_config()
    assert cfg is not None
    assert cfg.host == "mail.temp.example"
    assert cfg.from_addr == "temp@example.com"


def test_delivery_configs_primary_then_fallback(monkeypatch):
    monkeypatch.setenv("SMTP_SERVER", "mail.official.example")
    monkeypatch.setenv("SMTP_USERNAME", "official@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("TEMP_SMTP_SERVER", "mail.temp.example")
    monkeypatch.setenv("TEMP_SMTP_USERNAME", "temp@example.com")
    monkeypatch.setenv("TEMP_SMTP_PASSWORD", "secret")

    profiles = resolve_smtp_delivery_configs()
    assert [label for label, _ in profiles] == ["primary", "fallback"]
    assert profiles[0][1].host == "mail.official.example"
    assert profiles[1][1].host == "mail.temp.example"


def test_delivery_configs_fallback_only(monkeypatch):
    monkeypatch.setenv("TEMP_SMTP_SERVER", "mail.temp.example")
    monkeypatch.setenv("TEMP_SMTP_USERNAME", "temp@example.com")
    monkeypatch.setenv("TEMP_SMTP_PASSWORD", "secret")

    profiles = resolve_smtp_delivery_configs()
    assert len(profiles) == 1
    assert profiles[0][0] == "fallback"
