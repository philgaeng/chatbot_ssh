"""
GRM Ticketing System — FastAPI application entrypoint.
Port: TICKETING_PORT (default 5002)

Run:
  conda activate chatbot-rest
  uvicorn ticketing.api.main:app --host 0.0.0.0 --port 5002 --reload

Or via module:
  python -m ticketing.api.main
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ticketing.api.routers import tickets, workflows, users
from ticketing.api.routers import settings as settings_router
from ticketing.api.routers import reports
from ticketing.api.routers import locations as locations_router
from ticketing.config.settings import get_settings
from ticketing.models.base import ensure_ticketing_schema

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure the ticketing schema exists (idempotent)
    ensure_ticketing_schema()
    logger.info("GRM Ticketing Service started on port %s", get_settings().ticketing_port)
    yield
    logger.info("GRM Ticketing Service shutting down")


app = FastAPI(
    title="GRM Ticketing API",
    description=(
        "Grievance Redress Mechanism Ticketing System\n"
        "ADB Nepal KL Road Project (Loan 52097-003)\n\n"
        "**Inbound** (chatbot → ticketing): `POST /api/v1/tickets` requires `x-api-key` header.\n"
        "**Officer UI** endpoints: proto uses mock auth; production requires Cognito JWT."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# INTEGRATION POINT: restrict allow_origins to ticketing-ui domain in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(tickets.router,          prefix="/api/v1", tags=["Tickets"])
app.include_router(workflows.router,        prefix="/api/v1", tags=["Workflows"])
app.include_router(users.router,            prefix="/api/v1", tags=["Users & Roles"])
app.include_router(settings_router.router,  prefix="/api/v1", tags=["Settings"])
app.include_router(reports.router,          prefix="/api/v1", tags=["Reports"])
app.include_router(locations_router.router, prefix="/api/v1", tags=["Locations & Projects"])


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
def health():
    """Basic liveness check."""
    return {"status": "ok", "service": "grm-ticketing", "version": "1.0.0"}


# ── Dev entrypoint ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "ticketing.api.main:app",
        host="0.0.0.0",
        port=settings.ticketing_port,
        reload=True,
        log_level="info",
    )
