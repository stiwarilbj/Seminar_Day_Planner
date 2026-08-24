CREATE TABLE events (
    id INTEGER PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    school_name VARCHAR(160) NOT NULL,
    event_date DATE,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    total_blocks INTEGER NOT NULL DEFAULT 4,
    seminars_per_student INTEGER NOT NULL DEFAULT 3,
    preference_count INTEGER NOT NULL DEFAULT 6,
    lunch_enabled BOOLEAN NOT NULL DEFAULT 1,
    lunch_block_a INTEGER NOT NULL DEFAULT 2,
    lunch_block_b INTEGER NOT NULL DEFAULT 3,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE blocks (
    id INTEGER PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    label VARCHAR(80) NOT NULL,
    UNIQUE(event_id, position)
);

CREATE TABLE students (
    id INTEGER PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    external_id VARCHAR(100),
    full_name VARCHAR(120) NOT NULL,
    email VARCHAR(254) NOT NULL COLLATE NOCASE,
    grade INTEGER NOT NULL CHECK(grade BETWEEN 9 AND 12),
    submitted_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(event_id, email)
);

CREATE TABLE seminars (
    id INTEGER PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    title VARCHAR(160) NOT NULL COLLATE NOCASE,
    presenter VARCHAR(120) NOT NULL,
    room VARCHAR(80) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    default_capacity INTEGER NOT NULL CHECK(default_capacity > 0),
    active BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(event_id, title)
);

CREATE TABLE seminar_sessions (
    id INTEGER PRIMARY KEY,
    seminar_id INTEGER NOT NULL REFERENCES seminars(id) ON DELETE CASCADE,
    block_id INTEGER NOT NULL REFERENCES blocks(id) ON DELETE CASCADE,
    capacity INTEGER NOT NULL CHECK(capacity > 0),
    UNIQUE(seminar_id, block_id)
);

CREATE TABLE preferences (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    seminar_id INTEGER NOT NULL REFERENCES seminars(id) ON DELETE CASCADE,
    rank INTEGER NOT NULL CHECK(rank > 0),
    UNIQUE(student_id, rank),
    UNIQUE(student_id, seminar_id)
);

CREATE TABLE import_batches (
    id INTEGER PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    source_type VARCHAR(30) NOT NULL,
    target_type VARCHAR(20) NOT NULL,
    filename VARCHAR(255),
    status VARCHAR(20) NOT NULL DEFAULT 'staged',
    row_count INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    warning_count INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    confirmed_at DATETIME
);

CREATE TABLE import_rows (
    id INTEGER PRIMARY KEY,
    batch_id INTEGER NOT NULL REFERENCES import_batches(id) ON DELETE CASCADE,
    row_number INTEGER NOT NULL,
    raw_data JSON NOT NULL,
    normalized_data JSON NOT NULL,
    status VARCHAR(20) NOT NULL,
    messages JSON NOT NULL DEFAULT '[]'
);

CREATE TABLE schedule_runs (
    id INTEGER PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL,
    solver_status VARCHAR(40) NOT NULL,
    configuration JSON NOT NULL,
    satisfaction JSON NOT NULL DEFAULT '{}',
    diagnostics JSON NOT NULL DEFAULT '{}',
    objective_value FLOAT,
    random_seed INTEGER NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE assignments (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES schedule_runs(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    block_id INTEGER NOT NULL REFERENCES blocks(id) ON DELETE CASCADE,
    activity_type VARCHAR(20) NOT NULL CHECK(activity_type IN ('seminar', 'lunch')),
    seminar_session_id INTEGER REFERENCES seminar_sessions(id) ON DELETE RESTRICT,
    preference_rank INTEGER,
    UNIQUE(run_id, student_id, block_id),
    CHECK(
        (activity_type = 'lunch' AND seminar_session_id IS NULL)
        OR (activity_type = 'seminar' AND seminar_session_id IS NOT NULL)
    )
);

CREATE INDEX ix_students_event_grade ON students(event_id, grade);
CREATE INDEX ix_preferences_student_rank ON preferences(student_id, rank);
CREATE INDEX ix_sessions_block ON seminar_sessions(block_id);
CREATE INDEX ix_assignments_run_student ON assignments(run_id, student_id);
CREATE INDEX ix_assignments_session ON assignments(seminar_session_id);

