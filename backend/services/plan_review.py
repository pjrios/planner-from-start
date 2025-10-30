"""Plan review service with simple JSON-backed persistence."""
from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict

from ..config import DATA_DIR

PLAN_REVIEW_DIR = DATA_DIR / "plan_reviews"
PLAN_REVIEW_DIR.mkdir(parents=True, exist_ok=True)

_FILE_LOCK = Lock()


@dataclass(slots=True)
class PlanRecord:
    """Container for a draft and its audit history."""

    draft: Dict[str, Any]
    history: list[dict[str, Any]]

    def to_response(self) -> dict[str, Any]:
        payload = deepcopy(self.draft)
        payload["history"] = deepcopy(self.history)
        return payload


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _draft_path(draft_id: str) -> Path:
    safe_id = draft_id.replace("/", "_")
    return PLAN_REVIEW_DIR / f"{safe_id}.json"


_DEFAULT_TEMPLATE: dict[str, Any] = {
    "title": "Auto-parsed yearly plan",
    "summary": (
        "This draft was parsed automatically. Review trimester dates, learning levels, "
        "and topic coverage before approving."
    ),
    "status": "pending_review",
    "review_notes": "",
    "trimesters": [
        {
            "id": "trimester-1",
            "name": "Trimester 1",
            "start_date": "2024-01-08",
            "end_date": "2024-03-22",
        },
        {
            "id": "trimester-2",
            "name": "Trimester 2",
            "start_date": "2024-04-08",
            "end_date": "2024-06-28",
        },
        {
            "id": "trimester-3",
            "name": "Trimester 3",
            "start_date": "2024-07-15",
            "end_date": "2024-09-27",
        },
    ],
    "levels": [
        {
            "id": "level-7",
            "name": "Level 7",
            "description": "Students consolidate foundational skills and explore applied projects.",
        },
        {
            "id": "level-8",
            "name": "Level 8",
            "description": "Learners expand analytical thinking with interdisciplinary tasks.",
        },
    ],
    "topics": [
        {
            "id": "topic-1",
            "name": "Scientific Inquiry",
            "trimester_id": "trimester-1",
            "level_id": "level-7",
            "summary": "Introduce the scientific method with lab investigations.",
        },
        {
            "id": "topic-2",
            "name": "Ecosystems Project",
            "trimester_id": "trimester-2",
            "level_id": "level-7",
            "summary": "Field study of local ecosystems and sustainability challenges.",
        },
        {
            "id": "topic-3",
            "name": "Technology & Society",
            "trimester_id": "trimester-3",
            "level_id": "level-8",
            "summary": "Evaluate the social impact of emerging technologies.",
        },
    ],
}


def _seed_record(draft_id: str) -> PlanRecord:
    now = _now_iso()
    draft = deepcopy(_DEFAULT_TEMPLATE)
    draft.update(
        {
            "id": draft_id,
            "created_at": now,
            "updated_at": now,
        }
    )
    history = [
        {
            "timestamp": now,
            "action": "seed",
            "payload": {"message": "Draft created from default template"},
        }
    ]
    return PlanRecord(draft=draft, history=history)


def _load_raw(draft_id: str) -> PlanRecord:
    path = _draft_path(draft_id)
    if not path.exists():
        record = _seed_record(draft_id)
        _write_raw(draft_id, record)
        return record

    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return PlanRecord(draft=payload["draft"], history=payload.get("history", []))


def _write_raw(draft_id: str, record: PlanRecord) -> None:
    path = _draft_path(draft_id)
    payload = {"draft": record.draft, "history": record.history}
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def _apply_changes(draft: dict[str, Any], changes: dict[str, Any]) -> bool:
    """Apply partial updates to the draft. Returns True if something changed."""

    mutable_fields = {"title", "summary", "review_notes", "status", "trimesters", "levels", "topics"}
    changed = False
    for key, value in changes.items():
        if key not in mutable_fields:
            continue
        if draft.get(key) != value and value is not None:
            draft[key] = value
            changed = True
    if changed:
        draft["updated_at"] = _now_iso()
    return changed


def get_draft(draft_id: str) -> dict[str, Any]:
    """Return the draft payload, seeding from defaults if necessary."""

    with _FILE_LOCK:
        record = _load_raw(draft_id)
        return record.to_response()


def patch_draft(draft_id: str, changes: dict[str, Any]) -> dict[str, Any]:
    """Persist partial updates to a draft and append to the audit log."""

    with _FILE_LOCK:
        record = _load_raw(draft_id)
        draft = record.draft
        if not changes:
            return record.to_response()

        applied = _apply_changes(draft, changes)
        if applied:
            record.history.append(
                {
                    "timestamp": draft["updated_at"],
                    "action": "patch",
                    "payload": deepcopy(changes),
                }
            )
            _write_raw(draft_id, record)
        return record.to_response()


def approve_draft(draft_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Mark a draft as approved and record the action."""

    payload = payload or {}
    with _FILE_LOCK:
        record = _load_raw(draft_id)
        draft = record.draft
        now = _now_iso()
        draft["status"] = "approved"
        draft["approved_at"] = now
        draft["updated_at"] = now
        if "review_notes" in payload and payload["review_notes"] is not None:
            draft["review_notes"] = payload["review_notes"]
        record.history.append(
            {
                "timestamp": now,
                "action": "approve",
                "payload": deepcopy(payload),
            }
        )
        _write_raw(draft_id, record)
        return record.to_response()


def request_reparse(draft_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Flag a draft for re-parsing and update the audit log."""

    payload = payload or {}
    with _FILE_LOCK:
        record = _load_raw(draft_id)
        draft = record.draft
        now = _now_iso()
        draft["status"] = "reparse_requested"
        draft["updated_at"] = now
        if "review_notes" in payload and payload["review_notes"] is not None:
            draft["review_notes"] = payload["review_notes"]
        record.history.append(
            {
                "timestamp": now,
                "action": "reparse",
                "payload": deepcopy(payload),
            }
        )
        _write_raw(draft_id, record)
        return record.to_response()
