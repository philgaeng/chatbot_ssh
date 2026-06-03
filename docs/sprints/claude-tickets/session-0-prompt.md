# Session 0 — Codebase Analysis Prompt
# Paste this as your first message to Claude Code after opening nepal_chatbot on feature/grm-ticketing

---

Read CLAUDE.md first.

Then do a full read-only analysis of this codebase. Read these files:
1. backend/api/fastapi_app.py
2. backend/api/routers/ (all files)
3. backend/services/database_services/__init__.py and base_manager.py
4. backend/task_queue/celery_app.py
5. backend/orchestrator/main.py
6. docs/ticketing_system/ (all files)
7. requirements.txt
8. docker-compose.yml

Do NOT modify any files. Do NOT create any code yet.

After reading, create ONE file at:
docs/claude-tickets/session-0-codebase-findings.md

This file must contain:

## 1. FastAPI patterns
- Exact router structure, prefix conventions, dependency injection patterns
- How auth/middleware is applied in existing routers
- Response model patterns (Pydantic schemas location and naming)

## 2. Database connection pattern
- SQLAlchemy engine setup and session factory (exact code pattern to copy)
- Connection string env var name(s) used
- Any existing Alembic setup to be aware of

## 3. Celery configuration
- Exact broker URL format (Redis connection string pattern)
- Queue naming convention
- How tasks are registered and imported

## 4. Env var inventory
- List every env var already used (so ticketing does not conflict or duplicate)
- Note any that ticketing can reuse (DB URL, Redis URL, AWS region)

## 5. Conventions to match
- Import style (relative vs absolute)
- Error handling patterns
- Logging setup
- Any shared utilities ticketing should use

## 6. Gaps or conflicts
- Anything in the existing codebase that conflicts with the ticketing plans in CLAUDE.md
- Any assumption in CLAUDE.md that needs correction based on real code

## 7. New questions (add as SECTION H)
- Any decision needed before Session 1 that only the codebase can reveal
- Append these to docs/claude-tickets/context/existing-services.md as SECTION H
