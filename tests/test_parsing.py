"""Tests for the pure parsing/derivation helpers.

These cover the values that have historically gone silently wrong: CRV
reward ranges arriving in four different shapes, pool IDs that key the
history file, and the derived StakeDAO fee.
"""

import pytest

from curve_tracker import CurveTracker


class TestParseCrvRewards:
    """Curve's gauge API returns this field as a 2-list, a 1-list, a scalar,
    a preformatted string, or a list containing Nones."""

    def test_two_element_list_becomes_min_max(self, exporter):
        assert exporter._parse_crv_rewards([3.43, 8.57]) == (3.43, 8.57)

    def test_single_element_list_collapses_to_flat_range(self, exporter):
        assert exporter._parse_crv_rewards([5.0]) == (5.0, 5.0)

    def test_scalar_collapses_to_flat_range(self, exporter):
        assert exporter._parse_crv_rewards(7.25) == (7.25, 7.25)

    def test_string_range_is_parsed(self, exporter):
        assert exporter._parse_crv_rewards("6.07 - 15.18") == (6.07, 15.18)

    def test_none_elements_are_filtered(self, exporter):
        # Regression: the gauge API can return [None, None], which used to
        # raise before commit 97dbd4c.
        assert exporter._parse_crv_rewards([None, None]) == (0.0, 0.0)

    def test_partial_none_list_uses_the_numeric_value(self, exporter):
        assert exporter._parse_crv_rewards([None, 4.2]) == (4.2, 4.2)

    @pytest.mark.parametrize("value", [None, "", "not-a-number", {}, []])
    def test_unparseable_values_default_to_zero(self, exporter, value):
        assert exporter._parse_crv_rewards(value) == (0.0, 0.0)

    def test_zero_is_preserved_not_treated_as_missing(self, exporter):
        assert exporter._parse_crv_rewards(0) == (0.0, 0.0)


class TestGeneratePoolId:
    """Pool IDs key the history file. A change to this function silently
    forks a pool's time series, so its behaviour is a contract."""

    def test_id_combines_chain_and_slugified_name(self, exporter, make_pool):
        pool = make_pool(name="reUSD/scrvUSD", chain="ethereum")
        assert exporter._generate_pool_id(pool) == "ethereum_reusd_scrvusd"

    def test_parenthesised_text_is_stripped(self, exporter, make_pool):
        pool = make_pool(name="AUSD/USDC/USDT0 (3pool)", chain="monad")
        assert exporter._generate_pool_id(pool) == "monad_ausd_usdc_usdt0"

    def test_spaces_and_hyphens_become_underscores(self, exporter, make_pool):
        pool = make_pool(name="frxUSD - FXB 2027", chain="fraxtal")
        assert exporter._generate_pool_id(pool) == "fraxtal_frxusd_fxb_2027"

    def test_id_is_stable_across_calls(self, exporter, make_pool):
        pool = make_pool()
        assert exporter._generate_pool_id(pool) == exporter._generate_pool_id(pool)

    def test_same_name_on_different_chains_does_not_collide(self, exporter, make_pool):
        eth = exporter._generate_pool_id(make_pool(name="3pool", chain="ethereum"))
        arb = exporter._generate_pool_id(make_pool(name="3pool", chain="arbitrum"))
        assert eth != arb


class TestDeriveStakedaoFee:
    """The platform fee is derived from the gap between the gross Curve gauge
    range and StakeDAO's reported net CRV APR, so it must refuse to guess."""

    @staticmethod
    def _stakedao_payload(min_apr, boost, net_crv):
        return {
            "minApr": min_apr,
            "apr": {
                "boost": boost,
                "current": {"details": [{"label": "CRV APR", "value": [net_crv]}]},
            },
        }

    def test_derives_expected_fee(self):
        tracker = CurveTracker()
        # gross = 10 * 2.0 = 20; net = 16 -> 20% fee
        fee = tracker._derive_stakedao_fee(self._stakedao_payload(10.0, 2.0, 16.0))
        assert fee == pytest.approx(20.0)

    def test_returns_none_when_boost_missing(self):
        tracker = CurveTracker()
        assert tracker._derive_stakedao_fee(self._stakedao_payload(10.0, None, 16.0)) is None

    def test_returns_none_when_net_crv_missing(self):
        tracker = CurveTracker()
        payload = {"minApr": 10.0, "apr": {"boost": 2.0, "current": {"details": []}}}
        assert tracker._derive_stakedao_fee(payload) is None

    def test_returns_none_rather_than_a_negative_fee(self):
        # net > gross implies our model is wrong; None beats a bogus number.
        tracker = CurveTracker()
        assert tracker._derive_stakedao_fee(self._stakedao_payload(10.0, 2.0, 25.0)) is None

    def test_returns_none_when_fee_would_be_100_percent_or_more(self):
        tracker = CurveTracker()
        assert tracker._derive_stakedao_fee(self._stakedao_payload(10.0, 2.0, 0.0)) is None

    def test_returns_none_on_zero_gross_emissions(self):
        # Guards the division; near-zero emissions produce absurd rates.
        tracker = CurveTracker()
        assert tracker._derive_stakedao_fee(self._stakedao_payload(0.0, 2.0, 5.0)) is None
