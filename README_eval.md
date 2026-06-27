# Scoring eval (Deliverable A)

A small labeled-evaluation harness for the schedule-scoring logic. Human judgment
is compared against the live committed code; disagreements are findings.

## Files
- `eval_scoring.py`              -> harness (root of repo)
- `eval/labeled_schedules.csv`   -> 30 student schedules; human labels in your_* columns

## How to run
    EVAL_SEED_DB=/path/to/sample_courses.db python eval_scoring.py eval/labeled_schedules.csv
If EVAL_SEED_DB is unset, it builds the same text seed the test suite uses.
The harness calls the LIVE scoring functions, so it always reflects current code.

## What was labeled
A human reviewed all 30 schedules and recorded an independent recommendation on
the 5 boundary cases most likely to expose a flaw (heavy-but-not-overloaded loads
with high burnout). Blank cells are not scored — the eval scores only what a human
actually judged.

## Result and the finding it produced
Run against the ORIGINAL Option B logic: 0/5 agreement on recommendation.
All 5 disagreements were identical (human "Swap" vs code "Drop") and traced to one
cause: the severe-burnout override (`burnout >= 6 -> Drop`) fired before the
hours/density logic, force-dropping schedules that were only Heavy (not Overloaded).
An advisor would Swap a hard course, not drop one, when hours are still manageable.

### Fix applied
Gate the override so it only forces Drop when the schedule is ALSO overloaded:

    if burnout >= SEVERE_BURNOUT_THRESHOLD and overloaded:
        return "Drop"

Verified: this raised agreement to 4/5, changed only the 4 intended rows (no other
schedule's recommendation moved), and the full 72-test suite still passes.

### One documented, intentional remaining disagreement
STU10 (27 hrs, 4 courses, difficulty density 0.5) — human said Swap, code says Drop.
With only half the courses hard, there is no clearly-hard course worth swapping, so
dropping a course is the better lever at that load. Decision: keep the code's Drop
for now; revisit with real user feedback rather than overfitting the formula to a
single hand-labeled case.

## Honest note on the number
"0/5" reflects selective labeling: the human deliberately labeled only the hardest
boundary cases, where disagreement was expected. It is not "the code is 0% correct."
The value of the eval is the consistent, explainable finding it surfaced, plus a
verified fix — not the headline percentage.
