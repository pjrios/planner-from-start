"""Simple scheduler that recomputes rescheduling suggestions for classes."""
from __future__ import annotations

from datetime import date

import sqlite3

from .database import row_to_dict


def recompute_for_holiday(conn: sqlite3.Connection, holiday_id: int) -> list[dict]:
    """Recompute suggestions for classes affected by a holiday."""
    holiday_row = conn.execute(
        "SELECT * FROM holidays WHERE id = ?", (holiday_id,)
    ).fetchone()
    if holiday_row is None:
        raise ValueError(f"Holiday {holiday_id} does not exist")

    holiday = row_to_dict(holiday_row)
    start = _coerce_date(holiday["start_date"])
    end = _coerce_date(holiday["end_date"])

    overlapping_classes = conn.execute(
        """
        SELECT * FROM classes
        WHERE academic_year_id = ?
          AND DATE(scheduled_date) BETWEEN DATE(?) AND DATE(?)
        ORDER BY DATE(scheduled_date)
        """,
        (holiday["academic_year_id"], start, end),
    ).fetchall()

    conn.execute(
        "DELETE FROM rescheduling_suggestions WHERE holiday_id = ?",
        (holiday_id,),
    )

    suggestions: list[dict] = []
    for class_row in overlapping_classes:
        cls = row_to_dict(class_row)
        suggestion_text = (
            f"Class '{cls['name']}' on {cls['scheduled_date']} overlaps with holiday "
            f"'{holiday['name']}'. Consider rescheduling."
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO rescheduling_suggestions (class_id, holiday_id, suggestion)
            VALUES (?, ?, ?)
            """,
            (cls["id"], holiday_id, suggestion_text),
        )
        suggestions.append(
            {
                "class_id": cls["id"],
                "class_name": cls["name"],
                "scheduled_date": cls["scheduled_date"],
                "holiday_id": holiday_id,
                "holiday_name": holiday["name"],
                "suggestion": suggestion_text,
            }
        )

    # return persisted suggestions for the holiday in case of conflict resolution
    stored = conn.execute(
        """
        SELECT rs.*, c.name AS class_name, c.scheduled_date
        FROM rescheduling_suggestions rs
        JOIN classes c ON c.id = rs.class_id
        WHERE rs.holiday_id = ?
        ORDER BY rs.id
        """,
        (holiday_id,),
    ).fetchall()

    return [
        {
            "id": row["id"],
            "class_id": row["class_id"],
            "holiday_id": row["holiday_id"],
            "suggestion": row["suggestion"],
            "class_name": row["class_name"],
            "scheduled_date": row["scheduled_date"],
        }
        for row in stored
    ]


def _coerce_date(value: object) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError(f"Unsupported date value: {value!r}")
