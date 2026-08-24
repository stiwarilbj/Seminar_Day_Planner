from __future__ import annotations

from nicegui import run, ui

from seminar_day_planner.database.engine import session_scope
from seminar_day_planner.database.repository import (
    event_counts,
    latest_schedule_run,
    schedule_rows,
)
from seminar_day_planner.ingestion.parsers import parse_scheduling_rule
from seminar_day_planner.scheduling.solver import generate_and_persist_schedule
from seminar_day_planner.types import SchedulingConfiguration
from seminar_day_planner.ui.app import ApplicationContext
from seminar_day_planner.ui.theme import (
    labeled_field,
    metric_strip,
    require_staff,
    satisfaction_bar,
    staff_shell,
)


def register_builder_page(context: ApplicationContext) -> None:
    @ui.page("/staff/builder")
    def builder_page() -> None:
        if not require_staff():
            return
        with session_scope(context.engine) as session:
            counts = event_counts(session, context.event_id)
            latest = latest_schedule_run(session, context.event_id)
            sample = schedule_rows(session, latest.id, limit=8) if latest else []

        parsed_settings: dict[str, bool] = {
            "balance_lunch": True,
            "prioritize_seniors": False,
            "prioritize_earlier_submissions": False,
        }
        controls: dict[str, object] = {}

        async def generate_schedule() -> None:
            button = controls["generate"]
            button.set_enabled(False)
            button.props(add="loading")
            ui.notify("Building a fair schedule. This can take a moment.", type="ongoing")
            try:
                max_value = controls["maximum"].value
                configuration = SchedulingConfiguration(
                    event_id=context.event_id,
                    required_seminars=3,
                    lunch_blocks=(2, 3),
                    maximum_seminar_size=int(max_value) if max_value else None,
                    prioritize_seniors=parsed_settings.get("prioritize_seniors", False),
                    prioritize_earlier_submissions=parsed_settings.get(
                        "prioritize_earlier_submissions", False
                    ),
                    balance_lunch=True,
                    random_seed=42,
                    time_limit_seconds=45,
                )
                run_id, result = await run.io_bound(
                    generate_and_persist_schedule,
                    context.engine,
                    context.event_id,
                    configuration,
                )
            except Exception as error:
                ui.notify(str(error), type="negative", multi_line=True)
                button.props(remove="loading")
                button.set_enabled(True)
                return
            button.props(remove="loading")
            button.set_enabled(True)
            if result.status in {"optimal", "feasible"}:
                ui.notify(f"Schedule run {run_id} is ready.", type="positive")
                ui.navigate.to("/staff/results")
            else:
                message = " ".join(result.diagnostics.errors) or "No schedule was found."
                ui.notify(message, type="negative", multi_line=True, timeout=10000)

        def actions() -> None:
            ui.button(
                "Save draft",
                icon="save",
                on_click=lambda: ui.notify("The current rules are saved in this browser."),
            ).props("no-caps unelevated").classes("secondary-btn")
            generate = ui.button(
                "Generate schedule", icon="play_arrow", on_click=generate_schedule
            ).props("no-caps unelevated").classes("primary-btn")
            controls["generate"] = generate

        with staff_shell(
            "builder",
            "Build the seminar schedule",
            "Check your data, set the rules, and make a fair schedule.",
            actions,
        ):
            metric_strip(counts["students"], counts["seminars"])
            with ui.element("div").classes("two-column"):
                with ui.column().classes("open-surface section-pad gap-4"):
                    ui.label("Scheduling rules").classes("section-title")
                    with ui.element("div").classes("form-grid"):
                        with ui.column().classes("gap-1"):
                            labeled_field("Periods")
                            ui.select(["4 periods"], value="4 periods").props(
                                "outlined"
                            ).classes("w-full")
                        with ui.column().classes("gap-1"):
                            labeled_field("Lunch pattern")
                            ui.select(
                                ["Balanced in periods 2 and 3"],
                                value="Balanced in periods 2 and 3",
                            ).props("outlined").classes("w-full")
                        with ui.column().classes("gap-1"):
                            labeled_field("Maximum seminar size")
                            maximum = ui.number(value=24, min=1, max=500).props(
                                "outlined"
                            ).classes("w-full")
                            controls["maximum"] = maximum
                        with ui.column().classes("gap-1"):
                            labeled_field("Priority order")
                            ui.select(
                                ["1st choice, 2nd, 3rd, 4th, 5th, 6th"],
                                value="1st choice, 2nd, 3rd, 4th, 5th, 6th",
                            ).props("outlined").classes("w-full")
                    with ui.column().classes("gap-1"):
                        labeled_field("Natural-language rule (optional)")
                        rule_input = ui.textarea(
                            value="Try to give seniors their first choice and keep lunch groups balanced."
                        ).props("outlined rows=3").classes("w-full")
                        rule_status = ui.label("").classes("section-copy")

                        def apply_rule() -> None:
                            settings, warnings = parse_scheduling_rule(str(rule_input.value or ""))
                            if warnings:
                                rule_status.set_text(
                                    warnings[0] + " Nothing was applied."
                                )
                                rule_status.classes(replace="validation-message")
                                return
                            parsed_settings.update(settings)
                            applied = [key.replace("_", " ") for key, enabled in settings.items() if enabled]
                            rule_status.set_text("Applied: " + ", ".join(applied) + ".")
                            rule_status.classes(replace="section-copy status-ok")

                        ui.button("Apply rule", on_click=apply_rule).props(
                            "no-caps unelevated"
                        ).classes("primary-btn self-start")

                with ui.column().classes("open-surface section-pad gap-4"):
                    ui.label("Run preview").classes("section-title")
                    ui.label("Preference satisfaction (based on the last run)").classes(
                        "field-label"
                    )
                    satisfaction_bar(latest.satisfaction if latest else None)
                    ui.separator().classes("bg-[#cddff5]")
                    ui.label("Capacity warnings").classes("field-label")
                    with ui.row().classes("w-full items-center gap-2"):
                        has_capacity_issue = counts["seminars"] == 0 or counts["sessions"] == 0
                        ui.icon(
                            "warning" if has_capacity_issue else "check_circle", size="18px"
                        ).classes("status-warning" if has_capacity_issue else "status-ok")
                        ui.label(
                            "Seminar setup needs attention"
                            if has_capacity_issue
                            else "No setup conflicts found"
                        ).classes("text-[12px]")
                        ui.link("View details", "/staff/seminars").classes(
                            "ml-auto text-[12px] text-[#0756c9]"
                        )
                    ui.separator().classes("bg-[#cddff5]")
                    ui.label("Action checklist").classes("field-label")
                    checklist = (
                        (True, "Periods and lunch are configured"),
                        (counts["seminars"] > 0, "All seminars have capacities"),
                        (latest is not None, "Run the schedule to review results"),
                        (latest is not None, "Review warnings and adjust if needed"),
                        (latest is not None, "Export schedules and attendance lists"),
                    )
                    for ready, label in checklist:
                        with ui.row().classes("items-center gap-2"):
                            ui.icon(
                                "check_circle" if ready else "radio_button_unchecked",
                                size="16px",
                            ).classes("status-ok" if ready else "text-[#9aabc2]")
                            ui.label(label).classes("text-[12px] text-[#344c73]")

            with ui.column().classes("open-surface overflow-hidden gap-0"):
                with ui.row().classes("table-header"):
                    with ui.row().classes("items-center gap-3"):
                        ui.label("Sample schedule").classes("section-title")
                        ui.label(
                            f"Showing {len(sample)} of {counts['students']} students"
                        ).classes("section-copy")
                    search = ui.input(placeholder="Filter students").props(
                        "outlined dense clearable debounce=250"
                    ).classes("w-[210px] max-w-full")
                columns = [
                    {"name": "student", "label": "Student", "field": "student", "align": "left"},
                    {"name": "grade", "label": "Grade", "field": "grade", "align": "left"},
                    {"name": "period_1", "label": "Period 1", "field": "period_1", "align": "left"},
                    {"name": "period_2", "label": "Period 2", "field": "period_2", "align": "left"},
                    {"name": "period_3", "label": "Period 3", "field": "period_3", "align": "left"},
                    {"name": "period_4", "label": "Period 4", "field": "period_4", "align": "left"},
                ]
                if sample:
                    table = ui.table(
                        columns=columns,
                        rows=sample,
                        row_key="student_id",
                        pagination={"rowsPerPage": 8},
                    ).props("flat bordered separator='cell'").classes("data-table")
                    table.bind_filter_from(search, "value")
                else:
                    with ui.column().classes("w-full items-center py-10 gap-2"):
                        ui.icon("calendar_month", size="34px").classes("text-[#9aabc2]")
                        ui.label("Generate a schedule to see student assignments here.").classes(
                            "section-copy"
                        )
