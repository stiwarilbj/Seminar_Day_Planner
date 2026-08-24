from __future__ import annotations

import inspect
from pathlib import Path

from nicegui import events, ui

from seminar_day_planner.database.engine import session_scope
from seminar_day_planner.database.repository import list_seminars
from seminar_day_planner.ingestion.parsers import (
    parse_delimited_bytes,
    parse_json_bytes,
    parse_natural_language,
    parse_spreadsheet_bytes,
    parse_sqlite_table,
)
from seminar_day_planner.ingestion.service import confirm_import_batch, stage_import_batch
from seminar_day_planner.types import ImportPreview
from seminar_day_planner.ui.app import ApplicationContext
from seminar_day_planner.ui.theme import require_staff, staff_shell

DEMO_TEXT = """Maya Anderson, grade 12, maya@student.example.test, wants Robotics Lab, Film Scoring, then Climate Science
Liam Baker, grade 11, liam@student.example.test, wants Local Journalism, Robotics Lab, then Sports Medicine
Sophia Chen, grade 12, sophia@student.example.test, wants Sports Medicine, Climate Science, then Robotics Lab
Mateo Diaz, grade 10, mateo@student.example.test, wants Intro to Architecture, Local Journalism, then Climate Science
Olivia Evans, grade 11, olivia@student.example.test, wants Robotics Lab, Sports Medicine, then Film Scoring
Ethan Foster, grade 10, ethan@student.example.test, wants Local Journalism, Intro to Architecture, then Robotics Lab"""


