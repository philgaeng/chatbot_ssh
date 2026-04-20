"""
SQLAlchemy declarative base and engine/session factory for the ticketing schema.
All models must use __table_args__ = {"schema": "ticketing"}.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from ticketing.config.settings import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine():
    settings = get_settings()
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )


engine = _make_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency — yields a DB session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_ticketing_schema() -> None:
    """Create the ticketing schema if it does not exist. Call once at startup."""
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS ticketing"))
