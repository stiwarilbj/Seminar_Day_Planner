from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StudentImportRow(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=254)
    grade: int = Field(ge=9, le=12)
    preferences: list[str] = Field(min_length=1, max_length=12)
    submitted_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )
    external_id: str | None = None

    @field_validator("email")
    @classmethod
    def email_must_have_valid_syntax(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized):
            raise ValueError("Enter a valid email address.")
        return normalized

    @field_validator("preferences")
    @classmethod
    def choices_must_be_unique(cls, value: list[str]) -> list[str]:
        normalized = [choice.strip() for choice in value if choice.strip()]
        if len({choice.casefold() for choice in normalized}) != len(normalized):
            raise ValueError("Choose each seminar only once.")
        return normalized


class SeminarImportRow(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=2, max_length=160)
    presenter: str = Field(min_length=2, max_length=120)
    room: str = Field(min_length=1, max_length=80)
    capacity: int = Field(ge=1, le=500)
    periods: list[int] = Field(min_length=1, max_length=12)
    description: str = Field(default="", max_length=1000)

    @field_validator("periods")
    @classmethod
    def periods_must_be_unique_and_positive(cls, value: list[int]) -> list[int]:
        if any(period < 1 for period in value):
            raise ValueError("Periods start at 1.")
        return sorted(set(value))


class EventConfiguration(BaseModel):
    name: str = "Seminar Day"
    school_name: str = "Dover-Sherborn High School"
    event_date: date | None = None
    total_blocks: int = 4
    seminars_per_student: int = 3
    preference_count: int = 6
    lunch_enabled: bool = True
    lunch_blocks: tuple[int, int] = (2, 3)


class SchedulingConfiguration(BaseModel):
    event_id: int
    required_seminars: int = 3
    lunch_blocks: tuple[int, int] = (2, 3)
    preference_weights: tuple[int, ...] = (100, 60, 35, 20, 10, 5)
    maximum_seminar_size: int | None = None
    prioritize_seniors: bool = False
    prioritize_earlier_submissions: bool = False
    balance_lunch: bool = True
    random_seed: int = 42
    time_limit_seconds: float = 45.0


class ScheduleDiagnostics(BaseModel):
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    capacity_by_block: dict[int, int] = Field(default_factory=dict)
    required_seats_by_block: dict[int, int] = Field(default_factory=dict)

    @property
    def is_ready(self) -> bool:
        return not self.errors


class AssignmentRecord(BaseModel):
    student_id: int
    block_id: int
    activity_type: Literal["seminar", "lunch"]
    seminar_session_id: int | None = None


class ScheduleResult(BaseModel):
    status: Literal["optimal", "feasible", "infeasible", "invalid", "unknown"]
    solver_status: str
    assignments: list[AssignmentRecord] = Field(default_factory=list)
    satisfaction: dict[str, int] = Field(default_factory=dict)
    objective_value: float | None = None
    diagnostics: ScheduleDiagnostics = Field(default_factory=ScheduleDiagnostics)


class ImportRowPreview(BaseModel):
    row_number: int
    target_type: Literal["student", "seminar"]
    normalized_data: dict
    status: Literal["valid", "warning", "error"]
    messages: list[str] = Field(default_factory=list)


class ImportPreview(BaseModel):
    source_type: str
    target_type: Literal["student", "seminar"]
    rows: list[ImportRowPreview]
    field_mappings: dict[str, str] = Field(default_factory=dict)

    @property
    def error_count(self) -> int:
        return sum(row.status == "error" for row in self.rows)

    @property
    def warning_count(self) -> int:
        return sum(row.status == "warning" for row in self.rows)

    @property
    def ready_count(self) -> int:
        return sum(row.status != "error" for row in self.rows)
