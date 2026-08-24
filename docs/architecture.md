# Architecture

The project separates each job so a new reader can find the right code quickly.

```text
src/seminar_day_planner/
├── database/    SQLAlchemy models, migrations, and repository functions
├── ingestion/   CSV, Excel, JSON, SQLite, and natural-language parsing
├── scheduling/  Capacity checks, CP-SAT model, persistence, and validation
├── exports/     Student PDFs, attendance PDFs, spreadsheets, and ZIP files
└── ui/          NiceGUI routes, pages, components, and the shared theme
```

## Data flow

1. The student form or an import creates normalized student and preference records.
2. File imports are staged in `import_batches` and `import_rows` for review.
3. Confirming an import updates canonical SQL records inside one transaction.
4. The schedule builder loads one immutable scheduling problem from SQLite.
5. Preflight checks validate periods, seats, rooms, and presenter conflicts.
6. OR-Tools assigns three seminars and one balanced lunch to every student.
7. A schedule run stores its configuration, solver status, score summary, and assignments.
8. The results page validates the saved run before creating exports.

## Scheduling priorities

Hard constraints always win. No period can contain two activities for one student. Seminar capacities cannot be exceeded. A student cannot repeat a seminar. Lunch is assigned in period 2 or 3 and the two groups differ by at most one student.

The objective works in priority layers. It first protects the number of students who receive any ranked choice. It then protects students receiving a top-two choice. After that it maximizes total preference points using weights of 100, 60, 35, 20, 10, and 5. Grade and submission time only break otherwise equal results.

## SQL and local safety

SQLite foreign keys are enabled for every connection. The app also enables WAL mode and a busy timeout for smoother use on a local network. Versioned scripts live in `sql/migrations`. The database file, uploaded files, and exports are ignored by Git.

The student route is public on the configured host. Staff routes use one password from `.env`. This is intentionally a simple school tool, not an internet-scale identity system.

