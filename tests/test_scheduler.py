"""Integration tests covering scheduling and agenda behaviour."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Iterator

import pytest

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend import database
from backend.app import agenda_endpoint, create_group, create_level, update_class
from backend.schemas import (
    ClassUpdate,
    GroupCreate,
    GroupResponse,
    LevelCreate,
    LevelResponse,
    PlanPayload,
    PlanTopic,
    PlanWeek,
)
from backend.services.scheduler import generate_classes
from sqlite3 import Connection


@pytest.fixture
def session_factory(tmp_path) -> Iterator[Connection]:
    db_path = tmp_path / "test.db"
    database.configure(f"sqlite:///{db_path}")
    database.init_db()
    conn = database.open_connection()
    try:
        yield conn
    finally:
        conn.close()


def _persist_level(session: Connection, name: str, start_date: date) -> LevelResponse:
    payload = LevelCreate(name=name, start_date=start_date)
    return create_level(payload, db=session)


def _persist_group(session: Connection, level_id: int, name: str) -> GroupResponse:
    payload = GroupCreate(
        name=name,
        schedule=[{"weekday": 0, "start_time": "09:00", "end_time": "10:00"}],
    )
    # Pydantic will parse the nested schedule dictionaries automatically
    return create_group(level_id, payload, db=session)


def test_scheduler_skips_holidays(session_factory) -> None:
    start = date(2024, 9, 2)
    session = session_factory
    level = _persist_level(session, "Level 1", start)
    group = _persist_group(session, level.id, "Group A")

    session.execute(
        "INSERT INTO no_class_days (date, reason) VALUES (?, ?)",
        (start.isoformat(), "Holiday"),
    )

    plan = PlanPayload(
        level_id=level.id,
        weeks=[
            PlanWeek(
                week_number=1,
                topics=[PlanTopic(group_id=group.id, topic="Introduction", trimester_color="green")],
            )
        ],
    )

    generate_classes(plan, session)

    rows = session.execute("SELECT * FROM classes").fetchall()
    assert rows == []


def test_trimester_color_exposed_in_agenda(session_factory) -> None:
    start = date(2024, 9, 2)
    session = session_factory
    level = _persist_level(session, "Level 1", start)
    group = _persist_group(session, level.id, "Group A")

    plan = PlanPayload(
        level_id=level.id,
        weeks=[
            PlanWeek(
                week_number=1,
                topics=[PlanTopic(group_id=group.id, topic="Introduction", trimester_color="blue")],
            )
        ],
    )

    generate_classes(plan, session)

    agenda = agenda_endpoint(level_id=level.id, week=1, db=session)
    assert agenda.classes, "Expected at least one class in the agenda"
    first_class = agenda.classes[0]
    assert first_class.trimester_color == "blue"
    assert first_class.topic == "Introduction"


def test_manual_reschedule_persists_on_regeneration(session_factory) -> None:
    start = date(2024, 9, 2)
    session = session_factory
    level = _persist_level(session, "Level 1", start)
    group = _persist_group(session, level.id, "Group A")

    plan = PlanPayload(
        level_id=level.id,
        weeks=[
            PlanWeek(
                week_number=1,
                topics=[PlanTopic(group_id=group.id, topic="Introduction", trimester_color="green")],
            )
        ],
    )

    generate_classes(plan, session)

    existing = session.execute("SELECT id FROM classes").fetchone()
    assert existing is not None
    class_id = existing["id"]

    new_date = start + timedelta(days=1)
    update_payload = ClassUpdate(date=new_date, start_time="11:00")
    updated = update_class(class_id, update_payload, db=session)
    assert updated.manual_override is True
    assert updated.status == "rescheduled"
    assert updated.date == new_date
    assert str(updated.start_time) == "11:00:00"

    generate_classes(plan, session)

    classes = session.execute("SELECT * FROM classes").fetchall()
    assert len(classes) == 1
    refreshed = classes[0]
    assert refreshed["manual_override"] == 1
    assert refreshed["date"] == new_date.isoformat()
    assert refreshed["start_time"] == "11:00:00"
