from __future__ import annotations

import argparse

from nicegui import ui

from seminar_day_planner.config import Settings
from seminar_day_planner.database import apply_migrations, create_database_engine, session_scope
from seminar_day_planner.database.repository import ensure_default_event
from seminar_day_planner.demo import seed_demo_data
from seminar_day_planner.ui import ApplicationContext, register_pages


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Seminar Day Planner.")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Load the deterministic fictional demo dataset before starting.",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Start the server without opening a browser window.",
    )
    parser.add_argument("--host", help="Override HOST from .env.")
    parser.add_argument("--port", type=int, help="Override PORT from .env.")
    return parser


def main() -> None:
    arguments = build_argument_parser().parse_args()
    settings = Settings.from_environment()
    if arguments.host or arguments.port:
        settings = Settings(
            **{
                **{field: getattr(settings, field) for field in settings.__dataclass_fields__},
                "host": arguments.host or settings.host,
                "port": arguments.port or settings.port,
            }
        )
    settings.prepare_runtime_directories()
    settings.validate_for_startup()
    engine = create_database_engine(settings.database_path)
    apply_migrations(engine, settings.migrations_root)
    with session_scope(engine) as session:
        event = ensure_default_event(session)
        event_id = event.id
        if arguments.demo:
            event_id = seed_demo_data(session)

    register_pages(ApplicationContext(settings=settings, engine=engine, event_id=event_id))
    ui.run(
        title="Seminar Day Planner",
        host=settings.host,
        port=settings.port,
        storage_secret=settings.session_secret,
        reload=False,
        show=not arguments.no_browser,
        favicon="📘",
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()

