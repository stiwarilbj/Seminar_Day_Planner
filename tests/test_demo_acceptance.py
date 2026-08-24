from __future__ import annotations

from seminar_day_planner.database import session_scope
from seminar_day_planner.demo import seed_demo_data
from seminar_day_planner.scheduling.solver import generate_and_persist_schedule, validate_schedule
from seminar_day_planner.types import SchedulingConfiguration


def test_248_student_demo_acceptance(engine) -> None:
    with session_scope(engine) as session:
        event_id = seed_demo_data(session)
    run_id, result = generate_and_persist_schedule(
        engine,
        event_id,
        SchedulingConfiguration(event_id=event_id, time_limit_seconds=45),
    )
    assert result.status in {"optimal", "feasible"}
    assert result.satisfaction["students_total"] == 248
    assert abs(
        result.satisfaction["lunch_block_2"] - result.satisfaction["lunch_block_3"]
    ) <= 1
    with session_scope(engine) as session:
        assert validate_schedule(session, run_id) == []

