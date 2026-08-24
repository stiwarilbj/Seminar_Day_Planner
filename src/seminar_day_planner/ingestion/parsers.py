from __future__ import annotations

import io
import json
import re
import sqlite3
from datetime import UTC, datetime
from difflib import SequenceMatcher, get_close_matches
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from pydantic import ValidationError

from seminar_day_planner.types import (
    ImportPreview,
    ImportRowPreview,
    SeminarImportRow,
    StudentImportRow,
)

TargetType = Literal["student", "seminar"]

HEADER_ALIASES = {
    "fullname": "full_name",
    "studentname": "full_name",
    "name": "full_name",
    "emailaddress": "email",
    "schoolemail": "email",
    "email": "email",
    "gradelevel": "grade",
    "grade": "grade",
    "timestamp": "submitted_at",
    "submittedat": "submitted_at",
    "submissiontime": "submitted_at",
    "studentid": "external_id",
    "externalid": "external_id",
    "classname": "title",
    "seminarname": "title",
    "seminar": "title",
    "title": "title",
    "teacher": "presenter",
    "speaker": "presenter",
    "presenter": "presenter",
    "roomnumber": "room",
    "location": "room",
    "room": "room",
    "cap": "capacity",
    "maxstudents": "capacity",
    "capacity": "capacity",
    "availableperiods": "periods",
    "offeredperiods": "periods",
    "periods": "periods",
    "description": "description",
}


def canonical_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).strip().casefold())


def _validation_messages(error: ValidationError) -> list[str]:
    return [
        f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
        for item in error.errors()
    ]


def _coerce_datetime(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)) or str(value).strip() == "":
        return datetime.now(UTC).isoformat()
    parsed = pd.to_datetime(value, utc=True, errors="raise")
    return parsed.to_pydatetime().isoformat()


def _parse_periods(value: Any) -> list[int]:
    if isinstance(value, list):
        return [int(item) for item in value]
    return [int(item) for item in re.findall(r"\d+", str(value))]


def _closest_seminar(choice: str, known_seminars: list[str]) -> str | None:
    direct_matches = get_close_matches(choice, known_seminars, n=1, cutoff=0.62)
    if direct_matches:
        return direct_matches[0]
    ignored_words = {"a", "and", "in", "intro", "lab", "of", "the", "to"}
    choice_tokens = set(re.findall(r"[a-z0-9]+", choice.casefold())) - ignored_words
    scored: list[tuple[float, str]] = []
    for candidate in known_seminars:
        candidate_tokens = set(re.findall(r"[a-z0-9]+", candidate.casefold())) - ignored_words
        shared = choice_tokens & candidate_tokens
        union = choice_tokens | candidate_tokens
        token_score = len(shared) / len(union) if union else 0
        sequence_score = SequenceMatcher(None, choice.casefold(), candidate.casefold()).ratio()
        scored.append((token_score * 0.75 + sequence_score * 0.25, candidate))
    best_score, best_candidate = max(scored, default=(0, ""))
    return best_candidate if best_score >= 0.38 else None


def _student_from_mapping(
    raw: dict[str, Any],
    row_number: int,
    known_seminars: list[str] | None,
) -> ImportRowPreview:
    mapped: dict[str, Any] = {}
    preferences: list[tuple[int, str]] = []
    for header, value in raw.items():
        normalized_header = canonical_header(header)
        preference_match = re.fullmatch(r"(?:pref(?:erence)?|choice)(\d+)", normalized_header)
        if preference_match:
            if value is not None and str(value).strip():
                preferences.append((int(preference_match.group(1)), str(value).strip()))
            continue
        target = HEADER_ALIASES.get(normalized_header)
        if target:
            mapped[target] = value

    if "preferences" in raw and isinstance(raw["preferences"], list):
        preferences = list(enumerate((str(item) for item in raw["preferences"]), start=1))
    preferences.sort(key=lambda item: item[0])
    mapped["preferences"] = [value for _, value in preferences]
    mapped["submitted_at"] = _coerce_datetime(mapped.get("submitted_at"))
    if mapped.get("grade") is not None and str(mapped["grade"]).strip():
        try:
            mapped["grade"] = int(float(mapped["grade"]))
        except (TypeError, ValueError):
            pass

    messages: list[str] = []
    status: Literal["valid", "warning", "error"] = "valid"
    if known_seminars:
        canonical = {item.casefold(): item for item in known_seminars}
        corrected: list[str] = []
        for choice in mapped.get("preferences", []):
            if choice.casefold() in canonical:
                corrected.append(canonical[choice.casefold()])
                continue
            match = _closest_seminar(choice, known_seminars)
            if match:
                corrected.append(match)
                status = "warning"
                messages.append(f"Mapped unknown seminar '{choice}' to '{match}'.")
            else:
                corrected.append(choice)
                status = "error"
                messages.append(f"Unknown seminar: {choice}")
        mapped["preferences"] = corrected

    try:
        validated = StudentImportRow.model_validate(mapped)
        mapped = validated.model_dump(mode="json")
    except (ValidationError, ValueError) as error:
        status = "error"
        if isinstance(error, ValidationError):
            messages.extend(_validation_messages(error))
        else:
            messages.append(str(error))
    return ImportRowPreview(
        row_number=row_number,
        target_type="student",
        normalized_data=mapped,
        status=status,
        messages=messages,
    )


