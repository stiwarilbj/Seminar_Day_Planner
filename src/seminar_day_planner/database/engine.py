from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def create_database_engine(database: Path | str) -> Engine:
    if isinstance(database, Path):
        database.parent.mkdir(parents=True, exist_ok=True)
        url = f"sqlite+pysqlite:///{database}"
    else:
        url = database

    options: dict = {"future": True}
    if url in {"sqlite://", "sqlite:///:memory:", "sqlite+pysqlite:///:memory:"}:
        options["poolclass"] = StaticPool
        options["connect_args"] = {"check_same_thread": False}
    else:
        options["connect_args"] = {"check_same_thread": False}

    engine = create_engine(url, **options)

    @event.listens_for(engine, "connect")
    def configure_sqlite_connection(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA busy_timeout = 5000")
        if ":memory:" not in url:
            cursor.execute("PRAGMA journal_mode = WAL")
        cursor.close()

    return engine


def apply_migrations(engine: Engine, migrations_root: Path) -> list[str]:
    migration_paths = sorted(migrations_root.glob("*.sql"))
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        applied = {
            row[0]
            for row in connection.execute(text("SELECT version FROM schema_migrations"))
        }

    newly_applied: list[str] = []
    for migration_path in migration_paths:
        version = migration_path.stem
        if version in applied:
            continue
        raw_connection = engine.raw_connection()
        try:
            script = migration_path.read_text(encoding="utf-8")
            escaped_version = version.replace("'", "''")
            raw_connection.executescript(
                "BEGIN IMMEDIATE;\n"
                + script
                + f"\nINSERT INTO schema_migrations(version) VALUES ('{escaped_version}');\n"
                + "COMMIT;"
            )
            newly_applied.append(version)
        except Exception:
            raw_connection.rollback()
            raise
        finally:
            raw_connection.close()
    return newly_applied


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

