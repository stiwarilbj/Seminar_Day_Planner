from __future__ import annotations

import json
import re
import shutil
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from fpdf import FPDF
from sqlalchemy import Engine, select
from sqlalchemy.orm import selectinload

from seminar_day_planner.database.engine import session_scope
from seminar_day_planner.database.models import (
    Assignment,
    Event,
    ScheduleRun,
    SeminarSession,
)


@dataclass(frozen=True, slots=True)
class ExportBundle:
    run_id: int
    root: Path
    archive_path: Path
    student_pdf_count: int
    attendance_pdf_count: int


def safe_filename(value: str, fallback: str = "schedule") -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip()).strip("._")
    return safe[:100] or fallback


def pdf_text(value: object) -> str:
    return str(value).encode("latin-1", errors="replace").decode("latin-1")


def _new_pdf(title: str, subtitle: str = "") -> FPDF:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_fill_color(8, 100, 232)
    pdf.rect(0, 0, 210, 10, style="F")
    pdf.set_text_color(13, 33, 79)
    pdf.set_font("Helvetica", style="B", size=18)
    pdf.ln(10)
    pdf.cell(0, 10, pdf_text(title), new_x="LMARGIN", new_y="NEXT")
    if subtitle:
        pdf.set_text_color(74, 96, 128)
        pdf.set_font("Helvetica", size=10)
        pdf.multi_cell(0, 6, pdf_text(subtitle))
    pdf.ln(4)
    return pdf


def export_schedule_bundle(
    engine: Engine,
    run_id: int,
    export_root: Path,
) -> ExportBundle:
    bundle_root = export_root / f"schedule-run-{run_id}"
    if bundle_root.exists():
        shutil.rmtree(bundle_root)
    student_root = bundle_root / "student_schedules"
    attendance_root = bundle_root / "attendance"
    student_root.mkdir(parents=True, exist_ok=True)
    attendance_root.mkdir(parents=True, exist_ok=True)

    with session_scope(engine) as session:
        run = session.get(ScheduleRun, run_id)
        if run is None:
            raise LookupError(f"Schedule run {run_id} does not exist.")
        if run.status not in {"optimal", "feasible"}:
            raise ValueError("Only a feasible schedule can be exported.")
        event = session.get(Event, run.event_id)
        assignments = session.scalars(
            select(Assignment)
            .where(Assignment.run_id == run_id)
            .options(
                selectinload(Assignment.student),
                selectinload(Assignment.block),
                selectinload(Assignment.seminar_session).selectinload(
                    SeminarSession.seminar
                ),
            )
            .order_by(Assignment.student_id, Assignment.block_id)
        ).all()

        student_rows: dict[int, list[Assignment]] = defaultdict(list)
        attendance_rows: dict[tuple[int, int], list[Assignment]] = defaultdict(list)
        audit_records: list[dict] = []
        for assignment in assignments:
            student_rows[assignment.student_id].append(assignment)
            if assignment.seminar_session_id:
                attendance_rows[
                    (assignment.block.position, assignment.seminar_session_id)
                ].append(assignment)
            activity = "Lunch"
            presenter = ""
            room = ""
            if assignment.seminar_session:
                seminar = assignment.seminar_session.seminar
                activity = seminar.title
                presenter = seminar.presenter
                room = seminar.room
            audit_records.append(
                {
                    "student_id": assignment.student_id,
                    "student": assignment.student.full_name,
                    "email": assignment.student.email,
                    "grade": assignment.student.grade,
                    "period": assignment.block.position,
                    "activity": activity,
                    "presenter": presenter,
                    "room": room,
                    "preference_rank": assignment.preference_rank,
                }
            )

        master_records: list[dict] = []
        for student_id, rows in student_rows.items():
            student = rows[0].student
            record = {
                "student_id": student_id,
                "student": student.full_name,
                "email": student.email,
                "grade": student.grade,
            }
            pdf = _new_pdf(
                f"Schedule for {student.full_name}",
                f"{event.school_name} | {event.name} | Grade {student.grade}",
            )
            for assignment in sorted(rows, key=lambda item: item.block.position):
                activity = "Lunch"
                detail = "Balanced lunch group"
                if assignment.seminar_session:
                    seminar = assignment.seminar_session.seminar
                    activity = seminar.title
                    detail = f"{seminar.presenter} | {seminar.room}"
                record[f"period_{assignment.block.position}"] = activity
                pdf.set_fill_color(241, 247, 255)
                pdf.set_text_color(13, 33, 79)
                pdf.set_font("Helvetica", style="B", size=11)
                pdf.cell(
                    28,
                    10,
                    pdf_text(f"Period {assignment.block.position}"),
                    border=0,
                    fill=True,
                )
                pdf.cell(0, 10, pdf_text(activity), new_x="LMARGIN", new_y="NEXT", fill=True)
                pdf.set_text_color(74, 96, 128)
                pdf.set_font("Helvetica", size=9)
                pdf.cell(28)
                pdf.cell(0, 6, pdf_text(detail), new_x="LMARGIN", new_y="NEXT")
                pdf.ln(2)
            filename = f"{student_id:04d}_{safe_filename(student.full_name)}.pdf"
            pdf.output(str(student_root / filename))
            master_records.append(record)

        attendance_pdf_count = 0
        for (period, _session_id), rows in sorted(attendance_rows.items()):
            session_row = rows[0].seminar_session
            seminar = session_row.seminar
            period_root = attendance_root / f"period_{period}"
            period_root.mkdir(parents=True, exist_ok=True)
            pdf = _new_pdf(
                f"{seminar.title} attendance",
                f"Period {period} | {seminar.presenter} | {seminar.room} | "
                f"{len(rows)}/{session_row.capacity} students",
            )
            pdf.set_font("Helvetica", size=10)
            for number, assignment in enumerate(
                sorted(rows, key=lambda item: item.student.full_name.casefold()), start=1
            ):
                pdf.cell(
                    0,
                    7,
                    pdf_text(f"{number:>2}.  {assignment.student.full_name}  "
                             f"(Grade {assignment.student.grade})"),
                    new_x="LMARGIN",
                    new_y="NEXT",
                )
            pdf.output(str(period_root / f"{safe_filename(seminar.title)}.pdf"))
            attendance_pdf_count += 1

        master_frame = pd.DataFrame(master_records).sort_values("student")
        audit_frame = pd.DataFrame(audit_records).sort_values(["student", "period"])
        master_frame.to_csv(bundle_root / "master_schedule.csv", index=False)
        audit_frame.to_csv(bundle_root / "assignment_audit.csv", index=False)
        with pd.ExcelWriter(bundle_root / "seminar_day_schedule.xlsx", engine="openpyxl") as writer:
            master_frame.to_excel(writer, sheet_name="Student schedules", index=False)
            audit_frame.to_excel(writer, sheet_name="Assignment audit", index=False)

        summary = {
            "run_id": run.id,
            "status": run.status,
            "solver_status": run.solver_status,
            "student_count": len(student_rows),
            "assignment_count": len(assignments),
            "satisfaction": run.satisfaction,
            "configuration": run.configuration,
        }
        (bundle_root / "schedule_summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )

    archive_path = export_root / f"seminar-day-schedule-run-{run_id}.zip"
    if archive_path.exists():
        archive_path.unlink()
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(bundle_root.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(bundle_root))
    return ExportBundle(
        run_id=run_id,
        root=bundle_root,
        archive_path=archive_path,
        student_pdf_count=len(student_rows),
        attendance_pdf_count=attendance_pdf_count,
    )

