"""
Unit tests for choose_drop_or_swap — OPTION B (final committed version).

Matches the committed decision_engine.py:
    Constants (defined in decision_engine.py):
      DIFFICULTY_DENSITY_THRESHOLD = 0.6
      EXTREME_HOURS_THRESHOLD      = 33
      SEVERE_BURNOUT_THRESHOLD     = 6
    Plus logic.py thresholds:
      WORKLOAD_HEAVY_THRESHOLD     = 30
      WORKLOAD_BALANCED_THRESHOLD  = 25
      BURNOUT_MEDIUM_THRESHOLD     = 2

Decision order:
    1. burnout >= 6                          -> "Drop"
    2. not heavy and not hard_mix            -> "Swap" if burnout > 2 else "Balanced"
    3. overloaded and hard_mix               -> "Drop" if hours > 33 else "Swap"
    4. heavy and not hard_mix                -> "Drop"
    5. hard_mix and not overloaded           -> "Swap"
    6. fallthrough                           -> "Drop" if overloaded else "Swap"

  where heavy = hours>25, overloaded = hours>30, hard_mix = density>=0.6,
        density = num_difficult / num_courses

Expected values are derived from the spec above, not read back from the code.
"""

import os
import shutil
import pytest

from tests import TEST_SECRET_KEY


@pytest.fixture
def app_ctx(tmp_path, monkeypatch):
    src = os.environ["EVAL_SEED_DB"]
    test_db = tmp_path / "ds_db.db"
    shutil.copy(src, test_db)
    monkeypatch.setenv("SQLITE3_DB", str(test_db))
    monkeypatch.setenv("SECRET_KEY", TEST_SECRET_KEY)
    monkeypatch.setenv("SEED_EMAIL", "ds@uci.edu")
    monkeypatch.setenv("SEED_PWD", "unused")
    from course_reg import create_app
    app = create_app()
    app.config["TESTING"] = True
    ctx = app.app_context()
    ctx.push()
    yield app
    ctx.pop()


# Scenarios built from real catalog courses (properties verified against the DB):
#
# A: 2 easy courses     -> 6.0 hrs, density 0.0, burnout 0
#    branch 2 (light), burnout not >2            -> Balanced
SCEN_BALANCED = [33201, 36045]
#
# B: 2 hard (d5) only   -> 19.2 hrs, density 1.0, burnout 3
#    not heavy, hard_mix True -> branch 5         -> Swap
SCEN_HARDMIX_SWAP = [36570, 36360]
#
# C: 5 medium + 1 hard  -> 31.8 hrs, density 0.17, burnout 5
#    overloaded, not hard_mix, burnout<6 -> branch 4 -> Drop
SCEN_HOURS_DROP = [33301, 36090, 36100, 67170, 36250, 34110]
#
# D: 4 hard (d5)        -> 38.4 hrs, density 1.0, burnout 8
#    burnout>=6 -> branch 1                        -> Drop
SCEN_SEVERE_DROP = [36570, 36360, 36050, 37204]
#
# E: 3 medium + 1 hard  -> 20.4 hrs, density 0.25, burnout 3
#    NEW: light branch with burnout>2             -> Swap
#    (pins the BURNOUT_MEDIUM_THRESHOLD light-load Swap path)
SCEN_LIGHT_STRAINED_SWAP = [33301, 36090, 36100, 44080]


def test_balanced_schedule_returns_balanced(app_ctx):
    from course_reg import decision_engine
    assert decision_engine.choose_drop_or_swap(SCEN_BALANCED) == "Balanced"


def test_hard_mix_low_hours_returns_swap(app_ctx):
    from course_reg import decision_engine
    assert decision_engine.choose_drop_or_swap(SCEN_HARDMIX_SWAP) == "Swap"


def test_high_hours_low_density_returns_drop(app_ctx):
    """The case the OLD formula could never produce: lots of hours, easy-ish
    mix -> Drop. Core regression the Option B fix addresses."""
    from course_reg import decision_engine
    assert decision_engine.choose_drop_or_swap(SCEN_HOURS_DROP) == "Drop"


def test_severe_burnout_returns_drop(app_ctx):
    """Option B: burnout >= 6 forces Drop regardless of the axis split."""
    from course_reg import decision_engine
    assert decision_engine.choose_drop_or_swap(SCEN_SEVERE_DROP) == "Drop"


def test_light_but_strained_returns_swap(app_ctx):
    """Light hours, easy mix, but burnout > 2 -> Swap (not Balanced).
    Pins the light-load Swap branch using BURNOUT_MEDIUM_THRESHOLD."""
    from course_reg import decision_engine
    assert decision_engine.choose_drop_or_swap(SCEN_LIGHT_STRAINED_SWAP) == "Swap"