def _seminar_from_mapping(raw: dict[str, Any], row_number: int) -> ImportRowPreview:
    mapped: dict[str, Any] = {}
    for header, value in raw.items():
        target = HEADER_ALIASES.get(canonical_header(header))
        if target:
            mapped[target] = value
    if "periods" in mapped:
        mapped["periods"] = _parse_periods(mapped["periods"])
    if "capacity" in mapped:
        try:
            mapped["capacity"] = int(float(mapped["capacity"]))
        except (TypeError, ValueError):
            pass
    messages: list[str] = []
    status: Literal["valid", "error"] = "valid"
    try:
        validated = SeminarImportRow.model_validate(mapped)
        mapped = validated.model_dump(mode="json")
    except ValidationError as error:
        status = "error"
        messages.extend(_validation_messages(error))
    return ImportRowPreview(
        row_number=row_number,
        target_type="seminar",
        normalized_data=mapped,
        status=status,
        messages=messages,
    )


def _records_to_preview(
    records: list[dict[str, Any]],
    source_type: str,
    target_type: TargetType,
    known_seminars: list[str] | None = None,
) -> ImportPreview:
    converter = _student_from_mapping if target_type == "student" else _seminar_from_mapping
    rows = []
    for index, record in enumerate(records, start=1):
        if target_type == "student":
            rows.append(converter(record, index, known_seminars))
        else:
            rows.append(converter(record, index))
    field_mappings: dict[str, str] = {}
    if records:
        for header in records[0]:
            normalized_header = canonical_header(header)
            preference_match = re.fullmatch(
                r"(?:pref(?:erence)?|choice)(\d+)", normalized_header
            )
            if preference_match:
                field_mappings[str(header)] = f"preference {preference_match.group(1)}"
            elif normalized_header == "preferences":
                field_mappings[str(header)] = "preferences"
            elif target := HEADER_ALIASES.get(normalized_header):
                field_mappings[str(header)] = target
            else:
                field_mappings[str(header)] = "ignored"
    return ImportPreview(
        source_type=source_type,
        target_type=target_type,
        rows=rows,
        field_mappings=field_mappings,
    )


def parse_delimited_bytes(
    content: bytes,
    target_type: TargetType,
    known_seminars: list[str] | None = None,
) -> ImportPreview:
    dataframe = pd.read_csv(io.BytesIO(content), sep=None, engine="python")
    records = dataframe.where(pd.notnull(dataframe), None).to_dict(orient="records")
    return _records_to_preview(records, "csv", target_type, known_seminars)


def parse_spreadsheet_bytes(
    content: bytes,
    target_type: TargetType,
    known_seminars: list[str] | None = None,
) -> ImportPreview:
    dataframe = pd.read_excel(io.BytesIO(content))
    records = dataframe.where(pd.notnull(dataframe), None).to_dict(orient="records")
    return _records_to_preview(records, "excel", target_type, known_seminars)


def parse_json_bytes(
    content: bytes,
    target_type: TargetType,
    known_seminars: list[str] | None = None,
) -> ImportPreview:
    parsed = json.loads(content.decode("utf-8"))
    if isinstance(parsed, dict):
        plural_key = "students" if target_type == "student" else "seminars"
        parsed = parsed.get(plural_key, parsed.get("rows", []))
    if not isinstance(parsed, list) or not all(isinstance(item, dict) for item in parsed):
        raise ValueError("JSON must contain a list of student or seminar objects.")
    return _records_to_preview(parsed, "json", target_type, known_seminars)


