"""Pydantic schemas for planner endpoints."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class ActivityRead(BaseModel):
    id: int
    title: str
    description: str
    provenance: dict[str, Any]
    superseded: bool
    created_at: datetime

    class Config:
        orm_mode = True


class ResourceRead(BaseModel):
    id: int
    name: str
    url: str | None
    type: str | None
    notes: str | None
    provenance: dict[str, Any]
    superseded: bool
    created_at: datetime

    class Config:
        orm_mode = True


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

    class Config:
        orm_mode = True


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

    class Config:
        orm_mode = True


class GenerationRequest(BaseModel):
    topic_ids: list[int] | None = None
    regenerate_all: bool = False
    reason: str = "manual"


class GenerationResponse(BaseModel):
    regenerated_topic_ids: list[int]


class HolidayAdjustmentRequest(BaseModel):
    no_class_dates: list[date]
    reason: str = "No class"


class HolidayAdjustmentResponse(BaseModel):
    inserted_holidays: int
    regenerated_topic_ids: list[int]
