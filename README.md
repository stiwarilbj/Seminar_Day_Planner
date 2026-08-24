```bash
cd seminar-day-planner
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
python -m seminar_day_planner --demo
```

Then open `http://127.0.0.1:8080/submit`. In demo mode, the staff password is `seminar-day`. Change it in `.env` before using the app on a school network.

# Seminar Day Planner

Seminar Day is a school day where students get to try short classes and activities that are different from their normal schedule. They rank the sessions they want, and then somebody has to fit all those choices into real rooms with real class-size limits. That gets messy surprisingly fast.

I made this for Dover-Sherborn High School's Seminar Day workflow. It is not connected to a live school system. Staff can bring in their own roster, seminars, rooms, presenters, and dates. The planner gives every student three different seminars and one lunch while trying to respect their choices and keep the groups balanced.

The part I like most is the import review. You can upload a Google Forms CSV, Excel file, JSON, SQLite table, or paste a sentence like `Maya Anderson, grade 12, wants Robotics Lab, then Film Scoring`. The app shows what it understood, points out missing or strange values, and waits for confirmation before saving anything. That feels a lot safer than hoping one giant spreadsheet is perfect.

The technology is pretty approachable. Python runs the whole app, and NiceGUI creates the light-blue web screens from Python code. SQLAlchemy connects the app to real SQLite tables. OR-Tools uses a constraint solver to place seminars, lunch, rooms, and capacities. pandas and openpyxl handle spreadsheets, and fpdf2 creates the student and attendance PDFs. Everything stays local, so no AI service or cloud account gets student data.

The demo includes 248 fictional students and 18 fictional seminars with six choices each. They all use `.example.test` addresses. The project folders are split by job, so `src/seminar_day_planner/ui` holds screens, `database` holds SQL storage, `ingestion` handles imports, `scheduling` builds the plan, and `exports` makes the files people actually need.

More detail is in [the architecture notes](docs/architecture.md) and [the data import guide](docs/data-import-guide.md).
