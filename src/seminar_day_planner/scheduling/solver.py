from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime

from ortools.sat.python import cp_model
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, selectinload

from seminar_day_planner.database.engine import session_scope
from seminar_day_planner.database.models import (
    Assignment,
    Event,
    ScheduleRun,
    Seminar,
    SeminarSession,
    Student,
)
from seminar_day_planner.types import (
    AssignmentRecord,
    ScheduleDiagnostics,
    ScheduleResult,
    SchedulingConfiguration,
)


@dataclass(frozen=True, slots=True)
class SchedulingStudent:
    id: int
    full_name: str
    email: str
    grade: int
    submitted_at: datetime
    preferences: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class SchedulingSession:
    id: int
    seminar_id: int
    title: str
    presenter: str
    room: str
    block_id: int
    block_position: int
    capacity: int


@dataclass(frozen=True, slots=True)
class SchedulingProblem:
    event_id: int
    blocks: tuple[tuple[int, int], ...]
    students: tuple[SchedulingStudent, ...]
    sessions: tuple[SchedulingSession, ...]


def load_scheduling_problem(session: Session, event_id: int) -> SchedulingProblem:
    event = session.scalar(
        select(Event)
        .where(Event.id == event_id)
        .options(selectinload(Event.blocks))
    )
    if event is None:
        raise LookupError(f"Event {event_id} does not exist.")

    student_rows = session.scalars(
        select(Student)
        .where(Student.event_id == event_id)
        .options(selectinload(Student.preferences))
        .order_by(Student.submitted_at, Student.id)
    ).all()
    students = tuple(
        SchedulingStudent(
            id=row.id,
            full_name=row.full_name,
            email=row.email,
            grade=row.grade,
            submitted_at=row.submitted_at,
            preferences=tuple(
                preference.seminar_id
                for preference in sorted(row.preferences, key=lambda item: item.rank)
            ),
        )
        for row in student_rows
    )

    session_rows = session.scalars(
        select(SeminarSession)
        .join(Seminar)
        .where(Seminar.event_id == event_id, Seminar.active.is_(True))
        .options(
            selectinload(SeminarSession.seminar),
            selectinload(SeminarSession.block),
        )
    ).all()
    sessions = tuple(
        SchedulingSession(
            id=row.id,
            seminar_id=row.seminar_id,
            title=row.seminar.title,
            presenter=row.seminar.presenter,
            room=row.seminar.room,
            block_id=row.block_id,
            block_position=row.block.position,
            capacity=row.capacity,
        )
        for row in session_rows
    )
    blocks = tuple((block.id, block.position) for block in sorted(event.blocks, key=lambda x: x.position))
    return SchedulingProblem(event_id=event_id, blocks=blocks, students=students, sessions=sessions)


def preflight_schedule(
    problem: SchedulingProblem,
    configuration: SchedulingConfiguration,
) -> ScheduleDiagnostics:
    diagnostics = ScheduleDiagnostics()
    if not problem.students:
        diagnostics.errors.append("Import at least one student before generating a schedule.")
    if not problem.sessions:
        diagnostics.errors.append("Add seminar sessions before generating a schedule.")
        return diagnostics
    if len(problem.blocks) != 4:
        diagnostics.errors.append("This version requires exactly four total periods.")
    block_positions = {position for _, position in problem.blocks}
    if not set(configuration.lunch_blocks).issubset(block_positions):
        diagnostics.errors.append("Lunch blocks must be valid event periods.")

    distinct_seminars = {item.seminar_id for item in problem.sessions}
    if len(distinct_seminars) < configuration.required_seminars:
        diagnostics.errors.append(
            f"At least {configuration.required_seminars} different seminars are required."
        )

    capacity_by_block: dict[int, int] = defaultdict(int)
    seen_rooms: dict[tuple[int, str], str] = {}
    seen_presenters: dict[tuple[int, str], str] = {}
    for item in problem.sessions:
        effective_capacity = item.capacity
        if configuration.maximum_seminar_size:
            effective_capacity = min(effective_capacity, configuration.maximum_seminar_size)
        capacity_by_block[item.block_position] += effective_capacity

        room_key = (item.block_position, item.room.casefold())
        presenter_key = (item.block_position, item.presenter.casefold())
        if room_key in seen_rooms:
            diagnostics.errors.append(
                f"Period {item.block_position} has two seminars in {item.room}: "
                f"{seen_rooms[room_key]} and {item.title}."
            )
        else:
            seen_rooms[room_key] = item.title
        if presenter_key in seen_presenters:
            diagnostics.errors.append(
                f"{item.presenter} is assigned to two seminars in period "
                f"{item.block_position}."
            )
        else:
            seen_presenters[presenter_key] = item.title

    student_count = len(problem.students)
    lunch_a, lunch_b = configuration.lunch_blocks
    for _, position in problem.blocks:
        required = student_count
        if position in {lunch_a, lunch_b}:
            required = student_count // 2
        diagnostics.capacity_by_block[position] = capacity_by_block[position]
        diagnostics.required_seats_by_block[position] = required
        if capacity_by_block[position] < required:
            diagnostics.errors.append(
                f"Period {position} needs {required} seminar seats but only has "
                f"{capacity_by_block[position]}."
            )

    incomplete_students = sum(
        len(set(student.preferences)) < configuration.required_seminars
        for student in problem.students
    )
    if incomplete_students:
        diagnostics.warnings.append(
            f"{incomplete_students} students ranked fewer than "
            f"{configuration.required_seminars} different seminars."
        )
    return diagnostics


