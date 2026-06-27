"""
Scoring eval harness (Deliverable A).

Reads a labeled CSV of student schedules where a human has filled in their own
expected recommendation (and optionally workload band / burnout level), runs the
LIVE committed scoring code on each schedule, and reports agreement plus every
disagreement.

Why this matters: the human labels are independent judgment. Where they disagree
with the code, that is a finding — either a bug or a threshold that does not match
how an advisor would actually advise. The harness calls the real functions (not a
re-implementation), so it always reflects the current committed logic; change the
formula and re-run to see agreement move.

CSV columns expected:
    student_id, course_codes ("a|b|c"),
    your_workload_band, your_burnout_level, your_recommendation   (any may be blank)
Blank human cells are simply not scored.

Usage:
    EVAL_SEED_DB=/path/to/sample_courses.db python eval_scoring.py labeled_schedules.csv
If EVAL_SEED_DB is unset, the same text seed used by the test suite is built.

Exit code 0 if the file was processed (regardless of agreement); 1 on a hard error.
"""

import csv
import os
import sys
import sqlite3
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent


def _ensure_seed_db():
    """Resolve a usable seed DB the same way the test suite does."""
    existing = os.environ.get("EVAL_SEED_DB")
    if existing and Path(existing).exists():
        return existing
    seed_sql = _ROOT / "tests" / "fixtures" / "seed.sql"
    if not seed_sql.exists():
        raise SystemExit(f"No EVAL_SEED_DB and no seed fixture at {seed_sql}")
    from course_reg import db as database
    fd, path = tempfile.mkstemp(suffix="_eval.db")
    os.close(fd)
    con = sqlite3.connect(path)
    database.init_db(con)
    con.commit()
    con.executescript(seed_sql.read_text())
    con.commit()
    con.close()
    return path


def _read_rows(csv_path):
    with open(csv_path, newline="", encoding="utf-8-sig") as f:  # utf-8-sig strips BOM
        return list(csv.DictReader(f))


def _codes(row):
    return [int(x) for x in row["course_codes"].split("|") if x.strip()]


def run(csv_path):
    db_path = _ensure_seed_db()
    os.environ["SQLITE3_DB"] = db_path
    os.environ.setdefault("SECRET_KEY", "eval")
    os.environ.setdefault("SEED_EMAIL", "eval@uci.edu")
    os.environ.setdefault("SEED_PWD", "unused")

    from course_reg import create_app, logic, decision_engine
    app = create_app()

    rows = _read_rows(csv_path)

    # (label key, human column, live function)
    dims = [
        ("workload band", "your_workload_band",
         lambda c: logic.classify_workload(logic.total_hours_per_week(c))),
        ("burnout level", "your_burnout_level",
         lambda c: logic.estimate_burnout_risk(logic.calculate_burnout_risk(c)[0])),
        ("recommendation", "your_recommendation",
         lambda c: decision_engine.choose_drop_or_swap(c)),
    ]

    scored = {d[0]: 0 for d in dims}
    agreed = {d[0]: 0 for d in dims}
    disagreements = []

    with app.app_context():
        for row in rows:
            sid = row.get("student_id") or row.get("\ufeffstudent_id") or "?"
            codes = _codes(row)
            for label, col, fn in dims:
                human = (row.get(col) or "").strip()
                if not human:
                    continue
                code_val = fn(codes)
                scored[label] += 1
                if human == code_val:
                    agreed[label] += 1
                else:
                    disagreements.append((sid, label, human, code_val,
                                          (row.get("your_notes") or "").strip()))

    # ---- report ----
    print(f"Scoring eval — {csv_path}")
    print(f"Seed DB: {db_path}\n")
    total_scored = sum(scored.values())
    total_agreed = sum(agreed.values())
    for label, _, _ in dims:
        s = scored[label]
        if s:
            print(f"  {label:15s}: {agreed[label]}/{s} agree "
                  f"({100*agreed[label]//s}%)")
        else:
            print(f"  {label:15s}: (no human labels)")
    if total_scored:
        print(f"\n  OVERALL: {total_agreed}/{total_scored} "
              f"({100*total_agreed//total_scored}%) agreement")
    else:
        print("\n  No human labels found to score.")

    if disagreements:
        print(f"\nDISAGREEMENTS ({len(disagreements)}) — human vs code:")
        for sid, label, human, code_val, note in disagreements:
            line = f"  {sid} [{label}] you={human} code={code_val}"
            if note:
                line += f"\n       note: {note}"
            print(line)
    else:
        print("\nNo disagreements among scored labels.")

    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python eval_scoring.py <labeled_schedules.csv>")
    sys.exit(run(sys.argv[1]))
