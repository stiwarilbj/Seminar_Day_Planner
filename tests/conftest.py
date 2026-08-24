from __future__ import annotations

from pathlib import Path

import pytest

from seminar_day_planner.database import apply_migrations, create_database_engine


@pytest.fixture
def migrations_root() -> Path:
    return Path(__file__).resolve().parents[1] / "sql" / "migrations"


@pytest.fixture
def engine(tmp_path: Path, migrations_root: Path):
    database_engine = create_database_engine(tmp_path / "test.db")
    apply_migrations(database_engine, migrations_root)
    yield database_engine
    database_engine.dispose()