def parse_sqlite_table(
    database_path: Path,
    target_type: TargetType,
    table_name: str | None = None,
    known_seminars: list[str] | None = None,
) -> ImportPreview:
    uri = f"file:{database_path.resolve()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        if not tables:
            raise ValueError("The SQLite file has no readable tables.")
        selected = table_name or tables[0]
        if selected not in tables:
            raise ValueError(f"Unknown SQLite table: {selected}")
        quoted = selected.replace('"', '""')
        cursor = connection.execute(f'SELECT * FROM "{quoted}"')
        columns = [item[0] for item in cursor.description]
        records = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
    return _records_to_preview(records, "sqlite", target_type, known_seminars)


STUDENT_LINE = re.compile(
    r"^(?P<name>[^,]+),\s*grade\s+(?P<grade>9|10|11|12)"
    r"(?:,\s*(?P<email>[^,\s]+@[^,\s]+))?"
    r"\s*,?\s*(?:wants|prefers)\s+(?P<preferences>.+)$",
    flags=re.IGNORECASE,
)

SEMINAR_LINE = re.compile(
    r"^(?P<title>.+?)\s+with\s+(?P<presenter>.+?)\s+in\s+(?P<room>.+?),\s*"
    r"capacity\s+(?P<capacity>\d+),\s*periods?\s+(?P<periods>.+)$",
    flags=re.IGNORECASE,
)


def parse_natural_language(
    text: str,
    target_type: TargetType,
    known_seminars: list[str] | None = None,
) -> ImportPreview:
    rows: list[ImportRowPreview] = []
    for row_number, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        pattern = STUDENT_LINE if target_type == "student" else SEMINAR_LINE
        match = pattern.match(line)
        if not match:
            rows.append(
                ImportRowPreview(
                    row_number=row_number,
                    target_type=target_type,
                    normalized_data={"source_text": line},
                    status="error",
                    messages=["Could not understand this line. Check the import guide format."],
                )
            )
            continue
        values = match.groupdict()
        if target_type == "student":
            preferences = re.split(r"\s*(?:>|,|\bthen\b)\s*", values["preferences"])
            raw = {
                "Name": values["name"],
                "Grade": values["grade"],
                "Email": values.get("email") or "",
                "preferences": [item for item in preferences if item],
            }
            rows.append(_student_from_mapping(raw, row_number, known_seminars))
        else:
            raw = {
                "Title": values["title"],
                "Presenter": values["presenter"],
                "Room": values["room"],
                "Capacity": values["capacity"],
                "Periods": values["periods"],
            }
            rows.append(_seminar_from_mapping(raw, row_number))
    field_mappings = (
        {
            "name phrase": "full_name",
            "grade phrase": "grade",
            "email phrase": "email",
            "wants phrase": "preferences",
        }
        if target_type == "student"
        else {
            "title phrase": "title",
            "with phrase": "presenter",
            "in phrase": "room",
            "capacity phrase": "capacity",
            "periods phrase": "periods",
        }
    )
    return ImportPreview(
        source_type="natural_language",
        target_type=target_type,
        rows=rows,
        field_mappings=field_mappings,
    )


def parse_scheduling_rule(text: str) -> tuple[dict[str, bool], list[str]]:
    normalized = " ".join(text.casefold().split())
    settings: dict[str, bool] = {}
    recognized: list[str] = []
    remainder = normalized
    patterns = (
        (("balance lunch", "keep lunch groups balanced"), "balance_lunch"),
        (("prioritize seniors", "give seniors", "seniors first"), "prioritize_seniors"),
        (("earlier submissions", "first submitted", "submitted first"), "prioritize_earlier_submissions"),
        (("maximize first choices", "first choice"), "maximize_preferences"),
    )
    for phrases, setting in patterns:
        matched_phrases = [phrase for phrase in phrases if phrase in normalized]
        if matched_phrases:
            settings[setting] = True
            recognized.append(setting.replace("_", " "))
            for phrase in sorted(matched_phrases, key=len, reverse=True):
                remainder = remainder.replace(phrase, " ")

    remainder_words = re.findall(r"[a-z0-9]+", remainder)
    filler_words = {"and", "please", "the", "their", "to", "try"}
    unsupported_words = [word for word in remainder_words if word not in filler_words]
    if unsupported_words:
        unsupported = " ".join(unsupported_words)
        warnings = [f"Unsupported rule language: '{unsupported}'."]
    elif normalized and not recognized:
        warnings = ["No supported rule was found. Nothing was changed."]
    else:
        warnings = []
    return settings, warnings
