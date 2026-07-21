"""Tests for the sheet-replace shrink guard.

Replacing a tab clears it first, so a run that produced a partial result set
destroyed the rest with no error. This guard is deliberately cause-agnostic:
it catches a targeted --pool run, a truncated pools.json, or an upstream
outage alike, without needing to know which happened.
"""

from curve_tracker import SHRINK_GUARD_RATIO, is_suspicious_shrink


class TestCatchesTruncation:
    def test_full_tab_replaced_by_single_row_is_refused(self):
        """The exact case that clobbered Ethereum USD: 16 pools -> 1."""
        assert is_suspicious_shrink(16, 1)

    def test_total_wipe_is_refused(self):
        assert is_suspicious_shrink(25, 0)


class TestAllowsLegitimateWrites:
    def test_growth_is_allowed(self):
        assert not is_suspicious_shrink(16, 17)

    def test_same_size_is_allowed(self):
        assert not is_suspicious_shrink(16, 16)

    def test_ordinary_churn_is_allowed(self):
        """Removing a pool or two must not require --force-replace."""
        assert not is_suspicious_shrink(16, 14)

    def test_empty_tab_is_allowed(self):
        """Nothing to lose, so the first write to a fresh tab must pass."""
        assert not is_suspicious_shrink(0, 1)

    def test_unreadable_tab_count_is_allowed(self):
        assert not is_suspicious_shrink(-1, 1)


class TestThreshold:
    def test_just_under_ratio_is_refused(self):
        assert is_suspicious_shrink(100, int(100 * SHRINK_GUARD_RATIO) - 1)

    def test_exactly_at_ratio_is_allowed(self):
        assert not is_suspicious_shrink(100, int(100 * SHRINK_GUARD_RATIO))

    def test_ratio_is_overridable(self):
        assert not is_suspicious_shrink(16, 1, ratio=0.0)
