"""Lightweight SQLite helpers for planner persistence."""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


_database_url = os.getenv("DATABASE_URL", "sqlite:///./data/planner.db")


def set_database_url(url: str) -> None:
    """Override the default database URL (primarily for tests)."""

    global _database_url
    _database_url = url


def _resolve_path() -> str:
    if _database_url.startswith("sqlite:///"):
        path = _database_url.replace("sqlite:///", "", 1)
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        return path
    raise ValueError(f"Unsupported database URL: {_database_url}")


def get_connection() -> sqlite3.Connection:
    path = _resolve_path()
    conn = sqlite3.connect(
        path,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def connection_scope() -> Iterator[sqlite3.Connection]:
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Initialise SQLite tables if they do not already exist."""

    with connection_scope() as conn:
        conn.executescript(
            """
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
        )
