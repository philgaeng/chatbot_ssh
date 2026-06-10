"""
Ticketing service configuration via pydantic-settings.
All values loaded from env.local / .env — no hardcoded credentials.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class TicketingSettings(BaseSettings):
    # ── Database (reuse existing chatbot env vars — same Postgres instance) ──
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "grievance_db"
    postgres_user: str = "nepal_grievance_admin"
    postgres_password: str = ""

    # ── Redis / Celery (reuse existing env vars) ──
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # ── Ticketing service ──
    ticketing_port: int = 5002
    # Canonical shared secret: chatbot ↔ ticketing + ticketing → chatbot backend.
    ticketing_secret_key: str = ""

    # ── Integration URLs ──
    backend_grievance_base_url: str = "http://localhost:5001"
    orchestrator_base_url: str = "http://localhost:8000"
    # Optional legacy alias; prefer TICKETING_SECRET_KEY everywhere.
    messaging_api_key: str = ""
    # Same key as chatbot backend — used only to decrypt vault fields for reveal broker.
    db_encryption_key: str = ""
    # User-facing webchat URL — embedded in QR codes so complainants reach the chatbot.
    # Override via CHATBOT_WEBCHAT_URL env var in production.
    chatbot_webchat_url: str = "https://grm.facets-ai.com/chat"
    # Public base for complainant closure page (no trailing slash)
    ticketing_public_base_url: str = "https://nepal-gms-chatbot.facets-ai.com"

    # ── Keycloak (replaces AWS Cognito for self-hosted deployments) ──
    # Leave keycloak_issuer empty to keep the dev bypass (returns mock-super-admin).
    keycloak_issuer: str = ""           # browser-facing URL — must match tokens' `iss` claim, e.g. http://localhost:18080/realms/grm
    # Optional JWKS URL override. When set, JWT verification fetches keys from this
    # URL instead of `{keycloak_issuer}/protocol/openid-connect/certs`. Use this when
    # the browser-facing issuer is unreachable from the backend container (e.g. local
    # dev with KC on a host port) — point this at the Docker-internal Keycloak URL.
    keycloak_jwks_url: str = ""         # e.g. http://keycloak:8080/realms/grm/protocol/openid-connect/certs
    # Server-side token endpoint base (Docker-internal). When empty, derived from
    # keycloak_jwks_url or keycloak_admin_url — not from keycloak_issuer (browser URL).
    keycloak_token_issuer: str = ""
    keycloak_client_id: str = "ticketing-api"   # confidential client for JWT audience check
    keycloak_client_secret: str = ""    # optional; fetched from Keycloak admin if empty
    keycloak_admin_url: str = ""        # e.g. http://keycloak:8080 (no trailing slash)
    keycloak_admin_password: str = ""   # KEYCLOAK_ADMIN_PASSWORD
    # Shared secret for POST /api/v1/webhooks/keycloak (Keycloak HTTP event listener)
    keycloak_webhook_secret: str = ""
    # Officer invite email: after required actions, redirect to GRM login (needs client_id).
    # Realm SMTP uses shared SMTP_* env — see backend/config/smtp_config.py + keycloak_setup.
    keycloak_invite_client_id: str = "ticketing-ui"
    keycloak_invite_redirect_uri: str = "http://localhost:3002/login"

    # ── LLM (OpenAI — same key used by chatbot backend) ──
    openai_api_key: str = ""

    # ── Archiving (docs/ARCHIVING_AND_RETENTION.md §7) ──
    archiving_dry_run: bool = False

    model_config = SettingsConfigDict(
        env_file=("env.local", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        """SQLAlchemy connection URL — built from POSTGRES_* env vars."""
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> TicketingSettings:
    """Return cached settings instance. Call get_settings() everywhere."""
    return TicketingSettings()
