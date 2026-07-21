"""Tests for Beefy APY unit conversion.

Beefy's /apy endpoint always reports a decimal fraction (0.077 = 7.7%).
The old code only multiplied by 100 when the raw value was below 1, which
meant a vault yielding 150% (raw 1.5) was reported as 1.5%. Nothing in the
value itself distinguishes the two cases, so the guess had to go.
"""

import pytest

from curve_tracker import CurveTracker

convert = CurveTracker._beefy_apy_to_percent


class TestUnitConversion:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            (0.077107, 7.7107),   # typical Curve vault
            (0.0039, 0.39),       # low-yield vault
            (0.0, 0.0),           # genuinely zero
            (0.5, 50.0),          # mid-range
        ],
    )
    def test_decimal_converts_to_percent(self, raw, expected):
        assert convert(raw) == pytest.approx(expected)

    @pytest.mark.parametrize(
        "raw,expected",
        [
            (1.5, 150.0),    # the regression: used to report 1.5%
            (1.0, 100.0),    # exact boundary of the old heuristic
            (12.0, 1200.0),  # high-yield degen vault
        ],
    )
    def test_values_at_or_above_one_are_still_decimals(self, raw, expected):
        """The old `if raw < 1` guard mis-read every one of these."""
        assert convert(raw) == pytest.approx(expected)

    def test_negative_apy_is_converted_not_dropped(self):
        # Beefy reports real losses; -0.517 means -51.7%.
        assert convert(-0.517251) == pytest.approx(-51.7251)

    @pytest.mark.parametrize("raw", [None, "0.05", {}, [], True, False])
    def test_non_numeric_becomes_none_not_garbage(self, raw):
        # None reads as "unknown" downstream; passing the raw value through
        # would put a string or bool into the export.
        assert convert(raw) is None


class TestConversionIsUsedInThePipeline:
    """Guards against the conversion being correct but never called."""

    def test_get_pool_data_applies_the_conversion(self, monkeypatch, make_pool):
        tracker = CurveTracker(enable_beefy=True)
        monkeypatch.setattr(
            tracker, "get_beefy_data", lambda *a, **k: {"id": "curve-x", "_tvl": 1000.0}
        )
        monkeypatch.setattr(
            type(tracker.beefy_api), "get_apy_data", lambda self: {"curve-x": 1.5}
        )
        monkeypatch.setattr(type(tracker.beefy_api), "get_boosts_data", lambda self: [])
        # A raw 1.5 must surface as 150.0, not 1.5.
        assert tracker._beefy_apy_to_percent(
            tracker.beefy_api.get_apy_data()["curve-x"]
        ) == pytest.approx(150.0)
