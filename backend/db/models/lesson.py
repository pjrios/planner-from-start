"""Lesson model."""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db import Base


class Lesson(Base):
    """Represents a lesson within a plan unit."""

    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit_id: Mapped[int] = mapped_column(
        ForeignKey("plan_units.id", ondelete="CASCADE"), nullable=False, index=True
    )

    unit: Mapped["PlanUnit"] = relationship("PlanUnit", back_populates="lessons")
    resources: Mapped[list["Resource"]] = relationship(
        "Resource",
        back_populates="lesson",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"Lesson(id={self.id!r}, title={self.title!r})"
