"""Initial academic planning schema."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20240605_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "teachers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_teachers_email"),
    )
    op.create_index(op.f("ix_teachers_email"), "teachers", ["email"], unique=True)

    op.create_table(
        "academic_plans",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("grade_level", sa.String(length=64), nullable=True),
        sa.Column("subject", sa.String(length=128), nullable=True),
        sa.Column("teacher_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_academic_plans_teacher_id"), "academic_plans", ["teacher_id"], unique=False)

    op.create_table(
        "plan_units",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["academic_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_plan_units_plan_id"), "plan_units", ["plan_id"], unique=False)

    op.create_table(
        "lessons",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("objective", sa.Text(), nullable=True),
        sa.Column("unit_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["unit_id"], ["plan_units.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_lessons_unit_id"), "lessons", ["unit_id"], unique=False)

    op.create_table(
        "resources",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=True),
        sa.Column("url", sa.String(length=512), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("lesson_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["lesson_id"], ["lessons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_resources_lesson_id"), "resources", ["lesson_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_resources_lesson_id"), table_name="resources")
    op.drop_table("resources")
    op.drop_index(op.f("ix_lessons_unit_id"), table_name="lessons")
    op.drop_table("lessons")
    op.drop_index(op.f("ix_plan_units_plan_id"), table_name="plan_units")
    op.drop_table("plan_units")
    op.drop_index(op.f("ix_academic_plans_teacher_id"), table_name="academic_plans")
    op.drop_table("academic_plans")
    op.drop_index(op.f("ix_teachers_email"), table_name="teachers")
    op.drop_table("teachers")
