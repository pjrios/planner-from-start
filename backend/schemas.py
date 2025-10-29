"""Pydantic schemas shared across API endpoints."""

from datetime import date as Date, time as Time
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


class LevelCreate(BaseModel):
    name: str = Field(..., min_length=1)
    start_date: Date


class LevelResponse(BaseModel):
    id: int
    name: str
    start_date: Date

    model_config = ConfigDict(from_attributes=True)


class ScheduleSlot(BaseModel):
    weekday: int = Field(..., ge=0, le=6)
    start_time: Time
    end_time: Optional[Time] = None

    @field_validator("end_time")
    @classmethod
    def validate_end_time(cls, value: Optional[Time], info: ValidationInfo) -> Optional[Time]:
        start = info.data.get("start_time")
        if value is not None and isinstance(start, Time) and value <= start:
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
    date: Date
    start_time: Time
    end_time: Optional[Time] = None
    topic: str
    trimester_color: Optional[str] = None
    status: str
    manual_override: bool

    model_config = ConfigDict(from_attributes=True)


class ClassUpdate(BaseModel):
    date: Optional[Date] = None
    start_time: Optional[Time] = None
    end_time: Optional[Time] = None
    week_number: Optional[int] = Field(default=None, gt=0)
    topic: Optional[str] = None
    trimester_color: Optional[str] = None
    status: Optional[str] = None

    @field_validator("end_time")
    @classmethod
    def validate_patch_end_time(
        cls, value: Optional[Time], info: ValidationInfo
    ) -> Optional[Time]:
        start = info.data.get("start_time")
        if value is not None and isinstance(start, Time) and value <= start:
            raise ValueError("end_time must be later than start_time")
        return value

    def ensure_any_field(self) -> None:
        if not self.model_dump(exclude_none=True):
            raise ValueError("At least one field must be provided for update")


class AgendaResponse(BaseModel):
    level_id: int
    week: int
    classes: List[ClassResponse]


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
