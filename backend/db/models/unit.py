"""Instructional unit model."""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db import Base


class PlanUnit(Base):
    """Represents a thematic unit within an academic plan."""

    __tablename__ = "plan_units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("academic_plans.id", ondelete="CASCADE"), nullable=False, index=True
    )

    plan: Mapped["AcademicPlan"] = relationship("AcademicPlan", back_populates="units")
    lessons: Mapped[list["Lesson"]] = relationship(
        "Lesson",
        back_populates="unit",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Lesson.sequence",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"PlanUnit(id={self.id!r}, title={self.title!r})"
