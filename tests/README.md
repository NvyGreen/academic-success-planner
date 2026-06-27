# Unit test suite (updated for committed Option B)

Three files covering the scoring/logic layer.

| File | Cases | Notes |
|------|-------|-------|
| `test_logic_pure.py` | 41 | Pure functions, no DB. Unchanged. |
| `test_logic_db.py` | 8 | DB-backed (needs seeded DB). Unchanged. |
| `test_drop_or_swap_optionB.py` | 5 | Updated: now matches the committed Option B `choose_drop_or_swap`, plus a new light-load Swap case. |

Total: 54 cases.

## What changed
The committed `choose_drop_or_swap` was confirmed (pulled from main):
- two-axis logic (hours + difficulty density), `num_difficult` spelled correctly
- constants in decision_engine.py: DIFFICULTY_DENSITY_THRESHOLD=0.6,
  EXTREME_HOURS_THRESHOLD=33, SEVERE_BURNOUT_THRESHOLD=6
- light-load branch uses `burnout > BURNOUT_MEDIUM_THRESHOLD` (>2)

New 5th test `test_light_but_strained_returns_swap` pins that light-load branch:
a 4-course, 20.4 hr, density-0.25, burnout-3 schedule must return "Swap" (not
"Balanced"). The previous 4 tests did not exercise this path.

## Layout
All test files live in this `tests/` directory. A `conftest.py` at the project
root puts the repo on `sys.path` (so `import course_reg` works) and defaults
`EVAL_SEED_DB` to the bundled `course_reg/sample_courses.db`, so the suite runs
with no manual setup.

## How to run
From the project root, using the project virtualenv (`.CourseRegProject`):
```bash
.CourseRegProject/Scripts/python.exe -m pytest tests/ -v
```
All 54 pass. `test_logic_pure.py` needs no DB. The other two copy the seed DB to
a temp file per test, so your real DB is never touched. To run against a
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