def build_schedule_model(
    problem: SchedulingProblem,
    configuration: SchedulingConfiguration,
) -> tuple[
    cp_model.CpModel,
    dict[tuple[int, int], cp_model.IntVar],
    dict[tuple[int, int], cp_model.IntVar],
]:
    model = cp_model.CpModel()
    sessions_by_block: dict[int, list[SchedulingSession]] = defaultdict(list)
    sessions_by_seminar: dict[int, list[SchedulingSession]] = defaultdict(list)
    for item in problem.sessions:
        sessions_by_block[item.block_position].append(item)
        sessions_by_seminar[item.seminar_id].append(item)

    assignment_variables: dict[tuple[int, int], cp_model.IntVar] = {}
    lunch_variables: dict[tuple[int, int], cp_model.IntVar] = {}
    for student in problem.students:
        for item in problem.sessions:
            assignment_variables[(student.id, item.id)] = model.new_bool_var(
                f"student_{student.id}_session_{item.id}"
            )
        for lunch_block in configuration.lunch_blocks:
            lunch_variables[(student.id, lunch_block)] = model.new_bool_var(
                f"student_{student.id}_lunch_{lunch_block}"
            )

    for student in problem.students:
        for _, block_position in problem.blocks:
            period_assignments = [
                assignment_variables[(student.id, item.id)]
                for item in sessions_by_block[block_position]
            ]
            if block_position in configuration.lunch_blocks:
                period_assignments.append(lunch_variables[(student.id, block_position)])
            model.add(sum(period_assignments) == 1)
        model.add(
            sum(lunch_variables[(student.id, block)] for block in configuration.lunch_blocks)
            == 1
        )
        for seminar_sessions in sessions_by_seminar.values():
            model.add(
                sum(assignment_variables[(student.id, item.id)] for item in seminar_sessions)
                <= 1
            )

    for item in problem.sessions:
        capacity = item.capacity
        if configuration.maximum_seminar_size:
            capacity = min(capacity, configuration.maximum_seminar_size)
        model.add(
            sum(
                assignment_variables[(student.id, item.id)]
                for student in problem.students
            )
            <= capacity
        )

    first_lunch_block = configuration.lunch_blocks[0]
    first_lunch_count = sum(
        lunch_variables[(student.id, first_lunch_block)] for student in problem.students
    )
    model.add(first_lunch_count >= len(problem.students) // 2)
    model.add(first_lunch_count <= (len(problem.students) + 1) // 2)

    any_ranked_vars: list[cp_model.IntVar] = []
    top_two_vars: list[cp_model.IntVar] = []
    weighted_preference_terms = []
    tie_break_terms = []
    submission_order = {
        student.id: order for order, student in enumerate(problem.students)
    }
    maximum_priority = 1

    for student in problem.students:
        ranked_variables = []
        top_variables = []
        for rank, seminar_id in enumerate(student.preferences, start=1):
            weight = (
                configuration.preference_weights[rank - 1]
                if rank <= len(configuration.preference_weights)
                else 1
            )
            for item in sessions_by_seminar.get(seminar_id, []):
                variable = assignment_variables[(student.id, item.id)]
                ranked_variables.append(variable)
                weighted_preference_terms.append(variable * weight)
                if rank <= 2:
                    top_variables.append(variable)
                grade_component = (student.grade - 8) * len(problem.students)
                time_component = len(problem.students) - submission_order[student.id]
                priority = grade_component + time_component
                if configuration.prioritize_seniors:
                    priority += grade_component * 2
                if configuration.prioritize_earlier_submissions:
                    priority += time_component
                maximum_priority = max(maximum_priority, priority)
                tie_break_terms.append(variable * priority)

        any_ranked = model.new_bool_var(f"student_{student.id}_has_ranked")
        top_two = model.new_bool_var(f"student_{student.id}_has_top_two")
        any_ranked_vars.append(any_ranked)
        top_two_vars.append(top_two)
        if ranked_variables:
            model.add(sum(ranked_variables) >= any_ranked)
            model.add(sum(ranked_variables) <= configuration.required_seminars * any_ranked)
        else:
            model.add(any_ranked == 0)
        if top_variables:
            model.add(sum(top_variables) >= top_two)
            model.add(sum(top_variables) <= configuration.required_seminars * top_two)
        else:
            model.add(top_two == 0)

    student_count = len(problem.students)
    maximum_tie = max(1, student_count * configuration.required_seminars * maximum_priority)
    tie_base = maximum_tie + 1
    maximum_rank_score = (
        student_count * configuration.required_seminars * max(configuration.preference_weights)
    )
    top_two_multiplier = maximum_rank_score * tie_base + maximum_tie + 1
    any_ranked_multiplier = (
        student_count * top_two_multiplier
        + maximum_rank_score * tie_base
        + maximum_tie
        + 1
    )
    objective = (
        sum(any_ranked_vars) * any_ranked_multiplier
        + sum(top_two_vars) * top_two_multiplier
        + sum(weighted_preference_terms) * tie_base
        + sum(tie_break_terms)
    )
    model.maximize(objective)
    return model, assignment_variables, lunch_variables


def solve_schedule(
    problem: SchedulingProblem,
    configuration: SchedulingConfiguration,
) -> ScheduleResult:
    diagnostics = preflight_schedule(problem, configuration)
    if not diagnostics.is_ready:
        return ScheduleResult(
            status="invalid",
            solver_status="PRECHECK_FAILED",
            diagnostics=diagnostics,
        )

    model, assignment_variables, lunch_variables = build_schedule_model(
        problem, configuration
    )
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = configuration.time_limit_seconds
    solver.parameters.random_seed = configuration.random_seed
    solver.parameters.num_search_workers = 8
    status_code = solver.solve(model)
    solver_status = solver.status_name(status_code)
    if status_code not in {cp_model.OPTIMAL, cp_model.FEASIBLE}:
        diagnostics.errors.append(
            "The solver could not find a valid schedule. Review capacities and session availability."
        )
        return ScheduleResult(
            status="infeasible" if status_code == cp_model.INFEASIBLE else "unknown",
            solver_status=solver_status,
            diagnostics=diagnostics,
        )

    session_by_id = {item.id: item for item in problem.sessions}
    block_id_by_position = {position: block_id for block_id, position in problem.blocks}
    assignments: list[AssignmentRecord] = []
    best_ranks: dict[int, int | None] = {student.id: None for student in problem.students}
    preference_maps = {
        student.id: {seminar_id: rank for rank, seminar_id in enumerate(student.preferences, start=1)}
        for student in problem.students
    }
    for student in problem.students:
        for item in problem.sessions:
            if solver.value(assignment_variables[(student.id, item.id)]):
                assignments.append(
                    AssignmentRecord(
                        student_id=student.id,
                        block_id=item.block_id,
                        activity_type="seminar",
                        seminar_session_id=item.id,
                    )
                )
                rank = preference_maps[student.id].get(session_by_id[item.id].seminar_id)
                if rank is not None and (
                    best_ranks[student.id] is None or rank < best_ranks[student.id]
                ):
                    best_ranks[student.id] = rank
        for block_position in configuration.lunch_blocks:
            if solver.value(lunch_variables[(student.id, block_position)]):
                assignments.append(
                    AssignmentRecord(
                        student_id=student.id,
                        block_id=block_id_by_position[block_position],
                        activity_type="lunch",
                    )
                )

    counts = Counter(best_ranks.values())
    lunch_counts = Counter(
        next(position for block_id, position in problem.blocks if block_id == item.block_id)
        for item in assignments
        if item.activity_type == "lunch"
    )
    satisfaction = {
        "students_total": len(problem.students),
        "students_with_ranked": len(problem.students) - counts[None],
        "students_with_top_two": counts[1] + counts[2],
        "first_choice": counts[1],
        "second_choice": counts[2],
        "third_choice": counts[3],
        "fourth_or_lower": sum(count for rank, count in counts.items() if rank and rank >= 4),
        "unranked": counts[None],
        "lunch_block_2": lunch_counts[2],
        "lunch_block_3": lunch_counts[3],
    }
    return ScheduleResult(
        status="optimal" if status_code == cp_model.OPTIMAL else "feasible",
        solver_status=solver_status,
        assignments=assignments,
        satisfaction=satisfaction,
        objective_value=solver.objective_value,
        diagnostics=diagnostics,
    )


def generate_and_persist_schedule(
    engine: Engine,
    event_id: int,
    configuration: SchedulingConfiguration,
) -> tuple[int, ScheduleResult]:
    with session_scope(engine) as session:
        problem = load_scheduling_problem(session, event_id)
        result = solve_schedule(problem, configuration)
        run = ScheduleRun(
            event_id=event_id,
            status=result.status,
            solver_status=result.solver_status,
            configuration=configuration.model_dump(mode="json"),
            satisfaction=result.satisfaction,
            diagnostics=result.diagnostics.model_dump(mode="json"),
            objective_value=result.objective_value,
            random_seed=configuration.random_seed,
        )
        session.add(run)
        session.flush()

        rank_lookup = {
            (student.id, preference.seminar_id): preference.rank
            for student in session.scalars(
                select(Student)
                .where(Student.event_id == event_id)
                .options(selectinload(Student.preferences))
            ).all()
            for preference in student.preferences
        }
        seminar_by_session = {
            row.id: row.seminar_id
            for row in session.scalars(
                select(SeminarSession).join(Seminar).where(Seminar.event_id == event_id)
            ).all()
        }
        for item in result.assignments:
            preference_rank = None
            if item.seminar_session_id:
                preference_rank = rank_lookup.get(
                    (item.student_id, seminar_by_session[item.seminar_session_id])
                )
            session.add(
                Assignment(
                    run_id=run.id,
                    student_id=item.student_id,
                    block_id=item.block_id,
                    activity_type=item.activity_type,
                    seminar_session_id=item.seminar_session_id,
                    preference_rank=preference_rank,
                )
            )
        session.flush()
        run_id = run.id
    return run_id, result


def validate_schedule(session: Session, run_id: int) -> list[str]:
    errors: list[str] = []
    run = session.get(ScheduleRun, run_id)
    if run is None:
        return [f"Schedule run {run_id} does not exist."]
    event = session.get(Event, run.event_id)
    assignments = session.scalars(
        select(Assignment)
        .where(Assignment.run_id == run_id)
        .options(
            selectinload(Assignment.block),
            selectinload(Assignment.seminar_session),
        )
    ).all()
    students = session.scalars(select(Student).where(Student.event_id == run.event_id)).all()
    by_student: dict[int, list[Assignment]] = defaultdict(list)
    by_session: Counter[int] = Counter()
    for item in assignments:
        by_student[item.student_id].append(item)
        if item.seminar_session_id:
            by_session[item.seminar_session_id] += 1

    for student in students:
        rows = by_student[student.id]
        if len(rows) != event.total_blocks:
            errors.append(f"{student.full_name} does not have {event.total_blocks} activities.")
            continue
        if len({row.block_id for row in rows}) != event.total_blocks:
            errors.append(f"{student.full_name} has more than one activity in a period.")
        lunches = [row for row in rows if row.activity_type == "lunch"]
        if len(lunches) != 1 or lunches[0].block.position not in {
            event.lunch_block_a,
            event.lunch_block_b,
        }:
            errors.append(f"{student.full_name} has an invalid lunch assignment.")
        seminar_ids = [
            row.seminar_session.seminar_id
            for row in rows
            if row.seminar_session is not None
        ]
        if len(seminar_ids) != event.seminars_per_student:
            errors.append(f"{student.full_name} does not have three seminars.")
        if len(seminar_ids) != len(set(seminar_ids)):
            errors.append(f"{student.full_name} was assigned the same seminar twice.")

    capacities = {
        row.id: row.capacity
        for row in session.scalars(
            select(SeminarSession).join(Seminar).where(Seminar.event_id == run.event_id)
        ).all()
    }
    for session_id, count in by_session.items():
        if count > capacities[session_id]:
            errors.append(
                f"Seminar session {session_id} has {count} students for {capacities[session_id]} seats."
            )

    lunch_counts = Counter(
        row.block.position
        for row in assignments
        if row.activity_type == "lunch"
    )
    if abs(lunch_counts[event.lunch_block_a] - lunch_counts[event.lunch_block_b]) > 1:
        errors.append("Lunch groups differ by more than one student.")
    return errors
