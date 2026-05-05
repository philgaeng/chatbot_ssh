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
    #: Base URL for ``POST /api/messaging/*`` (notify or backend). Env: ``MESSAGING_REMOTE_BASE_URL``. If empty, uses ``backend_grievance_base_url``.
    messaging_remote_base_url: str = ""

    # ── AWS Cognito (GRM pool — separate from Stratcon) ──
    cognito_grm_user_pool_id: str = ""
    cognito_grm_client_id: str = ""
    cognito_grm_region: str = "ap-southeast-1"

    # ── LLM (OpenAI — same key used by chatbot backend) ──
    openai_api_key: str = ""

    model_config = SettingsConfigDict(
        env_file=("env.local", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def messaging_api_base_url(self) -> str:
        """Host for messaging HTTP API (same spec as chatbot ``MESSAGING_REMOTE_BASE_URL``)."""
        u = (self.messaging_remote_base_url or "").strip()
        if u:
            return u.rstrip("/")
        return str(self.backend_grievance_base_url).rstrip("/")

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
