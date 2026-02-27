"""Phase 19.3 — Tier threshold tests.

New semantics: A (green) = 61+, B (yellow) = 41–60, C (skip) = 0–40.
"""

import pytest
from api.scoring import compute_tier


class TestComputeTier:
    def test_score_100_is_a(self):
        assert compute_tier(100) == "A"

    def test_score_61_is_a(self):
        assert compute_tier(61) == "A"

    def test_score_60_is_b(self):
        assert compute_tier(60) == "B"

    def test_score_41_is_b(self):
        assert compute_tier(41) == "B"

    def test_score_40_is_c(self):
        assert compute_tier(40) == "C"

    def test_score_0_is_c(self):
        assert compute_tier(0) == "C"
