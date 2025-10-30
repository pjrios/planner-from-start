"""FastAPI dependencies for shared services."""
from __future__ import annotations

from .database import get_connection
from .services.ai_planner import AIPlannerService


planner_service = AIPlannerService()


def get_db():  # pragma: no cover - thin wrapper for dependency injection
    """Expose a SQLite connection dependency."""

    conn = get_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def get_planner_service() -> AIPlannerService:
    """Return the singleton planner service instance."""

    return planner_service
