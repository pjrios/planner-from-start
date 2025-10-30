"""Development fixture helpers."""
from __future__ import annotations

from sqlalchemy.orm import Session

from backend.services.academic_plan import (
    LessonData,
    PlanData,
    ResourceData,
    UnitData,
    create_plan,
    create_teacher,
    get_teacher_by_email,
)


def seed_dev_data(session: Session) -> None:
    """Populate the database with a demo teacher and sample academic plan."""
    teacher = get_teacher_by_email(session, "demo.teacher@example.com")
    if teacher is None:
        teacher = create_teacher(session, name="Demo Teacher", email="demo.teacher@example.com")

    if not teacher.plans:
        plan = PlanData(
            title="Introduction to Climate Science",
            description="A three-week plan exploring climate systems and change.",
            grade_level="8",
            subject="Science",
            units=[
                UnitData(
                    title="Earth's Atmosphere",
                    position=1,
                    summary="Understand composition and layers of the atmosphere.",
                    lessons=[
                        LessonData(
                            title="Layers of the Atmosphere",
                            sequence=1,
                            objective="Identify characteristics of atmospheric layers.",
                            resources=[
                                ResourceData(
                                    name="NASA Atmosphere Overview",
                                    resource_type="article",
                                    url="https://climate.nasa.gov/",
                                ),
                                ResourceData(
                                    name="Interactive Layer Diagram",
                                    resource_type="activity",
                                ),
                            ],
                        ),
                        LessonData(
                            title="Weather vs Climate",
                            sequence=2,
                            objective="Differentiate between weather and climate trends.",
                            resources=[
                                ResourceData(
                                    name="Climate Graph Worksheet",
                                    resource_type="worksheet",
                                )
                            ],
                        ),
                    ],
                ),
                UnitData(
                    title="Climate Change Impacts",
                    position=2,
                    summary="Explore impacts of climate change on ecosystems.",
                    lessons=[
                        LessonData(
                            title="Evidence of Climate Change",
                            sequence=1,
                            objective="Analyze global temperature datasets.",
                            resources=[
                                ResourceData(name="NOAA Data Portal", resource_type="dataset"),
                                ResourceData(
                                    name="Graphing Template",
                                    resource_type="template",
                                ),
                            ],
                        )
                    ],
                ),
            ],
        )
        create_plan(session, teacher=teacher, plan_data=plan)

    session.flush()
