"""Lightweight SQLite helpers for planner persistence."""
"""SQLite database helpers for holiday and scheduling data."""
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
from datetime import date
from pathlib import Path
from typing import Generator, Iterable

DB_FILENAME = "planner.db"
DEFAULT_DB_PATH = Path(__file__).resolve().parent / DB_FILENAME


def _get_db_path() -> Path:
    override = os.environ.get("PLANNER_DB_PATH")
    if override:
        path = Path(override)
        if path.name == ":memory:":
            # Allow shared cache URI style path when using in-memory database.
            return path
        return path
    return DEFAULT_DB_PATH


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """Yield a SQLite connection with foreign keys enabled."""
    db_path = _get_db_path()
    if db_path.name == ":memory:":
        conn = sqlite3.connect("file::memory:?cache=shared", uri=True, detect_types=sqlite3.PARSE_DECLTYPES)
    else:
        conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
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
def init_db(reset: bool = False) -> None:
    """Initialize database tables and seed sample data."""
    db_path = _get_db_path()
    if (
        reset
        and db_path.name != ":memory:"
        and db_path.exists()
        and db_path.is_file()
    ):
        db_path.unlink()

    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS academic_years (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL
            );

            CREATE TABLE IF NOT EXISTS classes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                scheduled_date DATE NOT NULL,
                academic_year_id INTEGER NOT NULL,
                FOREIGN KEY (academic_year_id) REFERENCES academic_years(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS holidays (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                academic_year_id INTEGER NOT NULL,
                CHECK (DATE(start_date) <= DATE(end_date)),
                FOREIGN KEY (academic_year_id) REFERENCES academic_years(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS rescheduling_suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_id INTEGER NOT NULL,
                holiday_id INTEGER NOT NULL,
                suggestion TEXT NOT NULL,
                FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE,
                FOREIGN KEY (holiday_id) REFERENCES holidays(id) ON DELETE CASCADE,
                UNIQUE (class_id, holiday_id)
            );
            """
        )

        seed_academic_years(conn)
        seed_classes(conn)


def seed_academic_years(conn: sqlite3.Connection) -> None:
    cur = conn.execute("SELECT COUNT(*) AS total FROM academic_years")
    total = cur.fetchone()["total"]
    if total:
        return

    years: Iterable[tuple[str, date, date]] = (
        ("2024-2025", date(2024, 8, 1), date(2025, 5, 31)),
        ("2025-2026", date(2025, 8, 1), date(2026, 5, 31)),
    )
    conn.executemany(
        "INSERT INTO academic_years (name, start_date, end_date) VALUES (?, ?, ?)",
        years,
    )


def seed_classes(conn: sqlite3.Connection) -> None:
    cur = conn.execute("SELECT COUNT(*) AS total FROM classes")
    total = cur.fetchone()["total"]
    if total:
        return

    classes: Iterable[tuple[str, date, int]] = (
        ("Intro to Planning", date(2024, 9, 10), 1),
        ("Advanced Scheduling", date(2024, 12, 12), 1),
        ("Systems Design", date(2025, 2, 20), 1),
        ("Collaboration Workshop", date(2025, 9, 15), 2),
    )
    conn.executemany(
        "INSERT INTO classes (name, scheduled_date, academic_year_id) VALUES (?, ?, ?)",
        classes,
    )


def row_to_dict(row: sqlite3.Row) -> dict:
    return {key: row[key] for key in row.keys()}
