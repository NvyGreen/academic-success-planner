# Test suite

Eight files covering the scoring/logic layer and the registration workflows.

| File | Cases | Notes |
|------|-------|-------|
| `test_logic_pure.py` | 41 | Pure functions, no DB. |
| `test_logic_db.py` | 8 | DB-backed scoring helpers (needs seeded DB). |
| `test_drop_or_swap_optionB.py` | 5 | Committed Option B `choose_drop_or_swap`, incl. a light-load Swap case. |
| `test_swap_excludes_completed.py` | 2 | Swap never recommends an already-completed course. |
| `test_int_add_drop.py` | 5 | Integration: register / drop course workflow. |
| `test_int_apply_dismiss.py` | 3 | Integration: apply / dismiss a recommendation. |
| `test_int_generate_recommendation.py` | 4 | Integration: end-to-end recommendation generation. |
| `test_int_view_schedule.py` | 4 | Integration: schedule view reflects enrollment. |

Total: 72 cases.

## Background: Option B decision logic
Context for the `choose_drop_or_swap` tests. The committed version (pulled from main):
- two-axis logic (hours + difficulty density), `num_difficult` spelled correctly
- constants in decision_engine.py: DIFFICULTY_DENSITY_THRESHOLD=0.6,
  EXTREME_HOURS_THRESHOLD=33, SEVERE_BURNOUT_THRESHOLD=6
- light-load branch uses `burnout > BURNOUT_MEDIUM_THRESHOLD` (>2)

New 5th test `test_light_but_strained_returns_swap` pins that light-load branch:
a 4-course, 20.4 hr, density-0.25, burnout-3 schedule must return "Swap" (not
"Balanced"). The previous 4 tests did not exercise this path.

## Layout
All test files live in this `tests/` directory. A `conftest.py` at the project
root puts the repo on `sys.path` (so `import course_reg` works) and resolves the
seed database the DB-backed tests run against:

1. If `EVAL_SEED_DB` is set and points at an existing file, that file is used.
2. Otherwise a fresh temp DB is built once per session from
   `tests/fixtures/seed.sql` (schema via the app's own `course_reg.db.init_db`,
   data from the fixture), so the suite runs with no manual setup.

Either way, each DB-backed test copies the seed DB to its own temp file, so your
real DB is never touched.

## Seed data
`tests/fixtures/seed.sql` is the committed source of truth for test data — a
human-readable text export of the catalog/reference tables from the project's
`course_reg/sample_courses.db`. It contains only DATA (`INSERT`s); the schema is
created by `init_db`, so the two can't drift. Transient app-state tables
(`metric`, `enrollment`, `student_waitlist`, etc.) are intentionally omitted.

To refresh it after changing `sample_courses.db`, re-export these 10 tables in
this order, ordered by primary key, exporting only the columns defined in
`init_db`:

    school, department, ge_category, instructor, final,
    course, prerequisite, corequisite, student, prev_enrollment

Keep the file LF-terminated and wrapped in `BEGIN TRANSACTION; ... COMMIT;`, then
run the suite to confirm the new data still passes. After any refresh, diff the
result against the previous version and sanity-check the changes (e.g. no rows
with `NULL`/zero key fields you didn't intend) before committing.

## How to run
From the project root, using the project virtualenv (`.CourseRegProject`):
```bash
.CourseRegProject/Scripts/python.exe -m pytest tests/ -v
```
All 72 pass. `test_logic_pure.py` needs no DB. The DB-backed files copy the seed
DB to a temp file per test, so your real DB is never touched. To run against a
different seed DB, override the default:
```bash
EVAL_SEED_DB=/path/to/other.db .CourseRegProject/Scripts/python.exe -m pytest tests/ -v
```

## Saving results
The latest run is saved (and committed) to `tests/results/latest.txt`. Refresh it
by redirecting the run output:
```bash
.CourseRegProject/Scripts/python.exe -m pytest tests/ -v --no-header > tests/results/latest.txt 2>&1
```

## If a test reports failure
It means the code diverged from the documented spec above — check the constant
values first (a tuned threshold is the most common cause of a false-looking fail).
