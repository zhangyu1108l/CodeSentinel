"""Tests for the Phase 8.7 node allowance policy (pure math, no graph)."""

import math

import pytest

from app.graph.allocation import node_allowance


class TestNodeAllowance:
    def test_equal_share_of_remaining(self):
        assert node_allowance(100.0, 4, 60.0) == 25.0

    def test_local_cap_wins_over_share(self):
        assert node_allowance(1000.0, 1, 60.0) == 60.0

    def test_remaining_wins_over_local_cap(self):
        assert node_allowance(10.0, 1, 60.0) == 10.0

    def test_zero_remaining_yields_zero(self):
        assert node_allowance(0.0, 2, 60.0) == 0.0

    def test_integer_inputs_are_accepted(self):
        assert node_allowance(100, 2, 60) == 50.0

    def test_share_is_exact_division(self):
        assert node_allowance(9.0, 2, 60.0) == 4.5


class TestValidation:
    def test_negative_remaining_rejected(self):
        with pytest.raises(ValueError):
            node_allowance(-1.0, 1, 60.0)

    def test_non_finite_remaining_rejected(self):
        for value in (math.nan, math.inf, -math.inf):
            with pytest.raises(ValueError):
                node_allowance(value, 1, 60.0)

    def test_bool_remaining_rejected(self):
        with pytest.raises(ValueError):
            node_allowance(True, 1, 60.0)

    def test_stages_left_must_be_positive_int(self):
        for value in (0, -1, 1.5, True):
            with pytest.raises(ValueError):
                node_allowance(10.0, value, 60.0)

    def test_local_cap_must_be_positive_finite(self):
        for value in (0, -1.0, math.inf, math.nan, True):
            with pytest.raises(ValueError):
                node_allowance(10.0, 1, value)