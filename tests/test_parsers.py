from __future__ import annotations

import json

from seminar_day_planner.ingestion.parsers import (
    parse_delimited_bytes,
    parse_json_bytes,
    parse_natural_language,
    parse_scheduling_rule,
)

KNOWN = ["Robotics Lab", "Film Scoring", "Climate Science", "Creative Coding"]


def test_legacy_google_forms_column_order_is_read_correctly() -> None:
    content = (
        b"Timestamp,Name,Grade,Email,Pref 1,Pref 2,Pref 3\n"
        b"2026-08-01T08:00:00Z,Maya Anderson,12,maya@example.test,"
        b"Robotics Lab,Film Scoring,Climate Science\n"
    )
    preview = parse_delimited_bytes(content, "student", KNOWN)
    assert preview.error_count == 0
    row = preview.rows[0].normalized_data
    assert row["email"] == "maya@example.test"
    assert row["grade"] == 12
    assert row["preferences"] == KNOWN[:3]
    assert preview.field_mappings["Name"] == "full_name"
    assert preview.field_mappings["Pref 1"] == "preference 1"


def test_natural_language_student_parser_is_local_and_predictable() -> None:
    preview = parse_natural_language(
        "Maya Anderson, grade 12, maya@example.test, wants Robotics Lab, "
        "then Film Scoring, then Climate Science",
        "student",
        KNOWN,
    )
    assert preview.error_count == 0
    assert preview.rows[0].normalized_data["preferences"] == KNOWN[:3]


def test_missing_email_is_a_review_error() -> None:
    preview = parse_natural_language(
        "Maya Anderson, grade 12, wants Robotics Lab, then Film Scoring",
        "student",
        KNOWN,
    )
    assert preview.error_count == 1
    assert any("email" in message for message in preview.rows[0].messages)


def test_close_seminar_name_is_mapped_with_warning() -> None:
    preview = parse_natural_language(
        "Maya Anderson, grade 12, maya@example.test, wants Coding Lab, then Film Scoring",
        "student",
        KNOWN,
    )
    assert preview.warning_count == 1
    assert preview.rows[0].normalized_data["preferences"][0] == "Creative Coding"


def test_json_accepts_wrapped_student_records() -> None:
    payload = {
        "students": [
            {
                "Name": "Maya Anderson",
                "Email": "maya@example.test",
                "Grade": 12,
                "preferences": ["Robotics Lab", "Film Scoring"],
            }
        ]
    }
    preview = parse_json_bytes(json.dumps(payload).encode(), "student", KNOWN)
    assert preview.ready_count == 1


def test_unknown_rule_changes_nothing() -> None:
    settings, warnings = parse_scheduling_rule("make it awesome")
    assert settings == {}
    assert warnings


def test_known_rule_with_unknown_language_is_not_silently_applied() -> None:
    settings, warnings = parse_scheduling_rule("balance lunch and skip breakfast")
    assert settings["balance_lunch"] is True
    assert "skip breakfast" in warnings[0]


def test_supported_rules_are_detected() -> None:
    settings, warnings = parse_scheduling_rule(
        "Try to give seniors their first choice and keep lunch groups balanced."
    )
    assert settings["prioritize_seniors"] is True
    assert settings["balance_lunch"] is True
    assert warnings == []
