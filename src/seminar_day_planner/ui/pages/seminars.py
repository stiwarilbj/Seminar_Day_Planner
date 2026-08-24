from __future__ import annotations

from nicegui import ui

from seminar_day_planner.database.engine import session_scope
from seminar_day_planner.database.repository import list_seminars, upsert_seminar
from seminar_day_planner.types import SeminarImportRow
from seminar_day_planner.ui.app import ApplicationContext
from seminar_day_planner.ui.theme import labeled_field, require_staff, staff_shell


def register_seminars_page(context: ApplicationContext) -> None:
    @ui.page("/staff/seminars")
    def seminars_page() -> None:
        if not require_staff():
            return
        with session_scope(context.engine) as session:
            seminar_rows = list_seminars(session, context.event_id)

        selected: dict[str, dict | None] = {"row": None}

        with ui.dialog() as seminar_dialog, ui.card().classes("w-[560px] max-w-[94vw] p-5 gap-4"):
            dialog_title = ui.label("Add seminar").classes("section-title !text-[19px]")
            with ui.element("div").classes("form-grid"):
                with ui.column().classes("gap-1 col-span-2 max-[820px]:col-span-1"):
                    labeled_field("Seminar title")
                    title_input = ui.input().props("outlined").classes("w-full")
                with ui.column().classes("gap-1"):
                    labeled_field("Presenter")
                    presenter_input = ui.input().props("outlined").classes("w-full")
                with ui.column().classes("gap-1"):
                    labeled_field("Room")
                    room_input = ui.input().props("outlined").classes("w-full")
                with ui.column().classes("gap-1"):
                    labeled_field("Capacity")
                    capacity_input = ui.number(value=18, min=1, max=500).props("outlined").classes("w-full")
                with ui.column().classes("gap-1"):
                    labeled_field("Periods offered")
                    periods_input = ui.select(
                        [1, 2, 3, 4], value=[1, 2, 3, 4], multiple=True
                    ).props("outlined use-chips").classes("w-full")
                with ui.column().classes("gap-1 col-span-2 max-[820px]:col-span-1"):
                    labeled_field("Short description")
                    description_input = ui.textarea().props("outlined autogrow").classes("w-full")
            dialog_error = ui.label("").classes("validation-message")
            dialog_error.set_visibility(False)

            def save_seminar() -> None:
                try:
                    row = SeminarImportRow(
                        title=str(title_input.value or ""),
                        presenter=str(presenter_input.value or ""),
                        room=str(room_input.value or ""),
                        capacity=int(capacity_input.value or 0),
                        periods=[int(item) for item in (periods_input.value or [])],
                        description=str(description_input.value or ""),
                    )
                    with session_scope(context.engine) as session:
                        upsert_seminar(session, context.event_id, row)
                except Exception as error:
                    dialog_error.set_text(str(error))
                    dialog_error.set_visibility(True)
                    return
                seminar_dialog.close()
                ui.notify("Seminar saved.", type="positive")
                ui.navigate.to("/staff/seminars")

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=seminar_dialog.close).props("no-caps flat").classes("quiet-btn")
                ui.button("Save seminar", icon="save", on_click=save_seminar).props(
                    "no-caps unelevated"
                ).classes("primary-btn")

        def open_add() -> None:
            selected["row"] = None
            dialog_title.set_text("Add seminar")
            title_input.set_value("")
            presenter_input.set_value("")
            room_input.set_value("")
            capacity_input.set_value(18)
            periods_input.set_value([1, 2, 3, 4])
            description_input.set_value("")
            dialog_error.set_visibility(False)
            seminar_dialog.open()

        def open_edit() -> None:
            row = selected["row"]
            if row is None:
                ui.notify("Select a seminar row first.", type="warning")
                return
            dialog_title.set_text("Edit seminar")
            title_input.set_value(row["title"])
            presenter_input.set_value(row["presenter"])
            room_input.set_value(row["room"])
            capacity_input.set_value(row["capacity"])
            periods_input.set_value(row["periods"])
            description_input.set_value(row["description"])
            dialog_error.set_visibility(False)
            seminar_dialog.open()

        def actions() -> None:
            ui.button("Edit selected", icon="edit", on_click=open_edit).props(
                "no-caps unelevated"
            ).classes("secondary-btn")
            ui.button("Add seminar", icon="add", on_click=open_add).props(
                "no-caps unelevated"
            ).classes("primary-btn")

        with staff_shell(
            "seminars",
            "Seminars",
            "Set presenters, rooms, capacity, and the periods each session is offered.",
            actions,
        ):
            with ui.column().classes("open-surface overflow-hidden gap-0"):
                with ui.row().classes("table-header"):
                    with ui.column().classes("gap-0"):
                        ui.label("Seminar offerings").classes("section-title")
                        ui.label(f"{len(seminar_rows)} active seminars").classes("section-copy")
                    ui.input(placeholder="Search seminars").props(
                        "outlined dense clearable debounce=250"
                    ).classes("w-[240px] max-w-full")
                columns = [
                    {"name": "title", "label": "Seminar", "field": "title", "align": "left", "sortable": True},
                    {"name": "presenter", "label": "Presenter", "field": "presenter", "align": "left"},
                    {"name": "room", "label": "Room", "field": "room", "align": "left"},
                    {"name": "capacity", "label": "Capacity", "field": "capacity", "align": "left"},
                    {"name": "periods_display", "label": "Periods", "field": "periods_display", "align": "left"},
                ]
                table_rows = [
                    {**row, "periods_display": ", ".join(str(value) for value in row["periods"])}
                    for row in seminar_rows
                ]
                table = ui.table(
                    columns=columns,
                    rows=table_rows,
                    row_key="id",
                    selection="single",
                    pagination={"rowsPerPage": 25},
                ).props("flat bordered separator='cell'").classes("data-table")
                table.on(
                    "selection",
                    lambda event: selected.update(
                        row=(event.args.get("rows") or [None])[0]
                        if isinstance(event.args, dict)
                        else None
                    ),
                )

