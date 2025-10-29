"""Tests for reporting service outputs."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.services import reports


def test_trimester_summary_aggregates_hours_and_topics() -> None:
    records = [
        reports.ActivityRecord("Alpha", "Trimester 1", "Science", "Lab", 2.5),
        reports.ActivityRecord("Alpha", "Trimester 1", "Science", "Lab", 1.0),
        reports.ActivityRecord("Alpha", "Trimester 1", "Math", "Seminar", 3.0),
    ]

    summary = reports.trimester_summary(records)
    assert summary == [
        {
            "group": "Alpha",
            "trimester": "Trimester 1",
            "total_hours": 6.5,
            "topics": [
                {"topic": "Math", "hours": 3.0, "sessions": 1},
                {"topic": "Science", "hours": 3.5, "sessions": 2},
            ],
            "activities": [
                {"activity": "Lab", "hours": 3.5, "sessions": 2},
                {"activity": "Seminar", "hours": 3.0, "sessions": 1},
            ],
        }
    ]


def test_topic_summary_rolls_up_groups_and_trimester_hours() -> None:
    records = [
        reports.ActivityRecord("Alpha", "Trimester 1", "Science", "Lab", 2.5),
        reports.ActivityRecord("Alpha", "Trimester 2", "Science", "Workshop", 1.5),
        reports.ActivityRecord("Beta", "Trimester 1", "Science", "Lab", 2.0),
    ]

    summary = reports.topic_summary(records)
    assert summary == [
        {
            "topic": "Science",
            "total_hours": 6.0,
            "groups": [
                {
                    "group": "Alpha",
                    "hours": 4.0,
                    "sessions": 2,
                    "trimesters": [
                        {"trimester": "Trimester 1", "hours": 2.5},
                        {"trimester": "Trimester 2", "hours": 1.5},
                    ],
                },
                {
                    "group": "Beta",
                    "hours": 2.0,
                    "sessions": 1,
                    "trimesters": [
                        {"trimester": "Trimester 1", "hours": 2.0},
                    ],
                },
            ],
            "activities": [
                {"activity": "Lab", "hours": 4.5, "sessions": 2},
                {"activity": "Workshop", "hours": 1.5, "sessions": 1},
            ],
        }
    ]


def test_csv_builders_include_headers() -> None:
    trimester_csv = reports.build_trimester_csv([
        {
            "group": "Alpha",
            "trimester": "Trimester 1",
            "total_hours": 3.5,
            "topics": [{"topic": "Science", "hours": 3.5, "sessions": 2}],
            "activities": [{"activity": "Lab", "hours": 3.5, "sessions": 2}],
        }
    ])
    assert "Group,Trimester,Total Hours" in trimester_csv.splitlines()[0]

    topic_csv = reports.build_topic_csv([
        {
            "topic": "Science",
            "total_hours": 3.5,
            "groups": [{"group": "Alpha", "hours": 3.5, "sessions": 2}],
            "activities": [{"activity": "Lab", "hours": 3.5, "sessions": 2}],
        }
    ])
    assert "Topic,Total Hours,Group Breakdown" in topic_csv.splitlines()[0]


def test_pdf_builder_creates_valid_document() -> None:
    pdf_bytes = reports.build_topic_pdf([
        {
            "topic": "Science",
            "total_hours": 3.5,
            "groups": [{"group": "Alpha", "hours": 3.5, "sessions": 2}],
            "activities": [{"activity": "Lab", "hours": 3.5, "sessions": 2}],
        }
    ])
    assert pdf_bytes.startswith(b"%PDF")
    assert b"Science" in pdf_bytes
