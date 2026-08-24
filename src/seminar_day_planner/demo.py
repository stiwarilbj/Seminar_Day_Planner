from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from seminar_day_planner.database.models import Seminar, Student
from seminar_day_planner.database.repository import (
    ensure_default_event,
    upsert_seminar,
    upsert_student,
)
from seminar_day_planner.types import SeminarImportRow, StudentImportRow

DEMO_SEMINARS: tuple[tuple[str, str, str, int], ...] = (
    ("Robotics Lab", "Mr. Harris", "Engineering 201", 18),
    ("Sports Medicine", "Nurse Patel", "Health 114", 18),
    ("Local Journalism", "Ms. Baker", "Library Lab", 18),
    ("Intro to Architecture", "Mr. Diaz", "Art 108", 18),
    ("Climate Science", "Dr. Okafor", "Science 302", 18),
    ("Film Scoring", "Mr. Chen", "Music 120", 18),
    ("Emergency Medicine", "Dr. Silva", "Science 305", 18),
    ("Creative Coding", "Ms. Rivera", "Computer Lab", 18),
    ("Marine Biology", "Dr. Brooks", "Science 210", 18),
    ("Personal Finance", "Ms. Williams", "Room 214", 18),
    ("Mock Trial", "Attorney Lewis", "Auditorium A", 18),
    ("Digital Photography", "Mr. Kim", "Media Studio", 18),
    ("Sports Analytics", "Coach Morgan", "Room 118", 18),
    ("Psychology in Action", "Dr. Green", "Room 220", 18),
    ("Graphic Design", "Ms. Thompson", "Art 106", 18),
    ("Entrepreneurship", "Ms. Jackson", "Room 202", 18),
    ("Forensic Science", "Dr. Martinez", "Science 308", 18),
    ("Sustainable Engineering", "Mr. Wilson", "Maker Space", 18),
)

FIRST_NAMES = (
    "Maya",
    "Liam",
    "Sophia",
    "Mateo",
    "Olivia",
    "Ethan",
    "Isabella",
    "Noah",
    "Ava",
    "Lucas",
    "Amelia",
    "James",
    "Harper",
    "Elijah",
    "Mia",
    "Henry",
)

LAST_NAMES = (
    "Anderson",
    "Baker",
    "Chen",
    "Diaz",
    "Evans",
    "Foster",
    "Garcia",
    "Harris",
    "Ibrahim",
    "Johnson",
    "Kowalski",
    "Lee",
    "Miller",
    "Nguyen",
    "Owens",
    "Patel",
)


def seed_demo_data(session: Session, student_count: int = 248, seed: int = 42) -> int:
    event = ensure_default_event(session)
    existing_students = session.scalar(
        select(func.count(Student.id)).where(Student.event_id == event.id)
    )
    existing_seminars = session.scalar(
        select(func.count(Seminar.id)).where(Seminar.event_id == event.id)
    )
    if existing_students and existing_seminars:
        return event.id

    for title, presenter, room, capacity in DEMO_SEMINARS:
        upsert_seminar(
            session,
            event.id,
            SeminarImportRow(
                title=title,
                presenter=presenter,
                room=room,
                capacity=capacity,
                periods=[1, 2, 3, 4],
                description="A fictional demo seminar used to test the planner.",
            ),
        )

    rng = random.Random(seed)
    seminar_titles = [item[0] for item in DEMO_SEMINARS]
    base_time = datetime(2026, 8, 1, 8, 0, tzinfo=UTC)
    for index in range(student_count):
        first = FIRST_NAMES[index % len(FIRST_NAMES)]
        last = LAST_NAMES[(index // len(FIRST_NAMES)) % len(LAST_NAMES)]
        suffix = index // (len(FIRST_NAMES) * len(LAST_NAMES))
        full_name = f"{first} {last}" if suffix == 0 else f"{first} {last} {suffix + 1}"
        choices = seminar_titles.copy()
        rng.shuffle(choices)
        upsert_student(
            session,
            event.id,
            StudentImportRow(
                full_name=full_name,
                email=f"student{index + 1:03d}@student.example.test",
                grade=9 + (index % 4),
                preferences=choices[:6],
                submitted_at=base_time + timedelta(minutes=index),
                external_id=f"DEMO-{index + 1:03d}",
            ),
        )
    session.flush()
    return event.id

