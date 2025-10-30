"""Repository and service helpers for the academic planning domain."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import AcademicPlan, Lesson, PlanUnit, Resource, Teacher


@dataclass(slots=True)
class ResourceData:
    name: str
    resource_type: str | None = None
    url: str | None = None
    notes: str | None = None


@dataclass(slots=True)
class LessonData:
    title: str
    sequence: int = 0
    objective: str | None = None
    resources: list[ResourceData] = field(default_factory=list)


@dataclass(slots=True)
class UnitData:
    title: str
    position: int = 0
    summary: str | None = None
    lessons: list[LessonData] = field(default_factory=list)


@dataclass(slots=True)
class PlanData:
    title: str
    description: str | None = None
    grade_level: str | None = None
    subject: str | None = None
    units: list[UnitData] = field(default_factory=list)


def get_teacher_by_email(session: Session, email: str) -> Teacher | None:
    return session.scalar(select(Teacher).where(Teacher.email == email))


def create_teacher(session: Session, name: str, email: str) -> Teacher:
    teacher = Teacher(name=name, email=email)
    session.add(teacher)
    session.flush()
    return teacher


def list_teachers(session: Session) -> Sequence[Teacher]:
    return session.scalars(select(Teacher).order_by(Teacher.name)).all()


def _synchronise_resources(lesson: Lesson, resource_data: Iterable[ResourceData]) -> None:
    existing_by_key = {resource.name: resource for resource in lesson.resources}
    incoming_names = set()
    for data in resource_data:
        incoming_names.add(data.name)
        resource = existing_by_key.get(data.name)
        if resource is None:
            resource = Resource(name=data.name)
            lesson.resources.append(resource)
        resource.resource_type = data.resource_type
        resource.url = data.url
        resource.notes = data.notes

    lesson.resources = [r for r in lesson.resources if r.name in incoming_names]


def _synchronise_lessons(unit: PlanUnit, lesson_data: Iterable[LessonData]) -> None:
    existing_by_title = {lesson.title: lesson for lesson in unit.lessons}
    incoming_titles = set()
    for data in lesson_data:
        incoming_titles.add(data.title)
        lesson = existing_by_title.get(data.title)
        if lesson is None:
            lesson = Lesson(title=data.title)
            unit.lessons.append(lesson)
        lesson.sequence = data.sequence
        lesson.objective = data.objective
        _synchronise_resources(lesson, data.resources)

    unit.lessons = [lesson for lesson in unit.lessons if lesson.title in incoming_titles]


def _synchronise_units(plan: AcademicPlan, unit_data: Iterable[UnitData]) -> None:
    existing_by_title = {unit.title: unit for unit in plan.units}
    incoming_titles = set()
    for data in unit_data:
        incoming_titles.add(data.title)
        unit = existing_by_title.get(data.title)
        if unit is None:
            unit = PlanUnit(title=data.title)
            plan.units.append(unit)
        unit.position = data.position
        unit.summary = data.summary
        _synchronise_lessons(unit, data.lessons)

    plan.units = [unit for unit in plan.units if unit.title in incoming_titles]


def create_plan(session: Session, teacher: Teacher, plan_data: PlanData) -> AcademicPlan:
    plan = AcademicPlan(
        title=plan_data.title,
        description=plan_data.description,
        grade_level=plan_data.grade_level,
        subject=plan_data.subject,
        teacher=teacher,
    )
    session.add(plan)
    session.flush()
    _synchronise_units(plan, plan_data.units)
    session.flush()
    return plan


def update_plan(session: Session, plan: AcademicPlan, plan_data: PlanData) -> AcademicPlan:
    plan.title = plan_data.title
    plan.description = plan_data.description
    plan.grade_level = plan_data.grade_level
    plan.subject = plan_data.subject
    _synchronise_units(plan, plan_data.units)
    session.flush()
    return plan


def get_plan_by_id(session: Session, plan_id: int) -> AcademicPlan | None:
    return session.get(AcademicPlan, plan_id)


def list_plans_for_teacher(session: Session, teacher: Teacher) -> Sequence[AcademicPlan]:
    stmt = (
        select(AcademicPlan)
        .where(AcademicPlan.teacher_id == teacher.id)
        .order_by(AcademicPlan.title)
    )
    return session.scalars(stmt).all()


def delete_plan(session: Session, plan: AcademicPlan) -> None:
    session.delete(plan)
    session.flush()
