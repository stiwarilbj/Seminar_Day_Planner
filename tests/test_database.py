from __future__ import annotations

from sqlalchemy import text

from seminar_day_planner.database import apply_migrations, session_scope
from seminar_day_planner.database.repository import ensure_default_event


def test_migrations_are_idempotent(engine, migrations_root) -> None:
    assert apply_migrations(engine, migrations_root) == []
    with engine.connect() as connection:
        versions = connection.execute(text("SELECT version FROM schema_migrations")).scalars().all()
    assert versions == ["001_initial"]


def test_foreign_keys_are_enabled(engine) -> None:
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1


def test_default_event_has_four_blocks(engine) -> None:
    with session_scope(engine) as session:
        event = ensure_default_event(session)
        assert event.total_blocks == 4
        assert [block.position for block in event.blocks] == [1, 2, 3, 4]