def register_imports_page(context: ApplicationContext) -> None:
    @ui.page("/staff/imports")
    def imports_page() -> None:
        if not require_staff():
            return
        with session_scope(context.engine) as session:
            known_seminars = [row["title"] for row in list_seminars(session, context.event_id)]

        state: dict[str, object] = {
            "source": "text",
            "target": "student",
            "preview": None,
            "batch_id": None,
            "filename": None,
        }
        controls: dict[str, object] = {}

        def confirm_rows() -> None:
            batch_id = state.get("batch_id")
            preview = state.get("preview")
            if not batch_id or not isinstance(preview, ImportPreview):
                ui.notify("Parse or upload data before confirming.", type="warning")
                return
            if preview.error_count:
                ui.notify("Fix every error before confirming.", type="negative")
                return
            try:
                with session_scope(context.engine) as session:
                    count, warnings = confirm_import_batch(session, int(batch_id))
            except Exception as error:
                ui.notify(str(error), type="negative", multi_line=True)
                return
            ui.notify(
                f"Saved {count} rows" + (f" with {warnings} reviewed warnings." if warnings else "."),
                type="positive",
            )
            ui.navigate.to("/staff/overview")

        def actions() -> None:
            confirm = ui.button(
                "Confirm rows", icon="check", on_click=confirm_rows
            ).props("no-caps unelevated").classes("primary-btn")
            confirm.set_enabled(False)
            controls["confirm"] = confirm
            ui.button(
                "Cancel import",
                on_click=lambda: ui.navigate.to("/staff/overview"),
            ).props("no-caps unelevated").classes("secondary-btn")

        def store_preview(preview: ImportPreview, filename: str | None = None) -> None:
            with session_scope(context.engine) as session:
                batch = stage_import_batch(
                    session,
                    context.event_id,
                    preview,
                    filename=filename,
                )
                batch_id = batch.id
            state["preview"] = preview
            state["batch_id"] = batch_id
            state["filename"] = filename
            confirm = controls.get("confirm")
            if confirm is not None:
                confirm.set_text(f"Confirm {preview.ready_count} rows")
                confirm.set_enabled(preview.error_count == 0 and preview.ready_count > 0)
            render_review.refresh()
            render_summary.refresh()

        def parse_text_action() -> None:
            try:
                text_control = state.get("text_input")
                text_value = getattr(text_control, "value", "")
                preview = parse_natural_language(
                    str(text_value or ""),
                    state["target"],
                    known_seminars if state["target"] == "student" else None,
                )
                store_preview(preview)
            except Exception as error:
                ui.notify(str(error), type="negative", multi_line=True)

        async def handle_upload(event: events.UploadEventArguments) -> None:
            file_object = getattr(event, "file", None)
            filename = getattr(file_object, "name", None) or getattr(event, "name", "upload")
            if file_object is not None:
                content = file_object.read()
                if inspect.isawaitable(content):
                    content = await content
            else:
                content_stream = event.content
                content = content_stream.read()
            suffix = Path(filename).suffix.casefold()
            try:
                if suffix in {".csv", ".tsv", ".txt"}:
                    preview = parse_delimited_bytes(
                        content,
                        state["target"],
                        known_seminars if state["target"] == "student" else None,
                    )
                elif suffix in {".xlsx", ".xlsm"}:
                    preview = parse_spreadsheet_bytes(
                        content,
                        state["target"],
                        known_seminars if state["target"] == "student" else None,
                    )
                elif suffix == ".json":
                    preview = parse_json_bytes(
                        content,
                        state["target"],
                        known_seminars if state["target"] == "student" else None,
                    )
                elif suffix in {".db", ".sqlite", ".sqlite3"}:
                    upload_path = context.settings.upload_root / Path(filename).name
                    upload_path.write_bytes(content)
                    preview = parse_sqlite_table(
                        upload_path,
                        state["target"],
                        known_seminars=known_seminars if state["target"] == "student" else None,
                    )
                else:
                    raise ValueError("Use CSV, Excel, JSON, or SQLite files.")
                store_preview(preview, filename)
            except Exception as error:
                ui.notify(str(error), type="negative", multi_line=True)

        def select_source(source: str) -> None:
            state["source"] = source
            render_source.refresh()

        def select_target(value: str) -> None:
            state["target"] = value
            state["preview"] = None
            state["batch_id"] = None
            confirm = controls.get("confirm")
            if confirm is not None:
                confirm.set_text("Confirm rows")
                confirm.set_enabled(False)
            render_source.refresh()
            render_review.refresh()
            render_summary.refresh()

        @ui.refreshable
        def render_source() -> None:
            source = str(state["source"])
            with ui.column().classes("open-surface section-pad gap-4"):
                with ui.row().classes("w-full justify-between items-center gap-4 flex-wrap"):
                    ui.label("Import source").classes("section-title")
                    ui.toggle(
                        {"student": "Students", "seminar": "Seminars"},
                        value=state["target"],
                        on_change=lambda event: select_target(event.value),
                    ).props("no-caps unelevated")
                with ui.row().classes("source-switcher no-wrap"):
                    sources = (
                        ("files", "CSV or Excel", "table_view"),
                        ("json", "JSON", "data_object"),
                        ("sqlite", "SQLite", "database"),
                        ("text", "Paste text", "description"),
                    )
                    for key, label, icon in sources:
                        ui.button(
                            label,
                            icon=icon,
                            on_click=lambda key=key: select_source(key),
                        ).props("no-caps unelevated").classes(
                            "source-button" + (" selected" if source == key else "")
                        )
                if source == "text":
                    ui.label("Paste natural-language data. Use one record per line.").classes(
                        "section-copy"
                    )
                    text_input = ui.textarea(value=DEMO_TEXT).props(
                        "outlined rows=7 aria-label='Natural-language import text'"
                    ).classes("w-full")
                    state["text_input"] = text_input
                    with ui.row().classes("gap-3"):
                        ui.button("Parse text", icon="play_arrow", on_click=parse_text_action).props(
                            "no-caps unelevated"
                        ).classes("primary-btn")
                        ui.button(
                            "Choose another source",
                            on_click=lambda: select_source("files"),
                        ).props("no-caps unelevated").classes("secondary-btn")
                else:
                    accepted = {
                        "files": ".csv,.tsv,.xlsx,.xlsm",
                        "json": ".json",
                        "sqlite": ".db,.sqlite,.sqlite3",
                    }.get(source, ".csv,.xlsx,.json,.db")
                    ui.upload(
                        label="Choose a local data file",
                        on_upload=handle_upload,
                        auto_upload=True,
                        max_file_size=10_000_000,
                    ).props(f"accept='{accepted}' flat bordered").classes("w-full")
                    source_copy = {
                        "files": "Google Forms CSV, general CSV, TSV, and Excel are supported.",
                        "json": "Use a list of objects or a students or seminars array.",
                        "sqlite": "The first user table is read in read-only mode. No SQL is executed from the file.",
                    }
                    ui.label(source_copy.get(source, "Choose a supported file.")).classes(
                        "section-copy"
                    )

        @ui.refreshable
        def render_review() -> None:
            preview = state.get("preview")
            with ui.column().classes("open-surface overflow-hidden gap-0"):
                with ui.row().classes("table-header"):
                    with ui.column().classes("gap-0"):
                        ui.label(
                            "Review parsed students"
                            if state["target"] == "student"
                            else "Review parsed seminars"
                        ).classes("section-title")
                        if isinstance(preview, ImportPreview):
                            ui.label(
                                f"{preview.ready_count} ready, {preview.warning_count} warning, "
                                f"{preview.error_count} error"
                            ).classes("section-copy")
                        else:
                            ui.label("Parse or upload data to begin review.").classes("section-copy")
                    ui.checkbox("Issues only").classes("text-[12px]")
                if not isinstance(preview, ImportPreview):
                    with ui.column().classes("w-full items-center py-12 gap-2"):
                        ui.icon("table_rows", size="34px").classes("text-[#9aabc2]")
                        ui.label("No rows to review yet.").classes("section-copy")
                    return

                if state["target"] == "student":
                    columns = [
                        {"name": "status", "label": "Status", "field": "status", "align": "left"},
                        {"name": "full_name", "label": "Student", "field": "full_name", "align": "left"},
                        {"name": "email", "label": "Email", "field": "email", "align": "left"},
                        {"name": "grade", "label": "Grade", "field": "grade", "align": "left"},
                        {"name": "choice_1", "label": "Choice 1", "field": "choice_1", "align": "left"},
                        {"name": "choice_2", "label": "Choice 2", "field": "choice_2", "align": "left"},
                        {"name": "messages", "label": "Review note", "field": "messages", "align": "left"},
                    ]
                    rows = []
                    for row in preview.rows:
                        data = row.normalized_data
                        preferences = data.get("preferences", [])
                        rows.append(
                            {
                                "row": row.row_number,
                                "status": row.status.title(),
                                "full_name": data.get("full_name", "Needs attention"),
                                "email": data.get("email", ""),
                                "grade": data.get("grade", ""),
                                "choice_1": preferences[0] if preferences else "",
                                "choice_2": preferences[1] if len(preferences) > 1 else "",
                                "messages": " ".join(row.messages),
                            }
                        )
                else:
                    columns = [
                        {"name": "status", "label": "Status", "field": "status", "align": "left"},
                        {"name": "title", "label": "Seminar", "field": "title", "align": "left"},
                        {"name": "presenter", "label": "Presenter", "field": "presenter", "align": "left"},
                        {"name": "room", "label": "Room", "field": "room", "align": "left"},
                        {"name": "capacity", "label": "Capacity", "field": "capacity", "align": "left"},
                        {"name": "periods", "label": "Periods", "field": "periods", "align": "left"},
                        {"name": "messages", "label": "Review note", "field": "messages", "align": "left"},
                    ]
                    rows = [
                        {
                            "row": row.row_number,
                            "status": row.status.title(),
                            "title": row.normalized_data.get("title", "Needs attention"),
                            "presenter": row.normalized_data.get("presenter", ""),
                            "room": row.normalized_data.get("room", ""),
                            "capacity": row.normalized_data.get("capacity", ""),
                            "periods": ", ".join(
                                str(item) for item in row.normalized_data.get("periods", [])
                            ),
                            "messages": " ".join(row.messages),
                        }
                        for row in preview.rows
                    ]
                ui.table(
                    columns=columns,
                    rows=rows,
                    row_key="row",
                    pagination={"rowsPerPage": 25},
                ).props("flat bordered separator='cell'").classes("data-table")

        @ui.refreshable
        def render_summary() -> None:
            preview = state.get("preview")
            with ui.column().classes("summary-rail gap-0"):
                with ui.column().classes("summary-block"):
                    ui.label("Import check").classes("section-title")
                with ui.column().classes("summary-block"):
                    ui.label("Detected source").classes("summary-label")
                    with ui.row().classes("summary-line"):
                        ui.icon("description", size="22px")
                        ui.label(
                            (state.get("filename") or str(state["source"]).replace("_", " ")).title()
                        )
                with ui.column().classes("summary-block"):
                    ui.label("Will create").classes("summary-label")
                    ready = preview.ready_count if isinstance(preview, ImportPreview) else 0
                    with ui.row().classes("summary-line"):
                        ui.icon("groups", size="22px").classes("text-[#0864e8]")
                        ui.label(
                            f"{ready} {'students' if state['target'] == 'student' else 'seminars'}"
                        )
                if isinstance(preview, ImportPreview) and preview.field_mappings:
                    with ui.column().classes("summary-block"):
                        ui.label("Matched fields").classes("summary-label")
                        for source, target in list(preview.field_mappings.items())[:7]:
                            with ui.row().classes("summary-line w-full"):
                                ui.label(source).classes("truncate max-w-[105px]")
                                ui.icon("arrow_forward", size="14px").classes("text-[#9aabc2]")
                                ui.label(target).classes(
                                    "font-semibold" if target != "ignored" else "status-warning"
                                )
                with ui.column().classes("summary-block"):
                    ui.label("Needs attention").classes("summary-label")
                    errors = preview.error_count if isinstance(preview, ImportPreview) else 0
                    warnings = preview.warning_count if isinstance(preview, ImportPreview) else 0
                    with ui.row().classes("summary-line"):
                        ui.icon("error_outline", size="19px").classes("status-error")
                        ui.label(f"{errors} errors")
                    with ui.row().classes("summary-line"):
                        ui.icon("warning_amber", size="19px").classes("status-warning")
                        ui.label(f"{warnings} warnings")
                with ui.column().classes("summary-block"):
                    ui.label("Duplicate handling").classes("summary-label")
                    ui.label("If a student with the same email exists").classes("section-copy")
                    ui.select(["Update matching emails"], value="Update matching emails").props(
                        "outlined dense"
                    ).classes("w-full")
                with ui.column().classes("summary-block !border-b-0"):
                    with ui.row().classes("summary-line"):
                        ui.icon("info_outline", size="18px")
                        ui.label("Nothing is saved until you confirm.")

        with staff_shell(
            "imports",
            "Bring in your data",
            "Import students or seminars, check what we found, then save it.",
            actions,
        ):
            with ui.row().classes("step-row no-wrap"):
                for index, label in enumerate(("Source", "Match fields", "Review", "Save"), start=1):
                    with ui.row().classes("step active" if index == 3 else "step"):
                        ui.label(str(index)).classes("step-number")
                        ui.label(label)
                    if index < 4:
                        ui.element("span").classes("step-line")
            with ui.element("div").classes("import-layout"):
                with ui.column().classes("gap-4 min-w-0"):
                    render_source()
                    render_review()
                render_summary()
