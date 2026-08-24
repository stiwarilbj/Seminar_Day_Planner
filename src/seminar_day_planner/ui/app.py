from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Engine

from seminar_day_planner.config import Settings


@dataclass(frozen=True, slots=True)
class ApplicationContext:
    settings: Settings
    engine: Engine
    event_id: int


def register_pages(context: ApplicationContext) -> None:
    from seminar_day_planner.ui.pages.builder import register_builder_page
    from seminar_day_planner.ui.pages.imports import register_imports_page
    from seminar_day_planner.ui.pages.login import register_login_page
    from seminar_day_planner.ui.pages.overview import register_overview_page
    from seminar_day_planner.ui.pages.results import register_results_page
    from seminar_day_planner.ui.pages.seminars import register_seminars_page
    from seminar_day_planner.ui.pages.submit import register_submit_page

    register_login_page(context)
    register_submit_page(context)
    register_overview_page(context)
    register_imports_page(context)
    register_seminars_page(context)
    register_builder_page(context)
    register_results_page(context)

