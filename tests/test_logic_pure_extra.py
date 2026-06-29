"""
Pure-function tests for logic.py — the explanation / recommendation / chart helpers.

These take plain values (no DB, no app context), so they're exercised directly with
inputs chosen to hit every branch.
"""

import pytest

from course_reg import logic


@pytest.mark.parametrize("factors, expected", [
    ({"num_courses": 0, "workload": "-", "num_difficult": 0}, "No courses added."),
    ({"num_courses": 5, "workload": "Heavy", "num_difficult": 2}, "A lot of courses."),
    ({"num_courses": 2, "workload": "Light", "num_difficult": 0}, "Not a lot of courses."),
    ({"num_courses": 4, "workload": "Overloaded", "num_difficult": 0}, "Too many hard courses."),
    ({"num_courses": 4, "workload": "Balanced", "num_difficult": 3}, "A good amount of hard courses."),
    ({"num_courses": 4, "workload": "Balanced", "num_difficult": 1}, "Not a lot of hard courses."),
    ({"num_courses": 4, "workload": "Balanced", "num_difficult": 2}, "Good balance of courses."),
])
def test_generate_burnout_explanation(factors, expected):
    assert logic.generate_burnout_explanation(factors) == expected


@pytest.mark.parametrize("desc, expected", [
    ("Low", "Few/Easy courses"),
    ("Medium", "Good balance"),
    ("High", "Hard/Lots of courses"),
    ("Very High", "Lots of hard courses"),
])
def test_generate_impact_explanation(desc, expected):
    assert logic.generate_impact_explanation(desc) == expected


@pytest.mark.parametrize("workload, burnout, impact, expected", [
    (35, 0, 0.0, "Drop some courses."),             # overloaded: workload > heavy
    (10, 4, 0.0, "Swap out some hard courses."),    # overloaded: burnout >= high
    (10, 0, 1.5, "Drop or swap some courses."),     # overloaded: impact >= v.high
    (28, 2, 0.0, "Drop a course."),                 # heavy: workload > balanced
    (10, 3, 1.3, "Swap out a hard course."),        # heavy: burnout >= med-high
    (10, 2, 1.3, "Drop or swap a hard course."),    # heavy: else
    (20, 0, 0.0, "Pace yourself!"),                 # balanced
    (10, 0, 0.0, "Add or swap in a hard course!"),  # light
])
def test_generate_recommendation(workload, burnout, impact, expected):
    assert logic.generate_recommendation(workload, burnout, impact) == expected


@pytest.mark.parametrize("num_difficult, num_courses, expected", [
    (0, 0, "Low"),
    (4, 4, "Very High"),
    (3, 4, "High"),
    (2, 4, "Medium"),
    (1, 4, "Low"),
])
def test_classify_difficulty_ratio(num_difficult, num_courses, expected):
    assert logic.classify_difficulty_ratio(num_difficult, num_courses) == expected


def test_generate_sparkline_empty():
    assert logic.generate_sparkline_points([]) == ""


def test_generate_sparkline_single_point_is_duplicated():
    s = logic.generate_sparkline_points([5.0])
    assert isinstance(s, str)
    assert len(s.split(" ")) == 2          # one value renders as two points


def test_generate_sparkline_multiple_points():
    pts = logic.generate_sparkline_points([10.0, 20.0, 30.0]).split(" ")
    assert len(pts) == 3
    assert all("," in p for p in pts)      # each point is "x,y"


@pytest.mark.parametrize("values, lower_is_better, expected", [
    ([5.0], True, ("Not enough data yet", "neutral")),
    ([5.0, 5.0], True, ("Stable", "neutral")),
    ([10.0, 5.0], True, ("Improving", "positive")),    # decreased, lower is better
    ([5.0, 10.0], True, ("Worsening", "negative")),    # increased, lower is better
    ([5.0, 10.0], False, ("Improving", "positive")),   # increased, higher is better
])
def test_get_trend_direction(values, lower_is_better, expected):
    assert logic.get_trend_direction(values, lower_is_better=lower_is_better) == expected
