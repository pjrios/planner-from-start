"""Utilities to translate long-term plans into scheduled classes."""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import List, Sequence

from ..database import ensure_no_class_days_table
from ..schemas import PlanPayload, PlanWeek


class SchedulerError(RuntimeError):
    """Raised when scheduling cannot be completed."""


def _ensure_plan(plan: PlanPayload | dict) -> PlanPayload:
    if isinstance(plan, PlanPayload):
        return plan
    if isinstance(plan, dict):
        return PlanPayload(**plan)
    raise TypeError("plan must be a PlanPayload or mapping")


def _week_start_offset(week_number: int, weekday: int) -> int:
    return (week_number - 1) * 7 + weekday


def _collect_week_colours(weeks: Sequence[PlanWeek]) -> dict[tuple[int, int], str | None]:
    colours: dict[tuple[int, int], str | None] = {}
    for week in weeks:
        for topic in week.topics:
            colours[(topic.group_id, week.week_number)] = topic.trimester_color
    return colours


def generate_classes(plan: PlanPayload | dict, db: sqlite3.Connection) -> List[sqlite3.Row]:
    """Create concrete class entries for the supplied plan."""

    payload = _ensure_plan(plan)

    ensure_no_class_days_table(db)

    level_row = db.execute(
        "SELECT id, start_date FROM levels WHERE id = ?",
        (payload.level_id,),
    ).fetchone()
    if level_row is None:
        raise SchedulerError(f"Level {payload.level_id} not found")

    if not payload.weeks:
        return []

    start_date = date.fromisoformat(level_row["start_date"])
    blackout_dates = {
        row["date"] for row in db.execute("SELECT date FROM no_class_days").fetchall()
    }
    colours = _collect_week_colours(payload.weeks)

    generated_rows: list[sqlite3.Row] = []

    for week in payload.weeks:
        for topic in week.topics:
            group_row = db.execute(
                "SELECT id, level_id FROM groups WHERE id = ?",
                (topic.group_id,),
            ).fetchone()
            if group_row is None or group_row["level_id"] != payload.level_id:
                continue

            db.execute(
                "DELETE FROM classes WHERE group_id = ? AND week_number = ? AND manual_override = 0",
                (topic.group_id, week.week_number),
            )

            manual_override_exists = db.execute(
                "SELECT 1 FROM classes WHERE group_id = ? AND week_number = ? AND manual_override = 1 LIMIT 1",
                (topic.group_id, week.week_number),
            ).fetchone()

            schedule_rows = db.execute(
                "SELECT weekday, start_time, end_time FROM schedules WHERE group_id = ?",
                (topic.group_id,),
            ).fetchall()

            for slot in schedule_rows:
                if manual_override_exists:
                    continue

                day_offset = _week_start_offset(week.week_number, slot["weekday"])
                class_date = start_date + timedelta(days=day_offset)
                class_date_iso = class_date.isoformat()

                if class_date_iso in blackout_dates:
                    continue

                cursor = db.execute(
                    """
                    INSERT INTO classes (
                        group_id, week_number, date, start_time, end_time, topic,
                        trimester_color, status, manual_override
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'scheduled', 0)
                    """,
                    (
                        topic.group_id,
                        week.week_number,
                        class_date_iso,
                        slot["start_time"],
                        slot["end_time"],
                        topic.topic,
                        colours.get((topic.group_id, week.week_number)),
                    ),
                )
                class_id = cursor.lastrowid
                row = db.execute(
                    "SELECT * FROM classes WHERE id = ?",
                    (class_id,),
                ).fetchone()
                if row is not None:
                    generated_rows.append(row)

    return generated_rows
