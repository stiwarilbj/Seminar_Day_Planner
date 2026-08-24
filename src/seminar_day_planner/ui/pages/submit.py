from __future__ import annotations

from datetime import UTC, datetime

from nicegui import ui

from seminar_day_planner.database.engine import session_scope
from seminar_day_planner.database.repository import list_seminars, upsert_student
from seminar_day_planner.types import StudentImportRow
from seminar_day_planner.ui.app import ApplicationContext
from seminar_day_planner.ui.theme import apply_theme, brand, labeled_field


def register_submit_page(context: ApplicationContext) -> None:
    @ui.page("/")
    def root() -> None:
        ui.navigate.to("/submit")

    @ui.page("/submit")
    def student_submission() -> None:
        apply_theme("Choose your Seminar Day sessions")
        ui.query(".nicegui-content").classes("p-0")
        with session_scope(context.engine) as session:
            seminar_rows = list_seminars(session, context.event_id)
        option_labels = {
            row["id"]: (
                f"{row['title']}  |  {row['presenter']}  |  "
                f"Periods {', '.join(str(item) for item in row['periods'])}"
            )
            for row in seminar_rows
        }
        title_by_id = {row["id"]: row["title"] for row in seminar_rows}

        with ui.row().classes("public-header"):
            brand(compact=True)
            ui.link("Staff sign in", "/staff/login").classes(
                "text-[13px] text-[#0756c9] font-semibold no-underline"
            )

        with ui.element("main").classes("student-page student-layout"):
            with ui.column().classes("student-main"):
                with ui.column().classes("gap-1"):
                    ui.label("Choose your Seminar Day sessions").classes("page-title !text-[32px]")
                    ui.label(
                        "Rank six choices. We’ll use them to build the fairest schedule we can."
                    ).classes("page-subtitle !text-[15px]")
                with ui.column().classes("surface form-accent w-full gap-0"):
                    with ui.column().classes("student-section"):
                        ui.label("About you").classes("section-title !text-[18px]")
                        with ui.element("div").classes("student-about-grid"):
                            with ui.column().classes("gap-1"):
                                labeled_field("Full name (required)")
                                name = ui.input(placeholder="Maya Anderson").props(
                                    "outlined autocomplete='name'"
                                ).props(add="dense").classes("w-full")
                            with ui.column().classes("gap-1"):
                                labeled_field("School email (required)")
                                email = ui.input(placeholder="you@school.org").props(
                                    "outlined type='email' autocomplete='email'"
                                ).props(add="dense").classes("w-full")
                            with ui.column().classes("gap-1"):
                                labeled_field("Grade (required)")
                                grade = ui.toggle([9, 10, 11, 12], value=None).props(
                                    "spread no-caps unelevated"
                                ).classes("w-full")

                    with ui.column().classes("student-section"):
                        with ui.column().classes("gap-1"):
                            ui.label("Your choices").classes("section-title !text-[18px]")
                            ui.label(
                                "Rank six different seminars using the dropdowns. Use the arrows to reorder."
                            ).classes("section-copy")
                        choice_selects = []
                        for index in range(6):
                            with ui.row().classes("choice-row"):
                                ui.icon("drag_indicator", size="19px").classes("text-[#627491]")
                                ui.label(str(index + 1)).classes("choice-number")
                                select_control = ui.select(
                                    option_labels,
                                    value=None,
                                    with_input=True,
                                    clearable=True,
                                ).props(
                                    f"outlined dense options-dense aria-label='Choice {index + 1}'"
                                ).classes("choice-select")
                                choice_selects.append(select_control)

                                def move_choice(source: int, offset: int) -> None:
                                    target = source + offset
                                    if not 0 <= target < len(choice_selects):
                                        return
                                    old_value = choice_selects[source].value
                                    choice_selects[source].set_value(choice_selects[target].value)
                                    choice_selects[target].set_value(old_value)
                                    validate_form()

                                ui.button(
                                    icon="keyboard_arrow_up",
                                    on_click=lambda index=index: move_choice(index, -1),
                                ).props("flat dense aria-label='Move choice up'").classes("move-btn")
                                ui.button(
                                    icon="keyboard_arrow_down",
                                    on_click=lambda index=index: move_choice(index, 1),
                                ).props("flat dense aria-label='Move choice down'").classes("move-btn")
                        duplicate_error = ui.row().classes("validation-message")
                        with duplicate_error:
                            ui.icon("warning_amber", size="15px")
                            ui.label("Choose each seminar only once.")
                        duplicate_error.set_visibility(False)
                        ui.label("Seminar availability may change before scheduling.").classes(
                            "info-message"
                        )

                    with ui.column().classes("student-section"):
                        ui.label("Before you submit").classes("section-title")
                        confirmation = ui.checkbox(
                            "I have reviewed my six choices above and confirm they are correct."
                        )
                        form_error = ui.label("").classes("validation-message")
                        form_error.set_visibility(False)

                    with ui.row().classes(
                        "student-section !border-b-0 items-center justify-between flex-wrap"
                    ):
                        with ui.row().classes("gap-3"):
                            submit_button = ui.button(
                                "Submit preferences", icon="lock", on_click=lambda: submit()
                            ).props("no-caps unelevated").classes("primary-btn")

                            def clear_form() -> None:
                                name.set_value("")
                                email.set_value("")
                                grade.set_value(None)
                                confirmation.set_value(False)
                                for control in choice_selects:
                                    control.set_value(None)
                                validate_form()

                            ui.button("Clear form", on_click=clear_form).props(
                                "no-caps unelevated"
                            ).classes("secondary-btn")
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("lock", size="17px").classes("text-[#344c73]")
                            ui.label(
                                "Your information stays in the school’s Seminar Day planner."
                            ).classes("section-copy")

                def validate_form() -> bool:
                    values = [control.value for control in choice_selects]
                    selected = [value for value in values if value is not None]
                    duplicate = len(selected) != len(set(selected))
                    duplicate_error.set_visibility(duplicate)
                    email_value = str(email.value or "").strip().lower()
                    email_valid = "@" in email_value and "." in email_value.rsplit("@", 1)[-1]
                    if context.settings.allowed_email_domain and email_valid:
                        email_valid = email_value.endswith(
                            "@" + context.settings.allowed_email_domain
                        )
                    ready = bool(
                        str(name.value or "").strip()
                        and email_valid
                        and grade.value in {9, 10, 11, 12}
                        and len(selected) == 6
                        and not duplicate
                        and confirmation.value
                    )
                    submit_button.set_enabled(ready)
                    return ready

                def submit() -> None:
                    if not validate_form():
                        form_error.set_text("Complete every field and choose six different seminars.")
                        form_error.set_visibility(True)
                        return
                    try:
                        student_row = StudentImportRow(
                            full_name=str(name.value).strip(),
                            email=str(email.value).strip().lower(),
                            grade=int(grade.value),
                            preferences=[title_by_id[int(control.value)] for control in choice_selects],
                            submitted_at=datetime.now(UTC),
                        )
                        with session_scope(context.engine) as session:
                            upsert_student(session, context.event_id, student_row)
                    except Exception as error:
                        form_error.set_text(str(error))
                        form_error.set_visibility(True)
                        return
                    form_error.set_visibility(False)
                    ui.notify(
                        "Your preferences are saved. You’re all set!",
                        type="positive",
                        position="top",
                    )
                    clear_form()

                for control in [name, email, grade, confirmation, *choice_selects]:
                    control.on("update:model-value", lambda: validate_form())
                validate_form()

            with ui.column().classes("student-info-rail"):
                ui.label("How it works").classes("section-title !text-[18px]")
                steps = (
                    ("menu_book", "Pick six sessions", "Choose six different seminars and rank them from 1st to 6th."),
                    ("balance", "We balance choices and space", "We look at everyone’s choices and class sizes to build the fairest schedule possible."),
                    ("calendar_month", "Staff shares your final schedule", "You’ll see your Seminar Day schedule before the event so you know where to be."),
                )
                for number, (icon, title, copy) in enumerate(steps, start=1):
                    with ui.row().classes("how-step no-wrap"):
                        ui.label(str(number)).classes("how-number")
                        ui.icon(icon, size="31px").classes("text-[#0864e8] mt-1")
                        with ui.column().classes("gap-2"):
                            ui.label(title).classes("how-title")
                            ui.label(copy).classes("how-copy")
                with ui.column().classes("gap-4 pt-5"):
                    with ui.row().classes("summary-line"):
                        ui.icon("event", size="18px")
                        ui.label("Responses close Friday at 3:00 PM")
                    with ui.row().classes("summary-line"):
                        ui.icon("help_outline", size="18px")
                        ui.label("Questions? Ask the Seminar Day team.")
