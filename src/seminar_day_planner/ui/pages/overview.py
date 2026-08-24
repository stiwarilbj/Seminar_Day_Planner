from __future__ import annotations

from nicegui import ui

from seminar_day_planner.database.engine import session_scope
from seminar_day_planner.database.repository import (
    event_counts,
    latest_schedule_run,
    list_seminars,
)
from seminar_day_planner.ui.app import ApplicationContext
from seminar_day_planner.ui.theme import metric_strip, require_staff, staff_shell


def register_overview_page(context: ApplicationContext) -> None:
    @ui.page("/staff/overview")
    def overview() -> None:
        if not require_staff():
            return
        with session_scope(context.engine) as session:
            counts = event_counts(session, context.event_id)
            seminars = list_seminars(session, context.event_id)
            latest = latest_schedule_run(session, context.event_id)

        def actions() -> None:
            ui.button(
                "Open student form",
                icon="open_in_new",
                on_click=lambda: ui.navigate.to("/submit", new_tab=True),
            ).props("no-caps unelevated").classes("secondary-btn")
            ui.button(
                "Build schedule",
                icon="calendar_month",
                on_click=lambda: ui.navigate.to("/staff/builder"),
            ).props("no-caps unelevated").classes("primary-btn")

        with staff_shell(
            "overview",
            "Seminar Day at a glance",
            "See what is ready and what still needs attention.",
            actions,
        ):
            metric_strip(counts["students"], counts["seminars"])
            with ui.element("div").classes("overview-grid"):
                with ui.column().classes("open-surface section-pad gap-4"):
                    ui.label("Planning checklist").classes("section-title")
                    checks = (
                        (
                            counts["students"] > 0,
                            "Student preferences",
                            f"{counts['students']} student records are ready.",
                            "/staff/imports",
                        ),
                        (
                            counts["seminars"] > 0,
                            "Seminar offerings",
                            f"{counts['seminars']} seminars and {counts['sessions']} sessions are configured.",
                            "/staff/seminars",
                        ),
                        (
                            latest is not None and latest.status in {"optimal", "feasible"},
                            "Generated schedule",
                            (
                                f"Run {latest.id} is ready to review."
                                if latest
                                else "Generate the first schedule when the data is ready."
                            ),
                            "/staff/builder",
                        ),
                    )
                    for ready, title, copy, route in checks:
                        with ui.row().classes(
                            "w-full items-center gap-3 py-3 border-b border-[#dbe8f5] last:border-0"
                        ):
                            ui.icon(
                                "check_circle" if ready else "radio_button_unchecked",
                                size="21px",
                            ).classes("status-ok" if ready else "text-[#9aabc2]")
                            with ui.column().classes("gap-0 flex-1"):
                                ui.label(title).classes("text-[13px] font-bold")
                                ui.label(copy).classes("section-copy")
                            ui.button(
                                icon="arrow_forward",
                                on_click=lambda route=route: ui.navigate.to(route),
                            ).props("flat round dense aria-label='Open section'").classes(
                                "text-[#0864e8]"
                            )

                with ui.column().classes("open-surface section-pad gap-4"):
                    ui.label("Today’s setup").classes("section-title")
                    setup_rows = (
                        ("Period plan", "Four total periods"),
                        ("Student schedule", "Three seminars and one lunch"),
                        ("Lunch pattern", "Balanced between periods 2 and 3"),
                        ("Data storage", "Local SQLite database"),
                    )
                    for label, value in setup_rows:
                        with ui.row().classes("w-full justify-between gap-4 py-2"):
                            ui.label(label).classes("section-copy")
                            ui.label(value).classes("text-[12px] font-semibold text-right")
                    ui.separator().classes("bg-[#cddff5]")
                    if latest:
                        ui.label("Latest run").classes("field-label")
                        with ui.row().classes("items-center gap-2"):
                            ui.icon(
                                "check_circle" if latest.status in {"optimal", "feasible"} else "warning",
                                size="19px",
                            ).classes(
                                "status-ok" if latest.status in {"optimal", "feasible"} else "status-warning"
                            )
                            ui.label(f"Run {latest.id}: {latest.status.title()}").classes(
                                "text-[13px] font-semibold"
                            )
                        ui.button(
                            "Review results",
                            icon="bar_chart",
                            on_click=lambda: ui.navigate.to("/staff/results"),
                        ).props("no-caps unelevated").classes("secondary-btn w-full")
                    else:
                        ui.label("No schedule has been generated yet.").classes("section-copy")

            with ui.column().classes("open-surface overflow-hidden gap-0"):
                with ui.row().classes("table-header"):
                    ui.label("Seminar readiness").classes("section-title")
                    ui.label(f"Showing {min(6, len(seminars))} of {len(seminars)}").classes(
                        "section-copy"
                    )
                columns = [
                    {"name": "title", "label": "Seminar", "field": "title", "align": "left"},
                    {"name": "presenter", "label": "Presenter", "field": "presenter", "align": "left"},
                    {"name": "room", "label": "Room", "field": "room", "align": "left"},
                    {"name": "capacity", "label": "Capacity", "field": "capacity", "align": "left"},
                    {"name": "periods_display", "label": "Periods", "field": "periods_display", "align": "left"},
                ]
                rows = [
                    {**row, "periods_display": ", ".join(str(item) for item in row["periods"])}
                    for row in seminars[:6]
                ]
                ui.table(columns=columns, rows=rows, row_key="id", pagination=6).props(
                    "flat bordered separator='cell'"
                ).classes("data-table")

