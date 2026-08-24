from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    school_name: Mapped[str] = mapped_column(String(160))
    event_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    total_blocks: Mapped[int] = mapped_column(Integer, default=4)
    seminars_per_student: Mapped[int] = mapped_column(Integer, default=3)
    preference_count: Mapped[int] = mapped_column(Integer, default=6)
    lunch_enabled: Mapped[bool] = mapped_column(default=True)
    lunch_block_a: Mapped[int] = mapped_column(Integer, default=2)
    lunch_block_b: Mapped[int] = mapped_column(Integer, default=3)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    blocks: Mapped[list[Block]] = relationship(
        back_populates="event", cascade="all, delete-orphan", order_by="Block.position"
    )


class Block(Base):
    __tablename__ = "blocks"
    __table_args__ = (UniqueConstraint("event_id", "position"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(80))

    event: Mapped[Event] = relationship(back_populates="blocks")


class Student(Base):
    __tablename__ = "students"
    __table_args__ = (UniqueConstraint("event_id", "email"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    external_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254))
    grade: Mapped[int] = mapped_column(Integer)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    preferences: Mapped[list[Preference]] = relationship(
        back_populates="student", cascade="all, delete-orphan", order_by="Preference.rank"
    )


class Seminar(Base):
    __tablename__ = "seminars"
    __table_args__ = (UniqueConstraint("event_id", "title"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(160))
    presenter: Mapped[str] = mapped_column(String(120))
    room: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text, default="")
    default_capacity: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    sessions: Mapped[list[SeminarSession]] = relationship(
        back_populates="seminar", cascade="all, delete-orphan"
    )


class SeminarSession(Base):
    __tablename__ = "seminar_sessions"
    __table_args__ = (UniqueConstraint("seminar_id", "block_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    seminar_id: Mapped[int] = mapped_column(ForeignKey("seminars.id", ondelete="CASCADE"))
    block_id: Mapped[int] = mapped_column(ForeignKey("blocks.id", ondelete="CASCADE"))
    capacity: Mapped[int] = mapped_column(Integer)

    seminar: Mapped[Seminar] = relationship(back_populates="sessions")
    block: Mapped[Block] = relationship()


class Preference(Base):
    __tablename__ = "preferences"
    __table_args__ = (
        UniqueConstraint("student_id", "rank"),
        UniqueConstraint("student_id", "seminar_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    seminar_id: Mapped[int] = mapped_column(ForeignKey("seminars.id", ondelete="CASCADE"))
    rank: Mapped[int] = mapped_column(Integer)

    student: Mapped[Student] = relationship(back_populates="preferences")
    seminar: Mapped[Seminar] = relationship()


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    source_type: Mapped[str] = mapped_column(String(30))
    target_type: Mapped[str] = mapped_column(String(20))
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="staged")
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    rows: Mapped[list[ImportRow]] = relationship(
        back_populates="batch", cascade="all, delete-orphan", order_by="ImportRow.row_number"
    )


class ImportRow(Base):
    __tablename__ = "import_rows"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("import_batches.id", ondelete="CASCADE")
    )
    row_number: Mapped[int] = mapped_column(Integer)
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSON)
    normalized_data: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20))
    messages: Mapped[list[str]] = mapped_column(JSON, default=list)

    batch: Mapped[ImportBatch] = relationship(back_populates="rows")


class ScheduleRun(Base):
    __tablename__ = "schedule_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20))
    solver_status: Mapped[str] = mapped_column(String(40))
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON)
    satisfaction: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    diagnostics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    objective_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    random_seed: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    assignments: Mapped[list[Assignment]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class Assignment(Base):
    __tablename__ = "assignments"
    __table_args__ = (
        UniqueConstraint("run_id", "student_id", "block_id"),
        CheckConstraint("activity_type IN ('seminar', 'lunch')"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("schedule_runs.id", ondelete="CASCADE"))
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    block_id: Mapped[int] = mapped_column(ForeignKey("blocks.id", ondelete="CASCADE"))
    activity_type: Mapped[str] = mapped_column(String(20))
    seminar_session_id: Mapped[int | None] = mapped_column(
        ForeignKey("seminar_sessions.id", ondelete="RESTRICT"), nullable=True
    )
    preference_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)

    run: Mapped[ScheduleRun] = relationship(back_populates="assignments")
    student: Mapped[Student] = relationship()
    block: Mapped[Block] = relationship()
    seminar_session: Mapped[SeminarSession | None] = relationship()

