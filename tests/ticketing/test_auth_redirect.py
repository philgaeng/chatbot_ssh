"""Password reset redirect allowlist."""
from __future__ import annotations

import pytest

from ticketing.services.auth_login import AuthLoginError, _validate_redirect_base


@pytest.mark.parametrize(
    "url",
    [
        "https://grm-chatbot.dor.gov.np",
        "https://grm-auth.nepal-gms-chatbot.facets-ai.com",
        "https://grm.stage.facets-ai.com",
        "http://localhost:3002",
    ],
)
def test_validate_redirect_base_allows_known_hosts(url: str) -> None:
    assert _validate_redirect_base(url) == url.rstrip("/")


def test_validate_redirect_base_rejects_unknown_host() -> None:
    with pytest.raises(AuthLoginError) as exc:
        _validate_redirect_base("https://evil.example.com")
    assert exc.value.code == "invalid_redirect"
