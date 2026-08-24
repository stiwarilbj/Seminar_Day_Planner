from __future__ import annotations

import zipfile

from seminar_day_planner.exports import export_schedule_bundle
from seminar_day_planner.scheduling.solver import generate_and_persist_schedule
from seminar_day_planner.types import SchedulingConfiguration
from tests.test_solver import seed_small_problem


def test_export_bundle_contains_all_output_types(engine, tmp_path) -> None:
    event_id = seed_small_problem(engine)
    run_id, result = generate_and_persist_schedule(
        engine,
        event_id,
        SchedulingConfiguration(event_id=event_id, time_limit_seconds=10),
    )
    assert result.status in {"optimal", "feasible"}
    bundle = export_schedule_bundle(engine, run_id, tmp_path)
    assert bundle.student_pdf_count == 8
    assert bundle.attendance_pdf_count > 0
    assert (bundle.root / "master_schedule.csv").exists()
    assert (bundle.root / "seminar_day_schedule.xlsx").exists()
    assert (bundle.root / "assignment_audit.csv").exists()
    with zipfile.ZipFile(bundle.archive_path) as archive:
        names = archive.namelist()
    assert "master_schedule.csv" in names
    assert any(name.startswith("student_schedules/") and name.endswith(".pdf") for name in names)

