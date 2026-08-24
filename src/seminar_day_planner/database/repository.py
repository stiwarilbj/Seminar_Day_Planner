from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from seminar_day_planner.database.models import (
    Assignment,
    Block,
    Event,
    Preference,
    ScheduleRun,
    Seminar,
    SeminarSession,
    Student,
)
from seminar_day_planner.types import EventConfiguration, SeminarImportRow, StudentImportRow


def ensure_default_event(
    session: Session,
    configuration: EventConfiguration | None = None,
) -> Event:
    event = session.scalar(select(Event).where(Event.status == "active").order_by(Event.id))
    if event:
        return event

    config = configuration or EventConfiguration()
    event = Event(
        name=config.name,
        school_name=config.school_name,
        event_date=config.event_date,
        status="active",
        total_blocks=config.total_blocks,
        seminars_per_student=config.seminars_per_student,
        preference_count=config.preference_count,
        lunch_enabled=config.lunch_enabled,
        lunch_block_a=config.lunch_blocks[0],
        lunch_block_b=config.lunch_blocks[1],
    )
    event.blocks = [
        Block(position=position, label=f"Period {position}")
        for position in range(1, config.total_blocks + 1)
    ]
    session.add(event)
    session.flush()
    return event


def get_event_with_blocks(session: Session, event_id: int) -> Event:
    event = session.scalar(
        select(Event)
        .where(Event.id == event_id)
        .options(selectinload(Event.blocks))
    )
    if event is None:
        raise LookupError(f"Event {event_id} does not exist.")
    return event


def upsert_seminar(
    session: Session,
    event_id: int,
    row: SeminarImportRow,
) -> Seminar:
    seminar = session.scalar(
        select(Seminar).where(
            Seminar.event_id == event_id,
            func.lower(Seminar.title) == row.title.casefold(),
        )
    )
    if seminar is None:
        seminar = Seminar(event_id=event_id, title=row.title)
        session.add(seminar)

    seminar.presenter = row.presenter
    seminar.room = row.room
    seminar.description = row.description
    seminar.default_capacity = row.capacity
    seminar.active = True
    session.flush()

    event = get_event_with_blocks(session, event_id)
    blocks_by_position = {block.position: block for block in event.blocks}
    requested_periods = set(row.periods)
    missing_periods = requested_periods.difference(blocks_by_position)
    if missing_periods:
        raise ValueError(f"Unknown periods: {sorted(missing_periods)}")

    existing = {item.block_id: item for item in seminar.sessions}
    requested_block_ids = {blocks_by_position[p].id for p in requested_periods}
    for block_id, session_row in list(existing.items()):
        if block_id not in requested_block_ids:
            session.delete(session_row)
    for period in requested_periods:
        block = blocks_by_position[period]
        session_row = existing.get(block.id)
        if session_row is None:
            session_row = SeminarSession(seminar_id=seminar.id, block_id=block.id)
            session.add(session_row)
        session_row.capacity = row.capacity
    session.flush()
    return seminar


def upsert_student(
    session: Session,
    event_id: int,
    row: StudentImportRow,
) -> Student:
    student = session.scalar(
        select(Student).where(
            Student.event_id == event_id,
            func.lower(Student.email) == str(row.email).casefold(),
        )
    )
    if student is None:
        student = Student(event_id=event_id, email=str(row.email).lower())
        session.add(student)

    student.full_name = row.full_name
    student.email = str(row.email).lower()
    student.grade = row.grade
    student.external_id = row.external_id
    student.submitted_at = row.submitted_at
    student.updated_at = datetime.now(UTC)
    session.flush()

    seminars = session.scalars(
        select(Seminar).where(Seminar.event_id == event_id, Seminar.active.is_(True))
    ).all()
    seminar_by_title = {seminar.title.casefold(): seminar for seminar in seminars}
    unknown = [title for title in row.preferences if title.casefold() not in seminar_by_title]
    if unknown:
        raise ValueError(f"Unknown seminar choices: {', '.join(unknown)}")

    student.preferences.clear()
    session.flush()
    student.preferences.extend(
        Preference(seminar_id=seminar_by_title[title.casefold()].id, rank=rank)
        for rank, title in enumerate(row.preferences, start=1)
    )
    session.flush()
    return student


def event_counts(session: Session, event_id: int) -> dict[str, int]:
    return {
        "students": session.scalar(
            select(func.count(Student.id)).where(Student.event_id == event_id)
        )
        or 0,
        "seminars": session.scalar(
            select(func.count(Seminar.id)).where(
                Seminar.event_id == event_id, Seminar.active.is_(True)
            )
        )
        or 0,
        "preferences": session.scalar(
            select(func.count(Preference.id))
            .join(Student)
            .where(Student.event_id == event_id)
        )
        or 0,
        "sessions": session.scalar(
            select(func.count(SeminarSession.id))
            .join(Seminar)
            .where(Seminar.event_id == event_id)
        )
        or 0,
    }


def list_seminars(session: Session, event_id: int) -> list[dict[str, Any]]:
    seminars = session.scalars(
        select(Seminar)
        .where(Seminar.event_id == event_id, Seminar.active.is_(True))
        .options(selectinload(Seminar.sessions).selectinload(SeminarSession.block))
        .order_by(Seminar.title)
    ).all()
    return [
        {
            "id": seminar.id,
            "title": seminar.title,
            "presenter": seminar.presenter,
            "room": seminar.room,
            "capacity": seminar.default_capacity,
            "periods": sorted(item.block.position for item in seminar.sessions),
            "description": seminar.description,
        }
        for seminar in seminars
    ]


def latest_schedule_run(session: Session, event_id: int) -> ScheduleRun | None:
    return session.scalar(
        select(ScheduleRun)
        .where(ScheduleRun.event_id == event_id)
        .order_by(ScheduleRun.created_at.desc(), ScheduleRun.id.desc())
    )


def schedule_rows(
    session: Session,
    run_id: int,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    assignments = session.scalars(
        select(Assignment)
        .where(Assignment.run_id == run_id)
        .options(
            selectinload(Assignment.student),
            selectinload(Assignment.block),
            selectinload(Assignment.seminar_session).selectinload(
                SeminarSession.seminar
            ),
        )
        .order_by(Assignment.student_id, Assignment.block_id)
    ).all()
    by_student: dict[int, dict[str, Any]] = {}
    for assignment in assignments:
        row = by_student.setdefault(
            assignment.student_id,
            {
                "student_id": assignment.student_id,
                "student": assignment.student.full_name,
                "email": assignment.student.email,
                "grade": assignment.student.grade,
            },
        )
        activity = "Lunch"
        if assignment.activity_type == "seminar" and assignment.seminar_session:
            activity = assignment.seminar_session.seminar.title
        row[f"period_{assignment.block.position}"] = activity
    rows = sorted(by_student.values(), key=lambda item: item["student"].casefold())
    return rows[:limit] if limit is not None else rows


def delete_all_event_data(session: Session, event_id: int) -> None:
    for model in (ScheduleRun, Student, Seminar):
        items: Iterable[Any] = session.scalars(
            select(model).where(model.event_id == event_id)
        ).all()
        for item in items:
            session.delete(item)
    session.flush()

