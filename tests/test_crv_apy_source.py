"""Tests for CRV APR source selection.

The tracker preferred gaugeFutureCrvApy -- the post-vote projection -- and
published it in a field labelled current CRV rewards. On BOLD/USDC as of
2026-07-21 that read 0.45-1.13% against an actual 0.12-0.29%, a 3.9x
overstatement inherited by everything ranking pools on CRV APR.
"""

from curve_tracker import select_crv_apy


# Real values read from the Curve API for BOLD/USDC on 2026-07-21.
BOLD_USDC = {
    'gaugeCrvApy': [0.11581600463481903, 0.28954001158704756],
    'gaugeFutureCrvApy': [0.45179123718636927, 1.1294780929659232],
}


class TestPrefersCurrentOverProjection:
    def test_current_is_returned_as_the_headline(self):
        current, _ = select_crv_apy(BOLD_USDC)
        assert current == [0.11581600463481903, 0.28954001158704756]

    def test_projection_is_preserved_separately(self):
        _, future = select_crv_apy(BOLD_USDC)
        assert future == [0.45179123718636927, 1.1294780929659232]

    def test_the_regression_itself(self):
        """The exact bug: the future range must not become the headline."""
        current, _ = select_crv_apy(BOLD_USDC)
        assert current != BOLD_USDC['gaugeFutureCrvApy']
        assert max(current) < 0.3, "0.45-1.13 here means the old bug is back"


class TestFallback:
    def test_missing_current_falls_back_to_projection(self):
        """A projection beats nothing, but only when there is no current rate."""
        current, future = select_crv_apy({'gaugeFutureCrvApy': [1.0, 2.0]})
        assert current == [1.0, 2.0]
        assert future == [1.0, 2.0]

    def test_missing_projection_is_none(self):
        current, future = select_crv_apy({'gaugeCrvApy': [1.0, 2.0]})
        assert current == [1.0, 2.0]
        assert future is None

    def test_empty_gauge_yields_nothing(self):
        assert select_crv_apy({}) == (None, None)

    def test_empty_lists_are_treated_as_absent(self):
        assert select_crv_apy({'gaugeCrvApy': [], 'gaugeFutureCrvApy': []}) == (None, None)


class TestSingleValueRanges:
    def test_single_value_becomes_a_flat_range(self):
        current, _ = select_crv_apy({'gaugeCrvApy': [1.5]})
        assert current == [1.5, 1.5]

    def test_extra_values_are_truncated_to_min_max(self):
        current, _ = select_crv_apy({'gaugeCrvApy': [1.0, 2.0, 3.0]})
        assert current == [1.0, 2.0]
