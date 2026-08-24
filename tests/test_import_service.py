from __future__ import annotations

import pytest
from sqlalchemy import func, select

from seminar_day_planner.database import session_scope
from seminar_day_planner.database.models import Student
from seminar_day_planner.database.repository import ensure_default_event, upsert_seminar
from seminar_day_planner.ingestion.parsers import parse_natural_language
from seminar_day_planner.ingestion.service import confirm_import_batch, stage_import_batch
from seminar_day_planner.types import SeminarImportRow


def test_confirmed_import_updates_matching_email(engine) -> None:
    with session_scope(engine) as session:
        event = ensure_default_event(session)
        upsert_seminar(
            session,
            event.id,
            SeminarImportRow(
                title="Robotics Lab",
                presenter="Mr. Harris",
                room="201",
                capacity=12,
                periods=[1, 2, 3, 4],
            ),
        )
        event_id = event.id

    first = parse_natural_language(
        "Maya Anderson, grade 12, maya@example.test, wants Robotics Lab",
        "student",
        ["Robotics Lab"],
    )
    with session_scope(engine) as session:
        batch = stage_import_batch(session, event_id, first)
        batch_id = batch.id
    with session_scope(engine) as session:
        assert confirm_import_batch(session, batch_id) == (1, 0)

    updated = parse_natural_language(
        "Maya Anderson, grade 11, maya@example.test, wants Robotics Lab",
        "student",
        ["Robotics Lab"],
    )
    with session_scope(engine) as session:
        batch = stage_import_batch(session, event_id, updated)
        batch_id = batch.id
    with session_scope(engine) as session:
        confirm_import_batch(session, batch_id)
        assert session.scalar(select(func.count(Student.id))) == 1
        assert session.scalar(select(Student.grade)) == 11


def test_error_rows_cannot_be_confirmed(engine) -> None:
    with session_scope(engine) as session:
        event_id = ensure_default_event(session).id
    preview = parse_natural_language(
        "Maya Anderson, grade 12, wants Robotics Lab",
        "student",
        ["Robotics Lab"],
    )
    with session_scope(engine) as session:
        batch_id = stage_import_batch(session, event_id, preview).id
    with session_scope(engine) as session, pytest.raises(ValueError):
        confirm_import_batch(session, batch_id)

