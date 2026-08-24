from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class Settings:
    project_root: Path
    database_path: Path
    runtime_root: Path
    upload_root: Path
    export_root: Path
    migrations_root: Path
    staff_password: str
    session_secret: str
    host: str
    port: int
    allowed_email_domain: str | None

    @classmethod
    def from_environment(cls, project_root: Path = PROJECT_ROOT) -> Settings:
        load_dotenv(project_root / ".env")
        configured_database = Path(
            os.getenv("DATABASE_PATH", "runtime/database/seminar_day.db")
        )
        if not configured_database.is_absolute():
            configured_database = project_root / configured_database
        runtime_root = project_root / "runtime"
        domain = os.getenv("ALLOWED_EMAIL_DOMAIN", "").strip().lower().lstrip("@")
        return cls(
            project_root=project_root,
            database_path=configured_database,
            runtime_root=runtime_root,
            upload_root=runtime_root / "uploads",
            export_root=runtime_root / "exports",
            migrations_root=project_root / "sql" / "migrations",
            staff_password=os.getenv("STAFF_PASSWORD", "seminar-day"),
            session_secret=os.getenv("SESSION_SECRET", "local-demo-secret-change-me"),
            host=os.getenv("HOST", "127.0.0.1"),
            port=int(os.getenv("PORT", "8080")),
            allowed_email_domain=domain or None,
        )

    def prepare_runtime_directories(self) -> None:
        for directory in (
            self.database_path.parent,
            self.upload_root,
            self.export_root,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def validate_for_startup(self) -> None:
        if self.host not in {"127.0.0.1", "localhost"}:
            if self.staff_password == "seminar-day":
                raise ValueError("Change STAFF_PASSWORD before starting in LAN mode.")
            if self.session_secret == "local-demo-secret-change-me":
                raise ValueError("Change SESSION_SECRET before starting in LAN mode.")

