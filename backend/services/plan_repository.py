"""Persistence utilities for storing plan drafts awaiting teacher review."""
from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import PLAN_DRAFTS_PATH


@dataclass
class PlanDraft:
    """Structured representation of a plan draft awaiting confirmation."""

    id: str
    teacher_id: str
    academic_year: int
    structured_plan: dict[str, Any]
    raw_text: str
    tables: list[dict[str, Any]]
    metadata: dict[str, Any]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PlanDraftRepository:
    """Thread-safe JSON-backed persistence for plan drafts."""

    def __init__(self, storage_path: Path | None = None) -> None:
        self.storage_path = storage_path or PLAN_DRAFTS_PATH
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.storage_path.exists():
            self.storage_path.write_text("[]", encoding="utf-8")
        self._lock = threading.Lock()

    def save(
        self,
        *,
        teacher_id: str,
        academic_year: int,
        structured_plan: dict[str, Any],
        raw_text: str,
        tables: list[dict[str, Any]],
        metadata: dict[str, Any],
    ) -> PlanDraft:
        draft = PlanDraft(
            id=str(uuid.uuid4()),
            teacher_id=teacher_id,
            academic_year=academic_year,
            structured_plan=structured_plan,
            raw_text=raw_text,
            tables=tables,
            metadata=metadata,
            created_at=datetime.now(tz=timezone.utc).isoformat(),
        )
        with self._lock:
            drafts = self._read_all()
            drafts.append(draft.to_dict())
            self._write_all(drafts)
        return draft

    def _read_all(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = []
        return data

    def _write_all(self, items: list[dict[str, Any]]) -> None:
        payload = json.dumps(items, indent=2, ensure_ascii=False)
        self.storage_path.write_text(payload, encoding="utf-8")


__all__ = ["PlanDraft", "PlanDraftRepository"]
