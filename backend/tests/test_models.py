from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from backend.db import Base
from backend.db.models import AcademicPlan, Lesson, PlanUnit, Resource, Teacher
from backend.services.academic_plan import (
    LessonData,
    PlanData,
    ResourceData,
    UnitData,
    create_plan,
    create_teacher,
)


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, future=True)
    Base.metadata.create_all(engine)
    with TestingSession() as session:
        yield session
        session.rollback()


def build_sample_plan() -> PlanData:
    return PlanData(
        title="Sample Plan",
        description="A unit for algebra basics.",
        grade_level="7",
        subject="Math",
        units=[
            UnitData(
                title="Expressions",
                position=1,
                lessons=[
                    LessonData(
                        title="Variables and Constants",
                        sequence=1,
                        resources=[
                            ResourceData(name="Lesson Slides", resource_type="slides"),
                            ResourceData(name="Practice Worksheet", resource_type="worksheet"),
                        ],
                    ),
                    LessonData(
                        title="Combining Like Terms",
                        sequence=2,
                        objective="Students simplify algebraic expressions.",
                        resources=[
                            ResourceData(name="Video Overview", resource_type="video"),
                        ],
                    ),
                ],
            ),
            UnitData(
                title="Equations",
                position=2,
                lessons=[
                    LessonData(
                        title="Balancing Equations",
                        sequence=1,
                        resources=[ResourceData(name="Lab Activity", resource_type="activity")],
                    )
                ],
            ),
        ],
    )


def count_rows(session: Session, model: type[Base]) -> int:
    return session.scalar(select(sa.func.count()).select_from(model)) or 0


def test_create_plan_with_nested_structure(session: Session) -> None:
    teacher = create_teacher(session, name="Test Teacher", email="teacher@example.com")
    plan_data = build_sample_plan()
    plan = create_plan(session, teacher=teacher, plan_data=plan_data)

    assert plan.teacher == teacher
    assert len(plan.units) == 2
    assert plan.units[0].lessons[0].resources[0].name == "Lesson Slides"

    plan_from_db = session.scalar(select(AcademicPlan).where(AcademicPlan.id == plan.id))
    assert plan_from_db is not None
    assert plan_from_db.units[0].lessons[0].resources[0].resource_type == "slides"


def test_cascade_delete_plan_removes_children(session: Session) -> None:
    teacher = create_teacher(session, name="Test Teacher", email="cascade@example.com")
    plan = create_plan(session, teacher=teacher, plan_data=build_sample_plan())
    session.flush()

    assert count_rows(session, Resource) > 0
    assert count_rows(session, Lesson) > 0
    assert count_rows(session, PlanUnit) > 0

    session.delete(plan)
    session.flush()

    assert count_rows(session, PlanUnit) == 0
    assert count_rows(session, Lesson) == 0
    assert count_rows(session, Resource) == 0


def test_deleting_teacher_cascades_to_plans(session: Session) -> None:
    teacher = create_teacher(session, name="Cascade Teacher", email="delete@example.com")
    create_plan(session, teacher=teacher, plan_data=build_sample_plan())
    session.flush()

    teacher_id = teacher.id
    session.delete(teacher)
    session.flush()

    assert session.get(Teacher, teacher_id) is None
    assert count_rows(session, AcademicPlan) == 0
