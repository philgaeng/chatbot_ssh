"""SMTP env resolution."""
import pytest

from backend.config.smtp_config import missing_smtp_env_fields, resolve_smtp_config


@pytest.fixture(autouse=True)
def _clear_smtp_env(monkeypatch):
    for key in (
        "SMTP_SERVER",
        "SMTP_PORT",
        "SMTP_USERNAME",
        "SMTP_PASSWORD",
        "SMTP_FROM",
        "SMTP_FROM_DISPLAY",
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
