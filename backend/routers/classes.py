"""Class schedule endpoints providing AI-assisted planning capabilities."""
from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from typing import Iterable

from fastapi import APIRouter, Depends, HTTPException, status

from ..dependencies import get_db, get_planner_service
from ..schemas import (
    ClassScheduleCreate,
    ClassScheduleRead,
    GenerationRequest,
    GenerationResponse,
    HolidayAdjustmentRequest,
    HolidayAdjustmentResponse,
)
from ..services import AIPlannerService, PlannerOutput, PlannerTopic


router = APIRouter(prefix="/classes", tags=["classes"])


def _row_to_activity(row) -> dict:
    provenance = json.loads(row["provenance"])
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "provenance": provenance,
        "superseded": bool(row["superseded"]),
        "created_at": datetime.fromisoformat(row["created_at"]),
    }


def _row_to_resource(row) -> dict:
    provenance = json.loads(row["provenance"])
    return {
        "id": row["id"],
        "name": row["name"],
        "url": row["url"],
        "type": row["type"],
        "notes": row["notes"],
        "provenance": provenance,
        "superseded": bool(row["superseded"]),
        "created_at": datetime.fromisoformat(row["created_at"]),
    }


def _row_to_topic_summary(row) -> dict:
    return {
        "id": row["id"],
        "class_id": row["class_id"],
        "title": row["title"],
        "description": row["description"],
        "scheduled_date": date.fromisoformat(row["scheduled_date"]),
        "position": row["position"],
        "is_holiday": bool(row["is_holiday"]),
        "holiday_reason": row["holiday_reason"],
        "last_generated_at": (
            datetime.fromisoformat(row["last_generated_at"])
            if row["last_generated_at"]
            else None
        ),
    }


def _fetch_topic_details(conn, topic_id: int) -> dict:
    topic_row = conn.execute(
        "SELECT * FROM topics WHERE id = ?",
        (topic_id,),
    ).fetchone()
    if topic_row is None:
        raise ValueError(f"Topic {topic_id} not found")

    topic = _row_to_topic_summary(topic_row)
    activities = conn.execute(
        "SELECT * FROM activities WHERE topic_id = ? ORDER BY id",
        (topic_id,),
    ).fetchall()
    resources = conn.execute(
        "SELECT * FROM resources WHERE topic_id = ? ORDER BY id",
        (topic_id,),
    ).fetchall()
    topic["activities"] = [_row_to_activity(row) for row in activities]
    topic["resources"] = [_row_to_resource(row) for row in resources]
    return topic


def _fetch_topics(conn, class_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM topics WHERE class_id = ? ORDER BY position",
        (class_id,),
    ).fetchall()
    return [_row_to_topic_summary(row) for row in rows]


def _fetch_topics_by_ids(conn, topic_ids: Iterable[int]) -> list[dict]:
    ids = list(topic_ids)
    if not ids:
        return []
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"SELECT * FROM topics WHERE id IN ({placeholders}) ORDER BY position",
        ids,
    ).fetchall()
    return [_row_to_topic_summary(row) for row in rows]


def _fetch_schedule(conn, class_id: int) -> dict:
    schedule_row = conn.execute(
        "SELECT * FROM class_schedules WHERE id = ?",
        (class_id,),
    ).fetchone()
    if schedule_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")

    schedule = {
        "id": schedule_row["id"],
        "name": schedule_row["name"],
        "subject": schedule_row["subject"],
        "grade_level": schedule_row["grade_level"],
        "start_date": date.fromisoformat(schedule_row["start_date"]),
    }

    topic_rows = conn.execute(
        "SELECT id FROM topics WHERE class_id = ? ORDER BY position",
        (class_id,),
    ).fetchall()
    topics = [_fetch_topic_details(conn, row["id"]) for row in topic_rows]
    schedule["topics"] = topics
    return schedule


