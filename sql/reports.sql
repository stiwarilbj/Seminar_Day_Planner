-- Student schedules for the most recent successful run.
SELECT
    s.full_name,
    s.email,
    s.grade,
    b.position AS block,
    CASE WHEN a.activity_type = 'lunch' THEN 'Lunch' ELSE sem.title END AS activity,
    a.preference_rank
FROM assignments a
JOIN schedule_runs r ON r.id = a.run_id
JOIN students s ON s.id = a.student_id
JOIN blocks b ON b.id = a.block_id
LEFT JOIN seminar_sessions ss ON ss.id = a.seminar_session_id
LEFT JOIN seminars sem ON sem.id = ss.seminar_id
WHERE r.id = :run_id
ORDER BY s.full_name, b.position;

-- Attendance and capacity by seminar session.
SELECT
    b.position AS block,
    sem.title,
    sem.presenter,
    sem.room,
    ss.capacity,
    COUNT(a.id) AS assigned_students,
    ROUND(100.0 * COUNT(a.id) / ss.capacity, 1) AS capacity_percent
FROM seminar_sessions ss
JOIN seminars sem ON sem.id = ss.seminar_id
JOIN blocks b ON b.id = ss.block_id
LEFT JOIN assignments a
    ON a.seminar_session_id = ss.id AND a.run_id = :run_id
GROUP BY ss.id
ORDER BY b.position, sem.title;

-- Preference satisfaction for one run.
SELECT
    CASE
        WHEN preference_rank = 1 THEN '1st choice'
        WHEN preference_rank = 2 THEN '2nd choice'
        WHEN preference_rank = 3 THEN '3rd choice'
        WHEN preference_rank IS NULL THEN 'Not ranked'
        ELSE '4th choice or lower'
    END AS preference_group,
    COUNT(*) AS assignments
FROM assignments
WHERE run_id = :run_id AND activity_type = 'seminar'
GROUP BY preference_group
ORDER BY MIN(COALESCE(preference_rank, 99));

