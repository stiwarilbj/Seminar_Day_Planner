from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from seminar_day_planner.database.models import ImportBatch, ImportRow
from seminar_day_planner.database.repository import upsert_seminar, upsert_student
from seminar_day_planner.types import ImportPreview, SeminarImportRow, StudentImportRow


def stage_import_batch(
    session: Session,
    event_id: int,
    preview: ImportPreview,
    filename: str | None = None,
) -> ImportBatch:
    batch = ImportBatch(
        event_id=event_id,
        source_type=preview.source_type,
        target_type=preview.target_type,
        filename=filename,
        status="staged",
        row_count=len(preview.rows),
        error_count=preview.error_count,
        warning_count=preview.warning_count,
    )
    session.add(batch)
    session.flush()
    for row in preview.rows:
        batch.rows.append(
            ImportRow(
                row_number=row.row_number,
                raw_data={},
                normalized_data=row.normalized_data,
                status=row.status,
                messages=row.messages,
            )
        )
    session.flush()
    return batch


def confirm_import_batch(session: Session, batch_id: int) -> tuple[int, int]:
    batch = session.scalar(
        select(ImportBatch)
        .where(ImportBatch.id == batch_id)
        .options(selectinload(ImportBatch.rows))
    )
    if batch is None:
        raise LookupError(f"Import batch {batch_id} does not exist.")
    if batch.status != "staged":
        raise ValueError("Only staged imports can be confirmed.")
    if any(row.status == "error" for row in batch.rows):
        raise ValueError("Fix every error before confirming this import.")

    created_or_updated = 0
    for row in batch.rows:
        if batch.target_type == "student":
            upsert_student(
                session,
                batch.event_id,
                StudentImportRow.model_validate(row.normalized_data),
            )
        else:
            upsert_seminar(
                session,
                batch.event_id,
                SeminarImportRow.model_validate(row.normalized_data),
            )
        created_or_updated += 1

    batch.status = "confirmed"
    batch.confirmed_at = datetime.now(UTC)
    session.flush()
    return created_or_updated, batch.warning_count