def _fetch_schedule_header(conn, class_id: int) -> dict:
    row = conn.execute(
        "SELECT id, name, subject, grade_level FROM class_schedules WHERE id = ?",
        (class_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    return {
        "id": row["id"],
        "name": row["name"],
        "subject": row["subject"],
        "grade_level": row["grade_level"],
    }


def _supersede_existing_content(conn, topic_id: int, reason: str) -> None:
    timestamp = datetime.utcnow().isoformat()
    activity_rows = conn.execute(
        "SELECT id, provenance FROM activities WHERE topic_id = ? AND superseded = 0",
        (topic_id,),
    ).fetchall()
    for row in activity_rows:
        provenance = json.loads(row["provenance"])
        history = list(provenance.get("history", []))
        history.append({"event": "superseded", "reason": reason, "at": timestamp})
        provenance["history"] = history
        conn.execute(
            "UPDATE activities SET superseded = 1, provenance = ? WHERE id = ?",
            (json.dumps(provenance), row["id"]),
        )

    resource_rows = conn.execute(
        "SELECT id, provenance FROM resources WHERE topic_id = ? AND superseded = 0",
        (topic_id,),
    ).fetchall()
    for row in resource_rows:
        provenance = json.loads(row["provenance"])
        history = list(provenance.get("history", []))
        history.append({"event": "superseded", "reason": reason, "at": timestamp})
        provenance["history"] = history
        conn.execute(
            "UPDATE resources SET superseded = 1, provenance = ? WHERE id = ?",
            (json.dumps(provenance), row["id"]),
        )


def _store_generation_result(
    conn,
    topic_id: int,
    result: PlannerOutput,
    trigger: str,
    generated_at: datetime,
) -> None:
    base_provenance = dict(result.provenance or {})
    base_provenance.setdefault("model", "unknown")
    base_provenance.update(
        {
            "trigger": trigger,
            "topic_id": topic_id,
            "generated_at": generated_at.isoformat(),
        }
    )

    for plan in result.activities:
        provenance = dict(base_provenance)
        provenance["artifact"] = "activity"
        conn.execute(
            """
            INSERT INTO activities (topic_id, title, description, provenance, created_at, superseded)
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            (
                topic_id,
                plan.title,
                plan.description,
                json.dumps(provenance),
                generated_at.isoformat(),
            ),
        )

    for plan in result.resources:
        provenance = dict(base_provenance)
        provenance["artifact"] = "resource"
        conn.execute(
            """
            INSERT INTO resources (topic_id, name, url, type, notes, provenance, created_at, superseded)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                topic_id,
                plan.name,
                plan.url,
                plan.type,
                plan.notes,
                json.dumps(provenance),
                generated_at.isoformat(),
            ),
        )


def _topic_to_context(topic: dict, schedule: dict) -> PlannerTopic:
    scheduled_dt = datetime.combine(topic["scheduled_date"], time.min)
    return PlannerTopic(
        topic_title=topic["title"],
        topic_description=topic["description"],
        scheduled_date=scheduled_dt,
        class_name=schedule["name"],
        subject=schedule["subject"],
        grade_level=schedule["grade_level"],
    )


async def _generate_for_topics(
    conn,
    schedule: dict,
    topics: Iterable[dict],
    planner: AIPlannerService,
    trigger: str,
) -> list[int]:
    candidates = [topic for topic in topics if not topic["is_holiday"]]
    if not candidates:
        return []

    contexts = [_topic_to_context(topic, schedule) for topic in candidates]
    outputs = await planner.generate_many(contexts)

    regenerated_ids: list[int] = []
    now = datetime.utcnow()
    for topic, result in zip(candidates, outputs, strict=True):
        _supersede_existing_content(conn, topic["id"], reason=trigger)
        _store_generation_result(conn, topic["id"], result, trigger=trigger, generated_at=now)
        conn.execute(
            "UPDATE topics SET last_generated_at = ? WHERE id = ?",
            (now.isoformat(), topic["id"]),
        )
        regenerated_ids.append(topic["id"])

    return regenerated_ids


def _resequence_topics(conn, class_id: int) -> None:
    rows = conn.execute(
        "SELECT id FROM topics WHERE class_id = ? ORDER BY scheduled_date, id",
        (class_id,),
    ).fetchall()
    for index, row in enumerate(rows):
        conn.execute(
            "UPDATE topics SET position = ? WHERE id = ?",
            (index, row["id"]),
        )


def _apply_no_class_day(conn, class_id: int, day: date, reason: str) -> tuple[int, list[int]]:
    inserted = 0
    existing = conn.execute(
        """
        SELECT id FROM topics
        WHERE class_id = ? AND is_holiday = 1 AND scheduled_date = ?
        """,
        (class_id, day.isoformat()),
    ).fetchone()
    if existing is None:
        conn.execute(
            """
            INSERT INTO topics (class_id, title, description, scheduled_date, position, is_holiday, holiday_reason)
            VALUES (?, ?, NULL, ?, 0, 1, ?)
            """,
            (class_id, f"No class - {reason}", day.isoformat(), reason),
        )
        inserted = 1

    impacted_ids: list[int] = []
    rows = conn.execute(
        """
        SELECT id, scheduled_date FROM topics
        WHERE class_id = ? AND is_holiday = 0 AND scheduled_date >= ?
        ORDER BY scheduled_date, id
        """,
        (class_id, day.isoformat()),
    ).fetchall()

    for row in rows:
        new_date = date.fromisoformat(row["scheduled_date"]) + timedelta(days=1)
        conn.execute(
            "UPDATE topics SET scheduled_date = ? WHERE id = ?",
            (new_date.isoformat(), row["id"]),
        )
        impacted_ids.append(row["id"])

    return inserted, impacted_ids


@router.post("/", response_model=ClassScheduleRead, status_code=status.HTTP_201_CREATED)
async def create_class_schedule(
    payload: ClassScheduleCreate,
    conn = Depends(get_db),
    planner: AIPlannerService = Depends(get_planner_service),
) -> ClassScheduleRead:
    cursor = conn.execute(
        """
        INSERT INTO class_schedules (name, subject, grade_level, start_date)
        VALUES (?, ?, ?, ?)
        """,
        (
            payload.name,
            payload.subject,
            payload.grade_level,
            payload.start_date.isoformat(),
        ),
    )
    schedule_id = cursor.lastrowid

    for index, topic in enumerate(payload.topics):
        conn.execute(
            """
            INSERT INTO topics (class_id, title, description, scheduled_date, position, is_holiday)
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            (
                schedule_id,
                topic.title,
                topic.description,
                topic.scheduled_date.isoformat(),
                index,
            ),
        )

    schedule_header = {
        "id": schedule_id,
        "name": payload.name,
        "subject": payload.subject,
        "grade_level": payload.grade_level,
    }
    topics = _fetch_topics(conn, schedule_id)

    await _generate_for_topics(
        conn,
        schedule_header,
        topics,
        planner,
        trigger="schedule-created",
    )

    schedule = _fetch_schedule(conn, schedule_id)
    return schedule


@router.post("/{class_id}/generate", response_model=GenerationResponse)
async def trigger_generation(
    class_id: int,
    payload: GenerationRequest,
    conn = Depends(get_db),
    planner: AIPlannerService = Depends(get_planner_service),
) -> GenerationResponse:
    schedule = _fetch_schedule_header(conn, class_id)
    topics = _fetch_topics(conn, class_id)

    if payload.topic_ids:
        available = {topic["id"]: topic for topic in topics}
        missing = [topic_id for topic_id in payload.topic_ids if topic_id not in available]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"missing_topic_ids": missing},
            )
        selected = [available[topic_id] for topic_id in payload.topic_ids]
    elif payload.regenerate_all or not topics:
        selected = topics
    else:
        selected = [topic for topic in topics if not topic["is_holiday"]]

    regenerated_ids = await _generate_for_topics(
        conn,
        schedule,
        selected,
        planner,
        trigger=payload.reason,
    )
    return GenerationResponse(regenerated_topic_ids=regenerated_ids)


@router.post("/{class_id}/calendar/adjust", response_model=HolidayAdjustmentResponse)
async def adjust_for_holidays(
    class_id: int,
    payload: HolidayAdjustmentRequest,
    conn = Depends(get_db),
    planner: AIPlannerService = Depends(get_planner_service),
) -> HolidayAdjustmentResponse:
    schedule = _fetch_schedule_header(conn, class_id)

    if not payload.no_class_dates:
        return HolidayAdjustmentResponse(inserted_holidays=0, regenerated_topic_ids=[])

    inserted_total = 0
    impacted_topic_ids: list[int] = []

    for day in sorted(set(payload.no_class_dates)):
        inserted, impacted = _apply_no_class_day(conn, class_id, day, payload.reason)
        inserted_total += inserted
        impacted_topic_ids.extend(impacted)

    _resequence_topics(conn, class_id)
    impacted_topics = _fetch_topics_by_ids(conn, impacted_topic_ids)

    regenerated_ids = await _generate_for_topics(
        conn,
        schedule,
        impacted_topics,
        planner,
        trigger="calendar-adjustment",
    )
    return HolidayAdjustmentResponse(
        inserted_holidays=inserted_total,
        regenerated_topic_ids=regenerated_ids,
    )
