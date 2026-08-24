# Data Import Guide

Every import shows a review table before canonical student or seminar records change.

## Student fields

The required fields are `Name`, `Email`, `Grade`, and at least one ranked preference. Preference columns can be named `Pref 1`, `Preference 1`, or `Choice 1`. The same pattern continues for later choices. `Timestamp` and `Student ID` are optional.

```csv
Timestamp,Name,Grade,Email,Pref 1,Pref 2,Pref 3
2026-08-01T08:00:00Z,Maya Anderson,12,maya@student.example.test,Robotics Lab,Film Scoring,Climate Science
```

The old Google Forms order is supported, including `Timestamp, Name, Grade, Email`.

## Seminar fields

Seminars need `Title`, `Presenter`, `Room`, `Capacity`, and `Periods`.

```csv
Title,Presenter,Room,Capacity,Periods
Robotics Lab,Mr. Harris,Engineering 201,18,"1,2,3,4"
```

## Natural-language records

Use one record per line. The parser is local and intentionally predictable.

```text
Maya Anderson, grade 12, maya@student.example.test, wants Robotics Lab, then Film Scoring, then Climate Science
Robotics Lab with Mr. Harris in Engineering 201, capacity 18, periods 1, 2, 3, 4
```

Supported scheduling phrases include `balance lunch`, `prioritize seniors`, `earlier submissions`, and `maximize first choices`. If no supported phrase is found, the app changes nothing and shows a warning.

## Other formats

- Excel uses the first worksheet.
- JSON can be a list of objects or an object containing `students`, `seminars`, or `rows`.
- SQLite files are opened in read-only mode. The first non-system table is imported.
- Unknown headers stay out of the normalized record and appear as missing required fields during review.

