from __future__ import annotations

from datetime import UTC, datetime, timedelta

from seminar_day_planner.database import session_scope
from seminar_day_planner.database.repository import (
    ensure_default_event,
    upsert_seminar,
    upsert_student,
)
from seminar_day_planner.scheduling.solver import (
    generate_and_persist_schedule,
    validate_schedule,
)
from seminar_day_planner.types import SchedulingConfiguration, SeminarImportRow, StudentImportRow


def seed_small_problem(engine, student_count: int = 8) -> int:
    titles = ["Robotics Lab", "Film Scoring", "Climate Science", "Mock Trial"]
    with session_scope(engine) as session:
        event = ensure_default_event(session)
        for index, title in enumerate(titles):
            upsert_seminar(
                session,
                event.id,
                SeminarImportRow(
                    title=title,
                    presenter=f"Presenter {index}",
                    room=f"Room {index}",
                    capacity=4,
                    periods=[1, 2, 3, 4],
                ),
            )
        base = datetime(2026, 8, 1, tzinfo=UTC)
        for index in range(student_count):
            choices = titles[index % len(titles) :] + titles[: index % len(titles)]
            upsert_student(
                session,
                event.id,
                StudentImportRow(
                    full_name=f"Student {index}",
                    email=f"student{index}@example.test",
                    grade=9 + index % 4,
                    preferences=choices,
                    submitted_at=base + timedelta(minutes=index),
                ),
            )
        return event.id


def test_solver_respects_every_hard_constraint(engine) -> None:
    event_id = seed_small_problem(engine)
    run_id, result = generate_and_persist_schedule(
        engine,
        event_id,
        SchedulingConfiguration(event_id=event_id, time_limit_seconds=10),
    )
    assert result.status in {"optimal", "feasible"}
    assert len(result.assignments) == 8 * 4
    assert result.satisfaction["lunch_block_2"] == 4
    assert result.satisfaction["lunch_block_3"] == 4
    with session_scope(engine) as session:
        assert validate_schedule(session, run_id) == []


def test_preflight_reports_insufficient_capacity(engine) -> None:
    event_id = seed_small_problem(engine, student_count=20)
    _run_id, result = generate_and_persist_schedule(
        engine,
        event_id,
        SchedulingConfiguration(
            event_id=event_id,
            maximum_seminar_size=1,
            time_limit_seconds=3,
        ),
    )
    assert result.status == "invalid"
    assert any("needs" in error and "seats" in error for error in result.diagnostics.errors)

