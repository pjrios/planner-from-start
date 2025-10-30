"""Integration-style tests for AI planning routes using mocked planner output."""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Iterable
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend import database


pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture
def anyio_backend():
    return "asyncio"
from backend.routers.classes import (
    adjust_for_holidays,
    create_class_schedule,
    trigger_generation,
)
from backend.schemas import (
    ClassScheduleCreate,
    GenerationRequest,
    HolidayAdjustmentRequest,
    TopicCreate,
)
from backend.services import ActivityPlan, PlannerOutput, PlannerTopic, ResourcePlan


class QueuePlanner:
    """Test double for AI planner service with deterministic outputs."""

    def __init__(self) -> None:
        self.requests: list[PlannerTopic] = []
        self._queued: list[PlannerOutput] = []

    def queue(self, outputs: Iterable[PlannerOutput]) -> None:
        self._queued.extend(outputs)

    async def generate(self, topic: PlannerTopic) -> PlannerOutput:
        self.requests.append(topic)
        if not self._queued:
            raise AssertionError("Planner queue exhausted")
        return self._queued.pop(0)

    async def generate_many(self, topics):
        return [await self.generate(topic) for topic in topics]


def _make_output(activity_suffix: str, resource_suffix: str) -> PlannerOutput:
    return PlannerOutput(
        activities=[
            ActivityPlan(
                title=f"Activity {activity_suffix}",
                description=f"Do something important: {activity_suffix}",
            )
        ],
        resources=[
            ResourcePlan(
                name=f"Resource {resource_suffix}",
                type="handout",
                notes=f"Use during {resource_suffix}",
            )
        ],
        provenance={"model": "stub-model", "prompt": activity_suffix},
    )


@pytest.fixture()
def planner_and_conn(tmp_path):
    db_path = tmp_path / f"test_{uuid4().hex}.db"
    database.set_database_url(f"sqlite:///{db_path}")
    database.init_db()
    conn = database.get_connection()
    planner = QueuePlanner()
    try:
        yield conn, planner
    finally:
        conn.close()


async def test_generation_on_class_creation(planner_and_conn):
    conn, planner = planner_and_conn
    planner.queue([_make_output("fractions", "fractions")])

    payload = ClassScheduleCreate(
        name="Math 101",
        subject="Math",
        grade_level="5",
        start_date=date(2024, 9, 1),
        topics=[
            TopicCreate(
                title="Fractions",
                description="Equivalent fractions",
                scheduled_date=date(2024, 9, 1),
            )
        ],
    )

    schedule = await create_class_schedule(payload, conn=conn, planner=planner)
    conn.commit()

    assert schedule["topics"][0]["activities"][0]["title"] == "Activity fractions"
    assert schedule["topics"][0]["resources"][0]["name"] == "Resource fractions"

    activities = conn.execute("SELECT provenance FROM activities").fetchall()
    resources = conn.execute("SELECT provenance FROM resources").fetchall()
    assert json.loads(activities[0]["provenance"])["trigger"] == "schedule-created"
    assert json.loads(resources[0]["provenance"])["trigger"] == "schedule-created"


async def test_on_demand_regeneration_supersedes_previous(planner_and_conn):
    conn, planner = planner_and_conn
    planner.queue([_make_output("initial", "initial")])

    payload = ClassScheduleCreate(
        name="Science",
        subject="Science",
        grade_level="6",
        start_date=date(2024, 9, 1),
        topics=[
            TopicCreate(
                title="Cells",
                description="Cell structure",
                scheduled_date=date(2024, 9, 1),
            )
        ],
    )

    schedule = await create_class_schedule(payload, conn=conn, planner=planner)
    conn.commit()
    topic_id = schedule["topics"][0]["id"]
    class_id = schedule["id"]

    planner.queue([_make_output("regen", "regen")])
    request = GenerationRequest(topic_ids=[topic_id], reason="manual-refresh")
    result = await trigger_generation(class_id, request, conn=conn, planner=planner)
    conn.commit()

    assert result.regenerated_topic_ids == [topic_id]

    activities = conn.execute(
        "SELECT provenance, superseded FROM activities ORDER BY id"
    ).fetchall()
    assert len(activities) == 2
    first = json.loads(activities[0]["provenance"])
    second = json.loads(activities[1]["provenance"])
    assert activities[0]["superseded"] == 1
    assert first["history"][0]["reason"] == "manual-refresh"
    assert second["trigger"] == "manual-refresh"


async def test_holiday_adjustment_shifts_and_regenerates(planner_and_conn):
    conn, planner = planner_and_conn
    planner.queue([
        _make_output("day1", "day1"),
        _make_output("day2", "day2"),
    ])

    payload = ClassScheduleCreate(
        name="History",
        subject="History",
        grade_level="7",
        start_date=date(2024, 9, 1),
        topics=[
            TopicCreate(
                title="Ancient Civilizations",
                description="Egypt",
                scheduled_date=date(2024, 9, 1),
            ),
            TopicCreate(
                title="Middle Ages",
                description="Europe",
                scheduled_date=date(2024, 9, 2),
            ),
        ],
    )

    schedule = await create_class_schedule(payload, conn=conn, planner=planner)
    conn.commit()
    second_topic_id = schedule["topics"][1]["id"]
    class_id = schedule["id"]

    planner.queue([_make_output("shifted", "shifted")])
    request = HolidayAdjustmentRequest(no_class_dates=[date(2024, 9, 2)], reason="Labor Day")
    response = await adjust_for_holidays(class_id, request, conn=conn, planner=planner)
    conn.commit()

    assert response.inserted_holidays == 1
    assert response.regenerated_topic_ids == [second_topic_id]

    topic_rows = conn.execute(
        "SELECT id, is_holiday, scheduled_date FROM topics"
    ).fetchall()
    topics = {row["id"]: row for row in topic_rows}
    assert any(row["is_holiday"] == 1 for row in topics.values())
    assert date.fromisoformat(topics[second_topic_id]["scheduled_date"]) == date(2024, 9, 3)

    activities = conn.execute(
        "SELECT superseded FROM activities WHERE topic_id = ?",
        (second_topic_id,),
    ).fetchall()
    assert len(activities) == 2
    assert any(row["superseded"] == 0 for row in activities)
    assert any(row["superseded"] == 1 for row in activities)
