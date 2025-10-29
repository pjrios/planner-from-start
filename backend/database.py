"""Lightweight SQLite helpers for the planning backend."""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator


DATABASE_PATH = Path(os.getenv("DATABASE_URL", "planner.db")).expanduser()


def configure(db_url: str | None = None) -> None:
    """Configure the database file path."""

    global DATABASE_PATH  # noqa: PLW0603 - module-level configuration
    if db_url and db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "", 1)
        DATABASE_PATH = Path(db_path).expanduser()
    elif db_url:
        DATABASE_PATH = Path(db_url).expanduser()
    else:
        DATABASE_PATH = Path(os.getenv("DATABASE_URL", "planner.db")).expanduser()


def open_connection() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(
        DATABASE_PATH,
        check_same_thread=False,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """FastAPI dependency yielding a transactional SQLite connection."""

    connection = open_connection()
    try:
        yield connection
        connection.commit()
    except Exception:  # noqa: BLE001 - rollback on any error
        connection.rollback()
        raise
    finally:
        connection.close()


def session_scope() -> contextmanager[sqlite3.Connection]:
    """Provide a transactional context manager for scripts and tests."""

    return get_db()


def init_db() -> None:
    """Create tables if they do not yet exist."""

    with open_connection() as conn:
        conn.executescript(
            """
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

            CREATE TABLE IF NOT EXISTS classes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
                week_number INTEGER NOT NULL,
                date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                topic TEXT NOT NULL,
                trimester_color TEXT,
                status TEXT NOT NULL DEFAULT 'scheduled',
                manual_override INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS no_class_days (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL UNIQUE,
                reason TEXT
            );
            """
        )


# Configure immediately on import so the default path is respected.
configure()
