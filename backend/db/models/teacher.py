"""Teacher domain model."""
from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db import Base


class Teacher(Base):
    """Represents an educator who owns academic plans."""

    __tablename__ = "teachers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)

    plans: Mapped[list["AcademicPlan"]] = relationship(
        "AcademicPlan",
        back_populates="teacher",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover - repr not critical
        return f"Teacher(id={self.id!r}, email={self.email!r})"
