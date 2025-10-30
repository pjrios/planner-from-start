"""Reporting service aggregating teaching activities."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List, Sequence
import csv
import io


@dataclass(frozen=True)
class ActivityRecord:
    """Represents a single scheduled activity."""

    group: str
    trimester: str
    topic: str
    activity: str
    hours: float


_DEFAULT_DATASET: tuple[ActivityRecord, ...] = (
    ActivityRecord("Group A", "Trimester 1", "Literacy", "Workshop", 2.0),
    ActivityRecord("Group A", "Trimester 1", "Literacy", "Field Study", 1.5),
    ActivityRecord("Group A", "Trimester 1", "STEM", "Lab", 3.0),
    ActivityRecord("Group A", "Trimester 2", "STEM", "Workshop", 2.5),
    ActivityRecord("Group A", "Trimester 2", "Civics", "Seminar", 1.5),
    ActivityRecord("Group A", "Trimester 3", "Arts", "Studio", 2.25),
    ActivityRecord("Group B", "Trimester 1", "Literacy", "Seminar", 2.0),
    ActivityRecord("Group B", "Trimester 1", "Mathematics", "Lecture", 1.75),
    ActivityRecord("Group B", "Trimester 2", "Mathematics", "Workshop", 2.5),
    ActivityRecord("Group B", "Trimester 2", "STEM", "Lab", 2.0),
    ActivityRecord("Group B", "Trimester 3", "Civics", "Project", 3.0),
    ActivityRecord("Group C", "Trimester 1", "Literacy", "Workshop", 1.25),
    ActivityRecord("Group C", "Trimester 1", "Arts", "Studio", 2.0),
    ActivityRecord("Group C", "Trimester 2", "Arts", "Seminar", 1.5),
    ActivityRecord("Group C", "Trimester 2", "Mathematics", "Lab", 2.25),
    ActivityRecord("Group C", "Trimester 3", "Mathematics", "Lecture", 2.75),
)


def load_default_records() -> List[ActivityRecord]:
    """Return a copy of the default fixture dataset."""

    return list(_DEFAULT_DATASET)


def _prepare_records(records: Iterable[ActivityRecord] | None) -> List[ActivityRecord]:
    if records is None:
        return load_default_records()
    return list(records)


def trimester_summary(records: Iterable[ActivityRecord] | None = None) -> list[dict]:
    """Aggregate total hours, topics and activities by group/trimester."""

    prepared = _prepare_records(records)
    grouped: dict[tuple[str, str], dict] = {}

    for entry in prepared:
        key = (entry.group, entry.trimester)
        bucket = grouped.setdefault(
            key,
            {
                "hours": 0.0,
                "topics": defaultdict(lambda: {"hours": 0.0, "sessions": 0}),
                "activities": defaultdict(lambda: {"hours": 0.0, "sessions": 0}),
            },
        )
        bucket["hours"] += entry.hours

        topic_stats = bucket["topics"][entry.topic]
        topic_stats["hours"] += entry.hours
        topic_stats["sessions"] += 1

        activity_stats = bucket["activities"][entry.activity]
        activity_stats["hours"] += entry.hours
        activity_stats["sessions"] += 1

    summaries: list[dict] = []
    for (group, trimester), data in sorted(grouped.items()):
        topics = [
            {
                "topic": topic,
                "hours": round(values["hours"], 2),
                "sessions": values["sessions"],
            }
            for topic, values in sorted(data["topics"].items())
        ]
        activities = [
            {
                "activity": activity,
                "hours": round(values["hours"], 2),
                "sessions": values["sessions"],
            }
            for activity, values in sorted(data["activities"].items())
        ]
        summaries.append(
            {
                "group": group,
                "trimester": trimester,
                "total_hours": round(data["hours"], 2),
                "topics": topics,
                "activities": activities,
            }
        )

    return summaries


def topic_summary(records: Iterable[ActivityRecord] | None = None) -> list[dict]:
    """Aggregate hours and activities per topic across the dataset."""

    prepared = _prepare_records(records)
    grouped: dict[str, dict] = {}

    for entry in prepared:
        bucket = grouped.setdefault(
            entry.topic,
            {
                "hours": 0.0,
                "groups": defaultdict(lambda: {"hours": 0.0, "sessions": 0, "trimesters": defaultdict(float)}),
                "activities": defaultdict(lambda: {"hours": 0.0, "sessions": 0}),
            },
        )
        bucket["hours"] += entry.hours

        group_info = bucket["groups"][entry.group]
        group_info["hours"] += entry.hours
        group_info["sessions"] += 1
        group_info["trimesters"][entry.trimester] += entry.hours

        activity_info = bucket["activities"][entry.activity]
        activity_info["hours"] += entry.hours
        activity_info["sessions"] += 1

    summaries: list[dict] = []
    for topic, data in sorted(grouped.items()):
        groups = []
        for group, info in sorted(data["groups"].items()):
            trimester_breakdown = [
                {
                    "trimester": trimester,
                    "hours": round(hours, 2),
                }
                for trimester, hours in sorted(info["trimesters"].items())
            ]
            groups.append(
                {
                    "group": group,
                    "hours": round(info["hours"], 2),
                    "sessions": info["sessions"],
                    "trimesters": trimester_breakdown,
                }
            )

        activities = [
            {
                "activity": activity,
                "hours": round(values["hours"], 2),
                "sessions": values["sessions"],
            }
            for activity, values in sorted(data["activities"].items())
        ]

        summaries.append(
            {
                "topic": topic,
                "total_hours": round(data["hours"], 2),
                "groups": groups,
                "activities": activities,
            }
        )

    return summaries


def _csv_from_rows(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()


def build_trimester_csv(rows: Iterable[dict] | None = None) -> str:
    summaries = rows if rows is not None else trimester_summary()
    csv_rows: list[list[str]] = []
    for summary in summaries:
        topic_breakdown = "; ".join(
            f"{topic['topic']} ({topic['hours']}h/{topic['sessions']} sessions)"
            for topic in summary["topics"]
        )
        activity_breakdown = "; ".join(
            f"{activity['activity']} ({activity['hours']}h/{activity['sessions']} sessions)"
            for activity in summary["activities"]
        )
        csv_rows.append(
            [
                summary["group"],
                summary["trimester"],
                f"{summary['total_hours']}",
                topic_breakdown,
                activity_breakdown,
            ]
        )
    return _csv_from_rows(
        ["Group", "Trimester", "Total Hours", "Topic Breakdown", "Activity Breakdown"],
        csv_rows,
    )


def build_topic_csv(rows: Iterable[dict] | None = None) -> str:
    summaries = rows if rows is not None else topic_summary()
    csv_rows: list[list[str]] = []
    for summary in summaries:
        group_breakdown = "; ".join(
            f"{group['group']} ({group['hours']}h/{group['sessions']} sessions)"
            for group in summary["groups"]
        )
        activity_breakdown = "; ".join(
            f"{activity['activity']} ({activity['hours']}h/{activity['sessions']} sessions)"
            for activity in summary["activities"]
        )
        csv_rows.append(
            [
                summary["topic"],
                f"{summary['total_hours']}",
                group_breakdown,
                activity_breakdown,
            ]
        )
    return _csv_from_rows(
        ["Topic", "Total Hours", "Group Breakdown", "Activity Breakdown"],
        csv_rows,
    )


def _pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_text_stream(title: str, lines: Sequence[str]) -> str:
    escaped_lines = [_pdf_escape(line) for line in lines]
    stream_lines = [
        "BT",
        "/F1 16 Tf",
        "18 TL",
        "72 760 Td",
        f"({_pdf_escape(title)}) Tj",
        "/F1 11 Tf",
        "14 TL",
        "0 -24 Td",
    ]
    for line in escaped_lines:
        stream_lines.append(f"({line}) Tj")
        stream_lines.append("T*")
    stream_lines.append("ET")
    return "\n".join(stream_lines)


def _build_pdf_document(title: str, headers: Sequence[str], rows: Sequence[Sequence[str]]) -> bytes:
    header_line = " | ".join(headers)
    separator = "-" * len(header_line)
    row_lines = [" | ".join(map(str, row)) for row in rows]
    timestamp = datetime.now(timezone.utc).strftime("Generated %Y-%m-%d %H:%M UTC")
    text_lines = [header_line, separator, *row_lines, "", timestamp]
    stream = _pdf_text_stream(title, text_lines)
    stream_bytes = stream.encode("latin-1", errors="replace")

    content_obj = (
        f"<< /Length {len(stream_bytes)} >>\nstream\n{stream}\nendstream"
    )

    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        content_obj,
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    pdf = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        obj_bytes = f"{index} 0 obj\n{obj}\nendobj\n".encode("latin-1")
        pdf.extend(obj_bytes)

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))

    pdf.extend(
        (
            "trailer\n"
            f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            "startxref\n"
            f"{xref_offset}\n"
            "%%EOF"
        ).encode("latin-1")
    )
    return bytes(pdf)


def build_trimester_pdf(rows: Iterable[dict] | None = None) -> bytes:
    summaries = rows if rows is not None else trimester_summary()
    pdf_rows = [
        [
            summary["group"],
            summary["trimester"],
            f"{summary['total_hours']}h",
            ", ".join(f"{topic['topic']} ({topic['hours']}h)" for topic in summary["topics"]),
        ]
        for summary in summaries
    ]
    headers = ["Group", "Trimester", "Total Hours", "Topics"]
    return _build_pdf_document("Trimester Report", headers, pdf_rows)


def build_topic_pdf(rows: Iterable[dict] | None = None) -> bytes:
    summaries = rows if rows is not None else topic_summary()
    pdf_rows = [
        [
            summary["topic"],
            f"{summary['total_hours']}h",
            ", ".join(f"{group['group']} ({group['hours']}h)" for group in summary["groups"]),
        ]
        for summary in summaries
    ]
    headers = ["Topic", "Total Hours", "Groups"]
    return _build_pdf_document("Topic Report", headers, pdf_rows)


__all__ = [
    "ActivityRecord",
    "load_default_records",
    "trimester_summary",
    "topic_summary",
    "build_trimester_csv",
    "build_topic_csv",
    "build_trimester_pdf",
    "build_topic_pdf",
]
