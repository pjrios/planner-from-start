"""Pydantic schemas shared across the planner backend."""
from __future__ import annotations

from datetime import date, datetime, time
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


# ---------------------------------------------------------------------------
# Scheduling primitives
# ---------------------------------------------------------------------------


class ScheduleSlot(BaseModel):
    weekday: int = Field(..., ge=0, le=6)
    start_time: time
    end_time: Optional[time] = None

    @field_validator("end_time")
    @classmethod
    def validate_end_time(cls, value: Optional[time], info: ValidationInfo) -> Optional[time]:
        start = info.data.get("start_time")
        if value is not None and isinstance(start, time) and value <= start:
            raise ValueError("end_time must be later than start_time")
        return value


class ScheduleSlotResponse(ScheduleSlot):
    id: int

    model_config = ConfigDict(from_attributes=True)


class GroupCreate(BaseModel):
    name: str = Field(..., min_length=1)
    schedule: List[ScheduleSlot] = Field(default_factory=list)


class GroupResponse(BaseModel):
    id: int
    name: str
    level_id: int
    schedule: List[ScheduleSlotResponse]

    model_config = ConfigDict(from_attributes=True)


class GroupSummary(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class ClassResponse(BaseModel):
    id: int
    group: GroupSummary
    week_number: int
    date: date
    start_time: time
    end_time: Optional[time] = None
    topic: str
    trimester_color: Optional[str] = None
    status: str
    manual_override: bool
    suggestions: List["ReschedulingSuggestion"] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ClassUpdate(BaseModel):
    date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    week_number: Optional[int] = Field(default=None, gt=0)
    topic: Optional[str] = None
    trimester_color: Optional[str] = None
    status: Optional[str] = None

    @field_validator("end_time")
    @classmethod
    def validate_patch_end_time(
        cls, value: Optional[time], info: ValidationInfo
    ) -> Optional[time]:
        start = info.data.get("start_time")
        if value is not None and isinstance(start, time) and value <= start:
            raise ValueError("end_time must be later than start_time")
        return value

    def ensure_any_field(self) -> None:
        if not self.model_dump(exclude_none=True):
            raise ValueError("At least one field must be provided for update")


class AgendaResponse(BaseModel):
    level_id: int
    week: int
    classes: List[ClassResponse]


# ---------------------------------------------------------------------------
# Planner ingestion payloads
# ---------------------------------------------------------------------------


class PlanTopic(BaseModel):
    group_id: int
    topic: str = Field(..., min_length=1)
    trimester_color: Optional[str] = None


class PlanWeek(BaseModel):
    week_number: int = Field(..., gt=0)
    topics: List[PlanTopic] = Field(default_factory=list)


class PlanPayload(BaseModel):
    level_id: int
    weeks: List[PlanWeek] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Vector search API
# ---------------------------------------------------------------------------


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    n_results: int = Field(5, ge=1, le=50)


class QueryResult(BaseModel):
    document: str
    metadata: dict[str, str]
    distance: float | None = None


class QueryResponse(BaseModel):
    query: str
    results: list[QueryResult]


# ---------------------------------------------------------------------------
# Plan review flows
# ---------------------------------------------------------------------------


class PlanAuditEntry(BaseModel):
    timestamp: datetime
    action: str
    payload: dict[str, Any] | None = None


class Trimester(BaseModel):
    id: str
    name: str
    start_date: date
    end_date: date


class PlanLevel(BaseModel):
    id: str
    name: str
    description: str | None = None


class PlanTopicSummary(BaseModel):
    id: str
    name: str
    trimester_id: str
    level_id: str
    summary: str | None = None


class PlanDraft(BaseModel):
    id: str
    title: str
    summary: str | None = None
    status: str
    review_notes: str | None = None
    trimesters: list[Trimester]
    levels: list[PlanLevel]
    topics: list[PlanTopicSummary]
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None = None
    history: list[PlanAuditEntry] = Field(default_factory=list)


class PlanPatchRequest(BaseModel):
    title: str | None = None
    summary: str | None = None
    status: str | None = None
    review_notes: str | None = None
    trimesters: list[Trimester] | None = None
    levels: list[PlanLevel] | None = None
    topics: list[PlanTopicSummary] | None = None


class ReviewActionRequest(BaseModel):
    review_notes: str | None = None


# ---------------------------------------------------------------------------
# Holiday and academic year helpers
# ---------------------------------------------------------------------------


class ReschedulingSuggestion(BaseModel):
    id: int
    class_id: int
    holiday_id: int
    suggestion: str
    class_name: str | None = None
    scheduled_date: date | None = None


class HolidayBase(BaseModel):
    name: str = Field(..., min_length=1)
    start_date: date
    end_date: date
    academic_year_id: int

    @field_validator("end_date")
    @classmethod
    def validate_date_range(cls, end_date: date, info: ValidationInfo) -> date:
        start = info.data.get("start_date")
        if isinstance(start, date) and end_date < start:
            raise ValueError("end_date must be on or after start_date")
        return end_date


class HolidayCreate(HolidayBase):
    pass


class HolidayUpdate(HolidayBase):
    pass


class HolidayResponse(BaseModel):
    id: int
    name: str
    start_date: date
    end_date: date
    academic_year_id: int
    suggestions: list[ReschedulingSuggestion] = Field(default_factory=list)


class LevelCreate(BaseModel):
    name: str = Field(..., min_length=1)
    start_date: date


class LevelResponse(BaseModel):
    id: int
    name: str
    start_date: date


class AcademicYearResponse(BaseModel):
    id: int
    name: str
    start_date: date
    end_date: date


# ---------------------------------------------------------------------------
# AI-assisted class planning schemas
# ---------------------------------------------------------------------------


class ActivityRead(BaseModel):
    id: int
    title: str
    description: str
    provenance: dict[str, Any]
    superseded: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResourceRead(BaseModel):
    id: int
    name: str
    url: str | None
    type: str | None
    notes: str | None
    provenance: dict[str, Any]
    superseded: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TopicBase(BaseModel):
    title: str
    description: str | None = None
    scheduled_date: date


class TopicCreate(TopicBase):
    pass


class TopicRead(TopicBase):
    id: int
    position: int
    is_holiday: bool
    holiday_reason: str | None
    last_generated_at: datetime | None
    activities: list[ActivityRead]
    resources: list[ResourceRead]

    model_config = ConfigDict(from_attributes=True)


class ClassScheduleCreate(BaseModel):
    name: str
    subject: str | None = None
    grade_level: str | None = None
    start_date: date
    topics: list[TopicCreate] = Field(default_factory=list)


class ClassScheduleRead(BaseModel):
    id: int
    name: str
    subject: str | None
    grade_level: str | None
    start_date: date
    topics: list[TopicRead]

    model_config = ConfigDict(from_attributes=True)


class GenerationRequest(BaseModel):
    topic_ids: list[int] | None = None
    regenerate_all: bool = False
    reason: str = Field(default="manual")


class GenerationResponse(BaseModel):
    regenerated_topic_ids: list[int]


class HolidayAdjustmentRequest(BaseModel):
    no_class_dates: list[date] = Field(default_factory=list)
    reason: str = Field(default="Holiday")


class HolidayAdjustmentResponse(BaseModel):
    inserted_holidays: int
    regenerated_topic_ids: list[int]


__all__ = [
    "ActivityRead",
    "AgendaResponse",
    "AcademicYearResponse",
    "ClassResponse",
    "ClassScheduleCreate",
    "ClassScheduleRead",
    "ClassUpdate",
    "GenerationRequest",
    "GenerationResponse",
    "GroupCreate",
    "GroupResponse",
    "GroupSummary",
    "HolidayAdjustmentRequest",
    "HolidayAdjustmentResponse",
    "HolidayCreate",
    "HolidayResponse",
    "HolidayUpdate",
    "LevelCreate",
    "LevelResponse",
    "PlanAuditEntry",
    "PlanDraft",
    "PlanLevel",
    "PlanPatchRequest",
    "PlanPayload",
    "PlanTopic",
    "PlanTopicSummary",
    "PlanWeek",
    "QueryRequest",
    "QueryResponse",
    "QueryResult",
    "ReschedulingSuggestion",
    "ReviewActionRequest",
    "ScheduleSlot",
    "ScheduleSlotResponse",
    "TopicCreate",
    "TopicRead",
    "Trimester",
]
