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
    ticketing_secret_key: str = ""

    # ── Integration URLs ──
    backend_grievance_base_url: str = "http://localhost:5001"
    orchestrator_base_url: str = "http://localhost:8000"
    messaging_api_key: str = ""
    # User-facing webchat URL — embedded in QR codes so complainants reach the chatbot.
    # Override via CHATBOT_WEBCHAT_URL env var in production.
    chatbot_webchat_url: str = "https://grm.facets-ai.com/chat"

    # ── Keycloak (replaces AWS Cognito for self-hosted deployments) ──
    # Leave keycloak_issuer empty to keep the dev bypass (returns mock-super-admin).
    keycloak_issuer: str = ""           # e.g. http://keycloak:8080/realms/grm
    keycloak_client_id: str = "ticketing-api"   # confidential client for JWT audience check
    keycloak_admin_url: str = ""        # e.g. http://keycloak:8080 (no trailing slash)
    keycloak_admin_password: str = ""   # KEYCLOAK_ADMIN_PASSWORD

    # ── LLM (OpenAI — same key used by chatbot backend) ──
    openai_api_key: str = ""

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
