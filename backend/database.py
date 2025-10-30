"""SQLite database helpers for the planner backend."""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Iterator

DATABASE_PRAGMA = "PRAGMA foreign_keys = ON"
_SQLITE_DETECT_TYPES = sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES

_database_url = os.getenv("DATABASE_URL", "sqlite:///./data/planner.db")


def set_database_url(url: str) -> None:
    """Override the database URL, primarily for tests."""

    global _database_url
    _database_url = url


def configure(url: str) -> None:
    """Backward compatible alias for ``set_database_url``."""

    set_database_url(url)


def _resolve_sqlite_target() -> tuple[str, bool]:
    """Return the SQLite connection target and whether URI mode is required."""

    if not _database_url.startswith("sqlite:///"):
        raise ValueError(f"Unsupported database URL: {_database_url}")

    target = _database_url.replace("sqlite:///", "", 1)
    if target == ":memory:":
        return target, False
    if target.startswith("file:"):
        return target, True

    path = Path(target).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path), False


def get_connection() -> sqlite3.Connection:
    """Create a SQLite connection with common configuration applied."""

    target, uri = _resolve_sqlite_target()
    conn = sqlite3.connect(
        target,
        detect_types=_SQLITE_DETECT_TYPES,
        check_same_thread=False,
        uri=uri,
    )
    conn.row_factory = sqlite3.Row
    conn.execute(DATABASE_PRAGMA)
    return conn


def open_connection() -> sqlite3.Connection:
    """Backward compatible alias for :func:`get_connection`."""

    return get_connection()


@contextmanager
def connection_scope() -> Iterator[sqlite3.Connection]:
    """Context manager that commits on success and rolls back on error."""

    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:  # noqa: BLE001 - propagate after rollback
        conn.rollback()
        raise
    finally:
        conn.close()


def get_db() -> Generator[sqlite3.Connection, None, None]:  # pragma: no cover - FastAPI hook
    """Yield a database connection suitable for FastAPI dependencies."""

    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:  # noqa: BLE001 - ensure rollback for API errors
        conn.rollback()
        raise
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a SQLite row to a plain dictionary."""

    return {key: row[key] for key in row.keys()}


def init_db() -> None:
    """Create required database tables if they do not already exist."""

    schema = """
    CREATE TABLE IF NOT EXISTS levels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        start_date TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        level_id INTEGER NOT NULL REFERENCES levels(id) ON DELETE CASCADE,
        name TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
        weekday INTEGER NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT,
        UNIQUE(group_id, weekday, start_time)
    );

    CREATE TABLE IF NOT EXISTS no_class_days (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL UNIQUE,
        reason TEXT
    );

    CREATE TABLE IF NOT EXISTS classes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
        week_number INTEGER NOT NULL,
        date TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT,
        topic TEXT,
        trimester_color TEXT,
        status TEXT NOT NULL DEFAULT 'scheduled',
        manual_override INTEGER NOT NULL DEFAULT 0,
        academic_year_id INTEGER
    );

    CREATE TABLE IF NOT EXISTS academic_years (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS holidays (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        academic_year_id INTEGER NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS rescheduling_suggestions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
        holiday_id INTEGER NOT NULL REFERENCES holidays(id) ON DELETE CASCADE,
        suggestion TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS class_schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        subject TEXT,
        grade_level TEXT,
        start_date TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS topics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        class_id INTEGER NOT NULL REFERENCES class_schedules(id) ON DELETE CASCADE,
        title TEXT NOT NULL,
        description TEXT,
        scheduled_date TEXT NOT NULL,
        position INTEGER NOT NULL,
        is_holiday INTEGER NOT NULL DEFAULT 0,
        holiday_reason TEXT,
        last_generated_at TEXT
    );

    CREATE TABLE IF NOT EXISTS activities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        provenance TEXT NOT NULL,
        created_at TEXT NOT NULL,
        superseded INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS resources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        url TEXT,
        type TEXT,
        notes TEXT,
        provenance TEXT NOT NULL,
        created_at TEXT NOT NULL,
        superseded INTEGER NOT NULL DEFAULT 0
    );
    """

    with connection_scope() as conn:
        conn.executescript(schema)


__all__ = [
    "connection_scope",
    "configure",
    "get_connection",
    "get_db",
    "init_db",
    "open_connection",
    "row_to_dict",
    "set_database_url",
]
