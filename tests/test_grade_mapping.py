"""Tests for api/grade_mapping.py — grade-to-points conversion."""

import pytest


class TestGradeToPoints:
    def test_a_returns_20(self):
        from api.grade_mapping import grade_to_points
        assert grade_to_points("A") == 20

    def test_b_returns_12(self):
        from api.grade_mapping import grade_to_points
        assert grade_to_points("B") == 12

    def test_c_returns_5(self):
        from api.grade_mapping import grade_to_points
        assert grade_to_points("C") == 5

    def test_none_returns_default_10(self):
        from api.grade_mapping import grade_to_points
        assert grade_to_points(None) == 10

    def test_lowercase_a_returns_20(self):
        from api.grade_mapping import grade_to_points
        assert grade_to_points("a") == 20

    def test_lowercase_b_returns_12(self):
        from api.grade_mapping import grade_to_points
        assert grade_to_points("b") == 12

    def test_lowercase_c_returns_5(self):
        from api.grade_mapping import grade_to_points
        assert grade_to_points("c") == 5

    def test_unknown_grade_returns_default_10(self):
        from api.grade_mapping import grade_to_points
        assert grade_to_points("X") == 10

    def test_empty_string_returns_default_10(self):
        from api.grade_mapping import grade_to_points
        assert grade_to_points("") == 10

    def test_custom_default(self):
        from api.grade_mapping import grade_to_points
        assert grade_to_points(None, default=15) == 15

    def test_grade_points_constant_exists(self):
        from api.grade_mapping import GRADE_POINTS
        assert GRADE_POINTS["A"] == 20
        assert GRADE_POINTS["B"] == 12
        assert GRADE_POINTS["C"] == 5
