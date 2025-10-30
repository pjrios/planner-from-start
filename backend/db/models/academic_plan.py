"""Academic plan model."""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db import Base


class AcademicPlan(Base):
    """High-level instructional plan owned by a teacher."""

    __tablename__ = "academic_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    grade_level: Mapped[str | None] = mapped_column(String(64), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(128), nullable=True)
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True
    )

    teacher: Mapped["Teacher"] = relationship("Teacher", back_populates="plans")
    units: Mapped[list["PlanUnit"]] = relationship(
        "PlanUnit",
        back_populates="plan",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="PlanUnit.position",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"AcademicPlan(id={self.id!r}, title={self.title!r})"
