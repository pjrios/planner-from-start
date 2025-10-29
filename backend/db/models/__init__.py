"""SQLAlchemy model package."""
from backend.db.models.academic_plan import AcademicPlan
from backend.db.models.lesson import Lesson
from backend.db.models.resource import Resource
from backend.db.models.teacher import Teacher
from backend.db.models.unit import PlanUnit

__all__ = [
    "AcademicPlan",
    "Lesson",
    "PlanUnit",
    "Resource",
    "Teacher",
]
