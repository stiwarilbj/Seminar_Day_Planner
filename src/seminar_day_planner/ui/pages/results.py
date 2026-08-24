from __future__ import annotations

from nicegui import run, ui

from seminar_day_planner.database.engine import session_scope
from seminar_day_planner.database.repository import latest_schedule_run, schedule_rows
from seminar_day_planner.exports import export_schedule_bundle
from seminar_day_planner.scheduling.solver import validate_schedule
from seminar_day_planner.ui.app import ApplicationContext
from seminar_day_planner.ui.theme import require_staff, satisfaction_bar, staff_shell


def register_results_page(context: ApplicationContext) -> None:
    @ui.page("/staff/results")
    def results_page() -> None:
        if not require_staff():
            return
        with session_scope(context.engine) as session:
            latest = latest_schedule_run(session, context.event_id)
            rows = schedule_rows(session, latest.id) if latest else []
            validation_errors = validate_schedule(session, latest.id) if latest else []
        controls: dict[str, object] = {}

        async def export_results() -> None:
            if latest is None or latest.status not in {"optimal", "feasible"}:
                ui.notify("Generate a feasible schedule before exporting.", type="warning")
                return
            button = controls["export"]
            button.set_enabled(False)
            button.props(add="loading")
            try:
                bundle = await run.io_bound(
                    export_schedule_bundle,
                    context.engine,
                    latest.id,
                    context.settings.export_root,
                )
            except Exception as error:
                ui.notify(str(error), type="negative", multi_line=True)
                button.props(remove="loading")
                button.set_enabled(True)
                return
            button.props(remove="loading")
            button.set_enabled(True)
            ui.notify(
                f"Created {bundle.student_pdf_count} student schedules and "
                f"{bundle.attendance_pdf_count} attendance lists.",
                type="positive",
            )
            ui.download(bundle.archive_path)

        def actions() -> None:
            ui.button(
                "Back to builder",
                icon="arrow_back",
                on_click=lambda: ui.navigate.to("/staff/builder"),
            ).props("no-caps unelevated").classes("secondary-btn")
            export = ui.button(
                "Export schedule ZIP", icon="download", on_click=export_results
            ).props("no-caps unelevated").classes("primary-btn")
            export.set_enabled(latest is not None and latest.status in {"optimal", "feasible"})
            controls["export"] = export

        with staff_shell(
            "results",
            "Schedule results",
            "Review the latest run, check fairness, and download every schedule.",
            actions,
        ):
            if latest is None:
                with ui.column().classes("open-surface w-full items-center py-16 gap-3"):
                    ui.icon("bar_chart", size="44px").classes("text-[#9aabc2]")
                    ui.label("No schedule results yet").classes("section-title !text-[20px]")
                    ui.label("Finish setup, then generate a schedule in the builder.").classes(
                        "section-copy"
                    )
                    ui.button(
                        "Open schedule builder",
                        icon="calendar_month",
                        on_click=lambda: ui.navigate.to("/staff/builder"),
                    ).props("no-caps unelevated").classes("primary-btn")
                return

            with ui.element("div").classes("overview-grid"):
                with ui.column().classes("open-surface section-pad gap-4"):
                    with ui.row().classes("w-full justify-between items-center"):
                        with ui.column().classes("gap-0"):
                            ui.label(f"Run {latest.id}").classes("section-title")
                            ui.label(f"Solver status: {latest.solver_status}").classes("section-copy")
                        with ui.row().classes("items-center gap-2"):
                            ui.icon(
                                "check_circle" if not validation_errors else "warning",
                                size="20px",
                            ).classes("status-ok" if not validation_errors else "status-warning")
                            ui.label(
                                "Validated" if not validation_errors else "Needs attention"
                            ).classes("text-[13px] font-bold")
                    ui.label("Best preference received by each student").classes("field-label")
                    satisfaction_bar(latest.satisfaction)
                with ui.column().classes("open-surface section-pad gap-3"):
                    ui.label("Run summary").classes("section-title")
                    summary_rows = (
                        ("Students", latest.satisfaction.get("students_total", 0)),
                        ("Received a ranked choice", latest.satisfaction.get("students_with_ranked", 0)),
                        ("Received a top-two choice", latest.satisfaction.get("students_with_top_two", 0)),
                        ("Lunch in period 2", latest.satisfaction.get("lunch_block_2", 0)),
                        ("Lunch in period 3", latest.satisfaction.get("lunch_block_3", 0)),
                    )
                    for label, value in summary_rows:
                        with ui.row().classes("w-full justify-between gap-4 py-1"):
                            ui.label(label).classes("section-copy")
                            ui.label(str(value)).classes("text-[13px] font-bold")
                    if validation_errors:
                        ui.separator().classes("bg-[#cddff5]")
                        for error in validation_errors[:4]:
                            with ui.row().classes("validation-message"):
                                ui.icon("warning_amber", size="16px")
                                ui.label(error)

            with ui.column().classes("open-surface overflow-hidden gap-0"):
                with ui.row().classes("table-header"):
                    with ui.column().classes("gap-0"):
                        ui.label("Student schedules").classes("section-title")
                        ui.label(f"{len(rows)} students in run {latest.id}").classes("section-copy")
                    search = ui.input(placeholder="Filter students").props(
                        "outlined dense clearable debounce=250"
                    ).classes("w-[220px] max-w-full")
                columns = [
                    {"name": "student", "label": "Student", "field": "student", "align": "left", "sortable": True},
                    {"name": "grade", "label": "Grade", "field": "grade", "align": "left"},
                    {"name": "period_1", "label": "Period 1", "field": "period_1", "align": "left"},
                    {"name": "period_2", "label": "Period 2", "field": "period_2", "align": "left"},
                    {"name": "period_3", "label": "Period 3", "field": "period_3", "align": "left"},
                    {"name": "period_4", "label": "Period 4", "field": "period_4", "align": "left"},
                ]
                table = ui.table(
                    columns=columns,
                    rows=rows,
                    row_key="student_id",
                    pagination={"rowsPerPage": 25},
                ).props("flat bordered separator='cell'").classes("data-table")
                table.bind_filter_from(search, "value")

