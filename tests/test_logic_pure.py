"""
Unit test suite — PURE functions (no database).

Covers the deterministic, DB-free functions in course_reg/logic.py and
course_reg/utility.py. These run instantly with no fixtures.

Expected values are derived from INTENDED behavior and the documented thresholds,
not copied from the implementation's output, so a disagreement means a real bug.

Thresholds referenced (from logic.py):
    WORKLOAD: Light<=15, Balanced<=25, Heavy<=30, Overloaded>30
    BURNOUT level: High>=4, Medium>=2, else Low
    IMPACT: Low<0.8, Medium<1.2, High<1.4, else Very High
    DIFFICULTY RATIO: VeryHigh>=1.0, High>=0.75, Medium>=0.5, else Low

NOTE on choose_drop_or_swap: those tests live in test_drop_or_swap_optionB.py and
are written against the Option B spec. They will FAIL until that fix is pushed.
"""

import pytest
from course_reg import logic
from course_reg import utility


# --------------------------------------------------------------------------
# classify_workload  (boundary-focused: cutoffs at 15, 25, 30)
# --------------------------------------------------------------------------
@pytest.mark.parametrize("score,expected", [
    (0, "Light"), (15, "Light"),            # <=15 Light (15 is inclusive)
    (15.1, "Balanced"), (25, "Balanced"),   # <=25 Balanced
    (25.1, "Heavy"), (30, "Heavy"),         # <=30 Heavy
    (30.1, "Overloaded"), (50, "Overloaded"),
])
def test_classify_workload(score, expected):
    assert logic.classify_workload(score) == expected


# --------------------------------------------------------------------------
# estimate_burnout_risk  (cutoffs: High>=4, Medium>=2)
# --------------------------------------------------------------------------
@pytest.mark.parametrize("score,expected", [
    (0, "Low"), (1, "Low"),
    (2, "Medium"), (3, "Medium"),
    (4, "High"), (8, "High"),
])
def test_estimate_burnout_risk(score, expected):
    assert logic.estimate_burnout_risk(score) == expected


# --------------------------------------------------------------------------
# classify_academic_impact  (Low<0.8, Medium<1.2, High<1.4, else Very High)
# --------------------------------------------------------------------------
@pytest.mark.parametrize("score,expected", [
    (0.0, "Low"), (0.79, "Low"),
    (0.8, "Medium"), (1.19, "Medium"),
    (1.2, "High"), (1.39, "High"),
    (1.4, "Very High"), (2.0, "Very High"),
])
def test_classify_academic_impact(score, expected):
    assert logic.classify_academic_impact(score) == expected


# --------------------------------------------------------------------------
# classify_difficulty_ratio  (ratio cutoffs: 1.0, 0.75, 0.5)
# --------------------------------------------------------------------------
@pytest.mark.parametrize("num_difficult,num_courses,expected", [
    (0, 0, "Low"),     # guard: no courses
    (0, 4, "Low"),     # 0.0
    (2, 4, "Medium"),  # 0.5
    (3, 4, "High"),    # 0.75
    (4, 4, "Very High"),  # 1.0
    (1, 4, "Low"),     # 0.25
])
def test_classify_difficulty_ratio(num_difficult, num_courses, expected):
    assert logic.classify_difficulty_ratio(num_difficult, num_courses) == expected


# --------------------------------------------------------------------------
# generate_recommendation  (intent-level checks, not exact-string brittleness)
# args: (workload_score, burnout_score, academic_impact)
# --------------------------------------------------------------------------
def test_recommendation_overloaded_hours_says_drop():
    # workload > 30 -> drop branch
    assert "Drop" in logic.generate_recommendation(35, 0, 0)

def test_recommendation_high_burnout_low_hours_says_swap():
    # burnout >= 4 but workload not over 30 -> swap branch
    assert "Swap" in logic.generate_recommendation(10, 5, 0)

def test_recommendation_balanced_says_pace():
    # workload over Light(15) but not Heavy, modest burnout -> Pace
    assert "Pace" in logic.generate_recommendation(20, 0, 0)

def test_recommendation_light_says_add():
    # everything low -> add
    assert "Add" in logic.generate_recommendation(5, 0, 0)


# --------------------------------------------------------------------------
# serialize / deserialize round-trips (utility.py)
# The robust property: deserialize(serialize(x)) == x
# --------------------------------------------------------------------------
@pytest.mark.parametrize("arr", [
    [], ["a"], ["a", "b", "c"], ["x", "y", "z", "w"],
])
def test_list_roundtrip(arr):
    assert utility.deserialize_list(utility.serialize_list(arr)) == arr

def test_deserialize_empty_list_is_empty():
    assert utility.deserialize_list("") == []

@pytest.mark.parametrize("matrix", [
    [["a", "b"], ["c", "d"]],
    [["1"]],
    [["x", "y", "z"], ["p", "q", "r"]],
])
def test_matrix_roundtrip(matrix):
    assert utility.deserialize_matrix(utility.serialize_matrix(matrix)) == matrix

def test_deserialize_empty_matrix_is_empty():
    assert utility.deserialize_matrix("") == []
