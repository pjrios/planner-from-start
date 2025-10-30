from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture()
def app_module(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("PLANNER_DB_PATH", str(db_path))

    database = importlib.import_module("backend.database")
    importlib.reload(database)
    database.init_db(reset=True)

    scheduler = importlib.import_module("backend.scheduler")
    importlib.reload(scheduler)

    app_module = importlib.import_module("backend.app")
    importlib.reload(app_module)
    return app_module


def _find_class(classes, name: str):
    for item in classes:
        if item.name == name:
            return item
    raise AssertionError(f"Class {name!r} not found in response")


def test_holiday_creation_triggers_rescheduling(app_module) -> None:
    years = app_module.list_academic_years()
    assert years
    year_id = years[0].id

    classes = app_module.list_classes(year_id)
    target_class = _find_class(classes, "Advanced Scheduling")

    payload = app_module.HolidayCreate(
        name="Winter Break",
        start_date="2024-12-10",
        end_date="2024-12-20",
        academic_year_id=year_id,
    )
    holiday = app_module.create_holiday(payload)
    assert holiday.suggestions, "Expected rescheduling suggestions for overlapping class"
    assert any(
        target_class.name in suggestion.suggestion for suggestion in holiday.suggestions
    )

    refreshed_class = app_module.get_class(target_class.id)
    assert refreshed_class.suggestions

    update_payload = app_module.HolidayUpdate(
        name="Winter Break",
        start_date="2024-11-01",
        end_date="2024-11-10",
        academic_year_id=year_id,
    )
    updated_holiday = app_module.update_holiday(holiday.id, update_payload)
    assert updated_holiday.suggestions == []

    updated_class = app_module.get_class(target_class.id)
    assert updated_class.suggestions == []


def test_holiday_requires_valid_academic_year(app_module) -> None:
    payload = app_module.HolidayCreate(
        name="Invalid Year Holiday",
        start_date="2024-09-01",
        end_date="2024-09-05",
        academic_year_id=999,
    )
    with pytest.raises(app_module.HTTPException) as exc_info:
        app_module.create_holiday(payload)
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Academic year not found"
