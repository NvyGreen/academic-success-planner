# Scoring eval (Deliverable A)

A small labeled-evaluation harness for the schedule-scoring logic. Human judgment
is compared against the live committed code; disagreements are findings.

## Files
- `eval_scoring.py`              -> harness (root of repo)
- `eval/labeled_schedules.csv`   -> 30 student schedules; human labels in your_* columns
- `eval/results/latest.txt`      -> saved before/after run

## How to run
    EVAL_SEED_DB=/path/to/sample_courses.db python eval_scoring.py eval/labeled_schedules.csv
If EVAL_SEED_DB is unset, it builds the same text seed the test suite uses.
The harness calls the LIVE scoring functions, so it always reflects current code.

## What was labeled, and how blanks are scored
A human reviewed all 30 schedules and recorded an independent recommendation on
the 5 boundary cases most likely to expose a flaw (heavy-but-not-overloaded loads
with high burnout). A blank `your_recommendation` is scored as **agreement** — a
blank means the human had no objection to the code's recommendation. So all 30
schedules count toward the recommendation total: 5 explicit labels + 25
blank-as-agreement. (Workload band / burnout level were left unlabeled and are not
scored.)

## Result and the finding it produced
Run against the ORIGINAL Option B logic: **25/30** agreement on recommendation —
and critically, **all 5 explicitly-labeled cases disagreed** (human "Swap" vs code
"Drop"). They traced to one cause: the severe-burnout override (`burnout >= 6 ->
Drop`) fired before the hours/density logic, force-dropping schedules that were
only Heavy (not Overloaded). An advisor would Swap a hard course, not drop one,
when hours are still manageable.

### Fix applied
Gate the override so it only forces Drop when the schedule is ALSO overloaded:

    if burnout >= SEVERE_BURNOUT_THRESHOLD and overloaded:
        return "Drop"

Verified: this raised agreement to **29/30** (the 5 labeled cases went 0/5 -> 4/5),
changed only the 4 intended rows (no other schedule's recommendation moved), and
the full test suite still passes.

### One documented, intentional remaining disagreement
STU10 (27 hrs, 4 courses, difficulty density 0.5) — human said Swap, code says Drop.
With only half the courses hard, there is no clearly-hard course worth swapping, so
dropping a course is the better lever at that load. Decision: keep the code's Drop
for now; revisit with real user feedback rather than overfitting the formula to a
single hand-labeled case.

## Honest note on the numbers
The 25/30 and 29/30 totals fold in 25 unlabeled rows as agreement, so they read
high by construction. The real signal is the 5 deliberately-labeled boundary cases,
where the fix moved agreement from 0/5 to 4/5. The value of the eval is that
consistent, explainable finding plus a verified fix — not the headline percentage.
